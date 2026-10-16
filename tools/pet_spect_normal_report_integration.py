"""CLI for Step 40 PET/SPECT normal report integration readiness."""
from services.pet_spect_normal_report_integration_readiness import assess_step40_normal_report_integration


def main() -> int:
    result = assess_step40_normal_report_integration()
    print("PET/SPECT STEP 40 NORMAL REPORT INTEGRATION")
    print("=" * 46)
    for check in result["checks"]:
        print(f"[{'PASS' if check['passed'] else 'FAIL'}] {check['check_id']}: {check['detail']}")
    print()
    print("Normal report payload integration ready:", "YES" if result["normal_report_payload_integration_ready"] else "NO")
    print("PET/SPECT generic recalculation disabled:", "YES" if result["pet_spect_generic_recalculation_disabled"] else "NO")
    print("Issued PDF ready:", "YES" if result["issued_pdf_ready"] else "NO")
    print("Machine export ready:", "YES" if result["machine_export_ready"] else "NO")
    print("Certification ready:", "YES" if result["certification_ready"] else "NO")
    return 0 if result["normal_report_payload_integration_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
