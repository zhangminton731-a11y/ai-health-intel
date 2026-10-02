"""Track source failures independently of whether a batch may be published."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def load_history(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        history = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(history, dict):
            raise ValueError("expected object")
        for entry in history.values():
            if not isinstance(entry, dict):
                raise ValueError("expected source state")
            count = entry.get("consecutive_failures", 0)
            if not isinstance(count, int) or count < 0:
                raise ValueError("invalid failure count")
            if entry.get("retry_not_before"):
                deadline = datetime.fromisoformat(entry["retry_not_before"])
                if deadline.tzinfo is None:
                    raise ValueError("missing timezone")
        return history
    except (ValueError, OSError, TypeError):
        # Missing history is not evidence of a previously healthy source.
        print("::warning::来源健康历史不可读；本轮重新计数，最后成功时间未知。")
        return {}


def update_source_health(manifest: dict, history: dict) -> None:
    """Add observation state in place; inactive sources do not count as failures."""
    source_id = manifest["source_id"]
    previous = history.get(source_id, {})
    failures = previous.get("consecutive_failures", 0)
    last_success = previous.get("last_success_at")
    if manifest["status"] == "inactive":
        manifest.update(last_success_at=last_success, consecutive_failures=failures, recovered=False)
        return
    if manifest["status"] in {"ok", "ok_no_updates"}:
        recovered = failures > 0
        failures = 0
        last_success = manifest["generated_at"]
    elif manifest["status"] == "failed":
        recovered = False
        if not any(check.get("request_deferred") for check in manifest["checks"]):
            failures += 1
    else:
        recovered = False
    state = {
        "last_success_at": last_success,
        "consecutive_failures": failures,
        "last_checked_at": manifest["generated_at"],
    }
    if manifest["status"] == "failed" and manifest["checks"]:
        last_check = manifest["checks"][-1]
        if last_check.get("retry_not_before"):
            state["retry_not_before"] = last_check["retry_not_before"]
            state["error_code"] = last_check.get("error_code", "unknown")
    manifest.update(state, recovered=recovered)
    history[source_id] = state


def deferred_retry(source: dict, history: dict, run_at: str) -> dict | None:
    """Do not contact a rate-limited server before its cross-run deadline."""
    if not source.get("enabled") or source.get("kind") != "rss":
        return None
    previous = history.get(source["id"], {})
    deadline = previous.get("retry_not_before")
    if deadline and datetime.fromisoformat(run_at) < datetime.fromisoformat(deadline):
        return {
            "kind": "rss_retry_window",
            "request_deferred": True,
            "retry_not_before": deadline,
            "error_code": previous.get("error_code", "unknown"),
        }
    return None
