"""
Derivational Spine — STORY-213.W1.2

Derives generative edges (GERA/PRODUZ/MATERIALIZA/IMPLEMENTA) between
adjacent-layer DNA atoms of the SAME person that share SPECIFIC provenance.
Reconstructed for the free release (referenced by graph_builder.py but not
shipped in the published package).

Chain (forward-only, mirrors the L1→L5 DNA cascade):
    filosofia      --GERA-->        modelo_mental
    modelo_mental  --PRODUZ-->      heuristica
    heuristica     --MATERIALIZA--> framework
    framework      --IMPLEMENTA-->  metodologia

No-Invention rules honored here:
- An edge only exists when two atoms share at least one REAL, SPECIFIC
  source unit (``metadata.via`` carries the audit trail).
- Generic/gap provenance ("desconhecido", "gap", empty) NEVER links atoms.
- NULL honesto: no shared provenance → zero edges, silently.

Default OFF via ``MB_DERIVATIONAL_EDGES_ENABLED`` (see graph_builder).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

# Forward-only derivational chain: (source_type, target_type, verb)
DERIVATIONAL_CHAIN: list[tuple[str, str, str]] = [
    ("filosofia", "modelo_mental", "GERA"),
    ("modelo_mental", "heuristica", "PRODUZ"),
    ("heuristica", "framework", "MATERIALIZA"),
    ("framework", "metodologia", "IMPLEMENTA"),
]

# Provenance values that are too generic to prove a real derivation link
_GENERIC_PROVENANCE = {
    "", "desconhecido", "unknown", "gap", "n/a", "na", "none", "null",
    "geral", "diversos", "varios", "várias", "misc",
}

# DNA entry fields that may carry source units (schema drifted across versions)
_PROVENANCE_FIELDS = ("fontes", "fonte", "sources", "source", "origem", "provenance", "evidencias")

_DOMAIN_FIELDS = ("dominios", "categoria", "tags")


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if v]
    return []


def extract_domains(entry: dict) -> list[str]:
    """Union of the REAL domain-bearing fields (dominios + categoria + tags).

    Widens the PERTENCE_A source beyond ``dominios`` (issue #141). An atom
    with none of those fields yields ``[]`` — no PERTENCE_A edge (NULL honesto).
    """
    seen: set[str] = set()
    domains: list[str] = []
    for field in _DOMAIN_FIELDS:
        for item in _as_list(entry.get(field)):
            item = item.strip()
            if item and item.lower() not in seen:
                seen.add(item.lower())
                domains.append(item)
    return domains


def _is_specific(unit: str) -> bool:
    return unit.strip().lower() not in _GENERIC_PROVENANCE


def extract_provenance(entry: dict) -> set[str]:
    """Real, specific source units backing this atom (normalized, lowercase)."""
    units: set[str] = set()
    for field in _PROVENANCE_FIELDS:
        for item in _as_list(entry.get(field)):
            item = item.strip()
            if item and _is_specific(item):
                units.add(item.lower())
    return units


def derive_edges(
    atoms_prov: dict[str, dict[str, list[tuple[str, set[str]]]]],
) -> list[dict[str, Any]]:
    """Derive the spine from shared specific provenance, per person.

    Args:
        atoms_prov: {person: {atom_type: [(entity_id, provenance_set), ...]}}

    Returns:
        [{"source": id, "target": id, "rel_type": verb, "via": [shared units]}]
        Forward-only; deduped per (source, target, verb).
    """
    specs: list[dict[str, Any]] = []
    emitted: set[tuple[str, str, str]] = set()

    for by_type in atoms_prov.values():
        for source_type, target_type, verb in DERIVATIONAL_CHAIN:
            for source_id, source_prov in by_type.get(source_type, []):
                if not source_prov:
                    continue
                for target_id, target_prov in by_type.get(target_type, []):
                    shared = source_prov & target_prov
                    if not shared:
                        continue
                    key = (source_id, target_id, verb)
                    if key in emitted:
                        continue
                    emitted.add(key)
                    specs.append(
                        {
                            "source": source_id,
                            "target": target_id,
                            "rel_type": verb,
                            "via": sorted(shared),
                        }
                    )
    return specs


def count_by_verb(specs: list[dict[str, Any]]) -> dict[str, int]:
    """Verb histogram for build logs (e.g. {'GERA': 12, 'PRODUZ': 3})."""
    return dict(Counter(spec["rel_type"] for spec in specs))
