from __future__ import annotations

import os
import sys


def ensure_src_path() -> str:
    """Ensure the project `src/` directory is importable.

    The current repo still runs directly from the repository root instead of an
    installed package, so runtime entrypoints and tests need a shared bootstrap
    instead of each file mutating `sys.path` independently.
    """
    src_path = os.path.join(os.path.dirname(__file__), "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    return src_path
