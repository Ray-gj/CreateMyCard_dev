from __future__ import annotations

from typing import Any

from ..base import BaseValidator, numeric
from .common import add, children_of, component_pointer


class Layout2x4Validator(BaseValidator):
    stage = "quality"
    name = "layout_2x4"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        if getattr(context, "card_size", None) != "2x4":
            return
        by_id = context.components_by_id
        for index, component in enumerate(context.components):
            if not isinstance(component, dict) or component.get("component") not in {
                "Row",
                "Column",
            }:
                continue
            children = children_of(component, by_id)
            styles = component.get("styles")
            if not isinstance(styles, dict) or len(children) < 2:
                continue
            dimension_key = "width" if component.get("component") == "Row" else "height"
            parent = numeric(styles.get(dimension_key))
            values = [numeric((child.get("styles") or {}).get(dimension_key)) for child in children]
            if parent is None or any(value is None for value in values):
                continue
            gap = numeric(component.get("itemMargin")) or 0
            padding = numeric(styles.get("padding")) or 0
            total = (
                sum(value for value in values if value is not None)
                + gap * (len(values) - 1)
                + padding * 2
            )
            if total > parent + 1:
                add(
                    reporter,
                    "LAYOUT2X4.CLOSURE",
                    component_pointer(index, f"styles/{dimension_key}"),
                    "2x4 容器内容超出声明尺寸。",
                    round(total, 2),
                    parent,
                )
            expected = (parent - padding * 2 - gap * (len(values) - 1)) / len(values)
            if any(abs(value - expected) > 1 for value in values if value is not None):
                add(
                    reporter,
                    "LAYOUT2X4.EQUAL_SPLIT",
                    component_pointer(index, "children"),
                    "2x4 Row/Column 子项应按契约等分。",
                    values,
                    round(expected, 2),
                )
