"""Public-source evidence acquisition only; no model or forecast modifications."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
import requests
from lxml import html
OUT=Path('bank_benchmark_sources');OUT.mkdir(exist_ok=True)
URLS={
'ing_sep04_pdf':'https://cdn-netpr.pl/file/attachment/3065713/84/dane_i_prognozy.pdf?download=false',
'mbank_t1':'https://prowly-prod.s3.eu-west-1.amazonaws.com/uploads/11961/assets/846128/-7ba01053b0c38bfc455c71b78eaa37e3.png',
'mbank_t2':'https://prowly-prod.s3.eu-west-1.amazonaws.com/uploads/11961/assets/846129/-110510ef62425556fadb02c0b743be07.jpg',
'mbank_t3':'https://prowly-prod.s3.eu-west-1.amazonaws.com/uploads/11961/assets/846130/-dde9fc7de60f01da70def7c0eff61315.jpg',
'mbank_t4':'https://prowly-prod.s3.eu-west-1.amazonaws.com/uploads/11961/assets/846131/-6b39e2b07705cff61c00bab944127e6a.jpg',
'ca_sep07':'https://static.credit-agricole.pl/asset/m/a/k/makromapa-07092026_36674.pdf',
'ca_aug31':'https://static.credit-agricole.pl/asset/m/a/k/makromapa-310862026_36577.pdf',
'erste_jun24':'https://www.erste.pl/regulation_file_server/time20260624153549/download?id=169535&lang=pl_PL',
'bgk_quarterly':'https://www.bgk.pl/przydatne-informacje/sprawozdania-i-raporty/kwartalny-raport-makroekonomiczny/',
'ali_economics':'https://www.aliorbank.pl/dodatkowe-informacje/informacje/serwis-ekonomiczny.html',
'bnp_may26':'https://media.bnpparibas.pl/pr/870567/polska-gospodarka-solidny-wzrost-mimo-geopolitycznego-chaosu',
'bos_overview':'https://www.bosbank.pl/korporacje-i-JST/serwis-ekonomiczny',
'bos_monthly':'https://www.bosbank.pl/korporacje-i-JST/serwis-ekonomiczny/przeglad-miesieczny',
'citi_economics':'https://www.citibank.pl/poland/homepage/polish/komentarze.htm',
'millennium_economics':'https://www.bankmillennium.pl/o-banku/analizy-i-raporty/analizy-makroekonomiczne',
'millennium_home':'https://www.bankmillennium.pl/o-banku',
'bos_aug25_pap':'https://strefainwestorow.pl/wiadomosci/20260825/w-26-wzrost-pkb-polski-38-proc-cpi-nie-przekroczy-trwale-35-proc-rpp-nie-zmieni',
'analizy_jun30':'https://www.analizy.pl/tylko-u-nas/40029/prognozy-pkb-i-inflacji-czerwiec-2026'}
def one(item):
 name,url=item
 try:
  r=requests.get(url,timeout=35);r.raise_for_status();data=r.content;ct=r.headers.get('content-type','')
  ext='.pdf' if data.startswith(b'%PDF') else '.png' if data.startswith(b'\x89PNG') else '.jpg' if 'image/' in ct else '.html'
  (OUT/(name+ext)).write_bytes(data)
  out={'name':name,'url':r.url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'status':'ok','content_type':ct}
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
