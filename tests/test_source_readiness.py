from types import SimpleNamespace

from services.source_readiness import (
    PET_WORKING_STATE_BLOCK_REASON,
    source_readiness_summary_lines,
    validate_project_source_readiness,
)


def _source(source_type="ct_scatter", params=None, name="Secondary scatter source diagnostic", radiation_type="xray_140kvp"):
    return SimpleNamespace(
        name=name,
        source_type=source_type,
        params=params or {},
        radiation_type=radiation_type,
    )


def _room(name="CT Room 1", modality="CT"):
    return SimpleNamespace(name=name, modality=modality)


def _project(room):
    return SimpleNamespace(rooms=[room], sources=[])


def _valid_database_params():
    return {
        "scanner_family": "GE_APEX",
        "scanner_vendor": "GE",
        "scanner_model": "GE Revolution Apex",
        "scanner_kvp": 140,
        "ksec_energy_kvp": 140,
        "scans_per_week": 60,
        "workload_mAs_per_scan": 630,
        "ksec_mGy_per_100mAs_at_1m": 0.0457,
        "scanner_source": "JSON worst-case Ksec lookup",
    }


def test_source_readiness_database_ct_ksec_passes_with_rich_checks():
    room = _room()
    src = _source(params=_valid_database_params())
    project = _project(room)

    result = validate_project_source_readiness(
        project,
        get_sources_for_room=lambda room_name: [src],
    )

    assert result["overall_status"] == "PASS"
    assert not result["blocking"]
    assert result["errors"] == []

    lines = source_readiness_summary_lines(result)
    assert any("Scanner family" in line for line in lines)
    assert any("Ksec energy basis" in line for line in lines)
    assert any("Workload mAs/scan" in line for line in lines)
    assert any("TVL key" in line for line in lines)


def test_source_readiness_null_ct_ksec_blocks():
    room = _room()
    params = _valid_database_params()
    params.update({
        "scanner_family": "PHILIPS_BRILLIANCE_64",
        "scanner_model": "Philips Brilliance 64",
        "ksec_mGy_per_100mAs_at_1m": "",
        "scanner_source": "NULL ksec — manual override required",
    })
    src = _source(params=params)
    project = _project(room)

    result = validate_project_source_readiness(
        project,
        get_sources_for_room=lambda room_name: [src],
    )

    assert result["overall_status"] == "FAIL"
    assert result["blocking"]
    assert any("ksec is missing" in item for item in result["errors"])


def test_source_readiness_manual_override_without_audit_reviews_not_blocks():
    room = _room()
    params = _valid_database_params()
    params.update({
        "scanner_family": "PHILIPS_BRILLIANCE_64",
        "scanner_model": "Philips Brilliance 64",
        "ksec_mGy_per_100mAs_at_1m": 0.06,
        "manual_ksec_override": "1",
        "manual_ksec_reason": "",
        "manual_ksec_source_reference": "",
    })
    src = _source(params=params)
    project = _project(room)

    result = validate_project_source_readiness(
        project,
        get_sources_for_room=lambda room_name: [src],
    )

    assert result["overall_status"] == "REVIEW"
    assert not result["blocking"]
    assert any("audit trail is incomplete" in item for item in result["warnings"])


def test_source_readiness_manual_override_with_audit_reviews_not_blocks():
    room = _room()
    params = _valid_database_params()
    params.update({
        "scanner_family": "PHILIPS_BRILLIANCE_64",
        "scanner_model": "Philips Brilliance 64",
        "ksec_mGy_per_100mAs_at_1m": 0.06,
        "manual_ksec_override": "1",
        "manual_ksec_reason": "Vendor document pending",
    })
    src = _source(params=params)
    project = _project(room)

    result = validate_project_source_readiness(
        project,
        get_sources_for_room=lambda room_name: [src],
    )

    assert result["overall_status"] == "REVIEW"
    assert not result["blocking"]
    assert any("Manual CT scanner ksec override is being used" in item for item in result["warnings"])


def test_source_readiness_missing_ct_source_blocks():
    room = _room()
    project = _project(room)

    result = validate_project_source_readiness(
        project,
        get_sources_for_room=lambda room_name: [],
    )

    assert result["overall_status"] == "FAIL"
    assert result["blocking"]
    assert any("Room has no sources" in item for item in result["errors"])


def test_persisted_pet_working_state_is_nonblocking_but_output_review_required():
    room = SimpleNamespace(
        name="CT Room 1",
        modality="CT",
        modality_state={"pet_single_source": {"schema": "radshield_pet_working_source_v2"}},
    )
    src = _source(params=_valid_database_params())
    project = _project(room)

    result = validate_project_source_readiness(
        project,
        get_sources_for_room=lambda room_name: [src],
    )

    assert result["overall_status"] == "REVIEW"
    assert result["blocking"] is False
    assert result["errors"] == []
    assert result["warnings"] == [f"CT Room 1: {PET_WORKING_STATE_BLOCK_REASON}"]
    room_result = result["room_results"][0]
    assert any(
        check["name"] == "PET working-state production host"
        and check["status"] == "REVIEW"
        and check["detail"] == PET_WORKING_STATE_BLOCK_REASON
        for check in room_result["checks"]
    )
    assert any(item.get("output_blocking") is True for item in room_result["source_results"])


def test_room_without_persisted_pet_working_state_remains_ready():
    room = SimpleNamespace(name="CT Room 1", modality="CT", modality_state={})
    src = _source(params=_valid_database_params())
    project = _project(room)

    result = validate_project_source_readiness(
        project,
        get_sources_for_room=lambda room_name: [src],
    )

    assert result["overall_status"] == "PASS"
    assert result["blocking"] is False
