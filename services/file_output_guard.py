from __future__ import annotations

"""
Friendly file-output guard for generated reports.

Windows commonly raises PermissionError when a PDF is still open in a viewer,
browser preview, or the Explorer preview pane. This module checks writability
before report generation so the UI can show a clear recovery message instead
of a traceback.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class OutputPathCheck:
    ok: bool
    path: Path
    message: str = ""
    suggested_path: Path | None = None


def suggest_timestamped_output_path(path: str | Path) -> Path:
    path = Path(path)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return path.with_name(f"{path.stem}_{stamp}{path.suffix}")


def check_output_path_writable(path: str | Path) -> OutputPathCheck:
    path = Path(path)
    suggested = suggest_timestamped_output_path(path)

    if path.exists() and path.is_dir():
        return OutputPathCheck(
            ok=False,
            path=path,
            suggested_path=suggested,
            message=(
                "The selected output path is a folder, not a PDF file.\n\n"
                "Choose a PDF filename and try again."
            ),
        )

    parent = path.parent if path.parent != Path("") else Path(".")
    if not parent.exists():
        return OutputPathCheck(
            ok=False,
            path=path,
            suggested_path=suggested,
            message=(
                f"The output folder does not exist:\n{parent}\n\n"
                "Choose an existing folder and try again."
            ),
        )

    if not parent.is_dir():
        return OutputPathCheck(
            ok=False,
            path=path,
            suggested_path=suggested,
            message=(
                f"The output folder is not valid:\n{parent}\n\n"
                "Choose a valid folder and try again."
            ),
        )

    # Existing file: open in read/write mode without truncating. This catches
    # Windows file locks from PDF viewers and preview panes.
    if path.exists():
        try:
            with path.open("r+b"):
                pass
        except PermissionError:
            return OutputPathCheck(
                ok=False,
                path=path,
                suggested_path=suggested,
                message=_locked_file_message(path, suggested),
            )
        except OSError as exc:
            return OutputPathCheck(
                ok=False,
                path=path,
                suggested_path=suggested,
                message=_generic_write_error_message(path, suggested, exc),
            )

    # New file: test parent directory write access using a temporary probe file.
    else:
        probe = parent / f".{path.stem}.write_test.tmp"
        try:
            with probe.open("xb"):
                pass
            probe.unlink(missing_ok=True)
        except PermissionError:
            return OutputPathCheck(
                ok=False,
                path=path,
                suggested_path=suggested,
                message=(
                    f"The output folder is not writable:\n{parent}\n\n"
                    "Choose a different folder and try again."
                ),
            )
        except FileExistsError:
            try:
                probe.unlink(missing_ok=True)
            except Exception:
                pass
        except OSError as exc:
            try:
                probe.unlink(missing_ok=True)
            except Exception:
                pass
            return OutputPathCheck(
                ok=False,
                path=path,
                suggested_path=suggested,
                message=_generic_write_error_message(path, suggested, exc),
            )

    return OutputPathCheck(ok=True, path=path)


def check_output_bundle_writable(pdf_path: str | Path, extra_paths: Iterable[str | Path] | None = None) -> OutputPathCheck:
    """
    Check the PDF and optional sidecar outputs before generation.

    The primary user-facing path is the PDF, but callers can also pass the JSON
    sidecar if they want to fail before partial output is written.
    """
    pdf_path = Path(pdf_path)
    paths = [pdf_path]
    if extra_paths:
        paths.extend(Path(p) for p in extra_paths)

    for path in paths:
        check = check_output_path_writable(path)
        if not check.ok:
            return check

    return OutputPathCheck(ok=True, path=pdf_path)


def expected_report_sidecar_paths(pdf_path: str | Path) -> list[Path]:
    """
    Paths written by reports.results_exporter.write_results_exports_from_payload().
    """
    pdf_path = Path(pdf_path)
    stem = pdf_path.stem
    output_dir = pdf_path.parent
    return [
        output_dir / f"{stem}_barrier_results.json",
    ]


def friendly_permission_error_message(path: str | Path) -> str:
    path = Path(path)
    return _locked_file_message(path, suggest_timestamped_output_path(path))


def _locked_file_message(path: Path, suggested: Path) -> str:
    return (
        "The selected PDF could not be overwritten.\n\n"
        f"File:\n{path}\n\n"
        "It may already be open in a PDF viewer, browser preview, or Windows preview pane.\n\n"
        "Close the file and try again, or save using a different filename.\n\n"
        f"Suggested alternate filename:\n{suggested.name}"
    )


def _generic_write_error_message(path: Path, suggested: Path, exc: OSError) -> str:
    return (
        "The output file could not be written.\n\n"
        f"File:\n{path}\n\n"
        f"System message:\n{exc}\n\n"
        "Close any open copy of the file, check folder permissions, or save using a different filename.\n\n"
        f"Suggested alternate filename:\n{suggested.name}"
    )
