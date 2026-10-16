from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CORE_DIRS = [
    "engine",
    "services",
    "reports",
]

FORBIDDEN_MODULES = {
    "tkinter",
    "_tkinter",
    "customtkinter",
    "app",
    "tabs",
    "ui",
}

# Some report modules may intentionally import reportlab etc. That is fine.
# This test only blocks UI/app-layer imports from core/headless layers.


def _python_files_under(relative_dir: str) -> list[Path]:
    root = PROJECT_ROOT / relative_dir
    if not root.exists():
        return []

    return sorted(
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _import_root(module_name: str) -> str:
    return str(module_name or "").split(".", 1)[0]


def _relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")


def _forbidden_imports_in_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))

    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _import_root(alias.name)
                if root in FORBIDDEN_MODULES:
                    violations.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            # Ignore relative imports such as "from .foo import bar".
            if node.level:
                continue

            module = node.module or ""
            root = _import_root(module)

            if root in FORBIDDEN_MODULES:
                violations.append(module)

    return violations


def test_core_report_service_layers_do_not_import_ui_modules():
    """
    Non-UI layers must remain usable by headless tests, CLI/batch runs,
    future API paths, and report/export generation.

    This guards against accidental imports of app.py, tabs/*, tkinter, or ui/*
    from engine/services/reports/geometry/sources.
    """
    checked_files: list[Path] = []
    failures: list[str] = []

    for relative_dir in CORE_DIRS:
        for path in _python_files_under(relative_dir):
            checked_files.append(path)

            violations = _forbidden_imports_in_file(path)
            for violation in violations:
                failures.append(f"{_relative(path)} imports forbidden UI module: {violation}")

    assert checked_files, "No core files were checked"

    assert not failures, "Forbidden UI imports found:\n" + "\n".join(failures)