import json
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from timesfm3 import TimesFM3Evaluator, ModelConfig
from timesfm_poland_forecast import fred, append_or_replace

MODEL='google/timesfm-3.0-pytorch'; END=2030; QS=[.1,.2,.3,.4,.5,.6,.7,.8,.9]

def m(d): return d.set_index('date').resample('MS').mean().interpolate(limit_direction='both').reset_index()
def q(d): return d.set_index('date').resample('QS').mean().interpolate(limit_direction='both').reset_index()
def yoy(d,n):
    z=d.copy(); z['value']=z.value.pct_change(n)*100; return z.dropna().reset_index(drop=True)
def align(d,idx): return d.set_index('date').value.reindex(idx).interpolate(limit_direction='both').ffill().bfill().to_numpy(np.float32)
def fut(last,freq,h):
    off=pd.offsets.MonthBegin(1) if freq=='M' else pd.offsets.QuarterBegin(startingMonth=1)
    return pd.date_range(pd.Timestamp(last)+off,periods=h,freq='MS' if freq=='M' else 'QS')
def kpo(dt): return {2023:.02,2024:.25,2025:.55,2026:1.,2027:.22}.get(dt.year,0.)
def defense(dt):
    a={2014:1.88,2020:2.2,2021:2.2,2022:2.4,2023:3.3,2024:4.12,2025:4.48,2026:4.81,2027:4.8,2028:4.8,2029:4.8,2030:4.8}; y=dt.year
    if y in a:return a[y]
    ys=sorted(a)
    if y<ys[0]:return a[ys[0]]
    if y>ys[-1]:return a[ys[-1]]
    lo=max(x for x in ys if x<y); hi=min(x for x in ys if x>y)
    return a[lo]+(a[hi]-a[lo])*(y-lo)/(hi-lo)
def ets2(dt): return 1. if dt.year>=2028 else 0.
def ea_future(dt): return {2026:.9,2027:1.2,2028:1.4,2029:1.5,2030:1.5}.get(dt.year,1.5)
def ecb_future(dt): return 2.25 if dt.year==2026 else 2.0
def brent_future(dt,s='base'):
    y=min(max(dt.year,2026),2030)
    x={2026:74.,2027:69.,2028:66.,2029:65.,2030:65.}[y]
    return x+({2026:35,2027:25,2028:10,2029:5,2030:3}[y] if s=='energy_stress' else (-10 if s=='energy_relief' else 0))
def gas_future(dt,s='base'):
    qq=(dt.month-1)//3+1
    x=({1:14,2:16,3:23,4:22}[qq] if dt.year==2026 else {1:20,2:17,3:15,4:14}[qq] if dt.year==2027 else 12 if dt.year==2028 else 10.5 if dt.year==2029 else 10)
    return x*({'energy_stress':1.45,'energy_relief':.75}.get(s,1.))

def annual(hist,dates,point,quant=None):
    h=hist[['date','value']].rename(columns={'value':'point'}) if hist is not None else pd.DataFrame(columns=['date','point'])
    f=pd.DataFrame({'date':dates,'point':point}); c=pd.concat([h,f]).drop_duplicates('date',keep='last').sort_values('date'); out=[]
    for y in range(2026,END+1):
        v=c[c.date.dt.year==y].point
        if len(v):
            r={'year':y,'point':float(v.mean())}
            if quant is not None:
                qarr=np.asarray(quant)
                if qarr.ndim==3:qarr=qarr[0]
                for j,x in enumerate(QS):
                    z=pd.concat([h,pd.DataFrame({'date':dates,'point':qarr[:,j]})]).drop_duplicates('date',keep='last').sort_values('date')
                    w=z[z.date.dt.year==y].point
                    if len(w): r[f'p{int(x*100)}']=float(w.mean())
            out.append(r)
    return out

def inflation(hist,dates,point,quant=None):
    h=hist[['date','value']].rename(columns={'value':'point'}); f=pd.DataFrame({'date':dates,'point':point}); c=pd.concat([h,f]).drop_duplicates('date',keep='last').sort_values('date'); out=[]
    for y in range(2026,END+1):
        a=c[c.date.dt.year==y].point; b=c[c.date.dt.year==y-1].point
        if len(a)==12 and len(b)==12:
            r={'year':y,'point':float((a.mean()/b.mean()-1)*100)}
            if quant is not None:
                qarr=np.asarray(quant)
                if qarr.ndim==3:qarr=qarr[0]
                for j,x in enumerate(QS):
                    z=pd.concat([h,pd.DataFrame({'date':dates,'point':qarr[:,j]})]).drop_duplicates('date',keep='last').sort_values('date'); aa=z[z.date.dt.year==y].point; bb=z[z.date.dt.year==y-1].point
                    if len(aa)==12 and len(bb)==12:r[f'p{int(x*100)}']=float((aa.mean()/bb.mean()-1)*100)
            out.append(r)
    return out

