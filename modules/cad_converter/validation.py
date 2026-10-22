"""Structural format checks, not a geometric equivalence certificate."""

import math
from pathlib import Path
import re
import struct

from .models import checkpoint


def validate_output(path, format_key, *, stop=None):
    path = Path(path)
    if not path.is_file() or path.stat().st_size < 16:
        raise ValueError('SolidWorks geçerli boyutta bir çıktı oluşturmadı.')
    checkpoint(stop)
    if format_key.startswith('step'):
        _step(path, int(format_key[4:]), stop)
    elif format_key == 'iges':
        _iges(path, stop)
    elif format_key.startswith('stl_'):
        _stl(path, format_key == 'stl_binary', stop)
    elif format_key in ('xt', 'xb'):
        _parasolid(path, format_key == 'xb')
    else:
        raise ValueError('Çıktı formatı tanınmıyor.')
    return path.stat().st_size


def _step(path, protocol, stop):
    header = ''
    end = ''
    entities = False
    sections = 0
    with path.open(encoding='latin-1') as stream:
        for line in stream:
            checkpoint(stop)
            upper = line.upper()
            if 'DATA;' not in header:
                header += upper
                if len(header) > 1024 * 1024:
                    raise ValueError('STEP başlığı veya DATA bölümü geçersiz.')
            entities |= bool(re.search(r'#\d+\s*=', upper))
            sections += upper.count('ENDSEC;')
            end = (end + upper)[-256:]
    schemas = {203: ('CONFIG_CONTROL_DESIGN',), 214: ('AUTOMOTIVE_DESIGN',),
               242: ('AP242',)}
    if not header.lstrip().startswith('ISO-10303-21;') or 'HEADER;' not in header or 'FILE_SCHEMA' not in header or 'DATA;' not in header:
        raise ValueError('STEP dosyasında ISO-10303 başlığı veya veri bölümü eksik.')
    schema = re.search(r'FILE_SCHEMA\s*\((.*?)\)\s*;', header, re.S)
    if schema is None or not any(name in schema[1] for name in schemas[protocol]):
        raise ValueError(f'STEP dosyası istenen AP{protocol} protokolünü taşımıyor.')
    if not entities or sections < 2 or not end.rstrip().endswith('END-ISO-10303-21;'):
        raise ValueError('STEP dosyası boş, kesilmiş veya tamamlanmamış.')


def _iges(path, stop):
    counts = dict.fromkeys('SGDPT', 0)
    stage = -1
    terminal = ''
    with path.open(encoding='ascii', errors='strict') as stream:
        for line in stream:
            checkpoint(stop)
            line = line.rstrip('\r\n')
            if len(line) != 80 or line[72] not in counts or not line[73:80].strip().isdigit():
                raise ValueError('IGES 80 sütunlu kayıt yapısı geçersiz.')
            kind = line[72]
            order = 'SGDPT'.index(kind)
            counts[kind] += 1
            if order < stage or int(line[73:80]) != counts[kind]:
                raise ValueError('IGES bölüm sırası veya kayıt numarası geçersiz.')
            stage = order
            if kind == 'T': terminal = line[:72]
    if not all(counts[k] for k in 'SGDP') or counts['T'] != 1 or counts['D'] % 2:
        raise ValueError('IGES geometri veya sonlandırma bölümü eksik.')
    for index, kind in enumerate('SGDP'):
        token = terminal[index * 8:(index + 1) * 8]
        if token[:1] != kind or not token[1:].strip().isdigit() or int(token[1:]) != counts[kind]:
            raise ValueError('IGES sonlandırma sayacı içerikle uyuşmuyor.')


def _numbers(tokens):
    if len(tokens) != 3 or not all(math.isfinite(float(x)) for x in tokens):
        raise ValueError('STL içinde geçersiz koordinat var.')


def _triangle(vertices):
    a, b, c = vertices
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
    if not any(value != 0 for value in cross):
        raise ValueError('STL içinde sıfır alanlı üçgen var.')


def _stl(path, binary, stop):
    if binary:
        with path.open('rb') as stream:
            header = stream.read(84)
            if len(header) != 84:
                raise ValueError('Binary STL başlığı eksik.')
            count = struct.unpack('<I', header[80:])[0]
            if not count or path.stat().st_size != 84 + 50 * count:
                raise ValueError('Binary STL üçgen sayısı ile dosya boyutu uyuşmuyor.')
            for index in range(count):
                if index % 2048 == 0: checkpoint(stop)
                values = struct.unpack('<12fH', stream.read(50))
                if not all(math.isfinite(v) for v in values[:12]):
                    raise ValueError('Binary STL içinde sonlu olmayan mesh koordinatı var.')
                _triangle((values[3:6], values[6:9], values[9:12]))
        return
    state = 'solid'; triangles = 0; vertices = []
    # Solid names may use the Windows code page or UTF-8 for Turkish names;
    # mesh grammar and every numeric coordinate are still checked strictly.
    with path.open(encoding='utf-8-sig', errors='replace') as stream:
        for line in stream:
            checkpoint(stop)
            tokens = line.strip().split()
            if not tokens: continue
            if state == 'solid' and tokens[0].lower() == 'solid': state = 'facet'; continue
            if state == 'facet' and tokens[0].lower() == 'endsolid': state = 'done'; continue
            if state == 'facet' and [x.lower() for x in tokens[:2]] == ['facet', 'normal']:
                _numbers(tokens[2:]); state = 'loop'; continue
            if state == 'loop' and [x.lower() for x in tokens] == ['outer', 'loop']: state = 0; vertices = []; continue
            if isinstance(state, int) and tokens[0].lower() == 'vertex':
                _numbers(tokens[1:]); vertices.append(tuple(float(v) for v in tokens[1:])); state = state + 1 if state < 2 else 'endloop'; continue
            if state == 'endloop' and tokens == ['endloop']: state = 'endfacet'; continue
            if state == 'endfacet' and tokens == ['endfacet']: _triangle(vertices); triangles += 1; state = 'facet'; continue
            raise ValueError('ASCII STL facet/vertex yapısı geçersiz veya dosya türü yanlış.')
    if state != 'done' or not triangles:
        raise ValueError('ASCII STL boş veya tamamlanmamış.')


def _parasolid(path, binary):
    with path.open('rb') as stream:
        prefix = stream.read(65536)
    header, separator, payload = prefix.partition(b'END_OF_HEADER')
    if not separator or b'**PART1;' not in header or not re.search(rb'SCH\s*=\s*SCH_\d+', header):
        raise ValueError('Parasolid transmit başlığı veya şema işareti bulunamadı.')
    payload = payload.split(b'\n', 1)[-1]
    if len(payload.strip()) < 32:
        raise ValueError('Parasolid gövde verisi eksik.')
    if binary:
        if b'\x00' not in payload:
            raise ValueError('Parasolid Binary yerine metin veya bozuk veri oluştu.')
    elif b'\x00' in payload or not re.search(rb'\d+\s+\d+\s+\d+', payload):
        raise ValueError('Parasolid Text sayısal gövde verisi geçersiz.')
