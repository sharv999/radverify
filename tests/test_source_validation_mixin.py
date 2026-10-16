from types import SimpleNamespace

from sources.source_validation import SourceValidationMixin


class _Harness(SourceValidationMixin):
    LOCKED_MODALITY_SOURCES = {}

    def __init__(self, project, sources_by_room):
        self.project = project
        self._sources_by_room = sources_by_room

    def get_sources_for_room(self, room_name):
        return self._sources_by_room.get(room_name, [])


def _valid_ct_source():
    return SimpleNamespace(
        name="CT scatter",
        source_type="ct_scatter",
        radiation_type="xray_140kvp",
        params={
            "scanner_family": "GE_APEX",
            "scanner_vendor": "GE",
            "scanner_model": "GE Revolution Apex",
            "scanner_kvp": 140,
            "ksec_energy_kvp": 140,
            "scans_per_week": 60,
            "workload_mAs_per_scan": 630,
            "ksec_mGy_per_100mAs_at_1m": 0.0457,
            "scanner_source": "JSON worst-case Ksec lookup",
        },
    )


def test_project_source_readiness_mixin_aggregates_without_stale_pet_locals():
    room = SimpleNamespace(name="CT Room 1", modality="CT", modality_state={})
    project = SimpleNamespace(rooms=[room])
    app = _Harness(project, {room.name: [_valid_ct_source()]})

    result = app.validate_project_source_readiness()

    assert result["overall_status"] == "PASS"
    assert result["blocking"] is False
    assert result["errors"] == []
    assert len(result["room_results"]) == 1
