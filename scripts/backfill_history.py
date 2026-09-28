"""Backfill public RSS pages without relabeling their original dates."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine/src'))
from sih_ref.sources import collect_source
from sih_ref.core import normalize_item
from reader_context import update_history

def main():
    today=datetime.now(timezone(timedelta(hours=8))).date()
    config=json.loads((ROOT/'config/sources.json').read_text(encoding='utf-8'))
    source=next(s for s in config['sources'] if s['id']=='medcity_news')
    pages=[{**source,'url':f'https://medcitynews.com/feed/?paged={n}','max_results':100} for n in range(2,6)]
    def get(page):
        return page,collect_source(page,base_dir=ROOT/'config',live=True,as_of=today)
    rows=[];audit=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for page,result in pool.map(get,pages):
            audit.append({'url':page['url'],'status':result.status,'count':len(result.items),'error':result.error})
            rows.extend(normalize_item(i,page) for i in result.items)
    profile=json.loads((ROOT/'config/profile.json').read_text(encoding='utf-8'))
    selected=update_history(ROOT/'output/history_items.jsonl',rows,profile,today)
    report={'as_of':str(today),'pages':audit,'history_count':len(selected),'dates':sorted(set(r['published_at'] for r in selected))}
    (ROOT/'output/history-backfill-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
