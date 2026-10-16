from __future__ import annotations

from pathlib import Path


def resolve_logo_path() -> Path | None:
    """Return the first available logo asset for report generation."""
    module_dir = Path(__file__).resolve().parent
    project_root = module_dir.parent

    candidates = [
        project_root / "logo.png",
        project_root / "logo.jpg",
        project_root / "logo.jpeg",
        module_dir / "logo.png",
        module_dir / "logo.jpg",
        module_dir / "logo.jpeg",
        Path.cwd() / "logo.png",
        Path.cwd() / "logo.jpg",
        Path.cwd() / "logo.jpeg",
    ]

    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                return candidate
        except Exception:
            pass

    return None
