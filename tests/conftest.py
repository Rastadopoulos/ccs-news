"""Shared pytest setup for the CCS-Brief regression suite.

Interpreter situation on this machine (macOS):
  * /usr/bin/python3 (3.9.6) has pytest + openpyxl but NOT feedparser/PyYAML.
  * .venv/bin/python  (3.9.6) has feedparser/PyYAML but NOT pytest.

Both are CPython 3.9.6, so we bridge them: if a third-party import is missing,
fall back to the repo venv's site-packages. This keeps the suite runnable as
plain `python3 -m pytest tests/` with no network access (the sandbox cannot
reach PyPI).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Scripts import each other as top-level modules (e.g. `from _canon import …`).
sys.path.insert(0, str(SCRIPTS_DIR))

# Venv site-packages fallback for feedparser / yaml.
_VENV_SITE = REPO_ROOT / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
for mod in ("feedparser", "yaml"):
    try:
        __import__(mod)
    except ImportError:
        if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
            sys.path.append(str(_VENV_SITE))
        break

import pytest  # noqa: E402


@pytest.fixture()
def repo_root() -> Path:
    return REPO_ROOT
