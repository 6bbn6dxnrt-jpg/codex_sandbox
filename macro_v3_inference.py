"""Poland Macro v3: auditable inference challenge, not claims of model superiority.
Historical folds use latest-vintage data and conservative release-lag proxies.
No realized future covariates, no institutional forecasts in model inputs.
"""
from __future__ import annotations
import hashlib, json, os, platform, re, time, traceback
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd
import requests

ROOT=Path('poland_macro_v3_run');RAW=ROOT/'raw';CLEAN=ROOT/'clean';ROOT.mkdir(exist_ok=True);RAW.mkdir(exist_ok=True);CLEAN.mkdir(exist_ok=True)
SUP=[]
urls={
 'gus_cpi_full':'https://stat.gov.pl/obszary-tematyczne/ceny-handel/wskazniki-cen/wskazniki-cen-towarow-i-uslug-konsumpcyjnych-pot-inflacja-/miesieczne-wskazniki-cen-towarow-i-uslug-konsumpcyjnych-od-1982-roku/',
 'gus_gdp_nsa.xlsx':'https://stat.gov.pl/download/gfx/portalinformacyjny/pl/defaultaktualnosci/5480/3/96/1/pkb_niewyrownany_sezonowo_tablica.xlsx',
 'gus_gdp_sa.xlsx':'https://stat.gov.pl/download/gfx/portalinformacyjny/pl/defaultaktualnosci/5480/3/96/1/pkb_wyrownany_sezonowo_tablica.xlsx',
 'budget_2027':'https://www.gov.pl/web/premier/budzet-bezpieczenstwa-rozwoju-i-optymizmu',
 'budget_pap':'https://strefainwestorow.pl/wiadomosci/20260828/deficyt-budzetu-w-2027-r-planowany-na-2826-mld-zl-deficyt-sektora-gg-71-proc',
 'gus_august_flash':'https://stat.gov.pl/obszary-tematyczne/ceny-handel/wskazniki-cen/szybki-szacunek-wskaznika-cen-towarow-i-uslug-konsumpcyjnych-w-sierpniu-2026-r-,21,44.html'
}
for indicator in ['NGDP_RPCH','PCPIPCH','PCPIEPCH','GGXWDG_NGDP','GGXCNL_NGDP']:
 urls['imf_apr26_'+indicator]='https://www.imf.org/external/datamapper/api/v1/'+indicator+'/POL'

def download(item):
 name,url=item
 try:
  r=requests.get(url,timeout=35);r.raise_for_status();path=RAW/(name if name.endswith('.xlsx') else name+'.html');path.write_bytes(r.content)
  return {'name':name,'url':url,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(r.content).hexdigest(),'status':'ok'}
 except Exception as e:return {'name':name,'url':url,'status':'error','error':repr(e)}
with ThreadPoolExecutor(max_workers=5) as p:SUP=list(p.map(download,urls.items()))
(ROOT/'supplement_manifest.json').write_text(json.dumps(SUP,indent=2));print('Supplement',SUP,flush=True)

def read(name):
 d=pd.read_csv(CLEAN/(name+'.csv'),parse_dates=['date']).set_index('date')['value'].sort_index();return d.astype(float)
def monthly(name):return read(name).resample('MS').mean().dropna()

# Preserve observed current releases. Quarterly NSA level bridge uses same-quarter
# preceding-year levels; it is NOT an official revised full historical vintage.
gdp=read('EU_GDP_PL_NSA').copy();reconciliation=[]
for date,rate in [('2026-01-01',3.5),('2026-04-01',3.9)]:
 dt=pd.Timestamp(date);old=float(gdp.loc[dt]);gdp.loc[dt]=gdp.loc[dt-pd.DateOffset(years=1)]*(1+rate/100)
 reconciliation.append({'series':'gdp_nsa_level','date':date,'old':old,'new':float(gdp.loc[dt]),'yoy_source':rate,'status':'GUS release bridge; not an official level'})
