"""Manual, read-only public catalogue audit; not part of network-free pytest.

Only public catalogue metadata and model page HTML are inspected. No source
calculation engine, paid files, authentication or third-party code is imported.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET

BASE='https://unfoldo.com'


class Page(HTMLParser):
    def __init__(self,text):
        super().__init__();self.canonical='';self.h1=[];self.description='';self.heading=False
        self.feed(text)
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='link' and attrs.get('rel')=='canonical':self.canonical=attrs.get('href','')
        if tag=='meta' and attrs.get('name')=='description':self.description=attrs.get('content','')
        if tag=='h1':self.heading=True
    def handle_endtag(self,tag):
        if tag=='h1':self.heading=False
    def handle_data(self,data):
        if self.heading:self.h1.append(data)


def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'GOKWORKS-public-catalogue-audit/1.0'})
    with urllib.request.urlopen(req,timeout=20) as response:
        content=response.read()
        return response.status,response.url,content


def audit(output,browser_evidence=None):
    root=Path(__file__).resolve().parents[2]
    inventory=json.loads((root/'docs/unfolding/unfoldo_inventory.json').read_text(encoding='utf-8'))
    _,_,home=fetch(BASE+'/tr/')
    asset=re.search(rb'(/assets/catalog-[^"\s]+\.js)',home).group(1).decode()
    _,_,catalogue=fetch(BASE+asset)
    raw=re.search(r'var d=JSON\.parse\(`(.*?)`\)',catalogue.decode(),re.S)
    if raw is None:raise ValueError('Public catalogue metadata schema changed; audit parser must be reviewed.')
    models=json.loads(raw.group(1));live={m['id']:m for m in models}
    _,_,sitemap=fetch(BASE+'/sitemap.xml')
    urls={e.text for e in ET.fromstring(sitemap).iter() if e.tag.endswith('}loc')}
    def model_page(m):
        row=dict(source_id=m['source_id'],url=m['source_url'],in_sitemap=m['source_url'] in urls)
        try:
            status,url,html=fetch(m['source_url']);page=Page(html.decode('utf-8'))
            row.update(http_status=status,final_url=url,canonical=page.canonical,h1=''.join(page.h1).strip(),
                       description=page.description,html_sha256=hashlib.sha256(html).hexdigest())
        except Exception as exc:row['error']=str(exc)
        row['page_verified']=(row.get('http_status')==200 and row.get('canonical')==m['source_url']
                              and bool(row.get('h1')) and row['in_sitemap'])
        source=live.get(m['source_id']);differences=[]
        if source is None:differences.append(dict(kind='missing_live_model'))
        else:
            if [f['id'] for f in source['fields']]!=[f['id'] for f in m['fields']]:
                differences.append(dict(kind='field_ids_or_order'))
            for field,own in zip(source['fields'],m['fields']):
                normalized=dict(default=field['default'],kind='angle' if field.get('angle') else 'count' if field.get('count') else 'option' if field.get('options') else 'length',
                                signed=field.get('signed',False),minimum=field.get('min'),
                                options=[o['value'] for o in field.get('options',[])],symbol=field.get('symbol',field['id']))
                for key,value in normalized.items():
                    stored=[o[0] for o in own[key]] if key=='options' else own[key]
                    if stored!=value:differences.append(dict(field=field['id'],property=key,stored=stored,live=value))
            if [c['value'] for c in source['cutTypes']]!=[c['value'] for c in m['cut_options']]:
                differences.append(dict(kind='cut_options'))
            for key in ('lap','stripLap','heel','meanOnly','noNumbers','triangulate','bendFace','kind','refs'):
                if source.get(key)!=m['source_features'].get(key):
                    differences.append(dict(feature=key,stored=m['source_features'].get(key),live=source.get(key)))
        row['metadata_differences']=differences
        return row
    with ThreadPoolExecutor(max_workers=6) as pool:rows=list(pool.map(model_page,inventory['models']))
    browser={}
    if browser_evidence:
        evidence=json.loads(browser_evidence.read_text(encoding='utf-8'))
        links={e['url'] for e in evidence['links']}
        browser=dict(expanded_home_model_links=sum(m['source_url'] in links for m in inventory['models']),
                     source_sha256=hashlib.sha256(browser_evidence.read_bytes()).hexdigest())
    own={m['source_id'] for m in inventory['models']}
    report=dict(schema='gokworks.unfolding.live_source_audit',version=1,
        checked_at=datetime.now(timezone.utc).isoformat(),site=BASE+'/tr/',
        public_catalogue_url=BASE+asset,public_catalogue_sha256=hashlib.sha256(catalogue).hexdigest(),
        sitemap_sha256=hashlib.sha256(sitemap).hexdigest(),source_models=len(models),
        source_fields=sum(len(m['fields']) for m in models),source_cut_options=sum(len(m['cutTypes']) for m in models),
        missing_in_gokworks=sorted(set(live)-own),missing_on_live_site=sorted(own-set(live)),
        browser=browser,pages_verified=sum(r['page_verified'] for r in rows),
        models_with_metadata_differences=sum(bool(r['metadata_differences']) for r in rows),models=rows,
        meaning='Public model/field/option coverage only; not source engine equivalence or manufacturing approval.')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='models'},ensure_ascii=False,indent=2))
    return 0 if report['pages_verified']==len(own) and not report['missing_in_gokworks'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--browser-evidence',type=Path)
    arguments=parser.parse_args()
    raise SystemExit(audit(arguments.output,arguments.browser_evidence))
