from pathlib import Path

src = Path('timesfm_poland_forecast.py').read_text()

old = '''def annualize_rate(actual_df, dates, point, quant=None, start_year=2026):
    rows=[]
    f = pd.DataFrame({'date':dates, 'point':point})
    for year in range(start_year, END_YEAR+1):
        vals = f.loc[f.date.dt.year == year, 'point']
        if len(vals):
            row={'year':year, 'point':float(vals.mean())}
            if quant is not None:
                mask=(f.date.dt.year==year).to_numpy()
                for j,q in enumerate(Q_LEVELS):
                    row[f'p{int(q*100)}']=float(np.asarray(quant)[mask,j].mean())
            rows.append(row)
    return rows
'''

new = '''def annualize_rate(actual_df, dates, point, quant=None, start_year=2026):
    rows=[]
    f = pd.DataFrame({'date':pd.to_datetime(dates), 'point':point})
    if actual_df is not None:
        hist = actual_df[['date','value']].rename(columns={'value':'point'}).copy()
        hist['date'] = pd.to_datetime(hist['date'])
        combined = pd.concat([hist,f], ignore_index=True).drop_duplicates('date', keep='last').sort_values('date')
    else:
        hist = None
        combined = f
    for year in range(start_year, END_YEAR+1):
        vals = combined.loc[combined.date.dt.year == year, 'point']
        if len(vals):
            row={'year':year, 'point':float(vals.mean())}
            if quant is not None:
                for j,q in enumerate(Q_LEVELS):
                    qf = pd.DataFrame({'date':pd.to_datetime(dates), 'point':np.asarray(quant)[:,j]})
                    if hist is not None:
                        qc = pd.concat([hist,qf], ignore_index=True).drop_duplicates('date', keep='last').sort_values('date')
                    else:
                        qc = qf
                    qvals = qc.loc[qc.date.dt.year == year, 'point']
                    if len(qvals):
                        row[f'p{int(q*100)}']=float(qvals.mean())
            rows.append(row)
    return rows
'''

if old not in src:
    raise RuntimeError('Expected annualize_rate block not found')

src = src.replace(old, new)
src = src.replace('results[k]=annualize_level(dates,p,q,q)', 'results[k]=annualize_level(dates,p,q)')
exec(compile(src, 'timesfm_poland_forecast_patched.py', 'exec'), {'__name__':'__main__'})
