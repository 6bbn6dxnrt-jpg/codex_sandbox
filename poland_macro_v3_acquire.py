"""Acquire public source snapshots; no forecasts and no invented observations."""
from __future__ import annotations
import hashlib, io, json, os, sys, time, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import requests

ROOT=Path('poland_macro_v3_run'); RAW=ROOT/'raw'; CLEAN=ROOT/'clean'
RAW.mkdir(parents=True,exist_ok=True); CLEAN.mkdir(exist_ok=True)
ASOF=pd.Timestamp('2026-09-09'); META=[]; ERRORS=[]

def get(url,params=None):
    err=None
    for attempt in range(3):
        try:
            r=requests.get(url,params=params,timeout=45)
            r.raise_for_status(); return r
        except Exception as e:
            err=e
            if attempt<2:time.sleep(2*(attempt+1))
    raise err

def save(name,response,extension):
    path=RAW/(name+extension); path.write_bytes(response.content)
    return {'name':name,'url':response.url,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'raw_file':str(path),'sha256':hashlib.sha256(response.content).hexdigest(),'http_status':response.status_code}

def fred(sid):
    r=get('https://fred.stlouisfed.org/graph/fredgraph.csv',{'id':sid}); meta=save(sid,r,'.csv')
    d=pd.read_csv(io.StringIO(r.text)).iloc[:,:2];d.columns=['date','value']
    d['date']=pd.to_datetime(d.date);d['value']=pd.to_numeric(d.value,errors='coerce')
    d=d.dropna().sort_values('date');d=d[d.date<=ASOF]
    if len(d)<8:raise ValueError('too few observations '+sid)
    d.to_csv(CLEAN/(sid+'.csv'),index=False)
    meta.update({'n':len(d),'first':str(d.date.min().date()),'last':str(d.date.max().date()),'last_value':float(d.iloc[-1].value),'provider':'FRED; underlying provider in series metadata','series_page':'https://fred.stlouisfed.org/series/'+sid})
    return meta

def eurostat(name,dataset,params):
    r=get('https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/'+dataset,{'lang':'EN',**params});meta=save(name,r,'.json');j=r.json()
    if any(n!=1 for dim,n in zip(j['id'],j['size']) if dim!='time'):raise ValueError('not a single series')
    ti=j['dimension']['time']['category']['index']; vals=j.get('value',{})
    rows=[]
    for label,i in ti.items():
        v=vals.get(str(i)) if isinstance(vals,dict) else vals[i]
        if v is None:continue
        if '-Q' in label: date=pd.Period(label,freq='Q').start_time
        elif len(label)==4:date=pd.Timestamp(label+'-01-01')
        else:date=pd.Timestamp(label+'-01')
        if date<=ASOF:rows.append((date,float(v)))
    d=pd.DataFrame(rows,columns=['date','value']).sort_values('date')
    if len(d)<8:raise ValueError('too few observations '+name)
    d.to_csv(CLEAN/(name+'.csv'),index=False)
    meta.update({'n':len(d),'first':str(d.date.min().date()),'last':str(d.date.max().date()),'last_value':float(d.iloc[-1].value),'provider':'Eurostat','label':j.get('label'),'updated':j.get('updated'),'params':params})
    return meta

def websnapshot(name,url):
    r=get(url);meta=save(name,r,'.pdf' if 'application/pdf' in r.headers.get('content-type','') else '.html')
    meta['content_type']=r.headers.get('content-type');return meta

def nbpfx(code):
    # Freeze latest observed daily rates and all 2025/2026 daily rates for correct annual means.
    rows=[];meta=[]
    for start,end in [('2025-01-01','2025-06-30'),('2025-07-01','2025-12-31'),('2026-01-01','2026-06-30'),('2026-07-01','2026-09-08')]:
        r=get(f'https://api.nbp.pl/api/exchangerates/rates/a/{code}/{start}/{end}/',{'format':'json'});meta.append(save('nbp_'+code+'_'+start,r,'.json'))
        for x in r.json()['rates']:rows.append((x['effectiveDate'],x['mid']))
    d=pd.DataFrame(rows,columns=['date','value']).drop_duplicates('date').sort_values('date');d.to_csv(CLEAN/('NBP_'+code.upper()+'_DAILY.csv'),index=False)
    return {'name':'NBP_'+code.upper()+'_DAILY','n':len(d),'first':str(d.iloc[0].date),'last':str(d.iloc[-1].date),'last_value':float(d.iloc[-1].value),'parts':meta,'provider':'NBP'}

