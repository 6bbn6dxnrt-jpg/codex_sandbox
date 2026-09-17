"""Read-only realization cross-check; no model changes or new forecasts."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
import requests,json,hashlib,fitz
from lxml import html
O=Path('official_realizations');O.mkdir(exist_ok=True);M=[]
def save(name,url):
 try:
  r=requests.get(url,timeout=45);r.raise_for_status();b=r.content
  ext='.pdf' if b.startswith(b'%PDF') else '.json' if r.headers.get('content-type','').startswith('application/json') else '.html'
  (O/(name+ext)).write_bytes(b);rec={'name':name,'url':r.url,'sha256':hashlib.sha256(b).hexdigest(),'retrieved_at':datetime.now(timezone.utc).isoformat(),'status':'ok','file':name+ext}
  if ext=='.pdf':
   d=fitz.open(stream=b,filetype='pdf');rec['pages']=len(d);(O/(name+'.txt')).write_text('\n'.join(f'--- PAGE {i+1} ---\n'+p.get_text(sort=True) for i,p in enumerate(d)))
  if ext=='.html':
   d=html.fromstring(b);rec['links']=[{'text':' '.join(a.text_content().split()),'url':urljoin(r.url,a.get('href'))} for a in d.xpath('//a[@href]')]
  return rec
 except Exception as e:return {'name':name,'url':url,'status':'error','error':repr(e)}
urls={
 'gus_2021_2025_page':'https://stat.gov.pl/obszary-tematyczne/rachunki-narodowe/kwartalne-rachunki-narodowe/rachunki-kwartalne-produktu-krajowego-brutto-w-latach-2021-2025,6,20.html',
 'gus_2020_2024_page':'https://stat.gov.pl/obszary-tematyczne/rachunki-narodowe/kwartalne-rachunki-narodowe/rachunki-kwartalne-produktu-krajowego-brutto-w-latach-2020-2024,6,19.html',
 'gus_2019_2023_page':'https://stat.gov.pl/obszary-tematyczne/rachunki-narodowe/kwartalne-rachunki-narodowe/rachunki-kwartalne-produktu-krajowego-brutto-w-latach-2019-2023,6,18.html',
 'eurostat_gdp_yoy_nsa':'https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/namq_10_gdp?lang=EN&geo=PL&na_item=B1GQ&s_adj=NSA&unit=CLV_PCH_SM&freq=Q&sinceTimePeriod=2019-Q1&untilTimePeriod=2024-Q4'}
with ThreadPoolExecutor(max_workers=4) as p:M=list(p.map(lambda x:save(*x),urls.items()))
jobs=[]
for item in M:
 for a in item.get('links',[]):
  if '.pdf' in a['url'].lower() and 'rachunki_kwartalne' in a['url'].lower():jobs.append((item['name'].replace('_page','')+'_pdf',a['url']));break
with ThreadPoolExecutor(max_workers=3) as p:M.extend(list(p.map(lambda x:save(*x),jobs)))
(O/'manifest.json').write_text(json.dumps(M,ensure_ascii=False,indent=2));print(json.dumps([{k:v for k,v in x.items() if k!='links'} for x in M],indent=2))
