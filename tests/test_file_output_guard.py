from pathlib import Path

from services.file_output_guard import (
    check_output_bundle_writable,
    check_output_path_writable,
    expected_report_sidecar_paths,
    suggest_timestamped_output_path,
)


def test_new_output_path_passes(tmp_path):
    path = tmp_path / "report.pdf"

    check = check_output_path_writable(path)

    assert check.ok
    assert check.path == path


def test_existing_writable_path_passes(tmp_path):
    path = tmp_path / "report.pdf"
    path.write_bytes(b"old pdf")

    check = check_output_path_writable(path)

    assert check.ok


def test_directory_path_fails(tmp_path):
    check = check_output_path_writable(tmp_path)

    assert not check.ok
    assert "folder" in check.message.lower()


def test_missing_parent_fails(tmp_path):
    path = tmp_path / "missing" / "report.pdf"

    check = check_output_path_writable(path)

    assert not check.ok
    assert "does not exist" in check.message


def test_suggest_timestamped_output_path_preserves_suffix(tmp_path):
    path = tmp_path / "Example_Shielding_Assessment.pdf"

    suggested = suggest_timestamped_output_path(path)

    assert suggested.parent == path.parent
    assert suggested.suffix == ".pdf"
    assert suggested.name.startswith("Example_Shielding_Assessment_")


def test_expected_report_sidecar_paths_match_exporter_names(tmp_path):
    pdf = tmp_path / "Example_Shielding_Assessment.pdf"

    sidecars = expected_report_sidecar_paths(pdf)

    assert [p.name for p in sidecars] == [
        "Example_Shielding_Assessment_barrier_results.json",
    ]


def test_output_bundle_checks_pdf_and_sidecars(tmp_path):
    pdf = tmp_path / "report.pdf"

    check = check_output_bundle_writable(pdf, expected_report_sidecar_paths(pdf))

    assert check.ok
