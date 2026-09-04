from __future__ import annotations

from typing import Any

from ..base import BaseValidator, numeric
from .common import add, children_of


class SlotValidator(BaseValidator):
    stage = "quality"
    name = "slot"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        root = context.components_by_id.get(context.root_id) if context.root_id else None
        if not isinstance(root, dict):
            return
        children = children_of(root, context.components_by_id)
        if not children:
            add(
                reporter,
                "SLOT.MODEL_REQUIRED",
                "/updateComponents/root/children",
                "卡片至少需要标题或内容区域。",
                len(children),
                ">= 1",
            )
            return
        action_indexes = [
            index for index, child in enumerate(children) if child.get("onClick") is not None
        ]
        if action_indexes and action_indexes[-1] != len(children) - 1:
            add(
                reporter,
                "SLOT.ORDER",
                "/updateComponents/root/children",
                "操作区域应位于最后。",
                action_indexes,
                "title, content, action",
            )
        title = children[0]
        if title.get("component") == "Text":
            styles = title.get("styles")
            size = numeric(styles.get("fontSize")) if isinstance(styles, dict) else None
            if size is not None and size != 12:
                add(
                    reporter,
                    "AREA.TITLE_TEXT_TIER",
                    f"/updateComponents/componentsById/{title.get('id')}/styles/fontSize",
                    "标题区域应使用 12vp 字号。",
                    size,
                    12,
                )
