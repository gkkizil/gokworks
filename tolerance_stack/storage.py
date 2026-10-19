"""Atomic project files and conservative source revision detection."""

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from tempfile import mkstemp

from .calculator import check_cancel
from .chain import validate_dimension
from .models import Dimension, Project, SourceStamp, Term, number, serializable


def atomic_write(path, writer, *, overwrite=False, stop=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError('Çıktı zaten var; başka bir ad seçin.')
    fd, name = mkstemp(prefix='.gokworks-stack-', suffix=path.suffix, dir=path.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        check_cancel(stop)
        writer(temporary)
        check_cancel(stop)
        with temporary.open('r+b') as stream:
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            # Same-volume hard link publishes a complete file without replacing
            # a concurrently created destination. Supported by Windows NTFS.
            os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def fingerprint(path, *, stop=None, **kwargs):
    path = Path(path)
    before = path.stat()
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024*1024):
            check_cancel(stop)
            sha.update(chunk)
    after = path.stat()
    if (before.st_size,before.st_mtime_ns) != (after.st_size,after.st_mtime_ns):
        raise ValueError('Kaynak okunurken değişti; yeniden tarayın.')
    return SourceStamp(str(path.resolve()),sha.hexdigest(),after.st_size,after.st_mtime_ns,**kwargs)


def check_sources(project, *, stop=None):
    errors=[]
    for source in project.sources:
        check_cancel(stop)
        try:
            current=fingerprint(source.path,stop=stop)
            if current.sha256!=source.sha256:
                errors.append(f'{Path(source.path).name}: kaynak dosya değişti; ölçüleri yeniden tarayın.')
        except OSError:
            errors.append(f'{Path(source.path).name}: kaynak dosya bulunamadı veya okunamıyor.')
    if errors:
        raise ValueError('\n'.join(errors))


def save_project(project, path, *, result=None, overwrite=False, stop=None):
    for dimension in project.dimensions:
        validate_dimension(dimension)
    payload = dict(format='GOKWORKS-TOLERANCE-STACK',version=1,unit='mm',project=serializable(project),
                   archived_result=serializable(result) if result is not None else None)
    def write(temporary):
        temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return atomic_write(path,write,overwrite=overwrite,stop=stop)


def load_project(path):
    path=Path(path)
    if path.stat().st_size>20*1024*1024:
        raise ValueError('Analiz proje dosyası 20 MB sınırını aşıyor.')
    data=json.loads(path.read_text(encoding='utf-8'),parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Sonlu olmayan JSON sayısı.')))
    if not isinstance(data,dict) or data.get('format')!='GOKWORKS-TOLERANCE-STACK' or type(data.get('version')) is not int or data.get('version')!=1 or data.get('unit')!='mm':
        raise ValueError('Analiz biçimi, sürümü veya normalize birimi desteklenmiyor.')
    raw=data['project']
    if not isinstance(raw,dict) or len(raw.get('dimensions',[]))>20000 or len(raw.get('terms',[]))>1000:
        raise ValueError('Proje boyutu veya yapısı geçersiz.')
    raw=dict(raw)
    try:
        raw['dimensions']=[Dimension(**dict(item,position=tuple(item.get('position',())))) for item in raw['dimensions']]
        raw['terms']=[Term(**item) for item in raw['terms']]
        raw['sources']=[SourceStamp(**dict(item,notes=tuple(item.get('notes',())))) for item in raw.get('sources',[])]
        for key in ('acceptance_min','acceptance_max','input_sigma','output_sigma'):
            if raw.get(key) is not None: raw[key]=number(raw[key],key)
        project=Project(**raw)
        for dimension in project.dimensions:
            validate_dimension(dimension)
        from .models import DISTRIBUTIONS
        if project.method not in ('worst_case','rss','all') or project.distribution not in DISTRIBUTIONS:
            raise ValueError('Kayıtlı analiz yöntemi/dağılımı desteklenmiyor.')
        for key in ('name','id','start','end','critical','axis','datum','confirmed_digest'):
            if not isinstance(getattr(project,key),str):raise ValueError('Proje metin alanları geçersiz.')
        for key in ('independent','truncate_normal','offline_snapshot'):
            if not isinstance(getattr(project,key),bool):raise ValueError('Proje mantıksal alanı geçersiz.')
        for term in project.terms:
            if not isinstance(term.alignment_confirmed,bool):
                raise ValueError('Ölçünün doğrultu kontrolü geçersiz; projeyi yeniden açın.')
            if term.distribution not in ('inherit',*DISTRIBUTIONS) or type(term.direction) is not int or term.direction not in (-1,1):
                raise ValueError('Kayıtlı ölçü zinciri dağılımı/yönü geçersiz.')
            if not all(isinstance(getattr(term,key),str) for key in ('dimension_id','start','end','axis','datum','relation')):
                raise ValueError('Ölçü zinciri metin alanları geçersiz.')
        for source in project.sources:
            if not isinstance(source.path,str) or not isinstance(source.sha256,str) or len(source.sha256)!=64:
                raise ValueError('Kaynak dosya kimliği geçersiz.')
    except (TypeError,KeyError,AttributeError) as error:
        raise ValueError('Analiz kaydı eksik veya alan türleri geçersiz.') from error
    project.invalidate()  # Saved calculations are historical, never current on open.
    return project, data.get('archived_result')
