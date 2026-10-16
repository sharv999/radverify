from __future__ import annotations

from types import SimpleNamespace

import pytest

from geometry.source_sync import SourceSyncMixin


class _Var:
    def __init__(self, value=""):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class _Harness(SourceSyncMixin):
    def __init__(self, modality: str, source_type: str, source_name: str):
        source = SimpleNamespace(source_type=source_type, name=source_name)
        self.app = SimpleNamespace(
            get_sources_for_room=lambda _room_name: [source],
        )
        self.source_type_var = _Var("CT")
        self.source_label_var = _Var("Canon Aquilion Exceed LB")
        self.geometry = SimpleNamespace(
            source=SimpleNamespace(label="Canon Aquilion Exceed LB")
        )
        self._loading = False
        self.update_calls = 0
        self.modality = modality

    def update_source_options(self):
        self.update_calls += 1


@pytest.mark.parametrize(
    ("modality", "source_type", "source_name", "expected_label"),
    [
        ("SPECT", "spect_patient", "SPECT Patient Source", "SPECT Patient Source"),
        ("PET", "pet_patient", "PET Patient Source", "PET Patient Source"),
    ],
)
def test_startup_room_load_replaces_stale_ct_geometry_label_from_patient_source_inventory(
    modality, source_type, source_name, expected_label
):
    """Startup load must not display a stale CT scanner name for PET/SPECT.

    The live modality-switch path already resets labels, but startup room loading
    runs under ``_loading``.  This test protects the separate load-time sync path
    by making the project source inventory authoritative for patient modalities.
    """
    h = _Harness(modality, source_type, source_name)
    room = SimpleNamespace(name=f"{modality} Room 1", geometry=h.geometry)

    h.load_source_from_project(room)

    assert h.source_type_var.get() == modality
    assert h.source_label_var.get() == expected_label
    assert h.geometry.source.label == expected_label
    assert h.update_calls == 1
