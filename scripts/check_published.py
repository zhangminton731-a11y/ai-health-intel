"""Check the published site, not only the repository's last collection."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from notify_feishu import send

URL='https://zhangminton731-a11y.github.io/ai-health-intel/api/v1/health.json'
CST=timezone(timedelta(hours=8))

def problems(health: dict, now: datetime) -> list[str]:
    issues=[]
    stamp=datetime.fromisoformat(health['generated_at'])
    age=(now-stamp).total_seconds()/3600
    local=now.astimezone(CST)
    if age<0 or age>36:issues.append('距上次成功采集超过 36 小时，或时间异常')
    if local.hour>=9 and stamp.astimezone(CST).date()<local.date():issues.append('今天的早间更新尚未上线')
    if health.get('daily_status')!='complete':issues.append('部分信源采集异常')
    return issues

def main() -> int:
    try:
        req=Request(URL,headers={'User-Agent':'SIH-status-monitor/1.0','Cache-Control':'no-cache'})
        with urlopen(req,timeout=20) as response:health=json.load(response)
        issues=problems(health,datetime.now(timezone.utc))
    except Exception:issues=['无法读取或解析已发布的网站健康数据']
    if not issues:
        print('线上批次正常，无需通知。');return 0
    message='循证人初异常：'+'；'.join(issues)+'。\n请检查：https://github.com/zhangminton731-a11y/ai-health-intel/actions'
    print(message)
    try:send(message)
    except Exception:print('::error::飞书通知发送失败，请检查机器人配置或网络。')
    return 1

if __name__=='__main__':raise SystemExit(main())
