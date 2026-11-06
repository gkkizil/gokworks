"""Strict versioned JSON projects; atomic, no-clobber publication on NTFS/POSIX."""
from dataclasses import fields
import json
import os
from pathlib import Path
from tempfile import mkstemp
from .models import UnfoldRequest,UnfoldProject,ProjectItem,to_data
from .validation import validate,integer

SCHEMA='gokworks.unfolding.project'


def atomic_write(path,writer,overwrite=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and not overwrite:raise FileExistsError('Çıktı zaten var; üzerine yazma açık değil.')
    fd,name=mkstemp(prefix='.gokworks-unfold-',suffix=path.suffix,dir=path.parent);os.close(fd)
    temporary=Path(name)
    try:
        writer(temporary)
        with temporary.open('r+b') as f:os.fsync(f.fileno())
        if overwrite:os.replace(temporary,path)
        else:os.link(temporary,path)
    finally:temporary.unlink(missing_ok=True)
    return path


def request_from_dict(data):
    if not isinstance(data,dict) or set(data)-{f.name for f in fields(UnfoldRequest)} or not {'shape_id','variant_id','parameters'}<=data.keys():
        raise ValueError('İstek nesnesi eksik veya tanımsız alan içeriyor.')
    try:r=UnfoldRequest(**data)
    except (TypeError,ValueError) as exc:raise ValueError('İstek alan türleri geçersiz.') from exc
    report=validate(r)
    if not report.valid:raise ValueError('; '.join(x.message for x in report.errors))
    return r


def _pairs(pairs):
    data={}
    for k,v in pairs:
        if k in data:raise ValueError('JSON tekrarlanan alan içeriyor: '+k)
        data[k]=v
    return data


def read_json(path):
    path=Path(path)
    with path.open('rb') as f:content=f.read(4*1024*1024+1)
    if len(content)>4*1024*1024:raise ValueError('JSON 4 MiB sınırını aşıyor.')
    def invalid(value):raise ValueError('Sonlu olmayan JSON sayısı.')
    try:return json.loads(content,object_pairs_hook=_pairs,parse_constant=invalid)
    except (UnicodeError,RecursionError,json.JSONDecodeError) as exc:raise ValueError('JSON biçimi geçersiz.') from exc


def check_project(project):
    if not isinstance(project,UnfoldProject):raise ValueError('UnfoldProject gerekli.')
    integer(project.quantity,'Proje adedi',1,1000000)
    if not isinstance(project.items,tuple) or not 1<=len(project.items)<=256:raise ValueError('1–256 değişmez proje öğesi gerekli.')
    for name in ('name','code','revision','engine_version'):
        value=getattr(project,name)
        if not isinstance(value,str) or len(value)>256:raise ValueError('Proje metin alanı geçersiz: '+name)
    ids=set()
    for item in project.items:
        if not isinstance(item,ProjectItem) or not isinstance(item.code,str) or len(item.code)>256:raise ValueError('Proje öğesi geçersiz.')
        integer(item.quantity,'Öğe adedi',1,1000000)
        report=validate(item.request)
        if not report.valid:raise ValueError('; '.join(x.message for x in report.errors))
        if item.request.request_id in ids:raise ValueError('Proje içinde istek kimlikleri benzersiz olmalı.')
        ids.add(item.request.request_id)


def project_to_dict(project):
    check_project(project)
    return dict(schema=SCHEMA,version=1,project=to_data(project))


def save_project(project,path,*,overwrite=False):
    data=project_to_dict(project)
    content=json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2)
    if len(content.encode('utf-8'))>4*1024*1024:raise ValueError('Proje JSON 4 MiB okuma sınırını aşıyor; tablo/öğe sayısını azaltın.')
    return atomic_write(path,lambda p:p.write_text(content,encoding='utf-8'),overwrite)


def load_project(path):
    data=read_json(path)
    if not isinstance(data,dict) or set(data)!={'schema','version','project'} or data['schema']!=SCHEMA or type(data['version']) is not int or data['version']!=1:
        raise ValueError('Sac açınımı proje şeması/sürümü desteklenmiyor.')
    raw=data['project']
    if not isinstance(raw,dict) or set(raw)!={f.name for f in fields(UnfoldProject)}:raise ValueError('Proje alanları eksik veya tanımsız.')
    if not isinstance(raw['items'],list) or not 1<=len(raw['items'])<=256:raise ValueError('Proje öğe sayısı sınırı aşıldı.')
    try:
        items=[]
        for x in raw['items']:
            if not isinstance(x,dict) or set(x)!={'code','quantity','request'}:raise ValueError('Öğe alanları geçersiz.')
            items.append(ProjectItem(x['code'],request_from_dict(x['request']),x['quantity']))
        project=UnfoldProject(**dict(raw,items=tuple(items)))
        check_project(project)
        return project
    except (TypeError,KeyError) as exc:raise ValueError('Proje alan türleri geçersiz.') from exc
