from pathlib import Path


PRODUCTION_PATHS = [
    Path("app.py"),
    Path("engine"),
    Path("geometry"),
    Path("reports"),
    Path("services"),
    Path("sources"),
    Path("tabs"),
]


def _production_text() -> str:
    chunks: list[str] = []
    for root in PRODUCTION_PATHS:
        paths = [root] if root.is_file() else root.rglob("*.py")
        for path in paths:
            if "__pycache__" in path.parts:
                continue
            if path == Path("services/pet_results_model.py"):
                continue
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def test_pet_legacy_runtime_paths_are_removed():
    text = _production_text()

    forbidden = [
        "pet_ct_secondary_scatter",
        "PET_SOURCE_TYPE_UPTAKE",
        "PET_SOURCE_TYPE_IMAGING",
        "PET_RADIONUCLIDE_DEFAULTS",
        "PET_511_ARCHER",
        "actual_pet_511_transmission_from_archer",
        "compute_pet_required_thickness_mm_for_barrier",
        "mixed_pet_ct",
        "aapm108_pet_511",
        "SOLVER_MODE_AAPM108",
    ]

    for token in forbidden:
        assert token not in text


def test_pre_modality_cleanup_does_not_keep_old_manual_nm_room_profiles():
    constraints_text = Path("engine/design_constraints.py").read_text(encoding="utf-8")

    assert '"Manual NM"' not in constraints_text
    assert '"Theranostic"' not in constraints_text
    assert "nm_source" not in constraints_text
    assert "theranostic_radionuclide" not in constraints_text
