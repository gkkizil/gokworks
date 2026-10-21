"""Area/mass conservation and purchasing/operation costs from verified geometry."""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from modules.nesting.geometry import polygons
from modules.nesting.validation import validate_result


def mass(area, thickness, density):
    return area*thickness*density/1_000_000_000


def money(value):
    return Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def calculate(project, result, *, complete=True, stop=None):
    validate_result(project, result, complete=complete, stop=stop)
    groups = defaultdict(list)
    for p in result.placements:
        groups[(p.sheet_id, p.sheet_number)].append(p)
    sheets = []; parts = []; material_total = Decimal(0)
    cut_mm = 0.; piercings = 0
    for plate, ((sheet_id, number), placements) in enumerate(groups.items(),1):
        sheet = project.sheet(sheet_id); material = project.material(sheet.material)
        gross_area = sheet.width*sheet.height
        gross_mass = mass(gross_area, sheet.thickness, material.density)
        net_area = sum(project.part(p.part_id).area for p in placements)
        net_mass = mass(net_area, sheet.thickness, material.density)
        cost = money(sheet.price_sheet if sheet.pricing == 'sheet' else gross_mass*sheet.price_kg)
        material_total += cost; assigned = Decimal(0)
        for index, placement in enumerate(placements):
            part = project.part(placement.part_id); g = part.polygon
            allocation = cost-assigned if index == len(placements)-1 else min(cost-assigned, money(cost*Decimal(str(part.area/net_area))))
            assigned += allocation
            length = g.length
            holes = sum(len(p.interiors) for p in polygons(g)); outer_count = len(polygons(g))
            cut_mm += length; piercings += holes+outer_count
            parts.append(dict(id=part.id, code=part.code, description=part.description, instance=placement.instance,
                              material=material.name, density=material.density, thickness=part.thickness,
                              area=part.area, weight=mass(part.area, part.thickness, material.density),
                              sheet=f'{plate}. plaka · {sheet.name}', plate=plate, sheet_id=sheet_id, sheet_number=number,
                              allocation=float(allocation), perimeter=length,
                              outer_perimeter=sum(p.exterior.length for p in polygons(g)),
                              inner_perimeter=sum(r.length for p in polygons(g) for r in p.interiors),
                              holes=holes, source=part.source, sha256=part.source_sha256))
        if net_area > gross_area+1e-6 or net_mass > gross_mass+1e-9:
            raise ValueError('Brüt / net alan veya ağırlık tutarsızlığı.')
        sheets.append(dict(id=sheet_id, number=number, plate=plate, name=sheet.name, material=material.name,
                           width=sheet.width, height=sheet.height, thickness=sheet.thickness, density=material.density,
                           gross_area=gross_area, net_area=net_area, waste_area=gross_area-net_area,
                           gross_weight=gross_mass, net_weight=net_mass, waste_weight=gross_mass-net_mass,
                           efficiency=100*net_area/gross_area, material_cost=float(cost),
                           net_material_value=float(cost)*net_area/gross_area,
                           waste_material_value=float(cost)*(1-net_area/gross_area),
                           pricing='TL/levha' if sheet.pricing == 'sheet' else 'TL/kg',
                           price=sheet.price_sheet if sheet.pricing == 'sheet' else sheet.price_kg))
    gross_area = sum(s['gross_area'] for s in sheets); net_area = sum(s['net_area'] for s in sheets)
    gross = sum(s['gross_weight'] for s in sheets); net = sum(s['net_weight'] for s in sheets)
    operations = project.operations
    cut_cost = money(cut_mm/1000*operations.cut_price_m)
    piercing_cost = money(piercings*operations.piercing_price)
    setup = money(operations.setup); fixed = money(operations.fixed)
    base = material_total+cut_cost+piercing_cost+setup+fixed
    profit = money(base*Decimal(str(operations.profit_percent/100)))
    vat = money((base+profit)*Decimal(str(operations.vat_percent/100)))
    if sum(money(p['allocation']) for p in parts) != material_total:
        raise ValueError('Dağıtılan malzeme maliyetleri toplamı tutarsız.')
    summaries = []
    for part in project.parts:
        rows = [row for row in parts if row['id'] == part.id]
        if rows:
            bounds = part.polygon.bounds
            summaries.append(dict(id=part.id,code=part.code,description=part.description,material=rows[0]['material'],
                                  thickness=part.thickness,quantity=len(rows),requested=part.quantity,area=part.area,
                                  weight=rows[0]['weight'],total_weight=sum(r['weight'] for r in rows),
                                  allocation=float(sum(money(r['allocation']) for r in rows)),
                                  width=bounds[2]-bounds[0],height=bounds[3]-bounds[1],
                                  sheets=', '.join(dict.fromkeys(r['sheet'] for r in rows))))
    return dict(sheets=sheets, parts=parts, part_summary=summaries, sheet_count=len(sheets), part_count=len(parts), unplaced=len(result.unplaced),
                gross_area=gross_area, net_area=net_area, waste_area=gross_area-net_area,
                gross_weight=gross, net_weight=net, waste_weight=gross-net,
                efficiency=100*net_area/gross_area if gross_area else 0,
                material_cost=float(material_total), net_material_value=sum(s['net_material_value'] for s in sheets),
                waste_material_value=sum(s['waste_material_value'] for s in sheets), cut_length_m=cut_mm/1000,
                piercing_count=piercings, cut_cost=float(cut_cost), piercing_cost=float(piercing_cost),
                setup=float(setup), fixed=float(fixed), profit=float(profit), vat=float(vat), total=float(base+profit+vat))
