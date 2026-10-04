# Pages Pipeline Implementation Plan

**Goal:** Repair missing research coverage and make Pages collection, publication and diagnostics efficient without changing product modules.

**Architecture:** Keep Python collection and static delivery. Integrate PR #9, parallelize only network work, persist validated caches, preserve one current publication set and defer hidden UI rendering.

**Tech Stack:** Python 3.12 standard library, browser JavaScript, GitHub Actions/Pages.

**Spec:** ../specs/2026-10-04-pages-pipeline-design.md

## Global Constraints

- Preserve existing URLs, modules and original publication dates; 10-day current and 20-day history windows.
- No new model calls, notification recipients, paid services or server deployment.
- Tests use local fake responses. Live read-only sampling is separately recorded.
- Execute in this session; preserve PR #9 author history and review changes before publishing a draft PR.

### Task 1: Source reliability and bounded concurrency

Files: `engine/src/sih_ref/{pipeline,rss_fetch,sources}.py`, `.github/workflows/aggregate.yml`, `tests/test_pipeline_upgrade.py`.

- [x] Re-run PR #9 tests and commit its integration.
- [x] Add failure tests for cache validation, changed validators and deterministic concurrent results.
- [x] Extend `fetch_feed(url, user_agent, cache_path=None)` to reuse only valid cached XML on HTTP 304; cache only parsed successes.
- [x] Run collection in `ThreadPoolExecutor(max_workers=4)` with ordered results and serial state writes; validate IDs before scheduling.
- [x] Preserve ignored runtime caches with Actions cache; failure never advances successful feed cache.
- [x] Run `python -m unittest discover -s tests -p 'test_*.py'`.

### Task 2: Research input quality and selection audit

Files: `engine/src/sih_ref/{article_metadata,core,sources}.py`, `config/{sources,profile}.json`, `tests/test_pipeline_upgrade.py`.

- [x] Reproduce the October 3 Nature cases and negative cases (general software, drug-only finance, title-only candidates).
- [x] Add `enrich_summary(item, cache_dir)` using only configured Nature article metadata, successful caching and bounded response size; preserve source URL in provenance.
- [x] Add a separate research relevance predicate alongside the existing industry predicate, plus explicit rejection reasons.
- [x] Reuse `freshness_gate` and keep missing/invalid/future dates excluded.
- [x] Replay real saved facts, inspect changed decisions and read source metadata independently.

### Task 3: Publication size, date clarity and rendering

Files: `scripts/{build_site,export_feeds,quality_gate}.py`, `templates/site.html`, `tests/{test_pipeline_upgrade.py,site.test.cjs}`.

- [x] Keep archival facts on disk but omit hidden summaries/reasons from the embedded payload.
- [x] Extract inline CSS/JS into content-hashed files at build time; validate referenced local assets.
- [x] Add collection/publication counts by original date to health and explain the latest edition on the existing daily page.
- [x] Render only the selected route; test direct article/daily/policy URLs and escaping.
- [x] Run Python suites, DOM tests, rebuild saved batch and publication quality gate.

### Task 4: Evidence and reviewable delivery

Files: `scripts/benchmark_pipeline.py`, `docs/pages-upgrade-acceptance.md`, `README.md`.

- [x] Use fixed delayed source fixtures to measure serial vs four-worker work with identical output; label results synthetic.
- [x] Compare same-batch HTML bytes and original article IDs, preserving all routes and historical reading.
- [x] Record remaining limits: Actions scheduling, absent Feishu credentials, content assessment not human validation, no guaranteed lead generation.
- [x] Create a draft PR with verification evidence and attach it to this chat; no automated production merge.

Draft PR: https://github.com/zhangminton731-a11y/ai-health-intel/pull/10
