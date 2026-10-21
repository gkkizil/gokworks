"""Pinlenmiş GitHub tablolarını gerçek GOKWORKS hesap koduyla karşılaştır.

Kaynak checkoutlarını --sources dizininde isofits, passungsrechner,
iso-286-rust ve ISO286 adlarıyla hazırlayın. Ağ isteği/kod indirmesi yapmaz.
"""

import argparse
import ast
from collections import Counter
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from modules.iso_fits.rules import classes, limits

SOURCES = {
    'isofits': ('parkergreene/isofits', 'd3083a941e8071bb12114a28a25274bf99c30ac0', 'src/data.py'),
    'passungsrechner': ('lachr/Passungsrechner', '0289439b1883db363d92e38f1ab352817b4d5a47', 'src/data/tolerances.json'),
    'iso-286-rust': ('bell-jamie/iso-286', '6580fbecaf167249024c60e35c4b8fbbddb540f4', 'src/tables.rs'),
    'ISO286': ('saucecode/ISO286', 'f455cecdfc6659f35002bc112e3667f4316eb086', 'iso286.py'),
}


def literal_assignments(path):
    return {node.targets[0].id: ast.literal_eval(node.value)
            for node in ast.parse(path.read_text()).body
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'docs/reports/iso-fits/source-comparison.json')
    args = parser.parse_args()
    evidence = {'sources': {}, 'table_sha256': hashlib.sha256((ROOT/'modules/iso_fits/tables.json').read_bytes()).hexdigest()}
    for name, (repo, expected, relative) in SOURCES.items():
        folder = args.sources/name
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=folder, text=True).strip()
        if commit != expected:
            raise ValueError(f'{repo}: kaynak commit değişti.')
        evidence['sources'][name] = {'repository': repo, 'commit': commit, 'file': relative,
                                    'sha256': hashlib.sha256((folder/relative).read_bytes()).hexdigest()}
    source = args.sources/'isofits/src'
    sys.path.insert(0, str(source))
    spec = importlib.util.spec_from_file_location('reference_isofits', source/'isofits.py')
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    records = json.loads((args.sources/'passungsrechner/src/data/tolerances.json').read_text())
    count, mismatches = Counter(), []
    bounds = json.loads((ROOT/'modules/iso_fits/tables.json').read_text())['bounds_mm']
    for feature in ('hole', 'shaft'):
        reference_data = reference.hole_data if feature == 'hole' else reference.shaft_data
        for code in classes(feature):
            lower = 0
            for upper in bounds:
                for size in (Decimal(upper), Decimal(lower+upper)/2):
                    band = limits(size, code, feature)
                    actual = (band.upper_nm, band.lower_nm)
                    if size > 3 and code in reference_data:
                        expected = tuple(int(Decimal(str(v))*1000) for v in reference.isotol(feature, float(size), code, 'both'))
                        count['isofits_runtime'] += 1
                        if actual != expected:
                            mismatches.append({'source': 'isofits_runtime', 'class': code, 'diameter_mm': str(size), 'application_nm': actual, 'source_nm': expected})
                    rows = [r for r in records if r['toleranzklasse'] == code and Decimal(str(r['lowerlimit'])) < size <= Decimal(str(r['upperlimit']))]
                    if rows:
                        if len(rows) != 1:
                            raise ValueError(f'Çakışan kaynak satırı: {code} / {size}')
                        expected = tuple(int(Decimal(str(rows[0][key]))*1000) for key in ('es', 'ei'))
                        count['passungsrechner_table'] += 1
                        if actual != expected:
                            mismatches.append({'source': 'passungsrechner_table', 'class': code, 'diameter_mm': str(size), 'application_nm': actual, 'source_nm': expected})
                lower = upper
    # Independent IT widths at every supported diameter interval, including ≤3.
    numeric = literal_assignments(args.sources/'ISO286/iso286.py')
    for feature in ('hole', 'shaft'):
        for code in classes(feature):
            grade = int(''.join(c for c in code if c.isdigit()))
            for size in bounds:
                width = next(row[grade+1]*100 for (low, high), row in numeric['tolerance_grades'].items() if low < size <= high)
                if limits(size, code, feature).tolerance_nm != width:
                    raise ValueError(f'IT genişliği uyuşmuyor: {size}/{code}')
                count['independent_it_width'] += 1
    for feature, codes in [('hole', ('F8', 'G7')), ('shaft', ('c11', 'd9', 'e8', 'f7', 'g6'))]:
        for code in codes:
            column = 'A B C CD D E EF F FG G H'.split().index(code[0].upper())
            for size in bounds:
                base = next(row[column]*1000 for (low, high), row in numeric['fundamental_deviations_A_to_H'].items() if low < size <= high)
                band = limits(size, code, feature)
                actual = band.lower_nm if feature == 'hole' else -band.upper_nm
                if actual != base:
                    raise ValueError(f'Temel sapma uyuşmuyor: {size}/{code}')
                count['independent_fundamental_deviation'] += 1
    f_ei = numeric['fundamental_deviations_A_to_H'][(0, 3)][7]*1000
    if limits(3, 'F8', 'hole').lower_nm != f_ei:
        raise ValueError('F8 temel sapması uyuşmuyor.')
    count['independent_f8_fundamental_deviation'] += 1
    # Reject unexpected differences; retain both known bad source comparisons.
    if len(mismatches) != 2 or any(r['source'] != 'passungsrechner_table' or r['class'] != 'F8'
                                  or Decimal(r['diameter_mm']) not in (Decimal('1.5'), Decimal(3))
                                  or r['application_nm'] != (20000, 6000) or r['source_nm'] != (20000, 10000)
                                  for r in mismatches):
        raise ValueError(f'Beklenmeyen kaynak farkı: {mismatches}')
    evidence.update(comparisons=dict(count), comparisons_total=sum(count.values()),
                    known_source_errors=mismatches, unexpected_differences=0,
                    f8_resolution='F8 ≤3: EI=+6 µm; IT8=14 µm; ES=+20 µm. Kaynaktaki EI=+10 µm reddedildi.',
                    limits='Resmî ISO metni erişilemedi. Rust kodu yürütülmedi; sayısal tablo kaynağıdır. Dış Python isotol gerçekten yürütüldü; 3 mm sınır hatası nedeniyle yalnız D>3 için kullanıldı.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'comparisons': dict(count), 'known_source_errors': len(mismatches), 'unexpected_differences': 0}))


if __name__ == '__main__':
    main()
