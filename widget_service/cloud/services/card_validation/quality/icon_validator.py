from __future__ import annotations

from collections import Counter
from typing import Any

from ..base import BaseValidator
from .common import add, component_pointer, iter_components


class IconValidator(BaseValidator):
    stage = "quality"
    name = "icon"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        sources: list[tuple[int, str]] = []
        for index, component in iter_components(context):
            if component.get("component") != "Image":
                continue
            src = component.get("src")
            if isinstance(src, str) and src and not src.strip().startswith("{{"):
                sources.append((index, src))
        for src, count in Counter(value for _, value in sources).items():
            if count > 1:
                index = next(index for index, value in sources if value == src)
                add(
                    reporter,
                    "ICON.DUPLICATE_SRC",
                    component_pointer(index, "src"),
                    "同一卡片不应重复使用相同装饰图标。",
                    src,
                    "避免重复装饰素材",
                )
