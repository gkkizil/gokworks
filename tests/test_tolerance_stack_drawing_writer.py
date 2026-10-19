"""Controlled CAD transaction doubles. These are not live SolidWorks tests."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import threading

import pytest

from test_tolerance_stack_com import Drawing,View,Display,Sheet,Annotation
from tolerance_stack import com,storage,solidworks_reader as reader,drawing_writer as writer
from tolerance_stack.models import Project,Term
from tolerance_stack.calculator import calculate,Cancelled


class NoteAnnotation(Annotation):
    def __init__(self,model,note):super().__init__(note.text);self.model=model;self.note=note;self.position=None
    def Select3(self,append,data):
        assert data.varianttype==9 and data.value is None
        self.model.selected=[self];return True
    def SetPosition2(self,x,y,z):self.position=(x,y,z);return True
    def GetTextFormat(self,index):return NS(CharHeight=.004)
    def SetTextFormat(self,index,use_document,format):return format.CharHeight==.0025


class Note:
    def __init__(self,model,text):self.text=text;self.annotation=NoteAnnotation(model,self)
    def GetText(self):return self.text
    def GetAnnotation(self):return self.annotation


class Extension:
    def __init__(self,model):self.model=model
    def GetPersistReference3(self,obj):return obj.GetName().encode()
    def DeleteSelection2(self,options):
        selected=self.model.selected
        if len(selected)!=1:raise AssertionError('Deletion must select only the created object')
        item=selected[0]
        if isinstance(item,NoteAnnotation):self.model.notes.remove(item.note)
        elif isinstance(item,tuple) and item[0]=='sheet':self.model.groups=[g for g in self.model.groups if g[0].Sheet.GetName()!=item[1]]
        else:raise AssertionError('Production annotation selected for deletion')
        self.model.selected=[];return True
    def SelectByID2(self,name,kind,*args):
        assert kind=='SHEET' and name.startswith('GOKWORKS-')
        self.model.selected=[('sheet',name)];return True
    def SaveAs(self,path,version,options,export_data,errors,warnings):
        assert options==3 and export_data.varianttype==9 and export_data.value is None
        Path(path).write_bytes(Path(self.model.path).read_bytes())
        copy=NativeDrawing(path,self.model.session)
        copy.references=list(self.model.references);copy.save_fail=self.model.copy_save_fail
        copy.reference_fail=self.model.reference_fail
        if copy.reference_fail:copy.references=['Part','C:/unexpected/Other.SLDPRT']
        self.model.session.copies[path]=copy
        self.model.save_as_options.append(options);return True


class NativeDrawing(Drawing):
    def __init__(self,path,session=None):
        super().__init__(path);self.notes=[];self.current='Sheet1';self.selected=['USER_SELECTION']
        self.saved_selection=None;self.session=session;self.Extension=Extension(self)
        self.references=['Part','C:/parts/Part.SLDPRT'];self.save_calls=0;self.save_fail=False
        self.copy_save_fail=False;self.reference_fail=False;self.insert_fail=False;self.save_as_options=[]
        self.SelectionManager=NS(SuspendSelectionList=self.suspend,ResumeSelectionList2=self.resume)
        self.groups[0][0].GetNotes=lambda:self.notes
    def suspend(self):self.saved_selection=self.selected[:];self.selected=[];return len(self.saved_selection)
    def resume(self,append):self.selected=self.saved_selection;self.saved_selection=None
    def ClearSelection2(self,all):self.selected=[]
    def GetCurrentSheet(self):return Sheet(self.current)
    def ActivateSheet(self,name):
        if name not in [group[0].Sheet.GetName() for group in self.groups]:return False
        self.current=name;return True
    def NewSheet3(self,name,paper,template,*args):
        assert paper==12 and template==13
        self.groups.append([View(name,name,[])]);self.current=name;self.dirty=True;return True
    def InsertNote(self,text):
        if self.insert_fail:return None
        note=Note(self,text);self.notes.append(note);self.dirty=True;return note
    def GetDependencies2(self,traverse,search,readonly):return tuple(self.references)
    def Save3(self,options,errors,warnings):
        assert options==1
        self.save_calls+=1
        Path(self.path).write_bytes(b'CAD WITH ANALYSIS '+str(len(self.notes)).encode())
        if self.save_fail:errors.value=32;return False
        self.dirty=False;return True


class Session:
    def __init__(self):self.copies={};self.closed=[];self.kept=[];self.original=None;self.activated=[]
    def __enter__(self):return self
    def __exit__(self,*args):self.closed.extend(copy for copy in self.copies.values() if copy not in self.closed and copy not in self.kept)
    def document(self,path=None,**kwargs):
        return self.original if str(path)==self.original.path else self.copies[str(path)]
    def activate(self,model):self.activated.append(model.path)
    def keep(self,model):self.kept.append(model)
    def close_owned(self,model):
        assert model is not self.original;self.closed.append(model)


@pytest.fixture
def setup(tmp_path):
    path=tmp_path/'Original.SLDDRW';path.write_bytes(b'ORIGINAL PRODUCTION DRAWING')
    session=Session();model=NativeDrawing(path,session);session.original=model
    dims,source=reader.read_document(model)
    p=Project(dimensions=dims,sources=[source],end='P1',method='worst_case',
              terms=[Term(dims[0].id,start='P0',end='P1',datum='A',relation='Görünüm X → montaj X; A')])
    p.confirm();result=calculate(p)
    with patch.object(com,'Session',return_value=session),patch.object(writer,'verify_live'):
        yield model,session,p,result


def test_memory_annotation_is_additive_preserves_production_values_selection_and_disk(setup):
    model,session,p,result=setup;before=Path(model.path).read_bytes()
    original=reader.read_document(model)[0]
    output=writer.write_drawing(p,result,model.path,mode='memory',labels=True)
    assert output['saved'] is False and Path(model.path).read_bytes()==before
    assert model.save_calls==0 and model.selected==['USER_SELECTION'] and model.current=='Sheet1'
    assert len(model.notes)>=2 and any('TOLERANCE STACK-UP ANALYSIS' in n.text for n in model.notes)
    assert any('L1' in n.text for n in model.notes)
    assert [d.original_signature for d in reader.read_document(model)[0]]==[d.original_signature for d in original]
    assert model in session.kept


def test_copy_verifies_references_closes_only_copy_and_atomically_publishes(setup,tmp_path):
    model,session,p,result=setup;source=Path(model.path).read_bytes();target=tmp_path/'New analysis.SLDDRW'
    output=writer.write_drawing(p,result,model.path,mode='copy',destination=target,labels=True)
    assert target.read_bytes().startswith(b'CAD WITH ANALYSIS') and output['saved']
    assert Path(model.path).read_bytes()==source and model.notes==[] and not model.dirty
    assert model.save_calls==0 and model.save_as_options==[3]
    assert len(session.closed)==1 and session.closed[0] is not model
    assert not list(tmp_path.glob('.gokworks-stack-*'))


@pytest.mark.parametrize('failure',['save','references'])
def test_failed_copy_does_not_publish_or_touch_source(setup,tmp_path,failure):
    model,session,p,result=setup;before=Path(model.path).read_bytes()
    if failure=='save':model.copy_save_fail=True
    else:model.reference_fail=True
    target=tmp_path/'failed.SLDDRW'
    with pytest.raises(RuntimeError):writer.write_drawing(p,result,model.path,mode='copy',destination=target)
    assert not target.exists() and Path(model.path).read_bytes()==before and model.notes==[]
    assert model not in session.closed
    assert not list(tmp_path.glob('.gokworks-stack-*'))


def test_source_save_requires_explicit_approval_and_verified_backup(setup):
    model,session,p,result=setup;before=Path(model.path).read_bytes()
    with pytest.raises(PermissionError):writer.write_drawing(p,result,model.path,mode='source')
    assert model.notes==[] and model.save_calls==0
    output=writer.write_drawing(p,result,model.path,mode='source',approved=True)
    assert output['saved'] and Path(output['backup']).read_bytes()==before
    assert Path(model.path).read_bytes()!=before and model.save_calls==1


def test_source_save_failure_restores_backup_and_original_production_drawing(setup):
    model,session,p,result=setup;before=Path(model.path).read_bytes();model.save_fail=True
    with pytest.raises(RuntimeError,match='yedekten geri getirildi'):
        writer.write_drawing(p,result,model.path,mode='source',approved=True)
    assert Path(model.path).read_bytes()==before and model.notes==[]
    assert model.selected==['USER_SELECTION']
    assert list(Path(model.path).parent.glob('.gokworks-backups/*.SLDDRW'))


def test_insert_failure_and_cancel_leave_no_partial_annotations(setup):
    model,session,p,result=setup;model.insert_fail=True
    with pytest.raises(RuntimeError,match='notunu oluşturmadı'):writer.write_drawing(p,result,model.path)
    assert model.notes==[] and len(model.groups)==1 and model.selected==['USER_SELECTION']
    stop=threading.Event();stop.set()
    with pytest.raises(Cancelled):writer.write_drawing(p,result,model.path,stop=stop)
    assert model.notes==[]


def test_copy_cannot_replace_source_and_source_save_rejects_user_unsaved_edits(setup):
    model,session,p,result=setup
    with pytest.raises(ValueError,match='üzerine yazılamaz'):
        writer.write_drawing(p,result,model.path,mode='copy',destination=model.path)
    model.dirty=True
    with pytest.raises(ValueError,match='kaydedilmemiş'):
        writer.write_drawing(p,result,model.path,mode='source',approved=True)
    assert model.notes==[] and not list(Path(model.path).parent.glob('.gokworks-backups/*'))
