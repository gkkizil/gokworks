"""Separate strict v1 mechanism schema; never silently changes gear_pair v1."""
from dataclasses import asdict,fields
from .models import MechanismSpecification
from .calculation import calculate
from ..models import LoadSpecification


def to_dict(spec):
    calculate(spec)
    return dict(schema='gokworks.gear_mechanism',version=1,units='mm',**asdict(spec))


def from_dict(data):
    keys={f.name for f in fields(MechanismSpecification)}
    if not isinstance(data,dict) or set(data)!=keys|{'schema','version','units'}:
        raise ValueError('Mekanizma sözleşmesinde eksik/bilinmeyen alan.')
    if data['schema']!='gokworks.gear_mechanism' or type(data['version']) is not int or data['version']!=1 or data['units']!='mm':
        raise ValueError('Mekanizma şeması/sürümü/birimi geçersiz.')
    values={k:data[k] for k in keys};load=values['load']
    if not isinstance(load,dict) or set(load)!={f.name for f in fields(LoadSpecification)}:
        raise ValueError('Yük sözleşmesi geçersiz.')
    values['load']=LoadSpecification(**load);spec=MechanismSpecification(**values);calculate(spec)
    return spec
