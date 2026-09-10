"""保守解析融球前景背景链；只为明确覆盖的纯色层建立确定性背景。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .color_math import RgbColor, _composite, _gradient_color_samples
from .fusion_structure import FusionStructure, color_of, styles_of


@dataclass
class _Background:
    color: RgbColor | None = None
    samples: list[RgbColor] = field(default_factory=list)
    reasons: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    path: tuple[str, ...] = ()


def _opaque_rgb(color: tuple[float, float, float, float]) -> RgbColor:
    return color[0], color[1], color[2]


def _initial_background(structure: FusionStructure, root: dict[str, Any]) -> _Background:
    samples: list[RgbColor] = []
    if structure.glass is not None:
        for color in structure.colors:
            samples.append(_composite(_opaque_rgb(color), structure.glass))
    reasons = ["融球玻璃模糊尚未与端侧校准，球色候选不代表文字位置的实际背景"]
    root_color = color_of(styles_of(root).get("backgroundColor"))
    if root_color is None or root_color[3] != 1.0:
        reasons.append("透明背景覆盖不足时可能依赖未知宿主底色")
    return _Background(
        samples=samples,
        reasons=tuple(reasons),
        path=("root", "fusionBallBackground", "fusionBallGlassLayer"),
    )


def _is_text(component: dict[str, Any]) -> bool:
    kind = component.get("component")
    if kind not in ("Text", "Button"):
        return False
    content = component.get("content" if kind == "Text" else "label")
    if isinstance(content, str):
        return bool(content.strip())
    return content is not None


def _with_background(component: dict[str, Any], inherited: _Background) -> _Background:
    styles = styles_of(component)
    result = _Background(
        inherited.color,
        list(inherited.samples),
        inherited.reasons,
        inherited.effects,
        inherited.path,
    )
    component_id = component.get("id")
    if isinstance(component_id, str):
        result.path += (component_id,)
    effects = list(result.effects)
    if styles.get("opacity", 1) != 1:
        effects.append("祖先或文字含未合成的整体 opacity")
    if any(key in styles for key in ("transform", "blendMode", "filter", "foregroundBlur")):
        effects.append("存在未建模的绘制效果")
    result.effects = tuple(dict.fromkeys(effects))
    if "backgroundColor" in styles:
        color = color_of(styles.get("backgroundColor"))
        if color is None:
            result.color = None
            result.samples = []
            result.reasons = ("局部背景颜色无法静态解析",)
        elif color[3] == 1.0:
            contained = styles.get("clip") is True or _is_text(component)
            result.color = _opaque_rgb(color) if contained else None
            result.samples = [_opaque_rgb(color)]
            result.reasons = () if contained else ("不透明底板未裁剪，无法证明文字位于底板覆盖区",)
        else:
            if result.color is not None:
                result.color = _composite(result.color, color)
            result.samples = [_composite(sample, color) for sample in result.samples]
            contained = styles.get("clip") is True or _is_text(component)
            if color[3] > 0.0 and not contained:
                result.color = None
                result.reasons += ("半透明局部底板未裁剪，文字可能跨越底板边缘",)
    gradient_present = "linearGradient" in styles or "radialGradient" in styles
    if gradient_present:
        gradient = styles.get("linearGradient") or styles.get("radialGradient")
        samples = _gradient_color_samples(gradient)
        candidates: list[RgbColor] = []
        for sample in samples:
            if sample[3] == 1.0:
                candidates.append(_opaque_rgb(sample))
            else:
                for base in result.samples:
                    candidates.append(_composite(base, sample))
        result.color = None
        result.samples = candidates
        result.reasons = ("局部渐变仅作颜色候选采样，尚未确定文字区域覆盖",)
    uncertain_paint = "backgroundImage" in styles or "backdropBlur" in styles
    if uncertain_paint:
        result.color = None
        result.samples = []
        result.reasons = ("局部图片、渐变或背景模糊尚未纳入确定性合成",)
    return result


def _uniform_stack_background(
    component: dict[str, Any], children: list[dict[str, Any]], inherited: _Background
) -> _Background | None:
    """只解析明确铺满的底层色板；未知布局、圆角和额外叠层仍交给渲染复核。"""
    result: _Background | None = None
    styles = styles_of(component)
    safe_parent = styles.get("clip") is True and styles.get("alignContent") == "topStart"
    if len(children) != 2 or not safe_parent:
        return result
    if any(key in styles for key in ("padding", "borderRadius", "constraintSize")):
        return result
    base, content = children
    base_styles = styles_of(base)
    allowed = {"width", "height", "backgroundColor", "clip"}
    safe_base = base.get("component") in ("Column", "Row", "Stack")
    if not safe_base or base.get("children", []) != []:
        return result
    if set(base_styles) - allowed or color_of(base_styles.get("backgroundColor")) is None:
        return result
    for key in ("width", "height"):
        if base_styles.get(key) != "matchParent":
            return result
    content_styles = styles_of(content)
    if content_styles.get("clip") is not True:
        return result
    if any(key in content_styles for key in ("margin", "transform", "position", "offset")):
        return result
    # 父级裁剪确保内容不越出铺满的底色；用副本表达覆盖证明，不改写输入。
    covered = dict(base)
    covered["styles"] = dict(base_styles, clip=True)
    result = _with_background(covered, inherited)
    return result
