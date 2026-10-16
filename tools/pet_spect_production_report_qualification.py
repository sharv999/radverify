from services.pet_spect_production_report_qualification import require_step41_production_report_qualification

def main() -> int:
    result = require_step41_production_report_qualification()
    print("PET/SPECT STEP 41 PRODUCTION REPORT QUALIFICATION")
    print("=" * 51)
    print(f"Save/reopen deterministic replay: {'PASS' if result['save_reopen_replay_qualified'] else 'FAIL'}")
    print(f"Results-to-report equivalence: {'PASS' if result['results_report_equivalence_qualified'] else 'FAIL'}")
    print(f"Representative known-answer cases: {'PASS' if result['known_answer_cases_qualified'] else 'FAIL'}")
    print(f"Visual report validation: {'PASS' if result['visual_report_validation_qualified'] else 'FAIL'}")
    print(f"Production report qualification complete: {'YES' if result['production_report_qualification_complete'] else 'NO'}")
    print(f"Issued PDF enabled: {'YES' if result['issued_pdf_enabled'] else 'NO'}")
    print(f"Machine export enabled: {'YES' if result['machine_export_enabled'] else 'NO'}")
    print(f"Certification enabled: {'YES' if result['certification_enabled'] else 'NO'}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
