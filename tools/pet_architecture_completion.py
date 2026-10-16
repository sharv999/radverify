"""Print the Step 29 PET architecture-completion assessment."""
from __future__ import annotations

from services.pet_architecture_completion import assess_pet_architecture_completion


def main() -> int:
    result = assess_pet_architecture_completion()
    print("PET STEP 29 ARCHITECTURE COMPLETION")
    print("===================================")
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
