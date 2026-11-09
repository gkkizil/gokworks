"""The existing Nesting Part/Sheet/Options contracts; additive, transactional UI transfer."""
from copy import deepcopy
from dataclasses import replace
import hashlib

from shapely import affinity
from modules.nesting.materials import new_project
from modules.nesting.models import Part, Sheet, Options, uid
from .dxf_export import embedded_dxf
from .models import PROFILES


def source_key(source):
    return hashlib.sha256((source.source_sha256+source.code+source.polygon.normalize().wkb_hex).encode()).hexdigest()


def to_project(solution):
    settings=solution.settings; project=new_project(); project.name=solution.source.code+' · Bölünmüş'
    if settings.material not in {m.id for m in project.materials}:
        raise ValueError('Bölme malzemesi Nesting kütüphanesinde bulunamadı.')
    project.parts=[]
    for segment in solution.segments:
        g=segment.blank; x0,y0,_,_=g.bounds
        native=embedded_dxf(g,solution.source)
        # Translate native entities and polygons together, preserving native holes.
        import ezdxf
        from io import StringIO
        from ezdxf.math import Matrix44
        doc=ezdxf.read(StringIO(native))
        for entity in doc.modelspace(): entity.transform(Matrix44.translate(-x0,-y0,0))
        stream=StringIO(); doc.write(stream)
        part=Part.create(f'{solution.source.code}_SEG_{segment.number:03d}',affinity.translate(g,-x0,-y0),
            settings.material,settings.thickness,quantity=settings.quantity,
            source=solution.source.source,source_sha256=solution.source.source_sha256,
            source_unit=solution.source.source_unit,curve_tolerance=solution.source.curve_tolerance,
            join_tolerance=solution.source.join_tolerance,endpoint_error=solution.source.endpoint_error,
            grain_locked=solution.source.grain_locked,
            original_dxf=stream.getvalue(),notes=[*solution.warnings,f'Özgün segment kimliği: {segment.id}',
                'Akıllı bölme kaynak kimliği: '+source_key(solution.source)])
        part.id=segment.id; project.parts.append(part)
    project.sheets=[Sheet(uid(),f'{settings.sheet_width:g} × {settings.sheet_height:g}',
        settings.sheet_width,settings.sheet_height,settings.thickness,settings.material,stock=10000)]
    project.options=Options(gap=settings.gap,margin=settings.margin,kerf=settings.kerf,rotation=settings.rotation,
                            angles=list(settings.angles),quality='Hızlı',seconds=PROFILES[settings.profile][1])
    project.validate(); return project


def transfer_to_nesting(page, solution):
    if page.jobs.busy: raise ValueError('Devam eden işlem bitmeden Nesting’e aktarım yapılamaz.')
    incoming=to_project(solution); candidate=deepcopy(page.project)
    transfers=deepcopy(getattr(page,'_split_transfers',{}))
    key=source_key(solution.source)
    previous=set(transfers.get(key,[]))|{p.id for p in candidate.parts if 'Akıllı bölme kaynak kimliği: '+key in p.notes}
    incoming_ids={p.id for p in incoming.parts}
    candidate.parts=[p for p in candidate.parts if p.id not in previous|incoming_ids]+incoming.parts
    sheet=incoming.sheets[0]
    if not any((s.width,s.height,s.material,s.thickness)==(sheet.width,sheet.height,sheet.material,sheet.thickness) for s in candidate.sheets):
        candidate.sheets.append(sheet)
    for material in incoming.materials:
        if material.id not in {m.id for m in candidate.materials}: candidate.materials.append(material)
    # Cost and grain settings are the user's existing project settings.
    candidate.options=replace(candidate.options,gap=incoming.options.gap,margin=incoming.options.margin,
        kerf=incoming.options.kerf,rotation=incoming.options.rotation,angles=incoming.options.angles)
    candidate.validate(); transfers[key]=[p.id for p in incoming.parts]
    page.invalidate(); page.project=candidate; page._split_transfers=transfers
    page.search.clear(); page.sync_forms(); page.refresh(); page.parts_toggle.setChecked(True)
    page.set_status(f'{len(incoming.parts)} segment türü · {sum(p.quantity for p in incoming.parts)} adet Nesting’e aktarıldı.')
