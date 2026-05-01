from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import tomllib
from typing import Iterable

from scripts.harness.behavioral_invariants import run_behavioral_invariants
from scripts.harness.commands import (
    COMMAND_REGISTRY,
    LOCAL_CHECK_BEHAVIORAL_INVARIANTS,
    LOCAL_CHECK_DOCS,
    LOCAL_RUN,
    LOCAL_TEST,
    LOCAL_VERIFY_CI,
    RAILWAY_BUILD_COMMAND,
    RAILWAY_PYTEST,
    RAILWAY_START,
    RAILWAY_VERIFY_CI,
)

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

REQUIRED_FILES = (
    "docs/AI_WORKFLOW.md",
    "docs/DOCUMENTATION_WORKFLOW.md",
    "docs/specs/_TEMPLATE.md",
    "docs/plans/_TEMPLATE.md",
    "docs/adrs/_TEMPLATE.md",
)
AGENT_ENTRYPOINTS = ("AGENTS.md", "CLAUDE.md", "GEMINI.md")
ARCHIVE_DIRS = ("docs/specs/archive", "docs/plans/archive")
TERMINAL_STATUSES = {"completed", "implemented"}
VALID_SPEC_STATUSES = {"draft", "approved", "superseded", "completed", "implemented"}
VALID_PLAN_STATUSES = {"draft", "in progress", "completed", "implemented", "superseded"}
SKIPPED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "htmlcov",
}

STATUS_RE = re.compile(r"^\s*-\s+\*\*Status:\*\*\s*(.+?)\s*$", re.MULTILINE)
SOURCE_SPEC_RE = re.compile(
    r"^\s*-\s+\*\*Source Spec:\*\*\s*`([^`]+)`\s*$", re.MULTILINE
)
ADR_DOC_REF_RE = re.compile(r"`(docs/(?:specs|plans)/(?:archive/)?[^`]+\.md)`")
ROADMAP_MARKER_RE = re.compile(
    r"^\s*-\s+\*\*Harness Roadmap Marker:\*\*\s*(.+?)\s*$", re.MULTILINE
)
ROADMAP_IGNORE_RE = re.compile(
    r"^\s*-\s+\*\*Harness Roadmap:\*\*\s*Ignore\s*$",
    re.IGNORECASE | re.MULTILINE,
)
UNCHECKED_TASK_RE = re.compile(r"^\s*-\s+\[\s\]\s+", re.MULTILINE)
COMMAND_REGISTRY_DOC = "docs/harness/COMMANDS.md"
WORKFLOW_COMMAND_DOCS = ("docs/AI_WORKFLOW.md",)


@dataclass(frozen=True)
class Finding:
    severity: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class InvariantEvidenceFile:
    path: str
    snippets: tuple[str, ...]


@dataclass(frozen=True)
class FinancialInvariantEvidence:
    label: str
    docs: tuple[InvariantEvidenceFile, ...] = ()
    sources: tuple[InvariantEvidenceFile, ...] = ()
    tests: tuple[InvariantEvidenceFile, ...] = ()


