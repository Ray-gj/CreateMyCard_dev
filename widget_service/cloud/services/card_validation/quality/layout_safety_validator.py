# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""检查可确定的兄弟组件矩形重叠，不推导内容最小尺寸或主轴容量。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..base import BaseValidator

_FUSION_BACKGROUND_ID = "fusionBallBackground"
_FUSION_BACKGROUND_COMPONENTS = frozenset(
    {
        "fusionBallBackground",
        "fusionBallLargeSlot",
        "fusionBallLarge",
        "fusionBallMediumSlot",
        "fusionBallMedium",
        "fusionBallSmallSlot",
        "fusionBallSmall",
        "fusionBallGlassLayer",
    }
)
_HIDDEN = frozenset({"hidden", "none"})
_LINEAR_CONTAINERS = frozenset({"Column", "List", "Row"})
_CONTENT_COMPONENTS = frozenset({"Button", "Checkbox", "List", "Progress", "Text"})
_EPSILON = 0.01


@dataclass(frozen=True)
class _Rect:
    x: float
    y: float
    width: float
    height: float


def component_pointer(index: int, key: str = "") -> str:
    suffix = f"/{key}" if key else ""
    return f"/updateComponents/components/{index}{suffix}"


def _styles(component: dict[str, Any]) -> dict[str, Any]:
    styles = component.get("styles")
    return styles if isinstance(styles, dict) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        stripped = value.strip()
        try:
            number = float(stripped.removesuffix("vp").removesuffix("px"))
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def _dimension(value: Any, parent_size: float | None) -> float | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "matchParent":
            return parent_size
        if stripped.endswith("%") and parent_size is not None:
            percentage = _number(stripped.removesuffix("%"))
            return (
                parent_size * percentage / 100.0
                if percentage is not None and percentage >= 0.0
                else None
            )
    number = _number(value)
    return number if number is not None and number >= 0.0 else None


def _spacing(value: Any) -> tuple[float, float, float, float] | None:
    if isinstance(value, dict):
        values = (
            _number(value.get("top", 0.0)),
            _number(value.get("right", 0.0)),
            _number(value.get("bottom", 0.0)),
            _number(value.get("left", 0.0)),
        )
    else:
        number = _number(value if value is not None else 0.0)
        values = (number, number, number, number)
    if any(item is None or item < 0.0 for item in values):
        return None
    top, right, bottom, left = values
    if top is None or right is None or bottom is None or left is None:
        return None
    return top, right, bottom, left


def _visible(component: dict[str, Any]) -> bool:
    visibility = _styles(component).get("visibility")
    return not isinstance(visibility, str) or visibility not in _HIDDEN


