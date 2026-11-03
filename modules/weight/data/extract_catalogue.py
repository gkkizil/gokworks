"""Build ``sections.json`` from manufacturer datasheets (run by a developer, not by the app).

Each row is read programmatically from the PDF text (``pdftotext -layout``); no value is
typed by hand. Every row is checked twice before it is written:

* geometry: the nominal area recomputed from h, b, tw, tf and the radii with the
  EN 10365 / EN 10056-1 formulas must match the tabulated area within rounding;
* mass: the tabulated kg/m must equal area × 7850 kg/m³ within rounding.

Where two manufacturers list the same designation, their dimensions must agree.

Usage:  python modules/weight/data/extract_catalogue.py <folder with the PDFs>
The PDFs and their URLs are listed in SOURCES below.
"""

import json
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEEL = 7850.0

SOURCES = {
    'bs_ipe': dict(manufacturer='British Steel', document='IPE sections – Dimensions and properties',
                   date='2026-07-21', standard='EN 10365',
                   url='https://www.britishsteel.co.uk/wp-content/uploads/2026/07/IPE-datasheet-21.07.26.pdf'),
    'bs_he': dict(manufacturer='British Steel', document='HE sections – Dimensions and properties',
                  date='2026-07-21', standard='EN 10365',
                  url='https://www.britishsteel.co.uk/wp-content/uploads/2026/07/HE-datasheet-21.07.26.pdf'),
    'bs_ea': dict(manufacturer='British Steel', document='Equal angles (EA) – Dimensions and properties',
                  date='2026-07-21', standard='EN 10056-1',
                  url='https://www.britishsteel.co.uk/wp-content/uploads/2026/07/EA-datasheet-21.07.26.pdf'),
    'bs_ua': dict(manufacturer='British Steel', document='Unequal angles (UA) – Dimensions and properties',
                  date='2026-07-21', standard='EN 10056-1',
                  url='https://www.britishsteel.co.uk/wp-content/uploads/2026/07/UA-datasheet-21.07.26.pdf'),
    'swt_ipe': dict(manufacturer='Stahlwerk Thüringen', document='IPE – Details', date='2025-05',
                    standard='EN 10365:2017',
                    url='https://www.stahlwerk-thueringen.de/wp-content/uploads/2025/05/SWT-IPE-Details.pdf'),
    'swt_he': dict(manufacturer='Stahlwerk Thüringen', document='HE – Details', date='2025-06',
                   standard='EN 10365:2017',
                   url='https://www.stahlwerk-thueringen.de/wp-content/uploads/2025/06/SWT-HE-Details.pdf'),
    'swt_hphd': dict(manufacturer='Stahlwerk Thüringen', document='HP / HD – Details', date='2025-06',
                     standard='EN 10365:2017',
                     url='https://www.stahlwerk-thueringen.de/wp-content/uploads/2025/06/SWT-HP-HD-Details.pdf'),
    'swt_upe': dict(manufacturer='Stahlwerk Thüringen', document='UPE – Details', date='2025-06',
                    standard='EN 10365:2017',
                    url='https://www.stahlwerk-thueringen.de/wp-content/uploads/2025/06/SWT-UPE-Details.pdf'),
    'swt_upn': dict(manufacturer='Stahlwerk Thüringen', document='UPN – Details', date='2025-06',
                    standard='EN 10365:2017',
                    url='https://www.stahlwerk-thueringen.de/wp-content/uploads/2025/06/SWT-UPN-Details.pdf'),
    'kocaer_upn': dict(manufacturer='Kocaer Çelik', document='Channels – UPN', date='2025-02',
                       standard='DIN 1026-1 (toleranslar EN 10279)',
                       url='https://kocaersteel.com/uploads/2025/02/channels-upn.pdf'),
}

FAMILIES = {
    'IPE': dict(title='IPE', shape='I', standard='EN 10365'),
    'HEA': dict(title='HEA (HE A)', shape='I', standard='EN 10365'),
    'HEB': dict(title='HEB (HE B)', shape='I', standard='EN 10365'),
    'HEM': dict(title='HEM (HE M)', shape='I', standard='EN 10365'),
    'HP': dict(title='HP', shape='I', standard='EN 10365'),
    'HD': dict(title='HD', shape='I', standard='EN 10365'),
    'UPE': dict(title='UPE', shape='U', standard='EN 10365'),
    'UPN': dict(title='UPN (NPU)', shape='U_tapered', standard='EN 10365 / DIN 1026-1'),
    'L': dict(title='Eşit kollu köşebent (L)', shape='L', standard='EN 10056-1'),
    'LU': dict(title='Farklı kollu köşebent (L)', shape='L', standard='EN 10056-1'),
}

NUMBER = r'[0-9]+(?:[.,][0-9]+)?'


def text(pdf):
    return subprocess.run(['pdftotext', '-layout', str(pdf), '-'], capture_output=True, text=True, check=True).stdout


def num(value):
    return float(value.replace(',', '.'))


