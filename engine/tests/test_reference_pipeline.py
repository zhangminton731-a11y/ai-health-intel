from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sih_ref.core import PUBLIC_ITEM_FIELDS, classify_daily_health, normalize_date, normalize_item, public_item  # noqa: E402
from sih_ref.delivery import publish_webhook  # noqa: E402
from sih_ref.pipeline import run_pipeline  # noqa: E402
from sih_ref.render import render_site  # noqa: E402
from sih_ref.sources import NETWORK_SOURCE_KINDS, collect_source  # noqa: E402
from sih_ref.core import apply_incremental, freshness_gate, score_item  # noqa: E402

sys.path.insert(0, str(ROOT.parent / "scripts"))
import build_site  # noqa: E402


class FreshnessTests(unittest.TestCase):
    as_of = date(2026, 9, 7)
    profile = {"freshness_days": 10, "topic_terms": {"wellness": 1}}

    def item(self, published="2026-09-07", name="fresh"):
        return normalize_item({"title": f"wellness {name}", "summary": f"{name} {name}",
                               "url": f"https://example.org/{name}", "published_at": published},
                              {"id": "fixture", "kind": "rss"})

    def test_day_zero(self):
        self.assertEqual("fresh", freshness_gate(self.item(), self.as_of, 10))

    def test_day_ten(self):
        self.assertEqual("fresh", freshness_gate(self.item("2026-08-28"), self.as_of, 10))

    def test_day_eleven(self):
        self.assertEqual("stale", freshness_gate(self.item("2026-08-27"), self.as_of, 10))

    def test_tomorrow(self):
        self.assertEqual("future", freshness_gate(self.item("2026-09-08"), self.as_of, 10))

    def test_far_future(self):
        self.assertEqual("future", freshness_gate(self.item("2027-01-01"), self.as_of, 10))

    def test_missing_date_archived(self):
        result = score_item(self.item(None), self.profile, self.as_of)
        self.assertEqual(("undated", "archive"), (result["freshness_gate"], result["reading_tier"]))

    def test_invalid_date_archived(self):
        for value in ("nonsense", "2026-02-30"):
            with self.subTest(value=value):
                result = score_item({**self.item(), "published_at": value}, self.profile, self.as_of)
                self.assertEqual(("undated", "archive"), (result["freshness_gate"], result["reading_tier"]))

    def build_fixture(self, items, as_of=None, health=None):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / "site").mkdir()
            raw = "\n".join(json.dumps(item) for item in items)
            (output / "daily_items.jsonl").write_text(raw, encoding="utf-8")
            with patch.object(build_site, "OUTPUT", output), patch.object(build_site, "load_health", return_value=health or {}), \
                 patch.object(build_site.Translator, "zh", return_value=None), patch.object(build_site, "save_cache"):
                build_site.build(as_of=as_of or self.as_of)
            html = (output / "site/index.html").read_text(encoding="utf-8")
            payload = json.loads(re.search(r'<script id="payload" type="application/json">(.*?)</script>', html, re.S).group(1))
            briefing = (output / "daily_briefing_cn.md").read_text(encoding="utf-8")
            self.assertEqual(raw, (output / "daily_items.jsonl").read_text(encoding="utf-8"))
            return payload, briefing, html

    def test_all_views_exclude_noncurrent_and_preserve_archive(self):
        items = [self.item(), self.item("2026-08-27", "stale"),
                 self.item("2026-09-08", "future"), self.item(None, "undated")]
        # Simulate old persisted labels and higher scores on excluded records.
        items = [{**it, "freshness_gate": "fresh", "reading_tier": "skim", "topic_relevance": 1} for it in items]
        payload, briefing, _ = self.build_fixture(items)
        self.assertEqual([items[0]["item_id"]], payload["top"])
        self.assertEqual(payload["top"], [it["id"] for it in payload["hot30"]])
        self.assertEqual([], payload["kws"])  # Only one eligible wellness occurrence.
        for name in ("stale", "future", "undated"):
            self.assertNotIn(f"https://example.org/{name}", briefing)
        self.assertEqual(4, len(payload["items"]))
        self.assertTrue(all(it["tier"] == "archive" for it in payload["items"][1:]))
        self.assertEqual({"fresh": 1, "stale": 1, "future": 1, "undated": 1}, payload["freshnessCounts"])

    def test_all_stale_never_backfilled(self):
        items = [{**self.item("2020-01-01"), "reading_tier": "skim", "freshness_gate": "fresh"}]
        payload, briefing, html = self.build_fixture(items)
        for field in ("top", "hot30", "kws"):
            self.assertEqual([], payload[field])
        self.assertIn("今日暂无新条目", briefing)
        self.assertIn("当前有效 0", briefing)
        self.assertIn("今日暂无新条目", html)
        self.assertEqual(1, len(payload["items"]))

    def test_empty_pool(self):
        payload, briefing, _ = self.build_fixture([])
        self.assertEqual([], payload["top"])
        self.assertIn("当前有效 0", briefing)

    def test_future_and_undated_only_never_backfilled(self):
        for published in ("2026-09-08", "2027-01-01", None, "invalid"):
            with self.subTest(published=published):
                payload, briefing, _ = self.build_fixture([
                    {**self.item(published), "reading_tier": "skim", "topic_relevance": 1}])
                self.assertEqual([], payload["top"])
                self.assertEqual([], payload["hot30"])
                self.assertEqual([], payload["kws"])
                self.assertNotIn("https://example.org/fresh", briefing)

    def test_ranking_limits_and_day_ten_inclusion(self):
        items = [{**self.item("2026-08-28", f"item-{i}"), "reading_tier": "skim",
                  "topic_relevance": i / 100} for i in range(35)]
        payload, briefing, _ = self.build_fixture(items)
        expected = [it["item_id"] for it in reversed(items)]
        self.assertEqual(expected[:10], payload["top"])
        self.assertEqual(expected[:30], [it["id"] for it in payload["hot30"]])
        self.assertEqual([{"term": "wellness", "n": 35}], payload["kws"])
        self.assertIn("https://example.org/item-34", briefing)
        self.assertNotIn("https://example.org/item-24", briefing)

    def test_build_date_overrides_old_collection_labels(self):
        item = score_item(self.item(), self.profile, self.as_of)
        payload, _, _ = self.build_fixture([item], date(2026, 9, 18), {"as_of": "2026-09-07"})
        self.assertEqual("2026-09-18", payload["asOf"])
        self.assertEqual([], payload["top"])

    def test_fresh_archive_stays_out(self):
        payload, _, _ = self.build_fixture([{**self.item(), "reading_tier": "archive"}])
        self.assertEqual([], payload["top"])
        self.assertEqual([], payload["hot30"])

    def test_low_activity_is_not_collection_failure(self):
        for published, expected in (("2026-08-24", ""), ("2026-08-23", "低活跃")):
            health = {"daily_status": "complete", "sources": [{"source_id": "fixture", "status": "ok", "item_count": 1}]}
            payload, _, _ = self.build_fixture([self.item(published)], health=health)
            self.assertEqual("complete", payload["statusRaw"])
            self.assertTrue(payload["srcs"][0]["ok"])
            self.assertEqual(expected, payload["srcs"][0]["activity"])

    def test_legacy_state_seen_does_not_revive_stale_item(self):
        item = self.item("2020-01-01")
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "fixture.json"
            legacy = {item["item_id"]: item["fingerprint"]}
            state.write_text(json.dumps(legacy), encoding="utf-8")
            stamped = apply_incremental([item], state, persist=True)[0]
            result = score_item(stamped, self.profile, self.as_of)
            self.assertEqual("seen", result["event_type"])
            self.assertEqual("archive", result["reading_tier"])
            self.assertEqual(legacy, json.loads(state.read_text(encoding="utf-8")))
            for key in ("item_id", "fingerprint", "provenance"):
                self.assertEqual(item[key], result[key])


def tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(str(file_path.relative_to(path)).encode())
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


class ReferencePipelineTests(unittest.TestCase):
    def run_demo(self, output: Path) -> dict:
        return run_pipeline(
            config_path=ROOT / "config" / "sources.demo.json",
            profile_path=ROOT / "config" / "profile.example.json",
            output_dir=output,
            as_of=date(2026, 1, 15),
            stateless=True,
            deterministic=True,
        )

    def test_offline_demo_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            result = self.run_demo(Path(first))
            self.run_demo(Path(second))
            self.assertEqual("complete", result["daily_status"])
            self.assertEqual(tree_digest(Path(first)), tree_digest(Path(second)))

    def test_public_items_use_positive_allowlist(self) -> None:
        raw = {
            "title": "A synthetic organoid benchmark",
            "url": "https://example.org/item",
            "published_at": "2026-01-15",
            "private_note": "must never pass through",
        }
        normalized = normalize_item(raw, {"id": "fixture", "kind": "fixture_jsonl"})
        projected = public_item({**normalized, "private_note": "still private"})
        self.assertEqual(set(PUBLIC_ITEM_FIELDS), set(projected))
        self.assertNotIn("private_note", projected)

    def test_demo_output_contains_no_private_extra_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self.run_demo(Path(temp))
            for line in (Path(temp) / "daily_items.jsonl").read_text(encoding="utf-8").splitlines():
                self.assertEqual(set(PUBLIC_ITEM_FIELDS), set(json.loads(line)))

    def test_network_sources_cannot_run_without_live_flag(self) -> None:
        with patch("sih_ref.sources._request", side_effect=AssertionError("network called")):
            for kind in NETWORK_SOURCE_KINDS:
                result = collect_source(
                    {"id": f"test-{kind}", "kind": kind, "enabled": True},
                    base_dir=ROOT,
                    live=False,
                    as_of=date(2026, 1, 15),
                )
                self.assertEqual("inactive", result.status)

    def test_required_live_source_without_live_flag_is_degraded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            config = ROOT / "config" / "sources.live-smoke.json"
            result = run_pipeline(
                config_path=config,
                profile_path=ROOT / "config" / "profile.example.json",
                output_dir=temp_path,
                as_of=date(2026, 1, 15),
                live=False,
                stateless=True,
                deterministic=True,
            )
            self.assertEqual("degraded", result["daily_status"])

    def test_example_config_represents_every_capability_family(self) -> None:
        payload = json.loads((ROOT / "config" / "sources.example.json").read_text(encoding="utf-8"))
        kinds = {source["kind"] for source in payload["sources"]}
        expected = {
            "pubmed", "pubmed_journals", "arxiv", "rss", "hacker_news",
            "openalex_author", "email_directory", "imap", "feishu_export",
            "stork_inbox", "browser_snapshot", "legacy_jsonl",
        }
        self.assertTrue(expected.issubset(kinds))
        self.assertIn("llm", payload)
        self.assertIn("delivery", payload)

    def test_health_distinguishes_warning_degraded_and_failure(self) -> None:
        self.assertEqual("complete_with_warning", classify_daily_health([{"required": False, "status": "warning"}]))
        self.assertEqual(
            "degraded",
            classify_daily_health([{"required": True, "status": "ok"}, {"required": True, "status": "failed"}]),
        )
        self.assertEqual("failed", classify_daily_health([{"required": True, "status": "failed"}]))
        self.assertEqual(
            "complete_with_warning",
            classify_daily_health([{"required": True, "status": "ok"}, {"required": False, "status": "failed"}]),
        )
        self.assertEqual("failed", classify_daily_health([{"required": False, "status": "failed"}]))

    def test_rfc_feed_date_is_normalized(self) -> None:
        self.assertEqual("2026-01-15", normalize_date("Thu, 15 Jan 2026 08:30:00 +0000"))

    def test_webhook_needs_config_flag_and_https_environment(self) -> None:
        with patch("sih_ref.delivery.urlopen", side_effect=AssertionError("network called")):
            self.assertEqual("disabled", publish_webhook({}, {"enabled": False}, publish=True)["status"])
            self.assertEqual(
                "dry_run",
                publish_webhook({}, {"enabled": True, "endpoint_env": "SIH_TEST_ENDPOINT"}, publish=False)["status"],
            )
            with self.assertRaisesRegex(ValueError, "HTTPS endpoint"):
                publish_webhook({}, {"enabled": True, "endpoint_env": "SIH_TEST_ENDPOINT"}, publish=True)

    def test_llm_needs_config_and_cli_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch(
            "sih_ref.pipeline.llm_triage", side_effect=AssertionError("LLM called")
        ):
            result = run_pipeline(
                config_path=ROOT / "config" / "sources.demo.json",
                profile_path=ROOT / "config" / "profile.example.json",
                output_dir=Path(temp),
                as_of=date(2026, 1, 15),
                llm_enabled=True,
                stateless=True,
                deterministic=True,
            )
            health = json.loads((Path(temp) / "source_health.json").read_text(encoding="utf-8"))
            self.assertEqual("inactive", health["extensions"]["llm_triage"]["status"])
            self.assertEqual("complete", result["daily_status"])

    def test_html_projection_escapes_script_termination(self) -> None:
        malicious = "</script><script>alert('x')</script>"
        html = render_site(
            [{
                "item_id": "url:https://example.org/x",
                "title": malicious,
                "url": "https://example.org/x",
                "summary": malicious,
                "source_id": "fixture",
                "published_at": "2026-01-15",
                "tags": [],
                "reading_tier": "skim",
                "freshness_gate": "fresh",
                "topic_relevance": 0.5,
            }],
            {"daily_status": "complete", "source_count": 1, "loaded_source_count": 1},
            as_of="2026-01-15",
            synthetic_demo=True,
        )
        self.assertNotIn(malicious, html)
        self.assertIn("<\\/script>", html)

    def tearDown(self) -> None:
        shutil.rmtree(ROOT / "demo" / "output", ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
