"""CLI for the PET Step 28 PDF integration readiness gate."""
from services.pet_pdf_integration_readiness_gate import assess_pet_pdf_integration_readiness


def main() -> int:
    state = assess_pet_pdf_integration_readiness()
    print("PET STEP 28 PDF INTEGRATION READINESS")
    print("=====================================")
    for check in state["checks"]:
        print(f"{'PASS' if check['passed'] else 'FAIL'}  {check['check_id']}")
        print(f"      {check['detail']}")
    print()
    print(f"Validated foundations: {'YES' if state['validated_foundations'] else 'NO'}")
    print(f"PDF integration switch enabled: {'YES' if state['pdf_integration_switch_enabled'] else 'NO'}")
    print(f"PDF integration ready: {'YES' if state['pdf_integration_ready'] else 'NO'}")
    print("Issued PET PDF enabled: NO")
    print("Machine export enabled: NO")
    print("Certification enabled: NO")
    if state["blocking_reasons"]:
        print("Blocking reasons:")
        for reason in state["blocking_reasons"]:
            print(f"  - {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
