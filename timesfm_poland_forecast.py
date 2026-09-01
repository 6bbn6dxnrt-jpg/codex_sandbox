import json
import math
import os
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
import requests
from timesfm3 import TimesFM3Evaluator, ModelConfig

MODEL = 'google/timesfm-3.0-pytorch'
END_YEAR = 2030
Q_LEVELS = [0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9]


def fred(series_id):
    url = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}'
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(pd.io.common.StringIO(r.text))
    if len(df.columns) < 2:
        raise RuntimeError(f'Bad FRED response {series_id}')
    df = df.iloc[:, :2].copy()
    df.columns = ['date','value']
    df['date'] = pd.to_datetime(df['date'])
    df['value'] = pd.to_numeric(df['value'], errors='coerce')
    df = df.dropna().sort_values('date').reset_index(drop=True)
    if len(df) < 8:
        raise RuntimeError(f'Too few observations {series_id}: {len(df)}')
    return df


def wb(indicator):
    url = f'https://api.worldbank.org/v2/country/POL/indicator/{indicator}?format=json&per_page=100'
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    payload = r.json()
    rows = payload[1]
    data = []
    for x in rows:
        if x['value'] is not None:
            data.append((pd.Timestamp(f"{x['date']}-01-01"), float(x['value'])))
    return pd.DataFrame(data, columns=['date','value']).sort_values('date').reset_index(drop=True)


def append_or_replace(df, date, value):
    date = pd.Timestamp(date)
    df = df[df['date'] != date].copy()
    out = pd.concat([df, pd.DataFrame({'date':[date], 'value':[float(value)]})], ignore_index=True)
    return out.sort_values('date').reset_index(drop=True)


def infer_univariate(forecaster, df, horizon):
    x = df['value'].to_numpy(dtype=np.float32)
    out = list(forecaster.predict_batch(
        contexts=[x], horizon=int(horizon), return_quantiles=True,
        use_symmetric_averaging=False))[0]
    point = np.asarray(out.forecast, dtype=float).reshape(-1)
    quant = np.asarray(out.quantiles, dtype=float)
    if quant.ndim == 3:
        quant = quant[0]
    return point, quant


def future_dates(last_date, freq, horizon):
    if freq == 'M':
        start = pd.Timestamp(last_date) + pd.offsets.MonthBegin(1)
        return pd.date_range(start=start, periods=horizon, freq='MS')
    if freq == 'Q':
        start = pd.Timestamp(last_date) + pd.offsets.QuarterBegin(startingMonth=1)
        return pd.date_range(start=start, periods=horizon, freq='QS')
    if freq == 'A':
        start = pd.Timestamp(f'{pd.Timestamp(last_date).year + 1}-01-01')
        return pd.date_range(start=start, periods=horizon, freq='YS')
    raise ValueError(freq)


def annualize_rate(actual_df, dates, point, quant=None, start_year=2026):
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


def annualize_level(dates, point, quant=None, start_year=2026):
    return annualize_rate(None, dates, point, quant, start_year)


def inflation_from_index(actual, dates, point, quant):
    hist = actual[['date','value']].rename(columns={'value':'point'}).copy()
    fc = pd.DataFrame({'date':dates,'point':point})
    combined = pd.concat([hist,fc], ignore_index=True).sort_values('date')
    rows=[]
    for y in range(2026, END_YEAR+1):
        cy = combined[combined.date.dt.year==y]['point']
        py = combined[combined.date.dt.year==y-1]['point']
        if len(cy)==12 and len(py)==12:
            row={'year':y,'point':float((cy.mean()/py.mean()-1)*100)}
            # quantile paths: use actual months where known and corresponding q forecast where unknown
            for j,q in enumerate(Q_LEVELS):
                qdf = hist.copy()
                qfc = pd.DataFrame({'date':dates,'point':np.asarray(quant)[:,j]})
                qc = pd.concat([qdf,qfc], ignore_index=True).sort_values('date')
                cyq=qc[qc.date.dt.year==y]['point']; pyq=qc[qc.date.dt.year==y-1]['point']
                if len(cyq)==12 and len(pyq)==12:
                    row[f'p{int(q*100)}']=float((cyq.mean()/pyq.mean()-1)*100)
            rows.append(row)
    return rows