FINANCIAL_INVARIANT_EVIDENCE = (
    FinancialInvariantEvidence(
        label="milliunit expense conversion",
        docs=(
            InvariantEvidenceFile(
                "docs/AI_WORKFLOW.md",
                (
                    "YNAB amounts are ×1000",
                    "Expenses are negative",
                ),
            ),
        ),
        sources=(
            InvariantEvidenceFile(
                "src/domain/models/expense.py",
                (
                    "amount_milliunits = int(self.amount * -1000)",
                    '"amount": amount_milliunits',
                ),
            ),
        ),
        tests=(
            InvariantEvidenceFile(
                "tests/domain/models/test_domain_models.py",
                (
                    "test_to_ynab_format_with_valid_category",
                    "assert txn['amount'] == -25000000",
                ),
            ),
        ),
    ),
    FinancialInvariantEvidence(
        label="transaction spending totals",
        docs=(
            InvariantEvidenceFile(
                "docs/AI_WORKFLOW.md",
                ("Spending totals use transactions",),
            ),
            InvariantEvidenceFile(
                "docs/adrs/2026-04-12-ynab-source-of-truth.md",
                ("Monthly spending totals still come from transactions",),
            ),
        ),
        sources=(
            InvariantEvidenceFile(
                "src/domain/services/spending_aggregation.py",
                (
                    "def summarize_transaction_net_spending",
                    "net_activity_by_key",
                ),
            ),
            InvariantEvidenceFile(
                "src/application/services/budget_query_service.py",
                ("summarize_transaction_net_spending(transactions)",),
            ),
        ),
        tests=(
            InvariantEvidenceFile(
                "tests/domain/services/test_spending_aggregation.py",
                (
                    "test_summarize_transaction_net_spending_offsets_category_inflows",
                    "test_summarize_transaction_net_spending_nets_split_tracking_inflows_against_month_total",
                ),
            ),
            InvariantEvidenceFile(
                "tests/application/services/test_budget_query_service.py",
                (
                    "test_budget_summary_uses_transactions_for_spending_totals_and_top_categories",
                    "test_budget_summary_nets_category_inflows_from_transactions",
                ),
            ),
        ),
    ),
    FinancialInvariantEvidence(
        label="budget health category snapshots",
        docs=(
            InvariantEvidenceFile(
                "docs/AI_WORKFLOW.md",
                ("budget health uses category snapshots",),
            ),
            InvariantEvidenceFile(
                "docs/adrs/2026-04-12-ynab-source-of-truth.md",
                ("YNAB category activity/balance",),
            ),
        ),
        sources=(
            InvariantEvidenceFile(
                "src/domain/services/spending_aggregation.py",
                (
                    "def normalize_budget_category_snapshots",
                    '"balance": balance',
                ),
            ),
            InvariantEvidenceFile(
                "src/application/services/advisor_dashboard_service.py",
                (
                    "normalize_budget_category_snapshots",
                    'remaining = entry["balance"]',
                ),
            ),
        ),
        tests=(
            InvariantEvidenceFile(
                "tests/domain/services/test_spending_aggregation.py",
                ("test_normalize_budget_category_snapshots_filters_inactive_hidden_and_deleted",),
            ),
            InvariantEvidenceFile(
                "tests/application/services/test_advisor_dashboard_service.py",
                ("test_build_dashboard_month_uses_balance_for_overspending",),
            ),
        ),
    ),
    FinancialInvariantEvidence(
        label="account balances from account fields",
        docs=(
            InvariantEvidenceFile(
                "docs/AI_WORKFLOW.md",
                ("account balances use account fields",),
            ),
        ),
        sources=(
            InvariantEvidenceFile(
                "src/application/services/budget_query_service.py",
                (
                    "def _query_account_balance",
                    "'balance': account.balance",
                    "'cleared_balance': account.cleared_balance",
                    "'uncleared_balance': account.uncleared_balance",
                ),
            ),
        ),
        tests=(
            InvariantEvidenceFile(
                "tests/application/services/test_budget_query_service.py",
                (
                    "class TestAccountBalance",
                    "assert result.data['balance'] == -500000",
                    "assert result.data['cleared_balance'] == -400000",
                ),
            ),
        ),
    ),
    FinancialInvariantEvidence(
        label="recent edit undo convenience boundary",
        docs=(
            InvariantEvidenceFile(
                "docs/AI_WORKFLOW.md",
                ("recent/edit/undo state is convenience-only",),
            ),
            InvariantEvidenceFile(
                "docs/adrs/2026-04-25-recent-edit-live-ynab-reconciliation.md",
                ("local recent metadata can drift from YNAB",),
            ),
        ),
        sources=(
            InvariantEvidenceFile(
                "src/application/services/expense_service.py",
                (
                    "def _get_live_transaction_state_for_edit",
                    "ynab_repository.get_transaction_by_id",
                    "update_recent_transaction",
                    "delete_recent_transaction",
                ),
            ),
        ),
        tests=(
            InvariantEvidenceFile(
                "tests/application/services/test_expense_service.py",
                (
                    "test_missing_live_ynab_transaction_blocks_edit",
                    "test_successful_edit_refreshes_recent_cache_from_live_transaction",
                    "test_success_removes_from_recent_transactions",
                ),
            ),
        ),
    ),
)


