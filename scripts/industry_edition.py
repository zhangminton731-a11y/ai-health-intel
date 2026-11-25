"""Verified event editions projected onto the existing publication pipeline."""
from datetime import date, datetime, timedelta, timezone
from html import escape
import json
from pathlib import Path
from urllib.parse import urlsplit

from sih_ref.editorial import combine, material, project, validate_review


DIRECTORY = Path(__file__).resolve().parents[1] / 'config/editions'
START = date(2026, 11, 25)
CST = timezone(timedelta(hours=8))
LANES = {'consumer': '消费健康科技', 'medical': '医药研发与临床'}
SOURCE_TYPES = {'官方机构', '企业披露', '原始访谈'}
STAGES = {
    'product': {'concept': '概念展示', 'announced': '正式发布', 'presale': '预售',
                'on_sale': '实售', 'paid_pilot': '付费试点', 'cleared': '获准上市'},
    'policy': {'consultation': '征求意见', 'filing': '信息申报', 'list_announced': '公布名单',
               'announced': '政策公布', 'notices_issued': '各省发文', 'pilot': '试点启动',
               'effective': '正式实施', 'expanded': '推广'},
    'industry': {'signed': '已签约', 'closed': '已完成', 'announced': '已宣布'},
    'opinion': {'published': '行业观点'},
}


def records(edition):
    day = date.fromisoformat(edition['date'])
    updated = datetime.fromisoformat(edition['updated_at'])
    if updated.tzinfo is None or len(edition['events']) > 5:
        raise ValueError('日报更新时间或条数异常')
    update_day = updated.astimezone(CST).date()
    revisions = edition.get('revisions', [])
    revision_days = [date.fromisoformat(revision['date']) for revision in revisions]
    has_later_update = update_day > day
    if (update_day < day or (has_later_update and (not revision_days or revision_days[-1] != update_day)) or
            any(not day <= revision_day <= update_day for revision_day in revision_days) or
            revision_days != sorted(revision_days) or any(not revision['note'].strip() for revision in revisions)):
        raise ValueError('日报更新时间与修订记录不一致')
    rows = []
    for event in edition['events']:
        kind, stage = event['kind'], event['stage']
        source_day, event_day = map(date.fromisoformat, (event['published_at'], event['event_date']))
        if (event['verification'] != 'passed' or event['lane'] not in LANES or
                event['source_type'] not in SOURCE_TYPES or
                stage not in STAGES.get(kind, {}) or not 0 <= (day-source_day).days <= 2 or
                event_day > day or not event['why'].strip() or not event['summary'].strip() or
                not event['evidence'] or event['url'] not in event['evidence'] or
                any(urlsplit(url).scheme != 'https' or not urlsplit(url).hostname for url in event['evidence'])):
            raise ValueError(f'事件证据、日期或阶段不合格: {event["id"]}')
        row = dict(item_id='event:'+event['id'], title=event['original_title'], summary=event['source_excerpt'],
                   url=event['url'], published_at=event['published_at'], source_id=event['source'],
                   event_type=event['stage'], provenance={'evidence_urls': event['evidence']}, reader_event=event)
        reviews = [validate_review(review, material(row)) for review in event['reviews']]
        judgment = combine(reviews, event['source_tier'])
        if not judgment['selected'] or judgment['audiences'] != ['industry'] or reviews[0]['kind'] != kind:
            raise ValueError(f'事件双评未通过: {event["id"]}')
        row['editorial'] = judgment
        rows.append(project(row, {}, day))
    if len({row['item_id'] for row in rows}) != len(rows) or len({row['url'] for row in rows}) != len(rows):
        raise ValueError('同一期存在重复事件或原文')
    return sorted(rows, key=lambda row: -row['editorial']['score'])


