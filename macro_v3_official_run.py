"""Final audited input layer for v3. Reuses the unchanged inference challenge.
The first run remains archived as a diagnostic; final outputs use GUS CPI only.
"""
from pathlib import Path
import json, re, hashlib
import numpy as np
import pandas as pd
import requests
from lxml import html

source=Path('macro_v3_inference.py').read_text()
head,tail=source.split('from huggingface_hub import HfApi, snapshot_download',1)
ns={'__name__':'__main__'}
exec(compile(head,'macro_v3_inference.py:acquisition','exec'),ns)
ROOT=ns['ROOT'];CLEAN=ns['CLEAN'];RAW=ns['RAW']
tree=html.fromstring((RAW/'gus_cpi_full.html').read_text())
section=None;parsed={}
for tr in tree.xpath('//table//tr'):
 vals=[' '.join(x.text_content().split()) for x in tr.xpath('./td|./th')]
 if not vals:continue
 if any('Grudzień' in v for v in vals):section='decprev'
 for label,key in [('Poprzedni miesiąc','mom'),('Analogiczny miesiąc','yoy'),('Analogiczny okres','ytd'),('Rok poprzedni','prevannual')]:
  if any(label in v for v in vals):section=key
 yi=next((i for i,v in enumerate(vals[:2]) if re.match(r'^(19|20)\d{2}',v)),None)
 if yi is None or len(vals)<yi+13:continue
 year=int(vals[yi][:4]);parsed.setdefault(section,{})
 for month,value in enumerate(vals[yi+1:yi+13],1):
  try:parsed[section][pd.Timestamp(year,month,1)]=float(value.replace(',','.'))
  except ValueError:pass
if len(parsed.get('yoy',{}))<400:raise ValueError('GUS CPI parsing failed')
official=pd.Series(parsed['yoy']).sort_index()-100
official.loc[pd.Timestamp('2026-08-01')]=3.4
levels=pd.Series(dtype=float);lastdec=100.
for year in range(2000,2027):
 if year<2015:
  for month in range(1,13):
   dt=pd.Timestamp(year,month,1)
   if dt in parsed['decprev']:levels.loc[dt]=lastdec*parsed['decprev'][dt]/100
  lastdec=levels.loc[pd.Timestamp(year,12,1)]
 else:
  prevmean=float(levels[levels.index.year==year-1].mean())
  for month in range(1,13):
   dt=pd.Timestamp(year,month,1)
   if dt in parsed['prevannual']:levels.loc[dt]=prevmean*parsed['prevannual'][dt]/100
levels.loc[pd.Timestamp('2026-08-01')]=levels.loc[pd.Timestamp('2025-08-01')]*1.034
annual25=(levels.loc['2025'].mean()/levels.loc['2024'].mean()-1)*100
if abs(annual25-3.6)>.06:raise ValueError('GUS 2025 annual CPI reconciliation failed')
levels.to_frame('value').to_csv(CLEAN/'MODEL_CPI_LEVEL.csv',index_label='date')
official.to_frame('value').to_csv(CLEAN/'GUS_CPI_OFFICIAL_YOY.csv',index_label='date')
ns['series']['cpi']=official.loc['2000-01-01':]
ns['series']['cpi'].to_frame('value').to_csv(CLEAN/'TARGET_cpi.csv',index_label='date')
# Values below transcribed and independently inspected from the downloaded GUS
# quarterly NSA workbook, 31 August 2026 release, row C6:L6.
gus_quarterly={2024:[2.5,3.6,3.0,3.7],2025:[3.2,3.3,3.8,4.1],2026:[3.5,3.9]}
gdp=ns['read']('EU_GDP_PL_NSA').copy()
for year,rates in gus_quarterly.items():
 for quarter,rate in enumerate(rates,1):
  dt=pd.Timestamp(year,(quarter-1)*3+1,1)
  gdp.loc[dt]=gdp.loc[dt-pd.DateOffset(years=1)]*(1+rate/100)
