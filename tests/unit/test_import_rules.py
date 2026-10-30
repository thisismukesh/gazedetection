"""Guardrail: pure modules import only stdlib, numpy, lookaway.types/events (CLAUDE.md §5)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "lookaway"
PURE = [
    "attention/state_machine.py",
    "attention/one_euro.py",
    "zones/zone_map.py",
    "control/targeting.py",
    "control/motion.py",
    "control/policy.py",
    "control/assigner.py",
    "control/wander.py",
    "perception/geometry.py",
]
ALLOWED_THIRD_PARTY = {"numpy"}
ALLOWED_INTERNAL = {"lookaway.types", "lookaway.events"}
FORBIDDEN_CALLS = {"time.time", "time.monotonic", "time.sleep"}


def _imports(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
    return names


def test_pure_modules_import_rules() -> None:
    violations: list[str] = []
    for rel in PURE:
        path = SRC / rel
        if not path.exists():
            continue
        tree = ast.parse(path.read_text())
        for name in _imports(tree):
            top = name.split(".")[0]
            if top in sys.stdlib_module_names or top == "__future__":
                continue
            if top in ALLOWED_THIRD_PARTY or name in ALLOWED_INTERNAL:
                continue
            violations.append(f"{rel}: {name}")
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and f"{node.value.id}.{node.attr}" in FORBIDDEN_CALLS
            ):
                violations.append(f"{rel}: wall-clock {node.value.id}.{node.attr}")
    assert not violations, violations
