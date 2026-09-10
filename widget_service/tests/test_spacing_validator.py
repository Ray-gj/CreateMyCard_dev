from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from services.card_validation import ValidationOptions, pipeline, validate_card
from services.card_validation.context import ValidationContext
from services.card_validation.diagnostics import Reporter
from services.card_validation.quality.spacing_validator import SpacingValidator
from services.card_validation.rule_registry import RuleRegistry
from services.card_validation.source_parser import SourceParser
from services.fusion_ball_expander import FusionBallPalette, expand_fusion_ball_components
from services.template_generation.engine.cardplan.compiler import _serialize_node
from services.template_generation.engine.cardplan.fusion_ball_background import (
    apply_content_safe_inset,
    apply_fusion_ball_background,
)
from services.template_generation.engine.tersel_converter import (
    convert_tersel_to_a2ui,
    parse_tersel,
)
from services.template_generation.profile import read_tersel_protocol_profile


@pytest.fixture
def rules() -> RuleRegistry:
    rules_dir = Path(__file__).resolve().parents[1] / "cloud" / "data" / "validator_rules"
    return RuleRegistry(rules_dir)


def _parse(dsl: str) -> ValidationContext:
    reporter = Reporter()
    context = SourceParser().parse(dsl, '{"suggestSize":"2x2"}', reporter)
    assert not reporter.diagnostics
    return context


def _context(components: list[dict[str, Any]]) -> ValidationContext:
    messages = [
        {"version": "v0.9", "createSurface": {"surfaceId": "spacing-test"}},
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "spacing-test",
                "root": "root",
                "components": components,
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {"surfaceId": "spacing-test", "path": "/", "value": {}},
        },
    ]
    return _parse("\n".join(json.dumps(message) for message in messages))


def _node(context: ValidationContext, component_id: str) -> dict[str, Any]:
    component = context.components_by_id.get(component_id)
    assert isinstance(component, dict)
    return component


def _run(context: ValidationContext, rules: RuleRegistry) -> Reporter:
    reporter = Reporter()
    SpacingValidator().validate(context, rules, reporter)
    return reporter


def _layered_context(scene: str) -> ValidationContext:
    foreground_id = "__genui_render_component__root" if scene == "design" else "template_root"
    root_children = [foreground_id]
    if scene != "normal":
        root_children.insert(0, "fusionBallBackground")
    return _context(
        [
            {
                "id": "root",
                "component": "Stack",
                "children": root_children,
                "styles": {"padding": 0},
            },
            {
                "id": "fusionBallBackground",
                "component": "Stack",
                "styles": {"padding": 0},
            },
            {
                "id": foreground_id,
                "component": "Stack",
                "children": ["__genui_render_component__template_root"],
                "styles": {"padding": 12},
            },
            {
                "id": "__genui_render_component__template_root",
                "component": "Column",
                "children": ["title"],
                "styles": {"padding": 0},
            },
            {"id": "title", "component": "Text", "content": "今日安排"},
        ]
    )


@pytest.mark.parametrize("scene", ["normal", "design", "fusion_template"])
@pytest.mark.parametrize(
    "padding", [None, 0, 8, 12, {"left": 12, "right": 12, "top": 12, "bottom": 12}]
)
def test_spacing_checks_foreground_not_background(
    rules: RuleRegistry, scene: str, padding: Any
) -> None:
    context = _layered_context(scene)
    foreground_id = "__genui_render_component__root" if scene == "design" else "template_root"
    foreground = _node(context, foreground_id)
    foreground["styles"] = {} if padding is None else {"padding": padding}

    reporter = _run(context, rules)

    if padding == 12 or isinstance(padding, dict):
        assert not reporter.diagnostics
    else:
        assert len(reporter.diagnostics) == 1
        diagnostic = reporter.diagnostics[0]
        assert diagnostic.code == "SPACING.SAFE_MARGIN"
        assert diagnostic.json_pointer == "/updateComponents/components/2/styles/padding"
        assert diagnostic.actual == padding
        assert diagnostic.expected == 12


@pytest.mark.parametrize("scene", ["normal", "design", "fusion_template"])
def test_spacing_reports_missing_foreground_styles(rules: RuleRegistry, scene: str) -> None:
    context = _layered_context(scene)
    foreground_id = "__genui_render_component__root" if scene == "design" else "template_root"
    _node(context, foreground_id).pop("styles", None)

    reporter = _run(context, rules)

    assert len(reporter.diagnostics) == 1
    assert reporter.diagnostics[0].json_pointer == "/updateComponents/components/2/styles/padding"


@pytest.mark.parametrize("scene", ["normal", "design", "fusion_template"])
def test_spacing_foreground_honors_configured_padding(rules: RuleRegistry, scene: str) -> None:
    context = _layered_context(scene)
    foreground_id = "__genui_render_component__root" if scene == "design" else "template_root"
    rules.layout["defaultPadding"] = 8
    _node(context, foreground_id)["styles"] = {"padding": 8}

    assert not _run(context, rules).diagnostics