gdp.to_frame('value').to_csv(CLEAN/'MODEL_GDP_LEVEL.csv',index_label='date')
ns['series']['gdp']=(gdp.pct_change(4)*100).dropna().loc['2000-01-01':]
ns['series']['gdp'].to_frame('value').to_csv(CLEAN/'TARGET_gdp.csv',index_label='date')
quality={'input_version':'GUS_reconciled_final','cpi_target':'Official GUS monthly y/y table, not a retired FRED series','cpi_level':'GUS December-relative indices before 2015; prior-annual-average indices thereafter; August 2026 flash y/y bridge','cpi_annual_2025_reconstructed':annual25,'cpi_annual_2025_official_rounded':3.6,'cpi_warning':'Changing annual basket weights and rounded published indices need not yield identical monthly y/y rates. Annual aggregation uses prior-year-average index basis; official y/y is the modeled target.','gdp_2024_2026_official_yoy':gus_quarterly,'gdp_warning':'Quarterly level bridge combines Eurostat historical seasonal weights with latest GUS quarterly y/y. Not an official revised level series. Retrospective evaluation remains latest-vintage, not historical-vintage.','observation_cutoff':'2026-09-08 for daily FX; macro source snapshots retrieved 2026-09-09','source_published':'GUS 31 August 2026 GDP and CPI flash'}
(ROOT/'input_quality_final.json').write_text(json.dumps(quality,indent=2))
(ROOT/'gus_cpi_tables.json').write_text(json.dumps({k:{str(d.date()):v for d,v in vals.items()} for k,vals in parsed.items()},indent=2))
# Fiscal stock-flow history: official Eurostat annual deficit, debt and nominal GDP.
fiscal_manifest=[]
for name,dataset,params in [
 ('EU_DEBT','gov_10dd_edpt1',{'geo':'PL','sector':'S13','na_item':'GD','unit':'PC_GDP','freq':'A'}),
 ('EU_BALANCE','gov_10dd_edpt1',{'geo':'PL','sector':'S13','na_item':'B9','unit':'PC_GDP','freq':'A'}),
 ('EU_NOMINAL_ANNUAL','nama_10_gdp',{'geo':'PL','na_item':'B1GQ','unit':'CP_MNAC','freq':'A'})]:
 try:
  r=requests.get('https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/'+dataset,params={'lang':'EN',**params},timeout=35);r.raise_for_status();j=r.json();(RAW/(name+'.json')).write_bytes(r.content)
  if any(size!=1 for dim,size in zip(j['id'],j['size']) if dim!='time'):raise ValueError('non-single series')
  values=j['value'];rows=[]
  for year,index in j['dimension']['time']['category']['index'].items():
   v=values.get(str(index)) if isinstance(values,dict) else values[index]
   if v is not None and int(year)<=2025:rows.append((year+'-01-01',v))
  pd.DataFrame(rows,columns=['date','value']).to_csv(CLEAN/(name+'.csv'),index=False)
  fiscal_manifest.append({'name':name,'url':r.url,'sha256':hashlib.sha256(r.content).hexdigest(),'n':len(rows),'status':'ok'})
 except Exception as e:fiscal_manifest.append({'name':name,'status':'error','error':repr(e)})
(ROOT/'fiscal_source_manifest.json').write_text(json.dumps(fiscal_manifest,indent=2))
# Save the executed source and workflow in the artifact for self-contained reuse.
(ROOT/'executed_code').mkdir(exist_ok=True)
for filename in ['macro_v3_inference.py','macro_v3_official_run.py','poland_macro_v3_acquire.py']:
 (ROOT/'executed_code'/filename).write_text(Path(filename).read_text())
print('FINAL INPUT GATE',quality,flush=True)
exec(compile('from huggingface_hub import HfApi, snapshot_download'+tail,'macro_v3_inference.py:inference','exec'),ns)
