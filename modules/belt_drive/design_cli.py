"""Qt-free executable automatic search, including normalized local catalogues."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

from .catalog.importers import load_catalog
from .design_models import DesignRequest
from .design_search import search_drives
from .design_serialization import (request_from_dict, request_to_dict, project_loads,
                                   recalculate_project, report_to_dict)
from .serialization import read_json, result_to_dict, MAX_JSON_SIZE


def _read(path):
    with Path(path).open('rb') as stream:
        content = stream.read(MAX_JSON_SIZE + 1)
    if len(content) > MAX_JSON_SIZE:
        raise ValueError('Girdi en çok 2 MiB olabilir.')
    return content


def main(argv=None):
    parser = argparse.ArgumentParser(description='GOKWORKS V / triger-senkron kayış otomatik tasarım motoru')
    parser.add_argument('request', nargs='?', help='Otomatik tasarım isteği JSON')
    parser.add_argument('--catalog', help='Normalize ürün kataloğu JSON/CSV')
    parser.add_argument('--project', help='Geriye uyumlu v1/v2 proje JSON')
    parser.add_argument('--include-unverified', action='store_true', help='Doğrulanmamış geometrik adayları ayrı grupta döndür')
    parser.add_argument('--example', action='store_true', help='1450 → 700 rpm istek örneğini yaz')
    args = parser.parse_args(argv)
    try:
        if args.example:
            if args.request or args.project or args.catalog:
                parser.error('--example başka dosya girdileri ile birleştirilmez.')
            output = request_to_dict(DesignRequest(1.5,1450.,700.,family='timing'))
        elif args.project:
            if args.request or args.catalog or args.include_unverified:
                parser.error('--project yalnız kayıtlı proje girdilerini kullanır.')
            result, selection = recalculate_project(project_loads(_read(args.project)))
            output = report_to_dict(result) if hasattr(result,'search_complete') else result_to_dict(result)
            output['restored_selection'] = selection
        else:
            if not args.request or not args.catalog:
                parser.error('İstek ve --catalog veya --project gerekli.')
            request = request_from_dict(read_json(_read(args.request)))
            if args.include_unverified:
                request = replace(request, include_unverified=True)
            output = report_to_dict(search_drives(request, load_catalog(args.catalog)))
        print(json.dumps(output,ensure_ascii=False,allow_nan=False,indent=2))
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print('Otomatik kayış tasarımı: '+str(error), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('Arama durduruldu; tamamlanmış sonuç üretilmedi.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
