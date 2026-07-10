"""
Mega Brain — Configuration Access

``get_config(key, default)`` is the single read path for credentials and
settings. Hierarchy (first hit wins):

1. Process environment (already loaded by the CLI via .env)
2. ``.env`` at repo root (for direct ``python3`` invocations that skip the CLI)
3. Caller-provided default

`.env` is the ONLY source of truth for credentials (see .claude/CLAUDE.md
"Configuration") — this module never persists or logs values.
"""

from __future__ import annotations

import os
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
_dotenv_cache: dict[str, str] | None = None


def _load_dotenv() -> dict[str, str]:
    global _dotenv_cache
    if _dotenv_cache is not None:
        return _dotenv_cache
    values: dict[str, str] = {}
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip("'\"")
    _dotenv_cache = values
    return values


def get_config(key: str, default: str | None = None) -> str | None:
    """Read a config value: environment first, then .env, then default."""
    value = os.environ.get(key)
    if value is not None and value.strip():
        return value
    value = _load_dotenv().get(key)
    if value:
        return value
    return default
