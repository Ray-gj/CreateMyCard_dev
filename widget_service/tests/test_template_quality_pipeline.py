"""模板标记的公共质量阶段门禁回归。"""

import json
import logging
from typing import Any
from unittest.mock import Mock

import pytest

from services.card_validation import ValidationOptions, pipeline, validate_card


def _components(marker: str = "template_root", fusion: bool = True) -> list[dict[str, Any]]:
    children = [marker, "external"]
    if fusion:
        children.append("fusionBallBackground")
    return [
        {"id": "root", "component": "Column", "children": children},
        {"id": marker, "component": "Column", "children": ["label"]},
        {"id": "label", "component": "Text", "content": "模板内容"},
        {"id": "external", "component": "Text", "content": "template_root"},
        {"id": "fusionBallBackground", "component": "Divider"},
    ]


def _dsl(components: list[dict[str, Any]], root: str = "root") -> str:
    messages = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "card",
                "catalogId": "ohos.a2ui.extended.catalog.form",
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "card", "root": root, "components": components,
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {"surfaceId": "card", "path": "/", "value": {"ready": True}},
        },
    ]
    return "\n".join(json.dumps(message) for message in messages)


@pytest.fixture
def quality_spy(monkeypatch: pytest.MonkeyPatch) -> Mock:
    validator = Mock(stage="quality")
    monkeypatch.setattr(pipeline, "QUALITY_VALIDATORS", [validator])
    return validator.validate


@pytest.mark.parametrize("stage", ["all", "quality"])
@pytest.mark.parametrize("fusion", [False, True])
def test_template_runs_quality_stage(
    quality_spy: Mock, caplog: pytest.LogCaptureFixture, stage: str, fusion: bool,
) -> None:
    components = _components(fusion=fusion)
    with caplog.at_level(logging.INFO, logger=pipeline.__name__):
        reporter = validate_card(dsl_text=_dsl(components), options=ValidationOptions(stage=stage))
    quality_spy.assert_called_once()
    assert "quality_validation_skipped" not in caplog.text
    assert reporter.quality_score is None


@pytest.mark.parametrize("marker", [
    "regular", "template_root_1", "Template_root", "__genui_render_component__template_root",
])
def test_non_template_runs_quality(quality_spy: Mock, marker: str) -> None:
    validate_card(dsl_text=_dsl(_components(marker)))
    quality_spy.assert_called_once()


@pytest.mark.parametrize("case", ["orphan", "missing", "nested", "duplicate", "other_root"])
def test_invalid_template_marker_does_not_skip_quality(quality_spy: Mock, case: str) -> None:
    components = _components()
    root = "root"
    if case == "orphan":
        components[0]["children"] = ["external"]
    elif case == "missing":
        components.pop(1)
    elif case == "nested":
        components[0]["children"] = ["wrapper", "external"]
        components.append({"id": "wrapper", "component": "Column", "children": ["template_root"]})
    elif case == "duplicate":
        components.append({"id": "template_root", "component": "Text", "content": "重复"})
    else:
        root = "other_root"
        components[0]["id"] = root
    validate_card(dsl_text=_dsl(components, root))
    quality_spy.assert_called_once()


def test_parse_failure_does_not_run_quality(quality_spy: Mock) -> None:
    reporter = validate_card(dsl_text="{template_root")
    assert reporter.has_code("DSL_JSON_PARSE_FAILED")
    quality_spy.assert_not_called()


@pytest.mark.parametrize("case", ["missing", "text_only", "similar", "duplicate", "nested"])
def test_invalid_background_does_not_skip_quality(quality_spy: Mock, case: str) -> None:
    components = _components()
    if case in {"missing", "text_only"}:
        components.pop()
        if case == "text_only":
            components[3]["content"] = "fusionBallBackground template_root"
    elif case == "similar":
        components[-1]["id"] = "fusionBallBackground_1"
    elif case == "duplicate":
        components.append({"id": "fusionBallBackground", "component": "Divider"})
    else:
        components[0]["children"] = ["template_root", "external"]
        components[1]["children"] = ["label", "fusionBallBackground"]
    validate_card(dsl_text=_dsl(components))
    quality_spy.assert_called_once()


@pytest.mark.parametrize("remove", ["template_root", "fusionBallBackground"])
def test_revalidation_rechecks_both_markers(quality_spy: Mock, remove: str) -> None:
    components = _components()
    validate_card(dsl_text=_dsl(components))
    quality_spy.assert_called_once()
    quality_spy.reset_mock()
    remaining = []
    for component in components:
        if component.get("id") != remove:
            remaining.append(component)
    validate_card(dsl_text=_dsl(remaining))
    quality_spy.assert_called_once()


def test_revalidation_rechecks_marker(quality_spy: Mock) -> None:
    validate_card(dsl_text=_dsl(_components()))
    quality_spy.assert_called_once()
    quality_spy.reset_mock()
    validate_card(dsl_text=_dsl(_components("regular")))
    quality_spy.assert_called_once()


@pytest.mark.parametrize(("field", "value", "code"), [
    ("component", "Unsupported", "DSL_COMPONENT_UNKNOWN"),
    ("content", "{{ ${/data/missing} }}", "BINDING_PATH_NOT_FOUND"),
    ("content", "😀", "ASSET.EMOJI_ICON"),
    ("onClick", [{"call": "unknownAction", "args": {}}], "EVENT_CAPABILITY_UNKNOWN"),
])
def test_template_retains_non_quality_checks(
    quality_spy: Mock, field: str, value: Any, code: str,
) -> None:
    components = _components()
    components[2][field] = value
    reporter = validate_card(dsl_text=_dsl(components))
    assert reporter.has_code(code)
    quality_spy.assert_called_once()
