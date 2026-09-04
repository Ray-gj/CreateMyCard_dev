from __future__ import annotations

from typing import Any

from ..base import BaseValidator, numeric
from .common import add, component_pointer, iter_components


class TypographyValidator(BaseValidator):
    stage = "quality"
    name = "typography"
    allowed = frozenset({8, 10, 12, 14, 16, 18, 20, 24, 30, 32, 38, 40, 48, 56})

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        for index, component in iter_components(context):
            if component.get("component") not in {"Text", "Button"}:
                continue
            styles = component.get("styles")
            if not isinstance(styles, dict):
                continue
            size = numeric(styles.get("fontSize"))
            if size is not None and int(size) not in self.allowed:
                add(
                    reporter,
                    "TYPE.FONT_SIZE_STEP",
                    component_pointer(index, "styles/fontSize"),
                    "字号不在登记的字体档位中。",
                    size,
                    sorted(self.allowed),
                )
            weight = numeric(styles.get("fontWeight"))
            if weight is not None and int(weight) not in {400, 500, 700}:
                add(
                    reporter,
                    "TYPE.WEIGHT_MATRIX",
                    component_pointer(index, "styles/fontWeight"),
                    "字重不在允许范围内。",
                    weight,
                    [400, 500, 700],
                )
