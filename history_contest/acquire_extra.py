from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import requests,fitz,json,hashlib,re
from lxml import html
O=Path('extra_history_sources');O.mkdir(exist_ok=True);M=[]
PAGES={'mbank_2023_05_page':'https://makroekonomia.mbank.pl/246034-maj-2023','mbank_2023_08_page':'https://makroekonomia.mbank.pl/257974-sierpien-2023','mbank_2023_11_page':'https://makroekonomia.mbank.pl/269742-listopad-2023','mbank_2024_05_ref':'https://makroekonomia.mbank.pl/318444-rozgrzewka','mbank_reports_archive':'https://makroekonomia.mbank.pl/releases/raporty-cykliczne'}
def save(name,url):
 try:
  r=requests.get(url,timeout=35);r.raise_for_status();b=r.content;pdf=b.startswith(b'%PDF');ext='.pdf' if pdf else '.html';(O/(name+ext)).write_bytes(b)
  out={'name':name,'url':r.url,'sha256':hashlib.sha256(b).hexdigest(),'status':'ok','retrieved_at':datetime.now(timezone.utc).isoformat()}
  if pdf:
   d=fitz.open(stream=b,filetype='pdf');out['pages']=len(d);(O/(name+'.txt')).write_text('\n'.join(f'--- PAGE {i+1} ---\n'+p.get_text(sort=True) for i,p in enumerate(d)))
  else:
   d=html.fromstring(b);links=[{'text':' '.join(a.text_content().split()),'url':urljoin(r.url,a.get('href'))} for a in d.xpath('//a[@href]')];out['links']=links;(O/(name+'.txt')).write_text(d.text_content())
  return out
 except Exception as e:return {'name':name,'url':url,'status':'error','error':repr(e)}
with ThreadPoolExecutor(max_workers=5) as p:M=list(p.map(lambda x:save(*x),PAGES.items()))
for item in list(M):
 if item['name']=='mbank_2024_05_ref':
  for a in item.get('links',[]):
   if a['text'].startswith('Maj 2024') or a['url'].endswith('-maj-2024'):
    M.append(save('mbank_2024_05_page',a['url']));break
jobs=[]
for item in M:
 if item['name'].endswith('_page'):
  seen=set()
  for a in item.get('links',[]):
   if '.pdf' in a['url'].lower() and a['url'] not in seen:
    seen.add(a['url']);jobs.append((item['name']+'_pdf_'+str(len(seen)),a['url']))
with ThreadPoolExecutor(max_workers=5) as p:M.extend(list(p.map(lambda x:save(*x),jobs)))
(O/'manifest.json').write_text(json.dumps(M,ensure_ascii=False,indent=2));print(json.dumps([{k:v for k,v in m.items() if k!='links'} for m in M],indent=2))
