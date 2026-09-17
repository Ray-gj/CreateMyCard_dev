# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""检查文字分区和线性布局空间，不模拟端侧字形测量。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..base import BaseValidator


def component_pointer(index: int, key: str = "") -> str:
    suffix = f"/{key}" if key else ""
    return f"/updateComponents/components/{index}{suffix}"


def children_of(
    component: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    children = component.get("children")
    if not isinstance(children, list):
        return []
    return [
        by_id[child]
        for child in children
        if isinstance(child, str) and child in by_id
    ]

_ALIGNMENTS = {
    "topStart": (0.0, 0.0),
    "top": (0.5, 0.0),
    "topEnd": (1.0, 0.0),
    "start": (0.0, 0.5),
    "center": (0.5, 0.5),
    "end": (1.0, 0.5),
    "bottomStart": (0.0, 1.0),
    "bottom": (0.5, 1.0),
    "bottomEnd": (1.0, 1.0),
}
_HIDDEN = {"hidden", "none"}


@dataclass(frozen=True)
class _Slot:
    component_id: str
    horizontal: tuple[float, float] | None
    vertical: tuple[float, float] | None


def _styles(component: dict[str, Any]) -> dict[str, Any]:
    value = component.get("styles")
    return value if isinstance(value, dict) else {}


def _finite_number(value: Any) -> float | None:
    result: float | None = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            candidate = float(value)
        except OverflowError:
            return result
        if math.isfinite(candidate):
            result = candidate
    return result


def _visible(component: dict[str, Any]) -> bool:
    visibility = _styles(component).get("visibility")
    return not isinstance(visibility, str) or visibility not in _HIDDEN


def _has_label(component: dict[str, Any]) -> bool:
    kind = component.get("component")
    if not isinstance(kind, str) or kind not in {"Text", "Button"}:
        return False
    key = "content" if kind == "Text" else "label"
    value = component.get(key)
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, dict) and bool(value)


