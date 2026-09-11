# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Validator pipeline orchestration.

Owns the static list of built-in validators and the stage/short-circuit logic.
``validators`` are grouped by responsibility so it is obvious at a glance which
subsystem a given validator belongs to.

公共根双标记跳过质量阶段，单融球仅执行融球专项，其余执行完整质量管线。
融球展开由转换层在校验前完成；此处不改写输入组件树。
"""

from __future__ import annotations

import logging

from .aesthetic_baseline_validator import AestheticBaselineValidator
from .asset_validator import AssetValidator
from .binding_validator import BindingValidator
from .cardspec_validator import CardSpecValidator
from .component_validator import ComponentValidator
from .context import ValidationContext
from .contrast_validator import ContrastValidator
from .cross_validator import CrossValidator
from .diagnostics import Reporter
from .display_unit_validator import DisplayUnitValidator
from .effective_capability_validator import EffectiveCapabilityValidator
from .expression_validator import ExpressionValidator
from .fusion_readability_validator import FusionReadabilityValidator
from .layout_safety_validator import LayoutSafetyValidator
from .protocol_validator import ProtocolValidator
from .quality.color_validator import ColorValidator
from .quality.copy_validator import CopyValidator
from .quality.density_validator import DensityValidator
from .quality.gradient_validator import GradientValidator
from .quality.icon_validator import IconValidator
from .quality.shape_validator import ShapeValidator
from .quality.slot_validator import SlotValidator
from .quality.spacing_validator import SpacingValidator
from .quality.typography_validator import TypographyValidator

_LOGGER = logging.getLogger(__name__)

STATIC_VALIDATORS = [
    ProtocolValidator(),
    ComponentValidator(),
    AestheticBaselineValidator(),
    CardSpecValidator(),
    ExpressionValidator(),
    AssetValidator(),
    BindingValidator(),
    DisplayUnitValidator(),
    CrossValidator(),
]

QUALITY_VALIDATORS = [
    FusionReadabilityValidator(),
    LayoutSafetyValidator(),
    ShapeValidator(),
    SpacingValidator(),
    ContrastValidator(),
    TypographyValidator(),
    ColorValidator(),
    SlotValidator(),
    IconValidator(),
    CopyValidator(),
    DensityValidator(),
    GradientValidator(),
]

FUSION_QUALITY_VALIDATORS = [FusionReadabilityValidator()]

EFFECTIVE_VALIDATORS = [
    EffectiveCapabilityValidator(),
]


PIPELINE_BLOCKING_CODES = {
    "DSL_JSON_PARSE_FAILED",
}


def selected_stages(stage: str) -> list[str]:
    if stage == "hard":
        return ["hard"]
    if stage == "semantic":
        return ["hard", "semantic"]
    # "quality" and "all" both run every declared stage, including the
    # deterministic quality validators registered above.
    return ["hard", "semantic", "quality"]


def run_pipeline(
    context: ValidationContext,
    rules,
    reporter: Reporter,
    stage: str,
    *,
    stop_on_stage_error: bool = False,
) -> None:
    validators = list(STATIC_VALIDATORS) + list(EFFECTIVE_VALIDATORS)
    for current_stage in selected_stages(stage):
        if stop_on_stage_error and current_stage == "semantic" and reporter.has_error("hard"):
            return
        if stop_on_stage_error and current_stage == "quality" and reporter.error_count:
            return
        current_validators = validators
        if current_stage == "quality":
            if context.has_fusion_template_root():
                _LOGGER.info("quality_validation_skipped reason=fusion_template_root")
                continue
            current_validators = QUALITY_VALIDATORS
            if context.has_fusion_background_root():
                _LOGGER.info(
                    "quality_validation_selected reason=fusion_background_only "
                    "validators=fusion_readability"
                )
                current_validators = FUSION_QUALITY_VALIDATORS
        for validator in current_validators:
            if validator.stage == current_stage:
                validator.validate(context, rules, reporter)
