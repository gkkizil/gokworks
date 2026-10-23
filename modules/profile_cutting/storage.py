"""Versioned atomic local projects and an auditable cut/scan report."""

import csv
from dataclasses import asdict
import json
from pathlib import Path

from modules.tolerance_stack.storage import atomic_write
from modules.tolerance_stack.calculator import Cancelled as StorageCancelled
from .models import Demand, Project, Property, ScanResult, ScanRow, checkpoint, Cancelled
from .optimizer import validate_plan


def publish(path, writer, stop):
    try: return atomic_write(path,writer,overwrite=True,stop=stop)
    except StorageCancelled as error: raise Cancelled(str(error)) from None


def save(project, scan, path, *, stop=None):
    checkpoint(stop)
    project.validate()
    data = dict(format='GOKWORKS-PROFILE-CUTTING', version=1, unit='mm',
                project=asdict(project), scan=asdict(scan) if scan else None)
    text = json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2)
    if len(text.encode('utf-8')) > 20*1024*1024: raise ValueError('Proje 20 MB sınırını aşıyor.')
    return publish(path, lambda temp: temp.write_text(text, encoding='utf-8'), stop)


def load(path):
    path = Path(path)
    if path.stat().st_size > 20*1024*1024: raise ValueError('Proje 20 MB sınırını aşıyor.')
    try:
        def invalid(_): raise ValueError('Proje sonlu olmayan JSON sayısı içeriyor.')
        data = json.loads(path.read_text(encoding='utf-8'), parse_constant=invalid)
        if data.get('format') != 'GOKWORKS-PROFILE-CUTTING' or type(data.get('version')) is not int or data['version'] != 1 or data.get('unit') != 'mm':
            raise ValueError('Profil kesim proje biçimi/sürümü desteklenmiyor.')
        raw = dict(data['project'])
        raw['demands'] = [Demand(**d) for d in raw['demands']]
        project = Project(**raw); project.validate()
        scan = None
        if data.get('scan'):
            raw = dict(data['scan'])
            rows = []
            for row in raw['rows']:
                row = dict(row)
                row['properties'] = {name: Property(**prop) for name, prop in row['properties'].items()}
                rows.append(ScanRow(**row))
            raw['rows'] = rows; scan = ScanResult(**raw)
            validate_scan(scan)
        return project, scan
    except (TypeError, KeyError, AttributeError, RecursionError) as error:
        raise ValueError('Profil kesim proje içeriği geçersiz.') from error


def validate_scan(scan):
    """Untrusted saved snapshots must be plain typed data before entering Qt."""
    if not isinstance(scan.source, str) or not isinstance(scan.configuration, str):
        raise ValueError('Tarama kaynağı/konfigürasyonu geçersiz.')
    if not isinstance(scan.rows, list) or len(scan.rows) > 20000:
        raise ValueError('Tarama satır sınırı aşıldı.')
    if not isinstance(scan.diagnostics, list) or not all(isinstance(d, dict) for d in scan.diagnostics):
        raise ValueError('Tarama raporu geçersiz.')
    for key in ('scanned_parts', 'weldments', 'unscanned'):
        if type(getattr(scan, key)) is not int or not 0 <= getattr(scan, key) <= 10000000:
            raise ValueError('Tarama sayıları geçersiz.')
    for row in scan.rows:
        for key in ('id', 'source', 'configuration', 'folder', 'profile', 'material', 'length',
                    'angle1', 'angle2', 'thickness', 'standard', 'stock_code', 'length_source',
                    'freshness', 'allowance', 'review_note', 'display_unit'):
            if not isinstance(getattr(row, key), str): raise ValueError('Tarama metin alanı geçersiz.')
        for key in ('excluded', 'geometry_verified', 'reviewed'):
            if type(getattr(row, key)) is not bool: raise ValueError('Tarama doğrulama alanı geçersiz.')
        if type(row.count) is not int or not 0 <= row.count <= 100000:
            raise ValueError('Tarama gövde adedi geçersiz.')
        for key in ('body_refs', 'occurrences', 'issues', 'property_errors'):
            values = getattr(row, key)
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise ValueError('Tarama kaynak/uyarı listesi geçersiz.')
        for prop in row.properties.values():
            if (not all(isinstance(getattr(prop, k), str) for k in ('name', 'raw', 'evaluated', 'status'))
                    or type(prop.resolved) is not bool or type(prop.linked) is not bool):
                raise ValueError('Kayıtlı Cut List property içeriği geçersiz.')


def export_report(project, scan, plan, path, *, stop=None):
    checkpoint(stop)
    if plan: validate_plan(project, plan)
    def write(temp):
        with temp.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream, delimiter=';')
            class SafeWriter:
                def writerow(self, values):
                    checkpoint(stop)
                    writer.writerow(["'"+value if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')) else value for value in values])
            out = SafeWriter()
            out.writerow(['GOKWORKS · Profil kesim / Weldments', 'mm'])
            out.writerow(['Açı bilgisi', 'SOLIDWORKS property açısıdır; doğrudan testere ayarı değildir.'])
            if scan:
                out.writerow(['Tarama özeti', json.dumps(scan.summary, ensure_ascii=False)])
                out.writerow(['Kaynak', 'Konfigürasyon', 'Cut List', 'Profil', 'Malzeme', 'Boy', 'Adet',
                              'Açı 1', 'Açı 2', 'Durum', 'Ek boy', 'İnceleme', 'Sorunlar', 'Gövde kimlikleri', 'Montaj örnekleri'])
                for row in scan.rows:
                    out.writerow(['BİRİM', row.source, row.display_unit or 'okunamadı', 'Hesap: mm'])
                    out.writerow([row.source, row.configuration, row.folder, row.profile, row.material,
                                  row.length, row.count, row.angle1, row.angle2, row.status, row.allowance,
                                  row.review_note, ' | '.join(row.issues+row.errors()),
                                  ' | '.join(row.body_refs), ' | '.join(row.occurrences)])
                    for prop in row.properties.values():
                        out.writerow(['PROPERTY', prop.name, prop.raw, prop.evaluated, prop.resolved, prop.linked, prop.status])
                for diagnostic in scan.diagnostics: out.writerow(['TARAMA NOTU', json.dumps(diagnostic, ensure_ascii=False)])
            out.writerow(['Kesim listesi'])
            for row in project.demands: out.writerow([row.source, row.profile, row.material, row.length, row.count, row.allowance, row.note])
            if plan:
                out.writerow(['Yöntem', plan.method])
                out.writerow(['Stok boyu', plan.stock_length, 'Testere payı / her kesim', plan.kerf, 'Uç düzeltme / bir uç', plan.trim])
                out.writerow(['Stok no', 'Grup', 'Kesim sırası', 'Nominal boy', 'Ek ham boy', 'Tüketim', 'Kalan', 'Açı 1 (kaynak)', 'Açı 2 (kaynak)', 'Doğrulama'])
                for index, bar in enumerate(plan.bars, 1):
                    for order, cut in enumerate(bar.cuts, 1):
                        out.writerow([index, ' / '.join(bar.group), order, cut.length, cut.allowance, cut.consumption, bar.remaining, cut.angle1, cut.angle2, cut.note])
    return publish(path, write, stop)
