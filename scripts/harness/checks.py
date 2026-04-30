from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import tomllib
from typing import Iterable

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
HARNESS_VERIFY_COMMAND = "python scripts/harness/verify.py --ci"
PYTEST_COMMAND = "pytest"
RAILWAY_START_COMMAND = "python main.py"


@dataclass(frozen=True)
class Finding:
    severity: str
    message: str
    path: str | None = None


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
        if start_command == RAILWAY_START_COMMAND:
            findings.append(Finding(PASS, f"Railway start command is expected app entrypoint: {relative}", relative))
        else:
            findings.append(Finding(FAIL, f"Railway start command must be `{RAILWAY_START_COMMAND}`: {relative}", relative))

    return findings


def check_railway_build_command(build_command: str, relative: str) -> list[Finding]:
    findings: list[Finding] = []
    harness_index = build_command.find(HARNESS_VERIFY_COMMAND)
    pytest_index = build_command.find(PYTEST_COMMAND)

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
