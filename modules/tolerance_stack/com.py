"""Explicit IDispatch contracts; no MakePy, type-info generation or global COM objects."""

from contextlib import contextmanager
from types import SimpleNamespace


MISSING={-2147352573,-2147352570}
DRAWING_IID='{83A33D33-27C5-11CE-BFD4-00400513BB57}'
MODEL_IID='{B90793FB-EF3D-4B80-A5C4-99959CDB6CEB}'
DRAWING_MEMBERS={'GetViews','GetSheetNames','Sheet','GetCurrentSheet','ActivateSheet','NewSheet3','NewSheet4'}


class DrawingDocument:
    """Route ModelDoc2 and DrawingDoc members to their actual dual interfaces."""
    def __init__(self,model):
        import pythoncom
        dispatch=raw(model)
        self._oleobj_=dispatch.QueryInterface(pythoncom.MakeIID(MODEL_IID),pythoncom.IID_IDispatch)
        self.drawing=dispatch.QueryInterface(pythoncom.MakeIID(DRAWING_IID),pythoncom.IID_IDispatch)


def raw(obj):
    value=getattr(obj,'_oleobj_',obj)
    return value if hasattr(value,'Invoke') and hasattr(value,'GetIDsOfNames') else None


def invoke(obj,name,flags,*args):
    try:
        dispatch=obj.drawing if isinstance(obj,DrawingDocument) and name in DRAWING_MEMBERS else raw(obj)
        if dispatch is not None:
            member=dispatch.GetIDsOfNames(0,name)
            values=tuple(raw(arg) if raw(arg) is not None else arg for arg in args)
            return dispatch.Invoke(member,0,flags,flags!=4,*values)
        value=getattr(obj,name)
        return value(*args) if flags==1 and callable(value) and raw(value) is None else value
    except Exception as error:
        raise RuntimeError(f'SolidWorks API · {name}: {error}') from error


def call(obj,name,*args): return invoke(obj,name,1,*args)
def get(obj,name): return invoke(obj,name,2)
def put(obj,name,value):
    dispatch=raw(obj)
    if dispatch is not None: return invoke(obj,name,4,value)
    setattr(obj,name,value)


def optional(obj,name,*args,property=False,default=None):
    try: return get(obj,name) if property else call(obj,name,*args)
    except RuntimeError as error:
        cause=error.__cause__
        if isinstance(cause,AttributeError) or getattr(cause,'hresult',None) in MISSING: return default
        raise


def variant(kind,value):
    try:
        from win32com.client import VARIANT
        return VARIANT(kind,value)
    except ImportError:
        return SimpleNamespace(varianttype=kind,value=value)


def out_int(): return variant(0x4003,0)
def null_dispatch(): return variant(9,None)
def config_array(configuration): return variant(0x2008,(configuration,)) if configuration else variant(0,None)


def tolerance_value(tolerance,member):
    # Int32 swDimensionToleranceWarning_e and one [out] double, not an HRESULT
    # or the tolerance itself. 1 means this bound is not valid for this type.
    output=variant(0x4005,float('nan'))
    status=call(tolerance,member,output)
    if isinstance(status,(tuple,list)):
        if len(status)!=2: raise RuntimeError('Tolerans API çıktı yapısı geçersiz.')
        status,output.value=status
    if status==1:
        bound='Alt' if member=='GetMinValue2' else 'Üst'
        raise RuntimeError(f'{bound} tolerans bu tolerans türü için tanımlı değil (API kodu: 1). '
                           'Analiz için gerekli toleransı çizimden doğrulayıp manuel tamamlayın.')
    if status!=0:
        raise RuntimeError(f'Tolerans değeri okunamadı; API hata kodu: {status}.')
    return output.value


def path_key(path): return str(path).replace('\\','/').rstrip('/').casefold()


def drawing(model,path=None):
    if model is None or call(model,'GetType')!=3:
        raise ValueError('SolidWorks’te bir .SLDDRW teknik resmi açın veya dosya seçin.')
    if path and path_key(call(model,'GetPathName'))!=path_key(path):
        raise RuntimeError('SolidWorks istenen teknik resim yerine farklı belge döndürdü.')
    if not isinstance(model,DrawingDocument) and raw(model) is not None and hasattr(raw(model),'QueryInterface'):
        try:return DrawingDocument(model)
        except Exception as error:raise RuntimeError('IDrawingDoc / IModelDoc2 COM arayüzüne erişilemiyor; teknik resim okunamadı.') from error
    return model


class Session:
    def __enter__(self):
        try:
            import pythoncom
        except ImportError as error:
            raise RuntimeError('SolidWorks işlemleri Windows ve pywin32 gerektirir. Manuel analiz çevrimdışı çalışır.') from error
        pythoncom.CoInitialize()
        self.pythoncom=pythoncom
        self.opened=[];self.previous=''
        try:
            from solidworks.connection import connect_to_solidworks
            self.app=connect_to_solidworks(raw=True)
            active=get(self.app,'ActiveDoc')
            if active is not None: self.previous=call(active,'GetPathName') or call(active,'GetTitle')
            return self
        except Exception:
            pythoncom.CoUninitialize();raise

    def document(self,path=None,*,readonly=True):
        if path is None: return drawing(get(self.app,'ActiveDoc'))
        if not str(path).casefold().endswith('.slddrw'):
            raise ValueError('Yalnız .SLDDRW teknik resimleri seçilebilir.')
        for owned in self.opened:
            if path_key(call(owned,'GetPathName'))==path_key(path):return owned
        model=call(self.app,'GetOpenDocumentByName',str(path))
        opened_here=False
        if model is None:
            errors,warnings=out_int(),out_int()
            model=call(self.app,'OpenDoc6',str(path),3,3 if readonly else 1,'',errors,warnings)
            if model is not None and not warnings.value & 128:self.opened.append(model);opened_here=True
            if model is None or errors.value: raise RuntimeError(f'Teknik resim açılamadı; API kodu: {errors.value}.')
        model=drawing(model,path)
        if opened_here:self.opened[-1]=model
        return model

    def activate(self,model):
        errors=out_int()
        active=call(self.app,'ActivateDoc3',call(model,'GetPathName') or call(model,'GetTitle'),False,2,errors)
        if active is None or errors.value: raise RuntimeError('Teknik resim etkinleştirilemedi.')

    def keep(self,model):
        self.opened=[item for item in self.opened if item is not model]

    def close_owned(self,model):
        if not any(item is model for item in self.opened):
            raise RuntimeError('Kullanıcının açık belgesi araç tarafından kapatılamaz.')
        call(self.app,'CloseDoc',call(model,'GetTitle'))
        self.keep(model)

    def __exit__(self,kind,error,tb):
        failures=[]
        try:
            for model in reversed(self.opened):
                try: call(self.app,'CloseDoc',call(model,'GetTitle'))
                except Exception: failures.append('Araç tarafından açılan çizim kapatılamadı.')
            if self.previous:
                try:
                    errors=out_int();restored=call(self.app,'ActivateDoc3',self.previous,False,2,errors)
                    if restored is None or errors.value: failures.append('Önceki aktif belge geri getirilemedi.')
                except Exception: failures.append('Önceki aktif belge geri getirilemedi.')
        finally: self.pythoncom.CoUninitialize()
        if failures and error is None: raise RuntimeError(' '.join(failures))


@contextmanager
def preserve_selection(model):
    manager=get(model,'SelectionManager')
    call(manager,'SuspendSelectionList')
    try:
        call(model,'ClearSelection2',True)
        yield
    finally: call(manager,'ResumeSelectionList2',False)
