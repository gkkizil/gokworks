"""Per-source import drafts, independent of widgets and DXF geometry reading."""

from copy import deepcopy
from dataclasses import dataclass, field

from .filename_parser import FilenameInfo, parse_filename
from .models import integer, number


DEFAULT_OPTIONS = dict(material='S235JR', thickness=2., quantity=1, unit=None,
                       tolerance=.02, join_tolerance=.001, excluded_layers=[], grouped=False)


def normalize_options(options):
    result = deepcopy(DEFAULT_OPTIONS)
    if set(options) - set(result):
        raise ValueError('DXF yükleme seçenekleri desteklenmiyor.')
    result.update(deepcopy(options))
    for key, title in (('thickness','Kalınlık'), ('tolerance','Eğri toleransı'), ('join_tolerance','Uç toleransı')):
        result[key] = number(result[key], title, positive=True)
    result['quantity'] = integer(result['quantity'], 'Adet')
    if result['tolerance'] > 1 or result['join_tolerance'] > .1:
        raise ValueError('Eğri toleransı en fazla 1 mm; uç birleştirme toleransı en fazla 0,1 mm olabilir.')
    if (result['unit'] not in (None,'mm','cm','inch') or not isinstance(result['material'],str)
            or not result['material'] or type(result['grouped']) is not bool
            or not isinstance(result['excluded_layers'],list)
            or not all(isinstance(s,str) for s in result['excluded_layers'])):
        raise ValueError('DXF birim, malzeme veya katman seçeneği geçersiz.')
    return result


@dataclass
class ImportDraft:
    source: str
    detected: FilenameInfo
    manual: dict = field(default_factory=dict)

    @classmethod
    def create(cls, source, *, retained=None):
        return cls(str(source), parse_filename(source), deepcopy(retained or {}))

    def options(self, defaults, automatic=True):
        result = deepcopy(defaults)
        if automatic:
            for key in ('thickness','quantity'):
                value = getattr(self.detected,key)
                if value is not None: result[key] = value
        result.update(deepcopy(self.manual))
        return normalize_options(result)

    def issues(self, automatic=True):
        return ' '.join(getattr(self.detected,key+'_issue') for key in ('thickness','quantity')
                        if automatic and key not in self.manual and getattr(self.detected,key+'_issue'))

    def status(self, automatic=True):
        if self.issues(automatic): return 'Kontrol gerekli'
        if not automatic: return 'Varsayılan değer'
        known = sum(key in self.manual or getattr(self.detected,key) is not None for key in ('thickness','quantity'))
        return 'Algılandı' if known == 2 else 'Kısmen algılandı' if known else 'Varsayılan değer'

    def edit(self, key, value):
        if key == 'thickness': value = number(value,'Kalınlık',positive=True)
        elif key == 'quantity': value = integer(value,'Adet')
        else: raise ValueError('Yalnız kalınlık ve adet hücreleri düzenlenebilir.')
        self.manual[key] = value

