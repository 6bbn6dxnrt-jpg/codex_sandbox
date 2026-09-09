from __future__ import annotations
import hashlib,json,io,time
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
from lxml import html
ROOT=Path('v4_run');RAW=ROOT/'raw';RAW.mkdir(parents=True,exist_ok=True)
BASE='https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/'
JOBS={
 'hicp_new_indices':(BASE+'prc_hicp_minr',{'geo':'PL','unit':'I25','sinceTimePeriod':'1996-01'}),
 'hicp_new_weights':(BASE+'prc_hicp_iw',{'geo':'PL'}),
 'hicp_old_indices':(BASE+'prc_hicp_midx',{'geo':'PL','unit':'I15'}),
 'hicp_old_weights':(BASE+'prc_hicp_inw',{'geo':'PL'}),
 'gdp_nsa':(BASE+'namq_10_gdp',{'geo':'PL','na_item':'B1GQ','s_adj':'NSA','unit':'CLV20_MNAC'}),
 'gdp_sca':(BASE+'namq_10_gdp',{'geo':'PL','na_item':'B1GQ','s_adj':'SCA','unit':'CLV20_MNAC'}),
 'gdp_yoy':(BASE+'namq_10_gdp',{'geo':'PL','na_item':'B1GQ','s_adj':'NSA','unit':'CLV_PCH_SM'}),
 'industry_pl':(BASE+'sts_inpr_m',{'geo':'PL','nace_r2':'B-D','indic_bt':'PROD','s_adj':'SCA','unit':'I21'}),
 'industry_de':(BASE+'sts_inpr_m',{'geo':'DE','nace_r2':'B-D','indic_bt':'PROD','s_adj':'SCA','unit':'I21'}),
 'construction_pl':(BASE+'sts_copr_m',{'geo':'PL','nace_r2':'F','indic_bt':'PROD','s_adj':'SCA','unit':'I21'}),
 'retail_pl':(BASE+'sts_trtu_m',{'geo':'PL','nace_r2':'G47','indic_bt':'VOL_SLS','s_adj':'SCA','unit':'I21'}),
 'unemployment_pl':(BASE+'une_rt_m',{'geo':'PL','sex':'T','age':'Y15-74','unit':'PC_ACT','s_adj':'SA'}),
 'gus_cpi':('https://stat.gov.pl/obszary-tematyczne/ceny-handel/wskazniki-cen/wskazniki-cen-towarow-i-uslug-konsumpcyjnych-pot-inflacja-/miesieczne-wskazniki-cen-towarow-i-uslug-konsumpcyjnych-od-1982-roku/',None),
 'gus_prices_dashboard':('https://ssgk.stat.gov.pl/Ceny_towarow_i_uslug_konsumpcyjnych.html',None),
 'gus_industry_dashboard':('https://ssgk.stat.gov.pl/Produkcja_sprzedana_przemyslu.html',None),
 'gus_cpi_release':('https://stat.gov.pl/obszary-tematyczne/ceny-handel/wskazniki-cen/wskazniki-cen-towarow-i-uslug-konsumpcyjnych-w-lipcu-2026-r-,2,177.html',None),
 'hicp_method':('https://ec.europa.eu/eurostat/web/hicp/information-data',None),
 'timesfm_api':('https://huggingface.co/api/models/google/timesfm-3.0-pytorch',None),
 'timesfm_card':('https://huggingface.co/google/timesfm-3.0-pytorch/raw/main/README.md',None),
 'gus_dbw_api':('https://api.dbw.stat.gov.pl/api/1.1.0/variable/variable-section',None)
}
def one(name,url,params):
 try:
  r=requests.get(url,params=params,timeout=50);r.raise_for_status();ext='.json' if 'json' in r.headers.get('content-type','') else '.html'
  (RAW/(name+ext)).write_bytes(r.content)
  item={'name':name,'url':r.url,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(r.content).hexdigest(),'bytes':len(r.content),'file':name+ext,'status':'ok'}
  if ext=='.json':
   try:
    j=r.json();item['dimensions']=j.get('id');item['size']=j.get('size');item['updated']=j.get('updated')
    if 'dimension' in j:
     item['dimension_labels']={dim:j['dimension'][dim].get('category',{}) for dim in j['id'] if dim!='time'}
     item['times']=list(j['dimension']['time']['category']['index'])[-5:]
   except Exception:pass
  else:
   try:
    t=html.fromstring(r.content);links=[{'text':' '.join(e.text_content().split()),'url':requests.compat.urljoin(r.url,e.get('href'))} for e in t.xpath('//a[@href]')]
    (RAW/(name+'_links.json')).write_text(json.dumps(links,ensure_ascii=False))
   except Exception:pass
  return item
 except Exception as e:return {'name':name,'url':url,'status':'failed','error':repr(e)}
manifest=[]
with ThreadPoolExecutor(max_workers=5) as pool:
 futures={pool.submit(one,k,*v):k for k,v in JOBS.items()}
 for f in as_completed(futures):
  item=f.result();manifest.append(item);print(item['name'],item['status'],item.get('times'),flush=True)
  (ROOT/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
(ROOT/'PROTOCOL.json').write_bytes(Path('v4/PROTOCOL.json').read_bytes())
