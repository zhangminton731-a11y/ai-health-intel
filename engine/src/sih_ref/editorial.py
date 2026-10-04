"""Auditable reading-value judgments. No keyword-derived fallback scores."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .core import freshness_gate, text, write_json_atomic
from .intelligence import _endpoint, _extract_json

AXES = ('significance', 'novelty', 'evidence', 'relevance', 'usefulness')
WEIGHTS = {'research': (3, 2, 3, 1, 1), 'product': (2, 2, 2, 2, 2),
           'method': (1, 2, 2, 1, 4), 'industry': (3, 2, 2, 3, 0),
           'policy': (3, 1, 3, 2, 1), 'opinion': (2, 3, 2, 2, 1)}
THRESHOLDS = {'T1': 70, 'T1_5': 72, 'T2': 76}
PROMPT = (Path(__file__).parent / 'prompts/reading_value.md').read_text(encoding='utf-8')
VERSION = hashlib.sha256((PROMPT + json.dumps([WEIGHTS, THRESHOLDS, 98, 20])).encode()).hexdigest()[:16]


def material(item):
    return {'title': text(item.get('title'))[:400],
            'summary': text(html.unescape(re.sub(r'<[^>]*>', ' ', item.get('summary') or '')))[:12000]}


def validate_review(raw, content):
    if not isinstance(raw, dict) or raw.get('kind') not in WEIGHTS:
        raise ValueError('invalid content kind')
    axes = raw.get('axes')
    if not isinstance(axes, dict) or set(axes) != set(AXES) or any(type(v) is not int or not 0 <= v <= 10 for v in axes.values()):
        raise ValueError('five integer axes required')
    audience = raw.get('audiences')
    if not isinstance(audience, list) or any(a not in ('research', 'industry') for a in audience):
        raise ValueError('invalid audiences')
    reason, support = text(raw.get('reason')), text(raw.get('support'))
    if not 10 <= len(reason) <= 500 or not re.search(r'[\u4e00-\u9fff]', reason):
        raise ValueError('Chinese reading reason required')
    if len(support) < 15 or support not in text(content['title'] + ' ' + content['summary']):
        raise ValueError('support must be a verbatim material excerpt')
    total = sum(axes[key] * weight for key, weight in zip(AXES, WEIGHTS[raw['kind']]))
    return {'kind': raw['kind'], 'axes': axes, 'total': total,
            'audiences': sorted(set(audience)), 'reason': reason, 'support': support[:200]}


def request_review(content, provider):
    endpoint = _endpoint(provider)
    key = os.environ.get(provider.get('api_key_env', 'SIH_LLM_API_KEY'), '').strip()
    model = text(provider.get('model') or os.environ.get(provider.get('model_env', 'SIH_LLM_MODEL')))
    if not key or not model:
        raise ValueError('model credentials not configured')
    body = {'model': model, 'messages': [{'role': 'system', 'content': PROMPT},
            {'role': 'user', 'content': json.dumps(content, ensure_ascii=False)}],
            'max_tokens': 4096, **provider.get('request_options', {})}
    url = endpoint if endpoint.endswith('/chat/completions') else endpoint + '/chat/completions'
    started = time.monotonic()
    for attempt in range(2):
        try:
            request = Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
            with urlopen(request, timeout=int(provider.get('timeout_seconds', 90))) as response:
                payload = json.loads(response.read())
            choice = payload['choices'][0]
            if choice.get('finish_reason') not in (None, 'stop'):
                raise ValueError('incomplete model response')
            result = validate_review(_extract_json(choice['message']['content']), content)
            result['receipt'] = {'request_id': text(payload.get('id')), 'model': text(payload.get('model') or model),
                                 'usage': payload.get('usage', {}), 'seconds': round(time.monotonic() - started, 2)}
            return result
        except HTTPError as exc:
            if attempt == 0 and (exc.code == 429 or exc.code >= 500):
                time.sleep(2)
                continue
            # Never put provider response bodies, request headers or keys in public diagnostics.
            raise RuntimeError('model_http_' + str(exc.code)) from None
        except (URLError, TimeoutError):
            if attempt == 0:
                time.sleep(2)
                continue
            raise RuntimeError('model_connection_failed') from None
        except (ValueError, KeyError, TypeError):
            if attempt == 0:
                continue
            raise ValueError('invalid model judgment') from None


def combine(reviews, source_tier):
    if len(reviews) != 2:
        raise ValueError('two independent reviews required')
    score = min(98, sum(r['total'] for r in reviews) // 2)
    audiences = sorted(set(reviews[0]['audiences']) & set(reviews[1]['audiences']))
    disputed = abs(reviews[0]['total'] - reviews[1]['total']) > 20 or reviews[0]['kind'] != reviews[1]['kind']
    threshold = THRESHOLDS.get(source_tier, THRESHOLDS['T2'])
    selected = bool(audiences) and score >= threshold and not disputed and source_tier != 'EXCLUDE_MP'
    return {'status': 'needs_review' if disputed else 'scored', 'score': score, 'selected': selected,
            'source_tier': source_tier, 'threshold': threshold, 'audiences': audiences,
            'reviews': reviews, 'reason': min(reviews, key=lambda r: r['total'])['reason'],
            'input_scope': 'source_summary', 'policy_version': VERSION}


def project(item, profile, as_of):
    """Apply an existing editorial receipt without assigning a keyword score."""
    result = dict(item)
    gate = freshness_gate(item, as_of, int(profile.get('freshness_days', 10)))
    judgment = item.get('editorial') or {'status': 'pending', 'selected': False}
    current = gate == 'fresh' and judgment.get('selected') and judgment.get('policy_version') == VERSION
    result.update(editorial=judgment, topic_relevance=(judgment['score'] / 100 if current else 0),
                  method_novelty_hint=0, freshness_gate=gate,
                  reading_tier=('must_read' if judgment.get('score', 0) >= 85 else 'skim') if current else 'archive',
                  selection_audiences=judgment.get('audiences', []),
                  selection_reasons=['editorial_selected' if current else gate if gate != 'fresh' else judgment.get('status', 'pending')],
                  content_status='source_summary' if text(item.get('summary')) else 'title_only')
    return result


def evaluate(items, profile, provider, cache_dir, as_of):
    """Two separate requests per changed fresh article; bounded concurrency and cached receipts."""
    model = text(provider.get('model') or os.environ.get(provider.get('model_env', 'SIH_LLM_MODEL')))
    configured = bool(provider.get('enabled') and model and os.environ.get(provider.get('api_key_env', 'SIH_LLM_API_KEY')))
    if configured:
        endpoint = _endpoint(provider)
    else:
        endpoint = ''
    tiers = profile.get('editorial', {}).get('source_tiers', {})
    def one(item):
        row = project({**item, 'editorial': None}, profile, as_of)
        content = material(item)
        if row['freshness_gate'] != 'fresh' or len(content['summary']) < 80:
            row['editorial'] = {'status': 'ineligible' if row['freshness_gate'] != 'fresh' else 'insufficient_material', 'selected': False}
            return row
        if not configured:
            row['editorial'] = {'status': 'unconfigured', 'selected': False}
            return row
        tier = tiers.get(item.get('source_id'), 'T2')
        digest = hashlib.sha256(json.dumps([content, model, endpoint, provider.get('request_options'), VERSION, tier], sort_keys=True).encode()).hexdigest()
        path = cache_dir / (digest + '.json')
        try:
            if path.exists():
                saved = json.loads(path.read_text(encoding='utf-8'))
                reviews = [{**validate_review(r, content), 'receipt': r['receipt']} for r in saved['reviews']]
                judgment = combine(reviews, tier)
                judgment['evaluated_at'] = saved['evaluated_at']
            else:
                reviews = [request_review(content, provider) for _ in range(2)]
                judgment = combine(reviews, tier)
                judgment['evaluated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
                write_json_atomic(path, judgment)
            judgment['input_hash'] = digest
            row['editorial'] = judgment
        except Exception as exc:
            row['editorial'] = {'status': 'failed', 'selected': False, 'error_type': type(exc).__name__}
        return project(row, profile, as_of)
    with ThreadPoolExecutor(max_workers=min(4, max(1, int(provider.get('max_workers', 2))))) as pool:
        rows = list(pool.map(one, items))
    counts = {}
    for row in rows:
        status = row['editorial']['status']
        counts[status] = counts.get(status, 0) + 1
    return rows, {'status': 'warning' if any(counts.get(k) for k in ('failed', 'unconfigured', 'needs_review')) else 'ok',
                  'model': model, 'policy_version': VERSION, 'counts': counts,
                  'selected': sum(bool(r['editorial'].get('selected')) for r in rows)}


def restore_receipts(items_path, cache_dir):
    """Seed a new runner from published receipts; evaluate() revalidates every cache hit."""
    if not items_path.exists():
        return
    for line in items_path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        judgment = json.loads(line).get('editorial') or {}
        digest = judgment.get('input_hash', '')
        if judgment.get('policy_version') == VERSION and re.fullmatch(r'[a-f0-9]{64}', digest):
            path = cache_dir / (digest + '.json')
            if not path.exists():
                write_json_atomic(path, judgment)