def _children(component: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    children = children_of(component, by_id)
    template = component.get("children")
    if isinstance(template, dict):
        template_id = template.get("componentId")
        if isinstance(template_id, str):
            child = by_id.get(template_id)
            if isinstance(child, dict):
                children.append(child)
    return children


def _contains_label(component: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    pending = [component]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        current_id = current.get("id")
        if not isinstance(current_id, str) or current_id in visited:
            continue
        visited.add(current_id)
        if not _visible(current):
            continue
        if _has_label(current):
            return True
        pending.extend(_children(current, by_id))
    return False


def _margin(styles: dict[str, Any], edge: str) -> float | None:
    value = styles.get("margin", 0.0)
    if isinstance(value, dict):
        value = value.get(edge, 0.0)
    return _finite_number(value)


def _axis_interval(
    styles: dict[str, Any], dimension: str, edges: tuple[str, str], anchor: float
) -> tuple[float, float] | None:
    interval: tuple[float, float] | None = None
    size = _finite_number(styles.get(dimension))
    before = _margin(styles, edges[0])
    after = _margin(styles, edges[1])
    if size is None or before is None or after is None:
        return interval
    if size <= 0.0 or before < 0.0 or after < 0.0:
        return interval
    # 兄弟共享父级锚点，因此相对锚点计算即可，无需猜测父容器的自适应尺寸。
    start = before - anchor * (size + before + after)
    end = start + size
    if math.isfinite(start) and math.isfinite(end):
        interval = (start, end)
    return interval


def _slot(component: dict[str, Any], alignment: Any) -> _Slot:
    component_id = component.get("id")
    if not isinstance(component_id, str):
        raise ValueError("文字分支必须具有字符串 id")
    horizontal: tuple[float, float] | None = None
    vertical: tuple[float, float] | None = None
    anchors = _ALIGNMENTS.get(alignment) if isinstance(alignment, str) else None
    if anchors is not None:
        styles = _styles(component)
        horizontal = _axis_interval(styles, "width", ("left", "right"), anchors[0])
        vertical = _axis_interval(styles, "height", ("top", "bottom"), anchors[1])
    return _Slot(component_id, horizontal, vertical)


def _separated(left: tuple[float, float] | None, right: tuple[float, float] | None) -> bool:
    if left is None or right is None:
        return False
    return left[1] <= right[0] or right[1] <= left[0]


def _padding(styles: dict[str, Any], edge: str) -> float:
    value = styles.get("padding", 0.0)
    if isinstance(value, dict):
        value = value.get(edge, 0.0)
    result = _finite_number(value)
    return result if result is not None and result >= 0.0 else 0.0


def _item_margin(styles: dict[str, Any]) -> float:
    value = _finite_number(styles.get("itemMargin", 0.0))
    return value if value is not None and value >= 0.0 else 0.0


def _declared_size(component: dict[str, Any], axis: str) -> float | None:
    value = _finite_number(_styles(component).get(axis))
    return value if value is not None and value > 0.0 else None


def _text_minimum_height(component: dict[str, Any]) -> float | None:
    styles = _styles(component)
    declared = _declared_size(component, "height")
    if declared is not None:
        return declared
    font_size = _finite_number(styles.get("fontSize"))
    if font_size is None or font_size <= 0.0:
        return None
    max_lines = _finite_number(styles.get("maxLines", 1))
    lines = max_lines if max_lines is not None and max_lines > 0.0 else 1.0
    return font_size * 1.2 * lines


def _minimum_size(
    component: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    visiting: set[str] | None = None,
) -> tuple[float | None, float | None]:
    styles = _styles(component)
    declared_width = _declared_size(component, "width")
    declared_height = _declared_size(component, "height")
    kind = component.get("component")
    if kind == "Text":
        return declared_width, _text_minimum_height(component)
    if kind == "Button":
        return declared_width, declared_height or _text_minimum_height(component)
    children = _children(component, by_id)
    if not children:
        return declared_width, declared_height
    current_id = component.get("id")
    active = set() if visiting is None else set(visiting)
    if isinstance(current_id, str):
        if current_id in active:
            return declared_width, declared_height
        active.add(current_id)
    measures = [_minimum_size(child, by_id, active) for child in children]
    child_widths = [item[0] for item in measures if item[0] is not None]
    child_heights = [item[1] for item in measures if item[1] is not None]
    margin = _item_margin(styles) * max(len(children) - 1, 0)
    if kind == "Column":
        minimum_height = (
            sum(child_heights) + margin if len(child_heights) == len(children) else None
        )
        minimum_width = max(child_widths) if len(child_widths) == len(children) else None
        return declared_width or (
            minimum_width
            + _padding(styles, "left")
            + _padding(styles, "right")
            if minimum_width is not None
            else None
        ), declared_height or (
            minimum_height
            + _padding(styles, "top")
            + _padding(styles, "bottom")
            if minimum_height is not None
            else None
        )
    if kind == "Row":
        minimum_width = (
            sum(child_widths) + margin if len(child_widths) == len(children) else None
        )
        minimum_height = max(child_heights) if len(child_heights) == len(children) else None
        return declared_width or (
            minimum_width
            + _padding(styles, "left")
            + _padding(styles, "right")
            if minimum_width is not None
            else None
        ), declared_height or (
            minimum_height
            + _padding(styles, "top")
            + _padding(styles, "bottom")
            if minimum_height is not None
            else None
        )
    return declared_width, declared_height


class LayoutSafetyValidator(BaseValidator):
    stage = "quality"
    name = "layout_safety"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        by_id = context.components_by_id
        root = by_id.get(context.root_id)
        if not isinstance(root, dict):
            return
        indexes: dict[str, int] = {}
        for index, component in enumerate(context.components):
            component_id = component.get("id")
            if isinstance(component_id, str):
                indexes[component_id] = index
        pending = [root]
        visited: set[str] = set()
        while pending:
            component = pending.pop()
            component_id = component.get("id")
            if not isinstance(component_id, str) or component_id in visited:
                continue
            visited.add(component_id)
            if not _visible(component):
                continue
            children = _children(component, by_id)
            pending.extend(reversed(children))
            index = indexes.get(component_id)
            kind = component.get("component")
            if kind == "Stack" and index is not None:
                self._check_stack(component, children, by_id, index, reporter)
            elif kind in {"Column", "Row"} and index is not None:
                self._check_linear_layout(component, children, by_id, index, reporter)

    @staticmethod
    def _check_linear_layout(
        component: dict[str, Any],
        children: list[dict[str, Any]],
        by_id: dict[str, dict[str, Any]],
        index: int,
        reporter: Any,
    ) -> None:
        if not children:
            return
        styles = _styles(component)
        kind = component.get("component")
        axis = "height" if kind == "Column" else "width"
        declared = _declared_size(component, axis)
        if declared is None:
            return
        before = _padding(styles, "top" if axis == "height" else "left")
        after = _padding(styles, "bottom" if axis == "height" else "right")
        available = declared - before - after
        if available < 0.0:
            return
        child_sizes = []
        for child in children:
            minimum_width, minimum_height = _minimum_size(child, by_id)
            size = minimum_height if axis == "height" else minimum_width
            if size is None:
                return
            child_sizes.append((child, size))
        required = sum(size for _, size in child_sizes)
        required += _item_margin(styles) * max(len(child_sizes) - 1, 0)
        if required <= available:
            return
        overflow = required - available
        conflict_ids = [child.get("id") for child, _ in child_sizes]
        reporter.add(
            "error",
            "LAYOUT.LINEAR_CONTENT_OVERFLOW",
            "quality",
            "genui",
            line=2,
            json_pointer=component_pointer(index, "children"),
            actual={
                "container": component.get("id"),
                "axis": axis,
                "available": available,
                "required": required,
                "overflow": overflow,
                "children": conflict_ids,
            },
            expected="线性容器的子树最小尺寸、间距和 padding 不超过可用主轴空间",
            message=(
                f"{kind} {component.get('id')} 的子内容最小{axis}度为 {required:g}，"
                f"可用{axis}度为 {available:g}，存在 {overflow:g} 的挤压或重叠风险。"
            ),
            fix_hint=(
                f"请调整 {kind} {component.get('id')} 的固定尺寸、padding、itemMargin "
                "或子节点布局，确保文字和按钮的最小内容尺寸能够完整容纳。"
                "不要仅通过裁剪、隐藏内容或盲目增加 flexShrink 消除问题。"
            ),
            source="layout-safety",
        )

    @staticmethod
    def _check_stack(
        component: dict[str, Any],
        children: list[dict[str, Any]],
        by_id: dict[str, dict[str, Any]],
        index: int,
        reporter: Any,
    ) -> None:
        alignment = _styles(component).get("alignContent", "center")
        slots: list[_Slot] = []
        seen: set[str] = set()
        for child in children:
            child_id = child.get("id")
            if not isinstance(child_id, str) or child_id in seen:
                continue
            seen.add(child_id)
            if _contains_label(child, by_id):
                slots.append(_slot(child, alignment))
        conflicts: list[list[str]] = []
        for left_index, left in enumerate(slots):
            for right_index in range(left_index + 1, len(slots)):
                right = slots[right_index]
                if _separated(left.horizontal, right.horizontal):
                    continue
                if _separated(left.vertical, right.vertical):
                    continue
                conflicts.append([left.component_id, right.component_id])
        if not conflicts:
            return
        reporter.add(
            "error",
            "LAYOUT.STACK_CONTENT_FLOW",
            "quality",
            "genui",
            line=2,
            json_pointer=component_pointer(index, "children"),
            actual={"stack": component.get("id"), "conflictingBranches": conflicts},
            expected="单一文字前景容器，或可证明互不相交的文字分支槽位",
            message="Stack 内多个文字前景分支缺少可验证的安全分区，存在内容重叠风险。",
            fix_hint=(
                f"Stack {component.get('id')} 的文字分支 {conflicts} 需要重新分区："
                "纵向内容合并到 Column，横向内容合并到 Row；背景可继续放在 Stack。"
                "layoutWeight 和子容器 justifyContent 不会将 Stack 兄弟按顺序排开。"
                "保留文字内容和可读字号，不通过裁剪或隐藏内容消除问题。"
            ),
            source="layout-safety",
        )
