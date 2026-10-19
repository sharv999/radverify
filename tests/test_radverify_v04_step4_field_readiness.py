"""V0.4 Step 4: field-readiness gates and recoverable persistence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from radverify.deployment import run_field_readiness_audit, audit_markdown, write_audit_files
from radverify.models import RadVerifyProject
from radverify.safe_io import atomic_write_json, read_native_project


def test_atomic_native_save_preserves_previous_file_when_replace_fails(tmp_path, monkeypatch):
    target = tmp_path / "important.radverify.json"
    target.write_bytes(b"existing archived contents")
    from radverify import safe_io
    def fail_replace(_source, _dest):
        raise PermissionError("File locked by another application")
    monkeypatch.setattr(safe_io.os, "replace", fail_replace)
    with pytest.raises(PermissionError, match="File locked"):
        atomic_write_json(target, {"schema_version": "radverify-0.1"})
    assert target.read_bytes() == b"existing archived contents"
    assert not list(tmp_path.glob(".important.radverify.json.*.tmp"))


def test_invalid_json_serialization_does_not_replace_existing_file(tmp_path):
    target = tmp_path / "protected.json"
    target.write_bytes(b"original")
    with pytest.raises(ValueError):
        atomic_write_json(target, {"invalid": float("nan")})
    assert target.read_bytes() == b"original"


def test_strict_native_load_rejects_corrupted_and_unrelated_projects(tmp_path):
    corrupted = tmp_path / "bad.radverify.json"
    corrupted.write_text("[broken", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        read_native_project(corrupted)
    corrupted.write_text(json.dumps({"not": "a project"}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        read_native_project(corrupted)
    good = RadVerifyProject()
    atomic_write_json(corrupted, good.to_dict())
    assert read_native_project(corrupted).details.room_name == good.details.room_name


def test_synthetic_audit_covers_portability_and_requires_manual_signoff(tmp_path):
    result = run_field_readiness_audit()
    assert result["automated_result"] == "PASS", result
    assert result["automated_pass"] == result["automated_total"] == 8
    assert len(result["manual_gates"]) >= 10
    assert all(row["status"] == "NOT RUN" for row in result["manual_gates"])
    assert "NOT CLEARED" in result["field_release_status"]
    checklist = audit_markdown(result)
    assert "not compliance certificates" in checklist.lower()
    assert "No automatic crash recovery/autosave" in checklist
    md, record = write_audit_files(result, tmp_path / "audit.md")
    assert md.is_file() and record.is_file()
    assert json.loads(record.read_text(encoding="utf-8"))["automated_result"] == "PASS"
    assert "M08 RadShield interoperability" in md.read_text(encoding="utf-8")


def test_audit_fails_closed_when_a_synthetic_probe_fails(monkeypatch):
    from radverify import deployment
    def broken(_path):
        raise RuntimeError("Simulated unsafe package restore")
    monkeypatch.setattr(deployment, "_exercise_portability", broken)
    result = run_field_readiness_audit()
    assert result["automated_result"] == "FAIL"
    assert "NOT CLEARED" in result["field_release_status"]
    assert next(row for row in result["checks"] if row["id"] == "A07")["status"] == "FAIL"


def test_failed_save_as_does_not_change_active_path_or_dirty_state(tmp_path, monkeypatch):
    from app import RadVerifyApp
    from app import filedialog, messagebox
    import app as gui_module

    gui = RadVerifyApp()
    gui.withdraw()
    try:
        original = tmp_path / "original.radverify.json"
        assert gui._write_project(original)
        gui.project.details.notes = "edited but unsaved"
        gui.mark_dirty()
        new_file = tmp_path / "unwritable.radverify.json"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(new_file))
        monkeypatch.setattr(gui_module, "atomic_write_json", lambda *_a, **_kw: (_ for _ in ()).throw(PermissionError("mock access denied")))
        monkeypatch.setattr(messagebox, "showerror", lambda *_a, **_kw: None)
        assert gui.save_project_as() is False
        assert gui.current_file == original
        assert gui._dirty is True
        assert not new_file.exists()
        assert original.exists()
    finally:
        gui.destroy()


def test_corrupt_open_keeps_current_project_and_path(tmp_path, monkeypatch):
    from app import RadVerifyApp, filedialog, messagebox
    gui = RadVerifyApp()
    gui.withdraw()
    try:
        old = gui.project
        assert gui._write_project(tmp_path / "current.radverify.json")
        current = gui.current_file
        corrupted = tmp_path / "bad.radverify.json"
        corrupted.write_text('{ "schema_version": "malformed" }', encoding="utf-8")
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(corrupted))
        monkeypatch.setattr(messagebox, "showerror", lambda *_a, **_kw: None)
        gui.open_project()
        assert gui.project is old
        assert gui.current_file == current
        assert gui._dirty is False
    finally:
        gui.destroy()


def test_cancel_quit_retains_dirty_app(monkeypatch):
    from app import RadVerifyApp, messagebox
    gui = RadVerifyApp()
    gui.withdraw()
    try:
        gui.mark_dirty()
        monkeypatch.setattr(messagebox, "askyesnocancel", lambda *_a, **_kw: None)
        gui.on_close()
        assert gui.winfo_exists()
        assert gui._dirty
    finally:
        gui.destroy()
