from pathlib import Path
import json

from scripts.harness.checks import (
    FAIL,
    PASS,
    Finding,
    exit_code_for_findings,
    format_findings,
    format_findings_json,
    run_checks,
)


VALID_RAILWAY_TOML = (
    "[build]\n"
    'buildCommand = "pip install -r requirements.txt && '
    'python scripts/harness/verify.py --ci && pytest"\n'
    "\n"
    "[deploy]\n"
    'startCommand = "python main.py"\n'
    'healthcheckPath = "/"\n'
)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_minimal_repo(root: Path) -> None:
    write(root / "docs/AI_WORKFLOW.md", "# AI Workflow\n")
    write(root / "docs/DOCUMENTATION_WORKFLOW.md", "# Documentation Workflow\n")
    write(root / "docs/specs/_TEMPLATE.md", "# Spec Template\n")
    write(root / "docs/plans/_TEMPLATE.md", "# Plan Template\n")
    write(root / "docs/adrs/_TEMPLATE.md", "# ADR Template\n")
    write(
        root / "docs/harness/COMMANDS.md",
        "# Harness Commands\n\n"
        "- `.venv/bin/python main.py`\n"
        "- `.venv/bin/pytest`\n"
        "- `.venv/bin/python scripts/harness/check_docs.py`\n"
        "- `.venv/bin/python scripts/harness/verify.py --ci`\n"
        "- `python scripts/harness/verify.py --ci`\n"
        "- `pip install -r requirements.txt && python scripts/harness/verify.py --ci && pytest`\n",
    )
    write(root / "ROADMAP.md", "# Roadmap\n")
    write(root / "railway.toml", VALID_RAILWAY_TOML)
    (root / "docs/specs/archive").mkdir(parents=True)
    (root / "docs/plans/archive").mkdir(parents=True)
    write(
        root / "AGENTS.md",
        "Read `docs/AI_WORKFLOW.md` and `docs/DOCUMENTATION_WORKFLOW.md`.\n"
        "Run `.venv/bin/python main.py` and `.venv/bin/pytest`.\n",
    )
    write(
        root / "docs/AI_WORKFLOW.md",
        "# AI Workflow\n\n"
        "Run `.venv/bin/python scripts/harness/check_docs.py` locally.\n"
        "Run `.venv/bin/python scripts/harness/verify.py --ci` before closing work.\n",
    )
    write(
        root / "docs/specs/2026-04-30-feature.md",
        "# Spec: Feature\n\n"
        "## Metadata\n"
        "- **Status:** Approved\n"
        "- **Owner:** Codex\n",
    )
    write(
        root / "docs/plans/2026-04-30-feature.md",
        "# Plan: Feature\n\n"
        "## Objective & Context\n"
        "- **Status:** In Progress\n"
        "- **Source Spec:** `docs/specs/2026-04-30-feature.md`\n",
    )


def failures(root: Path) -> list[Finding]:
    return [finding for finding in run_checks(root) if finding.severity == FAIL]


def messages_for(root: Path, severity: str) -> set[str]:
    return {finding.message for finding in run_checks(root) if finding.severity == severity}


