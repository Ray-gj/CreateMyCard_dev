"""从正式主题和模板预览生成精确配色组合白名单；不改模板或降低对比度阈值。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SERVICE = Path(__file__).resolve().parents[3]
SOURCE = SERVICE / "cloud/services/template_generation/resources/source"
TARGET = SERVICE / "cloud/data/validator_rules/config/template_contrast.json"


def _styles(node: dict[str, Any]) -> dict[str, Any]:
    value = node.get("styles")
    return value if isinstance(value, dict) else {}


def _collect(
    node: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    backgrounds: list[tuple[float, float, float]],
    source: str,
    pairs: dict[str, dict[str, Any]],
    visited: set[str],
) -> None:
    from services.card_validation.contrast_validator import (
        _composite_candidates,
        _gradient_color_samples,
        _rgba,
    )

    node_id = node.get("id")
    if not isinstance(node_id, str) or node_id in visited:
        return
    visited.add(node_id)
    styles = _styles(node)
    effective = backgrounds
    color = styles.get("backgroundColor")
    if color is not None:
        effective = _composite_candidates(effective, [_rgba(color)])
    gradient = styles.get("linearGradient") or styles.get("radialGradient")
    samples = _gradient_color_samples(gradient)
    if samples:
        effective = _composite_candidates(effective, samples)
    foreground = styles.get("fontColor")
    if node.get("component") in {"Text", "Button"} and isinstance(foreground, str):
        normalized = []
        for background in effective:
            normalized.append([round(value, 9) for value in background])
        normalized.sort()
        record = {"foreground": foreground.upper(), "backgrounds": normalized}
        key = json.dumps(record, sort_keys=True)
        saved = pairs.setdefault(key, {**record, "sources": []})
        sources = saved.get("sources")
        assert isinstance(sources, list)
        if source not in sources:
            sources.append(source)
    children = node.get("children")
    if isinstance(children, list):
        for child_id in children:
            child = by_id.get(child_id)
            if isinstance(child, dict):
                _collect(child, by_id, effective, source, pairs, visited)


def build_allowlist() -> dict[str, Any]:
    from services.template_generation.engine.cardplan.preview_dataset import (
        build_template_preview_cases,
    )

    pairs: dict[str, dict[str, Any]] = {}
    cases = build_template_preview_cases()
    for case in cases:
        update = case.messages[1].get("updateComponents")
        assert isinstance(update, dict)
        components = update.get("components")
        assert isinstance(components, list)
        by_id: dict[str, dict[str, Any]] = {}
        for node in components:
            node_id = node.get("id")
            assert isinstance(node_id, str)
            by_id[node_id] = node
        root = by_id.get("root")
        assert isinstance(root, dict)
        _collect(root, by_id, [(1.0, 1.0, 1.0)], case.template_id, pairs, set())
    theme_count = 0
    for path in sorted((SOURCE / "themes").glob("*/theme.json")):
        theme = json.loads(path.read_text(encoding="utf-8"))
        theme_count += 1
        children = ["primary", "secondary"]
        nodes = [
            {
                "id": "root",
                "component": "Column",
                "styles": theme.get("rootStyle", {}),
                "children": children,
            },
            {
                "id": "primary",
                "component": "Text",
                "styles": {"fontColor": theme.get("primaryColor")},
            },
            {
                "id": "secondary",
                "component": "Text",
                "styles": {"fontColor": theme.get("supportContentColor")},
            },
        ]
        for key in ("actionStyle", "supportContentStyle"):
            style = theme.get(key)
            if not isinstance(style, dict):
                continue
            children.append(key)
            text_id = key + "Text"
            foreground = style.get("contentColor", theme.get("supportContentColor"))
            nodes.append({"id": key, "component": "Column", "styles": style, "children": [text_id]})
            nodes.append({"id": text_id, "component": "Text", "styles": {"fontColor": foreground}})
        theme_nodes = {}
        for node in nodes:
            node_id = node.get("id")
            assert isinstance(node_id, str)
            theme_nodes[node_id] = node
        _collect(
            nodes[0],
            theme_nodes,
            [(1.0, 1.0, 1.0)],
            path.relative_to(SERVICE).as_posix(),
            pairs,
            set(),
        )
    records = []
    for key in sorted(pairs):
        record = pairs.get(key)
        assert record is not None
        sources = record.get("sources")
        assert isinstance(sources, list)
        sources.sort()
        records.append(record)
    return {
        "source": "template_generation",
        "templateCount": len(cases),
        "themeCount": theme_count,
        "approvedPairs": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build_allowlist(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != rendered:
            raise SystemExit("模板配色白名单过期，请运行同步脚本。")
        print("模板配色白名单一致性检查通过。")
    else:
        TARGET.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"已生成 {TARGET}")


if __name__ == "__main__":
    sys.path.insert(0, str(SERVICE / "cloud"))
    main()
