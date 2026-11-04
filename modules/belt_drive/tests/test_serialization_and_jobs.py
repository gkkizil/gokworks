"""Strict project contracts, controlled CLI errors and Qt-free worker protocol."""

from dataclasses import replace
import json
import os
from pathlib import Path
from queue import Queue
import subprocess
import sys
from threading import Event

import pytest

from modules.belt_drive.calculation import calculate
from modules.belt_drive.controller import calculation_job
from modules.belt_drive.models import BeltDriveSpecification, LoadSpecification, SpecificationError
from modules.belt_drive.serialization import (dumps, loads, to_dict, from_dict, read_json,
    result_to_dict, catalog_to_dict, catalog_from_dict, MAX_JSON_SIZE)
from modules.belt_drive.validation import CalculationCancelled
from .test_calculation import timing
from .test_catalog import timing_catalog


@pytest.mark.parametrize('spec', [BeltDriveSpecification(), timing(),
    replace(timing(), load=LoadSpecification(power_kw=None, torque_nm=10., efficiency=.9, service_factor=1.2))])
def test_project_roundtrip_revalidates_all_inputs(spec):
    assert loads(dumps(spec)) == spec
    assert calculate(loads(dumps(spec))) == calculate(spec)


@pytest.mark.parametrize('changes', [
    {'version': True}, {'version': 2}, {'units': 'inch'}, {'schema': 'another'}, {'unexpected': 1},
])
def test_wrong_schema_and_unknown_fields(changes):
    with pytest.raises(ValueError):
        from_dict(to_dict(BeltDriveSpecification()) | changes)


def test_missing_nested_fields_and_bad_values_are_not_filled_silently():
    data = to_dict(BeltDriveSpecification())
    del data['load']['efficiency']
    with pytest.raises(ValueError, match='eksik'):
        from_dict(data)
    data = to_dict(BeltDriveSpecification())
    data['load']['input_rpm'] = 0
    with pytest.raises(SpecificationError):
        from_dict(data)
    data = to_dict(BeltDriveSpecification())
    data['center']['distance_mm'] = 10
    with pytest.raises(SpecificationError):
        from_dict(data)


@pytest.mark.parametrize('text', ['{"version":1,"version":1}', '{"x":NaN}', '{"x":Infinity}',
    '{"x":-Infinity}', '{broken', ' '*(MAX_JSON_SIZE+1)],
    ids=['duplicate-key', 'nan', 'positive-inf', 'negative-inf', 'syntax', 'oversize'])
def test_malformed_duplicate_nonfinite_and_oversized_json(text):
    with pytest.raises(ValueError):
        read_json(text)


def test_nested_array_is_not_a_design_even_if_the_json_parser_accepts_it():
    with pytest.raises(ValueError):
        loads('['*2000 + ']'*2000)


def test_numeric_exponent_overflow_is_rejected_by_input_validation():
    text = dumps(BeltDriveSpecification()).replace('1450.0', '1e999')
    with pytest.raises(SpecificationError):
        loads(text)


def test_catalog_roundtrip_preserves_declared_source_but_not_verification():
    catalog = timing_catalog()
    restored = catalog_from_dict(read_json(json.dumps(catalog_to_dict(catalog))))
    assert restored == catalog
    data = catalog_to_dict(catalog)
    data['source']['verified'] = True
    with pytest.raises(ValueError):
        catalog_from_dict(data)


def test_result_is_serializable_and_cannot_be_loaded_as_a_design():
    result = calculate(timing())
    data = result_to_dict(result)
    assert json.loads(json.dumps(data, allow_nan=False))['geometry']['segments'][0]['kind'] == 'line'
    assert data['geometry']['length_mm'] == pytest.approx(result.length_exact_mm)
    assert not data['power_capacity_verified'] and not data['production_approved'] and not data['cad_available']
    assert any(check['severity'] == 'NOT_EVALUATED' for check in data['checks'])
    with pytest.raises(ValueError):
        from_dict(data)


