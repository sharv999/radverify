from models.shielding_models import Barrier
from reports.barrier_schedule import _base_row_from_live


class _App:
    def _row_confidence_from_live(self, barrier_name, live):
        return 1.0


def test_canonical_barrier_schedule_exposes_modality_solver_mode_when_solver_used_absent():
    row = _base_row_from_live(
        _App(),
        Barrier(name="N wall"),
        {
            "solver_mode": "spect_tc99m_practical_archer",
            "compliance_status": "PASS",
            "required_thickness_mm": 0.1,
            "margin_mm": 0.78,
        },
        status="PASS",
    )
    assert row["solver_used"] == "spect_tc99m_practical_archer"
