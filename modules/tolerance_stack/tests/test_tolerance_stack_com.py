from dataclasses import replace
from decimal import Decimal as D
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest

from modules.tolerance_stack import com,solidworks_reader as reader,storage
from modules.tolerance_stack.models import Project,Term


class Annotation:
    def __init__(self,name):self.name=name
    def GetPosition(self):return (.1,.15,0.)
    def GetName(self):return self.name


class Tolerance:
    def __init__(self,kind=4,lower=-.0001,upper=.0001,status=0,hole='',shaft=''):
        self.Type=kind;self.lower=lower;self.upper=upper;self.status=status;self.hole=hole;self.shaft=shaft
    def GetMinValue2(self,output):
        assert output.varianttype==0x4005
        output.value=self.lower;return self.status
    def GetMaxValue2(self,output):
        assert output.varianttype==0x4005
        output.value=self.upper;return self.status
    def GetHoleFitValue(self):return self.hole
    def GetShaftFitValue(self):return self.shaft


class Dimension:
    def __init__(self,name='D1@Sketch@Part.SLDPRT',value=.05,tolerance=None):
        self.FullName=name;self.value=value;self.Tolerance=tolerance or Tolerance();self.config_calls=[]
    def GetSystemValue3(self,which,names):
        self.config_calls.append((which,names.varianttype,names.value))
        return (self.value,)


class Display:
    def __init__(self,dimension=None,kind=2,reference=False):
        self.dimension=dimension or Dimension();self.Type2=kind;self.next=None;self.reference=reference
        self.annotation=Annotation(self.dimension.FullName)
    def GetDimension2(self,index):assert index==0;return self.dimension
    def GetAnnotation(self):return self.annotation
    def GetNext5(self):return self.next
    def IsReferenceDim(self):return self.reference
    def GetText(self,index):assert index==0;return '50 ±0,1'
    def GetOverride(self):return False


class Sheet:
    def __init__(self,name):self.name=name
    def GetName(self):return self.name


class View:
    def __init__(self,name,sheet,displays,notes=()):
        self.name=name;self.Sheet=Sheet(sheet);self.ReferencedConfiguration='Default'
        self.displays=displays;self.notes=notes
        for a,b in zip(displays,displays[1:]):a.next=b
    def GetName2(self):return self.name
    def GetFirstDisplayDimension5(self):return self.displays[0] if self.displays else None
    def GetReferencedModelName(self):return 'C:/parts/Part.SLDPRT'
    def GetNotes(self):return [NS(GetText=lambda text=text:text) for text in self.notes]
    def GetGTols(self):return ()


class Drawing:
    def __init__(self,path,groups=None):
        self.path=str(path);self.groups=groups or [[View('Front','Sheet1',[Display()])]]
        self.Extension=NS(GetPersistReference3=lambda obj:obj.GetName().encode())
        self.dirty=False
    def GetType(self):return 3
    def GetPathName(self):return self.path
    def GetTitle(self):return self.path.replace('\\','/').split('/')[-1]
    def GetSaveFlag(self):return self.dirty
    def GetViews(self):return self.groups
    def GetUserUnit(self,kind):return NS(GetConversionFactor=lambda:57.29577951308232 if kind else 1000.)


@pytest.fixture
def drawing(tmp_path):
    source=tmp_path/'İmalat.SLDDRW';source.write_bytes(b'Native drawing double')
    return Drawing(source)


def test_all_sheets_views_nominal_tolerances_identity_position_and_configuration(drawing):
    drawing.groups.append([View('Top','Sheet2',[Display(Dimension('D2',.02))])])
    dims,source=reader.read_document(drawing)
    assert len(dims)==2 and {d.sheet for d in dims}=={'Sheet1','Sheet2'}
    first=dims[0]
    assert (first.nominal,first.lower,first.upper)==(D(50),D('-.1'),D('.1'))
    assert first.position==(100.,150.,0.) and first.persistent_ref
    assert first.configuration=='Default' and first.source==drawing.path and first.original_signature
    assert drawing.groups[0][0].displays[0].dimension.config_calls==[(3,0x2008,('Default',))]
    assert source.sha256==storage.fingerprint(drawing.path).sha256
    assert drawing.dirty is False