def endyear(hist,dates,point):
    h=hist[['date','value']].rename(columns={'value':'point'}) if hist is not None else pd.DataFrame(columns=['date','point']); c=pd.concat([h,pd.DataFrame({'date':dates,'point':point})]).drop_duplicates('date',keep='last').sort_values('date')
    return [{'year':y,'point':float(c[c.date.dt.year==y].iloc[-1].point)} for y in range(2026,END+1) if len(c[c.date.dt.year==y])]

def qcov(idx,fd,ea,br,gas,ecb,s):
    full=idx.append(fd); arr=[]
    for d,fn in [(ea,ea_future),(br,lambda x:brent_future(x,s)),(gas,lambda x:gas_future(x,s)),(ecb,ecb_future)]: arr.append(np.r_[align(d,idx),np.array([fn(x) for x in fd],np.float32)])
    arr += [np.array([fn(x) for x in full],np.float32) for fn in (kpo,defense,ets2)]
    return np.vstack(arr).astype(np.float32)
def mcov(idx,fd,br,gas,ecb,gip,s):
    full=idx.append(fd); arr=[]
    for d,fn in [(br,lambda x:brent_future(x,s)),(gas,lambda x:gas_future(x,s)),(ecb,ecb_future)]: arr.append(np.r_[align(d,idx),np.array([fn(x) for x in fd],np.float32)])
    gp=align(gip,idx); anchor=float(np.mean(gp[-12:])); arr.append(np.r_[gp,np.linspace(gp[-1],anchor,len(fd),dtype=np.float32)])
    arr += [np.array([fn(x) for x in full],np.float32) for fn in (kpo,defense,ets2)]
    return np.vstack(arr).astype(np.float32)

