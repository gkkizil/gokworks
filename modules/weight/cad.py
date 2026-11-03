"""Mass of the active SOLIDWORKS model (part or assembly), read with the existing connection.

This is a separate method from the formula-based weight: SOLIDWORKS integrates the real
model volume, so holes, chamfers and pockets are included. The weight module works without
it; this file imports pywin32 only when called.
"""

from dataclasses import dataclass
import math

PART, ASSEMBLY, DRAWING = 1, 2, 3
DEFAULT_SW_DENSITY = 1000.0  # kg/m³ SOLIDWORKS uses when no material is assigned


@dataclass(frozen=True)
class CadMass:
    document: str
    configuration: str
    kind: str              # 'Parça' / 'Montaj'
    material: str
    volume_m3: float
    density_kg_m3: float
    mass_kg: float
    notes: tuple = ()


def _value(obj, name):
    value = getattr(obj, name)
    if hasattr(value, '_oleobj_'):   # CDispatch is callable: don't invoke its default member
        return value
    return value() if callable(value) else value


def _number(value, label):
    if isinstance(value, bool) or value is None:
        raise RuntimeError(f'SOLIDWORKS {label} değerini döndürmedi.')
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise RuntimeError(f'SOLIDWORKS geçersiz {label} döndürdü.')
    return number


def material_name(model):
    """Assigned material of a part ('' if none). MaterialIdName: 'database|name|id|'."""
    try:
        text = _value(model, 'MaterialIdName')
    except Exception:
        text = ''
    if isinstance(text, str) and '|' in text:
        parts = text.split('|')
        if len(parts) > 1 and parts[1].strip():
            return parts[1].strip()
    return ''


def read(model):
    """Mass properties of one open model (injectable: tests pass a fake)."""
    if model is None:
        raise RuntimeError('SOLIDWORKS’te açık bir parça veya montaj yok.')
    doc_type = _value(model, 'GetType')
    if doc_type not in (PART, ASSEMBLY):
        raise RuntimeError('Etkin belge parça veya montaj değil. Teknik resim yerine modeli etkinleştirin.')
    title = str(_value(model, 'GetTitle') or '')
    try:
        configuration = str(_value(_value(model, 'ConfigurationManager'), 'ActiveConfiguration').Name)
    except Exception:
        configuration = ''
    properties = _value(_value(model, 'Extension'), 'CreateMassProperty2')
    if properties is None:
        raise RuntimeError('SOLIDWORKS kütle hesaplayıcısı oluşturulamadı.')
    properties.UseSystemUnits = True   # metres, kilograms
    if not _value(properties, 'Recalculate'):
        raise RuntimeError('SOLIDWORKS kütle özelliklerini hesaplayamadı; modeli yeniden oluşturun.')
    volume = _number(_value(properties, 'Volume'), 'hacim')
    mass = _number(_value(properties, 'Mass'), 'kütle')
    if volume <= 0 or mass <= 0:
        raise RuntimeError('Modelde katı gövde yok; hacim sıfır.')
    density = mass / volume
    notes = ['Kütle SOLIDWORKS model geometrisinden hesaplandı (delik, pah ve boşaltmalar dahil).']
    if doc_type == PART:
        material = material_name(model)
        if not material:
            raise RuntimeError('Parçada malzeme tanımlı değil. SOLIDWORKS’te malzeme atayın; '
                               f'aksi hâlde {DEFAULT_SW_DENSITY:g} kg/m³ varsayılan yoğunlukla yanlış kütle çıkar.')
        kind = 'Parça'
    else:
        material = 'Montaj (bileşen malzemeleri)'
        kind = 'Montaj'
        notes.append('Montajda yoğunluk, toplam kütle / toplam hacim ortalamasıdır.')
    return CadMass(title, configuration, kind, material, volume, density, mass, tuple(notes))


def read_active(connect=None):
    """Connect to the running SOLIDWORKS and read its active document."""
    if connect is None:
        from solidworks.connection import connect_to_solidworks as connect
    app = connect()
    return read(_value(app, 'ActiveDoc'))


def worker(events, stop):
    """JobManager entry: COM in this thread, result as an event."""
    import pythoncom
    pythoncom.CoInitialize()
    try:
        events.put(('weight_cad_phase', 'SOLIDWORKS etkin modeli okunuyor…'))
        events.put(('weight_cad', read_active()))
    finally:
        pythoncom.CoUninitialize()


__all__ = ['CadMass', 'read', 'read_active', 'worker', 'material_name']
