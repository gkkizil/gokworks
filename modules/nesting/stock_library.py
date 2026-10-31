"""Shared sheet definitions in the existing atomic user-preference store.

Project files remain independent. Only explicit stock/material edits update
the library; loading a historical project never replaces it.
"""
from copy import deepcopy
from dataclasses import asdict

from .materials import new_project
from .models import Material,Project,Sheet,number


KEY = 'nesting_stock_library'
_MISSING = object()


def decode(value):
    try:
        if (not isinstance(value,dict) or type(value.get('version')) is not int or value['version']!=1
                or not isinstance(value.get('materials'),list) or not isinstance(value.get('sheets'),list)
                or len(value['materials'])>10000 or len(value['sheets'])>10000):
            raise ValueError('Stok kayıt biçimi geçersiz.')
        materials=[Material(**row) for row in value['materials']]
        sheets=[Sheet(**row) for row in value['sheets']]
        for material in materials:
            if not all(isinstance(v,str) and v for v in (material.id,material.name)) or not isinstance(material.source,str):
                raise ValueError('Malzeme adı/kimliği geçersiz.')
            material.density=number(material.density,'Yoğunluk',positive=True)
        for sheet in sheets:
            if not all(isinstance(v,str) and v for v in (sheet.id,sheet.name,sheet.material)):
                raise ValueError('Sac adı/kimliği geçersiz.')
            for key in ('width','height','thickness'):
                setattr(sheet,key,number(getattr(sheet,key),key,positive=True))
            for key in ('price_kg','price_sheet'):
                setattr(sheet,key,number(getattr(sheet,key),key))
        project=Project(materials=materials,sheets=sheets)
        project.validate(require_work=False)
        return project
    except (ValueError,TypeError,KeyError,AttributeError) as error:
        raise ValueError('Kalıcı sac stoğu okunamadı: '+str(error)) from error


class StockLibrary:
    def __init__(self,settings):self.settings=settings

    def read(self):
        value=self.settings.get(KEY,_MISSING)
        return None if value is _MISSING else decode(value)

    def new_project(self):
        project=new_project();saved=self.read()
        if saved is None:return project
        materials={m.id:m for m in saved.materials}
        defaults={m.id for m in project.materials}
        project.materials=[materials.get(m.id,m) for m in project.materials]
        project.materials.extend(m for m in saved.materials if m.id not in defaults)
        project.sheets=saved.sheets
        return project

    def remember(self,project,*,sheet=None,removed=None,material=None):
        saved=self.read()
        if saved is None:
            saved=Project(materials=deepcopy(project.materials),sheets=deepcopy(project.sheets))
        if removed is not None:saved.sheets=[s for s in saved.sheets if s.id!=removed]
        if sheet is not None:
            for index,item in enumerate(saved.sheets):
                if item.id==sheet.id:saved.sheets[index]=deepcopy(sheet);break
            else:saved.sheets.append(deepcopy(sheet))
            material=project.material(sheet.material)
        if material is not None:
            for index,item in enumerate(saved.materials):
                if item.id==material.id:saved.materials[index]=deepcopy(material);break
            else:saved.materials.append(deepcopy(material))
        payload=dict(version=1,materials=[asdict(m) for m in saved.materials],sheets=[asdict(s) for s in saved.sheets])
        decode(payload)  # Validate before replacing even the in-memory setting.
        self.settings.set(KEY,payload)
        if not self.settings.flush():
            raise OSError(self.settings.last_error or 'Ayar dosyası kaydedilemedi.')
