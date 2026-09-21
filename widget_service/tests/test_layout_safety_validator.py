# -*- coding: utf-8 -*-
"""兄弟组件矩形重叠校验回归。"""

import json
from typing import Any

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


def _text(identifier: str, width: float = 80, height: float = 20) -> dict[str, Any]:
    return _component(
        identifier,
        "Text",
        styles={"width": width, "height": height, "fontSize": 12},
        content=identifier,
    )


def test_detects_overlapping_content_branches_in_stack() -> None:
    components = [
        _component(
            "root",
            "Stack",
            children=["background", "primary", "secondary"],
            styles={"width": 136, "height": 100, "alignContent": "center"},
        ),
        _component("background", "Image", styles={"width": 136, "height": 100}),
        _text("primary"),
        _text("secondary"),
    ]

    reporter = validate_card(dsl_text=_dsl(components))

    diagnostics = [
        item for item in reporter.diagnostics if item.code == "LAYOUT.SIBLING_OVERLAP"
    ]
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.actual["parent"] == "root"
    assert diagnostic.actual["children"] == ["primary", "secondary"]
    assert diagnostic.actual["intersection"] == {
        "x": 28.0,
        "y": 40.0,
        "width": 80.0,
        "height": 20.0,
    }


def test_fusion_background_is_ignored_but_foreground_is_checked() -> None:
    components = [
        _component(
            "root",
            "Stack",
            children=["fusionBallBackground", "__genui_render_component__root"],
            styles={"width": 160, "height": 160, "alignContent": "topStart"},
        ),
        _component(
            "fusionBallBackground",
            "Stack",
            children=["fusionBallLarge", "fusionBallGlassLayer"],
            styles={"width": "100%", "height": "100%"},
        ),
        _component(
            "fusionBallLarge",
            "Divider",
            styles={"width": 160, "height": 160},
        ),
        _component(
            "fusionBallGlassLayer",
            "Divider",
            styles={"width": 160, "height": 160},
        ),
        _component(
            "__genui_render_component__root",
            "Column",
            children=["title", "value"],
            itemMargin=8,
            styles={"width": "matchParent", "height": "matchParent"},
        ),
        _text("title", height=20),
        _text("value", height=20),
    ]

    reporter = validate_card(dsl_text=_dsl(components))

    assert not reporter.has_code("LAYOUT.SIBLING_OVERLAP")


def test_hidden_siblings_do_not_participate() -> None:
    components = [
        _component(
            "root",
            "Stack",
            children=["hidden", "visible"],
            styles={"width": 136, "height": 100},
        ),
        _component(
            "hidden",
            "Text",
            styles={"width": 80, "height": 20, "visibility": "hidden"},
            content="隐藏",
        ),
        _text("visible"),
    ]

    reporter = validate_card(dsl_text=_dsl(components))

    assert not reporter.has_code("LAYOUT.SIBLING_OVERLAP")


def test_unknown_geometry_is_skipped() -> None:
    components = [
        _component(
            "root",
            "Stack",
            children=["first", "second"],
            styles={"width": 136, "height": 100},
        ),
        _component("first", "Text", content="一"),
        _component("second", "Text", content="二"),
    ]

    reporter = validate_card(dsl_text=_dsl(components))

    assert not reporter.has_code("LAYOUT.SIBLING_OVERLAP")


def test_match_parent_root_uses_cardspec_canvas_size() -> None:
    components = [
        _component(
            "root",
            "Stack",
            children=["first", "second"],
            styles={"width": "matchParent", "height": "matchParent"},
        ),
        _text("first"),
        _text("second"),
    ]
    cardspec = {
        "title": "测试",
        "description": "重叠校验",
        "suggestSize": "2x2",
        "dataBindings": [],
    }

    reporter = validate_card(
        dsl_text=_dsl(components),
        cardspec=json.dumps(cardspec, ensure_ascii=False),
    )

    assert reporter.has_code("LAYOUT.SIBLING_OVERLAP")


def test_linear_children_are_checked_recursively_when_geometry_is_known() -> None:
    components = [
        _component(
            "root",
            "Column",
            children=["content"],
            styles={"width": 136, "height": 100},
        ),
        _component(
            "content",
            "Stack",
            children=["first", "second"],
            styles={"width": 136, "height": 100},
        ),
        _text("first"),
        _text("second"),
    ]

    reporter = validate_card(dsl_text=_dsl(components))

    diagnostic = next(
        item for item in reporter.diagnostics if item.code == "LAYOUT.SIBLING_OVERLAP"
    )
    assert diagnostic.actual["parent"] == "content"
    assert diagnostic.fix_hint.startswith("请调整 first 和 second")
