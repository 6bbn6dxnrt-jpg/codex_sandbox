"""Archive public evidence only; never change the frozen forecast."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import requests
from lxml import html
OUT=Path('bank_benchmark_sources');OUT.mkdir(exist_ok=True)
URLS={
'ali_aug13':'https://www.aliorbank.pl/dam/jcr:2400942f-ff71-4147-9442-f3d8c5e0993f/20260813-makrowizjer.pdf',
'bgk_q2':'https://www.bgk.pl/files/public/user_upload/Kwartalny_raport_makroekonomiczny_BGK_-_2Q2026.pdf',
'bnp_may_pdf':'https://cdn-netpr.pl/file/attachment/3010646/c3/polska_w_geopolitycznym_chaosie_aktualizacja_prognoz_makroekonomicznych_maj_2026.pdf',
'bank_comments_aug31':'https://300gospodarka.pl/news/inflacja-sierpien-2026-finalne-dane-i-pkb',
'velo_jul17':'https://www.velobank.pl/makroekonomia/makropodsumowanie-tygodnia-17-lipca-2026-r.html',
'velo_sep07':'https://www.velobank.pl/makroekonomia/velotydzien-ekonomiczny-7-wrzesnia-2026-r.html',
'bps_archive':'https://bank.pl/bps-prognozuje-ze-do-konca-2025-r-rpp-zdecyduje-sie-jeszcze-na-dwie-obnizki-stop-procentowych-po-25-pb/',
'mbank_secondary':'https://www.analizy.pl/tylko-u-nas/40533/prognozy-pkb-i-inflacji-sierpien-2026',
'kbc_aug_table':'https://www.kbc.com/en/economics/publications/economic-perspectives-april-2026.html'
}
def one(item):
 name,url=item
 try:
  r=requests.get(url,timeout=40);r.raise_for_status();data=r.content
  ext='.pdf' if data.startswith(b'%PDF') else '.html';(OUT/(name+ext)).write_bytes(data)
  if ext=='.html':
   doc=html.fromstring(data)
   for e in doc.xpath('//script|//style'):e.drop_tree()
   (OUT/(name+'.txt')).write_text(doc.text_content())
  return {'name':name,'url':r.url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'status':'ok'}
 except Exception as e:return {'name':name,'url':url,'status':'error','error':repr(e)}
with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(one,URLS.items()))
(OUT/'manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps(results,indent=2))
