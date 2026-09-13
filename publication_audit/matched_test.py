"""Diagnostic audit of frozen outputs; this script never writes a forecast registry."""
from __future__ import annotations
import csv, hashlib, importlib.metadata, json, os, platform, shutil, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from huggingface_hub import snapshot_download
from timesfm3 import TimesFM3Evaluator, ModelConfig

ROOT=Path('publication_audit_run'); ROOT.mkdir(exist_ok=True)
SRC=Path('frozen_google')
PROTOCOL=json.loads(Path('publication_audit/PROTOCOL.json').read_text())
EXPECTED={'national_inputs.csv':'910ac907fedb53b92f7e18ae93d58732c52db406864479097c6cf299c81b6d0c','historical_paths.json':'68d9b03c0ee7ff4ff1af9bb6d7e8de2ed8ca8dd18fce7ae8e57f60720dff0bf1','execution.json':'9a6abd47b0a4a225ec4af5e0585da5e6027b4700bbb9f6069e0d6c455b2c0ed7','current_path.json':'335b087a3b19857bd4c1d5c8501f30154ae6f371ac4c1ae9ca9bbdc76d584f84'}
def write_csv(name, rows):
 if not rows: return
 with (ROOT/name).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
checks=[]
for name, expected in EXPECTED.items():
 digest=hashlib.sha256((SRC/name).read_bytes()).hexdigest()
 checks.append({'test':'frozen_'+name,'passed':digest==expected,'value':digest})
 if digest!=expected: raise ValueError('Frozen source mismatch: '+name)
oldmeta=json.loads((SRC/'execution.json').read_text())
assert oldmeta['revision']==PROTOCOL['model_revision']
df=pd.read_csv(SRC/'national_inputs.csv',parse_dates=['date']).set_index('date')
assert df.shape==(199,9) and list(df.columns)[0]=='TOTAL'
assert df.index.equals(pd.date_range('2010-01-01','2026-07-01',freq='MS'))
assert np.isfinite(df.to_numpy()).all()
shutil.copy2('publication_audit/PROTOCOL.json',ROOT/'PROTOCOL.json')
shutil.copy2('publication_audit/matched_test.py',ROOT/'matched_test.py')
shutil.copy2(SRC/'national_inputs.csv',ROOT/'national_inputs.csv')
np.random.seed(PROTOCOL['seed']);torch.manual_seed(PROTOCOL['seed']);torch.set_num_threads(2)
cp=snapshot_download(PROTOCOL['model'],revision=PROTOCOL['model_revision'])
model=TimesFM3Evaluator(ModelConfig(checkpoint_path=cp,per_core_batch_size=2,device='cpu'))
metadata={'audit_date':'2026-09-12','generated_at_utc':datetime.now(timezone.utc).isoformat(),'github_sha':os.environ.get('GITHUB_SHA'),'github_run_id':os.environ.get('GITHUB_RUN_ID'),'python':platform.python_version(),'model':PROTOCOL['model'],'model_revision':PROTOCOL['model_revision'],'packages':{p:importlib.metadata.version(p) for p in ['timesfm','torch','numpy','pandas','huggingface_hub','safetensors']},'model_files':{},'task':'matched historical diagnostic; not a new forecast vintage'}
for name in ['model.safetensors','config.json']:
 path=Path(cp)/name
 if path.exists():
  sha=hashlib.sha256()
  with path.open('rb') as f:
   for chunk in iter(lambda:f.read(8*1024*1024),b''):sha.update(chunk)
  metadata['model_files'][name]={'sha256':sha.hexdigest(),'bytes':path.stat().st_size}
(ROOT/'execution.json').write_text(json.dumps(metadata,indent=2))
origins=[pd.Timestamp(y,m,9) for y in range(2015,2026) for m in [3,6,9,12]]
oldpaths={r['origin']:r for r in json.loads((SRC/'historical_paths.json').read_text())}
levels=np.arange(1,10,dtype=float)/10
rows=[];raw=[];rep=[]
def scoring(y, q):
 residual=y-q
 pinball=np.maximum(levels*residual,(levels-1)*residual)
 weighted=.5*abs(y-q[4])
 for lower in [.1,.2,.3,.4]:
  a=2*lower;j=int(round(lower*10))-1;lo=q[j];hi=q[8-j]
  score=hi-lo+2/a*max(lo-y,0)+2/a*max(y-hi,0)
  weighted+=(a/2)*score
 wis=weighted/4.5
 if not np.isclose(wis,2*pinball.mean(),rtol=1e-10,atol=1e-10):raise ValueError('WIS identity failed')
 return float(pinball.mean()),float(wis)
