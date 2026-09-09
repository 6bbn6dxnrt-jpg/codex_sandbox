"""Public-source audit only. No inference, account data, or forecast modifications."""
import json,hashlib,re
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
import requests
from lxml import html
OUT=Path('bank_benchmark_sources');OUT.mkdir(exist_ok=True)
URLS={
'mbank_aug11':'https://makroekonomia.mbank.pl/467714-prognozy-dla-stop-procentowych-i-walut-z-komentarzem',
'mbank_home':'https://makroekonomia.mbank.pl/',
'pko_aug13':'https://www.pkobp.pl/relacje-inwestorskie/akcjonariusze/konsensus-i-prognozy',
'pekao_jul23':'https://www.pekao.com.pl/relacje-inwestorskie/akcje/konsensus.html',
'pekao_home':'https://www.pekao.com.pl/analizy-makroekonomiczne',
'ing_sep04':'https://ekonomiczny.ing.pl/publikacja/876305',
'ca_aug31':'https://www.credit-agricole.pl/amp/przedsiebiorstwa/serwis-ekonomiczny/makromapa/2026/niekorzystne-tendencje-demograficzne-spowolnia-wzrost-gospodarczy-w-polsce',
'ca_home':'https://www.credit-agricole.pl/przedsiebiorstwa/serwis-ekonomiczny/makromapa',
'erste_home':'https://www.erste.pl/serwis-ekonomiczny',
'erste_macro':'https://www.erste.pl/serwis-ekonomiczny/makroskop',
'millennium_home':'https://www.bankmillennium.pl/o-banku/analizy-makroekonomiczne',
'millennium_alt':'https://www.bankmillennium.pl/analizy-makroekonomiczne',
'bos_home':'https://www.bosbank.pl/korporacje-i-JST/serwis-ekonomiczny/analizy-makroekonomiczne',
'citi_home':'https://www.citihandlowy.pl/poland/homepage/polish/komentarze.htm',
'bgk_home':'https://www.bgk.pl/analizy-i-badania/',
'ali_home':'https://www.aliorbank.pl/dodatkowe-informacje/analizy-makroekonomiczne.html',
'bnp_home':'https://www.bnpparibas.pl/badania-ekonomiczne',
'analizy_aug31':'https://www.analizy.pl/tylko-u-nas/40533/prognozy-pkb-i-inflacji-sierpien-2026'}
def one(item):
 name,url=item
 try:
  r=requests.get(url,timeout=30);r.raise_for_status();data=r.content
  ext='.pdf' if data.startswith(b'%PDF') else '.html'
  (OUT/(name+ext)).write_bytes(data)
  out={'name':name,'url':r.url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'status':'ok'}
  if ext=='.html':
   doc=html.fromstring(data)
   links=[{'text':' '.join(e.text_content().split()),'url':urljoin(r.url,e.get('href'))} for e in doc.xpath('//a[@href]')]
   images=[{'alt':e.get('alt'),'url':urljoin(r.url,e.get('src',''))} for e in doc.xpath('//img')]
   frames=[urljoin(r.url,e.get('src','')) for e in doc.xpath('//iframe')]
   (OUT/(name+'_links.json')).write_text(json.dumps({'links':links,'images':images,'iframes':frames},ensure_ascii=False,indent=2))
   for e in doc.xpath('//script|//style'):e.drop_tree()
   (OUT/(name+'.txt')).write_text(doc.text_content())
  return out
 except Exception as e:return {'name':name,'url':url,'status':'error','error':repr(e)}
with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(one,URLS.items()))
(OUT/'manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps(results,indent=2))
