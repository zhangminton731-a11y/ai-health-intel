# Date timeline and industry source expansion

**Goal:** Replace time-window dropdowns with expandable date groups and collect qualified industry articles for 2026-09-01 through 2026-10-04.

**Design:** Preserve current-only highlights/RSS/hot lists, merge dated archival content into the two section timelines with current copies taking precedence. Native details/summary supplies keyboard-accessible expand/collapse, latest date initially open. Keep article dates, archive provenance and primary-section distinctions.

**Constraints:** Existing GLM two-review weights, 98 ceiling, source admission latest 10 / 3 at 70, publication tiers unchanged. No fabricated or re-dated quota fillers. Measure all 34 dates and report remaining gaps. Source latest-ten sample is fixed before scoring; historical search cannot replace its low-scoring members.

- [x] Implement date accordions, remove time dropdowns, retain archive deep links, test expansion/filters/current-only highlights.
- [x] Probe official company/regulatory and industry media channels, audit latest ten, integrate only qualified new channels.
- [x] Backfill dated industry records from qualifying channels, validate scores and source dates, export monthly archive and day-by-day coverage report.
- [ ] Run tests, publication gates, browser desktop/mobile QA; publish through checked PRs and verify cloud deployment.

Progress: 10 channels / 82 fixed samples audited; CMS fact sheets admitted (4/10). Six qualified industry records cover 6 of 34 days; 28 dates remain unfilled. Quantity objective is not complete. Local checks pass: engine 27, project 133, DOM 46, quality gate, desktop/mobile browser.
