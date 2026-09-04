from __future__ import annotations

from typing import Any

from ..base import BaseValidator
from .common import add, component_pointer, iter_components, static_color


class GradientValidator(BaseValidator):
    stage = "quality"
    name = "gradient"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        for index, component in iter_components(context):
            styles = component.get("styles")
            if not isinstance(styles, dict):
                continue
            for key in ("linearGradient", "radialGradient"):
                gradient = styles.get(key)
                if gradient is None:
                    continue
                if (
                    not isinstance(gradient, dict)
                    or not gradient.get("direction")
                    and not gradient.get("center")
                ):
                    add(
                        reporter,
                        "GRADIENT.UNREGISTERED",
                        component_pointer(index, f"styles/{key}"),
                        "渐变必须声明方向或中心点。",
                        gradient,
                    )
                colors = gradient.get("colors") if isinstance(gradient, dict) else None
                if not isinstance(colors, list) or not colors:
                    add(
                        reporter,
                        "GRADIENT.UNREGISTERED",
                        component_pointer(index, f"styles/{key}/colors"),
                        "渐变必须包含非空颜色 stops。",
                        colors,
                    )
                    continue
                for stop_index, stop in enumerate(colors):
                    raw = stop[0] if isinstance(stop, (list, tuple)) and stop else None
                    offset = stop[1] if isinstance(stop, (list, tuple)) and len(stop) > 1 else None
                    if (
                        static_color(raw) is None
                        or not isinstance(offset, (int, float))
                        or not 0 <= offset <= 1
                    ):
                        add(
                            reporter,
                            "GRADIENT.UNREGISTERED",
                            component_pointer(index, f"styles/{key}/colors/{stop_index}"),
                            "渐变 stop 必须包含合法颜色和 0~1 offset。",
                            stop,
                        )
