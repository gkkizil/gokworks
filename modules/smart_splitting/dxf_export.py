"""Atomic, reimport-checked nominal/blank contours; no duplicated seam entities."""
from io import StringIO
import json
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

import ezdxf
from ezdxf.math import Matrix44
from shapely import affinity, union_all
from shapely.geometry import Polygon

from modules.nesting.dxf_import import check_cancel, flatten_entity, read_dxf


def document_for(geometry, source, *, offset=(0.,0.)):
    doc=ezdxf.new('R2018'); doc.units=4
    for name,color in (('OUTER_CONTOUR',7),('INNER_CONTOUR',1),('SPLIT_EDGE',3),('REFERENCE',8)):
        doc.layers.new(name,dxfattribs={'color':color,'plot':int(name!='REFERENCE')})
    circles=[]
    if source.original_dxf:
        native=ezdxf.read(StringIO(source.original_dxf))
        circles=list(native.modelspace().query('CIRCLE'))
    for inner,ring in [(False,geometry.exterior),*((True,r) for r in geometry.interiors)]:
        layer='INNER_CONTOUR' if inner else 'OUTER_CONTOUR'
        match=None
        for circle in circles:
            vertices,_,_=flatten_entity(circle,max(source.curve_tolerance,.001))
            approximation=Polygon([(v.x,v.y) for v in vertices])
            if Polygon(ring).symmetric_difference(approximation).area<max(1e-7,approximation.area*1e-10):
                match=circle; break
        if match is not None:
            copy=match.copy(); copy.transform(Matrix44.translate(*offset,0)); copy.dxf.layer=layer
            doc.modelspace().add_entity(copy)
        else:
            doc.modelspace().add_lwpolyline([(x+offset[0],y+offset[1]) for x,y in list(ring.coords)[:-1]],
                                          close=True,dxfattribs={'layer':layer})
    return doc


def embedded_dxf(geometry, source):
    stream=StringIO(); document_for(geometry,source).write(stream)
    return stream.getvalue()


def export_segments(solution, directory, *, stop=None):
    from .validation import validate_partition
    validate_partition(solution.source.polygon,[s.nominal for s in solution.segments],solution.settings.count)
    directory=Path(directory)
    if directory.exists(): raise FileExistsError('DXF için henüz bulunmayan yeni bir klasör seçin.')
    directory.parent.mkdir(parents=True,exist_ok=True)
    stem=re.sub(r'[^\w.\-]+','_',solution.source.code,flags=re.UNICODE).strip('.')[:100] or 'PARCA'
    outputs=[]; combined=ezdxf.new('R2018'); combined.units=4; offset=0.; combined_shapes=[]
    with TemporaryDirectory(prefix='.gokworks-split-',dir=directory.parent) as tmp:
        tmp=Path(tmp)
        for segment in solution.segments:
            check_cancel(stop)
            g=segment.blank; x0,y0,x1,y1=g.bounds; normalized=affinity.translate(g,-x0,-y0)
            filename=f'{stem}_SEG_{segment.number:03d}.dxf'
            # Native circles are matched in source assembly coordinates first.
            doc=document_for(g,solution.source,offset=(-x0,-y0)); doc.saveas(tmp/filename)
            loaded=read_dxf(tmp/filename,tolerance=max(solution.source.curve_tolerance,.001),stop=stop)
            if len(loaded)!=1 or normalized.symmetric_difference(loaded[0].polygon).area>max(1e-5,g.area*1e-9):
                raise ValueError('Segment DXF yeniden okuma / kontur doğrulaması başarısız.')
            model=combined.modelspace()
            placed_doc=document_for(g,solution.source,offset=(offset-x0,-y0))
            for layer in placed_doc.layers:
                if layer.dxf.name not in combined.layers:
                    combined.layers.new(layer.dxf.name,dxfattribs={'color':layer.dxf.color,'plot':layer.dxf.plot})
            for entity in placed_doc.modelspace(): model.add_entity(entity.copy())
            combined_shapes.append(affinity.translate(g,offset-x0,-y0))
            offset+=x1-x0+max(10.,solution.settings.gap); outputs.append(filename)
        combined.saveas(tmp/(stem+'_TUM_SEGMENTLER.dxf'))
        loaded=read_dxf(tmp/(stem+'_TUM_SEGMENTLER.dxf'),grouped=True,
                        tolerance=max(solution.source.curve_tolerance,.001),stop=stop)
        # Reader normalizes the combined assembly; its minimum is (0,0).
        expected=union_all(combined_shapes)
        if len(loaded)!=1 or expected.symmetric_difference(loaded[0].polygon).area>max(1e-5,expected.area*1e-9):
            raise ValueError('Birleşik DXF kontur doğrulaması başarısız.')
        report=dict(source=solution.source.code,source_sha256=solution.source.source_sha256,
                    count=len(solution.segments),quantity=solution.settings.quantity,
                    area_delta=solution.area_delta,symmetric_difference=solution.symmetric_difference,
                    nominal_area=solution.source.area,blank_area=sum(s.blank.area for s in solution.segments),
                    total_nominal_area=solution.source.area*solution.settings.quantity,
                    total_blank_area=sum(s.blank.area for s in solution.segments)*solution.settings.quantity,
                    joining_length=solution.seam_length,kerf_loss_estimate=solution.seam_length*solution.settings.kerf,
                    total_joining_length=solution.seam_length*solution.settings.quantity,
                    weld_gap=solution.settings.weld_gap,machining_allowance=solution.settings.allowance,
                    center=solution.center,angles=solution.angles,warnings=solution.warnings,
                    segments=[dict(id=s.id,number=s.number,area=s.nominal.area,blank_area=s.blank.area,
                        perimeter=s.blank.length,bounds=s.blank.bounds,minimum_width=s.minimum_width,
                        neighbors=s.neighbors,joining_length=s.seam_length,valid=s.blank.is_valid) for s in solution.segments])
        (tmp/'BOLME_RAPORU.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        check_cancel(stop); os.rename(tmp,directory)
    return [directory/name for name in outputs]