def _children(
    component: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    children = component.get("children")
    if not isinstance(children, list):
        return []
    result: list[dict[str, Any]] = []
    for child_id in children:
        if not isinstance(child_id, str):
            continue
        child = by_id.get(child_id)
        if isinstance(child, dict):
            result.append(child)
    return result


def _has_content(component: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    pending = [component]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        component_id = current.get("id")
        if not isinstance(component_id, str) or component_id in visited:
            continue
        visited.add(component_id)
        if not _visible(current):
            continue
        if current.get("component") in _CONTENT_COMPONENTS:
            return True
        pending.extend(_children(current, by_id))
    return False


def _is_fusion_scene(root: dict[str, Any], context: Any) -> bool:
    explicit = getattr(context, "fusion_ball", None)
    if isinstance(explicit, bool):
        return explicit
    children = root.get("children")
    return isinstance(children, list) and _FUSION_BACKGROUND_ID in children


def _fusion_background_ids(
    by_id: dict[str, dict[str, Any]],
) -> set[str]:
    background = by_id.get(_FUSION_BACKGROUND_ID)
    if not isinstance(background, dict):
        return set()
    ignored: set[str] = set()
    pending = [background]
    while pending:
        component = pending.pop()
        component_id = component.get("id")
        if not isinstance(component_id, str) or component_id in ignored:
            continue
        ignored.add(component_id)
        pending.extend(_children(component, by_id))
    ignored.update(_FUSION_BACKGROUND_COMPONENTS)
    return ignored


def _padding(component: dict[str, Any]) -> tuple[float, float, float, float] | None:
    return _spacing(_styles(component).get("padding"))


def _margin(component: dict[str, Any]) -> tuple[float, float, float, float] | None:
    return _spacing(_styles(component).get("margin"))


def _item_margin(component: dict[str, Any]) -> float | None:
    value = component.get("itemMargin", _styles(component).get("itemMargin", 0.0))
    number = _number(value)
    return number if number is not None and number >= 0.0 else None


def _component_size(
    component: dict[str, Any],
    parent: _Rect,
) -> tuple[float, float] | None:
    styles = _styles(component)
    width = _dimension(styles.get("width"), parent.width)
    height = _dimension(styles.get("height"), parent.height)
    if width is None or height is None:
        return None
    return width, height


def _align_offset(
    available: float,
    size: float,
    alignment: str,
) -> float | None:
    remaining = available - size
    if alignment in {"start", "top"}:
        return 0.0
    if alignment in {"end", "bottom"}:
        return remaining
    if alignment == "center":
        return remaining / 2.0
    return None


def _layout_children(
    parent: dict[str, Any],
    children: list[dict[str, Any]],
    parent_rect: _Rect,
) -> list[tuple[dict[str, Any], _Rect]] | None:
    kind = parent.get("component")
    if kind not in _LINEAR_CONTAINERS:
        return None
    padding = _padding(parent)
    item_margin = _item_margin(parent)
    if padding is None or item_margin is None:
        return None
    top, right, bottom, left = padding
    inner = _Rect(
        parent_rect.x + left,
        parent_rect.y + top,
        parent_rect.width - left - right,
        parent_rect.height - top - bottom,
    )
    if inner.width < 0.0 or inner.height < 0.0:
        return None
    sizes: list[tuple[dict[str, Any], float, float, tuple[float, float, float, float]]] = []
    for child in children:
        margin = _margin(child)
        size = _component_size(child, inner)
        if margin is None or size is None:
            return None
        sizes.append((child, size[0], size[1], margin))
    if kind == "List":
        list_direction = _styles(parent).get("listDirection", "vertical")
        if list_direction not in {"vertical", "horizontal"}:
            return None
        horizontal = list_direction == "horizontal"
    else:
        horizontal = kind == "Row"
    main_available = inner.width if horizontal else inner.height
    main_sizes = [item[1] if horizontal else item[2] for item in sizes]
    main_margins = [
        item[3][3] + item[3][1] if horizontal else item[3][0] + item[3][2]
        for item in sizes
    ]
    base = sum(main_sizes) + sum(main_margins) + item_margin * max(len(sizes) - 1, 0)
    justify = _styles(parent).get("justifyContent", "start")
    if kind == "List":
        justify = "start"
    if not isinstance(justify, str):
        return None
    remaining = main_available - base
    if justify == "start":
        leading = 0.0
        extra_gap = 0.0
    elif justify == "center":
        leading = remaining / 2.0
        extra_gap = 0.0
    elif justify == "end":
        leading = remaining
        extra_gap = 0.0
    elif justify == "spaceBetween" and len(sizes) > 1:
        leading = 0.0
        extra_gap = max(remaining, 0.0) / (len(sizes) - 1)
    elif justify == "spaceAround" and sizes:
        extra_gap = max(remaining, 0.0) / len(sizes)
        leading = extra_gap / 2.0
    elif justify == "spaceEvenly" and sizes:
        extra_gap = max(remaining, 0.0) / (len(sizes) + 1)
        leading = extra_gap
    else:
        return None
    result: list[tuple[dict[str, Any], _Rect]] = []
    cursor = leading
    default_alignment = "top" if horizontal else "start"
    cross_alignment = _styles(parent).get("alignItems", default_alignment)
    if kind == "List":
        cross_alignment = default_alignment
    if not isinstance(cross_alignment, str):
        return None
    for index, (child, width, height, margin) in enumerate(sizes):
        if horizontal:
            x = inner.x + cursor + margin[3]
            cross = _align_offset(inner.height - margin[0] - margin[2], height, cross_alignment)
            if cross is None:
                return None
            rect = _Rect(x, inner.y + margin[0] + cross, width, height)
            cursor += width + margin[1] + margin[3]
        else:
            y = inner.y + cursor + margin[0]
            cross = _align_offset(inner.width - margin[1] - margin[3], width, cross_alignment)
            if cross is None:
                return None
            rect = _Rect(inner.x + margin[3] + cross, y, width, height)
            cursor += height + margin[0] + margin[2]
        if index + 1 < len(sizes):
            cursor += item_margin + extra_gap
        result.append((child, rect))
    return result


def _layout_stack_children(
    parent: dict[str, Any],
    children: list[dict[str, Any]],
    parent_rect: _Rect,
    by_id: dict[str, dict[str, Any]],
) -> list[tuple[dict[str, Any], _Rect]] | None:
    alignment = _styles(parent).get("alignContent", "center")
    if not isinstance(alignment, str):
        return None
    result: list[tuple[dict[str, Any], _Rect]] = []
    for child in children:
        if not _has_content(child, by_id):
            continue
        margin = _margin(child)
        size = _component_size(child, parent_rect)
        if margin is None or size is None:
            return None
        horizontal = "end" if alignment.endswith("End") else "start"
        if alignment in {"top", "center", "bottom"}:
            horizontal = "center"
        vertical = "bottom" if alignment.startswith("bottom") else "top"
        if alignment in {"start", "center", "end"}:
            vertical = "center"
        x_offset = _align_offset(parent_rect.width - margin[1] - margin[3], size[0], horizontal)
        y_offset = _align_offset(parent_rect.height - margin[0] - margin[2], size[1], vertical)
        if x_offset is None or y_offset is None:
            return None
        result.append(
            (
                child,
                _Rect(
                    parent_rect.x + margin[3] + x_offset,
                    parent_rect.y + margin[0] + y_offset,
                    size[0],
                    size[1],
                ),
            )
        )
    return result


def _intersection(left: _Rect, right: _Rect) -> _Rect | None:
    x = max(left.x, right.x)
    y = max(left.y, right.y)
    right_edge = min(left.x + left.width, right.x + right.width)
    bottom_edge = min(left.y + left.height, right.y + right.height)
    width = right_edge - x
    height = bottom_edge - y
    if width <= _EPSILON or height <= _EPSILON:
        return None
    return _Rect(x, y, width, height)


def _rect_json(rect: _Rect) -> dict[str, float]:
    return {
        "x": round(rect.x, 4),
        "y": round(rect.y, 4),
        "width": round(rect.width, 4),
        "height": round(rect.height, 4),
    }


class LayoutSafetyValidator(BaseValidator):
    stage = "quality"
    name = "layout_safety"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        by_id = context.components_by_id
        root = by_id.get(context.root_id)
        if not isinstance(root, dict) or not isinstance(context.root_id, str):
            return
        root_rect = self._root_rect(context, root, rules)
        if root_rect is None:
            return
        fusion_scene = _is_fusion_scene(root, context)
        ignored = _fusion_background_ids(by_id) if fusion_scene else set()
        indexes = {
            component.get("id"): index
            for index, component in enumerate(context.components)
            if isinstance(component.get("id"), str)
        }
        self._walk(root, root_rect, by_id, indexes, ignored, fusion_scene, reporter, set())

    @staticmethod
    def _root_rect(context: Any, root: dict[str, Any], rules: Any) -> _Rect | None:
        surface = context.create_surface if isinstance(context.create_surface, dict) else {}
        surface_width = _number(surface.get("width"))
        surface_height = _number(surface.get("height"))
        size_name = (
            context.cardspec.get("suggestSize")
            if isinstance(context.cardspec, dict)
            else None
        )
        protocol = getattr(rules, "protocol", {})
        protocol = protocol if isinstance(protocol, dict) else {}
        sizes = protocol.get("sizes", {})
        configured_size = sizes.get(size_name) if isinstance(sizes, dict) else None
        if isinstance(configured_size, dict):
            surface_width = surface_width or _number(configured_size.get("width"))
            surface_height = surface_height or _number(configured_size.get("height"))
        width = _dimension(_styles(root).get("width"), surface_width)
        height = _dimension(_styles(root).get("height"), surface_height)
        if width is None or height is None:
            return None
        return _Rect(0.0, 0.0, width, height)

    def _walk(
        self,
        component: dict[str, Any],
        rect: _Rect,
        by_id: dict[str, dict[str, Any]],
        indexes: dict[str, int],
        ignored: set[str],
        fusion_scene: bool,
        reporter: Any,
        path: set[str],
    ) -> None:
        component_id = component.get("id")
        if not isinstance(component_id, str) or component_id in ignored or component_id in path:
            return
        if not _visible(component):
            return
        next_path = path | {component_id}
        children = [
            child
            for child in _children(component, by_id)
            if child.get("id") not in ignored and _visible(child)
        ]
        kind = component.get("component")
        if kind in _LINEAR_CONTAINERS:
            laid_out = _layout_children(component, children, rect)
        elif kind == "Stack":
            laid_out = _layout_stack_children(component, children, rect, by_id)
        else:
            laid_out = None
        if laid_out is None:
            return
        self._report_overlaps(component, laid_out, indexes, reporter, fusion_scene)
        for child, child_rect in laid_out:
            self._walk(
                child,
                child_rect,
                by_id,
                indexes,
                ignored,
                fusion_scene,
                reporter,
                next_path,
            )

    @staticmethod
    def _report_overlaps(
        parent: dict[str, Any],
        laid_out: list[tuple[dict[str, Any], _Rect]],
        indexes: dict[str, int],
        reporter: Any,
        fusion_scene: bool,
    ) -> None:
        parent_id = parent.get("id")
        parent_index = indexes.get(parent_id)
        if not isinstance(parent_id, str) or parent_index is None:
            return
        for left_index, (left, left_rect) in enumerate(laid_out):
            left_id = left.get("id")
            if not isinstance(left_id, str):
                continue
            for right, right_rect in laid_out[left_index + 1 :]:
                right_id = right.get("id")
                if not isinstance(right_id, str):
                    continue
                intersection = _intersection(left_rect, right_rect)
                if intersection is None:
                    continue
                actual = {
                    "parent": parent_id,
                    "children": [left_id, right_id],
                    "rects": {
                        left_id: _rect_json(left_rect),
                        right_id: _rect_json(right_rect),
                    },
                    "intersection": _rect_json(intersection),
                    "scene": "fusionBall" if fusion_scene else "normal",
                    "geometrySource": "static_layout",
                }
                reporter.add(
                    "error",
                    "LAYOUT.SIBLING_OVERLAP",
                    "quality",
                    "genui",
                    line=2,
                    json_pointer=component_pointer(parent_index, "children"),
                    actual=actual,
                    expected="同一父组件下的可见兄弟组件矩形不得发生面积重叠",
                    message=(
                        f"{parent_id} 的兄弟组件 {left_id} 与 {right_id} 的布局矩形发生重叠，"
                        f"交叠区域为 {_format_size(intersection)}。"
                    ),
                    fix_hint=(
                        f"请调整 {left_id} 和 {right_id} 的尺寸、顺序、间距或对齐方式，"
                        "保持业务内容、动态绑定和组件层级不变；不要删除、隐藏或裁剪内容。"
                    ),
                    source="layout-safety",
                )


def _format_size(rect: _Rect) -> str:
    return f"{rect.width:g}×{rect.height:g}vp"