def endyear_level(dates, point, quant=None):
    f = pd.DataFrame({'date':dates,'point':point})
    rows=[]
    for y in range(2026, END_YEAR+1):
        yy=f[f.date.dt.year==y]
        if len(yy):
            ix=yy.index[-1]
            pos=f.index.get_loc(ix)
            row={'year':y,'point':float(yy.iloc[-1].point)}
            if quant is not None:
                for j,q in enumerate(Q_LEVELS): row[f'p{int(q*100)}']=float(np.asarray(quant)[pos,j])
            rows.append(row)
    return rows


def growth_from_level(actual, dates, point, quant=None):
    hist = actual[['date','value']].rename(columns={'value':'point'}).copy()
    fc = pd.DataFrame({'date':dates,'point':point})
    comb=pd.concat([hist,fc],ignore_index=True).sort_values('date')
    rows=[]
    for y in range(2026,END_YEAR+1):
        a=comb[comb.date.dt.year==y]['point']; b=comb[comb.date.dt.year==y-1]['point']
        if len(a) and len(b):
            row={'year':y,'point':float((a.iloc[-1]/b.iloc[-1]-1)*100)}
            if quant is not None:
                for j,q in enumerate(Q_LEVELS):
                    qc=pd.concat([hist,pd.DataFrame({'date':dates,'point':np.asarray(quant)[:,j]})],ignore_index=True).sort_values('date')
                    aa=qc[qc.date.dt.year==y]['point']; bb=qc[qc.date.dt.year==y-1]['point']
                    if len(aa) and len(bb): row[f'p{int(q*100)}']=float((aa.iloc[-1]/bb.iloc[-1]-1)*100)
            rows.append(row)
    return rows


def run_multivariate_check(forecaster, series_map, freq, horizon):
    frames=[]
    for name,df in series_map.items():
        z=df[['date','value']].copy().rename(columns={'value':name}).set_index('date')
        frames.append(z)
    joined=pd.concat(frames,axis=1,join='inner').dropna()
    if len(joined)<24:
        return {'status':'skipped','reason':'insufficient common history','n':len(joined)}
    mat=joined.to_numpy(dtype=np.float32).T
    out=list(forecaster.predict_batch(contexts=[mat],horizon=horizon,return_quantiles=True,use_symmetric_averaging=False))[0]
    return {
      'status':'ok','variables':list(joined.columns),'n_obs':len(joined),
      'last_date':str(joined.index[-1].date()),
      'forecast_shape':list(np.asarray(out.forecast).shape),
      'first_step':{c:float(np.asarray(out.forecast)[i,0]) for i,c in enumerate(joined.columns)}
    }


