from reports.report_generator import (
    _human_barrier_role,
    _human_radiation_type,
    _human_project_type,
    _modality_specific_limitations,
)


def test_pdf_humanises_internal_labels():
    assert _human_barrier_role("secondary_wall") == "Secondary wall"
    assert _human_radiation_type("tc99m_140kev") == "Tc-99m (140 keV)"
    assert _human_project_type("new_build") == "New build"
    assert _human_project_type("refurbishment") == "Refurbishment"


def test_pet_and_spect_limitations_contain_no_ct_or_ksec_wording():
    for modality in ("PET", "SPECT"):
        text = " ".join(_modality_specific_limitations(modality)).lower()
        assert "ksec" not in text
        words = text.replace("/", " ").replace("-", " ").split()
        assert "ct" not in words


def test_ct_limitations_retain_ct_specific_ksec_controls():
    text = " ".join(_modality_specific_limitations("CT")).lower()
    assert "ct results" in text
    assert "ksec" in text
