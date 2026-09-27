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
REQUIRED_FILES = ['daily_items.jsonl','source_health.json','daily_briefing.md','daily_briefing_cn.md','site/index.html',
                  'site/api/v1/items.json','site/api/v1/health.json','site/api/v1/briefing.json','site/feed.xml','site/sih-intel.zip']

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
        match=re.search(r'<script id="payload" type="application/json">(.*?)</script>',html,re.S)
        if not match:problems.append('页面缺少情报数据');return problems
        payload=json.loads(match[1])
        feeds={name:json.loads((output/f'site/api/v1/{name}.json').read_text(encoding='utf-8')) for name in ('items','health','briefing')}
        if payload.get('generatedAt')!=health['generated_at'] or payload.get('asOf')!=health['as_of']:
            problems.append('页面与采集不是同一批次')
        for name,feed in feeds.items():
            if feed.get('generated_at')!=health['generated_at'] or feed.get('as_of')!=health['as_of']:
                problems.append(f'{name} 接口不是同一批次')
        current={i['id']:i for i in payload['items'] if i['freshness']=='fresh' and i['tier']!='archive'}
        by_id={i['item_id']:i for i in items}
        expected={i['item_id'] for i in items if i.get('freshness_gate')=='fresh' and i.get('reading_tier')!='archive'}
        if set(current)!=expected:problems.append('网页推荐池与采集筛选结果不一致')
        as_of=date.fromisoformat(health['as_of'])
        for iid,item in current.items():
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
        if feeds['briefing']['item_ids']!=payload['top']:problems.append('日报与网页推荐不一致')
        if feeds['briefing']['text']!=(output/'daily_briefing_cn.md').read_text(encoding='utf-8'):problems.append('日报文件与接口文本不一致')
        if payload.get('briefing')!=feeds['briefing']['text']:problems.append('网页与接口日报文本不一致')
        rss=ET.parse(output/'site/feed.xml')
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