def run_checks(root: Path | str) -> list[Finding]:
    repo_root = Path(root)
    findings: list[Finding] = []
    findings.extend(check_required_files(repo_root))
    findings.extend(check_active_specs(repo_root))
    findings.extend(check_active_plans(repo_root))
    findings.extend(check_adr_references(repo_root))
    findings.extend(check_agent_entrypoints(repo_root))
    findings.extend(check_stale_orchestration_references(repo_root))
    findings.extend(check_archived_completed_plans(repo_root))
    findings.extend(check_roadmap_coherence(repo_root))
    findings.extend(check_railway_config(repo_root))
    findings.extend(check_command_registry(repo_root))
    findings.extend(check_financial_invariants(repo_root))
    findings.extend(check_behavioral_invariants(repo_root))
    return findings


def check_required_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative in REQUIRED_FILES:
        if (root / relative).is_file():
            findings.append(Finding(PASS, f"Required workflow file exists: {relative}", relative))
        else:
            findings.append(Finding(FAIL, f"Required workflow file is missing: {relative}", relative))
    for relative in ARCHIVE_DIRS:
        if (root / relative).is_dir():
            findings.append(Finding(PASS, f"Required archive directory exists: {relative}", relative))
        else:
            findings.append(Finding(FAIL, f"Required archive directory is missing: {relative}", relative))
    return findings


