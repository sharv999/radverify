"""CLI for the SPECT Step 32 PDF integration readiness gate."""
from __future__ import annotations

from services.spect_pdf_integration_readiness_gate import assess_spect_pdf_integration_readiness


def main() -> int:
    state = assess_spect_pdf_integration_readiness()
    print("SPECT STEP 32 PDF INTEGRATION READINESS")
    print("=======================================")
    for check in state["checks"]:
        print(f"{'PASS' if check['passed'] else 'FAIL'}  {check['check_id']}")
        print(f"      {check['detail']}")
    print()
    print(f"Validated foundations: {'YES' if state['validated_foundations'] else 'NO'}")
    print(f"PDF integration switch enabled: {'YES' if state['pdf_integration_switch_enabled'] else 'NO'}")
    print(f"PDF integration ready: {'YES' if state['pdf_integration_ready'] else 'NO'}")
    print("Issued SPECT PDF enabled: NO")
    print("Machine export enabled: NO")
    print("Certification enabled: NO")
    if state["blocking_reasons"]:
        print("Blocking reasons:")
        for reason in state["blocking_reasons"]:
            print(f"  - {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
