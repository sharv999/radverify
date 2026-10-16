from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_shielding_desktop_app_tk_startup_smoke(tmp_path):
    """
    Instantiate the full app in a fresh Python process.

    Tk can be fragile when multiple Tk roots are created/destroyed in one
    pytest process, especially on Windows/Python 3.14. This still protects
    real app startup, but avoids order-dependent Tcl/Tk interpreter state.
    """
    code = r'''
from app import ShieldingDesktopApp

app = None
try:
    app = ShieldingDesktopApp()
    app.withdraw()
    app.update_idletasks()
finally:
    if app is not None:
        app.destroy()
'''

    stdout_path = tmp_path / "tk_startup_smoke_stdout.txt"
    stderr_path = tmp_path / "tk_startup_smoke_stderr.txt"

    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path.cwd(),
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            timeout=20,
        )

    stdout_text = stdout_path.read_text(encoding="utf-8")
    stderr_text = stderr_path.read_text(encoding="utf-8")

    assert result.returncode == 0, (
        "ShieldingDesktopApp failed to start in subprocess"
        f"\nSTDOUT:\n{stdout_text}"
        f"\nSTDERR:\n{stderr_text}"
    )