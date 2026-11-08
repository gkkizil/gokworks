"""Claude arayüzü için kararlı, Qt'siz metadata ve hesap sözleşmesi."""
from dataclasses import asdict, fields
from typing import get_type_hints
from .core import models
from .core.catalogs import (PUMP_DEFAULTS, PUMP_LABELS, MOUNT_K, SPEED_RANGES,
                           BORES_MM, RODS_MM, MOTORS_KW, PUMP_CC, PIPE_IDS_MM,
                           ACCUMULATORS_L, SOURCE_NOTE, MOTOR_RPM)
from .core.service import calculate_project
from .presentation import result_rows

CONTRACT_VERSION = 1
MODEL_TYPES = ('Cylinder','CylinderOperatingPoint','Phase','Pump','Pipe','Oil','Thermal','Accumulator','Project')
UNITS = {
    'bore':'m','rod':'m','stroke':'m','initial_position':'m','effective_length':'m','travel':'m','young_modulus':'Pa',
    'pressure':'Pa','force':'N','speed':'m/s','duration':'s','back_pressure':'Pa',
    'displacement':'m3/rev','angular_speed':'rad/s','max_pressure':'Pa','compensator_pressure':'Pa',
    'power_limit':'W','leakage_flow':'m3/s','idle_pressure':'Pa',
    'target_velocity':'m/s','min_velocity':'m/s','max_velocity':'m/s','length':'m','diameter':'m',
    'nu40':'m2/s','nu100':'m2/s','temperature':'K','density':'kg/m3',
    'residence_time':'s','width':'m','height':'m','heat_transfer':'W/m2K','ambient':'K','target':'K',
    'minimum_pressure':'Pa','maximum_pressure':'Pa','precharge_pressure':'Pa','delivery_volume':'m3',
    'atmospheric_pressure':'Pa','relief_pressure':'Pa','selected_motor':'W'}
DISPLAY_UNITS = {'m':'mm','Pa':'bar','N':'kN','m/s':'mm/s','m3/rev':'cm3/rev',
                 'rad/s':'rpm','W':'kW','m3/s':'L/min','m2/s':'cSt','K':'°C','m3':'L'}
CHOICES = {'mounting':tuple(MOUNT_K),'control':('fixed','pressure','power'),
           'role':tuple(SPEED_RANGES),'grade':('ISO VG 32','ISO VG 46','ISO VG 68','Custom'),
           'installation':('stationary','mobile'),'display_units':('metric','us')}


def describe() -> dict:
    """Varsayılanlar SI; UI dönüşümleri bu değerleri değiştirmeden yapmalıdır."""
    schemas = {}
    for name in MODEL_TYPES:
        cls = getattr(models, name); defaults = asdict(cls()); hints = get_type_hints(cls)
        descriptors = []
        for field in fields(cls):
            key = field.name; options = CHOICES.get(key)
            if key == 'kind':
                options = tuple(PUMP_DEFAULTS) if name == 'Pump' else ('extend','retract','regenerate','hold','idle') if name == 'Phase' else ('extend','retract','regenerate')
            unit = UNITS.get(key, '1')
            descriptors.append(dict(id=key,type=str(hints[key]),default=defaults[key],unit=unit,
                display_unit=DISPLAY_UNITS.get(unit,unit), options=options))
        schemas[name] = descriptors
    return dict(schema='gokworks.hydraulic_unit.metadata',version=CONTRACT_VERSION,engine_version='1.0.0',
                units='SI',models=schemas,pump_labels=PUMP_LABELS,
                typical_pump_defaults=PUMP_DEFAULTS,mounting_factors=MOUNT_K,
                motor_rpm_50hz=MOTOR_RPM,
                speed_ranges=SPEED_RANGES,high_pressure_speed_range=(5.,8.),
                high_pressure_threshold=200e5,
                nominal_series=dict(bores_mm=BORES_MM,rods_mm=RODS_MM,motors_kw=MOTORS_KW,
                    pump_cc=PUMP_CC,pipe_ids_mm=PIPE_IDS_MM,accumulators_l=ACCUMULATORS_L),
                source=SOURCE_NOTE, capabilities=dict(sequential_cycle=True,simultaneous=False,
                dynamic_simulation=False,cad=False,transient_heating=False,manufacturer_approved=False),
                severities={'info':'Bilgi','warning':'Uyarı','critical':'Kritik'})


def calculate(project: models.Project) -> dict:
    """Aynı sözleşme tablo ve rapor için; uygunluk üretim onayı değildir."""
    result = calculate_project(project)
    return dict(schema='gokworks.hydraulic_unit.result',version=CONTRACT_VERSION,units='SI',
                **asdict(result), rows=[dict(label=k,value=v,unit=u,formula=f)
                                       for k,v,u,f in result_rows(project,result)])
