"""Public monthly reports. URL pattern from archived official mBank attachment.
A guessed filename is not evidence: only successful PDFs with internal issue dates
and explicit forecast definitions may enter the contest.
"""
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import requests,fitz,hashlib,json
OUT=Path('mbank_history_sources');OUT.mkdir(exist_ok=True)
def one(ym):
 y,m=ym;name=f'mbank_{y}_{m:02d}';u=f'https://www.mbank.pl/pdf/serwis-ekonomiczny/raporty/mpc_{m:02d}{y}.pdf'
 try:
  r=requests.get(u,timeout=35);r.raise_for_status();b=r.content
  if not b.startswith(b'%PDF'):raise ValueError('not a PDF')
  (OUT/(name+'.pdf')).write_bytes(b);doc=fitz.open(stream=b,filetype='pdf');pages=[p.get_text(sort=True) for p in doc]
  (OUT/(name+'.txt')).write_text('\n'.join(f'--- PAGE {i+1} ---\n'+p for i,p in enumerate(pages)))
  return {'name':name,'requested_url':u,'url':r.url,'sha256':hashlib.sha256(b).hexdigest(),'status':'ok','pages':len(doc),'first_page':pages[0],'retrieved_utc':datetime.now(timezone.utc).isoformat()}
 except Exception as e:return {'name':name,'requested_url':u,'status':'error','error':repr(e)}
with ThreadPoolExecutor(max_workers=6) as p:
 results=list(p.map(one,[(y,m) for y in range(2019,2025) for m in (2,3,5,6,8,9,11,12)]))
(OUT/'manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps(results,ensure_ascii=False,indent=2))
