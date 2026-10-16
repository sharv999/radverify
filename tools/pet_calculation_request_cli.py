"""CLI wrapper for canonical PET calculation-request execution services."""
from __future__ import annotations

import argparse
import sys
from typing import Sequence

from services.pet_calculation_request_runner import (
    PetCalculationRequestCliError,
    render_request_validation,
    run_request_file,
    replay_request_file,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate, run, or replay a non-production PET calculation request."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="Validate and summarize a request file.")
    validate.add_argument("request", help="Path to the PET request JSON file.")
    for command in ("run", "replay"):
        child = subparsers.add_parser(
            command,
            help="Execute a validated request." if command == "run" else "Execute twice and verify deterministic replay.",
        )
        child.add_argument("request", help="Path to the PET request JSON file.")
        child.add_argument("--output", help="Optional path for the non-production result snapshot JSON.")
        child.add_argument("--overwrite", action="store_true", help="Explicitly allow replacement of an existing output file.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            print(render_request_validation(args.request))
        elif args.command == "run":
            _, summary = run_request_file(args.request, output=args.output, overwrite=args.overwrite)
            print(summary)
        else:
            _, summary = replay_request_file(args.request, output=args.output, overwrite=args.overwrite)
            print(summary)
    except PetCalculationRequestCliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
