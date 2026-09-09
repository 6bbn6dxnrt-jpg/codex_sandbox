from __future__ import annotations
import json,io,zipfile,hashlib,re,platform,importlib.metadata
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
import requests,numpy as np,pandas as pd,torch
from huggingface_hub import HfApi,snapshot_download
from timesfm3 import TimesFM3Evaluator,ModelConfig
OUT=Path('v4_google');OUT.mkdir(exist_ok=True)
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
SOURCES=[('old','https://bazydanych.new.stat.gov.pl/file/201217/download?token=OHHpTA0J','4cae6387a72c21a01f043c90cbb4a55f2642333cf6515c3777b3966277f63646'),('new','https://bazydanych.new.stat.gov.pl/file/199315/download','14f0f0afdb90f0397deb9f142468d8f513181a80259ea51c2b1131035b777341')]
MAP={'TOTAL':(1,1),'FOOD':(3,3),'ALCOHOL_TOBACCO':(35,37),'CLOTHING':(41,43),'ENERGY':(51,53),'FUEL':(83,83),'HEALTH':(67,69),'EDUCATION':(103,105),'RESTAURANTS':(105,107)}
rows=[];manifest=[]
for kind,url,sha in SOURCES:
 r=requests.get(url,timeout=60);r.raise_for_status();digest=hashlib.sha256(r.content).hexdigest()
 if digest!=sha:raise ValueError('Source bytes changed; re-audit before inference')
 z=zipfile.ZipFile(io.BytesIO(r.content));strings=[]
 if 'xl/sharedStrings.xml' in z.namelist():
  strings=[''.join(e.itertext()) for e in E.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
 for rr in E.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('.//s:row',NS):
  cells={}
  for c in rr.findall('s:c',NS):
   letters=re.match('[A-Z]+',c.attrib['r']).group();col=0
   for ch in letters:col=col*26+ord(ch)-64
   v=c.find('s:v',NS)
   if c.attrib.get('t')=='s':value=strings[int(v.text)] if v is not None else None
   elif c.attrib.get('t')=='inlineStr':value=''.join(c.find('s:is',NS).itertext())
   else:
    try:value=float(v.text) if v is not None else None
    except ValueError:value=None
   cells[col-1]=value
  period=cells.get(0)
  if not isinstance(period,str) or not re.match(r'^\d{4} M\d{2}$',period):continue
  yy,mm=map(int,re.findall(r'\d+',period))
  if (kind=='old' and yy>=2026) or (kind=='new' and yy<2026):continue
  vals=[cells.get(ij[kind=='new']) for ij in MAP.values()]
  if any(v is None for v in vals):raise ValueError('Missing CPI category observation')
  rows.append([f'{yy:04d}-{mm:02d}-01',*[v-100 for v in vals]])
 manifest.append({'name':kind,'url':r.url,'sha256':digest})
df=pd.DataFrame(rows,columns=['date',*MAP]);df.date=pd.to_datetime(df.date);df=df.set_index('date').sort_index().loc[:'2026-07-01'];df.to_csv(OUT/'national_inputs.csv')
np.random.seed(20260909);torch.manual_seed(20260909);torch.set_num_threads(2)
repo='google/timesfm-3.0-pytorch';revision=HfApi().model_info(repo).sha;cp=snapshot_download(repo,revision=revision)
model=TimesFM3Evaluator(ModelConfig(checkpoint_path=cp,per_core_batch_size=2,device='cpu'))
origins=[pd.Timestamp(y,m,9) for y in range(2015,2026) for m in (3,6,9,12)]
contexts=[];lastdates=[]
for o in origins:
 end=o.replace(day=1)-pd.DateOffset(months=2);h=df.loc[:end]
 if len(h)<36:raise ValueError('Short context')
 contexts.append(h.to_numpy(np.float32).T);lastdates.append(h.index[-1])
outputs=list(model.predict_batch(contexts=contexts,horizon=18,return_quantiles=False,use_symmetric_averaging=False))
records=[]
for origin,last,o in zip(origins,lastdates,outputs):
 f=np.asarray(o.forecast,dtype=float)
 if f.shape!=(9,18) or not np.isfinite(f).all():raise ValueError('invalid shape')
 dates=pd.date_range(last+pd.offsets.MonthBegin(1),periods=18,freq='MS')
 records.append({'origin':str(origin.date()),'context_end':str(last.date()),'dates':[str(d.date()) for d in dates],'forecast':f.tolist()})
(OUT/'historical_paths.json').write_text(json.dumps(records))
fd=pd.date_range(df.index[-1]+pd.offsets.MonthBegin(1),'2027-12-01',freq='MS')
o=list(model.predict_batch(contexts=[df.to_numpy(np.float32).T],horizon=len(fd),return_quantiles=True,use_symmetric_averaging=False))[0]
(OUT/'current_path.json').write_text(json.dumps({'origin':'2026-09-09','context_end':str(df.index[-1].date()),'series':list(MAP),'dates':[str(x.date()) for x in fd],'forecast':np.asarray(o.forecast).tolist(),'marginal_quantiles':np.asarray(o.quantiles).tolist()}))
meta={'model':repo,'revision':revision,'generated_at_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),'packages':{p:importlib.metadata.version(p) for p in ['timesfm','torch','numpy','pandas']},'history_shape':list(df.shape),'historical_origins':len(origins),'source_manifest':manifest,'notes':['actual inference, no hand-authored predictions','native multivariate, nine CPI series','historical forecast inputs exclude future values','latest-vintage context; not a vintage-correct backtest','pretraining overlap unknown','current context July; August CPI flash not inside this raw model output','cross-classification coarse mapping disclosed']}
(OUT/'execution.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta,indent=2))
