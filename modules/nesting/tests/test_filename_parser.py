"""Filename metadata is explicit, local, Unicode-safe and independent of CAD/Qt."""
import pytest

from modules.nesting.filename_parser import parse_filename


@pytest.mark.parametrize('token,value', [
    ('2mm',2),('2 mm',2),('1,2mm',1.2),('1,2 mm',1.2),('1.2mm',1.2),('1.2 mm',1.2),
    ('0,6 mm',.6),('0.6mm',.6),('T2',2),('T 2',2),('T2mm',2),('T 2mm',2),('T 2 mm',2),
    ('T=2mm',2),('T=2 mm',2),('T 1,5 mm',1.5),('T1.25',1.25),('THK2',2),
    ('THK 1,2 mm',1.2),('KALINLIK 0,8 mm',.8),('KALINLIK=3',3),('t_2_mm',2),
    ('T\t1,2\tMM',1.2),('T:2',2),
])
def test_thickness_rules(token,value):
    r=parse_filename(f'ŞASE_{token}_12AD.dxf')
    assert r.thickness == value and isinstance(r.thickness,float)
    assert r.quantity == 12 and r.status=='Algılandı'


@pytest.mark.parametrize('token', ['12AD','12 AD','12ADET','12 ADET','AD12','AD 12','ADET12',
    'ADET 12','ADET=12','QTY12','QTY 12','QTY=12','QUANTITY 12','A_12_AD','qty:12'])
def test_quantity_rules(token):
    r=parse_filename(f'PARÇA_T2_{token}.DXF')
    assert r.quantity==12 and type(r.quantity) is int and r.thickness==2


@pytest.mark.parametrize('name,t,q', [
    ('02BGL6199_T2_12AD.dxf',2,12),('GOVDE_1.5MM_8ADET.dxf',1.5,8),
    ('KAPAK_T0,6_QTY20.dxf',.6,20),('FLANS_3MM_AD5.dxf',3,5),('PROFIL_T1.25_ADET16.dxf',1.25,16),
    ('KAPAK_2mm_10ad.dxf',2,10),('GOVDE 1,2 mm 12 adet.dxf',1.2,12),('KAPAK T 2mm 5 adet.dxf',2,5),
    ('02BGL6199 T 1,5 mm 20 AD.dxf',1.5,20),('FLANS 0,8mm QTY 10.dxf',.8,10),
    ('YAN KAPAK T=3 mm AD 4.dxf',3,4),('GOVDE T 2 mm 12 AD.dxf',2,12),
    ('GOVDE_THK_1,5_MM_ADET_8.dxf',1.5,8),('02BGL6195.dxf',None,None),
    ('KAPAK_100x250_2ADET.dxf',None,2),('KAPAK_2MM_100x250.dxf',2,None),
    ('KAPAK_T2_3MM_10AD.dxf',None,10),('GOVDE-T2MM-QTY12.dxf',2,12),
    ('GOVDE  T  2  mm  12  adet.dxf',2,12),
])
def test_user_examples(name,t,q):
    result=parse_filename(name)
    assert (result.thickness,result.quantity)==(t,q)


@pytest.mark.parametrize('name', ['02BGL6199_500x300_REV2','KOD2026-10-30_REV02',
    'KAPAK_500x300mm','KAPAK_500 x 300 mm','KAPAK_500 mm x 300 mm','R20mm','Ø42mm','DELİK 6mm',
    'PARTT2','CODEQTY12','KAPAK_x12','KAPAK_12x','FİŞEK_123','M12_4xØ6mm'])
def test_codes_dimensions_dates_and_diameters_are_not_metadata(name):
    r=parse_filename(name+'.dxf')
    assert r.thickness is None and r.quantity is None and r.status=='Varsayılan değer'


@pytest.mark.parametrize('token,field', [('T0','thickness'),('T=-2','thickness'),
    ('T-2','thickness'),('THK -1,5','thickness'),('T=nan','thickness'),('THK=inf','thickness'),
    ('0mm','thickness'),('_-2mm','thickness'),('T1e999','thickness'),('AD0','quantity'),
    ('ADET=-3','quantity'),('QTY -3','quantity'),('1,2AD','quantity'),('AD1.5','quantity'),('QTY10001','quantity'),('AD1e2','quantity')])
def test_invalid_values_require_review(token,field):
    r=parse_filename('GÖVDE_'+token+'.dxf')
    assert getattr(r,field) is None and r.status=='Kontrol gerekli'


def test_conflicting_or_repeated_values_and_path_code():
    r=parse_filename(r'C:\T9_88AD\ŞASE_T2_2MM_10AD_QTY10.dxf')
    assert (r.filename,r.code,r.thickness,r.quantity)==('ŞASE_T2_2MM_10AD_QTY10.dxf','ŞASE',2,10)
    r=parse_filename('/T9/ŞASE_T2_3mm_10AD_QTY20.dxf')
    assert r.thickness is None and r.quantity is None and r.status=='Kontrol gerekli'
    assert r.thickness_issue and r.quantity_issue and r.rules
    assert parse_filename('PARÇA_T2_10000AD.dxf').quantity==10000
