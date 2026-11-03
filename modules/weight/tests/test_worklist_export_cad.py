"""Calculation list, cost, CSV/XLSX/PDF export and the SOLIDWORKS mass reader (with fakes)."""

import csv

import pytest

from modules.weight import cad, export, rules, worklist


def items():
    beam = worklist.from_result(rules.calculate(kind='IPE', profile='IPE 200', length=6000, count=4), 'Kiriş', 32.5)
    tube = worklist.from_result(rules.calculate(kind='Boru', d=60, t=3, length=1000, count=10))
    return [beam, tube]


def test_list_rows_keep_kg_per_m_and_totals_add_scrap_and_vat():
    beam, tube = items()
    assert beam.unit_mass_kg == pytest.approx(134.4) and beam.total_mass_kg == pytest.approx(537.6)
    assert tube.name == 'Boru Ø60 × 3' and tube.price_per_kg is None
    t = worklist.totals([beam, tube], '5', '20')
    assert t.count == 14 and t.mass_kg == pytest.approx(537.6 + 42.1711689)
    assert t.mass_with_scrap_kg == pytest.approx(t.mass_kg * 1.05)
    assert t.net == pytest.approx(537.6 * 1.05 * 32.5) and t.vat == pytest.approx(t.net * .2)
    assert t.gross == pytest.approx(t.net * 1.2) and t.unpriced_rows == 1
    for bad in ('-1', '101', 'abc'):
        with pytest.raises(ValueError):
            worklist.totals([beam], bad, 0)


def test_editing_rows_validates_and_recomputes():
    beam = items()[0]
    longer = worklist.edit(beam, 'length_mm', '12000')
    assert longer.unit_mass_kg == pytest.approx(268.8)
    assert worklist.edit(beam, 'count', '2').total_mass_kg == pytest.approx(268.8)
    assert worklist.edit(beam, 'price_per_kg', '').total_price is None
    assert worklist.edit(beam, 'name', ' Ana kiriş ').name == 'Ana kiriş'
    for field, value in (('count', '1,5'), ('count', '0'), ('length_mm', '-5'), ('price_per_kg', '-1'),
                         ('name', '  '), ('material', 'x')):
        with pytest.raises(ValueError):
            worklist.edit(beam, field, value)
    copy = worklist.Item.from_dict(beam.to_dict())
    assert copy == beam
    with pytest.raises(ValueError):
        worklist.Item.from_dict({'name': 'x'})


def test_csv_xlsx_and_pdf_exports_keep_numbers_and_totals(tmp_path, qapp):
    rows = items()
    path = export.export_csv(rows, tmp_path / 'liste.csv', 5, 20)
    lines = list(csv.reader(path.open(encoding='utf-8-sig'), delimiter=';'))
    assert lines[0] == list(export.COLUMNS)
    assert lines[1][0] == 'Kiriş' and lines[1][10] == '537,600' and lines[1][12] == '17472,00'
    assert any(line and line[0].startswith('Malzeme tutarı, KDV dahil') for line in lines)
    from openpyxl import load_workbook
    sheet = load_workbook(export.export_xlsx(rows, tmp_path / 'liste.xlsx', 5, 20)).active
    assert sheet['A2'].value == 'Kiriş' and sheet['K2'].value == pytest.approx(537.6)
    assert isinstance(sheet['I2'].value, float) and sheet['K2'].number_format == '#,##0.000'
    pdf = export.export_pdf(rows, tmp_path / 'liste.pdf', 5, 20, detail_rows=[('Kesit', 'IPE 200')])
    content = pdf.read_bytes()
    assert content.startswith(b'%PDF-') and len(content) > 2000
    assert not list(tmp_path.glob('.gokworks-weight-*'))   # temporary files removed


# ---- SOLIDWORKS mass (fake COM objects) -------------------------------------------------
class Fake:
    def __init__(self, **values):
        self.__dict__.update(values)


def model(doc_type=1, material='SOLIDWORKS Materials|AISI 304|41|', mass=7.9, volume=.001, recalc=True):
    properties = Fake(Recalculate=lambda: recalc, Volume=volume, Mass=mass, UseSystemUnits=False)
    return Fake(GetType=lambda: doc_type, GetTitle=lambda: 'FLANS.SLDPRT',
                ConfigurationManager=Fake(ActiveConfiguration=Fake(Name='Varsayılan')),
                Extension=Fake(CreateMassProperty2=lambda: properties), MaterialIdName=material,
                properties=properties)


def test_cad_part_mass_volume_material_and_density():
    part = model()
    value = cad.read(part)
    assert part.properties.UseSystemUnits is True
    assert value.kind == 'Parça' and value.material == 'AISI 304' and value.configuration == 'Varsayılan'
    assert value.mass_kg == 7.9 and value.volume_m3 == .001 and value.density_kg_m3 == pytest.approx(7900)
    assert cad.read_active(lambda: Fake(ActiveDoc=part)).mass_kg == 7.9


@pytest.mark.parametrize('doc,message', [(None, 'açık bir parça'), (model(doc_type=3), 'parça veya montaj değil'),
                                         (model(material=''), 'malzeme tanımlı değil'),
                                         (model(recalc=False), 'hesaplayamadı'),
                                         (model(volume=0), 'hacim sıfır')])
def test_cad_errors_are_meaningful(doc, message):
    with pytest.raises(RuntimeError, match=message):
        cad.read(doc)


def test_cad_assembly_reports_average_density():
    value = cad.read(model(doc_type=2, material=''))
    assert value.kind == 'Montaj' and any('ortalama' in note for note in value.notes)
