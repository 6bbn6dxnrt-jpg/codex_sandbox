# Follow-up protocol — 13 September 2026

This is a technical erratum experiment using the frozen 9 September dataset. It is NOT a new September 9 forecast, not a new live vintage, and not external human validation.

## Prespecified single repair R1
The old classical CPI regression is trained on official category year-on-year rates but is fed future rates computed from synthetic December-linked analysis levels. To isolate this mismatch, R1 changes only the TRAINING component columns to the same function of the same synthetic analysis levels: 100 * (L[t]/L[t-12]-1). Headline targets, lagged headline inputs, seasonal/damped future-level generators, ridge penalty 10, estimation windows, 50/50 blend and origin grid remain unchanged. Derived columns must be labelled synthetic category indices, NOT official component inflation. This is a coordinate-consistency repair, not a complete official CPI basket model.

Why this repair: it isolates the identified inconsistency without adding an untested official-weight reconstruction or choosing between alternative forecasters after inspecting results. No tuning or search for more attractive forecasts is allowed in this follow-up.

## Evaluations
1. Reproduce the original classical monthly paths from archived code and input files. Stop and disclose if reproduction fails.
2. Reproduce the official-vs-synthetic historical feature discrepancy, including energy February 2023, and verify R1 uses one definition in fitting and prediction.
3. Score old and repaired classical CPI on the original 132 issue dates (2015–2025, day 9 of each month) and original completed targets through December 2025. Report h=1/3/6/12/18 and all origin cohorts; compare only common observations.
4. Report current frozen-cutoff monthly diagnostic paths (September 2026 through December 2027). Annual diagnostics use exactly the old aggregation helper and stay explicitly approximate.
5. Check future-data perturbation invariance, positive scale invariance of synthetic levels and bitwise/numeric preservation of all frozen registers and Google inputs. No new raw Google inference is necessary: reuse the verified matched audit artifact 10304874252.
6. Keep every frozen forecast unchanged. Record any affected classical CPI entries in a separate errata/status overlay; do not silently remove them from historical competition results.
7. Complete a reproducible reviewer packet. PR #1 stays draft. No independent reviewer has been assigned; a second implementation by this AI is not a human review.

Acceptance of R1 means eliminating this one training/prediction definition mismatch. It does not establish forecasting improvement, solve CPI reweighting/classification continuity, recover historical release vintages, or justify superiority over banks. Report negative results as well as positive ones.
