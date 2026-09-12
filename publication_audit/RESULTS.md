# Poland Macro publication audit — 12 September 2026

Status: RESEARCH ONLY WITH ERRATA. This audit did not change any of the 661 frozen forecast records and did not add a new competition forecast vintage. Independent human review has NOT occurred.

## Matched Google experiment completed

Run: 34718534798. Commit: e5998ea6b211b2b156176105a12f8599cc6ec584. Artifact: 10304874252; ZIP SHA256 5540a6a550c727124b878a2ee20f2a849e8b16c5e3421f1ad60d4f917f6e6e3b.
Model: google/timesfm-3.0-pytorch, revision 43046b85ec22d584a13f8098c2ed39c889e129c2. Package timesfm 3.0.0. Same frozen data, same contexts, same 44 quarterly-spaced historical origins in 2015–2025. One series is CPI; nine series adds the existing eight CPI categories. Both output all native deciles at every step of an 18-month horizon. Scoring only uses target dates through December 2025.

| h from context end | Calendar month offset from issue month | N | MAE one | MAE nine | Relative gain |
|---|---:|---:|---:|---:|---:|
| 1 | -1 | 44 | 0.348115 | 0.332842 | 4.39% |
| 3 | +1 | 43 | 0.996888 | 0.965272 | 3.17% |
| 6 | +4 | 42 | 1.869352 | 1.732325 | 7.33% |
| 12 | +10 | 40 | 3.384144 | 2.960720 | 12.51% |
| 18 | +16 | 38 | 4.042695 | 3.279408 | 18.88% |

Paired origin-year clustered bootstrap: 5000 replicates. Pointwise 95% CI for nine-minus-one MAE is [-0.996021, -0.026051] at h=12 and [-1.528642, -0.103684] at h=18. Other shown MAE intervals include zero. These are exploratory intervals, not multiplicity-adjusted confirmatory tests. The history has already been inspected. In the 2020–2022 origin cohort, nine-series MAE is 11.4% worse at h=6. Do not claim uniform dominance or superiority over banks.

## Native uncertainty

| h | WIS one | WIS nine | Nominal 80% coverage one | Nominal 80% coverage nine |
|---|---:|---:|---:|---:|
| 1 | 0.278254 | 0.274718 | 86.36% | 90.91% |
| 3 | 0.775343 | 0.752370 | 76.74% | 76.74% |
| 6 | 1.478481 | 1.375284 | 71.43% | 71.43% |
| 12 | 2.742773 | 2.436721 | 65.00% | 70.00% |
| 18 | 3.365239 | 2.848376 | 65.79% | 73.68% |

All five WIS difference intervals include zero. The nine-series 80% interval covers 28/40 outcomes at h=12 and 28/38 at h=18. All native quantiles are ordered. Native point forecasts equal q50. No interval sorting or recalibration was applied. WIS uses central 20%, 40%, 60%, 80% intervals and was independently recalculated from mean pinball loss (maximum difference 3.55e-15 over 1482 score rows).

The old V4 registry bands are empirical residual bands, NOT native Google quantiles. Their point and interval provenance must be stated separately. Native monthly quantiles are not annual quantiles.

## Reproduction and data integrity

Recomputed old nine-series historical points differ by at most 6.68e-6 percentage points; the old current point path differs by at most 1.19e-6. The frozen input has 199 consecutive monthly rows and 9 series. Independent XML extraction of the two archived GUS workbooks matches all 1791 model-input values exactly. Source hashes match. The original V3 registry SHA256 remains ec5314b41d638625fa39da91e2a98c8e7966994ca0aa1b954c2993fe41352a24. All 384 original records remain unchanged within the 661-record registry.

Future-value perturbations for the original classical CPI and GDP functions at 2016-09-09, 2020-06-09 and 2023-12-09 change outputs by zero. This does NOT address historical release vintages or model-pretraining overlap. Seventeen source files parse; annual arithmetic and the current-year-denominator debt identity were independently reproduced. Internal checks: 37 passes and 1 important methodology failure; this count is not a quality certificate.

## Important open issue: classical V4 CPI feature definitions

Training in `challenger.py` uses official component year-on-year rates. `price_levels_forecast` later supplies rates computed as ratios of synthetic December-linked levels. These representations are not identical.

Historical counterexample, energy February 2023: official y/y = 31.1%, synthetic reconstructed y/y = 38.2196629213%, a gap of 7.1196629213 percentage points. This is NOT an error in GUS data and NOT a 7-point gap in aggregate CPI. It is an inconsistency in our transformation of the component data. It cannot be dismissed as mere rounding. Largest aggregate CPI gap is 0.724803 pp; food is 3.309467 pp. Category/weight/classification changes require explicit reconciliation.

HOLD: do not market the classical V4 CPI path (including 4.09% annual CPI 2027) as validated before the feature representation is harmonized and retested under a new version. Do not invent a corrected point. Preserve the original forecast with this erratum. The raw Google path uses official y/y values directly and does not use this specific synthetic-regressor function.

## Attribution correction

V3 is not a pure TimesFM macro forecast. Actual linear contributions to annual publication point formulas:
- GDP 2026: 0% Google; statistical selection is 100% ridge autoregression.
- GDP 2027: approximately 34.92% Google after the judgment layer.
- GDP 2030: approximately 2.50% Google; 95% explicit judgment prior.
- CPI 2026: approximately 50.80% Google; CPI 2027 approximately 32.17%; CPI 2028–2030 zero.
- V3 FX statistical selections have zero Google weight. Policy rate and fiscal paths are explicit assumptions; debt is accounting from assumptions.
- V4 GDP and classical CPI are not Google models.
- Of 661 records, 18 V4 Google points are direct monthly/December outputs and 2 are annual aggregates. Other records include 28 classical V4, 263 V3 publication, 65 V3 statistical, 242 external benchmarks and 43 bank medians.

## Publication gate and review

Publishable scope: a transparent exploratory experiment with this erratum and data cutoffs. Not supported: a claim of bank superiority, a claim that the whole macro table is Google's forecast, or a claim of optimal use of all model capabilities.

Current raw Google context remains July 2026. Historical vintages have not been recovered. Classification continuity is approximate. Audit calculations from 12 September must not be backdated into the 9 September competition register.

A reviewer package and draft pull request are being prepared. No reviewer has signed off, no external human review is represented as completed, and a second numerical implementation by the same AI is not a second-person review.