for variant in PROTOCOL['variants']:
 contexts=[];ends=[]
 for origin in origins:
  end=origin.replace(day=1)-pd.DateOffset(months=2);hist=df.loc[:end]
  contexts.append(hist.T.to_numpy(np.float32) if variant=='nine_series' else hist.TOTAL.to_numpy(np.float32));ends.append(end)
 print('START',variant,len(contexts),'contexts',flush=True)
 outs=list(model.predict_batch(contexts=contexts,horizon=18,return_quantiles=True,use_symmetric_averaging=False))
 assert len(outs)==len(origins)
 for origin,end,out in zip(origins,ends,outs):
  f=np.asarray(out.forecast,dtype=float);q=np.asarray(out.quantiles,dtype=float)
  if f.ndim==2:f=f[0]
  if q.ndim==3:q=q[0]
  assert f.shape==(18,) and q.shape==(18,9) and np.isfinite(f).all() and np.isfinite(q).all()
  dates=pd.date_range(end+pd.offsets.MonthBegin(1),periods=18,freq='MS')
  rec={'variant':variant,'origin':str(origin.date()),'context_end':str(end.date()),'dates':[str(d.date()) for d in dates],'point':f.tolist(),'native_deciles':q.tolist()};raw.append(rec)
  if variant=='nine_series':
   old=np.asarray(oldpaths[str(origin.date())]['forecast'])[0]
   rep.append({'origin':str(origin.date()),'max_abs_point_difference':float(abs(f-old).max()),'same_dates':list(oldpaths[str(origin.date())]['dates'])==rec['dates']})
  for h,(dt,point,qq) in enumerate(zip(dates,f,q),1):
   if dt>pd.Timestamp(PROTOCOL['score_target_cutoff']) or dt not in df.index:continue
   y=float(df.loc[dt,'TOTAL']);cross=bool(np.any(np.diff(qq)<0));pin,wis=scoring(y,qq)
   row={'variant':variant,'origin':str(origin.date()),'origin_year':int(origin.year),'context_end':str(end.date()),'target':str(dt.date()),'h':h,'months_from_origin':(dt.year-origin.year)*12+dt.month-origin.month,'actual':y,'point':float(point),'median':float(qq[4]),'error':float(point-y),'absolute_error':float(abs(point-y)),'squared_error':float((point-y)**2),'mean_pinball':pin,'wis_native':wis,'crossed_quantiles':int(cross),'point_median_gap':float(abs(point-qq[4])),'coverage80':int(qq[0]<=y<=qq[8]),'width80':float(qq[8]-qq[0])}
   for j,p in enumerate(levels):row[f'q{int(round(p*100))}']=float(qq[j]);row[f'cdf{int(round(p*100))}']=int(y<=qq[j])
   rows.append(row)
 print('DONE',variant,flush=True)
 (ROOT/'native_paths.json').write_text(json.dumps(raw))
 write_csv('native_scores.csv',rows)
# Current historical-vintage replication only: never append results to the contest.
curref=json.loads((SRC/'current_path.json').read_text());hcur=len(curref['dates']);curr=[]
for variant in PROTOCOL['variants']:
 ctx=df.T.to_numpy(np.float32) if variant=='nine_series' else df.TOTAL.to_numpy(np.float32)
 out=list(model.predict_batch(contexts=[ctx],horizon=hcur,return_quantiles=True,use_symmetric_averaging=False))[0]
 f=np.asarray(out.forecast,dtype=float);q=np.asarray(out.quantiles,dtype=float)
 if f.ndim==2:f=f[0]
 if q.ndim==3:q=q[0]
 curr.append({'variant':variant,'audit_date':'2026-09-12','input_cutoff':'2026-07-01','not_a_new_forecast_vintage':True,'dates':curref['dates'],'point':f.tolist(),'native_deciles':q.tolist()})
 if variant=='nine_series':
  checks.append({'test':'current_nine_point_reproduction','passed':bool(np.allclose(f,np.asarray(curref['forecast'])[0],atol=1e-5,rtol=0)),'value':float(np.max(np.abs(f-np.asarray(curref['forecast'])[0])))})
