"""V0.4 Step 4: repeatable, *non-certifying* field deployment preflight.

The automated probes use synthetic data and are not a substitute for a real
Windows laptop/offline site acceptance exercise or physics sign-off.
"""
from __future__ import annotations

from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import platform
import sys
import tempfile
from typing import Any

from radverify.safe_io import atomic_write_json, read_native_project

MANUAL_CHECKS = (
    ("M01", "Windows field laptop", "Launch with RUN_RADVERIFY.bat, without VS Code or an internet connection; verify display scaling and screen fit."),
    ("M02", "Unsaved work / interrupted session", "Edit a disposable room; test Save/Discard/Cancel on Quit and simulate unexpected process termination. Document backup/recovery procedure; no autosave."),
    ("M03", "Real asymmetric room", "Inspect a real/asymmetric room and verify N/E/S/W openings, geometry, scanner position and floor-plan click targets."),
    ("M04", "Evidence handling", "Attach actual photos and drawings, move an evidence file and confirm missing/change warnings. Avoid patient-identifiable information."),
    ("M05", "Instrument traceability", "Record real meter identity, calibration/certificate, background and multiple survey events; physically verify dose-rate units."),
    ("M06", "PDF quality", "Inspect exported PDF at print scale for clipping, legibility, correct spatial labels and explicit DRAFT status."),
    ("M07", "Cross-computer package transfer", "Transfer ZIP to a second field computer, verify SHA-256, restore twice, check evidence and re-export."),
    ("M08", "RadShield interoperability", "Perform RadShield design -> RadVerify as-built -> RadShield reassessment using a real room; ensure assumptions are independently reviewed."),
    ("M09", "Security and records", "Confirm access controls, secure backup, retention, naming conventions and evidence provenance; SHA-256 manifest is unsigned."),
    ("M10", "Professional acceptance", "Obtain accountable physicist review, documented acceptance criteria and operational authorisation before issuing client reports."),
)


