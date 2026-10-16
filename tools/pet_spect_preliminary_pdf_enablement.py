from __future__ import annotations

from services.pet_spect_preliminary_pdf_issuance import assess_step42_preliminary_pdf_enablement


def main() -> int:
    result = assess_step42_preliminary_pdf_enablement()
    print("PET/SPECT STEP 42 PRELIMINARY PDF ENABLEMENT")
    print("=" * 48)
    print(f"Step 41 qualification complete: {'YES' if result['step41_qualification_complete'] else 'NO'}")
    print(f"Preliminary PDF enabled: {'YES' if result['preliminary_pdf_enabled'] else 'NO'}")
    print(f"Final/certified PDF enabled: {'YES' if result['final_or_certified_pdf_enabled'] else 'NO'}")
    print(f"Machine export enabled: {'YES' if result['machine_export_enabled'] else 'NO'}")
    print(f"Certification enabled: {'YES' if result['certification_enabled'] else 'NO'}")
    print(f"Signatures enabled: {'YES' if result['signature_enabled'] else 'NO'}")
    return 0 if result["step41_qualification_complete"] and result["preliminary_pdf_enabled"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
