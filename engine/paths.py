"""
Mega Brain — Canonical Path Constants

Single source of truth for every filesystem location the engine touches.
Reconstructed for the free release: the published package referenced this
module from 80+ files but did not ship it.

Layout contract (mirrors .claude/CLAUDE.md "Architecture"):
- knowledge/  → 3 isolated buckets (Constitution Art. XIII)
- workspace/  → business data L0-L4
- .data/      → RAG indexes + runtime state (gitignored)
- .claude/mission-control/ → pipeline MCE state
- logs/, artifacts/, processing/, inbox/ → runtime dirs (gitignored)

ROUTING is an optional override table: keys map logical destinations to
custom paths (workspace/config/routing.yaml). Callers always use
``ROUTING.get(key, <default>)`` so an empty table means "use defaults".
"""

from __future__ import annotations

from pathlib import Path

# Repo root: engine/paths.py → engine/ → root
ROOT = Path(__file__).resolve().parent.parent

# Legacy alias: the engine tree was once named core/ (compare-architecture 2026-04-16)
CORE = ROOT / "engine"

# ── Claude Code integration ────────────────────────────────────────────
CLAUDE = ROOT / ".claude"
COMMANDS = CLAUDE / "commands"
MISSION_CONTROL = CLAUDE / "mission-control"

# ── Runtime state (gitignored) ─────────────────────────────────────────
DATA = ROOT / ".data"
RAG_INDEX = DATA / "rag_index"          # bucket external
RAG_BUSINESS = DATA / "rag_business"    # bucket business
KNOWLEDGE_GRAPH = DATA / "knowledge_graph"
LOGS = ROOT / "logs"
ARTIFACTS = ROOT / "artifacts"
PROCESSING = ROOT / "processing"
INBOX = ROOT / "inbox"

# ── Knowledge buckets (Art. XIII: isolated, no cross-contamination) ───
KNOWLEDGE = ROOT / "knowledge"
KNOWLEDGE_EXTERNAL = KNOWLEDGE / "external"
KNOWLEDGE_BUSINESS = KNOWLEDGE / "business"
KNOWLEDGE_PERSONAL = KNOWLEDGE / "personal"

# external bucket internals
EXTERNAL_SOURCES = KNOWLEDGE_EXTERNAL / "sources"
EXTERNAL_DNA = KNOWLEDGE_EXTERNAL / "dna"
EXTERNAL_DNA_PERSONS = EXTERNAL_DNA / "persons"
EXTERNAL_DNA_DOMAINS = EXTERNAL_DNA / "domains"
EXTERNAL_DOSSIERS = KNOWLEDGE_EXTERNAL / "dossiers"
EXTERNAL_DOSSIERS_PERSONS_BY_THEME = EXTERNAL_DOSSIERS / "persons"

# business bucket internals
BUSINESS_DOSSIERS = KNOWLEDGE_BUSINESS / "dossiers"
BUSINESS_INSIGHTS = KNOWLEDGE_BUSINESS / "insights"
BUSINESS_SOPS = KNOWLEDGE_BUSINESS / "sops"
BUSINESS_DECISIONS = KNOWLEDGE_BUSINESS / "decisions"

# personal bucket internals
PERSONAL_CALLS = KNOWLEDGE_PERSONAL / "calls"
PERSONAL_COGNITIVE = KNOWLEDGE_PERSONAL / "cognitive"
PERSONAL_EMAIL = KNOWLEDGE_PERSONAL / "email"
PERSONAL_MESSAGES = KNOWLEDGE_PERSONAL / "messages"

# ── Agents (Kernel Session Layer) ──────────────────────────────────────
AGENTS = ROOT / "agents"
AGENTS_EXTERNAL = AGENTS / "external"
AGENTS_BUSINESS = AGENTS / "business"
AGENTS_CARGO = AGENTS / "cargo"

# ── Workspace (L0-L4 per business unit) ────────────────────────────────
WORKSPACE = ROOT / "workspace"
WORKSPACE_BUSINESSES = WORKSPACE / "businesses"
WORKSPACE_TEMPLATES = WORKSPACE / "_templates"
WORKSPACE_AUTOMATIONS = WORKSPACE / "automations"
WORKSPACE_FINANCE = WORKSPACE / "finance"
WORKSPACE_INBOX = WORKSPACE / "inbox"
WORKSPACE_MEETINGS = WORKSPACE / "meetings"
WORKSPACE_ORG = WORKSPACE / "org"
WORKSPACE_STRATEGY = WORKSPACE / "strategy"
WORKSPACE_TEAM = WORKSPACE / "team"
WORKSPACE_TOOLS = WORKSPACE / "tools"


def _load_routing() -> dict:
    """Optional path-override table from workspace/config/routing.yaml."""
    routing_file = WORKSPACE / "config" / "routing.yaml"
    if not routing_file.exists():
        return {}
    try:
        import yaml

        raw = yaml.safe_load(routing_file.read_text()) or {}
        if not isinstance(raw, dict):
            return {}
        return {k: Path(v) if isinstance(v, str) else v for k, v in raw.items()}
    except Exception:
        return {}


ROUTING: dict = _load_routing()
