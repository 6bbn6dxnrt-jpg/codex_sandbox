# Controller specification

At each run:
1. Read PROJECT_CHARTER.md, STATE.json and config.
2. Compute the coverage funnel and identify the throughput bottleneck.
3. Execute the largest safe idempotent batch at that bottleneck.
4. Run QA. Route only uncertain fields/pages to expensive vision/reasoning.
5. Never stop production because one document failed; classify and queue the failure.
6. Update STATE.json and emit machine-readable KPI deltas.

Optimization target: auditable representative person-years / unit time, constrained by Gold-set error rates.

Never change an extractor in production solely because it appears better on production data. Candidate changes must beat the current version on the frozen stratified Gold set, then pass a canary.
