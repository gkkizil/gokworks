from PySide6.QtCore import Qt
from shapely.geometry import box, Point, mapping

from modules.nesting.models import Part
from modules.nesting.thumbnails import PartThumbnails
from .test_nesting_gui import window  # noqa: F401


def test_icon_preserves_real_hole_and_transparent_background(qapp):
    part=Part.create('HOLE',box(0,0,100,100).difference(Point(50,50).buffer(15)))
    cache=PartThumbnails(); cache.set_parts([part]); before=part.geometry.copy()
    icon=cache.icon(part.id); image=icon.pixmap(36,28).toImage()
    assert not icon.isNull()
    assert image.pixelColor(18,14).alpha()==0
    assert image.pixelColor(10,10).alpha()>0 and image.pixelColor(0,0).alpha()==0
    assert part.geometry==before


def test_quantity_edit_reuses_icon_and_geometry_or_theme_changes_refresh_it(qapp):
    part=Part.create('A',box(0,0,100,100)); cache=PartThumbnails(); cache.set_parts([part])
    cache.icon(part.id); assert cache.render_count==1
    part.quantity=3; cache.set_parts([part]); cache.icon(part.id); assert cache.render_count==1
    cache.icon(part.id,'light'); assert cache.render_count==2
    part.geometry=mapping(box(0,0,200,20)); cache.set_parts([part]); cache.icon(part.id)
    assert cache.render_count==3
    cache.set_parts([]); assert cache.icon(part.id).isNull()


def test_cache_is_bounded_and_dpi_aware(qapp):
    cache=PartThumbnails(limit=4); parts=[Part.create(str(i),box(0,0,i+1,10)) for i in range(10)]
    cache.set_parts(parts)
    for part in parts: assert not cache.icon(part.id,dpr=2).isNull()
    assert len(cache.cache)==4


def test_part_rows_show_previews_and_editing_and_selection_still_work(window,qtbot):
    page=window.pages['nesting']; part=Part.create('WITH-HOLE',box(0,0,100,100).difference(Point(50,50).buffer(10)))
    page.project.parts=[part]; fingerprint=page.project.fingerprint(); page.refresh()
    index=page.part_tree_model.index_for_id(part.id)
    assert not index.data(Qt.DecorationRole).isNull()
    assert page.project.fingerprint()==fingerprint
    page.part_table.select_index(index); assert page.selected_part_ids()=={part.id}
    page.set_part_quantity(part.id,5); assert page.project.part(part.id).quantity==5
    page.search.setText('WITH-HOLE'); qtbot.wait(40)
    assert page.part_tree_model.index_for_id(part.id).isValid()
    for theme in ('dark','light'):
        window.set_theme(theme); qtbot.wait(30)
        assert not page.part_tree_model.index_for_id(part.id).data(Qt.DecorationRole).isNull()


def test_sparrow_can_be_selected_and_run_from_the_real_workbench(window,qtbot):
    page=window.pages['nesting']
    page.project.parts=[Part.create('Sparrow parçası',box(0,0,70,40),quantity=3)]
    page.refresh(); page.inspector.fields['engine'].setCurrentText('Sparrow'); page.form.set_value('quality','Hızlı')
    assert page.form.value('engine')=='Sparrow' and page.inspector.engine_hint.isVisible()
    page.start_nest(); assert window.jobs.owner is page
    qtbot.waitUntil(lambda:not window.jobs.busy,timeout=15000)
    assert page.result is not None and page.result.engine=='Sparrow'
    assert len(page.result.placements)==3 and not page.result.unplaced
    assert page.excel_button.isEnabled()
    page.form.set_value('engine','GOKWORKS NFP')
    assert page.result is None and not page.excel_button.isEnabled()
    assert not page.inspector.engine_hint.isVisible()
    page.form.set_value('engine','Sparrow')
    assert page.inspector.fields['engine'].currentText()=='Sparrow' and page.inspector.engine_hint.isVisible()
