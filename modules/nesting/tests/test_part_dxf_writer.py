"""Each part's own DXF text: the fast template path gives the same entities as a full document."""
from io import StringIO

import ezdxf

import modules.nesting.dxf_import as dxf_import
from modules.nesting.dxf_import import PartDxfWriter, read_dxf


def mixed_drawing(path):
    doc = ezdxf.new(); doc.units = 4; msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (60, 0), (60, 40), (0, 40)], close=True)            # part 1 outline
    msp.add_circle((15, 20), 5)                                                       # its hole
    msp.add_line((100, 0), (160, 0)); msp.add_line((160, 0), (160, 30))              # part 2: lines + arc
    msp.add_arc((130, 30), 30, 0, 180); msp.add_line((100, 30), (100, 0))
    msp.add_ellipse((230, 20), major_axis=(30, 0), ratio=.5)                          # part 3
    msp.add_spline([(300, 0), (330, 30), (360, 0)], degree=2).closed = True          # part 4
    doc.saveas(path)
    return path


def entities(text):
    doc = ezdxf.read(StringIO(text))
    assert not doc.audit().has_errors
    rows = []
    for entity in doc.modelspace():
        attributes = {k: str(v) for k, v in entity.dxf.all_existing_dxf_attribs().items() if k not in ('handle', 'owner')}
        if entity.dxftype() == 'LWPOLYLINE':
            attributes['points'] = str([tuple(round(c, 9) for c in p) for p in entity.get_points()])
        if entity.dxftype() == 'SPLINE':
            attributes['control'] = str([tuple(round(c, 9) for c in p) for p in entity.control_points])
        rows.append((entity.dxftype(), sorted(attributes.items())))
    return sorted(rows)


def test_fast_path_matches_the_full_document_for_every_part(tmp_path, monkeypatch):
    path = mixed_drawing(tmp_path/'mixed.dxf')
    fast = read_dxf(path)
    monkeypatch.setattr(PartDxfWriter, 'text', lambda self, entities: None)     # force the full-document path
    full = read_dxf(path)
    assert len(fast) == len(full) >= 3
    for a, b in zip(fast, full):
        assert a.original_dxf != b.original_dxf                                 # really written another way
        assert entities(a.original_dxf) == entities(b.original_dxf)


def test_entities_that_refer_to_other_objects_use_the_full_document():
    writer = PartDxfWriter()
    doc = ezdxf.new(); block = doc.blocks.new('B'); block.add_line((0, 0), (1, 0))
    insert = doc.modelspace().add_blockref('B', (0, 0)).copy()
    assert writer.text([insert]) is None and writer.text([]) is None


def test_parts_of_one_import_do_not_share_or_leak_entities(tmp_path):
    parts = read_dxf(mixed_drawing(tmp_path/'mixed.dxf'))
    counts = [len(ezdxf.read(StringIO(p.original_dxf)).modelspace()) for p in parts]
    assert counts == [2, 4, 1, 1]                           # every source entity once, in its own part
    assert dxf_import.PartDxfWriter().text is not None