jobs={}
with ThreadPoolExecutor(max_workers=5) as pool:
    for sid in ['POLGDPRQPSMEI','POLCPIALLMINMEI','CP0000PLM086NEST','IR3TIB01PLM156N','IRLTLT01PLM156N','CCUSMA02PLM618N','EXUSEU','MCOILBRENTEU','PNGASEUUSDM','ECBDFR','DEUPROINDMISMEI','POLPROINDMISMEI','SLRTTO01PLM661S','LRHUTTTTPLM156S','GGNLBAPLA188N','CLV10MNACB1GQSCAEA20Q','CLVMNACSCAB1GQPL']:
        jobs[pool.submit(fred,sid)]=sid
    for area in ['PL','EA20']:
        for adj in ['NSA','SCA']:
            name='EU_GDP_'+area+'_'+adj
            jobs[pool.submit(eurostat,name,'namq_10_gdp',{'geo':area,'na_item':'B1GQ','s_adj':adj,'unit':'CLV20_MNAC','freq':'Q'})]=name
    for name,ds,par in [
        ('EU_PL_GDP_NOMINAL','namq_10_gdp',{'geo':'PL','na_item':'B1GQ','s_adj':'NSA','unit':'CP_MNAC','freq':'Q'}),
        ('EU_PL_GDP_ANNUAL','nama_10_gdp',{'geo':'PL','na_item':'B1GQ','unit':'CLV20_MNAC','freq':'A'}),
        ('EU_PL_HICP','prc_hicp_midx',{'geo':'PL','coicop':'CP00','unit':'I15','freq':'M'}),
        ('EU_PL_HICP_YOY','prc_hicp_manr',{'geo':'PL','coicop':'CP00','unit':'RCH_A','freq':'M'})]:jobs[pool.submit(eurostat,name,ds,par)]=name
    for code in ['eur','usd']:jobs[pool.submit(nbpfx,code)]='nbp_'+code
    pages={
        'gus_cpi_monthly':'https://stat.gov.pl/obszary-tematyczne/ceny-handel/wskazniki-cen/miesieczne-wskazniki-cen-towarow-i-uslug-konsumpcyjnych-od-1982-roku,2,4.html',
        'gus_q2_2026':'https://stat.gov.pl/obszary-tematyczne/rachunki-narodowe/kwartalne-rachunki-narodowe/wstepny-szacunek-produktu-krajowego-brutto-w-2-kwartale-2026-r-,3,96.html',
        'nbp_reports':'https://nbp.pl/polityka-pieniezna/dokumenty-rpp/raport-o-inflacji/',
        'nbp_july_pdf':'https://nbp.pl/wp-content/uploads/2026/07/raport_lipiec_2026.pdf',
        'nbp_july_slides':'https://nbp.pl/wp-content/uploads/2026/07/projekcja_lipiec_2026.pdf',
        'nbp_rates':'https://nbp.pl/podstawowe-stopy-procentowe/',
        'ec_benchmark':'https://economy-finance.ec.europa.eu/economic-surveillance-eu-member-states/country-pages-including-country-reports/poland/economic-forecast-poland_en',
        'imf_benchmark':'https://www.imf.org/en/news/articles/2026/02/02/pr-26030-poland-imf-concludes-2025-article-iv-consultation',
        'oecd_benchmark':'https://www.oecd.org/en/publications/oecd-economic-outlook-volume-2026-issue-1_2d1956f0-en/full-report/poland_b5ae251e.html',
        'timesfm_model_card':'https://huggingface.co/google/timesfm-3.0-pytorch/raw/main/README.md',
        'timesfm_revision':'https://huggingface.co/api/models/google/timesfm-3.0-pytorch'
    }
    for name,url in pages.items():jobs[pool.submit(websnapshot,name,url)]=name
    for future in as_completed(jobs):
        name=jobs[future]
        try:
            item=future.result();META.append(item);print('OK',name,item.get('last'),flush=True)
        except Exception as e:ERRORS.append({'name':name,'error':repr(e)});print('ERROR',name,repr(e),flush=True)
        (ROOT/'source_manifest.json').write_text(json.dumps({'as_of':'2026-09-09','sources':META,'errors':ERRORS},indent=2),encoding='utf-8')
print(json.dumps({'sources':len(META),'errors':ERRORS},indent=2))