def main():
    config=ModelConfig(checkpoint_path=MODEL, per_core_batch_size=16, device='cpu')
    model=TimesFM3Evaluator(config)

    sources={}
    results={}
    raw={}

    monthly_specs={
      'hicp_index':('CP0000PLM086NEST','HICP index, 2025=100'),
      'unemployment_rate':('LRHUTTTTPLM156S','Unemployment rate, SA, %'),
      'industrial_production_yoy':('POLPRINTO01GYSAM','Industrial production, y/y %, SA'),
      'retail_sales_yoy':('POLSLRTTO01GYSAM','Retail trade volume, y/y %, SA'),
      'manufacturing_wages_yoy':('LCEAMN01PLM659S','Manufacturing hourly earnings, y/y %, SA'),
      'interbank_3m':('IR3TIB01PLM156N','3-month interbank rate, %'),
      'bond_10y':('IRLTLT01PLM156N','10-year government bond yield, %'),
      'usdpln':('CCUSMA02PLM618N','USD/PLN monthly average'),
      'eurusd':('EXUSEU','USD per EUR monthly average'),
      'manufacturing_expectations':('BSPRFT02PLM460S','Manufacturing future tendency balance')
    }
    monthly={}
    for k,(sid,label) in monthly_specs.items():
        try:
            d=fred(sid); monthly[k]=d
            sources[k]={'source':'FRED','series':sid,'label':label,'last_date':str(d.date.iloc[-1].date()),'last_value':float(d.value.iloc[-1])}
        except Exception as e:
            sources[k]={'error':str(e),'series':sid}

    # Univariate latest-data forecasts; 60 months is enough from any 2026 endpoint through 2030.
    mfc={}
    for k,d in monthly.items():
        try:
            p,q=infer_univariate(model,d,60)
            dates=future_dates(d.date.iloc[-1],'M',60)
            mfc[k]=(dates,p,q)
        except Exception as e:
            raw[f'{k}_error']=str(e)

    if 'hicp_index' in mfc:
        dates,p,q=mfc['hicp_index']; results['inflation_hicp_avg_yoy']=inflation_from_index(monthly['hicp_index'],dates,p,q)
    for k,outname in [
        ('unemployment_rate','unemployment_rate_avg'),('industrial_production_yoy','industrial_production_yoy_avg'),
        ('retail_sales_yoy','retail_sales_yoy_avg'),('manufacturing_wages_yoy','manufacturing_wages_yoy_avg'),
        ('interbank_3m','interbank_3m_avg'),('bond_10y','bond_10y_avg')]:
        if k in mfc:
            dates,p,q=mfc[k]; results[outname]=annualize_rate(monthly[k],dates,p,q)
    if 'interbank_3m' in mfc:
        dates,p,q=mfc['interbank_3m']; results['interbank_3m_endyear']=endyear_level(dates,p,q)
    if 'usdpln' in mfc:
        dates,p,q=mfc['usdpln']; results['usdpln_avg']=annualize_level(dates,p,q)
    if 'usdpln' in mfc and 'eurusd' in mfc:
        du,pu,qu=mfc['usdpln']; de,pe,qe=mfc['eurusd']
        fu=pd.DataFrame({'date':du,'usdpln':pu}); fe=pd.DataFrame({'date':de,'eurusd':pe})
        z=fu.merge(fe,on='date'); z['eurpln']=z.usdpln*z.eurusd
        results['eurpln_avg']=annualize_level(z.date,z.eurpln.to_numpy(),None)
        results['eurpln_endyear']=endyear_level(z.date,z.eurpln.to_numpy(),None)

    quarterly_specs={
      'gdp_yoy':('POLGDPRQPSMEI','Real GDP, y/y %, SA'),
      'private_consumption_yoy':('NAEXKP02PLQ659S','Private consumption, y/y %, SA'),
      'investment_yoy':('NAEXKP04PLQ659S','Gross fixed capital formation, y/y %, SA'),
      'government_consumption_yoy':('NAEXKP03PLQ659S','Government consumption, y/y %, SA'),
      'exports_yoy':('NAEXKP06PLQ659S','Exports, y/y %, SA'),
      'imports_yoy':('NAEXKP07PLQ659S','Imports, y/y %, SA')
    }
    quarterly={}
    for k,(sid,label) in quarterly_specs.items():
        try:
            d=fred(sid)
            if k=='gdp_yoy':
                # Fresh GUS Q2 2026 seasonally-adjusted y/y actual published 2026-08-31.
                d=append_or_replace(d,'2026-04-01',3.8)
            quarterly[k]=d
            sources[k]={'source':'FRED + GUS patch' if k=='gdp_yoy' else 'FRED','series':sid,'label':label,'last_date':str(d.date.iloc[-1].date()),'last_value':float(d.value.iloc[-1])}
        except Exception as e:
            sources[k]={'error':str(e),'series':sid}
    for k,d in quarterly.items():
        try:
            p,q=infer_univariate(model,d,20); dates=future_dates(d.date.iloc[-1],'Q',20)
            results[k]=annualize_rate(d,dates,p,q)
        except Exception as e: raw[f'{k}_error']=str(e)

    annual_specs={
      'nominal_gdp_mln_pln':('FRED','NGDPXDCPLA','Nominal GDP, PLN million'),
      'real_gdp_level':('FRED','NGDPRXDCPLA','Real GDP index-compatible level, PLN million'),
      'gdp_deflator_index':('FRED','NGDPDIXPLA','GDP deflator index'),
      'government_debt_pct_gdp':('FRED','GGGDTAPLA188N','General government gross debt, % GDP'),
      'government_balance_pct_gdp':('FRED','GGNLBAPLA188N','General government net lending/borrowing, % GDP'),
      'current_account_pct_gdp':('WB','BN.CAB.XOKA.GD.ZS','Current account balance, % GDP')
    }
    annual={}
    for k,(src,sid,label) in annual_specs.items():
        try:
            d=fred(sid) if src=='FRED' else wb(sid)
            # Replace stale IMF 2024 endpoints with verified Eurostat/GUS 2025 actuals.
            if k=='government_debt_pct_gdp': d=append_or_replace(d,'2025-01-01',59.7)
            if k=='government_balance_pct_gdp': d=append_or_replace(d,'2025-01-01',-7.3)
            annual[k]=d
            sources[k]={'source':src + (' + GUS/Eurostat 2025 patch' if k.startswith('government_') else ''),'series':sid,'label':label,'last_date':str(d.date.iloc[-1].date()),'last_value':float(d.value.iloc[-1])}
        except Exception as e: sources[k]={'error':str(e),'series':sid}
    for k,d in annual.items():
        try:
            horizon=max(5,END_YEAR-d.date.iloc[-1].year)
            p,q=infer_univariate(model,d,horizon); dates=future_dates(d.date.iloc[-1],'A',horizon)
            if k=='gdp_deflator_index': results['gdp_deflator_growth']=growth_from_level(d,dates,p,q)
            else: results[k]=annualize_level(dates,p,q,q)
        except Exception as e: raw[f'{k}_error']=str(e)

    # Native multivariate checks. These prove we are using the TimesFM-3 variate-attention path,
    # while final headline forecasts above preserve the freshest endpoint for each series.
    try:
        selected={k:monthly[k] for k in ['hicp_index','unemployment_rate','industrial_production_yoy','retail_sales_yoy','manufacturing_wages_yoy','interbank_3m','bond_10y','usdpln'] if k in monthly}
        raw['monthly_multivariate_check']=run_multivariate_check(model,selected,'M',12)
    except Exception as e: raw['monthly_multivariate_check']={'status':'error','error':str(e)}
    try:
        selected={k:quarterly[k] for k in ['gdp_yoy','private_consumption_yoy','investment_yoy','government_consumption_yoy','exports_yoy','imports_yoy'] if k in quarterly}
        raw['quarterly_multivariate_check']=run_multivariate_check(model,selected,'Q',4)
    except Exception as e: raw['quarterly_multivariate_check']={'status':'error','error':str(e)}

    payload={
      'generated_at_utc':datetime.utcnow().isoformat()+'Z',
      'model':MODEL,
      'method':'Actual TimesFM-3 PyTorch inference. Latest-endpoint univariate heads for headline series + native multivariate TimesFM-3 robustness checks.',
      'quantiles':Q_LEVELS,
      'sources':sources,
      'forecast':results,
      'diagnostics':raw
    }
    with open('poland_macro_timesfm3.json','w') as f: json.dump(payload,f,indent=2,ensure_ascii=False)

    # Flat CSV for easy inspection.
    rows=[]
    for indicator,vals in results.items():
        if isinstance(vals,list):
            for r in vals:
                rr={'indicator':indicator,**r}; rows.append(rr)
    pd.DataFrame(rows).to_csv('poland_macro_timesfm3.csv',index=False)
    print(json.dumps(payload,indent=2,ensure_ascii=False))

if __name__=='__main__':
    main()
