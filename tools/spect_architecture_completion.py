"""Print the Step 37 SPECT architecture-completion assessment."""
from __future__ import annotations

from services.spect_architecture_completion import assess_spect_architecture_completion


def main() -> int:
    result = assess_spect_architecture_completion()
    print("SPECT STEP 37 ARCHITECTURE COMPLETION")
    print("=====================================")
    for check in result["checks"]:
        print(f"{'PASS' if check['passed'] else 'FAIL'}  {check['check_id']}")
        print(f"      {check['detail']}")
    print()
    print(
        "Current production-host architecture: "
        + ("COMPLETE" if result["architecture_complete_current_scope"] else "INCOMPLETE")
    )
    print("Issued PDF/export/certification in completion scope: NO")
    print(f"Completion scope: {result['completion_scope']}")
    return 0 if result["architecture_complete_current_scope"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
