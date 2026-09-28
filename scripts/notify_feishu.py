"""Notify June through an explicitly configured Feishu bot; never print secrets."""
from __future__ import annotations
import argparse
import base64
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def message_payload(message: str, secret: str = '', timestamp: int | None = None) -> dict:
    payload={'msg_type':'text','content':{'text':message}}
    if secret:
        stamp=str(timestamp if timestamp is not None else int(time.time()))
        signature=base64.b64encode(hmac.new(f'{stamp}\n{secret}'.encode(),b'',hashlib.sha256).digest()).decode()
        payload.update(timestamp=stamp,sign=signature)
    return payload


def send(message: str) -> str:
    endpoint=os.environ.get('FEISHU_BOT_WEBHOOK','')
    if not endpoint:
        print('::warning::飞书通知未启用：尚未配置 FEISHU_BOT_WEBHOOK。')
        return 'not_configured'
    parsed=urlsplit(endpoint)
    if parsed.scheme!='https' or parsed.hostname not in ('open.feishu.cn','open.larksuite.com') or not parsed.path.startswith('/open-apis/bot/v2/hook/'):
        raise ValueError('飞书机器人地址格式不正确')
    payload=message_payload(message,os.environ.get('FEISHU_BOT_SECRET',''))
    request=Request(endpoint,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
    with urlopen(request,timeout=15) as response:result=json.load(response)
    if result.get('code',result.get('StatusCode'))!=0:raise RuntimeError('飞书未确认通知成功')
    print('飞书已确认通知送达。')
    return 'sent'


def main() -> int:
    parser=argparse.ArgumentParser();parser.add_argument('--message',required=True);args=parser.parse_args()
    try:send(args.message);return 0
    except Exception:
        print('::error::飞书通知发送失败，请检查机器人配置或网络；未输出敏感地址。')
        return 1

if __name__=='__main__':raise SystemExit(main())