@pytest.mark.parametrize('kind,status,notes,expected',[(0,0,('ISO 2768-m',),False),(4,2,(),False),
    (11,0,(),False),(11,0,('GENEL TOLERANSLAR: ±0,1 mm',),True),(1,0,(),False),
    (2,0,(),True),(3,0,(),True),(5,0,(),False),(6,0,(),False)])
def test_no_invented_tolerance_or_status_as_value(drawing,kind,status,notes,expected):
    drawing.groups[0][0].notes=notes
    drawing.groups[0][0].displays[0].dimension.Tolerance=Tolerance(kind,status=status)
    dims,_=reader.read_document(drawing);d=dims[0]
    assert (d.lower is not None and d.upper is not None)==expected
    if status==2:assert 'API hata kodu: 2' in d.note
    if kind==1:assert d.kind=='basic'


def test_asymmetric_and_reference_angular_and_diameter_classification(drawing):
    displays=[Display(Dimension('Asymmetric',.05,Tolerance(2,-.0001,.00005))),
              Display(Dimension('Angle',.5),kind=3),Display(Dimension('Reference',.03),reference=True),
              Display(Dimension('Diameter',.025),kind=6)]
    drawing.groups=[[View('Front','Sheet1',displays)]]
    dims,_=reader.read_document(drawing)
    assert (dims[0].lower,dims[0].upper)==(D('-.1'),D('.05'))
    assert dims[1].nominal==D('.5') and dims[1].display_unit=='rad'
    assert [d.kind for d in dims]==['linear','angle','reference','diameter']


def test_drawing_reference_uses_drawing_context_and_only_valid_symmetric_bound(drawing):
    class ReferenceDimension(Dimension):
        def GetSystemValue3(self,which,names):
            self.config_calls.append((which,names.varianttype,names.value))
            if which!=1 or names.varianttype!=0:
                raise RuntimeError('Reference dimension is not a part configuration parameter')
            return (self.value,)
    class Symmetric(Tolerance):
        def GetMinValue2(self,output):
            raise AssertionError('Symmetric tolerance has no independent lower deviation')
    dimension=ReferenceDimension(tolerance=Symmetric())
    drawing.groups[0][0].displays=[Display(dimension,reference=True)]
    dimensions,_=reader.read_document(drawing)
    d=dimensions[0]
    assert (d.nominal,d.lower,d.upper)==(D(50),D('-.1'),D('.1'))
    assert (d.kind,d.geometry_kind,d.configuration)==('reference','linear','Default')
    assert dimension.config_calls==[(1,0,None)]
    assert 'Nominal ölçü okunamadı' not in d.note and 'API kodu' not in d.note


def test_named_configuration_accepts_documented_single_bstr_without_active_fallback(drawing):
    class SingleString(Dimension):
        def GetSystemValue3(self,which,names):
            assert which==3
            if not isinstance(names,str):raise RuntimeError('Array rejected by OLE server')
            assert names=='Default'
            return (self.value,)
    drawing.groups[0][0].displays=[Display(SingleString())]
    dims,_=reader.read_document(drawing)
    assert dims[0].nominal==50


def test_failed_named_configuration_never_substitutes_active_model_value(drawing):
    class Unavailable(Dimension):
        def GetSystemValue3(self,which,names):
            assert which==3
            raise RuntimeError('Requested configuration unavailable')
        def GetSystemValue2(self,name):
            assert name=='Default'
            raise RuntimeError('Requested configuration unavailable')
        @property
        def SystemValue(self):raise AssertionError('Active model configuration must not be substituted')
    drawing.groups[0][0].displays=[Display(Unavailable())]
    dims,_=reader.read_document(drawing)
    assert dims[0].nominal is None and 'Nominal ölçü okunamadı' in dims[0].note
    assert dims[0].upper==D('.1')  # Nominal failure does not erase independent valid tolerance data.