def gdp_run(model,gdp,ea,br,gas,ecb,s):
    idx=pd.DatetimeIndex(gdp[gdp.date>=pd.Timestamp('1998-01-01')].date); x=align(gdp,idx)[None,:]; h=(END-idx[-1].year)*4+(5-((idx[-1].month-1)//3+1)); fd=fut(idx[-1],'Q',h)
    o=list(model.predict_batch(contexts=[x],horizon=h,past_future_covariates=[qcov(idx,fd,ea,br,gas,ecb,s)],return_quantiles=True,use_symmetric_averaging=False))[0]
    f=np.asarray(o.forecast)[0]; qq=np.asarray(o.quantiles)[0]; return annual(gdp,fd,f,qq)
def monthly_run(model,hicp,r3,b10,usd,eur,br,gas,ecb,gip,s):
    ss=[hicp,r3,b10,usd,eur]; last=min(x.date.max() for x in ss); first=max(max(x.date.min() for x in ss),pd.Timestamp('2000-01-01')); idx=pd.date_range(first,last,freq='MS'); mat=np.vstack([align(x,idx) for x in ss]); h=(END-last.year)*12+(13-last.month); fd=fut(last,'M',h)
    o=list(model.predict_batch(contexts=[mat],horizon=h,past_future_covariates=[mcov(idx,fd,br,gas,ecb,gip,s)],return_quantiles=True,use_symmetric_averaging=False))[0]; f=np.asarray(o.forecast); qq=np.asarray(o.quantiles)
    out={'inflation_hicp_avg_yoy':inflation(hicp,fd,f[0],qq[0]),'interbank_3m_avg':annual(r3,fd,f[1],qq[1]),'interbank_3m_endyear':endyear(r3,fd,f[1]),'bond_10y_avg':annual(b10,fd,f[2],qq[2]),'usdpln_avg':annual(usd,fd,f[3],qq[3]),'usdpln_endyear':endyear(usd,fd,f[3])}
    ep=f[3]*f[4]; out['eurpln_avg']=annual(None,fd,ep); out['eurpln_endyear']=endyear(None,fd,ep); return out

def backtest(model,gdp,ea,br,gas,ecb):
    rec=[]
    for origin in map(pd.Timestamp,['2018-10-01','2019-10-01','2021-10-01','2022-10-01','2023-10-01','2024-10-01']):
        if origin not in set(gdp.date) or origin+pd.DateOffset(years=1)>gdp.date.max():continue
        hist=gdp[gdp.date<=origin]; idx=pd.DatetimeIndex(hist[hist.date>=pd.Timestamp('1998-01-01')].date); x=align(hist,idx)[None,:]; fd=pd.date_range(origin+pd.offsets.QuarterBegin(startingMonth=1),periods=4,freq='QS'); act=align(gdp,fd).astype(float)
        b=np.asarray(list(model.predict_batch(contexts=[x],horizon=4,return_quantiles=False,use_symmetric_averaging=False))[0].forecast).reshape(-1)[:4]
        cov=np.vstack([np.r_[align(d,idx),align(d,fd)] for d in (ea,br,gas,ecb)]+[np.array([fn(x) for x in idx.append(fd)]) for fn in (kpo,defense,ets2)]).astype(np.float32)
        c=np.asarray(list(model.predict_batch(contexts=[x],horizon=4,past_future_covariates=[cov],return_quantiles=False,use_symmetric_averaging=False))[0].forecast).reshape(-1)[:4]
        rec.append({'origin':str(origin.date()),'baseline_mae':float(np.mean(abs(b-act))),'conditional_oracle_mae':float(np.mean(abs(c-act)))})
    return {'note':'conditional uses realized future exogenous variables; diagnostic, not a real-time backtest','origins':rec,'mean_baseline_mae':float(np.mean([x['baseline_mae'] for x in rec])),'mean_conditional_oracle_mae':float(np.mean([x['conditional_oracle_mae'] for x in rec]))}
def raw_balance(model):
    d=append_or_replace(fred('GGNLBAPLA188N'),'2025-01-01',-7.3); h=END-2025; o=list(model.predict_batch(contexts=[d.value.to_numpy(np.float32)],horizon=h,return_quantiles=True,use_symmetric_averaging=False))[0]; fd=pd.date_range('2026-01-01',periods=h,freq='YS'); qarr=np.asarray(o.quantiles); qarr=qarr[0] if qarr.ndim==3 else qarr; return annual(None,fd,np.asarray(o.forecast).reshape(-1),qarr)
def fiscal(balance,gdp,inf):
    bm={x['year']:x['point'] for x in balance}; gm={x['year']:x['point'] for x in gdp}; im={x['year']:x['point'] for x in inf}; sfa={2026:1.,2027:.8,2028:.5,2029:.3,2030:.2}; d=59.7; out=[]
    for y in range(2026,2031):
        ng=(1+gm[y]/100)*(1+im[y]/100)-1; d=(d/100 + (-bm[y]/100)+sfa[y]/100)/(1+ng)*100; out.append({'year':y,'debt_pct_gdp':d,'balance_pct_gdp':bm[y],'nominal_growth_proxy_pct':ng*100,'sfa_assumption_pct_gdp':sfa[y]})
    return out

def main():
    model=TimesFM3Evaluator(ModelConfig(checkpoint_path=MODEL,per_core_batch_size=8,device='cpu'))
    gdp=append_or_replace(fred('POLGDPRQPSMEI'),'2026-04-01',3.8); hicp=fred('CP0000PLM086NEST'); r3=fred('IR3TIB01PLM156N'); b10=fred('IRLTLT01PLM156N'); usd=fred('CCUSMA02PLM618N'); eur=m(fred('EXUSEU'))
    br=m(fred('MCOILBRENTEU')); gas=m(fred('PNGASEUUSDM')); ecb=m(fred('ECBDFR')); gip=m(fred('DEUPROINDMISMEI')); ea=q(yoy(fred('CLV10MNACB1GQSCAEA20Q'),4)); brq=q(br); gasq=q(gas); ecbq=q(ecb)
    sc={}
    for s in ('base','energy_stress','energy_relief'): sc[s]={'gdp_yoy':gdp_run(model,gdp,ea,brq,gasq,ecbq,s),**monthly_run(model,hicp,r3,b10,usd,eur,br,gas,ecb,gip,s)}
    bal=raw_balance(model); fis=fiscal(bal,sc['base']['gdp_yoy'],sc['base']['inflation_hicp_avg_yoy']); bt=backtest(model,gdp,ea,brq,gasq,ecbq)
    out={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'model':MODEL,'version':'Poland Macro v2 conditional','method':'native TimesFM-3 past_future_covariates + scenarios + fiscal reconciliation','scenarios':sc,'raw_balance':bal,'fiscal_reconciliation_base':fis,'backtest':bt,
         'assumptions':{'kpo':'relative impulse index: 2024 .25, 2025 .55, 2026 1.0, 2027 .22, then 0','defence':'4.12% GDP 2024, 4.48% 2025, 4.81% 2026; held near 4.8%','ets2':'dummy on from 2028','energy_stress':'Brent uplift; EU gas +45%','energy_relief':'Brent -10 USD/bbl; EU gas -25%'},
         'benchmarks':{'EC':{'gdp':{2026:3.5,2027:2.8},'inflation':{2026:3.6,2027:2.9},'debt':{2026:64.5,2027:68.3}},'IMF':{'gdp':{2026:3.5,2027:2.7,2028:2.7,2029:2.6,2030:2.5},'inflation':{2026:2.7,2027:2.6,2028:2.5,2029:2.5,2030:2.5},'debt':{2026:65.5,2027:68.7,2028:71.6,2029:73.9,2030:75.9}},'NBP_Mar26_50pct_ranges':{'gdp':{2026:[3.1,4.7],2027:[2.,3.8],2028:[1.8,4.1]},'inflation':{2026:[1.6,2.9],2027:[1.1,3.7],2028:[.9,4.]}}}}
    json.dump(out,open('poland_macro_v2.json','w'),indent=2); rows=[]
    for s,z in sc.items():
        for metric,vals in z.items():
            for r in vals: rows.append({'scenario':s,'metric':metric,**r})
    pd.DataFrame(rows).to_csv('poland_macro_v2.csv',index=False); pd.DataFrame(fis).to_csv('poland_macro_v2_fiscal.csv',index=False); print(json.dumps({'base_gdp':sc['base']['gdp_yoy'],'base_inflation':sc['base']['inflation_hicp_avg_yoy'],'fiscal':fis,'backtest':bt},indent=2))
if __name__=='__main__':main()
