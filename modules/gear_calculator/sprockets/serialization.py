"""Strict independent gokworks.chain_sprocket v1; no migration of old gear schemas."""
from dataclasses import asdict,fields
from .models import ChainSpecification,SprocketSpecification,SprocketPairSpecification
from .calculation import calculate
from ..models import LoadSpecification


def construct(cls,data):
    if not isinstance(data,dict) or set(data)!={f.name for f in fields(cls)}:
        raise ValueError(f'{cls.__name__}: eksik/bilinmeyen alan.')
    return cls(**data)


def to_dict(s):
    calculate(s)
    return dict(schema='gokworks.chain_sprocket',version=1,units='mm',**asdict(s))


def from_dict(data):
    if not isinstance(data,dict) or set(data)!={f.name for f in fields(SprocketPairSpecification)}|{'schema','version','units'}:
        raise ValueError('Zincir dişlisi sözleşmesinde eksik/bilinmeyen alan.')
    if data['schema']!='gokworks.chain_sprocket' or type(data['version']) is not int or data['version']!=1 or data['units']!='mm':
        raise ValueError('Zincir dişlisi şeması/sürümü/birimi geçersiz.')
    values={f.name:data[f.name] for f in fields(SprocketPairSpecification)}
    for key in ('driver','driven'):
        if not isinstance(values[key],dict):raise ValueError('Zincir dişlisi nesne olmalı.')
        d=dict(values[key]);d['chain']=construct(ChainSpecification,d.get('chain'));values[key]=construct(SprocketSpecification,d)
    values['load']=construct(LoadSpecification,values['load'])
    s=SprocketPairSpecification(**values);calculate(s);return s
