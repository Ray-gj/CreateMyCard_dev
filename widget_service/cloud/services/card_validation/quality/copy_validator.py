from __future__ import annotations

from typing import Any

from ..base import BaseValidator
from .common import add, component_pointer, iter_components


class CopyValidator(BaseValidator):
    stage = "quality"
    name = "copy"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        for index, component in iter_components(context):
            values = [("content", component.get("content")), ("label", component.get("label"))]
            for key, value in values:
                if not isinstance(value, str) or value.strip().startswith("{{"):
                    continue
                limit = 4 if key == "label" or component.get("onClick") is not None else 8
                code = "COPY.ACTION_LABEL_MAX_CHARS" if limit == 4 else "COPY.TITLE_MAX_CHARS"
                if len(value.strip()) > limit:
                    add(
                        reporter,
                        code,
                        component_pointer(index, key),
                        "文案超过卡片设计长度限制。",
                        len(value.strip()),
                        f"<= {limit} 字",
                    )