@pytest.mark.parametrize("scene", ["normal", "design", "fusion_template"])
@pytest.mark.parametrize("component_id", ["root", "fusionBallBackground", "title"])
def test_spacing_still_checks_background_and_content_scale(
    rules: RuleRegistry, scene: str, component_id: str
) -> None:
    context = _layered_context(scene)
    component = _node(context, component_id)
    styles = component.setdefault("styles", {})
    assert isinstance(styles, dict)
    styles["margin"] = 7

    reporter = _run(context, rules)

    assert len(reporter.diagnostics) == 1
    assert reporter.diagnostics[0].code == "SPACING.SCALE"


@pytest.mark.parametrize(
    "children",
    [
        ["fusionBallBackground"],
        ["fusionBallBackground", "missing"],
        ["fusionBallBackground", "title"],
        ["fusionBallBackground", "template_root", "title"],
        ["fusionBallBackground", "root_0"],
    ],
)
def test_spacing_marker_without_unique_foreground_keeps_root_check(
    rules: RuleRegistry, children: list[str]
) -> None:
    context = _layered_context("fusion_template")
    _node(context, "root")["children"] = children

    reporter = _run(context, rules)

    assert reporter.has_code("SPACING.SAFE_MARGIN")
    assert reporter.diagnostics[0].json_pointer == "/updateComponents/components/0/styles/padding"


@pytest.mark.parametrize("content_id", ["missing", "title", "__genui_render_component__missing"])
def test_spacing_template_marker_requires_real_overflow_container(
    rules: RuleRegistry, content_id: str
) -> None:
    context = _layered_context("normal")
    _node(context, "template_root")["children"] = [content_id]

    reporter = _run(context, rules)

    assert reporter.has_code("SPACING.SAFE_MARGIN")
    assert reporter.diagnostics[0].json_pointer == "/updateComponents/components/0/styles/padding"


@pytest.mark.parametrize("root_padding", [0, 12])
def test_spacing_nested_fusion_marker_does_not_reclassify_normal_root(
    rules: RuleRegistry, root_padding: int
) -> None:
    context = _layered_context("normal")
    _node(context, "root")["component"] = "Column"
    _node(context, "root")["styles"] = {"padding": root_padding}
    _node(context, "template_root")["children"] = ["fusionBallBackground", "title"]

    assert _run(context, rules).has_code("SPACING.SAFE_MARGIN") == (root_padding != 12)


@pytest.mark.parametrize("scene", ["plain", "normal_template", "fusion_template", "design"])
@pytest.mark.parametrize("padding", [0, 12])
def test_spacing_checks_real_generated_a2ui(
    rules: RuleRegistry, scene: str, padding: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    palette = FusionBallPalette("#FF121E59", "#FF2BA2D9", "#FF52CCCC")
    card = parse_tersel(
        'Column("card",{"_id":"root","padding":12,"borderRadius":18},'
        'Column({"_id":"template_root"},Text("今日安排","body")));'
    )
    if scene == "normal_template":
        card = apply_content_safe_inset(card, size="2x2")
    elif scene == "fusion_template":
        card = apply_fusion_ball_background(card, size="2x2", palette=palette)
    dsl = convert_tersel_to_a2ui(
        _serialize_node(card) + ";",
        size="2x2",
        protocol_profile=read_tersel_protocol_profile(),
    )
    context = _parse(dsl)
    if scene == "design":
        context = _context(expand_fusion_ball_components(context.components, palette))
    safe_id = "root"
    if scene in {"normal_template", "fusion_template"}:
        safe_id = "template_root"
    elif scene == "design":
        safe_id = "__genui_render_component__root"
    safe_root = _node(context, safe_id)
    styles = safe_root.get("styles")
    assert isinstance(styles, dict)
    assert styles.get("padding") == 12
    if scene != "plain":
        shell_styles = _node(context, "root").get("styles")
        assert isinstance(shell_styles, dict)
        assert shell_styles.get("padding") == 0
    styles["padding"] = padding

    reporter = _run(context, rules)
    monkeypatch.setattr(pipeline, "QUALITY_VALIDATORS", [SpacingValidator()])
    pipeline_reporter = validate_card(
        dsl_text="\n".join(json.dumps(message) for message in context.dsl_messages),
        options=ValidationOptions(max_errors=500),
    )
    spacing_diagnostics = [
        item for item in pipeline_reporter.diagnostics if item.code.startswith("SPACING.")
    ]
    assert len(spacing_diagnostics) == len(reporter.diagnostics)
    for actual, expected in zip(spacing_diagnostics, reporter.diagnostics, strict=True):
        assert actual.code == expected.code
        assert actual.json_pointer == expected.json_pointer
        assert actual.actual == expected.actual
        assert actual.expected == expected.expected

    if padding == 12:
        assert not reporter.diagnostics
    else:
        assert len(reporter.diagnostics) == 1
        diagnostic = reporter.diagnostics[0]
        assert diagnostic.code == "SPACING.SAFE_MARGIN"
        index = context.components.index(safe_root)
        assert diagnostic.json_pointer == f"/updateComponents/components/{index}/styles/padding"
