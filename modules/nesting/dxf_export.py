"""Validated nominal contours, analytic entities when available; no CAM toolpath claims."""

from io import StringIO
import csv
import json
import math
from pathlib import Path
import tempfile
import os

import ezdxf
from ezdxf.math import Matrix44
from shapely.geometry import LineString
from shapely import union_all

from modules.nesting.geometry import rings
from modules.nesting.validation import validate_result
from modules.nesting.dxf_import import check_cancel, flatten_entity
from modules.nesting.cutting import contour_plan

LAYERS = {'SHEET_BOUNDARY': 8, 'PART_OUTER': 7, 'PART_INNER': 1, 'PART_LABELS': 3, 'PART_REFERENCE': 4}


def export_dxf(project, result, directory, *, separate=True, stop=None):
    validate_result(project, result, stop=stop)
    directory = Path(directory)
    if directory.exists():
        raise FileExistsError('DXF için henüz bulunmayan yeni bir çıktı klasörü seçin.')
    directory.parent.mkdir(parents=True, exist_ok=True)
    # Whole export is published only after every sheet has been checked.
    with tempfile.TemporaryDirectory(prefix='.gokworks-nest-', dir=directory.parent) as tmp:
        tmp = Path(tmp); documents = {}; outputs = []; cut_rows = []
        keys = list(dict.fromkeys((p.sheet_id, p.sheet_number) for p in result.placements))
        for index, key in enumerate(keys, 1):
            check_cancel(stop)
            sheet = project.sheet(key[0]); offset = 0 if separate else sum(project.sheet(k[0]).width+100 for k in keys[:index-1])
            document_key = key if separate else 'all'
            if document_key not in documents:
                doc = ezdxf.new('R2018'); doc.units = ezdxf.units.MM
                doc.appids.new('GOKWORKS_NEST')
                for name, color in LAYERS.items():
                    doc.layers.new(name, dxfattribs={'color': color, 'plot': int(name in ('PART_OUTER', 'PART_INNER'))})
                documents[document_key] = doc
            doc = documents[document_key]; model = doc.modelspace()
            model.add_lwpolyline([(offset, 0), (offset+sheet.width, 0), (offset+sheet.width, sheet.height), (offset, sheet.height)],
                                 close=True, dxfattribs={'layer': 'SHEET_BOUNDARY'})
            entity_groups = {}
            for placement_index,placement in enumerate(result.placements):
                if (placement.sheet_id,placement.sheet_number) != key:
                    continue
                check_cancel(stop)
                part = project.part(placement.part_id)
                transform = Matrix44.chain(Matrix44.z_rotate(math.radians(placement.angle)),
                                           Matrix44.translate(placement.x+offset, placement.y, 0))
                if part.original_dxf:
                    source = ezdxf.read(StringIO(part.original_dxf))
                    boundaries = [LineString(coords) for _,coords in rings(part.polygon)]
                    entities = list(source.modelspace())
                    if not entities:
                        raise ValueError(part.code + ': saklanan DXF konturları boş.')
                    outlines = []
                    for entity in entities:
                        if entity.dxftype() not in ('LINE','ARC','CIRCLE','LWPOLYLINE','POLYLINE','SPLINE','ELLIPSE'):
                            raise ValueError('Saklanan DXF içinde kesim dışı nesne var.')
                        vertices,_,_ = flatten_entity(entity,max(part.curve_tolerance,.001))
                        points = [(v.x, v.y) for v in vertices]
                        curve = LineString(points)
                        outlines.append(curve)
                        tolerance = max(.002,2*part.curve_tolerance+2*part.join_tolerance)
                        matches = [i for i,r in enumerate(boundaries)
                                   if curve.difference(r.buffer(tolerance)).length < .002]
                        if len(matches) != 1:
                            raise ValueError(part.code + ': saklanan DXF ile doğrulanan kesim konturu eşleşmiyor veya birden çok kontura eşleşiyor; yeniden içe aktarın.')
                        entity = entity.copy(); entity.transform(transform)
                        entity_groups.setdefault((placement_index,matches[0]),[]).append(entity)
                    expected = part.polygon.boundary
                    actual = union_all(outlines); error = part.curve_tolerance+2*part.join_tolerance+1e-6
                    if not expected.difference(actual.buffer(error)).is_empty or not actual.difference(expected.buffer(error)).is_empty:
                        raise ValueError(part.code + ': saklanan DXF ile doğrulanan kontur eşleşmiyor; yeniden içe aktarın.')
                model.add_text(part.code, dxfattribs={'height': min(8, max(1, sheet.width/200)), 'layer': 'PART_LABELS'}).set_placement(
                    (placement.x+offset, placement.y))
                model.add_point((placement.x+offset, placement.y), dxfattribs={'layer': 'PART_REFERENCE'})
            for contour in contour_plan(project,result,key,stop=stop):
                check_cancel(stop)
                placement=result.placements[contour.placement_index]
                part=project.part(placement.part_id)
                layer='PART_INNER' if contour.inner else 'PART_OUTER'
                entities=entity_groups.get((contour.placement_index,contour.ring_index))
                if part.original_dxf:
                    if not entities:
                        raise ValueError(part.code + ': özgün DXF içinde bir kesim konturu eksik.')
                    for entity in entities:
                        entity.dxf.layer=layer
                        entity.set_xdata('GOKWORKS_NEST',[(1071,index),(1071,contour.sequence)])
                        model.add_entity(entity)
                else:
                    entity=model.add_lwpolyline([(x+offset,y) for x,y in contour.coordinates[:-1]],
                                               close=True,dxfattribs={'layer':layer})
                    entity.set_xdata('GOKWORKS_NEST',[(1071,index),(1071,contour.sequence)])
                cut_rows.append((index,contour.sequence,part.code,placement.instance,
                                 'İç kontur' if contour.inner else 'Dış kontur',layer))
        for index, doc in enumerate(documents.values(), 1):
            check_cancel(stop)
            filename = f'Levha-{index:03d}.dxf' if separate else 'Tum-levhalar.dxf'
            path = tmp/filename; doc.saveas(path)
            check = ezdxf.readfile(path)
            if check.audit().has_errors:
                raise ValueError('Dışa aktarılan DXF doğrulaması başarısız.')
            outputs.append(filename)
        with (tmp/'KESIM-SIRASI.csv').open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.writer(stream,delimiter=';')
            writer.writerow(('Plaka','Kontur sırası','Parça','Örnek','Kontur türü','DXF katmanı'))
            writer.writerows(cut_rows)
        (tmp/'KESIM-NOTLARI.txt').write_text(
            'GOKWORKS · NOMİNAL BİTMİŞ PARÇA KONTURLARI · birim mm\n'
            'PART_OUTER/PART_INNER kesim geometrisidir. Diğer katmanlar operatör bilgisidir.\n'
            f'Kerf {project.options.kerf:g} mm: çizgiye CAM takım telafisi UYGULANMADI; tezgâhta ayarlayın.\n'
            'Çarpışma mesafesi max(parça aralığı, kerf) + eğri hata paylarıdır. Ortak kesim yoktur.\n'
            'Uygun delik içleri otomatik yerleşim alanı olarak değerlendirilir.\n'
            'KESIM-SIRASI.csv önerilen kontur sırasıdır; DXF kesim nesneleri bu sırayla yazıldı.\n'
            'Önce delik içindeki küçük parçalar ve kendi iç konturları, sonra onları çevreleyen delik ve dış konturlar kesilir.\n'
            'Bu dosya CAM takım yolu değildir. CAM yazılımı nesneleri yeniden sıralayabilir; kontur sırasını CAM içinde uygulayın.\n'
            'Özgün DXF eğrileri korunur; özgün geometri yoksa aşağıdaki kiriş toleransları geçerlidir.\n'
            + '\n'.join(f'{p.code}: eğri {p.curve_tolerance:g} mm; uç hareketi {p.endpoint_error:g} mm; kaynak SHA256 {p.source_sha256}' for p in project.parts)
            + '\nMotor: '+result.engine+' '+result.engine_version+' · Matematiksel optimum garantisi yok.\n', encoding='utf-8')
        check_cancel(stop)
        os.rename(tmp, directory)
    return [directory/name for name in outputs]