def test_missing_full_name_does_not_erase_valid_nominal_or_annotation_identity(drawing):
    display=drawing.groups[0][0].displays[0]
    display.dimension=NS(GetSystemValue3=lambda *args:(.05,),Tolerance=Tolerance())
    dims,_=reader.read_document(drawing)
    assert dims[0].nominal==50 and dims[0].api_name==''
    assert dims[0].name==display.annotation.name and 'API ölçü adı okunamadı' in dims[0].note


def test_reference_system_value_compatibility_fallback_keeps_units_and_angular_kind(drawing):
    dimension=NS(FullName='Reference angle',Tolerance=Tolerance(),SystemValue=.5)
    display=drawing.groups[0][0].displays[0]
    display.dimension=dimension;display.reference=True;display.Type2=3
    dims,_=reader.read_document(drawing)
    assert dims[0].nominal==D('.5') and dims[0].display_unit=='rad'
    assert dims[0].kind=='reference' and dims[0].geometry_kind=='angle'


@pytest.mark.parametrize('value,expected',[(.05,D(50)),((.05,.06),None),(float('nan'),None),(True,None)])
def test_nominal_single_value_validation_does_not_pick_an_arbitrary_configuration(drawing,value,expected):
    dimension=drawing.groups[0][0].displays[0].dimension
    dimension.GetSystemValue3=lambda *args:value
    dims,_=reader.read_document(drawing)
    assert dims[0].nominal==expected


def test_warning_one_leaves_unknown_tolerance_and_its_output_is_never_a_limit(drawing):
    drawing.groups[0][0].displays[0].dimension.Tolerance=Tolerance(kind=2,status=1,lower=42,upper=42)
    dims,_=reader.read_document(drawing)
    assert dims[0].nominal==50 and dims[0].lower is None and dims[0].upper is None
    assert 'bu tolerans türü için tanımlı değil' in dims[0].note and 'API kodu: 1' in dims[0].note


def test_iso_api_values_match_verified_table_and_combined_callout_is_not_collapsed(drawing):
    from modules.iso_fits.rules import limits
    band=limits(50,'H7','hole')
    display=drawing.groups[0][0].displays[0];display.Type2=6
    display.dimension.Tolerance=Tolerance(7,float(band.lower_nm)/1e9,float(band.upper_nm)/1e9,hole='H7')
    dims,_=reader.read_document(drawing)
    assert dims[0].upper==D('.025') and 'H7' in dims[0].tolerance_type
    display.dimension.Tolerance.shaft='h6'
    dims,_=reader.read_document(drawing)
    assert dims[0].upper is None and 'çift gösterimi' in dims[0].note


def test_deleted_or_unsaved_changed_source_dimension_is_detected(drawing):
    dims,source=reader.read_document(drawing)
    p=Project(dimensions=dims,sources=[source],terms=[Term(dims[0].id,start='P0',end='P1',datum='A',relation='Kaynak görünüm X → montaj X; datum A')],end='P1',method='worst_case')
    p.confirm()
    with patch.object(reader,'read_sources',return_value=(dims,[source])):reader.verify_live(p)
    changed=replace(dims[0],nominal=D(51),original_signature='changed')
    with patch.object(reader,'read_sources',return_value=([changed],[source])):
        with pytest.raises(ValueError,match='değişmiş/silinmiş'):reader.verify_live(p)
    with patch.object(reader,'read_sources',return_value=([],[source])):
        with pytest.raises(ValueError,match='değişmiş/silinmiş'):reader.verify_live(p)


def test_native_idispatch_uses_exact_byref_double_contract_and_does_not_query_type_info():
    calls=[]
    class Raw:
        def GetIDsOfNames(self,lcid,name):return name
        def Invoke(self,member,lcid,flags,result,*args):
            calls.append((member,flags,result));assert flags==1 and args[0].varianttype==0x4005
            args[0].value=-.0001;return 0
        def GetTypeInfo(self,*args):raise AssertionError('TypeInfo must not be queried')
    value=com.tolerance_value(NS(_oleobj_=Raw()),'GetMinValue2')
    assert value==-.0001 and calls==[('GetMinValue2',1,True)]


