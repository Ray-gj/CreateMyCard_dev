# -*- coding: utf-8 -*-
"""Minimal text/background contrast validation for the quality stage."""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseValidator
from .color_math import (
    RgbaColor as RgbaColor,
)
from .color_math import (
    RgbColor,
    _composite_candidates,
    _contrast,
    _gradient_color_samples,
    _reported_contrast_ratio,
    _rgba,
    approved_color_pair,
)
from .color_math import (
    _composite as _composite,
)

_LOGGER = logging.getLogger(__name__)
_NORMAL_ROOT_ID = "root_0"
_FUSION_BACKGROUND_ID = "fusionBallBackground"
_OPAQUE_ALPHA = 1.0


class ContrastValidator(BaseValidator):
    """Check readable text against its effective ancestor backgrounds."""

    stage = "quality"
    name = "contrast"

    def validate(self, context, rules, reporter) -> None:
        palette = getattr(rules, "template_contrast", {})
        approved_pairs = palette.get("approvedPairs", [])
        if context.has_fusion_template_root():
            _LOGGER.info(
                "quality_validation_skipped reason=fusion_template_root validator=contrast"
            )
            return
        if not context.components or not context.root_id:
            return
        by_id = context.components_by_id
        root = by_id.get(context.root_id)
        if not isinstance(root, dict):
            return
        root_children = root.get("children")
        root_child_ids = root_children if isinstance(root_children, list) else []
        is_fusion_scene = _FUSION_BACKGROUND_ID in root_child_ids
        is_normal_scene = _NORMAL_ROOT_ID in root_child_ids
        self._walk(
            context,
            reporter,
            root,
            [(1.0, 1.0, 1.0)],
            is_gradient=False,
            is_fusion_scene=is_fusion_scene and not is_normal_scene,
            approved_pairs=approved_pairs,
        )

    def _walk(
        self,
        context: Any,
        reporter: Any,
        component: dict[str, Any],
        backgrounds: list[RgbColor],
        *,
        is_gradient: bool,
        is_fusion_scene: bool,
        approved_pairs: list[dict[str, Any]],
    ) -> None:
        styles = component.get("styles")
        styles = styles if isinstance(styles, dict) else {}
        effective_backgrounds = list(backgrounds)
        try:
            background = _rgba(styles.get("backgroundColor"))
            effective_backgrounds = _composite_candidates(
                effective_backgrounds,
                [background],
            )
            if background[3] >= _OPAQUE_ALPHA:
                is_gradient = False
        except ValueError as exc:
            if styles.get("backgroundColor") is not None:
                _LOGGER.debug(
                    "background_color_unresolved type=%s reason=%s", type(exc).__name__, exc
                )
        gradient = styles.get("linearGradient") or styles.get("radialGradient")
        gradient_samples = _gradient_color_samples(gradient)
        if gradient_samples:
            effective_backgrounds = _composite_candidates(
                effective_backgrounds,
                gradient_samples,
            )
            is_gradient = True

        if component.get("component") == "Text" and self._has_text(component.get("content")):
            color_key = "fontColor" if "fontColor" in styles else "textColor"
            foreground = styles.get(color_key)
            if is_fusion_scene:
                component_id = component.get("id")
                pointer = f"/updateComponents/componentsById/{component_id}/styles/{color_key}"
                reporter.add(
                    "warning",
                    "VISUAL.CONTRAST",
                    self.stage,
                    "genui",
                    line=2,
                    json_pointer=pointer,
                    actual={"scene": "fusionBall", "requiresRenderReview": True},
                    expected="端侧渲染后确认文字区域对比度",
                    message="fusionBall 背景由兄弟装饰层合成，静态对比度不作阻塞判定",
                    fix_hint="请在端侧渲染后复核文字可读性；仅在实际不可读时调整颜色。",
                    source="aesthetic-contrast",
                )
                return
            ratios = []
            for item in effective_backgrounds:
                try:
                    ratios.append(_contrast(foreground, item))
                except ValueError:
                    continue
            if ratios:
                ratio = _reported_contrast_ratio(ratios, is_gradient)
                approved = self._approved_pair(foreground, effective_backgrounds, approved_pairs)
                if ratio < 4.5 and not approved:
                    severity = "error" if ratio < 2.0 else "warning"
                    requires_render_review = is_gradient and severity == "warning"
                    component_id = component.get("id")
                    pointer = f"/updateComponents/componentsById/{component_id}/styles/{color_key}"
                    reporter.add(
                        severity,
                        "VISUAL.CONTRAST",
                        self.stage,
                        "genui",
                        line=2,
                        json_pointer=pointer,
                        actual=round(ratio, 2),
                        expected=(
                            ">= 2:1 after render review; >= 4.5:1 recommended"
                            if requires_render_review
                            else ">= 2:1; >= 4.5:1 recommended"
                        ),
                        message=(
                            f"text contrast is {ratio:.2f}:1; gradient requires render review"
                            if requires_render_review
                            else f"text contrast is {ratio:.2f}:1"
                        ),
                        fix_hint=(
                            "Confirm readability on the rendered gradient; adjust contrast "
                            "only if the text area is unclear."
                            if requires_render_review
                            else "Use a stronger foreground color or adjust the background."
                        ),
                        source="aesthetic-contrast",
                    )

        children = component.get("children")
        child_ids = children if isinstance(children, list) else []
        for child_id in child_ids:
            child = context.components_by_id.get(child_id)
            if isinstance(child, dict):
                self._walk(
                    context,
                    reporter,
                    child,
                    effective_backgrounds,
                    is_gradient=is_gradient,
                    is_fusion_scene=is_fusion_scene,
                    approved_pairs=approved_pairs,
                )

    @staticmethod
    def _approved_pair(
        foreground: Any, backgrounds: list[RgbColor], approved_pairs: list[dict[str, Any]]
    ) -> bool:
        return approved_color_pair(foreground, backgrounds, approved_pairs)

    @staticmethod
    def _has_text(value: Any) -> bool:
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, dict):
            return bool(value)
        return value is not None
