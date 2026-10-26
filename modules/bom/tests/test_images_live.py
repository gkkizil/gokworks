"""Opt-in real view capture of an explicitly opened, disposable native part."""

import hashlib
import os
from pathlib import Path
from io import BytesIO

from PIL import Image
import pytest

from modules.bom import images, exporter as bom
from modules.cad_converter.api import call, get


@pytest.mark.skipif(os.name != 'nt' or not os.environ.get('GOKWORKS_BOM_IMAGE_LIVE_SOURCE'),
                   reason='Windows, licensed open SOLIDWORKS and explicit opened BOM image test-copy source required.')
def test_live_bom_image_is_embedded_and_original_view_configuration_and_file_survive(tmp_path):
    source = Path(os.environ['GOKWORKS_BOM_IMAGE_LIVE_SOURCE']).resolve()
    assert source.is_file() and source.suffix.lower() == '.sldprt'
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    model = view = None
    with images.Session() as session:
        try:
            model = call(session.app, 'GetOpenDocumentByName', str(source))
            assert model is not None, 'Open the disposable SLDPRT test copy in SOLIDWORKS first.'
            previous_config = session.active_configuration(model)
            configuration = os.environ.get('GOKWORKS_BOM_IMAGE_LIVE_CONFIG', previous_config)
            visible = bool(get(model, 'Visible'))
            view = get(model, 'ActiveView')
            orientation = images._array(get(view, 'Orientation3'), 16)
            translation = images._array(get(view, 'Translation3'), 3)
            scale = float(get(view, 'Scale2'))
            perspective = bool(call(view, 'HasPerspective'))
            part = bom.Part(source.stem, str(source), configuration, 1)
            preview = session.picture(part)
            assert session.active_configuration(model) == previous_config and bool(get(model, 'Visible')) == visible
            assert images._same(images._array(get(view, 'Orientation3'), 16), orientation)
            assert images._same(images._array(get(view, 'Translation3'), 3), translation)
            assert float(get(view, 'Scale2')) == pytest.approx(scale)
            assert bool(call(view, 'HasPerspective')) == perspective
            with Image.open(BytesIO(preview.png)) as image:
                assert image.format == 'PNG' and image.size == (264, 200)
            result = bom.Result('Explicit live test copy', '', (part,), (), 0, 0, False)
            bom.export_excel(result, tmp_path/'BOM.xlsx', previews={bom.sw._part_key(part.path, configuration): preview})
        finally:
            model = view = None
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
