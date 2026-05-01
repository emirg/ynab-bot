from pathlib import Path
import json

from scripts.harness.checks import FAIL, run_checks
from scripts.harness.check_docs import main as check_docs_main
from scripts.harness.check_financial_invariants import main as check_financial_main


def test_checked_in_documentation_passes_harness() -> None:
    root = Path(__file__).resolve().parents[2]

    failures = [finding for finding in run_checks(root) if finding.severity == FAIL]

    assert failures == []


def test_railway_build_runs_harness_before_pytest() -> None:
    root = Path(__file__).resolve().parents[2]
    railway_toml = (root / "railway.toml").read_text(encoding="utf-8")

    assert (
        'buildCommand = "pip install -r requirements.txt && '
        'python scripts/harness/verify.py --ci && pytest"'
    ) in railway_toml


def test_check_docs_json_cli_outputs_valid_json(capsys) -> None:
    root = Path(__file__).resolve().parents[2]

    exit_code = check_docs_main(["--root", str(root), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["summary"]["FAIL"] == 0
    assert isinstance(payload["findings"], list)


def test_check_financial_invariants_json_cli_outputs_valid_json(capsys) -> None:
    root = Path(__file__).resolve().parents[2]

    exit_code = check_financial_main(["--root", str(root), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["summary"] == {"FAIL": 0, "PASS": 5, "WARN": 0, "total": 5}
    assert isinstance(payload["findings"], list)
