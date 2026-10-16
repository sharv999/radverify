"""Protect the production/developer-tool dependency boundary."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_production_layers_do_not_import_tools_package():
    offenders: list[str] = []
    for package in ("engine", "services", "modalities", "reports", "serialization"):
        for path in (ROOT / package).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and (
                    node.module == "tools" or node.module.startswith("tools.")
                ):
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "tools" or alias.name.startswith("tools."):
                            offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert offenders == [], "Production layers must not import developer CLI tools: " + ", ".join(offenders)
