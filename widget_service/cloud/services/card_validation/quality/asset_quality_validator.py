from __future__ import annotations

from typing import Any

from ..base import BaseValidator
from .common import add, component_pointer, iter_components


class AssetQualityValidator(BaseValidator):
    stage = "quality"
    name = "asset_quality"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        for index, component in iter_components(context):
            if component.get("component") != "Image":
                continue
            src = component.get("src")
            if isinstance(src, str) and src.strip().startswith(
                ("http://", "https://", "data:image", "data:;base64")
            ):
                add(
                    reporter,
                    "ASSET.REMOTE_SRC",
                    component_pointer(index, "src"),
                    "图片素材不得使用远程地址或内嵌 data URI。",
                    src,
                    "本地受控素材路径",
                )
