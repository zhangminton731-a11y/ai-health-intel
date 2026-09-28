"""Offline backend for a real stdio protocol test; never distributed."""
from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/mcp'))
from server import create_server

def load(name):
    stamp=datetime.now(timezone.utc)
    common={'generated_at':stamp.isoformat(),'as_of':stamp.astimezone(timezone(timedelta(hours=8))).date().isoformat()}
    if name=='briefing':raise RuntimeError('Test backend unavailable')
    if name=='health':return {**common,'daily_status':'complete','sources':[]}
    return {**common,'items':[{'id':'fixture','title':'AI 医学论文','published_at':common['as_of'],'url':'https://example.org/paper','sections':['research'],'categories':{'research':['papers']},'research_stages':['analysis']}]}

if __name__=='__main__':create_server(load).run(transport='stdio')
