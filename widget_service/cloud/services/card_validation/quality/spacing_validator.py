from __future__ import annotations

from typing import Any

from ..base import BaseValidator, numeric, spacing_tuple
from .common import add, component_pointer, iter_components, quality_scene


class SpacingValidator(BaseValidator):
    stage = "quality"
    name = "spacing"
    allowed = frozenset({0, 2, 4, 6, 8, 10, 12, 14, 16})

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        configured_spacing = rules.layout.get("allowedSpacing") if rules is not None else None
        allowed = self.allowed
        if isinstance(configured_spacing, list):
            values = {
                float(value)
                for value in configured_spacing
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            }
            if values:
                allowed = frozenset(values)
        default_padding = 12
        if rules is not None:
            configured_padding = numeric(rules.layout.get("defaultPadding"))
            if configured_padding is not None:
                default_padding = configured_padding
        scene = quality_scene(context)
        safe_root_id = scene.content_root.get("id") if scene is not None else context.root_id
        for index, component in iter_components(context):
            styles = component.get("styles")
            if not isinstance(styles, dict):
                if component.get("id") == safe_root_id:
                    add(
                        reporter,
                        "SPACING.SAFE_MARGIN",
                        component_pointer(index, "styles/padding"),
                        f"根容器安全边距应为 {default_padding:g}vp。",
                        None,
                        default_padding,
                    )
                continue
            padding = styles.get("padding")
            if component.get("id") == safe_root_id and not self._matches_padding(
                padding,
                default_padding,
            ):
                add(
                    reporter,
                    "SPACING.SAFE_MARGIN",
                    component_pointer(index, "styles/padding"),
                    f"根容器安全边距应为 {default_padding:g}vp。",
                    padding,
                    default_padding,
                )
            self._check_spacing_value(
                reporter,
                component_pointer(index, "styles/padding"),
                padding,
                allowed,
            )
            self._check_spacing_value(
                reporter,
                component_pointer(index, "styles/margin"),
                styles.get("margin"),
                allowed,
            )
            gap_field = "space" if component.get("component") == "List" else "itemMargin"
            self._check_spacing_value(
                reporter,
                component_pointer(index, gap_field),
                component.get(gap_field),
                allowed,
            )

    @staticmethod
    def _matches_padding(value: Any, expected: float) -> bool:
        if value is None:
            return False
        return spacing_tuple(value) == (expected, expected, expected, expected)

    @staticmethod
    def _check_spacing_value(
        reporter: Any,
        pointer: str,
        value: Any,
        allowed: frozenset[float],
    ) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            values = [numeric(item) for item in value.values()]
            if not values:
                values = [None]
        else:
            values = [numeric(value)]
        invalid = any(item is None or item not in allowed for item in values)
        if invalid:
            add(
                reporter,
                "SPACING.SCALE",
                pointer,
                "间距不在登记档位中。",
                value,
                sorted(allowed),
            )
