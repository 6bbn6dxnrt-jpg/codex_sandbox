import hashlib, pathlib, urllib.request

def download(url, out_dir, timeout=30):
    req=urllib.request.Request(url,headers={"User-Agent":"LocalWealthResearch/0.1"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        data=r.read(30_000_000)
        ctype=r.headers.get_content_type()
    sha=hashlib.sha256(data).hexdigest()
    ext={ "application/pdf":".pdf","image/jpeg":".jpg","image/png":".png"}.get(ctype,".bin")
    p=pathlib.Path(out_dir); p.mkdir(parents=True,exist_ok=True)
    path=p/(sha+ext)
    if not path.exists(): path.write_bytes(data)
    return {"url":url,"sha256":sha,"content_type":ctype,"bytes":len(data),"path":str(path)}
