import json
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from timesfm3 import TimesFM3Evaluator, ModelConfig
import timesfm_poland_macro_v2_conditional as mod
import timesfm_poland_macro_v2_runner as runner


def market_future_cov(idx, fd, ea, br, gas, ecb, scenario):
    arr=[]
    for d, fn in [
        (ea, mod.ea_future),
        (br, lambda x: mod.brent_future(x, scenario)),
        (gas, lambda x: mod.gas_future(x, scenario)),
        (ecb, mod.ecb_future),
    ]:
        arr.append(np.r_[mod.align(d, idx), np.array([fn(x) for x in fd], dtype=np.float32)])
    return np.vstack(arr).astype(np.float32)


def run(model, gdp, ea, br, gas, ecb, scenario):
    idx = pd.DatetimeIndex(gdp[gdp.date >= pd.Timestamp('1998-01-01')].date)
    x = mod.align(gdp, idx)[None, :]
    h = (mod.END - idx[-1].year) * 4 + (5 - ((idx[-1].month-1)//3+1))
    fd = mod.fut(idx[-1], 'Q', h)
    cov = market_future_cov(idx, fd, ea, br, gas, ecb, scenario)
    o = list(model.predict_batch(contexts=[x], horizon=h, past_future_covariates=[cov], return_quantiles=True, use_symmetric_averaging=False))[0]
    f = np.asarray(o.forecast)[0]
    qq = np.asarray(o.quantiles)[0]
    return runner.annual(gdp, fd, f, qq)


def main():
    model = TimesFM3Evaluator(ModelConfig(checkpoint_path=mod.MODEL, per_core_batch_size=8, device='cpu'))
    gdp = mod.append_or_replace(mod.fred('POLGDPRQPSMEI'), '2026-04-01', 3.8)
    ea = mod.q(mod.yoy(mod.fred('CLV10MNACB1GQSCAEA20Q'), 4))
    br = mod.q(mod.m(mod.fred('MCOILBRENTEU')))
    gas = mod.q(mod.m(mod.fred('PNGASEUUSDM')))
    ecb = mod.q(mod.m(mod.fred('ECBDFR')))
    scenarios = {s: run(model, gdp, ea, br, gas, ecb, s) for s in ('base','energy_stress','energy_relief')}
    out = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'model': mod.MODEL,
        'variant': 'GDP market-only covariates selected by ablation',
        'covariates': ['EA20 real GDP yoy','Brent','EU natural gas','ECB deposit rate'],
        'scenarios': scenarios,
    }
    json.dump(out, open('poland_macro_v2_gdp_marketonly.json','w'), indent=2)
    rows=[]
    for s, vals in scenarios.items():
        for r in vals: rows.append({'scenario':s, **r})
    pd.DataFrame(rows).to_csv('poland_macro_v2_gdp_marketonly.csv', index=False)
    print(json.dumps(out, indent=2))

if __name__ == '__main__':
    main()
