from __future__ import annotations

from typing import Any

from ..base import BaseValidator, numeric
from .common import add, component_pointer, iter_components


class SpacingValidator(BaseValidator):
    stage = "quality"
    name = "spacing"
    allowed = frozenset({0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 24, 32})

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        for index, component in iter_components(context):
            styles = component.get("styles")
            if not isinstance(styles, dict):
                continue
            padding = numeric(styles.get("padding"))
            if component.get("id") == context.root_id and padding is not None and padding != 12:
                add(
                    reporter,
                    "SPACING.SAFE_MARGIN",
                    component_pointer(index, "styles/padding"),
                    "根容器安全边距应为 12vp。",
                    padding,
                    12,
                )
            if padding is not None and padding not in self.allowed:
                add(
                    reporter,
                    "SPACING.SCALE",
                    component_pointer(index, "styles/padding"),
                    "间距不在登记档位中。",
                    padding,
                    sorted(self.allowed),
                )
