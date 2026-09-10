"""融球专项可读性：保留模板通用豁免，不将候选球色当作实测背景。"""

from __future__ import annotations

from typing import Any

from .base import BaseValidator
from .color_math import _contrast, approved_color_pair
from .fusion_background import (
    _Background,
    _initial_background,
    _is_text,
    _uniform_stack_background,
    _with_background,
)
from .fusion_geometry import FUSION_REFERENCE_SIZE
from .fusion_structure import (
    child_ids,
    color_of,
    dimension,
    inspect_fusion,
    reachable_fusion,
    styles_of,
    visible,
)


def _report(
    reporter: Any, code: str, severity: str, pointer: str, message: str, actual: Any, hint: str
) -> None:
    reporter.add(
        severity,
        code,
        "quality",
        "genui",
        line=2,
        json_pointer=pointer,
        actual=actual,
        message=message,
        fix_hint=hint,
        source="fusion-readability",
    )


class FusionReadabilityValidator(BaseValidator):
    stage = "quality"
    name = "fusion_readability"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        root = context.components_by_id.get(context.root_id)
        if not isinstance(root, dict) or not reachable_fusion(root, context.components_by_id):
            return
        size = context.cardspec.get("suggestSize")
        styles = styles_of(root)
        reference = float(FUSION_REFERENCE_SIZE)
        reference_dimensions = (
            dimension(styles.get("width", "matchParent"), reference),
            dimension(styles.get("height", "matchParent"), reference),
        )
        if size not in (None, "2x2") or reference_dimensions != (reference, reference):
            _report(
                reporter,
                "FUSION.RENDER_REVIEW_REQUIRED",
                "warning",
                "/updateComponents/root",
                "当前融球专项仅验证 160×160 的 2x2 参考结构。",
                {"size": size, "referenceDimensions": reference_dimensions},
                "按该尺寸的正式融球结构进行渲染复核，不套用 2x2 几何。",
            )
            return
        structure = inspect_fusion(root, context.components_by_id)
        if structure.errors:
            _report(
                reporter,
                "FUSION.STRUCTURE_INVALID",
                "error",
                "/updateComponents/components",
                "融球背景不符合受控几何或层次结构，不能据此计算文字背景。",
                {"violations": structure.errors},
                "按受控融球结构修复背景；百分比相对直接父级解析。"
                "中球槽应为参考 80×220、中球为 160×160；不要移动或压扁球体来修复颜色。",
            )
            return
        if structure.foreground is not None:
            initial = _initial_background(structure, root)
            # 外壳上的整体效果同样作用于前景，不能在局部底板处遗忘。
            root_effects = _with_background(root, _Background()).effects
            initial.effects = root_effects
            self._walk(context, structure.foreground, initial, reporter, rules)

    def _walk(
        self,
        context: Any,
        root: dict[str, Any],
        initial: _Background,
        reporter: Any,
        rules: Any,
    ) -> None:
        pending = [(root, initial)]
        indexes: dict[str, int] = {}
        for index, component in enumerate(context.components):
            component_id = component.get("id")
            if isinstance(component_id, str):
                indexes[component_id] = index
        visited: set[str] = set()
        while pending:
            component, inherited = pending.pop()
            component_id = component.get("id")
            if not isinstance(component_id, str) or not visible(component):
                continue
            index = indexes.get(component_id)
            if index is None:
                continue
            pointer = f"/updateComponents/components/{index}"
            if component_id in visited:
                _report(
                    reporter,
                    "FUSION.RENDER_REVIEW_REQUIRED",
                    "warning",
                    pointer,
                    "前景含循环或共享引用，无法唯一确定背景继承。",
                    component_id,
                    "修复组件引用关系后重新检查可读性。",
                )
                continue
            visited.add(component_id)
            background = _with_background(component, inherited)
            known_component = component.get("component") in (
                "Text",
                "Button",
                "Row",
                "Column",
                "Stack",
                "List",
                "Image",
                "Divider",
                "Progress",
                "Checkbox",
            )
            if not known_component:
                _report(
                    reporter,
                    "FUSION.RENDER_REVIEW_REQUIRED",
                    "warning",
                    pointer,
                    "前景含未知组件，不能确认其文字与背景绘制行为。",
                    component.get("component"),
                    "使用已支持组件，或补充该组件的渲染语义后复核。",
                )
            if _is_text(component):
                self._check_foreground(component, background, pointer, reporter, rules)
            elif component.get("component") == "Image" and "fillColor" in styles_of(component):
                self._check_foreground(component, background, pointer, reporter, rules)
            children = child_ids(component)
            raw_children = component.get("children")
            if raw_children is not None and not _complete_children(raw_children, children):
                _report(
                    reporter,
                    "FUSION.RENDER_REVIEW_REQUIRED",
                    "warning",
                    pointer + "/children",
                    "前景子组件引用无法完整解析，检查未完成。",
                    raw_children,
                    "补齐合法的子组件数组或模板引用后重新校验。",
                )
            visible_children = []
            for child_id in children:
                child = context.components_by_id.get(child_id)
                if not isinstance(child, dict):
                    _report(
                        reporter,
                        "FUSION.RENDER_REVIEW_REQUIRED",
                        "warning",
                        pointer + "/children",
                        "前景引用的组件不存在，检查未完成。",
                        child_id,
                        "补齐组件引用后重新校验。",
                    )
                elif visible(child):
                    visible_children.append(child)
            if component.get("component") == "Stack" and len(visible_children) > 1:
                composed = _uniform_stack_background(component, visible_children, background)
                if composed is not None:
                    pending.append((visible_children[1], composed))
                    continue
                background.effects += ("前景 Stack 存在未解析的兄弟叠层",)
            for child in reversed(visible_children):
                pending.append((child, background))

    @staticmethod
    def _check_foreground(
        component: dict[str, Any],
        background: _Background,
        pointer: str,
        reporter: Any,
        rules: Any,
    ) -> None:
        styles = styles_of(component)
        key = "fontColor" if "fontColor" in styles else "textColor"
        icon = component.get("component") == "Image"
        if icon:
            key = "fillColor"
        subject = "图标" if icon else "文字"
        color = styles.get(key)
        parsed = color_of(color)
        location = f"{pointer}/styles/{key}"
        if parsed is not None and background.color is not None and not background.effects:
            ratio = _contrast(color, background.color)
            palette = getattr(rules, "template_contrast", {})
            approved = approved_color_pair(
                color, [background.color], palette.get("approvedPairs", [])
            )
            if approved:
                return
            if icon:
                if ratio < 3.0:
                    _report(
                        reporter,
                        "FUSION.RENDER_REVIEW_REQUIRED",
                        "warning",
                        location,
                        "图标填充色与确定背景的对比度低于 3:1，请结合素材形状复核辨识度。",
                        {
                            "ratio": round(ratio, 4),
                            "target": "icon",
                            "backgroundPath": background.path,
                            "requiresRenderReview": True,
                        },
                        "优先调整图标填充色或局部底板；不根据装饰球色修改正式模板。",
                    )
                return
            if ratio < 4.5:
                severity = "error" if ratio < 3.0 else "warning"
                _report(
                    reporter,
                    "FUSION.TEXT_CONTRAST",
                    severity,
                    location,
                    f"融球卡片局部确定背景上的文字对比度为 {ratio:.2f}:1。",
                    {
                        "ratio": round(ratio, 4),
                        "basis": "opaque-local-background",
                        "backgroundPath": background.path,
                        "target": "text",
                    },
                    "提高文字与局部底色的对比度，至少达到 3:1，建议达到 4.5:1；"
                    "优先调整文字颜色、透明度或底板，不缩小字号。",
                )
            return
        reasons = list(dict.fromkeys(background.reasons + background.effects))
        actual: dict[str, Any] = {
            "requiresRenderReview": True,
            "reasons": reasons,
            "backgroundPath": background.path,
            "target": "icon" if icon else "text",
        }
        if parsed is None:
            reasons.append(subject + "颜色缺失或无法静态解析")
        elif background.samples:
            ratios = [_contrast(color, sample) for sample in background.samples]
            actual["candidateContrastRange"] = [round(min(ratios), 4), round(max(ratios), 4)]
            actual["candidateBasis"] = "球色、玻璃及局部纯色或渐变候选；非空间、非模糊测量"
        if not reasons:
            reasons.append("无法确定" + subject + "位置的实际背景")
        _report(
            reporter,
            "FUSION.RENDER_REVIEW_REQUIRED",
            "warning",
            location,
            "融球" + subject + "可读性需要复核：" + "；".join(reasons) + "。",
            actual,
            "复核目标所在位置的端侧合成结果；优先调整前景颜色、透明度或局部底板。"
            "候选范围不能作为实测对比度或通过依据，不据此改动正式模板球色。",
        )


def _complete_children(raw: Any, parsed: list[str]) -> bool:
    complete = False
    if isinstance(raw, list):
        complete = len(raw) == len(parsed)
    elif isinstance(raw, dict):
        complete = len(parsed) == 1
    return complete
