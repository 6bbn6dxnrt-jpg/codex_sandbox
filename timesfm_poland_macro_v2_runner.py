import pandas as pd
import numpy as np
import timesfm_poland_macro_v2_conditional as mod


def annual(hist, dates, point, quant=None):
    if hist is not None:
        h = hist[['date','value']].rename(columns={'value':'point'}).copy()
    else:
        h = pd.DataFrame({'date': pd.Series([], dtype='datetime64[ns]'), 'point': pd.Series([], dtype=float)})
    f = pd.DataFrame({'date': pd.to_datetime(dates), 'point': point})
    c = pd.concat([h, f], ignore_index=True).drop_duplicates('date', keep='last').sort_values('date')
    c['date'] = pd.to_datetime(c['date'])
    out = []
    for y in range(2026, mod.END+1):
        v = c.loc[c['date'].dt.year == y, 'point']
        if len(v):
            r = {'year': y, 'point': float(v.mean())}
            if quant is not None:
                qarr = np.asarray(quant)
                if qarr.ndim == 3:
                    qarr = qarr[0]
                for j, x in enumerate(mod.QS):
                    z = pd.concat([
                        h,
                        pd.DataFrame({'date': pd.to_datetime(dates), 'point': qarr[:, j]})
                    ], ignore_index=True).drop_duplicates('date', keep='last').sort_values('date')
                    z['date'] = pd.to_datetime(z['date'])
                    w = z.loc[z['date'].dt.year == y, 'point']
                    if len(w):
                        r[f'p{int(x*100)}'] = float(w.mean())
            out.append(r)
    return out


def endyear(hist, dates, point):
    if hist is not None:
        h = hist[['date','value']].rename(columns={'value':'point'}).copy()
    else:
        h = pd.DataFrame({'date': pd.Series([], dtype='datetime64[ns]'), 'point': pd.Series([], dtype=float)})
    c = pd.concat([
        h,
        pd.DataFrame({'date': pd.to_datetime(dates), 'point': point})
    ], ignore_index=True).drop_duplicates('date', keep='last').sort_values('date')
    c['date'] = pd.to_datetime(c['date'])
    return [
        {'year': y, 'point': float(c.loc[c['date'].dt.year == y].iloc[-1]['point'])}
        for y in range(2026, mod.END+1)
        if len(c.loc[c['date'].dt.year == y])
    ]

mod.annual = annual
mod.endyear = endyear

if __name__ == '__main__':
    mod.main()
