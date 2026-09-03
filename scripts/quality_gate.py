"""Quality Gate（V1）：结构完整性校验，宽松兜底。

只校验产物存在性与基本结构，不做内容级一票否决；
失败时输出明确清单并以非零码退出（workflow 中 continue-on-error 接住，仅告警）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUTPUT = Path(__file__).resolve().parents[1] / "output"
REQUIRED_FILES = [
    "daily_items.jsonl",
    "daily_briefing.md",
    "daily_briefing_cn.md",
    "site/index.html",
]
ALLOWED_DAILY_STATUS = {"complete", "complete_with_warning", "degraded", "failed"}
HARD_FAIL_STATUS = {"failed"}


def main() -> int:
    problems: list[str] = []

    for rel in REQUIRED_FILES:
        if not (OUTPUT / rel).exists():
            problems.append(f"缺少必需产物: {rel}")

    items_path = OUTPUT / "daily_items.jsonl"
    if items_path.exists():
        lines = [ln for ln in items_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if not lines:
            problems.append("daily_items.jsonl 为空（采集可能整体失败）")
        for i, ln in enumerate(lines[:5], 1):
            try:
                record = json.loads(ln)
                for field in ("item_id", "title", "url"):
                    if field not in record:
                        problems.append(f"daily_items.jsonl 第{i}行缺必填字段: {field}")
            except json.JSONDecodeError:
                problems.append(f"daily_items.jsonl 第{i}行不是合法 JSON")

    health_path = OUTPUT / "source_health.json"
    if health_path.exists():
        try:
            health = json.loads(health_path.read_text(encoding="utf-8"))
            status = health.get("daily_status", "")
            if status not in ALLOWED_DAILY_STATUS:
                problems.append(f"daily_status 非法: {status}")
            if status in HARD_FAIL_STATUS:
                print(f"⚠️ 告警：日健康状态为 failed（宽松兜底，不阻断部署）")
        except json.JSONDecodeError:
            problems.append("source_health.json 不是合法 JSON")

    if problems:
        print("❌ quality gate 未通过：")
        for p in problems:
            print(f"   - {p}")
        return 1

    print("✅ quality gate passed（结构完整性 OK）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