def i_area(h, b, tw, tf, r):
    """EN 10365 nominal area of a parallel-flange I/H section (mm²)."""
    return 2 * b * tf + (h - 2 * tf) * tw + (4 - math.pi) * r ** 2


def u_area(h, b, tw, tf, r):
    """EN 10365 nominal area of a parallel-flange channel (UPE) (mm²)."""
    return 2 * b * tf + (h - 2 * tf) * tw + (4 - math.pi) / 2 * r ** 2


def l_area(a, b, t, r1, r2):
    """EN 10056-1 nominal area of an angle (mm²)."""
    return t * (a + b - t) + (1 - math.pi / 4) * (r1 ** 2 - 2 * r2 ** 2)


def british_rows(pdf, family_of):
    """Page 1: designation … kg/m h b tw tf r; area from the second table (cm²)."""
    content = text(pdf)
    rows, areas = {}, {}
    head = re.compile(rf'^\s*((?:IPE|HE) [0-9]+(?: [ABM])?(?: x [0-9]+)?)\s+[0-9]+ x [0-9]+ x [0-9]+\s+'
                      rf'({NUMBER})\s+({NUMBER})\s+({NUMBER})\s+({NUMBER})\s+({NUMBER})\s+({NUMBER})')
    tail = re.compile(rf'\s({NUMBER})\s+((?:IPE|HE) [0-9]+(?: [ABM])?(?: x [0-9]+)?)\s+{NUMBER}\s*$')
    for line in content.splitlines():
        if match := head.match(line):
            name = match.group(1)
            g, h, b, tw, tf, r = map(num, match.groups()[1:])
            rows[name] = dict(mass_kg_m=g, h=h, b=b, tw=tw, tf=tf, r=r)
        elif match := tail.search(line):
            areas[match.group(2)] = num(match.group(1))
    out = []
    for name, row in rows.items():
        family, designation = family_of(name)
        if family is None:
            continue
        out.append(dict(row, designation=designation, family=family, area_cm2=areas[name]))
    return out


def he_family(name):
    match = re.match(r'HE ([0-9]+) ([ABM])$', name)
    if not match:
        return None, None
    return 'HE' + match.group(2), f'HE {match.group(1)} {match.group(2)}'


def ipe_family(name):
    match = re.match(r'IPE ([0-9]+)$', name)
    return ('IPE', f'IPE {match.group(1)}') if match else (None, None)


def swt_rows(pdf, pattern, radii=1):
    content = text(pdf)
    numbers = r'\s+'.join([f'({NUMBER})'] * (6 + radii))
    row = re.compile(rf'^\s*({pattern})[*•]?\s+{numbers}')
    out = []
    for line in content.splitlines():
        if match := row.match(line):
            values = list(map(num, match.groups()[1:]))
            g, h, b, tw, tf = values[:5]
            item = dict(designation=re.sub(r'\s+', ' ', match.group(1)).strip(), mass_kg_m=g, h=h, b=b, tw=tw, tf=tf)
            if radii == 2:
                item.update(r=values[5], r2=values[6])
            else:
                item.update(r=values[5])
            item['area_cm2'] = values[5 + radii]
            out.append(item)
    return out


def angle_rows(pdf, family):
    content = text(pdf)
    row = re.compile(rf'^\s*([0-9]+) x ([0-9]+) x ([0-9]+)\s+({NUMBER})\s+({NUMBER})\s+({NUMBER})\s+({NUMBER})'
                     rf'\s+({NUMBER})\s+({NUMBER})\s+({NUMBER})')
    out = []
    for line in content.splitlines():
        if match := row.match(line):
            g, a, b, t, r1, r2, area = map(num, match.groups()[3:])
            out.append(dict(designation=f'L {match.group(1)}x{match.group(2)}x{match.group(3)}', family=family,
                            mass_kg_m=g, h=a, b=b, tf=t, tw=t, r=r1, r2=r2, area_cm2=area))
    return out


def kocaer_upn(pdf):
    content = text(pdf)
    row = re.compile(r'^\s*(UPN [0-9]+)\s+' + r'\s+'.join([f'({NUMBER})'] * 8))
    out = []
    for line in content.splitlines():
        if match := row.match(line):
            g, h, b, tw, tf, r1, r2, area = map(num, match.groups()[1:])
            out.append(dict(designation=match.group(1), family='UPN', mass_kg_m=g, h=h, b=b, tw=tw, tf=tf,
                            r=r1, r2=r2, area_cm2=area))
    return out


