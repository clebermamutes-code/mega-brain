"""
Chunk Tagging — source_type / quality_tier / entity_type (S1/S4, STORY-F1-1)

Founder rule: "etiquetar + filtrar, NAO excluir" — tags restrict queries,
they never exclude data from the index. Reconstructed for the free release
(imported by rebuild.py but not shipped in the published package).

Contracts (consumed by ``rebuild._dual_write_pgvector``):
    derive_tags(chunk) -> (source_type | None, quality_tier | None)
    derive_entity_type(chunk, reflect=False, extractor=None)
        -> (entity_type | None, telemetry: {"llm_calls": int})
    source_content_sha(source_file) -> str | None

No-Invention: every tag must be provable from the chunk's real signals
(bucket + source path + layer). Unprovable → honest ``None`` (the
extraction-gap), never a guessed default.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

# DNA layer key → deterministic entity type (mirrors graph_builder._layer_to_type
# for L1-L5 and the MCE types for L6-L10)
DNA_LAYER_TO_ENTITY_TYPE: dict[str, str] = {
    "filosofias": "filosofia",
    "filosofia": "filosofia",
    "modelos_mentais": "modelo_mental",
    "modelo_mental": "modelo_mental",
    "heuristicas": "heuristica",
    "heuristica": "heuristica",
    "frameworks": "framework",
    "framework": "framework",
    "metodologias": "metodologia",
    "metodologia": "metodologia",
    "comportamentos": "behavioral_pattern",
    "behavioral_patterns": "behavioral_pattern",
    "valores": "value",
    "values_hierarchy": "value",
    "voice_dna": "voice_trait",
    "obsessoes": "obsession",
    "obsessions": "obsession",
    "paradoxos": "paradox",
    "paradoxes": "paradox",
}

# Path-segment → (source_type, quality_tier). Ordered: first match wins.
# curated  = human/pipeline-refined outputs (DNA, dossiers, playbooks)
# structured = organized derivatives (insights, SOPs, decisions)
# raw      = as-ingested material (sources, transcripts, calls, meetings)
_PATH_TAG_RULES: list[tuple[str, str, str]] = [
    ("/dna/", "dna", "curated"),
    ("/dossiers/", "dossier", "curated"),
    ("/playbooks/", "playbook", "curated"),
    ("/insights/", "insight", "structured"),
    ("/sops/", "sop", "structured"),
    ("/decisions/", "decision", "structured"),
    ("/meetings/", "meeting", "raw"),
    ("/calls/", "call", "raw"),
    ("/email/", "email", "raw"),
    ("/messages/", "message", "raw"),
    ("/sources/", "source", "raw"),
    ("/cognitive/", "note", "raw"),
]


def derive_tags(chunk: dict[str, Any]) -> tuple[str | None, str | None]:
    """Derive (source_type, quality_tier) from the chunk's real path signals.

    The caller injects the authoritative ``bucket`` before calling (the chunk
    dict's own bucket field is a construction-time default). A chunk whose
    source path matches no known segment stays (None, None) — honest gap.
    """
    source_file = str(chunk.get("source_file", "") or "").replace("\\", "/")
    if not source_file:
        return None, None
    # DNA signal can also come from the layer field even when the path is odd
    layer = str(chunk.get("layer", "") or "").lower()
    if layer in DNA_LAYER_TO_ENTITY_TYPE:
        return "dna", "curated"
    haystack = f"/{source_file.lower().lstrip('/')}"
    for segment, source_type, tier in _PATH_TAG_RULES:
        if segment in haystack:
            return source_type, tier
    return None, None


def derive_entity_type(
    chunk: dict[str, Any],
    reflect: bool = False,
    extractor: Callable[[dict], str | None] | None = None,
) -> tuple[str | None, dict[str, int]]:
    """Derive entity_type: DNA → deterministic (zero LLM); non-DNA → reflection.

    Non-DNA chunks are typed ONLY when ``reflect=True`` and an ``extractor``
    is provided (≤1 LLM call per chunk, counted in telemetry). Default is the
    deterministic / zero-LLM path — non-DNA stays honest ``None``.
    """
    telemetry = {"llm_calls": 0}
    layer = str(chunk.get("layer", "") or "").lower()
    deterministic = DNA_LAYER_TO_ENTITY_TYPE.get(layer)
    if deterministic is not None:
        return deterministic, telemetry
    if reflect and extractor is not None:
        telemetry["llm_calls"] = 1
        try:
            return extractor(chunk), telemetry
        except Exception:
            return None, telemetry
    return None, telemetry


def source_content_sha(source_file: str) -> str | None:
    """sha256 of the SOURCE file bytes (R3 provenance). None when unreadable."""
    if not source_file:
        return None
    path = Path(source_file)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / source_file
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None
