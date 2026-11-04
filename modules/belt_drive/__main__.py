"""Executable Stage 1 demonstration: Python API/JSON, without a Qt application."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .calculation import calculate
from .engineering.belt_selection import nearest_catalog_candidates
from .models import BeltDriveSpecification
from .serialization import loads, dumps, result_to_dict, catalog_from_dict, read_json, MAX_JSON_SIZE


def _read(path):
    with Path(path).open('rb') as stream:
        data = stream.read(MAX_JSON_SIZE + 1)
    if len(data) > MAX_JSON_SIZE:
        raise ValueError('JSON dosyası en çok 2 MiB olabilir.')
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description='GOKWORKS Belt Drive — Aşama 1 nominal hesap motoru')
    parser.add_argument('project', nargs='?', help='gokworks.belt_drive v1 JSON')
    parser.add_argument('--example', action='store_true', help='5 kW / 1450 rpm / 100–200–400 mm örneğini yaz')
    parser.add_argument('--catalog', help='Beyan edilen boyut listesinden en yakın adayları da göster')
    args = parser.parse_args(argv)
    try:
        if args.example:
            if args.project or args.catalog:
                parser.error('--example proje/katalog ile birlikte kullanılmaz.')
            print(dumps(BeltDriveSpecification()))
            return 0
        if not args.project:
            parser.error('Proje JSON yolu veya --example gerekli.')
        spec = loads(_read(args.project))
        output = result_to_dict(calculate(spec))
        if args.catalog:
            catalog = catalog_from_dict(read_json(_read(args.catalog)))
            output['catalog_candidates'] = [asdict(item) for item in nearest_catalog_candidates(spec, catalog)]
        print(json.dumps(output, ensure_ascii=False, allow_nan=False, indent=2))
        return 0
    except (ValueError, OSError, UnicodeError) as error:
        print('Kayış hesabı: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