def _check(items: list[dict[str, str]], key: str, test, success: str) -> None:
    try:
        detail = test()
        items.append({"id": key, "status": "PASS", "detail": str(detail or success)})
    except Exception as exc:
        items.append({"id": key, "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})


def _require_module(module: str) -> str:
    loaded = importlib.import_module(module)
    return f"{module} import available ({getattr(loaded, '__version__', 'version not published')})"


def _tcl_probe() -> str:
    import tkinter
    # Tcl does not open a GUI, so this is only a runtime probe; M01 tests real Tk.
    runtime = tkinter.Tcl()
    return f"Tcl {runtime.eval('info patchlevel')} initialised (GUI still requires M01)"


def _synthetic_record(path: Path):
    from radverify.models import EvidenceItem, MeasurementPoint, MeasurementRecord, RadVerifyProject
    project = RadVerifyProject()
    project.details.project_id = "FIELD-AUDIT-SYNTHETIC"
    project.details.site_name = "Synthetic audit only (no patient or client data)"
    project.geometry.width_m = 7.2
    project.geometry.length_m = 4.6
    project.geometry.source.x_m = 2.1
    project.geometry.source.y_m = 3.2
    barrier = next(b for b in project.barriers if b.barrier_id == "N wall")
    barrier.expected_pb_mm = 2.0
    barrier.observed_pb_mm = 1.5
    barrier.status = "Fail"
    evidence = path / "synthetic-photo.txt"
    evidence.write_text("Synthetic test evidence; no real site content.\n", encoding="utf-8")
    item = EvidenceItem(evidence_id="AUDIT-EV-01", file_path=str(evidence), reference="AUDIT-REF")
    item.refresh_hash()
    barrier.evidence_items.append(item)
    point = MeasurementPoint(point_id="AUDIT-MP-01", x_m=1.0, y_m=2.0)
    point.add_measurement_record(MeasurementRecord(
        record_id="AUDIT-MP-01-M01", measured_at="2026-10-19", instrument="Synthetic meter",
        calibration_due_date="2027-10-19", reading_uSv_h=0.8,
        background_uSv_h=0.1, status="Review",
    ))
    project.measurements.append(point)
    return project


def _exercise_native(path: Path) -> str:
    from radverify.packaging import project_json_for_save
    project = _synthetic_record(path)
    filename = path / "room.radverify.json"
    atomic_write_json(filename, project_json_for_save(project, filename))
    loaded = read_native_project(filename)
    assert loaded.details.project_id == project.details.project_id
    assert loaded.barriers[0].evidence_items[0].integrity_status() == "Verified"
    assert abs(loaded.measurements[0].measurement_history[0].corrected_uSv_h - 0.7) < 1e-9
    assert loaded.verification_summary()["verification_state"] == "Failed"
    return "Native JSON round-trip, evidence SHA-256, measurement history and failure state preserved"


def _exercise_twin(path: Path) -> str:
    from radverify.radtwin import project_to_radtwin, project_from_radtwin
    project = _synthetic_record(path)
    twin = project_to_radtwin(project)
    assert twin["schema"] == "radiation-room-digital-twin-0.1"
    clone = project_from_radtwin(twin)
    assert clone.geometry.width_m == 7.2 and clone.geometry.length_m == 4.6
    assert clone.barriers[0].expected_pb_mm == 2.0
    assert clone.barriers[0].observed_pb_mm == 1.5
    return "Digital Twin preserves asymmetric geometry and separate design/as-built"


def _exercise_portability(path: Path) -> str:
    from radverify.packaging import build_field_package, verify_field_package, restore_field_package
    project = _synthetic_record(path)
    archive = build_field_package(project, path / "survey.zip")
    assert verify_field_package(archive)["valid"]
    p1 = restore_field_package(archive, path / "laptop_b")
    p2 = restore_field_package(archive, path / "laptop_b_second_copy")
    assert p1.exists() and p2.exists() and p1 != p2
    clone = read_native_project(p1)
    assert clone.barriers[0].evidence_items[0].integrity_status() == "Verified"
    assert clone.measurements[0].measurement_history[0].record_id == "AUDIT-MP-01-M01"
    assert (p1.parent.parent / "report" / "verification_DRAFT.pdf").read_bytes().startswith(b"%PDF")
    return "Package checksum verified, PDF generated, restored twice, evidence links and history intact"


def _exercise_corruption(path: Path) -> str:
    from radverify.packaging import FieldPackageError, build_field_package, verify_field_package
    import zipfile
    project = _synthetic_record(path)
    source = build_field_package(project, path / "valid.zip")
    broken = path / "altered.zip"
    with zipfile.ZipFile(source) as reader, zipfile.ZipFile(broken, "w") as writer:
        for name in reader.namelist():
            content = reader.read(name)
            if name == "project/room.radverify.json":
                content += b"CORRUPTED"
            writer.writestr(name, content)
    try:
        verify_field_package(broken)
    except FieldPackageError:
        pass
    else:
        raise AssertionError("Corrupt archive was accepted")
    (path / "nonsense.radverify.json").write_text('{"unexpected":true}', encoding="utf-8")
    try:
        read_native_project(path / "nonsense.radverify.json")
    except ValueError:
        pass
    else:
        raise AssertionError("Unsupported native project schema was accepted")
    return "Changed archive and unsupported native project rejected"


def run_field_readiness_audit() -> dict[str, Any]:
    """Run independent synthetic probes. Never inspect user projects or change them."""
    checks: list[dict[str, str]] = []
    _check(checks, "A01", lambda: f"Python {platform.python_version()} ({platform.system()})", "Python available")
    _check(checks, "A02", lambda: _require_module("reportlab"), "ReportLab available")
    _check(checks, "A03", lambda: _require_module("PIL"), "Pillow available")
    _check(checks, "A04", _tcl_probe, "Tcl available")
    with tempfile.TemporaryDirectory(prefix="radverify-field-audit-") as tmp:
        root = Path(tmp)
        for name, probe in (
            ("A05", _exercise_native), ("A06", _exercise_twin),
            ("A07", _exercise_portability), ("A08", _exercise_corruption),
        ):
            folder = root / name
            folder.mkdir()
            _check(checks, name, lambda probe=probe, folder=folder: probe(folder), name)
    passed = sum(item["status"] == "PASS" for item in checks)
    return {
        "schema": "radverify-field-readiness-audit-0.1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "Synthetic automated probes only; no real-site field acceptance performed",
        "automated_pass": passed,
        "automated_total": len(checks),
        "automated_result": "PASS" if passed == len(checks) else "FAIL",
        "field_release_status": "NOT CLEARED — manual field acceptance and accountable physicist sign-off required",
        "checks": checks,
        "manual_gates": [{"id": id_, "title": title, "procedure": procedure, "status": "NOT RUN"}
                         for id_, title, procedure in MANUAL_CHECKS],
    }


def audit_markdown(result: dict[str, Any]) -> str:
    lines = ["# RadVerify V0.4 — Field Deployment Readiness Audit", "",
             f"Generated (UTC): {result['generated_at_utc']}", "",
             f"**Automated:** {result['automated_pass']}/{result['automated_total']} — {result['automated_result']}",
             f"**Release decision:** {result['field_release_status']}", "",
             "## Automated checks (synthetic)", ""]
    for item in result["checks"]:
        lines.append(f"- **{item['id']} {item['status']}** — {item['detail']}")
    lines += ["", "## Manual acceptance gates — NOT RUN", "",
              "A field operator must check and sign these on the target laptop/site:", ""]
    for item in result["manual_gates"]:
        lines.append(f"- [ ] **{item['id']} {item['title']}** — {item['procedure']}")
    lines += ["", "## Limitations and approval", "",
              "- Report PDFs are draft field records, **not compliance certificates**.",
              "- The field package manifest is **unsigned** and does not authenticate provenance.",
              "- No automatic crash recovery/autosave; manually save and back up field work regularly.",
              "- The Python/Tk desktop runtime and dependencies must be installed; this is not a standalone EXE.",
              "- Automated PASS is not deployment authorisation. Confirm regulatory and clinical constraints independently.",
              "", "Operator: __________________ Date: __________", "",
              "Accountable medical physicist: __________________ Date: __________", ""]
    return "\n".join(lines)


def write_audit_files(result: dict[str, Any], destination: str | Path) -> tuple[Path, Path]:
    """Create human-readable checklist plus JSON for audit provenance."""
    md = Path(destination)
    if md.suffix.lower() != ".md":
        md = md.with_suffix(".md")
    data_file = md.with_suffix(".json")
    atomic_write_json(data_file, result)
    md.write_text(audit_markdown(result), encoding="utf-8")
    return md, data_file


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run synthetic RadVerify field deployment readiness probes")
    parser.add_argument("--output", default="radverify_field_readiness_audit.md", help="Checklist report path (.md)")
    args = parser.parse_args()
    result = run_field_readiness_audit()
    md, json_path = write_audit_files(result, args.output)
    print(f"AUTOMATED: {result['automated_pass']}/{result['automated_total']} {result['automated_result']}")
    print(f"FIELD RELEASE: {result['field_release_status']}")
    print(f"Audit: {md} / {json_path}")
    sys.exit(0 if result["automated_result"] == "PASS" else 1)
