"""
Dynamic Security — filterable identity columns (STORY-213.W3.2, E2+E3)

Single declared source of truth for the identity axis of metadata filters:
``visibility`` (row-level exposure) and ``client_id`` (tenant scoping).
postgres_store composes these into its filterable-column enum so the SQL
WHERE pushdown and the in-memory post-filter accept the same keys.
"""

from __future__ import annotations

FILTERABLE_IDENTITY_COLUMNS: frozenset[str] = frozenset({"visibility", "client_id"})
