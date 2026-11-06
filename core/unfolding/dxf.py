"""1:1 planar DXF. Cutting wires are closed bulge polylines, annotations separate."""
import math
from .models import Line2D,Arc2D,Circle2D,Polyline2D
from .geometry import arc_point,guide_label_points

LAYERS=('CUT_OUTER','CUT_INNER','BEND_UP','BEND_DOWN','CONSTRUCTION','SEAM','DIMENSIONS','LABELS','BEND')


def _cut(model,contour,layer):
    if len(contour)==1 and isinstance(contour[0],Circle2D):
        c=contour[0];model.add_circle(c.center,c.radius,dxfattribs={'layer':layer});return
    vertices=[]
    for curve in contour:
        if isinstance(curve,Line2D):vertices.append((*curve.start,0.))
        elif isinstance(curve,Arc2D):
            # <=180° bulges avoid ambiguity in older CAM readers.
            count=max(1,math.ceil(abs(curve.sweep_deg)/180))
            for i in range(count):
                vertices.append((*arc_point(curve,curve.start_angle_deg+curve.sweep_deg*i/count),
                                 math.tan(math.radians(curve.sweep_deg/count)/4)))
        elif isinstance(curve,Polyline2D):
            points=curve.points if curve.closed else curve.points[:-1]
            vertices.extend((*p,0.) for p in points)
        else:raise ValueError('Kesim konturunda desteklenmeyen eleman.')
    model.add_lwpolyline(vertices,format='xyb',close=True,dxfattribs={'layer':layer,'elevation':0.})


def write_dxf(part,path,result):
    import ezdxf
    doc=ezdxf.new('R2013');doc.units=4
    doc.header['$INSUNITS']=4;doc.header['$MEASUREMENT']=1
    for i,name in enumerate(LAYERS):doc.layers.new(name,dxfattribs={'color':7 if i<2 else 3+i%4})
    model=doc.modelspace();_cut(model,part.geometry_2d.outer,'CUT_OUTER')
    for h in part.geometry_2d.holes:_cut(model,h,'CUT_INNER')
    # These are real fold locations. A signed bend direction is not yet part
    # of Line2D; putting all of them on BEND_UP would invent that direction.
    for layer,lines in (('CONSTRUCTION',part.construction_lines),('SEAM',part.seams),('BEND',part.bending_lines)):
        for line,anchor in zip(lines,guide_label_points(lines)):
            model.add_line((*line.start,0),(*line.end,0),dxfattribs={'layer':layer})
            if line.id and layer!='BEND':model.add_text(line.id,dxfattribs={'layer':'LABELS','height':2.}).dxf.insert=anchor
    for annotation in part.dimension_annotations:
        model.add_line((*annotation.start,0),(*annotation.end,0),dxfattribs={'layer':'DIMENSIONS'})
        model.add_text(f'{annotation.value:.6f} {annotation.unit}',dxfattribs={'layer':'DIMENSIONS','height':3.}).dxf.insert=annotation.text_position
    for text,point in part.labels:model.add_text(text,dxfattribs={'layer':'LABELS','height':4.}).dxf.insert=point
    y=part.metrics.bounds_mm[1]-20.
    model.add_text(f'Adet / Quantity: {part.quantity}',dxfattribs={'layer':'LABELS','height':3.}).dxf.insert=(part.metrics.bounds_mm[0],y)
    for warning in result.warnings:
        if warning.code=='APPROXIMATION':
            y-=5.
            model.add_text(warning.message,dxfattribs={'layer':'LABELS','height':2.}).dxf.insert=(part.metrics.bounds_mm[0],y)
    doc.appids.new('GOKWORKS_UNFOLD')
    for entity,line in zip(model.query('LINE[layer=="BEND"]'),part.bending_lines):
        entity.set_xdata('GOKWORKS_UNFOLD',[(1000,line.id),(1000,'direction=NOT_EVALUATED'),(1000,result.input_hash),(1071,result.revision)])
    for e in model.query('LWPOLYLINE CIRCLE'):
        e.set_xdata('GOKWORKS_UNFOLD',[(1000,result.input_hash),(1071,result.revision)])
    doc.saveas(path)
    check=ezdxf.readfile(path)
    if check.units!=4 or check.audit().errors:raise ValueError('DXF tekrar okuma/birim denetimi başarısız.')
    for entity in check.modelspace().query('LWPOLYLINE'):
        if entity.dxf.layer in ('CUT_OUTER','CUT_INNER') and not entity.closed:raise ValueError('Açık DXF kesim konturu.')
