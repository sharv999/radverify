"""CLI for the SPECT Step 24 production-dispatch readiness audit."""
from __future__ import annotations

from engine.spect_production_dispatch_gate import assess_spect_production_dispatch_readiness


def main() -> int:
    result = assess_spect_production_dispatch_readiness()
    print("SPECT STEP 24 PRODUCTION-DISPATCH READINESS")
    print("===========================================")
    print(f"Validated foundations: {'YES' if result.validated_foundations else 'NO'}")
    print(f"Production ready: {'YES' if result.production_ready else 'NO'}")
    print(f"Dispatch enabled: {'YES' if result.dispatch_enabled else 'NO'}")
    print()
    for check in result.checks:
        print(f"[{check.status}] {check.name}")
        print(f"  {check.detail}")
    if result.blocking_reasons:
        print("\nBLOCKING REASONS")
        for reason in result.blocking_reasons:
            print(f"- {reason}")
    return 0 if result.validated_foundations else 1


if __name__ == "__main__":
    raise SystemExit(main())
