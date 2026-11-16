"""Independent drawing-space geometry and SI/native scale regressions.

RawDispatch exercises API arithmetic, not a licensed SolidWorks session.
"""

import math
import random
from dataclasses import replace

import pytest
from shapely.geometry import box as rectangle

from modules.automatic_drawing.layout import arrange, plan_sheet, text_box
from modules.automatic_drawing.models import (
    Box,
    FaceEvidence,
    ModelInfo,
    Options,
    Source,
    ViewPlan,
)
from modules.automatic_drawing.rules import plan_views, score_views
from modules.automatic_drawing.validation import validate_views
from modules.cad_converter.api import ApiError

from .test_native_boundary import RawDispatch
from .test_native_boundary import case as case  # noqa: PLC0414 -- pytest fixture registration


def initialize(case, **changes):
    options = replace(case.options, **changes)
    case.native.options = options
    plan = plan_sheet(plan_views(case.info, options), options)
    case.native.create("recorded-boundary.drwdot", plan)
    case.native.create_views(plan)
    return plan


def test_auto_paper_skips_a_smaller_sheet_with_no_usable_height():
    options = Options(
        paper="auto",
        manual_scale=1.0,
        margin_mm=50.0,
        title_height_mm=120.0,
        annotation_padding_mm=0.0,
    )
    plan = plan_sheet([ViewPlan("main", "*Front", (50.0, 50.0))], options)
    # A4: 210-100-120=-10 mm; A3: 297-100-120=77 mm.
    assert plan.paper == "A3" and plan.scale == 1.0
    assert plan.usable.height == 77.0


def test_explicit_paper_with_no_usable_height_is_not_replaced():
    options = Options(
        paper="A4",
        manual_scale=1.0,
        margin_mm=50.0,
        title_height_mm=120.0,
        annotation_padding_mm=0.0,
    )
    with pytest.raises(ValueError, match="görünüş alanı"):
        plan_sheet([ViewPlan("main", "*Front", (50.0, 50.0))], options)


@pytest.mark.parametrize("factor", (0.001, 0.01, 0.1, 1.0, 10.0))
@pytest.mark.parametrize("classification", ("general", "shaft", "flange"))
def test_view_scores_are_dimensionless_under_uniform_model_rescaling(
    factor, classification
):
    info = ModelInfo(
        Source("fixture.sldprt", "A"),
        "part",
        "Fixture",
        (40.0, 50.0, 45.0),
        faces=[
            FaceEvidence("plane", area, direction)
            for area, direction in (
                (400.0, (1.0, 0.0, 0.0)),
                (400.0, (0.0, 1.0, 0.0)),
                (600.0, (0.0, 0.0, 1.0)),
            )
        ]
        + [
            FaceEvidence("cylinder", area, direction)
            for area, direction in (
                (800.0, (1.0, 0.0, 0.0)),
                (200.0, (0.0, 1.0, 0.0)),
                (200.0, (0.0, 0.0, 1.0)),
            )
        ],
        classification=classification,
    )
    scaled = replace(
        info,
        size_mm=tuple(x * factor for x in info.size_mm),
        faces=[replace(f, area_mm2=f.area_mm2 * factor**2) for f in info.faces],
    )
    expected = {row.name: row.score for row in score_views(info)}
    actual = {row.name: row.score for row in score_views(scaled)}
    assert actual == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("projection", ("first", "third"))
@pytest.mark.parametrize(
    "roles",
    (
        ("main",),
        ("flat",),
        ("isometric",),
        ("top",),
        ("side",),
        ("main", "top"),
        ("main", "side"),
        ("main", "top", "side", "isometric"),
    ),
)
def test_measured_layout_against_independent_rectangles(projection, roles):
    rng = random.Random(5456)
    options = Options(projection=projection, annotation_padding_mm=5.0, gap_mm=12.0)
    area = Box(17.0, 41.0, 1000.0, 1000.0)
    for _ in range(20):
        views = [ViewPlan(role, "", (1.0, 1.0)) for role in roles]
        measured, positions = {}, {}
        for role in roles:
            x, y = rng.uniform(-1000, 1000), rng.uniform(-1000, 1000)
            width, height = rng.uniform(10, 150), rng.uniform(10, 150)
            positions[role] = (x, y)
            measured[role] = Box(
                x - width * rng.uniform(0.1, 0.9),
                y - height * rng.uniform(0.1, 0.9),
                width,
                height,
            )
        planned = arrange(
            views, 1.0, area, options, measured=measured, positions=positions
        )
        assert planned is not None
        origins = {v.role: v.center for v in planned}
        shapes = []
        for view in planned:
            box, position = measured[view.role], positions[view.role]
            left = box.x - position[0] + view.center[0] - 5
            bottom = box.y - position[1] + view.center[1] - 5
            shape = rectangle(
                left, bottom, left + box.width + 10, bottom + box.height + 10
            )
            assert rectangle(17.0, 41.0, 1017.0, 1041.0).buffer(1e-8).covers(shape)
            shapes.append(shape)
        for i, first in enumerate(shapes):
            for second in shapes[i + 1 :]:
                assert first.intersection(second).area < 1e-8
                assert first.distance(second) + 1e-8 >= 12.0
        if "main" in origins:
            direction = -1 if projection == "first" else 1
            if "top" in origins:
                assert origins["top"][0] == origins["main"][0]
                assert direction * (origins["top"][1] - origins["main"][1]) > 0
            if "side" in origins:
                assert origins["side"][1] == origins["main"][1]
                assert direction * (origins["side"][0] - origins["main"][0]) > 0


