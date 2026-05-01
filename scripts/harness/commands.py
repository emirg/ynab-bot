from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HarnessCommand:
    key: str
    label: str
    command: str


LOCAL_RUN = HarnessCommand("local_run", "local run command", ".venv/bin/python main.py")
LOCAL_TEST = HarnessCommand("local_test", "local test command", ".venv/bin/pytest")
LOCAL_CHECK_DOCS = HarnessCommand(
    "local_check_docs",
    "local advisory docs command",
    ".venv/bin/python scripts/harness/check_docs.py",
)
LOCAL_CHECK_FINANCIAL_INVARIANTS = HarnessCommand(
    "local_check_financial_invariants",
    "local advisory financial invariant command",
    ".venv/bin/python scripts/harness/check_financial_invariants.py",
)
LOCAL_CHECK_BEHAVIORAL_INVARIANTS = HarnessCommand(
    "local_check_behavioral_invariants",
    "local advisory behavioral invariant command",
    ".venv/bin/python scripts/harness/check_behavioral_invariants.py",
)
LOCAL_VERIFY_CI = HarnessCommand(
    "local_verify_ci",
    "local CI harness command",
    ".venv/bin/python scripts/harness/verify.py --ci",
)
RAILWAY_VERIFY_CI = HarnessCommand(
    "railway_verify_ci",
    "Railway CI harness command",
    "python scripts/harness/verify.py --ci",
)
RAILWAY_PYTEST = HarnessCommand("railway_pytest", "Railway pytest command", "pytest")
RAILWAY_START = HarnessCommand("railway_start", "Railway start command", "python main.py")

COMMAND_REGISTRY = (
    LOCAL_RUN,
    LOCAL_TEST,
    LOCAL_CHECK_DOCS,
    LOCAL_CHECK_FINANCIAL_INVARIANTS,
    LOCAL_CHECK_BEHAVIORAL_INVARIANTS,
    LOCAL_VERIFY_CI,
    RAILWAY_VERIFY_CI,
    RAILWAY_PYTEST,
    RAILWAY_START,
)

RAILWAY_BUILD_COMMAND = (
    "pip install -r requirements.txt && "
    f"{RAILWAY_VERIFY_CI.command} && "
    f"{RAILWAY_PYTEST.command}"
)
