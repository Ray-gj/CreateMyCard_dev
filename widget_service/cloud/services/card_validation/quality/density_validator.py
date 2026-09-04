from __future__ import annotations

from typing import Any

from ..base import BaseValidator, numeric
from .common import add, iter_components


class DensityValidator(BaseValidator):
    stage = "quality"
    name = "density"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        actions = [
            component
            for _, component in iter_components(context)
            if component.get("onClick") is not None and component.get("id") != context.root_id
        ]
        limit = 2 if getattr(context, "card_size", None) == "2x4" else 1
        if len(actions) > limit:
            add(
                reporter,
                "DENSITY.EXPLICIT_ACTIONS",
                "/updateComponents/components",
                "显式操作数量超过卡片尺寸上限。",
                len(actions),
                f"<= {limit}",
            )
        if len(actions) > 1:
            add(
                reporter,
                "DENSITY.SINGLE_PRIMARY_ACTION",
                "/updateComponents/components",
                "卡片默认只保留一个主要操作。",
                len(actions),
                1,
            )
        numbers = [
            component
            for _, component in iter_components(context)
            if component.get("component") == "Text"
            and (numeric((component.get("styles") or {}).get("fontSize")) or 0) >= 24
        ]
        if len(numbers) > 1:
            add(
                reporter,
                "DENSITY.NUMBERS",
                "/updateComponents/components",
                "卡片不应同时出现多个大字号数字。",
                len(numbers),
                "<= 1",
            )
