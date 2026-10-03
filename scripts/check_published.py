"""Check the published batch and deduplicate acknowledged notifications."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from notify_feishu import send


URL = 'https://zhangminton731-a11y.github.io/ai-health-intel/api/v1/health.json'
ACTIONS_URL = 'https://github.com/zhangminton731-a11y/ai-health-intel/actions'
CST = timezone(timedelta(hours=8))
PERSISTENT_FAILURE_BATCHES = 3
REMINDER_INTERVAL = timedelta(hours=24)


def problems(health: dict, now: datetime) -> list[str]:
    issues = []
    stamp = datetime.fromisoformat(health['generated_at'])
    age = (now - stamp).total_seconds() / 3600
    local = now.astimezone(CST)
    if age < 0 or age > 36:
        issues.append('距上次成功采集超过 36 小时，或时间异常')
    if local.hour >= 9 and stamp.astimezone(CST).date() < local.date():
        issues.append('今天的早间更新尚未上线')
    if health.get('daily_status') != 'complete':
        issues.append('部分信源采集异常')
    return issues


def failed_sources(health: dict) -> list[dict]:
    return [source for source in health.get('sources', [])
            if source.get('enabled') and source.get('status') == 'failed']


def failure_code(source: dict) -> str:
    for check in reversed(source.get('checks', [])):
        if check.get('error_code'):
            return check['error_code']
    return 'unknown'


def alert_fingerprint(issues: list[str], health: dict) -> str:
    # Batch timestamps and exact counts change every run, but not the incident.
    sources = sorted(
        (source['source_id'], failure_code(source),
         source.get('consecutive_failures', 0) >= PERSISTENT_FAILURE_BATCHES)
        for source in failed_sources(health)
    )
    payload = json.dumps([issues, sources], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def alert_message(issues: list[str], health: dict) -> str:
    lines = ['奇点医研异常：' + '；'.join(issues)]
    for source in failed_sources(health):
        count = source.get('consecutive_failures')
        count_text = f'连续 {count} 批失败' if count is not None else '连续失败次数未知'
        last_success = source.get('last_success_at') or '未知'
        lines.append(f"{source['source_id']}：{failure_code(source)}，{count_text}，"
                     f'最后成功 {last_success}')
    lines.append('请检查：' + ACTIONS_URL)
    return '\n'.join(lines)


def load_receipt(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(state, dict):
            raise ValueError('invalid receipt')
        if state:
            stamp = datetime.fromisoformat(state['sent_at'])
            if stamp.tzinfo is None:
                raise ValueError('missing timezone')
            if state['status'] not in {'alert', 'healthy'}:
                raise ValueError('invalid status')
        return state
    except (OSError, ValueError, KeyError, TypeError):
        print('::warning::通知回执不可读，下一次异常将重新尝试通知。')
        return {}


def notify_if_needed(issues: list[str], health: dict, now: datetime, state_path: Path) -> str:
    state = load_receipt(state_path)
    if issues:
        fingerprint = alert_fingerprint(issues, health)
        if state.get('status') == 'alert' and state.get('fingerprint') == fingerprint:
            age = now - datetime.fromisoformat(state['sent_at'])
            if timedelta(0) <= age < REMINDER_INTERVAL:
                print('相同异常已确认送达，24 小时内不重复通知。')
                return 'suppressed'
        message = alert_message(issues, health)
        status = 'alert'
    elif state.get('status') == 'alert':
        message = '奇点医研已恢复：线上批次与来源状态正常。\n' + ACTIONS_URL
        fingerprint = ''
        status = 'healthy'
    else:
        return 'unchanged'

    # Missing configuration and rejected/failed delivery must remain retryable.
    result = send(message)
    if result == 'sent':
        receipt = {'status': status, 'fingerprint': fingerprint, 'sent_at': now.isoformat()}
        state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(receipt), encoding='utf-8')
        temporary.replace(state_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-file', type=Path, default=Path('.monitor-state/receipt.json'))
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    health = {}
    try:
        request = Request(URL, headers={
            'User-Agent': 'SIH-status-monitor/1.0',
            'Cache-Control': 'no-cache',
        })
        with urlopen(request, timeout=20) as response:
            health = json.load(response)
        issues = problems(health, now)
    except Exception:
        health = {}
        issues = ['无法读取或解析已发布的网站健康数据']
    if issues:
        print(alert_message(issues, health))
    else:
        print('线上批次正常。')
    try:
        notify_if_needed(issues, health, now, args.state_file)
    except Exception:
        print('::error::飞书通知或回执保存失败，请检查配置与网络。')
        return 1
    # Notification suppression never turns an unhealthy batch into a green check.
    return 1 if issues else 0


if __name__ == '__main__':
    raise SystemExit(main())
