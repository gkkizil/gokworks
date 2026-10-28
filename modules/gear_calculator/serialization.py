"""Strict versioned plain-data contract, shared by the UI and isolated CAD worker."""

from dataclasses import asdict, fields
from .models import GearSpecification, GearPairSpecification, LoadSpecification, FutureGearData
from .calculation import calculate_pair


def to_dict(spec):
    from .sprockets.models import SprocketPairSpecification
    if isinstance(spec,SprocketPairSpecification):
        from .sprockets.serialization import to_dict as sprocket_to_dict
        return sprocket_to_dict(spec)
    from .families.models import MechanismSpecification
    if isinstance(spec,MechanismSpecification):
        from .families.serialization import to_dict as mechanism_to_dict
        return mechanism_to_dict(spec)
    calculate_pair(spec)
    return dict(schema='gokworks.gear_pair',version=1,units='mm',**asdict(spec))


def _construct(cls,value):
    if not isinstance(value,dict) or set(value)!={f.name for f in fields(cls)}:
        raise ValueError(f'{cls.__name__}: eksik veya bilinmeyen veri alanı.')
    return cls(**value)


def from_dict(value):
    if isinstance(value,dict) and value.get('schema')=='gokworks.chain_sprocket':
        from .sprockets.serialization import from_dict as sprocket_from_dict
        return sprocket_from_dict(value)
    if isinstance(value,dict) and value.get('schema')=='gokworks.gear_mechanism':
        from .families.serialization import from_dict as mechanism_from_dict
        return mechanism_from_dict(value)
    if not isinstance(value,dict) or set(value)!={'schema','version','units','pinion','wheel','load'}:
        raise ValueError('Dişli çifti veri alanları geçersiz.')
    if value['schema']!='gokworks.gear_pair' or type(value['version']) is not int or value['version']!=1 or value['units']!='mm':
        raise ValueError('Desteklenmeyen dişli çifti şeması/birimi.')
    gears=[]
    for name in ('pinion','wheel'):
        if not isinstance(value[name],dict):
            raise ValueError('Dişli alanı nesne olmalı.')
        gear=dict(value[name]);gear['future']=_construct(FutureGearData,gear.get('future'))
        gears.append(_construct(GearSpecification,gear))
    spec=GearPairSpecification(*gears,_construct(LoadSpecification,value['load']))
    calculate_pair(spec)
    return spec
