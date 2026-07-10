"""
Typed Schema — the 12 Object Types (F0-13, schema-fonte)

Loads ``typed_schema.yaml`` (sibling file): the 10 DNA layers as graph object
types plus ``pessoa`` and ``dominio``. Consumed by ontology_layer when the
ONTOLOGY_HOTPATH_ENABLED kill-switch is ON; the legacy 5-type DNA chain is
the fallback when OFF or when this file is absent (No-Invention: the schema
file is the source, this module only reads it).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_SCHEMA_FILE = Path(__file__).resolve().parent / "typed_schema.yaml"


@lru_cache(maxsize=1)
def load_schema() -> dict:
    """Load and memoize typed_schema.yaml. Raises if absent/invalid —
    callers guard with try/except and fall back to the legacy chain."""
    import yaml

    data = yaml.safe_load(_SCHEMA_FILE.read_text())
    if not isinstance(data, dict) or "object_types" not in data:
        raise ValueError(f"typed_schema.yaml invalido: esperado mapa com 'object_types' em {_SCHEMA_FILE}")
    return data
