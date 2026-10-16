"""CLI wrapper for canonical PET deterministic-regression verification."""
from __future__ import annotations

import argparse
import sys
from typing import Sequence

from services.pet_regression_verification import (
    PetCliRegressionError,
    PetCliRegressionEntry,
    PetCliRegressionManifest,
    PetCliRegressionCaseResult,
    PetCliRegressionRunResult,
    canonical_payload_sha256,
    load_pet_cli_regression_manifest,
    run_pet_cli_regression_manifest,
    render_pet_cli_regression_summary,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run all approved non-production PET CLI regression fixtures."
    )
    parser.add_argument("manifest", help="Path to the PET CLI regression manifest JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = run_pet_cli_regression_manifest(args.manifest)
    except PetCliRegressionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(render_pet_cli_regression_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
