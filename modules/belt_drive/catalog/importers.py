"""Bounded, strict normalized JSON/CSV imports; no scraping or trust promotion."""

import csv
from dataclasses import asdict, fields, MISSING
import hashlib
import io
import json
from pathlib import Path

from ..serialization import read_json, MAX_JSON_SIZE
from .products import ProductSource, BeltProduct, PulleyProduct, ProductCatalog
from .rating_models import RatingTable, CorrectionTable

SCHEMA = 'gokworks.belt_drive.products'


def construct(cls, data):
    allowed = {item.name for item in fields(cls) if item.init}
    required = {item.name for item in fields(cls) if item.init and item.default is MISSING and item.default_factory is MISSING}
    if not isinstance(data, dict) or not required <= data.keys() or not data.keys() <= allowed:
        raise ValueError(cls.__name__ + ': eksik veya bilinmeyen alan.')
    try:
        return cls(**data)
    except (TypeError, OverflowError) as error:
        raise ValueError(cls.__name__ + ': geçersiz alan türü/sayı aralığı.') from error


def catalog_from_dict(value):
    if not isinstance(value, dict) or set(value) != {'schema', 'version', 'units', 'identifier', 'revision', 'sources', 'belts', 'pulleys', 'ratings'}:
        raise ValueError('Ürün katalog şeması alanları uyuşmuyor.')
    if value['schema'] != SCHEMA or type(value['version']) is not int or value['version'] != 1 or value['units'] != 'mm':
        raise ValueError('Ürün katalog sözleşmesi v1 ve mm gerekli.')
    data = {key: value[key] for key in ('identifier', 'revision')}
    for name, cls in (('sources', ProductSource), ('belts', BeltProduct), ('pulleys', PulleyProduct), ('ratings', RatingTable)):
        rows = value[name]
        if type(rows) not in (list, tuple) or len(rows) > 10000:
            raise ValueError(name + ': en çok 10000 kayıt.')
        items = []
        for row in rows:
            if name == 'ratings' and isinstance(row, dict):
                row = dict(row)
                corrections = row.get('corrections', [])
                if type(corrections) not in (list, tuple) or len(corrections) > 4:
                    raise ValueError('Düzeltme listesi geçersiz.')
                row['corrections'] = tuple(construct(CorrectionTable, item) for item in corrections)
            items.append(construct(cls, row))
        data[name] = tuple(items)
    return ProductCatalog(**data)


def catalog_to_dict(catalog):
    if not isinstance(catalog, ProductCatalog):
        raise ValueError('ProductCatalog gerekli.')
    return dict(schema=SCHEMA, version=1, units='mm', **asdict(catalog))


def catalog_dumps(catalog):
    return json.dumps(catalog_to_dict(catalog), ensure_ascii=False, allow_nan=False, indent=2)


def catalog_loads(content):
    return catalog_from_dict(read_json(content))


def fingerprint(catalog):
    canonical = json.dumps(catalog_to_dict(catalog), sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def load_catalog(path):
    with Path(path).open('rb') as stream:
        content = stream.read(MAX_JSON_SIZE + 1)
    if len(content) > MAX_JSON_SIZE:
        raise ValueError('Katalog en çok 2 MiB olabilir.')
    if Path(path).suffix.lower() == '.csv':
        return catalog_from_csv(content.decode('utf-8-sig'), identifier=Path(path).stem, revision='user-csv')
    return catalog_loads(content)


_NUMERIC = {'datum_length_mm', 'tooth_count', 'pitch_mm', 'pitch_length_mm', 'inside_length_mm',
            'outside_length_mm', 'width_mm', 'datum_diameter_mm', 'teeth', 'face_width_mm',
            'overall_width_mm', 'outside_diameter_mm', 'grooves', 'nominal_belt_width_mm',
            'catalog_pitch_diameter_mm', 'tooth_outside_diameter_mm', 'flange_diameter_mm',
            'pilot_bore_mm', 'catalog_face_dimension_f_mm', 'axial_min_mm', 'axial_max_mm'}
_INTEGER = {'tooth_count', 'teeth', 'grooves'}
_SOURCE_FIELDS = tuple(item.name for item in fields(ProductSource) if item.name != 'identifier')
_PRODUCT_FIELDS = ({item.name for item in fields(BeltProduct)} | {item.name for item in fields(PulleyProduct)})
CSV_FIELDS = ('kind', 'units', 'code', 'series_id', 'source_id', 'profile', 'compatibility_id',
              *_SOURCE_FIELDS, *sorted(_PRODUCT_FIELDS - {'code', 'series_id', 'source_id', 'profile', 'compatibility_id'}))


def catalog_from_csv(content, *, identifier, revision):
    if not isinstance(content, str) or len(content) > MAX_JSON_SIZE:
        raise ValueError('CSV en çok 2 MiB/karakter olabilir.')
    reader = csv.DictReader(io.StringIO(content, newline=''))
    headers = reader.fieldnames or []
    required = {'kind', 'units', 'code', 'series_id', 'source_id', 'profile', 'compatibility_id', 'manufacturer'}
    if len(headers) != len(set(headers)) or not required <= set(headers) or not set(headers) <= set(CSV_FIELDS):
        raise ValueError('CSV başlığı eksik, tekrarlı veya bilinmeyen alan içeriyor.')
    sources, belts, pulleys = {}, [], []
    try:
        for index, row in enumerate(reader, 1):
            if index > 10000 or None in row or any(value is None for value in row.values()):
                raise ValueError('CSV satır uzunluğu/kayıt sınırı uyuşmuyor.')
            if row['units'] != 'mm' or row['kind'] not in ('belt', 'pulley'):
                raise ValueError('CSV yalnız mm biriminde belt/pulley satırları içerir; güç tabloları JSON ile yüklenir.')
            source_data = {key: row[key] for key in _SOURCE_FIELDS if row.get(key)}
            source_data['identifier'] = row['source_id']
            source = construct(ProductSource, source_data | {key: source_data.get(key, '') for key in ('document', 'revision', 'page', 'url')})
            if source.identifier in sources and sources[source.identifier] != source:
                raise ValueError('CSV kaynak metadatası çelişiyor.')
            sources[source.identifier] = source
            cls = BeltProduct if row['kind'] == 'belt' else PulleyProduct
            names = {item.name for item in fields(cls)}
            data = {}
            for key in _PRODUCT_FIELDS:
                value = row.get(key, '')
                if value:
                    if key not in names:
                        raise ValueError('CSV ürün türüne ait olmayan alan: ' + key)
                    data[key] = int(value) if key in _INTEGER else float(value) if key in _NUMERIC else value
            (belts if cls is BeltProduct else pulleys).append(construct(cls, data))
    except csv.Error as error:
        raise ValueError('CSV okunamadı: ' + str(error)) from error
    return ProductCatalog(identifier, revision, tuple(sources.values()), tuple(belts), tuple(pulleys))


def catalog_to_csv(catalog):
    """Dimension-only export. Reject dropping rating tables silently."""
    if catalog.ratings:
        raise ValueError('Güç tablolarını korumak için JSON kullanın; CSV yalnız ürün boyutlarını taşır.')
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for kind, items in (('belt', catalog.belts), ('pulley', catalog.pulleys)):
        for product in items:
            source = asdict(catalog.source(product.source_id)); source.pop('identifier')
            writer.writerow(dict(kind=kind, units='mm', **asdict(product), **source))
    return buffer.getvalue()
