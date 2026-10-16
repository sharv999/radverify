"""CLI for Step 39 PET/SPECT common report-payload readiness."""
from services.pet_spect_report_payload_readiness import assess_step39_report_payload_readiness


def _yes(value: object) -> str:
    return "YES" if value is True else "NO"


def main() -> int:
    result = assess_step39_report_payload_readiness()
    print("PET/SPECT STEP 39 COMMON REPORT PAYLOAD READINESS")
    print("=" * 53)
    print(f"PET ultralow policy ready: {_yes(result['pet_ultralow_policy_ready'])}")
    print(f"Common non-issueable payload adapter ready: {_yes(result['common_non_issueable_payload_adapter_ready'])}")
    print(f"Normal report integration ready: {_yes(result['normal_report_integration_ready'])}")
    print(f"Issued PDF ready: {_yes(result['issued_pdf_ready'])}")
    print(f"Machine export ready: {_yes(result['machine_export_ready'])}")
    print(f"Certification ready: {_yes(result['certification_ready'])}")
    print("\nChecks")
    for check in result["checks"]:
        print(f"  {'PASS' if check['passed'] else 'FAIL'}  {check['check_id']}: {check['detail']}")
    print("\nNext boundary:")
    print(result["recommended_next_boundary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
