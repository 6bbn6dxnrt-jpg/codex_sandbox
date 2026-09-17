"""Read-only public report acquisition. No forecasts are fitted or changed."""
from pathlib import Path
from datetime import datetime,timezone,date
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import requests,re,json,hashlib
from lxml import html
ROOT=Path('history_sources');ROOT.mkdir(exist_ok=True)
manifest=[]

def get(url):
 r=requests.get(url,timeout=45);r.raise_for_status();return r

def save(name,url,extra=None):
 try:
  r=get(url);b=r.content;ext='.pdf' if b.startswith(b'%PDF') else '.html';p=ROOT/(name+ext);p.write_bytes(b)
  d={'name':name,'url':r.url,'requested_url':url,'sha256':hashlib.sha256(b).hexdigest(),'file':p.name,'retrieved_utc':datetime.now(timezone.utc).isoformat(),'status':'ok',**(extra or {})}
  if ext=='.html':
   doc=html.fromstring(b); links=[{'text':' '.join(x.text_content().split()),'url':urljoin(r.url,x.get('href'))} for x in doc.xpath('//a[@href]')]
   (ROOT/(name+'_links.json')).write_text(json.dumps(links,ensure_ascii=False,indent=2))
   (ROOT/(name+'.txt')).write_text(doc.text_content())
  else:
   import fitz
   pdf=fitz.open(stream=b,filetype='pdf'); d['pages']=len(pdf)
   (ROOT/(name+'.txt')).write_text('\n'.join(f'\n--- PAGE {i+1} ---\n'+pg.get_text(sort=True) for i,pg in enumerate(pdf)))
  return d
 except Exception as e:return {'name':name,'requested_url':url,'status':'error','error':repr(e),**(extra or {})}

ar=save('santander_archive','https://www.santander.pl/en/economic-analysis/macroscope/archives');manifest.append(ar)
selected={}
if ar['status']=='ok':
 links=json.loads((ROOT/'santander_archive_links.json').read_text());items=[]
 for a in links:
  m=re.search(r'Publication date:\s*(\d{2})-(\d{2})-(\d{4})',a['text'])
  if m:
   dd,mm,yy=map(int,m.groups())
   if 2019<=yy<=2024:items.append({'publication_date':date(yy,mm,dd).isoformat(),'url':a['url'],'text':a['text']})
 for yy in range(2019,2025):
  for mm in (3,6,9,12):
   origin=date(yy,mm,9);cand=[x for x in items if 0<=(origin-date.fromisoformat(x['publication_date'])).days<=31]
   if cand:
    x=max(cand,key=lambda z:z['publication_date']);key=x['publication_date'];selected.setdefault(key,{**x,'origins':[]})['origins'].append(origin.isoformat())
 (ROOT/'santander_selection.json').write_text(json.dumps({'grid':'quarterly day9, 2019-2024, latest report <=31d prior','selected':list(selected.values()),'archive_reports':items},indent=2))
 jobs=[]
 for d,x in selected.items():
  u=x['url'].replace('www.erste.pl','www.santander.pl');jobs.append(('santander_'+d,u,x))
 with ThreadPoolExecutor(max_workers=5) as ex:
  for item in ex.map(lambda args:save(*args),jobs):manifest.append(item);print(item['name'],item['status'],flush=True)

other={
 'mbank_archive':'https://www.mbank.pl/serwis-ekonomiczny/raporty/monthly-macroeconomic-update.html',
 'mbank_sep2021':'https://makroekonomia.mbank.pl/155753-wrzesien-2021',
 'mbank_reports':'https://makroekonomia.mbank.pl/aktualnosci/raporty-cykliczne',
 'pko_archive':'https://centrumanaliz.pkobp.pl/makroekonomia',
 'citi_archive':'https://www.citibank.pl/poland/homepage/polish/komentarze.htm',
 'gus_cpi_actual':'https://stat.gov.pl/obszary-tematyczne/ceny-handel/wskazniki-cen/wskazniki-cen-towarow-i-uslug-konsumpcyjnych-pot-inflacja-/miesieczne-wskazniki-cen-towarow-i-uslug-konsumpcyjnych-od-1982-roku/'
}
with ThreadPoolExecutor(max_workers=5) as ex:
 for item in ex.map(lambda x:save(*x),other.items()):manifest.append(item);print(item['name'],item['status'],flush=True)
# Follow actual mBank report attachment URLs returned by fetched page, do not guess PDFs.
for base in ['mbank_archive','mbank_sep2021']:
 p=ROOT/(base+'_links.json')
 if p.exists():
  links=json.loads(p.read_text());todo=[]
  for i,a in enumerate(links):
   if ('.pdf' in a['url'].lower() and ('202' in a['url'] or base=='mbank_sep2021')):
    todo.append((base+'_pdf_'+str(i),a['url'],{'link_text':a['text']}))
  with ThreadPoolExecutor(max_workers=4) as ex:
   manifest.extend(list(ex.map(lambda x:save(*x),todo[:36])))
(ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));print(json.dumps(manifest,ensure_ascii=False,indent=2))
