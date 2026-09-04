# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Validator pipeline orchestration.

Owns the static list of built-in validators and the stage/short-circuit logic.
``validators`` are grouped by responsibility so it is obvious at a glance which
subsystem a given validator belongs to.

The online variant keeps the protocol and semantic stages as its core pipeline.
The quality stage currently hosts deterministic contrast checks; broader design
contract checks remain the responsibility of the ``generateWidgetCard`` service.
"""

from __future__ import annotations

from .aesthetic_baseline_validator import AestheticBaselineValidator
from .asset_validator import AssetValidator
from .binding_validator import BindingValidator
from .cardspec_validator import CardSpecValidator
from .component_validator import ComponentValidator
from .contrast_validator import ContrastValidator
from .cross_validator import CrossValidator
from .diagnostics import Reporter
from .display_unit_validator import DisplayUnitValidator
from .effective_capability_validator import EffectiveCapabilityValidator
from .expression_validator import ExpressionValidator
from .protocol_validator import ProtocolValidator
from .quality.asset_quality_validator import AssetQualityValidator
from .quality.color_validator import ColorValidator
from .quality.copy_validator import CopyValidator
from .quality.density_validator import DensityValidator
from .quality.gradient_validator import GradientValidator
from .quality.icon_validator import IconValidator
from .quality.layout_2x4_validator import Layout2x4Validator
from .quality.shape_validator import ShapeValidator
from .quality.slot_validator import SlotValidator
from .quality.spacing_validator import SpacingValidator
from .quality.typography_validator import TypographyValidator

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
    ColorValidator(),
    GradientValidator(),
    AssetQualityValidator(),
    IconValidator(),
    ShapeValidator(),
    TypographyValidator(),
    CopyValidator(),
    SpacingValidator(),
    SlotValidator(),
    DensityValidator(),
    Layout2x4Validator(),
    ContrastValidator(),
]

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
    context,
    rules,
    reporter: Reporter,
    stage: str,
    *,
    stop_on_stage_error: bool = False,
) -> None:
    validators = list(STATIC_VALIDATORS) + list(EFFECTIVE_VALIDATORS) + list(QUALITY_VALIDATORS)
    for current_stage in selected_stages(stage):
        if stop_on_stage_error and current_stage == "semantic" and reporter.has_error("hard"):
            return
        if stop_on_stage_error and current_stage == "quality" and reporter.error_count:
            return
        for validator in validators:
            if validator.stage == current_stage:
                validator.validate(context, rules, reporter)
