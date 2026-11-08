"""Proje/rapor geri okuma, atomik yazma, iptal ve servis sözleşmesi."""
import json
import shutil
import subprocess
import threading
import unicodedata
from dataclasses import replace

import pytest

from modules.hydraulic_unit.core import Project, calculate_project
from modules.hydraulic_unit.serialization import dumps, loads, save, load
from modules.hydraulic_unit.service import describe, calculate
from modules.hydraulic_unit.report.export import export_json, export_excel, export_pdf


def test_project_roundtrip_and_strict_schema(tmp_path):
    p = Project(); path = tmp_path/'örnek.gwhyd'
    save(p,path)
    assert load(path) == p == loads(dumps(p))
    base = json.loads(dumps(p))
    for field,value in [('version',True),('version',2),('units','mm'),('schema','other')]:
        bad = {**base,field:value}
        with pytest.raises(ValueError): loads(json.dumps(bad))
    base['project']['pump']['unknown'] = 1
    with pytest.raises(ValueError): loads(json.dumps(base))
    with pytest.raises(ValueError): loads('{"schema":1,"schema":2}')
    with pytest.raises(ValueError): loads('{"v":NaN}')


def test_loaded_types_and_nonfinite_numbers_rejected():
    for key,value in [('overload','0.1'),('selected_motor',True),('name',123)]:
        data = json.loads(dumps(Project())); data['project'][key] = value
        with pytest.raises(ValueError): loads(json.dumps(data))
    data = json.loads(dumps(Project())); data['project']['pump']['displacement'] = float('inf')
    with pytest.raises(ValueError): loads(json.dumps(data))


def test_metadata_and_si_results_are_json_serializable():
    m = describe(); r = calculate(Project())
    assert m['version'] == r['version'] == 1
    assert not m['capabilities']['simultaneous']
    assert len(m['models']['Project']) > 10
    assert len(r['cycle']['phases']) == 4
    assert all(row['formula'] and row['unit'] for row in r['rows'])
    json.dumps(m,allow_nan=False); json.dumps(r,allow_nan=False)


def test_metric_and_us_only_change_presentation():
    a = calculate(Project()); b = calculate(replace(Project(),display_units='us'))
    assert a['cycle'] == b['cycle'] and a['thermal'] == b['thermal']
    assert a['rows'][0]['unit'] == 'L/min' and b['rows'][0]['unit'] == 'gpm'


def test_json_and_excel_preserve_inputs_results_and_literal_user_text(tmp_path):
    from openpyxl import load_workbook
    p = replace(Project(),name='=HYPERLINK("bad")'); r = calculate_project(p)
    export_json(p,r,tmp_path/'r.json'); export_excel(p,r,tmp_path/'r.xlsx')
    data = json.loads((tmp_path/'r.json').read_text())
    assert data['units'] == 'SI' and data['result']['cycle']['loss_energy'] == r.cycle['loss_energy']
    book = load_workbook(tmp_path/'r.xlsx',read_only=True,data_only=False)
    try:
        assert book['Özet']['B1'].value == p.name and book['Özet']['B1'].data_type == 's'
        assert book['Fazlar SI'].max_row == 5
        assert book['Girdiler SI'].max_row > 40
    finally: book.close()


@pytest.mark.parametrize('exporter',[export_json,export_excel])
def test_cancel_and_stale_results_preserve_previous_file(tmp_path,exporter):
    p = Project(); r = calculate_project(p); path = tmp_path/'old.dat'; path.write_bytes(b'previous')
    stop = threading.Event(); stop.set()
    with pytest.raises(InterruptedError): exporter(p,r,path,stop=stop)
    assert path.read_bytes() == b'previous'
    with pytest.raises(ValueError): exporter(replace(p,overload=.2),r,path)
    assert path.read_bytes() == b'previous'
    assert list(tmp_path.iterdir()) == [path]


def test_pdf_turkish_text_graphs_and_multipage_output(qapp,tmp_path):
    from modules.hydraulic_unit.report.plots import cycle_images
    p = Project(); r = calculate_project(p)
    images = cycle_images(p,r)
    assert len(images) == 3 and all(not image.isNull() for image in images)
    path = tmp_path/'rapor.pdf'; export_pdf(p,r,path,images)
    assert path.read_bytes().startswith(b'%PDF-')
    if shutil.which('pdftotext'):
        text = unicodedata.normalize('NFKC',subprocess.check_output(['pdftotext','-enc','UTF-8','-layout',str(path),'-']).decode('utf-8'))
        assert 'Hidrolik' in text and 'Presleme' in text and 'Geri dönüş' in text
        assert 'Girdi kaydı' in text and 'Soğutucusuz' in text
        assert text.count('\f') >= 2
        chart_page = next(page for page in text.split('\f') if 'Çevrim grafikleri' in page)
        assert all(title in chart_page for title in ('Gerekli basınç','Gerekli debi','Pompa mil gücü'))


def test_cli_example_without_gui(tmp_path):
    import sys
    target = tmp_path/'demo.gwhyd'
    subprocess.run([sys.executable,'-m','modules.hydraulic_unit','--save',str(target)],
                   capture_output=True,check=True,timeout=20)
    assert load(target) == Project()


def test_incremental_pdf_job_yields_and_cancel_preserves_target(qtbot,tmp_path):
    from modules.hydraulic_unit.report.export import create_pdf_job
    p = Project(); r = calculate_project(p); path = tmp_path/'report.pdf'
    path.write_bytes(b'previous'); job = create_pdf_job(p,r,path)
    progress = []; errors = []
    job.progress.connect(lambda page,total: (progress.append(page),job.cancel()))
    job.failed.connect(errors.append)
    job.start(); qtbot.waitUntil(lambda: bool(errors))
    assert progress == [1] and path.read_bytes() == b'previous'
    assert not list(tmp_path.glob('.gokworks-*'))
    job.cancel()  # tek terminal sinyal
    assert len(errors) == 1
    job.deleteLater()


def test_incremental_pdf_job_completes(qtbot,tmp_path):
    from modules.hydraulic_unit.report.export import create_pdf_job
    p = Project(); r = calculate_project(p); path = tmp_path/'complete.pdf'
    job = create_pdf_job(p,r,path); completed = []; failed = []
    job.finished.connect(completed.append); job.failed.connect(failed.append)
    job.start(); qtbot.waitUntil(lambda: bool(completed) or bool(failed),timeout=10000)
    assert not failed and completed == [str(path)]
    assert path.read_bytes().startswith(b'%PDF-')
    job.deleteLater()
