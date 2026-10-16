"""CLI wrapper for canonical SPECT calculation-request execution services."""
from __future__ import annotations

import argparse
import sys

from services.spect_calculation_request_runner import (
    SpectCalculationRequestCliError,
    render_request_validation,
    replay_request_file,
    run_request_file,
)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("validate", "run", "replay"))
    ap.add_argument("request")
    args = ap.parse_args(argv)
    try:
        if args.command == "validate":
            print(render_request_validation(args.request))
        elif args.command == "run":
            print(run_request_file(args.request)[1])
        else:
            print(replay_request_file(args.request)[1])
    except SpectCalculationRequestCliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
