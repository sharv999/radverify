"""CLI for the Step 38 combined PET/SPECT production-output readiness audit."""
from __future__ import annotations

from services.pet_spect_production_output_readiness import (
    assess_pet_spect_production_output_readiness,
    require_step38_audit_foundations_valid,
)


def main() -> int:
    result = require_step38_audit_foundations_valid()
    print("PET/SPECT STEP 38 PRODUCTION OUTPUT READINESS AUDIT")
    print("==================================================")
    for check in result["checks"]:
        state = "PASS" if check["passed"] else "BLOCKER"
        print(f"[{state}] {check['check_id']}: {check['detail']}")
    print()
    print(f"PET calculation production ready: YES" if result["pet_calculation_production_ready"] else "PET calculation production ready: NO")
    print(f"SPECT calculation production ready: YES" if result["spect_calculation_production_ready"] else "SPECT calculation production ready: NO")
    print(f"Normal issued-report payload ready: {'YES' if result['normal_report_payload_ready'] else 'NO'}")
    print(f"Issued PDF ready: {'YES' if result['issued_pdf_ready'] else 'NO'}")
    print(f"Machine export ready: {'YES' if result['machine_export_ready'] else 'NO'}")
    print(f"Certification ready: {'YES' if result['certification_ready'] else 'NO'}")
    print(f"Production output enablement: {'GO' if result['production_output_enablement_ready'] else 'NO-GO'}")
    print()
    print("Next boundary:")
    print(result["recommended_next_boundary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
