"""Sabit FreeCAD-GDT kaynağını yürütmeden özellik adları/yapısıyla kıyasla."""

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from geometric_tolerances.catalog import CATALOG, ACTIVE

COMMIT = '841518cdd74f6a7dad3321d29937c49dc7dc4b1f'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--standard', type=Path, required=True, help='Kullanıcının sağladığı ASME PDF dosyası')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'docs/reports/geometric-tolerances')
    args = parser.parse_args()
    ref, folder = args.reference.resolve(), args.output_dir.resolve()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ref, text=True).strip()
    assert head == COMMIT, 'Kaynak sürümü değişti; karşılaştırma yeniden incelenmeli.'
    text = (ref/'geometricTolerance.py').read_text()
    labels = ast.literal_eval(re.search(r'^Label = (.+)$', text, re.MULTILINE).group(1))
    records = []
    for item in CATALOG:
        english = 'Concentricity' if item.key == 'concentricity' else item.english
        match = next((name for name in labels if name.casefold() == english.casefold()), None)
        assert match, item.key
        records.append({'key': item.key, 'application': english, 'reference': match, 'match': True, 'asme_2018_active': item.active, 'asme_section': item.reference})
    assert len(labels) == len(records) == 14
    assert "Text='Tolerance value:'" in text and "Text='Datum system:'" in text
    files = [ref/'README.md', ref/'GDT.py', ref/'geometricTolerance.py', *sorted((ref/'Gui/Resources/icons/Characteristic').glob('*.svg'))]
    standard = args.standard.resolve()
    pdf_text = subprocess.check_output(['pdftotext', str(standard), '-'], text=True)
    assert 'ASME Y14.5-2018' in pdf_text, 'Belge baskısı doğrulanamadı.'
    anchors = [('Önsöz: kaldırılanlar', 'two past practices, use of concentricity'),
               ('5.8.1: Rule #1', '5.8.1 Rule #1'),
               ('5.9.1: Rule #2', '5.9.1 Rule #2'),
               ('8.4.4: silindiriklik', '8.4.4 Cylindricity'),
               ('10.3.2: RFS konum', '10.3.2 RFS as Related'),
               ('11.3.1: profil bölgesi', '11.3.1 Uniform Tolerance Zone'),
               ('12.4.2.1: toplam salgı', '12.4.2.1 Total Runout Tolerance Zone'),
               ('D.4: kaldırılan semboller', 'D-4 CONCENTRICITY AND SYMMETRY SYMBOLS')]
    pages = pdf_text.split('\f')
    checks = []
    for name, anchor in anchors:
        matches = [index+1 for index, page in enumerate(pages)
                   if anchor.casefold() in ' '.join(page.split()).casefold()]
        assert matches, name
        checks.append({'section': name, 'pdf_pages': matches, 'found': True})
    info = subprocess.check_output(['pdfinfo', str(standard)], text=True)
    count = int(re.search(r'^Pages:\s+(\d+)', info, re.MULTILINE).group(1))
    title = re.search(r'^Title:\s*(.*)', info, re.MULTILINE).group(1)
    primary = {'filename': standard.name, 'sha256': hashlib.sha256(standard.read_bytes()).hexdigest(),
               'bytes': standard.stat().st_size, 'pdf_pages': count, 'cover_edition': 'ASME Y14.5-2018',
               'r2024_in_filename': 'R2024' in standard.name, 'r2024_confirmed_in_content':
               'R2024' in pdf_text or 'Reaffirmed 2024' in pdf_text,
               'metadata_title': title, 'metadata_used_as_edition_evidence': False,
               'reviewed_sections': ['Önsöz', '5.1.1.2', '5.8.1–5.8.3', '5.9.1–5.9.2', '7',
                   '8.4.1–8.4.4', '9.3', '10.2–10.3.2', '10.6–10.7', '11.2–11.3', '12.4', 'D.2–D.4'],
               'section_anchor_checks': checks, 'pdf_published_to_repository': False,
               'full_standard_conformance_certified': False}
    folder.mkdir(parents=True, exist_ok=True)
    result = {'checked_utc': datetime.now(timezone.utc).isoformat(),
              'repository': 'https://github.com/juanvanyo/FreeCAD-GDT', 'commit': head,
              'discovered_via': 'https://github.com/FreeCAD/FreeCAD-addons/blob/master/.gitmodules',
              'comparisons_total': len(records), 'unexpected_differences': 0, 'characteristics': records,
              'explicit_tolerance_and_separate_datum_system': True,
              'freecad_application_executed': False, 'numeric_standard_validation': False,
              'source_code_copied': False, 'primary_standard': primary,
              'active_characteristics': len(ACTIVE), 'legacy_symbols_blocked': ['concentricity', 'symmetry'],
              'reference_sha256': {str(file.relative_to(ref)): hashlib.sha256(file.read_bytes()).hexdigest() for file in files}}
    (folder/'source-comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(f'{len(records)} özellik adı eşleşti; kaynak uygulama yürütülmedi.')


if __name__ == '__main__':
    main()
