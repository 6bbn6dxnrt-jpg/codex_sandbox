from pathlib import Path
import requests,json,hashlib
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
ROOT=Path('v4_run');RAW=ROOT/'raw';RAW.mkdir(parents=True,exist_ok=True)
B='https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/'
J={
 'gus_components_2010_2025':('https://bazydanych.new.stat.gov.pl/file/201217/download?token=OHHpTA0J',None),
 'gus_components_2026':('https://bazydanych.new.stat.gov.pl/file/199315/download',None),
 'gus_ssgk_july2026':('https://ssgk.stat.gov.pl/Tablice/SSGK_07.2026.xlsx',None),
 'gus_cpi_july2026_table':('https://stat.gov.pl/download/gfx/portalinformacyjny/pl/defaultaktualnosci/5464/2/177/1/wskazniki_cen_towarow_i_uslug_konsumpcyjnych_w_lipcu_2026_tab.xlsx',None),
 'gus_cpi_long_csv':('https://stat.gov.pl/download/gfx/portalinformacyjny/pl/defaultstronaopisowa/4741/1/1/miesieczne_wskazniki_cen_towarow_i_uslug_konsumpcyjnych_od_1982_roku__2_2.csv',None),
 'industry_pl_fixed':(B+'sts_inpr_m',{'geo':'PL','nace_r2':'B-D','s_adj':'SCA','unit':'I21'}),
 'industry_de_fixed':(B+'sts_inpr_m',{'geo':'DE','nace_r2':'B-D','s_adj':'SCA','unit':'I21'}),
 'construction_pl_fixed':(B+'sts_copr_m',{'geo':'PL','nace_r2':'F','s_adj':'SCA','unit':'I21'}),
 'unemployment_pl_fixed':(B+'une_rt_m',{'geo':'PL','sex':'T','unit':'PC_ACT','s_adj':'SA'})
}
def get(item):
 name,(url,params)=item
 try:
  r=requests.get(url,params=params,timeout=60);r.raise_for_status();ct=r.headers.get('content-type','');ext='.xlsx' if r.content[:2]==b'PK' else '.json' if 'json' in ct else '.csv' if 'csv' in name else '.bin'
  (RAW/(name+ext)).write_bytes(r.content)
  return {'name':name,'url':r.url,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(r.content).hexdigest(),'file':name+ext,'bytes':len(r.content),'status':'ok','content_type':ct}
 except Exception as e:return {'name':name,'url':url,'status':'failed','error':repr(e)}
with ThreadPoolExecutor(max_workers=4) as p:m=list(p.map(get,J.items()))
(ROOT/'extra_manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
