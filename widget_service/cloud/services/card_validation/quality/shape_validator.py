from __future__ import annotations

from typing import Any

from ..base import BaseValidator, numeric
from .common import add, component_pointer, iter_components


class ShapeValidator(BaseValidator):
    stage = "quality"
    name = "shape"
    root_radius = 18

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        root_radius = self.root_radius
        min_button_radius = 18.0
        if rules is not None:
            configured_root_radius = numeric(rules.layout.get("rootBorderRadius"))
            configured_button_radius = numeric(rules.layout.get("minButtonRadius"))
            if configured_root_radius is not None and configured_root_radius >= 0:
                root_radius = configured_root_radius
            if configured_button_radius is not None and configured_button_radius >= 0:
                min_button_radius = configured_button_radius
        radii: set[float] = set()
        for index, component in iter_components(context):
            styles = component.get("styles")
            is_root = component.get("id") == context.root_id
            if not isinstance(styles, dict):
                if is_root:
                    add(
                        reporter,
                        "SHAPE.CARD_ROOT_RADIUS",
                        component_pointer(index, "styles/borderRadius"),
                        f"根卡片圆角必须为 {root_radius:g}vp。",
                        None,
                        root_radius,
                    )
                continue
            radius = numeric(styles.get("borderRadius"))
            if is_root and radius != root_radius:
                add(
                    reporter,
                    "SHAPE.CARD_ROOT_RADIUS",
                    component_pointer(index, "styles/borderRadius"),
                    f"根卡片圆角必须为 {root_radius:g}vp。",
                    radius,
                    root_radius,
                )
            if radius is None:
                continue
            if component.get("component") == "Button" and radius < min_button_radius:
                add(
                    reporter,
                    "SHAPE.BUTTON_RADIUS",
                    component_pointer(index, "styles/borderRadius"),
                    f"按钮圆角应不小于 {min_button_radius:g}vp。",
                    radius,
                    f">= {min_button_radius:g}",
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