def check_active_specs(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    specs_dir = root / "docs/specs"
    for path in sorted(specs_dir.glob("*.md")) if specs_dir.is_dir() else []:
        if path.name == "_TEMPLATE.md":
            continue
        relative = relative_path(path, root)
        text = read_text(path)
        status = parse_status(text)
        if status is None:
            findings.append(Finding(FAIL, f"Active SPEC is missing Status metadata: {relative}", relative))
            continue
        normalized = normalize_status(status)
        if normalized not in VALID_SPEC_STATUSES:
            findings.append(Finding(FAIL, f"Active SPEC has invalid Status metadata: {relative}", relative))
        elif normalized in TERMINAL_STATUSES:
            findings.append(Finding(FAIL, f"Implemented SPECs must be archived: {relative}", relative))
        else:
            findings.append(Finding(PASS, f"Active SPEC metadata is valid: {relative}", relative))
    return findings


def check_active_plans(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    plans_dir = root / "docs/plans"
    for path in sorted(plans_dir.glob("*.md")) if plans_dir.is_dir() else []:
        if path.name == "_TEMPLATE.md":
            continue
        relative = relative_path(path, root)
        text = read_text(path)
        status = parse_status(text)
        if status is None:
            findings.append(Finding(FAIL, f"Active PLAN is missing Status metadata: {relative}", relative))
        else:
            normalized = normalize_status(status)
            if normalized not in VALID_PLAN_STATUSES:
                findings.append(Finding(FAIL, f"Active PLAN has invalid Status metadata: {relative}", relative))
            elif normalized in TERMINAL_STATUSES:
                label = "Completed" if normalized == "completed" else "Implemented"
                findings.append(Finding(FAIL, f"{label} PLANs must be archived: {relative}", relative))
            else:
                findings.append(Finding(PASS, f"Active PLAN metadata is valid: {relative}", relative))

        source_spec = parse_source_spec(text)
        if source_spec is None:
            findings.append(Finding(FAIL, f"Active PLAN is missing Source Spec: {relative}", relative))
        elif not (root / source_spec).is_file():
            findings.append(
                Finding(
                    FAIL,
                    f"PLAN Source Spec does not exist: {relative} -> {source_spec}",
                    relative,
                )
            )
        else:
            findings.append(Finding(PASS, f"Active PLAN Source Spec exists: {relative}", relative))
    return findings


def check_adr_references(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    adrs_dir = root / "docs/adrs"
    for path in sorted(adrs_dir.glob("*.md")) if adrs_dir.is_dir() else []:
        if path.name == "_TEMPLATE.md":
            continue
        relative = relative_path(path, root)
        refs = sorted(set(ADR_DOC_REF_RE.findall(read_text(path))))
        if not refs:
            findings.append(Finding(WARN, f"ADR has no SPEC/PLAN references: {relative}", relative))
            continue
        for reference in refs:
            if (root / reference).is_file():
                findings.append(Finding(PASS, f"ADR reference exists: {relative} -> {reference}", relative))
            else:
                findings.append(
                    Finding(FAIL, f"ADR reference does not exist: {relative} -> {reference}", relative)
                )
    return findings


def check_agent_entrypoints(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative in AGENT_ENTRYPOINTS:
        path = root / relative
        if not path.exists():
            findings.append(Finding(WARN, f"Agent entrypoint is absent: {relative}", relative))
            continue
        text = read_text(path)
        for workflow_doc in ("docs/AI_WORKFLOW.md", "docs/DOCUMENTATION_WORKFLOW.md"):
            if workflow_doc in text:
                findings.append(
                    Finding(PASS, f"Agent entrypoint references {workflow_doc}: {relative}", relative)
                )
            else:
                findings.append(
                    Finding(
                        FAIL,
                        f"Agent entrypoint is missing {workflow_doc} reference: {relative}",
                        relative,
                    )
                )
        findings.extend(check_agent_entrypoint_commands(text, relative))
    return findings


def check_agent_entrypoint_commands(text: str, relative: str) -> list[Finding]:
    findings: list[Finding] = []
    for command in (LOCAL_RUN, LOCAL_TEST):
        command_name = "run" if command == LOCAL_RUN else "test"
        if command.command in text:
            findings.append(Finding(PASS, f"Agent entrypoint references {command_name} command: {relative}", relative))
        else:
            findings.append(
                Finding(FAIL, f"Agent entrypoint is missing {command_name} command `{command.command}`: {relative}", relative)
            )
    return findings


def check_stale_orchestration_references(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_markdown_files(root):
        relative = relative_path(path, root)
        if relative == "docs/ORCHESTRATION.md":
            findings.append(Finding(FAIL, "Stale docs/ORCHESTRATION.md file found", relative))
            continue
        if "docs/ORCHESTRATION.md" in read_text(path):
            findings.append(Finding(FAIL, f"Stale docs/ORCHESTRATION.md reference found: {relative}", relative))
    if not findings:
        findings.append(Finding(PASS, "No stale docs/ORCHESTRATION.md references found", None))
    return findings


def check_archived_completed_plans(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    archive_dir = root / "docs/plans/archive"
    for path in sorted(archive_dir.glob("*.md")) if archive_dir.is_dir() else []:
        relative = relative_path(path, root)
        text = read_text(path)
        if has_roadmap_ignore(text):
            findings.append(Finding(PASS, f"Archived PLAN checklist ignored by metadata: {relative}", relative))
            continue
        status = parse_status(text)
        if normalize_status(status or "") != "completed":
            continue
        if UNCHECKED_TASK_RE.search(text):
            findings.append(Finding(FAIL, f"Completed archived PLAN has unchecked task boxes: {relative}", relative))
        else:
            findings.append(Finding(PASS, f"Completed archived PLAN task boxes are checked: {relative}", relative))
    return findings


def check_roadmap_coherence(root: Path) -> list[Finding]:
    roadmap_path = root / "ROADMAP.md"
    if not roadmap_path.is_file():
        return [Finding(FAIL, "Required roadmap file is missing: ROADMAP.md", "ROADMAP.md")]

    roadmap_text = read_text(roadmap_path)
    findings: list[Finding] = []
    findings.extend(check_archived_doc_roadmap_markers(root, "docs/specs/archive", "SPEC", "implemented", roadmap_text))
    findings.extend(check_archived_doc_roadmap_markers(root, "docs/plans/archive", "PLAN", "completed", roadmap_text))
    return findings


def check_archived_doc_roadmap_markers(
    root: Path,
    archive_dir: str,
    doc_label: str,
    required_status: str,
    roadmap_text: str,
) -> list[Finding]:
    findings: list[Finding] = []
    directory = root / archive_dir
    for path in sorted(directory.glob("*.md")) if directory.is_dir() else []:
        relative = relative_path(path, root)
        text = read_text(path)
        if has_roadmap_ignore(text):
            findings.append(Finding(PASS, f"Archived {doc_label} roadmap check ignored by metadata: {relative}", relative))
            continue
        status = parse_status(text)
        if normalize_status(status or "") != required_status:
            continue
        marker = parse_roadmap_marker(text)
        status_label = "Implemented" if doc_label == "SPEC" else "Completed"
        if marker is None:
            findings.append(
                Finding(
                    FAIL,
                    f"{status_label} archived {doc_label} is missing Harness Roadmap Marker: {relative}",
                    relative,
                )
            )
        elif marker not in roadmap_text:
            findings.append(
                Finding(
                    FAIL,
                    f"{status_label} archived {doc_label} roadmap marker is missing from ROADMAP.md: "
                    f"{relative} -> {marker}",
                    relative,
                )
            )
        else:
            findings.append(
                Finding(PASS, f"{status_label} archived {doc_label} roadmap marker exists: {relative}", relative)
            )
    return findings


def check_railway_config(root: Path) -> list[Finding]:
    relative = "railway.toml"
    path = root / relative
    if not path.is_file():
        return [Finding(FAIL, f"Required Railway config file is missing: {relative}", relative)]

    findings = [Finding(PASS, f"Railway config file exists: {relative}", relative)]
    try:
        config = tomllib.loads(read_text(path))
    except tomllib.TOMLDecodeError as exc:
        return [
            findings[0],
            Finding(FAIL, f"Railway config is not valid TOML: {relative}: {exc}", relative),
        ]

    build_config = config.get("build")
    if not isinstance(build_config, dict):
        findings.append(Finding(FAIL, f"Railway config is missing [build] section: {relative}", relative))
    else:
        build_command = build_config.get("buildCommand")
        if not isinstance(build_command, str) or not build_command.strip():
            findings.append(Finding(FAIL, f"Railway build command is missing: {relative}", relative))
        else:
            findings.extend(check_railway_build_command(build_command, relative))

    deploy_config = config.get("deploy")
    if not isinstance(deploy_config, dict):
        findings.append(Finding(FAIL, f"Railway config is missing [deploy] section: {relative}", relative))
    else:
        start_command = deploy_config.get("startCommand")
        if start_command == RAILWAY_START.command:
            findings.append(Finding(PASS, f"Railway start command is expected app entrypoint: {relative}", relative))
        else:
            findings.append(Finding(FAIL, f"Railway start command must be `{RAILWAY_START.command}`: {relative}", relative))

    return findings


def check_railway_build_command(build_command: str, relative: str) -> list[Finding]:
    findings: list[Finding] = []
    harness_index = build_command.find(RAILWAY_VERIFY_CI.command)
    pytest_index = build_command.find(RAILWAY_PYTEST.command)

    if harness_index == -1:
        findings.append(Finding(FAIL, f"Railway build command is missing harness verification: {relative}", relative))
    if pytest_index == -1:
        findings.append(Finding(FAIL, f"Railway build command is missing pytest: {relative}", relative))
    if harness_index != -1 and pytest_index != -1:
        if harness_index < pytest_index:
            findings.append(Finding(PASS, f"Railway build command runs harness before pytest: {relative}", relative))
        else:
            findings.append(
                Finding(FAIL, f"Railway build command runs pytest before harness verification: {relative}", relative)
            )

    return findings


def check_command_registry(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(check_command_registry_document(root))
    findings.extend(check_workflow_command_docs(root))
    return findings


def check_command_registry_document(root: Path) -> list[Finding]:
    relative = COMMAND_REGISTRY_DOC
    path = root / relative
    if not path.is_file():
        return [Finding(FAIL, f"Command registry document is missing: {relative}", relative)]

    text = read_text(path)
    findings = [Finding(PASS, f"Command registry document exists: {relative}", relative)]
    for command in COMMAND_REGISTRY:
        if command.command in text:
            findings.append(Finding(PASS, f"Command registry documents {command.label}: {relative}", relative))
        else:
            findings.append(
                Finding(FAIL, f"Command registry is missing {command.label}: {relative} -> {command.command}", relative)
            )
    if RAILWAY_BUILD_COMMAND in text:
        findings.append(Finding(PASS, f"Command registry documents Railway build command: {relative}", relative))
    else:
        findings.append(
            Finding(FAIL, f"Command registry is missing Railway build command: {relative} -> {RAILWAY_BUILD_COMMAND}", relative)
        )
    return findings


def check_workflow_command_docs(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative in WORKFLOW_COMMAND_DOCS:
        path = root / relative
        if not path.is_file():
            continue
        text = read_text(path)
        for command in (LOCAL_CHECK_DOCS, LOCAL_VERIFY_CI):
            if command.command in text:
                findings.append(Finding(PASS, f"Living workflow doc references {command.label}: {relative}", relative))
            else:
                findings.append(
                    Finding(
                        FAIL,
                        f"Living workflow doc is missing {command.label} `{command.command}`: {relative}",
                        relative,
                    )
                )
    return findings


def check_financial_invariants(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for invariant in FINANCIAL_INVARIANT_EVIDENCE:
        invariant_failures: list[Finding] = []
        invariant_failures.extend(check_invariant_evidence_group(root, invariant, "doc", invariant.docs))
        invariant_failures.extend(check_invariant_evidence_group(root, invariant, "source", invariant.sources))
        invariant_failures.extend(check_invariant_evidence_group(root, invariant, "test", invariant.tests))

        if invariant_failures:
            findings.extend(invariant_failures)
        else:
            findings.append(Finding(PASS, f"Financial invariant evidence exists: {invariant.label}", None))
    return findings


def check_behavioral_invariants(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for result in run_behavioral_invariants(root):
        context = f"{result.label} [{result.risk_area}: {result.protected_rule}]"
        if result.passed:
            findings.append(Finding(PASS, f"Behavioral invariant holds: {context}", result.path))
        else:
            findings.append(
                Finding(
                    FAIL,
                    f"Behavioral invariant failed: {context}: {result.message}",
                    result.path,
                )
            )
    return findings


def check_invariant_evidence_group(
    root: Path,
    invariant: FinancialInvariantEvidence,
    evidence_kind: str,
    evidence_files: tuple[InvariantEvidenceFile, ...],
) -> list[Finding]:
    findings: list[Finding] = []
    for evidence_file in evidence_files:
        path = root / evidence_file.path
        if not path.is_file():
            findings.append(
                Finding(
                    FAIL,
                    f"Financial invariant {evidence_kind} evidence file is missing for "
                    f"{invariant.label}: {evidence_file.path}",
                    evidence_file.path,
                )
            )
            continue

        text = read_text(path)
        for snippet in evidence_file.snippets:
            if snippet not in text:
                findings.append(
                    Finding(
                        FAIL,
                        f"Financial invariant {evidence_kind} evidence is missing for "
                        f"{invariant.label}: {evidence_file.path} -> {snippet}",
                        evidence_file.path,
                    )
                )
    return findings


def format_findings(findings: Iterable[Finding]) -> str:
    grouped = {PASS: [], WARN: [], FAIL: []}
    for finding in findings:
        grouped.setdefault(finding.severity, []).append(finding)

    lines: list[str] = []
    for severity in (PASS, WARN, FAIL):
        items = grouped.get(severity, [])
        lines.append(f"{severity} ({len(items)})")
        if items:
            for finding in items:
                suffix = f" [{finding.path}]" if finding.path else ""
                lines.append(f"  - {finding.message}{suffix}")
        else:
            lines.append("  - None")
    return "\n".join(lines)


def format_findings_json(findings: Iterable[Finding]) -> str:
    finding_list = list(findings)
    summary = {PASS: 0, WARN: 0, FAIL: 0, "total": len(finding_list)}
    for finding in finding_list:
        summary[finding.severity] = summary.get(finding.severity, 0) + 1

    payload = {
        "summary": summary,
        "findings": [
            {
                "severity": finding.severity,
                "message": finding.message,
                "path": finding.path,
            }
            for finding in finding_list
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def exit_code_for_findings(findings: Iterable[Finding], *, strict: bool) -> int:
    if not strict:
        return 0
    return 1 if any(finding.severity == FAIL for finding in findings) else 0


def parse_status(text: str) -> str | None:
    match = STATUS_RE.search(text)
    return match.group(1).strip() if match else None


def parse_source_spec(text: str) -> str | None:
    match = SOURCE_SPEC_RE.search(text)
    return match.group(1).strip() if match else None


def parse_roadmap_marker(text: str) -> str | None:
    match = ROADMAP_MARKER_RE.search(text)
    return match.group(1).strip() if match else None


def has_roadmap_ignore(text: str) -> bool:
    return bool(ROADMAP_IGNORE_RE.search(text))


def normalize_status(status: str) -> str:
    return status.strip().strip("[]").lower()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def iter_markdown_files(root: Path) -> Iterable[Path]:
    for current_root, dirnames, filenames in root.walk():
        dirnames[:] = [dirname for dirname in dirnames if dirname not in SKIPPED_DIRS]
        for filename in filenames:
            if filename.endswith(".md"):
                yield current_root / filename
