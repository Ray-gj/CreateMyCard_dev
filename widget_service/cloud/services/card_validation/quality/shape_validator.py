from __future__ import annotations

from typing import Any

from ..base import BaseValidator, numeric
from .common import add, component_pointer, iter_components


class ShapeValidator(BaseValidator):
    stage = "quality"
    name = "shape"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        radii: set[float] = set()
        for index, component in iter_components(context):
            styles = component.get("styles")
            if not isinstance(styles, dict):
                continue
            radius = numeric(styles.get("borderRadius"))
            if radius is None:
                continue
            if component.get("id") == context.root_id and radius != 18:
                add(
                    reporter,
                    "SHAPE.CARD_ROOT_RADIUS",
                    component_pointer(index, "styles/borderRadius"),
                    "根卡片圆角必须为 18vp。",
                    radius,
                    18,
                )
            if component.get("component") == "Button" and radius < 18:
                add(
                    reporter,
                    "SHAPE.BUTTON_RADIUS",
                    component_pointer(index, "styles/borderRadius"),
                    "按钮圆角应不小于 18vp。",
                    radius,
                    ">= 18",
                )
            if component.get("component") == "Button":
                radii.add(radius)
        if len(radii) > 1:
            add(
                reporter,
                "SHAPE.RADIUS_FAMILY",
                "/updateComponents/components",
                "可点击控件应使用统一圆角体系。",
                sorted(radii),
                "单一圆角档位",
            )
