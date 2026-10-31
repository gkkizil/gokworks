from copy import deepcopy
from dataclasses import asdict

import pytest

from modules.nesting.stock_library import StockLibrary,KEY
from modules.nesting.materials import new_project
from modules.nesting.models import Material,Sheet


class Settings:
    def __init__(self):self.values={};self.last_error='write failed';self.ok=True
    def get(self,key,default=None):return self.values.get(key,default)
    def set(self,key,value):self.values[key]=deepcopy(value)
    def flush(self):return self.ok


def test_all_sheet_and_custom_material_fields_survive_independent_new_projects():
    settings=Settings();library=StockLibrary(settings);project=new_project()
    custom=Material('special','Özel alaşım',2712.5,'Üretici föyü')
    project.materials.append(custom)
    sheet=Sheet('special-sheet','Özel sac',1000,2000,3.5,custom.id,27,78.5,999,'sheet')
    project.sheets.append(sheet);library.remember(project,sheet=sheet)
    a=library.new_project();b=library.new_project()
    assert asdict(a.sheet(sheet.id))==asdict(sheet) and asdict(a.material(custom.id))==asdict(custom)
    a.sheet(sheet.id).stock=0;a.material(custom.id).density=1
    assert b.sheet(sheet.id).stock==27 and b.material(custom.id).density==2712.5
    assert not b.parts


def test_edits_upsert_without_duplicating_and_foreign_project_edits_do_not_delete_stock():
    settings=Settings();library=StockLibrary(settings);project=new_project();a=project.sheets[0]
    library.remember(project,sheet=a)
    a.stock=0;a.price_kg=33;library.remember(project,sheet=a)
    assert len(library.new_project().sheets)==1 and library.new_project().sheets[0].stock==0
    other=new_project();b=other.sheets[0];b.name='Başka projenin sacı'
    library.remember(other,sheet=b)
    assert {s.id for s in library.new_project().sheets}=={a.id,b.id}
    library.remember(other,removed=b.id)
    assert [s.id for s in library.new_project().sheets]==[a.id]


def test_material_density_updates_are_shared_with_referenced_stock():
    settings=Settings();library=StockLibrary(settings);project=new_project();sheet=project.sheets[0]
    library.remember(project,sheet=sheet)
    material=project.material(sheet.material);material.density=7801
    library.remember(project,material=material)
    assert library.new_project().material(sheet.material).density==7801


@pytest.mark.parametrize('change',[
    lambda p:p.update(version=True),lambda p:p.update(sheets='invalid'),
    lambda p:p['sheets'][0].update(stock=True),lambda p:p['sheets'][0].update(width=0),
    lambda p:p['sheets'][0].update(material='missing'),lambda p:p['materials'][0].update(density=float('nan')),
])
def test_invalid_library_is_rejected_without_replacing_the_saved_value(change):
    settings=Settings();library=StockLibrary(settings);project=new_project()
    library.remember(project,sheet=project.sheets[0]);change(settings.values[KEY])
    before=deepcopy(settings.values[KEY])
    with pytest.raises(ValueError,match='Kalıcı sac stoğu'):library.remember(project,sheet=project.sheets[0])
    # repr also compares the deliberate NaN test without NaN equality semantics.
    assert repr(settings.values[KEY])==repr(before)


def test_persistence_failure_is_reported_without_losing_the_in_memory_edit():
    settings=Settings();settings.ok=False;library=StockLibrary(settings);project=new_project()
    project.sheets[0].stock=19
    with pytest.raises(OSError,match='write failed'):library.remember(project,sheet=project.sheets[0])
    assert settings.values[KEY]['sheets'][0]['stock']==19


def test_intentionally_empty_stock_does_not_restore_the_factory_sheet():
    settings=Settings();library=StockLibrary(settings);project=new_project()
    library.remember(project,sheet=project.sheets[0]);deleted=project.sheets.pop().id
    library.remember(project,removed=deleted)
    assert library.new_project().sheets==[] and library.new_project().materials