gdp.to_frame('value').to_csv(CLEAN/'MODEL_GDP_LEVEL.csv',index_label='date')
# FRED CPI index is retired after March 2025. Extend using published GUS y/y rates,
# retaining calendar-month base levels. Rounded monthly rates introduce ~0.05pp
# uncertainty in reconstructed annual inflation; output is rounded to 0.1pp.
cpi=read('POLCPIALLMINMEI')
updates={'2025-04-01':4.3,'2025-05-01':4.0,'2025-06-01':4.1,'2025-07-01':3.1,'2025-08-01':2.9,'2025-09-01':2.9,'2025-10-01':2.8,'2025-11-01':2.5,'2025-12-01':2.4,'2026-01-01':2.1,'2026-02-01':2.1,'2026-03-01':3.0,'2026-04-01':3.2,'2026-05-01':3.1,'2026-06-01':2.5,'2026-07-01':3.0,'2026-08-01':3.4}
for date,rate in updates.items():
 dt=pd.Timestamp(date);cpi.loc[dt]=cpi.loc[dt-pd.DateOffset(years=1)]*(1+rate/100)
cpi=cpi.sort_index();cpi.to_frame('value').to_csv(CLEAN/'MODEL_CPI_LEVEL.csv',index_label='date')
reconciliation.append({'series':'cpi_index','source':'FRED/OECD to March 2025; GUS published monthly y/y thereafter','updates_yoy':updates,'latest_status':'August 2026 flash, 31 August release','annual_reconstruction':'ratio of annual mean index levels; small rounding uncertainty'})
# FX: use original monthly USD series + monthly average EURUSD historically.
# Refresh 2025-26 with NBP daily means, excluding incomplete September.
usd=monthly('CCUSMA02PLM618N');eu=monthly('EXUSEU');fxidx=usd.index.intersection(eu.index);eurpln=usd.loc[fxidx]*eu.loc[fxidx]
for code in ['EUR','USD']:
 s=monthly('NBP_'+code+'_DAILY');s=s[s.index<'2026-09-01']
 if code=='EUR':eurpln=pd.concat([eurpln[eurpln.index<'2025-01-01'],s])
 else:usd=pd.concat([usd[usd.index<'2025-01-01'],s])
eurpln.to_frame('value').to_csv(CLEAN/'MODEL_EURPLN.csv',index_label='date');usd.to_frame('value').to_csv(CLEAN/'MODEL_USDPLN.csv',index_label='date')
# The historical EURPLN approximation is disclosed: product of monthly means
# before 2025, exact NBP daily means from 2025. Do not claim tick-level history.
reconciliation.append({'series':'eurpln','history':'product of monthly USDPLN and USDEUR means before 2025; NBP daily mean from 2025','warning':'historical cross-rate approximation before 2025'})
(ROOT/'reconciliation.json').write_text(json.dumps(reconciliation,indent=2))

series={'gdp':gdp.pct_change(4)*100,'cpi':cpi.pct_change(12)*100,'hicp':monthly('CP0000PLM086NEST').pct_change(12)*100,'rate3m':monthly('IR3TIB01PLM156N'),'yield10y':monthly('IRLTLT01PLM156N'),'eurpln':eurpln,'usdpln':usd}
series={k:v.dropna().loc['2000-01-01':] for k,v in series.items()}
for name,s in series.items():s.to_frame('value').to_csv(CLEAN/('TARGET_'+name+'.csv'),index_label='date')
# Covariates dated conservatively: previous quarter, or two-month lag. Only
# forward filling after an observation exists. No backward filling of unknowns.
br=monthly('MCOILBRENTEU');gas=monthly('PNGASEUUSDM');ecb=monthly('ECBDFR')
ea=read('EU_GDP_EA20_SCA').pct_change(4)*100

def covariates(idx,name):
 freq='QS' if name=='gdp' else 'MS';lag=1 if name=='gdp' else 2
 ss=[br.resample(freq).mean(),gas.resample(freq).mean(),ecb.resample(freq).mean()]
 if name=='gdp':ss.append(ea)
 cols=[]
 for s in ss:
  s=s.shift(lag);col=s.reindex(s.index.union(idx)).sort_index().ffill().reindex(idx)
  if col.isna().any():raise ValueError('missing historical exogenous context '+name)
  cols.append(col.to_numpy(np.float32))
 return np.vstack(cols)

