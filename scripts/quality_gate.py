"""Fail closed when collection and published projections disagree."""
from __future__ import annotations
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
OUTPUT = Path(__file__).resolve().parents[1] / 'output'
sys.path.insert(0, str(OUTPUT.parent / 'engine/src'))
from sih_ref.editorial import VERSION, combine, material, validate_review
REQUIRED_FILES = ['daily_items.jsonl','source_health.json','daily_briefing.md','daily_briefing_cn.md','site/index.html',
                  'site/api/v1/items.json','site/api/v1/health.json','site/api/v1/briefing.json','site/feed.xml','site/sih-intel.zip',
                  'site/sih-intel/README.md','site/sih-mcp.zip','site/sih-mcp/README.md','site/llms.txt','site/openapi.json']

def validate(output: Path, now: datetime | None = None) -> list[str]:
    problems = [f'缺少必需产物: {rel}' for rel in REQUIRED_FILES if not (output/rel).is_file()]
    if problems:
        return problems
    try:
        health = json.loads((output/'source_health.json').read_text(encoding='utf-8'))
        items=[]
        for number,line in enumerate((output/'daily_items.jsonl').read_text(encoding='utf-8').splitlines(),1):
            if not line.strip():continue
            try:
                item=json.loads(line)
                if not isinstance(item,dict) or not all(item.get(k) for k in ('item_id','title','url')):
                    problems.append(f'第 {number} 条缺少必需字段')
                elif urlsplit(item['url']).scheme not in ('http','https'):
                    problems.append(f'第 {number} 条原文地址非法')
                else:items.append(item)
            except (json.JSONDecodeError,TypeError,ValueError):problems.append(f'第 {number} 条不是合法情报 JSON')
        if len({i['item_id'] for i in items}) != len(items):problems.append('事实池存在重复 ID')
        if health.get('daily_status') not in ('complete','complete_with_warning'):problems.append('采集状态不允许发布')
        active=[s for s in health.get('sources',[]) if s.get('enabled')]
        loaded=sum(s.get('status') in ('ok','ok_no_updates') for s in active)
        if not active or loaded < max(1,(len(active)+1)//2):problems.append('成功来源不足一半')
        generated=datetime.fromisoformat(health['generated_at'])
        if generated.tzinfo is None:problems.append('采集时间缺少时区')
        else:
            age=((now or datetime.now(timezone.utc))-generated).total_seconds()
            if not 0<=age<=36*3600:problems.append('采集时间异常或已超过 36 小时')
            if generated.astimezone(timezone(timedelta(hours=8))).date().isoformat()!=health['as_of']:
                problems.append('批次日期与北京采集日期不一致')
        html=(output/'site/index.html').read_text(encoding='utf-8')
        for asset in re.findall(r'(?:href|src)="(assets/site\.[a-f0-9]+\.(?:css|js))"',html):
            if not (output/'site'/asset).is_file(): problems.append('缺少页面资源: '+asset)
        match=re.search(r'<script id="payload" type="application/json">(.*?)</script>',html,re.S)
        if not match:problems.append('页面缺少情报数据');return problems
        payload=json.loads(match[1])
        feeds={name:json.loads((output/f'site/api/v1/{name}.json').read_text(encoding='utf-8')) for name in ('items','health','briefing')}
        if feeds['health'].get('coverage',{}) != payload.get('coverage',{}): problems.append('内容覆盖诊断与页面不一致')
        if payload.get('generatedAt')!=health['generated_at'] or payload.get('asOf')!=health['as_of']:
            problems.append('页面与采集不是同一批次')
        for name,feed in feeds.items():
            if feed.get('generated_at')!=health['generated_at'] or feed.get('as_of')!=health['as_of']:
                problems.append(f'{name} 接口不是同一批次')
        current={i['id']:i for i in payload['items'] if i['freshness']=='fresh' and i['tier']!='archive'}
        if any(row.get('rel') is not None and not 0 <= row['rel'] <= 98 for row in payload['items'] + payload.get('historyItems', [])):
            problems.append('推荐指数超出 0–98 范围')
        by_id={i['item_id']:i for i in items}
        expected={i['item_id'] for i in items if i.get('freshness_gate')=='fresh' and i.get('reading_tier')!='archive'}
        if set(current)!=expected:problems.append('网页推荐池与采集筛选结果不一致')
        as_of=date.fromisoformat(health['as_of'])
        for iid,item in current.items():
            judgment = by_id[iid].get('editorial')
            if judgment is not None:
                try:
                    reviews = [validate_review(r, material(by_id[iid])) for r in judgment['reviews']]
                    checked = combine(reviews, judgment['source_tier'])
                    if len(item.get('sections', [])) != 1 or item['sections'] != checked['audiences']:
                        problems.append('当前文章必须只有一个经双次评审一致确认的主板块')
                    if (not checked['selected'] or judgment.get('policy_version') != VERSION or
                            item.get('rel') != checked['score'] or judgment.get('score') != checked['score']):
                        problems.append('编辑评分与分项、策略或入选结果不一致')
                except (KeyError, ValueError, TypeError):
                    problems.append('缺少有效双次编辑评分回执')
            age_days=(as_of-date.fromisoformat(item['date'])).days
            if not 0<=age_days<=10:problems.append('当前推荐中存在日期越界条目')
            if item['u']!=by_id[iid]['url']:problems.append('原文溯源不一致')
        if set(i['id'] for i in feeds['items']['items'])!=set(current):problems.append('API 与网页推荐池不一致')
        for item in feeds['items']['items']:
            page_item=current.get(item['id'],{})
            if (item.get('sections',[])!=page_item.get('sections',[]) or
                item.get('categories',{})!=page_item.get('categories',{}) or
                item.get('research_stages',[])!=page_item.get('stages',[])):
                problems.append('API 与网页栏目分类不一致')
        if not set(payload['top']).issubset(current) or not set(i['id'] for i in payload['hot30']).issubset(current):
            problems.append('榜单包含不合格条目')
        if len(payload['top'])>10 or len(payload['hot30'])>30:problems.append('榜单超出约定上限')
        if feeds['briefing']['item_ids']!=payload.get('dailyIds', payload['top']):problems.append('日报与网页推荐不一致')
        if feeds['briefing']['text']!=(output/'daily_briefing_cn.md').read_text(encoding='utf-8'):problems.append('日报文件与接口文本不一致')
        if payload.get('briefing')!=feeds['briefing']['text']:problems.append('网页与接口日报文本不一致')
        editions = payload.get('dailyIssues', [])
        publication = payload.get('publicationIssue')
        if publication is not None:
            if feeds['briefing'].get('publication') != publication:problems.append('出刊日报与接口不一致')
            if publication.get('date') != health['as_of'] or publication.get('date_basis') != 'publication':problems.append('出刊日期不正确')
            ids = publication.get('item_ids', [])
            if len(ids) > 5 or len(set(ids)) != len(ids):problems.append('出刊日报条数异常')
            if any(iid not in current or not 0 <= (as_of-date.fromisoformat(current[iid]['date'])).days <= 2 for iid in ids):problems.append('出刊日报含过期或不合格内容')
            if publication.get('source_dates') != sorted({current[iid]['date'] for iid in ids if iid in current}):problems.append('出刊日报原文日期不一致')
        if feeds['briefing'].get('editions', []) != editions:problems.append('日报日期目录与接口不一致')
        if 'dailyIssues' in payload and payload.get('dailyIds') != (editions[0]['item_ids'] if editions else []):problems.append('最新日报与目录不一致')
        if feeds['briefing'].get('edition_date') != (editions[0]['date'] if editions else None):problems.append('日报日期与接口不一致')
        for edition in editions:
            ids = edition['item_ids']
            if not 1 <= len(ids) <= 5 or len(set(ids)) != len(ids):problems.append('日报条数或去重异常')
            if any(iid not in current or current[iid]['date'] != edition['date'] for iid in ids):problems.append('日报包含非当日或不合格条目')
        rss=ET.parse(output/'site/feed.xml')
        for month in payload.get('archiveMonths', []):
            key = month['month']
            if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', key):
                problems.append('月度档案名称异常')
                continue
            archive = json.loads((output/'site/api/v1/archive'/f'{key}.json').read_text(encoding='utf-8'))
            raw = json.loads((output/'archives'/f'{key}.json').read_text(encoding='utf-8'))
            originals = {row['item_id']: row for row in raw['records']}
            archived = {row['id']: row for row in archive['items']}
            if archive['kind'] != 'retrospective' or archive['month'] != key or len(archived) != month['item_count']:
                problems.append('月度档案统计或类型不一致')
            for row in archive['items']:
                if row.get('rel') is not None and not 0 <= row['rel'] <= 98:
                    problems.append('月度推荐指数超出 0–98 范围')
                original = originals.get(row['id'], {})
                if row['u'] != original.get('url') or row['date'] != original.get('published_at') or not row['date'].startswith(key+'-') or row.get('archiveMonth') != key:
                    problems.append('月度档案原文或日期不一致')
            if len(raw['records']) != month['record_count']:
                problems.append('月度档案原始记录数不一致')
            for issue in archive['editions']:
                ids = issue['item_ids']
                if issue.get('kind') != 'retrospective' or not 1 <= len(ids) <= 5 or len(set(ids)) != len(ids) or any(iid not in archived or archived[iid]['date'] != issue['date'] for iid in ids):
                    problems.append('历史日报含非当日、重复或未知条目')
        if 'historyItems' in payload:
            historical=payload['historyItems']
            originals={i['item_id']:i for i in map(json.loads,(output/'history_items.jsonl').read_text(encoding='utf-8').splitlines())}
            history_feed=json.loads((output/'site/api/v1/history.json').read_text(encoding='utf-8'))
            if history_feed['items']!=historical or history_feed['editions']!=payload['historyIssues']:problems.append('历史接口与网页不一致')
            if len({i['id'] for i in historical})!=len(historical):problems.append('历史记录重复')
            for item in historical:
                if item['id'] in current:problems.append('历史与当前推荐重复')
                original=originals.get(item['id'],{})
                if item['u']!=original.get('url') or item['date']!=original.get('published_at'):problems.append('历史原文或日期不一致')
                if not 0<=(as_of-date.fromisoformat(item['date'])).days<=20:problems.append('历史日期越界')
            if json.loads((output/'site/api/v1/policies.json').read_text(encoding='utf-8'))!=payload['policyTimeline']:problems.append('政策接口与网页不一致')
        if {x.findtext('guid') for x in rss.findall('./channel/item')}!=set(current):problems.append('RSS 与网页推荐池不一致')
        if len(payload['items'])!=len(items):problems.append('事实池与页面总量不一致')
    except (ValueError,KeyError,TypeError,AttributeError,OSError,ET.ParseError) as exc:
        problems.append(f'产物结构异常: {type(exc).__name__}')
    return problems

def main() -> int:
    problems=validate(OUTPUT)
    if problems:
        print('❌ quality gate 未通过：\n'+'\n'.join('  - '+p for p in problems))
        return 1
    print('✅ quality gate passed（全记录、批次、时效与公开投影一致）')
    return 0

if __name__=='__main__':sys.exit(main())
