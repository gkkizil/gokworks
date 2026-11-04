"""Strict v1 JSON contracts. No computed result is trusted as project input."""

from dataclasses import asdict, fields
import json

from .calculation import calculate
from .catalog.models import CatalogSource, LengthCatalog
from .models import (BeltDriveSpecification, BeltSpecification, CenterSpecification,
                     LoadSpecification, PulleySpecification, BeltDriveResult)

SCHEMA = 'gokworks.belt_drive'
CATALOG_SCHEMA = 'gokworks.belt_drive.length_catalog'
VERSION = 1
MAX_JSON_SIZE = 2 * 1024 * 1024


def _construct(cls, value):
    names = {item.name for item in fields(cls) if item.init}
    if not isinstance(value, dict) or set(value) != names:
        raise ValueError(f'{cls.__name__}: eksik veya bilinmeyen alan var.')
    return cls(**value)


def _payload(value, schema, names):
    if not isinstance(value, dict) or set(value) != {'schema', 'version', 'units'} | set(names):
        raise ValueError('JSON alanları eksik veya bilinmeyen alan içeriyor.')
    if value['schema'] != schema or type(value['version']) is not int or value['version'] != VERSION or value['units'] != 'mm':
        raise ValueError('Desteklenmeyen şema, sürüm veya birim; v1 ve mm gerekli.')
    return {key: value[key] for key in names}


def to_dict(specification):
    calculate(specification)
    return dict(schema=SCHEMA, version=VERSION, units='mm', **asdict(specification))


def from_dict(value):
    names = {item.name for item in fields(BeltDriveSpecification)}
    data = _payload(value, SCHEMA, names)
    for name, cls in (('belt', BeltSpecification), ('driver', PulleySpecification), ('driven', PulleySpecification),
                      ('load', LoadSpecification), ('center', CenterSpecification)):
        data[name] = _construct(cls, data[name])
    result = _construct(BeltDriveSpecification, data)
    calculate(result)
    return result


def catalog_to_dict(catalog):
    if not isinstance(catalog, LengthCatalog):
        raise ValueError('LengthCatalog gerekli.')
    return dict(schema=CATALOG_SCHEMA, version=VERSION, units='mm', **asdict(catalog))


def catalog_from_dict(value):
    data = _payload(value, CATALOG_SCHEMA, {item.name for item in fields(LengthCatalog)})
    data['source'] = _construct(CatalogSource, data['source'])
    return _construct(LengthCatalog, data)


def result_to_dict(result):
    if not isinstance(result, BeltDriveResult):
        raise ValueError('BeltDriveResult gerekli.')
    data = asdict(result)
    data['geometry']['length_mm'] = result.geometry.length_mm
    for output, segment in zip(data['geometry']['segments'], result.geometry.segments):
        output['length_mm'] = segment.length_mm
    return dict(schema=SCHEMA + '.result', version=VERSION, units='mm', **data)


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Tekrarlanan JSON alanı: ' + key)
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError('JSON sonlu sayılar içermeli: ' + value)


def read_json(text):
    if not isinstance(text, (str, bytes, bytearray)) or len(text) > MAX_JSON_SIZE:
        raise ValueError('JSON metni en çok 2 MiB/karakter olmalı.')
    try:
        return json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_bad_constant)
    except RecursionError as error:
        raise ValueError('JSON iç içe veri sınırını aşıyor.') from error


def dumps(specification):
    return json.dumps(to_dict(specification), ensure_ascii=False, allow_nan=False, indent=2)


def loads(text):
    return from_dict(read_json(text))
