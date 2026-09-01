import json
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from timesfm3 import TimesFM3Evaluator, ModelConfig
import timesfm_poland_macro_v2_conditional as mod

ORIGINS = list(map(pd.Timestamp, ['2018-10-01','2019-10-01','2021-10-01','2022-10-01','2023-10-01','2024-10-01']))


def pred(model, x, h, cov=None):
    kwargs = dict(contexts=[x], horizon=h, return_quantiles=False, use_symmetric_averaging=False)
    if cov is not None:
        kwargs['past_future_covariates'] = [cov.astype(np.float32)]
    o = list(model.predict_batch(**kwargs))[0]
    return np.asarray(o.forecast).reshape(-1)[:h]


def market_cov(idx, fd, ea, br, gas, ecb):
    return np.vstack([np.r_[mod.align(d, idx), mod.align(d, fd)] for d in (ea, br, gas, ecb)]).astype(np.float32)


def policy_cov(idx, fd):
    full = idx.append(fd)
    return np.vstack([np.array([fn(x) for x in full], dtype=np.float32) for fn in (mod.kpo, mod.defense, mod.ets2)])


def evaluate(model, gdp, ea, br, gas, ecb):
    rows = []
    for origin in ORIGINS:
        if origin not in set(gdp.date) or origin + pd.DateOffset(years=1) > gdp.date.max():
            continue
        hist = gdp[gdp.date <= origin]
        idx = pd.DatetimeIndex(hist[hist.date >= pd.Timestamp('1998-01-01')].date)
        x = mod.align(hist, idx)[None, :]
        fd = pd.date_range(origin + pd.offsets.QuarterBegin(startingMonth=1), periods=4, freq='QS')
        act = mod.align(gdp, fd).astype(float)
        mc = market_cov(idx, fd, ea, br, gas, ecb)
        pc = policy_cov(idx, fd)
        variants = {
            'baseline': None,
            'market_only': mc,
            'policy_only': pc,
            'full': np.vstack([mc, pc]),
        }
        rec = {'origin': str(origin.date())}
        for name, cov in variants.items():
            p = pred(model, x, 4, cov)
            rec[name + '_mae'] = float(np.mean(np.abs(p - act)))
            rec[name + '_bias'] = float(np.mean(p - act))
        rows.append(rec)
    summary = {}
    for name in ('baseline','market_only','policy_only','full'):
        vals = np.array([r[name+'_mae'] for r in rows])
        b = np.array([r['baseline_mae'] for r in rows])
        summary[name] = {
            'mean_mae': float(vals.mean()),
            'median_mae': float(np.median(vals)),
            'wins_vs_baseline': int(np.sum(vals < b)) if name != 'baseline' else None,
            'mean_improvement_vs_baseline_pct': float((b.mean() - vals.mean()) / b.mean() * 100) if name != 'baseline' else 0.0,
            'median_improvement_vs_baseline_pct': float((np.median(b) - np.median(vals)) / np.median(b) * 100) if name != 'baseline' else 0.0,
        }
    # Robust summary excluding COVID forecast origin (2019Q4) and reopening origin (2021Q4)
    robust_rows = [r for r in rows if r['origin'] not in ('2019-10-01','2021-10-01')]
    robust = {}
    for name in ('baseline','market_only','policy_only','full'):
        vals = np.array([r[name+'_mae'] for r in robust_rows])
        b = np.array([r['baseline_mae'] for r in robust_rows])
        robust[name] = {
            'mean_mae': float(vals.mean()),
            'median_mae': float(np.median(vals)),
            'wins_vs_baseline': int(np.sum(vals < b)) if name != 'baseline' else None,
            'mean_improvement_vs_baseline_pct': float((b.mean() - vals.mean()) / b.mean() * 100) if name != 'baseline' else 0.0,
        }
    return {'origins': rows, 'summary_all': summary, 'summary_ex_covid_reopening': robust}


def main():
    model = TimesFM3Evaluator(ModelConfig(checkpoint_path=mod.MODEL, per_core_batch_size=8, device='cpu'))
    gdp = mod.append_or_replace(mod.fred('POLGDPRQPSMEI'), '2026-04-01', 3.8)
    ea = mod.q(mod.yoy(mod.fred('CLV10MNACB1GQSCAEA20Q'), 4))
    br = mod.q(mod.m(mod.fred('MCOILBRENTEU')))
    gas = mod.q(mod.m(mod.fred('PNGASEUUSDM')))
    ecb = mod.q(mod.m(mod.fred('ECBDFR')))
    result = evaluate(model, gdp, ea, br, gas, ecb)
    out = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'model': mod.MODEL, 'diagnostic': 'GDP one-year oracle-covariate ablation', **result}
    json.dump(out, open('poland_macro_v2_ablation.json','w'), indent=2)
    pd.DataFrame(result['origins']).to_csv('poland_macro_v2_ablation.csv', index=False)
    print(json.dumps(out, indent=2))

if __name__ == '__main__':
    main()
