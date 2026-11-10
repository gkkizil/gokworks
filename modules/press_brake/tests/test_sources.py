"""Original synthetic profiles; live manufacturer files are never test fixtures."""
from copy import deepcopy
from dataclasses import replace
from io import BytesIO
from math import cos, pi, sin, sqrt, tan
import json
import threading
import urllib.error

import pytest
from modules.cad_converter.models import Cancelled
from modules.press_brake.models import Channel
from modules.press_brake.sources import download_starter, manufacturer_tools, merged_catalog, parse_starter
from modules.press_brake.tooling import load_catalog, save_catalog


def catalog():
    # A round-nose 90-degree punch drawn from first principles, R1, H20.
    k = sqrt(.5)
    points = [(k, 1-k), (5, 6-2*k), (5, 20), (-5, 20), (-5, 6-2*k), (-k, 1-k)]
    edges = [dict(start=(-k, 1-k), end=(k, 1-k), center=(0, 1), sweepRadians=pi/2)]
    edges += [dict(start=a, end=b, center=None, sweepRadians=0) for a, b in zip(points, points[1:])]
    row = dict(id='original-test', code='GOK-TEST-R1', manufacturer='GOKWORKS TEST', kind='punch',
               parametersConfirmed=True, teaching=False, angleRadians=pi/2, noseRadiusMm=1,
               heightMm=20, lengthMm=50, openingsMm=[], grooveSettings=[],
               segments=[dict(lengthMm=50, quantity=2)],
               drawing=dict(millimeters=True, edges=edges, sourceFile='original-test.dxf', sha256='0'*64))
    return dict(format='bending-tool-catalog', version=5, tools=[row])


def die_catalog():
    """Original rounded-shoulder V8/90 die, shoulder R1, height 15."""
    k, c = sqrt(.5), 4+tan(pi/8)
    points = [(-10,-15),(10,-15),(10,0),(c,0),(c-k,-1+k),(0,-4),(-c+k,-1+k),(-c,0),(-10,0),(-10,-15)]
    edges = [dict(start=a, end=b, center=None, sweepRadians=0) for a,b in zip(points,points[1:])]
    edges[3].update(center=(c,-1),sweepRadians=pi/4)
    edges[6].update(center=(-c,-1),sweepRadians=pi/4)
    data = catalog(); row = data['tools'][0]
    row.update(id='original-die',code='GOK-TEST-DIE',kind='die',heightMm=15,lengthMm=100,noseRadiusMm=None,
               openingsMm=[8],grooveSettings=[dict(rotationRadians=0,angleRadians=pi/2)])
    row['drawing']['edges'] = edges
    return data


def test_native_arcs_working_tip_stock_and_atomic_catalog_roundtrip(tmp_path):
    tools = parse_starter(json.dumps(catalog()))
    tool = tools[0]
    assert tool.tip == pytest.approx((0, 0)) and tool.tip_radius == 1 and tool.tip_angle == 90
    assert tool.catalog_segments == ((50, 2),) and tool.segments[0].length == 50
    assert 'ARC' in tool.section_dxf and tool.section is not None and not tool.mount.compatible
    path = tmp_path/'catalog.json'; save_catalog(tools, path)
    assert load_catalog(path) == tools
    edited = replace(tool, code='Owned edit')
    assert merged_catalog((edited,), tools) == (edited,)


def test_submicron_source_endpoint_rounding_keeps_exact_arcs_and_valid_solid():
    from modules.press_brake.geometry import Geometry
    from modules.gear_calculator.cad import shape_stats
    data = catalog()
    start = list(data['tools'][0]['drawing']['edges'][1]['start']); start[0] += 5e-7
    data['tools'][0]['drawing']['edges'][1]['start'] = start
    tool = parse_starter(json.dumps(data))[0]
    assert 'ARC' in tool.section_dxf
    assert shape_stats(Geometry().tool_shape(tool, tool.segments[0]))['volume_mm3'] > 0


def test_real_rounded_shoulder_contact_follows_the_arc_not_a_sharp_v_corner():
    from modules.press_brake.demo import load_demo
    from modules.press_brake.geometry import Geometry
    from modules.press_brake.kinematics import step_angles
    from modules.press_brake.collision import check
    tool = parse_starter(json.dumps(die_catalog()))[0]
    channel = tool.channels[0]
    assert channel.opening == 8 and channel.shoulder_radius == pytest.approx(1)
    plan = load_demo('L120')
    plan = plan.changed(tools=plan.tools+(tool,),steps=(replace(plan.steps[0],die=tool.id,channel=channel.id),))
    geometry = Geometry(plan)
    for fraction in (.25,.5,1):
        bodies, contacts = geometry.scene(0,step_angles(plan,0,fraction))
        die = next(b for b in bodies if b.kind == 'die')
        contact = next(c for c in contacts if c[0] == 'die' and c[1] > 0)
        half = pi/3*fraction/2
        assert contact[1] == pytest.approx(4+tan(pi/8)-sin(half))
        assert contact[2] == pytest.approx(die.bounds[5]-1+cos(half))
        assert not any('die:' in ' '.join(hit.pair) for hit in check(bodies,contacts)[0])


@pytest.mark.parametrize('change', ['units', 'unconfirmed', 'arc', 'duplicate', 'version'])
def test_malformed_or_unconfirmed_source_is_rejected(change):
    data = deepcopy(catalog())
    if change == 'units': data['tools'][0]['drawing']['millimeters'] = False
    if change == 'unconfirmed': data['tools'][0]['parametersConfirmed'] = False
    if change == 'arc': data['tools'][0]['drawing']['edges'][0]['sweepRadians'] = 0
    if change == 'duplicate': data['tools'] *= 2
    if change == 'version': data['version'] = 99
    with pytest.raises(ValueError): parse_starter(json.dumps(data))


def test_download_is_explicit_bounded_cancelable_and_does_not_write_a_library(tmp_path):
    requests = []
    def opener(request, timeout):
        requests.append((request.full_url, timeout)); return BytesIO(json.dumps(catalog()).encode())
    assert download_starter(opener=opener)[0].code == 'GOK-TEST-R1'
    assert len(requests) == 1 and requests[0][0].startswith('https://raw.githubusercontent.com/')
    stop = threading.Event(); stop.set()
    with pytest.raises(Cancelled): download_starter(stop, opener=opener)
    assert len(requests) == 1
    def broken(*args, **kwargs): raise urllib.error.URLError('offline')
    with pytest.raises(ValueError, match='korunuyor'): download_starter(opener=broken)
    assert not list(tmp_path.iterdir())


def test_manufacturer_facts_are_not_fabricated_collision_geometry():
    tools = manufacturer_tools()
    assert len(tools) == 4 and all(t.section is None and t.holder_section is None and not t.demo for t in tools)
    punch = next(t for t in tools if t.code == 'BIU-021')
    assert (punch.height, punch.tip_angle, punch.tip_radius, punch.line_load_unit) == (163, 28, 1, 'ton/m')
    die = next(t for t in tools if t.code == 'OZU-313')
    assert die.channels[0] == Channel('V24', 24, 80, (0, 0), 5)