from huggingface_hub import HfApi, snapshot_download
from timesfm3 import TimesFM3Evaluator, ModelConfig
import torch, importlib.metadata
np.random.seed(20260909);torch.manual_seed(20260909);torch.set_num_threads(2)
revision=HfApi().model_info('google/timesfm-3.0-pytorch').sha
checkpoint=snapshot_download('google/timesfm-3.0-pytorch',revision=revision)
model=TimesFM3Evaluator(ModelConfig(checkpoint_path=checkpoint,per_core_batch_size=4,device='cpu'))
meta={'as_of':'2026-09-09','information_cutoff':'2026-09-08T23:59:59+02:00','model':'google/timesfm-3.0-pytorch','model_revision':revision,'seed':20260909,'python':platform.python_version(),'packages':{p:importlib.metadata.version(p) for p in ['timesfm','torch','numpy','pandas','huggingface_hub']},'historical_evaluation':'latest-vintage pseudo-real-time; release lags are proxies; foundation-model pretraining overlap not ruled out','selection':'no parameter tuning or winner claims in this script','forecast_statistic':'TimesFM point output is a median','license':'weights non-commercial; see preserved model card'}
(ROOT/'inference_metadata.json').write_text(json.dumps(meta,indent=2))
records=[]
for name,s in series.items():
 quarterly=name=='gdp';freq='QS' if quarterly else 'MS';h=12 if quarterly else 36
 tasks=[]
 for year in range(2011,2026):
  for month in [3,6,9,12]:
   origin=pd.Timestamp(year=year,month=month,day=9)
   if quarterly:
    end=pd.Timestamp(year=year-1 if month==3 else year,month=10 if month==3 else month-5,day=1)
   else:
    # Two monthly observations behind calendar month of forecast (e.g. July on Sept 9).
    end=pd.Timestamp(year=year,month=month-2,day=1)
   hist=s.loc[:end]
   if len(hist)<32:continue
   if hist.index[-1]!=end:continue
   tasks.append((origin,hist))
 for variant in ['timesfm_univariate','timesfm_exante']:
  contexts=[hist.to_numpy(np.float32) for _,hist in tasks]
  kwargs={}
  if variant=='timesfm_exante':
   cs=[]
   for _,hist in tasks:
    past=covariates(hist.index,name);cs.append(np.concatenate([past,np.repeat(past[:,-1:],h,axis=1)],axis=1))
   kwargs['past_future_covariates']=cs
  print('INFER',name,variant,'folds',len(tasks),flush=True)
  outputs=list(model.predict_batch(contexts=contexts,horizon=h,return_quantiles=False,use_symmetric_averaging=False,**kwargs))
  if len(outputs)!=len(tasks):raise ValueError('wrong batch output count')
  for (origin,hist),out in zip(tasks,outputs):
   f=np.asarray(out.forecast,dtype=float).reshape(-1)
   if len(f)!=h or not np.isfinite(f).all():raise ValueError('bad forecast output')
   offset=pd.offsets.QuarterBegin(startingMonth=1) if quarterly else pd.offsets.MonthBegin(1)
   dates=pd.date_range(hist.index[-1]+offset,periods=h,freq=freq)
   records.append({'metric':name,'model':variant,'origin':str(origin.date()),'context_end':str(hist.index[-1].date()),'dates':[str(x.date()) for x in dates],'forecast':f.tolist()})
  (ROOT/'timesfm_backtest_paths.json').write_text(json.dumps(records))
 # Fixed publication horizon ends precisely in December / Q4 2030.
 hist=s;offset=pd.offsets.QuarterBegin(startingMonth=1) if quarterly else pd.offsets.MonthBegin(1)
 dates=pd.date_range(hist.index[-1]+offset,pd.Timestamp('2030-12-01'),freq=freq);hcur=len(dates)
 for variant in ['timesfm_univariate','timesfm_exante']:
  kwargs={}
  if variant=='timesfm_exante':
   past=covariates(hist.index,name);kwargs['past_future_covariates']=[np.concatenate([past,np.repeat(past[:,-1:],hcur,axis=1)],axis=1)]
  out=list(model.predict_batch(contexts=[hist.to_numpy(np.float32)],horizon=hcur,return_quantiles=True,use_symmetric_averaging=False,**kwargs))[0]
  current={'metric':name,'model':variant,'origin':'2026-09-09','context_end':str(hist.index[-1].date()),'dates':[str(x.date()) for x in dates],'forecast':np.asarray(out.forecast).reshape(-1).tolist(),'marginal_quantiles_NOT_annual':np.asarray(out.quantiles).tolist()}
  (ROOT/('current_'+name+'_'+variant+'.json')).write_text(json.dumps(current))
print('DONE',len(records),'retrospective model paths',flush=True)