(ROOT/'current_diagnostic.json').write_text(json.dumps(curr))
write_csv('reproduction.csv',rep)
r=pd.DataFrame(rows);summary=[]
for cohort,mask in [('ALL',np.ones(len(r),bool)),('2015-2019',r.origin_year<=2019),('2020-2022',r.origin_year.between(2020,2022)),('2023-2025',r.origin_year>=2023)]:
 for (variant,h),d in r.loc[mask & r.h.isin(PROTOCOL['reported_horizons'])].groupby(['variant','h']):
  row={'cohort':cohort,'variant':variant,'h':int(h),'n':len(d),'n_origin_years':int(d.origin_year.nunique()),'mae':float(d.absolute_error.mean()),'rmse':float(np.sqrt(d.squared_error.mean())),'wis_native':float(d.wis_native.mean()),'mean_pinball':float(d.mean_pinball.mean()),'coverage80':float(d.coverage80.mean()),'width80':float(d.width80.mean()),'crossing_rows':int(d.crossed_quantiles.sum())}
  for p in range(10,100,10):row[f'coverage_decile{p}']=float(d[f'cdf{p}'].mean())
  summary.append(row)
write_csv('native_summary.csv',summary)
rng=np.random.default_rng(PROTOCOL['seed']);pairs=[]
for h in PROTOCOL['reported_horizons']:
 one=r[(r.variant=='one_series')&(r.h==h)];nine=r[(r.variant=='nine_series')&(r.h==h)]
 d=one.merge(nine,on=['origin','target','h'],suffixes=('_one','_nine'),validate='one_to_one')
 assert len(d)==len(one)==len(nine) and np.array_equal(d.actual_one,d.actual_nine)
 for field in ['absolute_error','wis_native']:
  d['delta']=d[field+'_nine']-d[field+'_one'];bs=d.groupby('origin_year_one').delta.agg(['sum','count']).to_numpy(float)
  ix=rng.integers(0,len(bs),size=(5000,len(bs)));samples=bs[ix,0].sum(axis=1)/bs[ix,1].sum(axis=1)
  pairs.append({'h':h,'metric':'MAE' if field=='absolute_error' else 'WIS_native','n_pairs':len(d),'n_origin_years':len(bs),'one_series':float(d[field+'_one'].mean()),'nine_series':float(d[field+'_nine'].mean()),'delta_nine_minus_one':float(d.delta.mean()),'gain_pct':float(100*(1-d[field+'_nine'].mean()/d[field+'_one'].mean())),'delta_ci025':float(np.quantile(samples,.025)),'delta_ci975':float(np.quantile(samples,.975)),'bootstrap':'origin-year clustered percentile; pointwise exploratory CI, not independent holdout'})
write_csv('paired_native_comparison.csv',pairs)
checks.extend([{'test':'old_nine_historical_reproduction','passed':max(t['max_abs_point_difference'] for t in rep)<=1e-5,'value':max(t['max_abs_point_difference'] for t in rep)},{'test':'native_quantiles_ordered','passed':int(r.crossed_quantiles.sum())==0,'value':int(r.crossed_quantiles.sum())},{'test':'point_is_native_median','passed':float(r.point_median_gap.max())<=1e-5,'value':float(r.point_median_gap.max())},{'test':'paired_identical_targets_and_actuals','passed':True,'value':'enforced by assertions'},{'test':'wis_equals_twice_mean_pinball','passed':True,'value':'asserted for every score row'}])
(ROOT/'checks.json').write_text(json.dumps(checks,indent=2))
metadata['finished_at_utc']=datetime.now(timezone.utc).isoformat();metadata['native_scored_rows']=len(rows);metadata['historical_calls']=88
(ROOT/'execution.json').write_text(json.dumps(metadata,indent=2))
print(json.dumps({'checks':checks,'pairs':pairs},indent=2),flush=True)