def test_session_coinitializes_on_worker_and_never_closes_user_owned_document(drawing):
    import sys
    calls=[]
    pythoncom=NS(CoInitialize=lambda:calls.append('init'),CoUninitialize=lambda:calls.append('uninit'))
    app=NS(ActiveDoc=drawing,GetOpenDocumentByName=lambda path:drawing,
           ActivateDoc3=lambda *args:drawing,CloseDoc=lambda name:calls.append('close'))
    with patch.dict(sys.modules,{'pythoncom':pythoncom}),patch('solidworks.connection.connect_to_solidworks',return_value=app):
        with com.Session() as session:assert session.document(drawing.path) is drawing
    assert calls==['init','uninit']


def test_session_uses_real_connection_path_without_type_wrapping_or_progid_helper(drawing):
    import sys
    calls=[]
    class Active:
        def QueryInterface(self,iid):
            calls.append(('query',iid));return self
        def GetIDsOfNames(self,lcid,name):return name
        def Invoke(self,member,lcid,flags,result,*args):
            calls.append((member,flags))
            if member=='ActiveDoc':return drawing
            if member=='ActivateDoc3':return drawing
            raise AssertionError(member)
        def GetTypeInfo(self,*args):raise AssertionError('Type information must not be requested')
    active=Active()
    pythoncom=NS(CoInitialize=lambda:calls.append('init'),CoUninitialize=lambda:calls.append('uninit'),
                 IID_IDispatch='IDispatch',
                 GetActiveObject=lambda name:calls.append(('existing',name)) or active)
    with patch.dict(sys.modules,{'pythoncom':pythoncom}):
        with com.Session() as session:
            assert session.document() is drawing
    assert calls==['init',('existing','SldWorks.Application'),('query','IDispatch'),
                   ('ActiveDoc',2),('ActiveDoc',2),('ActivateDoc3',1),'uninit']


def test_session_connection_failure_releases_com_apartment():
    import sys
    calls=[]
    def unavailable(name):
        calls.append(('existing',name))
        raise RuntimeError('Running CAD session unavailable')
    pythoncom=NS(CoInitialize=lambda:calls.append('init'),CoUninitialize=lambda:calls.append('uninit'),
                 GetActiveObject=unavailable)
    with patch.dict(sys.modules,{'pythoncom':pythoncom}):
        with pytest.raises(RuntimeError,match='Running CAD session unavailable'):
            with com.Session():raise AssertionError('Unavailable session must not be entered')
    assert calls==['init',('existing','SldWorks.Application'),'uninit']


def test_drawing_and_model_use_their_published_com_iids_without_makepy(drawing):
    import sys
    calls=[]
    class Raw:
        def __init__(self,interface='model'):self.interface=interface
        def GetIDsOfNames(self,lcid,name):
            if name in com.DRAWING_MEMBERS and self.interface!='drawing':raise AttributeError(name)
            return name
        def Invoke(self,member,lcid,flags,result,*args):
            calls.append((self.interface,member,flags))
            value=getattr(drawing,member)
            return value(*args) if flags==1 else value
        def QueryInterface(self,iid,wrapper):
            calls.append(('QI',iid,wrapper));return Raw('drawing' if iid==com.DRAWING_IID else 'model')
        def GetTypeInfo(self):raise AssertionError('Type info generation is forbidden')
    pythoncom=NS(MakeIID=lambda x:x,IID_IDispatch='IDispatch')
    with patch.dict(sys.modules,{'pythoncom':pythoncom}):
        wrapper=com.drawing(NS(_oleobj_=Raw()))
        assert com.call(wrapper,'GetViews')==drawing.groups
        assert com.call(wrapper,'GetPathName')==drawing.path
    assert ('QI',com.DRAWING_IID,'IDispatch') in calls
    assert ('drawing','GetViews',1) in calls and ('model','GetPathName',1) in calls