def test_job_manager_protocol_publishes_one_complete_immutable_report():
    events, stop = Queue(), Event()
    calculation_job(timing(), timing_catalog())(events, stop)
    kind, report = events.get_nowait()
    assert kind == 'belt_result' and len(report.candidates) == 3
    assert report.result.ratio == 2 and events.empty()


def test_failed_or_cancelled_jobs_publish_no_partial_result():
    events, stop = Queue(), Event()
    stop.set()
    with pytest.raises(CalculationCancelled):
        calculation_job(timing())(events, stop)
    stop.clear()
    with pytest.raises(SpecificationError):
        calculation_job(replace(timing(), load=LoadSpecification(input_rpm=0)))(events, stop)
    assert events.empty()


def test_cancellation_during_selection_publishes_nothing():
    class StopAfterChecks:
        calls = 0
        def is_set(self):
            self.calls += 1
            return self.calls >= 6
    events = Queue()
    with pytest.raises(CalculationCancelled):
        calculation_job(timing(), timing_catalog())(events, StopAfterChecks())
    assert events.empty()


def run_cli(*arguments):
    return subprocess.run([sys.executable, '-m', 'modules.belt_drive', *map(str, arguments)],
        cwd=Path(__file__).resolve().parents[3], capture_output=True, text=True, encoding='utf-8',
        env=dict(os.environ, PYTHONUTF8='1'), timeout=15)


def test_cli_example_and_real_calculation_without_a_qt_application(tmp_path):
    example = run_cli('--example')
    assert example.returncode == 0, example.stderr
    project = tmp_path / 'project.json'
    project.write_text(example.stdout, encoding='utf-8')
    result = run_cli(project)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['length_exact_mm'] == pytest.approx(1277.4970744746527)
    project.write_text(dumps(timing()), encoding='utf-8')
    catalog = tmp_path / 'catalog.json'
    catalog.write_text(json.dumps(catalog_to_dict(timing_catalog())), encoding='utf-8')
    result = run_cli(project, '--catalog', catalog)
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)['catalog_candidates']) == 3


def test_cli_reports_missing_and_corrupt_files_without_traceback(tmp_path):
    missing = run_cli(tmp_path / 'missing.json')
    assert missing.returncode == 2 and 'Traceback' not in missing.stderr and not missing.stdout
    path = tmp_path / 'broken.json'
    path.write_text('bad json', encoding='utf-8')
    broken = run_cli(path)
    assert broken.returncode == 2 and 'Traceback' not in broken.stderr and not broken.stdout


def test_complete_api_imports_and_calculates_without_site_packages():
    script = '''
import sys
from modules.belt_drive import calculate, BeltDriveSpecification
from modules.belt_drive.controller import calculation_job
from modules.belt_drive.serialization import dumps, loads
assert calculate(loads(dumps(BeltDriveSpecification()))).ratio == 2
assert not {'PySide6', 'OCP', 'win32com', 'ezdxf', 'numpy', 'shapely'} & sys.modules.keys()
'''
    result = subprocess.run([sys.executable, '-S', '-c', script], cwd=Path(__file__).resolve().parents[3],
                            capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr


def test_shipped_examples_are_valid_but_never_manufacturer_approved():
    examples = Path(__file__).resolve().parents[1] / 'examples'
    v = calculate(loads((examples / 'reference_v.json').read_bytes()))
    assert v.ratio == 2 and not v.production_approved
    spec = loads((examples / 'timing_110.json').read_bytes())
    catalog = catalog_from_dict(read_json((examples / 'dimension_list.example.json').read_bytes()))
    assert calculate(spec).selected_length_mm == 550
    assert catalog.source.kind == 'example'
    events = Queue()
    calculation_job(spec, catalog)(events, Event())
    _, report = events.get_nowait()
    assert len(report.candidates) == 3 and all(not item.production_approved for item in report.candidates)
