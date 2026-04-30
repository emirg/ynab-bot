from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.harness.checks import (
    exit_code_for_findings,
    format_findings,
    format_findings_json,
    run_checks,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run documentation workflow diagnostics.")
    parser.add_argument("--root", default=".", help="Repository root to check.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit nonzero when documentation workflow failures are found.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON diagnostics.")
    args = parser.parse_args(argv)

    findings = run_checks(Path(args.root).resolve())
    print(format_findings_json(findings) if args.json else format_findings(findings))
    return exit_code_for_findings(findings, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