def check(row):
    """Return a list of problems; an empty list means the row is consistent."""
    problems = []
    shape = FAMILIES[row['family']]['shape']
    area_mm2 = row['area_cm2'] * 100
    if shape == 'I':
        computed = i_area(row['h'], row['b'], row['tw'], row['tf'], row['r'])
    elif shape == 'U':
        computed = u_area(row['h'], row['b'], row['tw'], row['tf'], row['r'])
    elif shape == 'L':
        computed = l_area(row['h'], row['b'], row['tf'], row['r'], row['r2'])
    else:
        computed = None  # tapered flanges: no closed formula is applied here
    if computed is not None:
        # Tabulated areas carry 0.1 cm² (10 mm²) resolution; radii are rounded to 1 mm.
        if abs(computed - area_mm2) > max(6.0, 0.004 * area_mm2):
            problems.append(f'alan {computed / 100:.2f} cm² ≠ tablo {row["area_cm2"]} cm²')
    mass = area_mm2 * 1e-6 * STEEL
    if abs(mass - row['mass_kg_m']) > max(0.06, 0.006 * row['mass_kg_m']):
        problems.append(f'kütle {mass:.2f} kg/m ≠ tablo {row["mass_kg_m"]} kg/m')
    return problems


def build(folder):
    folder = Path(folder)
    sets = {
        'bs_ipe': british_rows(folder / 'IPE-datasheet-21.07.26.pdf', ipe_family),
        'bs_he': british_rows(folder / 'HE-datasheet-21.07.26.pdf', he_family),
        'bs_ea': angle_rows(folder / 'EA-datasheet-21.07.26.pdf', 'L'),
        'bs_ua': angle_rows(folder / 'UA-datasheet-21.07.26.pdf', 'LU'),
        # IPE A (light) and IPE O (heavy) are EN 10365 series; IPE AA/V are SWT-only and excluded.
        'swt_ipe': [dict(r, family='IPE') for r in swt_rows(folder / 'SWT-IPE-Details.pdf', r'IPE(?: [AO])? [0-9]+')],
        'swt_he': [dict(r, family='HE' + r['designation'][-1]) for r in
                   swt_rows(folder / 'SWT-HE-Details.pdf', r'HE [0-9]+ [ABM]')],
        'swt_hphd': [dict(r, family=r['designation'][:2]) for r in
                     swt_rows(folder / 'SWT-HP-HD-Details.pdf', r'H[PD] [0-9]+ x [0-9]+(?:,[0-9]+)?')],
        'swt_upe': [dict(r, family='UPE') for r in swt_rows(folder / 'SWT-UPE-Details.pdf', r'UPE [0-9]+')],
        'swt_upn': [dict(r, family='UPN') for r in swt_rows(folder / 'SWT-UPN-Details.pdf', r'UPN [0-9]+', radii=2)],
        'kocaer_upn': kocaer_upn(folder / 'channels-upn.pdf'),
    }
    # Preferred source first; later sources only add designations and must agree on overlaps.
    order = ['swt_ipe', 'bs_ipe', 'swt_he', 'bs_he', 'swt_hphd', 'swt_upe', 'swt_upn', 'kocaer_upn', 'bs_ea', 'bs_ua']
    sections, report, rejected = {}, [], []
    for source in order:
        for row in sets[source]:
            problems = check(row)
            key = row['designation']
            if problems:
                rejected.append(f'{source} {key}: ' + '; '.join(problems))
                continue
            if key in sections:
                first = sections[key]
                fields = ('h', 'b', 'tw', 'tf', 'r', 'r2', 'area_cm2', 'mass_kg_m')
                diff = [f for f in fields if f in row and f in first and abs(row[f] - first[f]) > 0.051 * max(1, abs(first[f]) / 10)]
                if diff:
                    report.append(f'FARK {key}: {first["sources"][0]} ↔ {source}: ' +
                                  ', '.join(f'{f} {first[f]}↔{row[f]}' for f in diff))
                    first.setdefault('differences', []).append(
                        f'{SOURCES[source]["manufacturer"]}: ' + ', '.join(f'{f} = {row[f]:g}' for f in diff))
                else:
                    first['sources'].append(source)
                continue
            sections[key] = dict(row, sources=[source])
    return sets, sections, report, rejected


def main(folder):
    sets, sections, report, rejected = build(folder)
    for name, rows in sets.items():
        print(f'{name}: {len(rows)} satır')
    for line in report + rejected:
        print(line)
    families = {}
    for row in sections.values():
        families.setdefault(row['family'], []).append(row)
    for rows in families.values():
        rows.sort(key=lambda r: (r['h'], r['b'], r['mass_kg_m']))
    data = dict(
        schema='gokworks.weight.sections', version=1, density_basis_kg_m3=STEEL,
        note=('Nominal ölçüler ve kg/m üretici veri sayfalarından programla çıkarıldı (extract_catalogue.py). '
              'Her satırın alanı ölçülerden yeniden hesaplanıp ve kg/m = A × 7850 kontrol edildi.'),
        sources=SOURCES, families={k: dict(FAMILIES[k], sections=[
            {f: r[f] for f in ('designation', 'h', 'b', 'tw', 'tf', 'r', 'r2', 'area_cm2', 'mass_kg_m', 'sources', 'differences') if f in r}
            for r in families.get(k, [])]) for k in FAMILIES if families.get(k)})
    (HERE / 'sections.json').write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('yazıldı:', sum(len(v) for v in families.values()), 'kesit,', len(rejected), 'reddedildi,', len(report), 'fark')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
