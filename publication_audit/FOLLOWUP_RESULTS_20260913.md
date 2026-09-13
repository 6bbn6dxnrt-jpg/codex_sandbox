# Follow-up audit results — 13 September 2026

## Scope
One prespecified classical CPI coordinate repair R1, not a new competition forecast. All 661 old forecast records and all original frozen files remain unchanged. Twenty classical CPI records have a separate errata/status overlay and remain in as-issued scoring. No independent human review has occurred. PR #1 stays draft.

Protocol committed before reading repaired results: 1d3aa013dd362083322d29dcb8b81fda1c3e061a. Minimal patch: publication_audit/R1_minimal_patch.py.

## Repair
Fitted component predictors now use 100*(L/L.shift(12)-1), the same synthetic-level ratio definition used at prediction. The official aggregate CPI target, lagged headline CPI, alpha=10, rolling windows, seasonal/damped component forecasting and 50/50 mixture are unchanged.

Predictors must be called synthetic category indices, NOT official component inflation. R1 resolves this specific fitting/prediction mismatch. It does not reconstruct official CPI weights, fix classification continuity or eliminate every issue with synthetic levels.

## Frozen-cutoff diagnostic, NOT reissued September 9 forecasts

| Target | Year | Original | R1 computed September 13 | Difference pp |
|---|---:|---:|---:|---:|
| CPI annual average | 2026 | 2.870641 | 2.879910 | +0.009269 |
| CPI December y/y | 2026 | 3.161818 | 3.192102 | +0.030283 |
| CPI annual average | 2027 | 4.086294 | 4.114878 | +0.028585 |
| CPI December y/y | 2027 | 4.736812 | 4.755619 | +0.018807 |

This particular correction does NOT explain away the high original 2027 inflation path. The original 4.086294 stays archived with an erratum; the 4.114878 diagnostic is not substituted into the old contest. Annual aggregation is still the original approximate reconstruction. No new R1 uncertainty bands or live forecasts were issued.

## Retrospective effect, 132 original issue dates
Targets through December 2025 only; h is from the last observation, not issuance.

| h | N | MAE original | MAE R1 | Relative improvement |
|---|---:|---:|---:|---:|
| 1 | 132 | 0.473469 | 0.452219 | 4.49% |
| 3 | 131 | 0.965562 | 0.930209 | 3.66% |
| 6 | 128 | 1.718791 | 1.676414 | 2.47% |
| 12 | 122 | 3.134291 | 3.104712 | 0.94% |
| 18 | 116 | 3.959208 | 3.940759 | 0.47% |

The 2015–2019 cohort gets slightly worse at h=1/3/6 (roughly 0.5–2.1%). R1 is not a universal winner. Results remain exploratory, latest-vintage and previously inspected. They are not evidence of bank superiority.

## Preserved Google audit
The actual September 12 one-vs-nine inference artifact 10304874252 was downloaded and checked again: SHA256 5540a6a550c727124b878a2ee20f2a849e8b16c5e3421f1ad60d4f917f6e6e3b. No new Google neural inference was run on September 13. Native WIS was recalculated from twice mean pinball on 1482 rows; maximum difference 3.55e-15, no crossed native deciles.

| h | Offset from issue month | N | MAE one | MAE nine | Relative improvement | Native 80% coverage nine |
|---|---:|---:|---:|---:|---:|---:|
| 1 | -1 | 44 | 0.348115 | 0.332842 | 4.39% | 90.91% |
| 3 | +1 | 43 | 0.996888 | 0.965272 | 3.17% | 76.74% |
| 6 | +4 | 42 | 1.869352 | 1.732325 | 7.33% | 71.43% |
| 12 | +10 | 40 | 3.384144 | 2.960720 | 12.51% | 70.00% |
| 18 | +16 | 38 | 4.042695 | 3.279408 | 18.88% | 73.68% |

This is Google-versus-Google, not versus banks. Previously computed paired intervals are exploratory and not multiplicity-adjusted. Small/dependent samples and unknown pretraining overlap remain limitations. Old V4 registry intervals are empirical residual bands, NOT the native Google intervals evaluated here.

## Provenance and technical checks
Reconciled 661 records: 18 direct Google V4 points, 2 annual derivatives, 28 classical V4, 263 V3 publication, 65 V3 statistical, 242 external and 43 bank medians. Some V3 records are mixtures containing Google; they are not direct outputs. Formula weights differ by target/year.

Original classical backtests and current frozen-cutoff outputs reproduced before comparing R1. Future-value perturbation at three origins, positive scale invariance and unchanged source hashes pass. R1 executed locally in 25.6 seconds. No model weights or credentials are bundled.

score_asof.py chooses one latest eligible competitor vintage not later than the focal issue date; exact-date mode is separate. Duplicate/ambiguous forecasts, missing realization sources and mixed outcome vintages are rejected. Fifteen isolated tests pass. Errata are retained and labelled in primary as-issued results. Original Excel files were not altered. All actual realization outputs remain empty.

## Review gate
Complete replay code, archived inputs, provenance, errata and reviewer instructions are delivered in the chat package. Independent human review remains PENDING: no person has signed off, been assigned or been automatically contacted. A second arithmetic implementation by the same AI is not a human review.

Supported publication: exploratory forecasting experiment with the erratum, sources and information cutoffs. Unsupported: best/optimal use of all TimesFM capabilities, superiority to banks, or claiming the whole macro table is Google's forecast.

## Checkpoints
- Frozen 661-row registry SHA256: 749c3c144ad4af224910c7d66845439818aba848d68bfe8a610658203f82ba65
- R1_metrics.csv SHA256: 45603884c5b887389efc963f9a06af400dcf13b7236f38a627ff9e3b978814ae
- R1_annual_diagnostic.csv SHA256: e5dc43eb795513f3f8079a0f76ac682d8564fffa99216dc96f8fb47385078235
- forecast_provenance_661.csv SHA256: be1acc1231fe734d98b5e30f6486e34ecc4c92e98305a425db9d145026dc8bc1
- frozen_registry_status_overlay.csv SHA256: 84e63a0998e6c453afe87b79933cc6134c3a492864ef2bd1544e16c25e85a1d1
