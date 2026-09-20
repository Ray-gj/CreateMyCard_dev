# -*- coding: utf-8 -*-
"""线性布局安全校验回归。"""

import json
from typing import Any

import pytest

from services.card_validation import validate_card


def _dsl(components: list[dict[str, Any]]) -> str:
    messages = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "surface_card",
                "catalogId": "ohos.a2ui.extended.catalog.form",
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "surface_card",
                "root": "root",
                "components": components,
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "surface_card",
                "path": "/",
                "value": {"data": {}},
            },
        },
    ]
    return "\n".join(json.dumps(message, ensure_ascii=False) for message in messages)


def _component(
    identifier: str,
    kind: str,
    *,
    children: list[str] | None = None,
    styles: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    component: dict[str, Any] = {
        "id": identifier,
        "component": kind,
        "styles": styles or {},
    }
    if children is not None:
        component["children"] = children
    component.update(extra)
    return component


def _title_area() -> list[dict[str, Any]]:
    return [
        _component(
            "title_area",
            "Row",
            children=["title_text"],
            styles={"width": 136, "height": 20},
        ),
        _component(
            "title_text",
            "Text",
            styles={"width": 112, "fontSize": 12, "maxLines": 1},
            content="标题",
        ),
    ]


def _text(identifier: str, font_size: int) -> dict[str, Any]:
    return _component(
        identifier,
        "Text",
        styles={"fontSize": font_size, "maxLines": 1},
        content="内容",
    )


def _button(identifier: str) -> dict[str, Any]:
    return _component(
        identifier,
        "Button",
        styles={"width": "matchParent", "height": 36},
        label="查看详情",
    )


def _first_components() -> list[dict[str, Any]]:
    components = [
        _component(
            "root",
            "Column",
            children=["title_area", "value_group", "action_area"],
            itemMargin=8,
            styles={"width": 160, "height": 160, "padding": 12},
        ),
        *_title_area(),
        _component(
            "value_group",
            "Column",
            children=["value_num", "value_unit", "start_time"],
            itemMargin=2,
            styles={"width": 136, "height": 64},
        ),
        _text("value_num", 38),
        _text("value_unit", 12),
        _text("start_time", 12),
        _component(
            "action_area",
            "Column",
            children=["action_unit"],
            styles={"width": 136, "height": 36},
        ),
        _button("action_unit"),
    ]
    return components


def _second_components() -> list[dict[str, Any]]:
    components = [
        _component(
            "root",
            "Stack",
            children=["fusionBallBackground", "__genui_render_component__root"],
            styles={"width": 160, "height": 160},
        ),
        _component(
            "fusionBallBackground",
            "Stack",
            styles={"width": "100%", "height": "100%"},
        ),
        _component(
            "__genui_render_component__root",
            "Column",
            children=["title_area", "value_group", "action_area"],
            itemMargin=8,
            styles={"width": "matchParent", "height": "matchParent", "padding": 12},
        ),
        *_title_area(),
        _component(
            "value_group",
            "Column",
            children=["value_num", "value_unit", "aux_text"],
            itemMargin=2,
            styles={"width": 136, "layoutWeight": 1},
        ),
        _text("value_num", 38),
        _text("value_unit", 12),
        _text("aux_text", 12),
        _component(
            "action_area",
            "Column",
            children=["action"],
            styles={"width": 136, "height": 36},
        ),
        _button("action"),
    ]
    return components


def _third_components() -> list[dict[str, Any]]:
    components = [
        _component(
            "root",
            "Column",
            children=["title_area", "content_area", "action_area"],
            itemMargin=4,
            styles={"width": 160, "height": 160, "padding": 12},
        ),
        *_title_area(),
        _component(
            "content_area",
            "Column",
            children=["value_row", "aux_text"],
            itemMargin=4,
            styles={"width": 136, "layoutWeight": 1},
        ),
        _component("value_row", "Row", children=["value_num", "value_unit"], styles={"width": 136}),
        _text("value_num", 30),
        _text("value_unit", 12),
        _text("aux_text", 12),
        _component(
            "action_area",
            "Column",
            children=["cta_save", "cta_nav"],
            itemMargin=8,
            styles={"width": 136},
        ),
        _button("cta_save"),
        _button("cta_nav"),
    ]
    return components


@pytest.mark.parametrize(
    ("components", "container", "required"),
    [
        (_first_components(), "value_group", 78.4),
        (_second_components(), "__genui_render_component__root", 150.4),
        (_third_components(), "root", 162.4),
    ],
)
def test_detects_linear_content_overflow(
    components: list[dict[str, Any]],
    container: str,
    required: float,
) -> None:
    reporter = validate_card(dsl_text=_dsl(components))
    diagnostics = [
        item
        for item in reporter.diagnostics
        if item.code == "LAYOUT.LINEAR_CONTENT_OVERFLOW"
        and item.actual.get("container") == container
    ]

    assert len(diagnostics) == 1
    assert diagnostics[0].actual.get("required") == pytest.approx(required)


def test_resolves_match_parent_for_row_child() -> None:
    components = [
        _component(
            "root",
            "Row",
            children=["left", "right"],
            itemMargin=8,
            styles={"width": 100, "height": 40, "padding": 4},
        ),
        _component("left", "Column", children=["text"], styles={"width": "matchParent"}),
        _text("text", 12),
        _component("right", "Column", children=["button"], styles={"width": 60}),
        _button("button"),
    ]

    reporter = validate_card(dsl_text=_dsl(components))

    assert reporter.has_code("LAYOUT.LINEAR_CONTENT_OVERFLOW")


def test_overflow_feedback_identifies_font_size_leaf_as_local_edit_target() -> None:
    components = [
        _component(
            "root",
            "Column",
            children=["a", "b", "c"],
            itemMargin=4,
            styles={"width": 136, "height": 100, "padding": 8},
        ),
        _component("a", "Text", styles={"height": 16, "fontSize": 12}, content="标题"),
        _component("b", "Column", children=["b1", "b2", "b3"], itemMargin=2, styles={"width": 136}),
        _component("b1", "Text", styles={"fontSize": 32, "maxLines": 1}, content="主数值"),
        _component("b2", "Text", styles={"height": 18, "fontSize": 14}, content="说明"),
        _component("b3", "Button", styles={"width": 100, "height": 32}, label="查看"),
        _component("c", "Text", styles={"height": 16, "fontSize": 12}, content="底部"),
    ]

    reporter = validate_card(dsl_text=_dsl(components))
    diagnostic = next(
        item
        for item in reporter.diagnostics
        if item.code == "LAYOUT.LINEAR_CONTENT_OVERFLOW"
        and item.actual.get("container") == "root"
    )

    assert "b1" in diagnostic.actual["recommendedEditTargets"]
    assert diagnostic.actual["sizeSources"]
    assert "fontSize" in {
        item["sizeSource"] for item in diagnostic.actual["sizeSources"] if item["component"] == "b1"
    }
    assert "优先处理" in diagnostic.fix_hint
