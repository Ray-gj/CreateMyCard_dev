from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

COLOR_KEYS = ("fontColor", "textColor", "fillColor", "backgroundColor", "borderColor", "color")
FONT_COMPONENTS = {"Text", "Button"}
CONTAINERS = {"Row", "Column", "Stack", "List"}
EMOJI_RANGES = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF))
HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
ALPHA_STEPS = frozenset(
    {
        0x00,
        0x0C,
        0x0D,
        0x19,
        0x1A,
        0x26,
        0x27,
        0x33,
        0x4D,
        0x66,
        0x7F,
        0x80,
        0x99,
        0xB2,
        0xB3,
        0xCC,
        0xE5,
        0xE6,
        0xFF,
    }
)


def component_pointer(index: int, key: str = "") -> str:
    suffix = f"/{key}" if key else ""
    return f"/updateComponents/components/{index}{suffix}"


def iter_components(context: Any) -> Iterator[tuple[int, dict[str, Any]]]:
    for index, component in enumerate(context.components):
        if isinstance(component, dict):
            yield index, component


def children_of(
    component: dict[str, Any], by_id: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    children = component.get("children")
    if not isinstance(children, list):
        return []
    return [by_id[child] for child in children if isinstance(child, str) and child in by_id]


def is_emoji(value: Any) -> bool:
    return isinstance(value, str) and any(
        start <= ord(char) <= end for char in value for start, end in EMOJI_RANGES
    )


def static_color(value: Any) -> str | None:
    if not isinstance(value, str) or value.strip().startswith(("{{", "${", "$theme(")):
        return None
    return value.strip() if HEX_RE.fullmatch(value.strip()) else None


def alpha(value: str) -> int:
    raw = value[1:]
    return int(raw[6:8], 16) if len(raw) == 8 else 0xFF


def all_colors(component: dict[str, Any]) -> Iterator[tuple[str, Any]]:
    styles = component.get("styles")
    if not isinstance(styles, dict):
        return
    for key in COLOR_KEYS:
        if key in styles:
            yield key, styles[key]
    for gradient_key in ("linearGradient", "radialGradient"):
        gradient = styles.get(gradient_key)
        if not isinstance(gradient, dict) or not isinstance(gradient.get("colors"), list):
            continue
        for index, stop in enumerate(gradient["colors"]):
            if isinstance(stop, (list, tuple)) and stop:
                yield f"{gradient_key}/{index}", stop[0]


def add(
    reporter: Any,
    code: str,
    pointer: str,
    message: str,
    actual: Any = None,
    expected: Any = None,
    severity: str = "warning",
) -> None:
    reporter.add(
        severity,
        code,
        "quality",
        "genui",
        line=2,
        json_pointer=pointer,
        actual=actual,
        expected=expected,
        message=message,
        source="aesthetic-quality",
    )
