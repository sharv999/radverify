"""CLI wrapper for canonical SPECT deterministic-regression verification."""
from __future__ import annotations

import argparse
import sys

from services.spect_calculation_request_runner import SpectCalculationRequestCliError
from services.spect_regression_verification import (
    SCHEMA,
    VERSION,
    SpectCliRegressionError,
    canonical_payload_sha256,
    load_manifest,
    run_manifest,
)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    args = ap.parse_args(argv)
    try:
        p, cases = run_manifest(args.manifest)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print("SPECT CLI REGRESSION MANIFEST\n=============================\n" + f"Manifest: {p}\nFixtures: {len(cases)}")
    for fid, rp, digest in cases:
        print(f"\n[{fid}] PASS\n  Request: {rp}\n  Output SHA-256: {digest}\n  Replay verified: yes")
    print("\nOverall status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