def test_required_workflow_files_are_enforced(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    (tmp_path / "docs/AI_WORKFLOW.md").unlink()

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Required workflow file is missing: docs/AI_WORKFLOW.md" in messages


def test_active_spec_and_plan_metadata_are_validated(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/specs/2026-04-29-done.md",
        "# Spec: Done\n\n## Metadata\n- **Status:** Implemented\n",
    )
    write(
        tmp_path / "docs/plans/2026-04-29-broken.md",
        "# Plan: Broken\n\n## Objective & Context\n- **Status:** Completed\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Implemented SPECs must be archived: docs/specs/2026-04-29-done.md" in messages
    assert "Completed PLANs must be archived: docs/plans/2026-04-29-broken.md" in messages
    assert "Active PLAN is missing Source Spec: docs/plans/2026-04-29-broken.md" in messages


def test_active_plan_source_spec_must_exist(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/plans/2026-04-29-missing-source.md",
        "# Plan: Missing Source\n\n"
        "## Objective & Context\n"
        "- **Status:** In Progress\n"
        "- **Source Spec:** `docs/specs/2026-04-29-missing-source.md`\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "PLAN Source Spec does not exist: docs/plans/2026-04-29-missing-source.md -> "
        "docs/specs/2026-04-29-missing-source.md"
    ) in messages


def test_adr_spec_and_plan_references_must_exist(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/adrs/2026-04-30-decision.md",
        "# ADR: Decision\n\n"
        "## Metadata\n"
        "- **Status:** Accepted\n"
        "- **Related Spec:** `docs/specs/archive/2026-04-30-feature.md`\n"
        "- **Related Plan:** `docs/plans/archive/2026-04-30-feature.md`\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "ADR reference does not exist: docs/adrs/2026-04-30-decision.md -> "
        "docs/specs/archive/2026-04-30-feature.md"
    ) in messages
    assert (
        "ADR reference does not exist: docs/adrs/2026-04-30-decision.md -> "
        "docs/plans/archive/2026-04-30-feature.md"
    ) in messages


def test_agent_entrypoints_must_reference_workflow_docs(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(tmp_path / "CLAUDE.md", "Read `docs/AI_WORKFLOW.md`.\n")

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "Agent entrypoint is missing docs/DOCUMENTATION_WORKFLOW.md reference: CLAUDE.md"
        in messages
    )


def test_stale_orchestration_references_fail(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(tmp_path / ".claude/agents/ynab-lead-architect.md", "Read docs/ORCHESTRATION.md\n")

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "Stale docs/ORCHESTRATION.md reference found: .claude/agents/ynab-lead-architect.md"
        in messages
    )


def test_advisory_mode_exits_zero_but_strict_mode_blocks() -> None:
    findings = [Finding(FAIL, "Broken", "docs/example.md")]

    assert exit_code_for_findings(findings, strict=False) == 0
    assert exit_code_for_findings(findings, strict=True) == 1


def test_format_findings_groups_pass_warn_and_fail() -> None:
    output = format_findings(
        [
            Finding(PASS, "Required file exists", "docs/AI_WORKFLOW.md"),
            Finding(FAIL, "Broken", "docs/example.md"),
        ]
    )

    assert "PASS" in output
    assert "WARN" in output
    assert "FAIL" in output
    assert "docs/example.md" in output


def test_format_findings_json_includes_counts_and_findings() -> None:
    output = format_findings_json(
        [
            Finding(PASS, "Required file exists", "docs/AI_WORKFLOW.md"),
            Finding(FAIL, "Broken", "docs/example.md"),
        ]
    )

    payload = json.loads(output)

    assert payload["summary"] == {"PASS": 1, "WARN": 0, "FAIL": 1, "total": 2}
    assert payload["findings"][1] == {
        "severity": "FAIL",
        "message": "Broken",
        "path": "docs/example.md",
    }


def test_valid_railway_config_reports_pass_findings(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)

    messages = messages_for(tmp_path, PASS)

    assert "Railway config file exists: railway.toml" in messages
    assert "Railway build command runs harness before pytest: railway.toml" in messages
    assert "Railway start command is expected app entrypoint: railway.toml" in messages


def test_railway_config_file_is_required(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    (tmp_path / "railway.toml").unlink()

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Required Railway config file is missing: railway.toml" in messages


def test_malformed_railway_config_fails(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(tmp_path / "railway.toml", "[build\n")

    messages = {finding.message for finding in failures(tmp_path)}

    assert any(message.startswith("Railway config is not valid TOML: railway.toml") for message in messages)


def test_railway_build_command_must_run_harness(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "railway.toml",
        "[build]\n"
        'buildCommand = "pip install -r requirements.txt && pytest"\n'
        "\n"
        "[deploy]\n"
        'startCommand = "python main.py"\n',
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Railway build command is missing harness verification: railway.toml" in messages


def test_railway_build_command_must_run_harness_before_pytest(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "railway.toml",
        "[build]\n"
        'buildCommand = "pip install -r requirements.txt && pytest && '
        'python scripts/harness/verify.py --ci"\n'
        "\n"
        "[deploy]\n"
        'startCommand = "python main.py"\n',
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Railway build command runs pytest before harness verification: railway.toml" in messages


def test_railway_start_command_must_use_expected_entrypoint(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "railway.toml",
        "[build]\n"
        'buildCommand = "pip install -r requirements.txt && '
        'python scripts/harness/verify.py --ci && pytest"\n'
        "\n"
        "[deploy]\n"
        'startCommand = "python other.py"\n',
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Railway start command must be `python main.py`: railway.toml" in messages


def test_command_registry_document_reports_pass_findings(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)

    messages = messages_for(tmp_path, PASS)

    assert "Command registry document exists: docs/harness/COMMANDS.md" in messages
    assert (
        "Command registry documents local advisory docs command: "
        "docs/harness/COMMANDS.md"
    ) in messages
    assert (
        "Living workflow doc references local CI harness command: docs/AI_WORKFLOW.md"
        in messages
    )
    assert "Agent entrypoint references run command: AGENTS.md" in messages
    assert "Agent entrypoint references test command: AGENTS.md" in messages


def test_command_registry_document_is_required(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    (tmp_path / "docs/harness/COMMANDS.md").unlink()

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Command registry document is missing: docs/harness/COMMANDS.md" in messages


def test_command_registry_document_must_include_canonical_commands(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/harness/COMMANDS.md",
        "# Harness Commands\n\n"
        "- `.venv/bin/python main.py`\n"
        "- `.venv/bin/pytest`\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "Command registry is missing local advisory docs command: "
        "docs/harness/COMMANDS.md -> .venv/bin/python scripts/harness/check_docs.py"
    ) in messages


def test_agent_entrypoints_must_reference_run_and_test_commands(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "CLAUDE.md",
        "Read `docs/AI_WORKFLOW.md` and `docs/DOCUMENTATION_WORKFLOW.md`.\n"
        "Run `.venv/bin/python main.py`.\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert "Agent entrypoint is missing test command `.venv/bin/pytest`: CLAUDE.md" in messages


def test_workflow_docs_must_reference_harness_commands(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/AI_WORKFLOW.md",
        "# AI Workflow\n\nNo executable harness commands here.\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "Living workflow doc is missing local advisory docs command "
        "`.venv/bin/python scripts/harness/check_docs.py`: docs/AI_WORKFLOW.md"
    ) in messages
    assert (
        "Living workflow doc is missing local CI harness command "
        "`.venv/bin/python scripts/harness/verify.py --ci`: docs/AI_WORKFLOW.md"
    ) in messages


def test_completed_archived_plan_cannot_have_unchecked_tasks(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/plans/archive/2026-04-30-done.md",
        "# Plan: Done\n\n"
        "## Objective & Context\n"
        "- **Status:** Completed\n"
        "- **Source Spec:** `docs/specs/archive/2026-04-30-done.md`\n"
        "- **Harness Roadmap Marker:** E.99\n\n"
        "## Verification\n"
        "- [x] Checked\n"
        "- [ ] Not checked\n",
    )
    write(
        tmp_path / "docs/specs/archive/2026-04-30-done.md",
        "# Spec: Done\n\n"
        "## Metadata\n"
        "- **Status:** Implemented\n"
        "- **Harness Roadmap Marker:** E.99\n",
    )
    write(tmp_path / "ROADMAP.md", "### E.99 — Done [COMPLETADO]\n")

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "Completed archived PLAN has unchecked task boxes: "
        "docs/plans/archive/2026-04-30-done.md"
    ) in messages


def test_implemented_archived_spec_requires_roadmap_marker_present_in_roadmap(
    tmp_path: Path,
) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/specs/archive/2026-04-30-missing-roadmap.md",
        "# Spec: Missing Roadmap\n\n"
        "## Metadata\n"
        "- **Status:** Implemented\n"
        "- **Harness Roadmap Marker:** E.404\n",
    )
    write(tmp_path / "ROADMAP.md", "### E.99 — Other [COMPLETADO]\n")

    messages = {finding.message for finding in failures(tmp_path)}

    assert (
        "Implemented archived SPEC roadmap marker is missing from ROADMAP.md: "
        "docs/specs/archive/2026-04-30-missing-roadmap.md -> E.404"
    ) in messages


def test_roadmap_ignore_metadata_skips_historical_documents(tmp_path: Path) -> None:
    make_minimal_repo(tmp_path)
    write(
        tmp_path / "docs/specs/archive/2026-04-30-historical.md",
        "# Spec: Historical\n\n"
        "## Metadata\n"
        "- **Status:** Implemented\n"
        "- **Harness Roadmap:** Ignore\n",
    )
    write(
        tmp_path / "docs/plans/archive/2026-04-30-historical.md",
        "# Plan: Historical\n\n"
        "## Objective & Context\n"
        "- **Status:** Completed\n"
        "- **Source Spec:** `docs/specs/archive/2026-04-30-historical.md`\n"
        "- **Harness Roadmap:** Ignore\n"
        "- [ ] Historical unchecked task\n",
    )

    messages = {finding.message for finding in failures(tmp_path)}

    assert all("2026-04-30-historical.md" not in message for message in messages)
