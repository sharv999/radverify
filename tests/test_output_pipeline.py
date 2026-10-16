from pathlib import Path

from reports.output_pipeline import generate_outputs_from_app


class DummyProject:
    project_type = "new_build"


class DummyApp:
    def __init__(self):
        self.project = DummyProject()
        self.refreshed_results = False
        self.refreshed_barriers = False

    def apply_project_form(self):
        self.applied = True

    def validate_project_source_readiness(self):
        return {
            "blocking": False,
            "overall_status": "PASS",
            "errors": [],
            "warnings": [],
        }

    def refresh_results_tab(self):
        self.refreshed_results = True

    def _safe_refresh_barrier_schedule(self):
        self.refreshed_barriers = True


def test_output_pipeline_uses_one_payload_for_pdf_and_exports(tmp_path, monkeypatch):
    calls = {}

    payload = {
        "project": {"project_name": "Test"},
        "rooms": [],
        "summary": {},
    }

    def fake_build_results_payload(**kwargs):
        calls["payload_app"] = kwargs["app"]
        return payload

    def fake_render_pdf_from_payload(render_payload, output_path):
        calls["pdf_payload"] = render_payload
        Path(output_path).write_text("PDF", encoding="utf-8")
        return Path(output_path)

    def fake_write_results_exports_from_payload(export_payload, output_path, *, include_csv=True):
        calls["export_payload"] = export_payload
        calls["include_csv"] = include_csv
        return {"barrier_results_json": Path(output_path).with_suffix(".json")}

    monkeypatch.setattr(
        "reports.output_pipeline.build_results_payload",
        fake_build_results_payload,
    )
    monkeypatch.setattr(
        "reports.output_pipeline.render_pdf_from_payload",
        fake_render_pdf_from_payload,
    )
    monkeypatch.setattr(
        "reports.output_pipeline.write_results_exports_from_payload",
        fake_write_results_exports_from_payload,
    )

    app = DummyApp()
    result = generate_outputs_from_app(
        app=app,
        output_path=tmp_path / "report.pdf",
    )

    assert result.generated
    assert calls["pdf_payload"] is not payload
    assert calls["pdf_payload"]["project"]["project_type"] == "new_build"
    assert "project_type" not in payload["project"]
    assert calls["export_payload"] is payload
    assert result.export_paths["barrier_results_json"].name == "report.json"
    assert app.refreshed_results
    assert app.refreshed_barriers


def test_output_pipeline_can_cancel_on_preflight_warning(tmp_path):
    class WarningApp(DummyApp):
        def validate_project_source_readiness(self):
            return {
                "blocking": True,
                "overall_status": "FAIL",
                "errors": ["Missing CT ksec"],
                "warnings": [],
            }

    result = generate_outputs_from_app(
        app=WarningApp(),
        output_path=tmp_path / "report.pdf",
        confirm_callback=lambda message, blocking: False,
    )

    assert result.cancelled
    assert not result.generated
    assert result.blocking_issues == ["Missing CT ksec"]


def test_output_pipeline_blocks_machine_exports_when_payload_integrity_fails(tmp_path, monkeypatch):
    calls = {}

    payload = {
        "project": {"project_name": "Test"},
        "rooms": [],
        "summary": {},
        "source_readiness": {"blocking": False, "overall_status": "PASS", "errors": [], "warnings": []},
        "calculation_integrity": {
            "calculation_complete": False,
            "blocking": True,
            "blocking_reasons": ["BLOCKED: barrier result count does not match the room barrier schedule."],
            "room_issues": [],
        },
    }

    def fake_build_results_payload(**kwargs):
        return payload

    def fake_render_pdf_from_payload(render_payload, output_path):
        calls["pdf_payload"] = render_payload
        Path(output_path).write_text("PDF", encoding="utf-8")
        return Path(output_path)

    def fake_write_results_exports_from_payload(export_payload, output_path, *, include_csv=True):
        calls["export_payload"] = export_payload
        calls["include_csv"] = include_csv
        return {"barrier_results_json": Path(output_path).with_suffix(".json")}

    monkeypatch.setattr(
        "reports.output_pipeline.build_results_payload",
        fake_build_results_payload,
    )
    monkeypatch.setattr(
        "reports.output_pipeline.render_pdf_from_payload",
        fake_render_pdf_from_payload,
    )
    monkeypatch.setattr(
        "reports.output_pipeline.write_results_exports_from_payload",
        fake_write_results_exports_from_payload,
    )

    result = generate_outputs_from_app(
        app=DummyApp(),
        output_path=tmp_path / "report.pdf",
        confirm_callback=lambda message, blocking: True,
    )

    assert result.generated
    assert result.export_paths == {}
    assert calls["pdf_payload"] is not payload
    assert calls["pdf_payload"]["project"]["project_type"] == "new_build"
    assert "project_type" not in payload["project"]
    assert "export_payload" not in calls
    assert result.blocking_issues == [
        "BLOCKED: barrier result count does not match the room barrier schedule."
    ]
