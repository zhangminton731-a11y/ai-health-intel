# Source admission and distinct sections

**Goal:** Admit new sources only after auditing their latest ten consecutive articles (at least three valid reading-value scores >=70), and give each current article one primary section.

**Scope:** Existing collection, editorial and static-site pipeline. Keep five-axis weights, two independent GLM reviews, 98 ceiling, tier publication thresholds and historical editions. A source passing 3/10 does not make every article publishable.

**Assumptions:** Recent means the last 90 days for source qualification; live recommendations keep their existing 10-day window. A channel is the audited source (not an entire publisher). Missing material, invalid dates and failed model judgments are reported rather than scored zero. No cherry-picking or quota filling.

## Execution and checks

- [x] Require zero or one audience in `editorial.py` and define research/industry primary-event rules in `reading_value.md`; mismatched reviewers go to review. Test double assignment and disagreement.
- [x] Add a reusable `scripts/audit_sources.py` for latest-ten sampling and explicit admission outcomes. Test time ordering, duplicates, insufficient sample, exactly-three pass, below threshold and failed reviews.
- [x] Probe candidate publisher feeds, score frozen samples with production GLM/weights, publish an article-level audit and integrate only passing feeds into source config and metadata.
- [x] Re-evaluate the current batch, render distinct section introductions/reasons, and enforce one section in publication validation. Check live article ID overlap is zero.
- [x] Run engine/project/DOM tests, quality gate and browser checks. Publish a reviewed GitHub change, run cloud aggregation and verify the deployed API and both sections.
