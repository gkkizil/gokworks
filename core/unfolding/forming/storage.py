"""Source-bearing shop profiles, using the existing bounded JSON/atomic writer."""
import json
from .mechanics import normalize_options
from ..models import to_data
from ..storage import read_json,atomic_write

SCHEMA='gokworks.unfolding.forming'


def load_profile(path):
    data=read_json(path)
    if not isinstance(data,dict) or set(data)!={'schema','version','options'} or data['schema']!=SCHEMA or type(data['version']) is not int or data['version']!=1:
        raise ValueError('Şekillendirme profili şeması/sürümü geçersiz.')
    return normalize_options(data['options'])


def save_profile(options,path,*,overwrite=False):
    data=dict(schema=SCHEMA,version=1,options=to_data(normalize_options(options)))
    return atomic_write(path,lambda p:p.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8'),overwrite)