def load(as_of, generated_at):
    if as_of < START or not DIRECTORY.is_dir():
        return None
    batches = {}
    published_ids = set()
    for path in sorted(DIRECTORY.glob('????-??-??.json')):
        if path.stem > as_of.isoformat():
            continue
        edition = json.loads(path.read_text(encoding='utf-8'))
        if edition['date'] != path.stem:
            raise ValueError('日报文件日期与期号不一致')
        rows = records(edition)
        if datetime.fromisoformat(edition['updated_at']).astimezone(CST).date() > as_of:
            raise ValueError('日报修订时间晚于当前批次')
        ids = {row['item_id'] for row in rows}
        if published_ids & ids:
            raise ValueError('已出刊事件应在原期号更正')
        published_ids.update(ids)
        batches[path.stem] = (edition, rows)
    day = as_of.isoformat()
    if day not in batches:
        batches[day] = ({'date': day, 'updated_at': generated_at, 'events': []}, [])
    return batches


def public_issue(edition, rows):
    lines = [f'奇点日报 · {edition["date"]}', '']
    for n, row in enumerate(rows):
        event = row['reader_event']
        prefix = '头条 · ' if n == 0 else ''
        lines += [prefix+LANES[event['lane']]+' · '+STAGES[event['kind']][event['stage']], event['title'],
                  event['summary'], event['why'], f'{event["source"]} · {row["published_at"]}', row['url'], '']
    if not rows:
        lines.append('本期暂无通过核验和评分的产业事件。')
    return {'date': edition['date'], 'date_basis': 'publication', 'kind': 'industry_edition',
            'updated_at': edition['updated_at'], 'item_ids': [row['item_id'] for row in rows],
            'headline_id': rows[0]['item_id'] if rows else None, 'minutes': 2 if len(rows) > 2 else 1,
            'revisions': edition.get('revisions', []),
            'source_dates': sorted({row['published_at'] for row in rows}), 'text': '\n'.join(lines)+'\n'}


def overlay(items, rows):
    """Keep collector facts and old IDs while replacing the current recommendation set."""
    ids = {row['item_id'] for row in rows}
    return [dict(item, reading_tier='archive', selection_reasons=['awaiting_industry_verification'])
            for item in items if item['item_id'] not in ids] + rows


def write_report(site, edition, rows, stylesheet):
    def story(row, lead=False):
        event = row['reader_event']
        label = STAGES[event['kind']][event['stage']]
        tag = 'h2' if lead else 'h3'
        if lead:
            label = '头条 · '+LANES[event['lane']]+' · '+label
        return (f'<article class="edition-story"><p class="digest-category">{escape(label)}</p>'
                f'<{tag}>{escape(event["title"])}</{tag}><p>{escape(event["summary"])}</p>'
                f'<p><strong>为什么看</strong> {escape(event["why"])}</p><div class="digest-source">'
                f'<span>{escape(event["source"])}</span><time>{escape(event["published_at"])}</time>'
                f'<a href="{escape(event["url"])}" rel="noopener noreferrer">原文 ↗</a></div></article>')

    day = edition['date']
    updated = datetime.fromisoformat(edition['updated_at']).astimezone(CST).strftime('%Y-%m-%d %H:%M:%S')
    body = '<p>本期暂无通过核验和评分的产业事件。</p>'
    if rows:
        body = story(rows[0], lead=True) + '<div class="edition-lanes">'
        for lane, label in LANES.items():
            stories = ''.join(story(row) for row in rows[1:] if row['reader_event']['lane'] == lane)
            body += f'<section><h2>{label}</h2>{stories or "<p>暂无其他达标事件</p>"}</section>'
        body += '</div>'
    revisions = ''.join(f'<li>{escape(row["date"])} · {escape(row["note"])}</li>' for row in edition.get('revisions', []))
    path = site / 'reports' / day / 'index.html'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>奇点日报 · {day}</title><link rel="stylesheet" href="../../{stylesheet}"></head>'
        f'<body><main><header class="digest-header"><h1>奇点日报 · {day}</h1>'
        f'<p>更新于 {updated}（北京时间）</p>'
        f'<a class="text-link" href="../../#daily?date={day}">切换日期、复制与分享 →</a></header>{body}'
        + ('<h2>修订记录</h2><ul>'+revisions+'</ul>' if revisions else '') +
        '</main></body></html>\n', encoding='utf-8')
