"""CLI for PET Step 26 production-host readiness audit."""
from services.pet_production_host_readiness_gate import audit_pet_production_host_readiness


def main() -> int:
    result = audit_pet_production_host_readiness()
    print("PET STEP 26 PRODUCTION-HOST READINESS")
    print("=====================================")
    for row in result["checks"]:
        print(f"{row['status']:4}  {row['name']}: {row['detail']}")
    print()
    print(f"Validated foundations: {'YES' if result['validated_foundations'] else 'NO'}")
    print(f"Production host integration enabled: {'YES' if result['production_host_integration_enabled'] else 'NO'}")
    print(f"Production host ready: {'YES' if result['production_host_ready'] else 'NO'}")
    print(f"Issued PDF/export/certification enabled: {'YES' if result['issued_output_enabled'] else 'NO'}")
    if result["blocking_checks"]:
        print("Blocking host checks: " + ", ".join(result["blocking_checks"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
