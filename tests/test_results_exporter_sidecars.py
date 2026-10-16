import json
from pathlib import Path

from reports.results_exporter import write_results_exports_from_payload
from services.file_output_guard import expected_report_sidecar_paths


def _payload():
    return {
        "meta": {"generated_on": "2026-09-15 12:00:00"},
        "project": {"project_name": "Example"},
        "summary": {"barrier_count": 1},
        "rooms": [
            {
                "name": "Room 1",
                "modality": "SPECT",
                "barriers": [
                    {
                        "name": "N wall",
                        "material": "Pb",
                        "provided_thickness_mm": 0.88,
                        "required_thickness_mm": 1.07,
                        "status": "FAIL",
                        "solver_used": "spect_tc99m_practical_archer",
                    }
                ],
            }
        ],
    }


def test_barrier_results_json_is_always_written_without_auxiliary_jsons(tmp_path):
    pdf_path = tmp_path / "Example.pdf"
    paths = write_results_exports_from_payload(_payload(), pdf_path, include_csv=False)

    assert set(paths) == {"barrier_results_json"}
    barrier_json = tmp_path / "Example_barrier_results.json"
    assert barrier_json.exists()
    data = json.loads(barrier_json.read_text(encoding="utf-8"))
    assert data["rows"][0]["barrier"] == "N wall"
    assert data["rows"][0]["status"] == "FAIL"
    assert not (tmp_path / "Example_source_readiness.json").exists()
    assert not (tmp_path / "Example_results_payload.json").exists()
    assert not (tmp_path / "Example_barrier_results.csv").exists()


def test_barrier_csv_is_not_written_even_when_legacy_include_csv_flag_is_true(tmp_path):
    pdf_path = tmp_path / "Example.pdf"
    paths = write_results_exports_from_payload(_payload(), pdf_path, include_csv=True)
    assert set(paths) == {"barrier_results_json"}
    assert not (tmp_path / "Example_barrier_results.csv").exists()
    assert expected_report_sidecar_paths(pdf_path) == [
        tmp_path / "Example_barrier_results.json",
    ]