@pytest.mark.parametrize("projection", ("first", "third"))
def test_asymmetric_dimension_envelopes_keep_native_projection_origins_aligned(
    case, monkeypatch, projection
):
    plan = initialize(
        case,
        projection=projection,
        isometric=False,
        manual_scale=1.0,
        annotation_padding_mm=2.0,
        gap_mm=5.0,
    )

    def dimensions(name, roles=None):
        if roles is not None and "main" not in roles:
            return []
        view = case.native.pages[name]["views"]["main"]
        x, y = (v * 1000 for v in view.properties["Position"])
        return [
            {
                "name": "D1",
                "owner": "main",
                "value": 12.5,
                "box": Box(x + 60, y + 19, 30, 4),
            }
        ]

    monkeypatch.setattr(case.native, "dimensions", dimensions)
    case.native.fit(plan.name, include_dimensions=True)
    state = case.native.sheet_state(plan.name)
    state.update(expected=["main", "top", "side"], usable=plan.usable)
    actual = case.native.actual_views(plan.name)
    assert not [
        f
        for f in validate_views(state, actual, case.info.source, projection=projection)
        if f.severity == "FAIL"
    ]
    assert plan.usable.contains(dimensions(plan.name)[0]["box"])


def test_fixed_size_dimension_text_does_not_block_a_feasible_larger_scale(
    case, monkeypatch
):
    plan = initialize(
        case,
        top=False,
        side=False,
        isometric=False,
        paper="custom",
        custom_width_mm=130.0,
        custom_height_mm=140.0,
        title_height_mm=20.0,
        annotation_padding_mm=5.0,
        scales=(2.0, 1.0),
    )
    assert plan.scale == 1.0  # Initial model-box estimate is deliberately conservative.

    def dimensions(name, roles=None):
        x, y = (
            v * 1000
            for v in case.native.pages[name]["views"]["main"].properties["Position"]
        )
        scale = case.state["props"][2] / case.state["props"][3]
        # SetScale(..., True, False): position scales, paper-space text size does not.
        return [
            {
                "name": "D1",
                "owner": "main",
                "value": 12.5,
                "box": Box(x - 40, y + 19 * scale, 80, 4),
            }
        ]

    monkeypatch.setattr(case.native, "dimensions", dimensions)
    case.native.fit(plan.name, include_dimensions=True)
    assert plan.scale == 2.0
    assert dimensions(plan.name)[0]["box"].width == 80.0
    assert plan.usable.contains(dimensions(plan.name)[0]["box"])


def test_refit_cannot_succeed_when_native_annotation_did_not_follow_the_view(
    case, monkeypatch
):
    plan = initialize(case, top=False, side=False, isometric=False, manual_scale=1.0)
    view = case.native.pages[plan.name]["views"]["main"]
    view.properties["Position"] = (2.0, 2.0)
    monkeypatch.setattr(
        case.native,
        "dimensions",
        lambda *a, **kw: [
            {
                "name": "D1",
                "owner": "main",
                "value": 12.5,
                "box": Box(2010, 2020, 20, 4),
            }
        ],
    )
    with pytest.raises(ApiError, match="sığdırılamadı"):
        case.native.fit(plan.name, include_dimensions=True)


