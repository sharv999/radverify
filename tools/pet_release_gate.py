"""Print the final Step 29 PET controlled-host release assessment."""
from __future__ import annotations

from services.pet_release_gate import assess_pet_release_gate


def main() -> int:
    result = assess_pet_release_gate()
    print("PET STEP 29 FINAL RELEASE GATE")
    print("==============================")
    for check in result["checks"]:
        print(f"{'PASS' if check['passed'] else 'FAIL'}  {check['check_id']}")
        print(f"      {check['detail']}")
    print()
    print(
        "Controlled production-host release: "
        + ("GO" if result["controlled_host_release_ready"] else "NO-GO")
    )
    print("Issued PDF/export/certification release: NO-GO")
    print(f"Release scope: {result['release_scope']}")
    if result["cleanup_debt"]:
        print("Cleanup debt:")
        for item in result["cleanup_debt"]:
            print(f"  - {item}")
    return 0 if result["controlled_host_release_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
