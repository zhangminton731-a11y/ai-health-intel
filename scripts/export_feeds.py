"""Public snapshots and RSS, derived from the same current set as the website."""
from __future__ import annotations
import json
import shutil
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from export_access import export_access

BASE_URL = 'https://zhangminton731-a11y.github.io/ai-health-intel/'

def export_feeds(site: Path, payload: dict, health: dict, briefing: str, skill: Path) -> None:
    api = site / 'api/v1'
    api.mkdir(parents=True, exist_ok=True)
    items = [{
        'id': i['id'], 'title': i['t'] or i['te'], 'original_title': i['te'],
        'summary': i['s'] or i['se'], 'url': i['u'], 'source': i['src'],
        'source_type': i['sourceType'], 'published_at': i['date'],
        'topics': i['topics'], 'event_type': i['event'], 'provenance': i['provenance'],
        'sections': i.get('sections', []), 'categories': i.get('categories', {}),
        'research_stages': i.get('stages', []), 'recommendation_reasons': i.get('reasons', {}),
    } for i in payload['items'] if i['freshness'] == 'fresh' and i['tier'] != 'archive']
    common = {'schema_version': '1.0', 'generated_at': payload['generatedAt'], 'as_of': payload['asOf']}
    for name, data in {
        'items': {**common, 'count': len(items), 'items': items},
        'health': {**common, 'daily_status': health.get('daily_status', 'unknown'), 'sources': health.get('sources', [])},
        'briefing': {**common, 'item_ids': payload.get('dailyIds', payload['top']), 'editions': payload.get('dailyIssues', []), 'edition_date': (payload.get('dailyIssues') or [{}])[0].get('date'), 'text': briefing},
    }.items():
        (api / f'{name}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (api / 'history.json').write_text(json.dumps({**common, 'description': '近20天历史阅读，不属于当前推荐', 'items': payload.get('historyItems', []), 'editions': payload.get('historyIssues', [])}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (api / 'policies.json').write_text(json.dumps(payload.get('policyTimeline', {}), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    rss = ET.Element('rss', {'version': '2.0'})
    channel = ET.SubElement(rss, 'channel')
    for key, value in {'title': payload['name'], 'link': BASE_URL, 'description': 'AI 医疗与消费健康产业情报', 'language': 'zh-cn'}.items():
        ET.SubElement(channel, key).text = value
    if payload['generatedAt']:
        ET.SubElement(channel, 'lastBuildDate').text = format_datetime(datetime.fromisoformat(payload['generatedAt']))
    for i in items:
        entry = ET.SubElement(channel, 'item')
        for key, value in {'title': i['title'], 'link': i['url'], 'description': i['summary']}.items():
            ET.SubElement(entry, key).text = value
        ET.SubElement(entry, 'guid', {'isPermaLink': 'false'}).text = i['id']
        ET.SubElement(entry, 'pubDate').text = format_datetime(datetime.fromisoformat(i['published_at']).replace(tzinfo=timezone.utc))
        for topic in i['topics']:
            ET.SubElement(entry, 'category').text = topic
        for section in i['sections']:
            ET.SubElement(entry, 'category', {'domain': BASE_URL + '#sections'}).text = section
    ET.ElementTree(rss).write(site / 'feed.xml', encoding='utf-8', xml_declaration=True)
    target = site / 'sih-intel'
    target.mkdir(exist_ok=True)
    with zipfile.ZipFile(site / 'sih-intel.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name in ('SKILL.md','README.md'):
            shutil.copyfile(skill / name, target / name)
            bundle.write(skill / name, 'sih-intel/' + name)
    export_access(site)
    (site / '.nojekyll').touch()
