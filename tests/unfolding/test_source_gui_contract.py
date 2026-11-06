"""The existing Qt adapter consumes source metadata without a second parameter list."""
from core.unfolding import UnfoldService
from core.unfolding.source_models import inventory
from modules.sheet_unfolding.service import EngineService
from .test_source_models import request


def test_adapter_exposes_all_191_source_variants_and_turkish_metadata():
    service=EngineService();shapes=service.list_shapes()
    source=[shape for shape in shapes if shape.get('source_ids')]
    assert len(source)==51
    assert sum(len(shape['variants']) for shape in source)==191
    assert {shape['category'] for shape in source}=={m['category'] for m in inventory()['models']}
    assert not any(shape['status']=='planned' for shape in source)
    for m in inventory()['models']:
        schema=service.get_schema(**m['internal_id'])
        assert schema['source_id']==m['source_id']
        assert [f['id'] for f in schema['parameters']]==[f['id'] for f in m['fields']]
        assert schema['options']['model_options']['cut_options']==m['cut_options']
        assert all(f['kind']!='length' for f in schema['parameters'] if f['id'] in {v['id'] for v in m['fields'] if v['kind'] in ('angle','count','option')})


def test_adapter_preserves_source_manufacturing_options_in_project_dto():
    original=request('oval-cylinder',model_options={'cut_type':'2_parts_180_degrees','strip_lap':7.})
    page=EngineService.page_request(original)
    restored=EngineService.engine_request(page)
    assert restored.model_options==original.model_options
    assert UnfoldService().calculate(restored).status=='success'