@pytest.mark.parametrize("projection", ("first", "third"))
@pytest.mark.parametrize("role", ("top", "side"))
def test_validator_rejects_projected_view_on_the_wrong_side(projection, role):
    source = Source("C:/p.sldprt", "A")
    sheet = {
        "name": "S1",
        "width_mm": 420.0,
        "height_mm": 297.0,
        "expected": ["main", role],
        "projection": projection,
        "usable": Box(10.0, 50.0, 400.0, 237.0),
    }
    wrong = 50.0 if projection == "first" else -50.0
    position = (200.0, 150.0 + wrong) if role == "top" else (200.0 + wrong, 150.0)
    main = {
        "role": "main",
        "name": "Main",
        "outline": Box(190, 140, 20, 20),
        "path": source.path,
        "configuration": "A",
        "position": (200.0, 150.0),
    }
    child = {
        "role": role,
        "name": "Child",
        "outline": Box(position[0] - 10, position[1] - 10, 20, 20),
        "path": source.path,
        "configuration": "A",
        "position": position,
        "parent": "Main",
        "main_name": "Main",
    }
    assert "projection_direction" in {
        f.code
        for f in validate_views(sheet, [main, child], source, projection=projection)
    }


@pytest.mark.parametrize("scale", (0.1, 1.0, 2.0))
@pytest.mark.parametrize(
    "dimension_type,system_value,expected", ((2, 0.0125, 12.5), (3, math.pi / 3, 60.0))
)
def test_native_dimension_values_stay_in_model_mm_or_degrees_at_every_sheet_scale(
    case, scale, dimension_type, system_value, expected
):
    plan = initialize(case, top=False, side=False, isometric=False, manual_scale=scale)
    annotation = RawDispatch(
        "IAnnotation",
        methods={
            "GetDisplayData": lambda: None,
            "IsDangling": lambda: False,
            "GetPosition": lambda: (0.1, 0.1, 0.0),
        },
    )
    dimension = RawDispatch(
        "IDimension",
        methods={"GetSystemValue3": lambda *args: (system_value,)},
        properties={"FullName": "D1@Fixture"},
    )
    display = RawDispatch(
        "IDisplayDimension",
        methods={
            "GetNameForSelection": lambda: "D1@View",
            "GetAnnotation": lambda: annotation,
            "GetDimension2": lambda index: dimension,
            "IsReferenceDim": lambda: False,
            "GetNext5": lambda: None,
        },
        properties={"Type2": dimension_type},
    )
    case.native.pages[plan.name]["views"]["main"].methods[
        "GetFirstDisplayDimension5"
    ] = lambda: display
    records = case.native.dimensions(plan.name)
    assert records[0]["value"] == pytest.approx(expected, abs=1e-12)


def test_flat_dimension_uses_its_own_referenced_configuration(case):
    plan = initialize(case, top=False, side=False, isometric=False, manual_scale=1.0)
    page = case.native.pages[plan.name]
    view = page["views"]["main"]
    view.properties["ReferencedConfiguration"] = "Body-01-Flat"
    page["views"] = {"flat": view}

    def system_value(mode, configurations):
        names = getattr(configurations, "value", configurations)
        names = (names,) if isinstance(names, str) else tuple(names)
        return (0.125 if names == ("Body-01-Flat",) else 0.100,)

    annotation = RawDispatch(
        "IAnnotation",
        methods={
            "GetDisplayData": lambda: None,
            "IsDangling": lambda: False,
            "GetPosition": lambda: (0.1, 0.1, 0.0),
        },
    )
    dimension = RawDispatch(
        "IDimension",
        methods={"GetSystemValue3": system_value},
        properties={"FullName": "D1@Body"},
    )
    display = RawDispatch(
        "IDisplayDimension",
        methods={
            "GetNameForSelection": lambda: "D1@Flat",
            "GetAnnotation": lambda: annotation,
            "GetDimension2": lambda index: dimension,
            "IsReferenceDim": lambda: False,
            "GetNext5": lambda: None,
        },
        properties={"Type2": 2},
    )
    view.methods["GetFirstDisplayDimension5"] = lambda: display
    record = case.native.dimensions(plan.name)[0]
    assert record["value"] == 125.0
    assert (
        record["model_identity"][0] == Source(case.info.source.path, "Body-01-Flat").key
    )


@pytest.mark.parametrize(
    "angle,expected",
    (
        (0.0, (4.0, 3.0)),
        (math.pi / 2, (3.0, 4.0)),
        (-math.pi / 2, (3.0, 4.0)),
        (math.atan2(3, 4), (5.0, 4.8)),
    ),
)
def test_rotated_text_envelope_against_exact_right_triangle_components(angle, expected):
    box = text_box(10.0, 20.0, 4.0, 3.0, angle)
    assert (box.width, box.height) == pytest.approx(expected, abs=1e-12)
