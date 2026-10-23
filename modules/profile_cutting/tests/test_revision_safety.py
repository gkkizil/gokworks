from dataclasses import asdict
from copy import deepcopy
import json

import pytest

from modules.profile_cutting.models import Project, Demand, transfer, reconcile
from modules.profile_cutting.optimizer import optimize
from modules.profile_cutting.storage import save, load, export_report
from .fakes import Model, Folder
from .test_scanner import read


def imported(tmp_path):
    result, _ = read(Model(tmp_path/'frame.SLDPRT', [Folder()]))
    project = Project([Demand('manual', '50x30x2', 'S235JR', '1000', 1)])
    transfer(project, result)
    return project, result


@pytest.mark.parametrize('change', ['length', 'count', 'deleted', 'not_ready'])
def test_refreshed_or_removed_source_blocks_old_plan_without_deleting_values(tmp_path, change):
    project, result = imported(tmp_path); plan = optimize(project)
    if change == 'deleted': result.rows.clear()
    elif change == 'not_ready': result.rows[0].issues.append('Kaynak artık doğrulanamıyor.')
    else: setattr(result.rows[0], change, '1200' if change == 'length' else 5)
    assert reconcile(project, result) == 1
    assert not project.demands[0].source_changed
    assert project.demands[1].length == '1000' and project.demands[1].count == 1
    with pytest.raises(ValueError, match='kaynak verisi'):
        optimize(project)
    target = tmp_path/'report.csv'; target.write_text('previous')
    with pytest.raises(ValueError): export_report(project, result, plan, target)
    assert target.read_text() == 'previous'
    path = tmp_path/'stale.gokprofile'; save(project, result, path)
    assert load(path)[0] == project  # Stale analyses remain saveable for review.


def test_another_root_configuration_and_unchanged_refresh_preserve_current_import(tmp_path):
    project, result = imported(tmp_path)
    other = deepcopy(result); other.source = str(tmp_path/'another.SLDASM'); other.rows = []
    assert reconcile(project, other) == 0
    other = deepcopy(result); other.configuration = 'Another'; other.rows = []
    assert reconcile(project, other) == 0
    assert reconcile(project, result) == 0
    assert optimize(project).bars


def test_legacy_v1_project_defaults_remain_loadable_and_refreshable(tmp_path):
    project, result = imported(tmp_path)
    path = tmp_path/'v1.gokprofile'; save(project, result, path)
    data = json.loads(path.read_text())
    for demand in data['project']['demands']:
        demand.pop('source_changed'); demand.pop('import_root')
    path.write_text(json.dumps(data))
    again, _ = load(path); assert optimize(again).bars
    result.rows[0].length = '2000'
    assert reconcile(again, result) == 1
    with pytest.raises(ValueError): optimize(again)


@pytest.mark.parametrize('field,value', [('profile', None), ('reviewed', 'yes'), ('count', -1),
                                       ('body_refs', 'bad'), ('issues', [42])])
def test_corrupt_scan_fields_are_rejected_before_ui_receives_them(tmp_path, field, value):
    project, result = imported(tmp_path)
    path = tmp_path/'bad.gokprofile'; save(project, result, path)
    data = json.loads(path.read_text()); data['scan']['rows'][0][field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError): load(path)


def test_nonfinite_json_and_wrong_demand_types_are_rejected(tmp_path):
    project, result = imported(tmp_path)
    path = tmp_path/'bad.gokprofile'; save(project, result, path)
    data = json.loads(path.read_text()); data['project']['demands'][0]['profile'] = None
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError): load(path)
    data['project']['demands'][0] = asdict(project.demands[0])
    data['scan']['rows'][0]['count'] = float('nan')
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError): load(path)
