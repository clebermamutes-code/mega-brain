"""
Mega Brain — Operations Dispatcher (Story W1-001.5, AC2)

Single entry point for CLI/MCP/API access to engine capabilities.
`bin/mega-brain.js` dispatches every knowledge/pipeline command here via:

    from engine.operations import dispatch
    result = dispatch("search_knowledge", query="...", buckets=["external"])

Contract:
- ``dispatch(name, **kwargs)`` ALWAYS returns a JSON-serializable value.
- Errors never raise across the boundary — they come back as
  ``{"ok": false, "error": ..., "hint": ...}`` so the CLI prints something
  actionable instead of a Python traceback.
- Handlers lazy-import their engine module: a missing optional dependency
  breaks only the operations that need it, never the whole registry.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _err(error: str, hint: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "error": error}
    if hint:
        out["hint"] = hint
    return out


def _run_module_cli(argv: list[str], timeout: int = 1800) -> dict[str, Any]:
    """Run an engine module through its own tested CLI and capture output."""
    proc = subprocess.run(
        [sys.executable, *argv],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "output": proc.stdout.strip()[-8000:],
        "stderr": proc.stderr.strip()[-2000:] if proc.returncode != 0 else "",
    }


# ---------------------------------------------------------------------------
# Knowledge operations
# ---------------------------------------------------------------------------


def op_search_knowledge(
    query: str,
    buckets: list[str] | None = None,
    top_k: int = 5,
    **_: Any,
) -> dict[str, Any]:
    from engine.intelligence.rag.bucket_query_router import query as bucket_query

    bucket = (buckets[0] if buckets else "auto") or "auto"
    return bucket_query(query, bucket=bucket, top_k=int(top_k))


def op_available_buckets(**_: Any) -> dict[str, Any]:
    from engine.intelligence.rag.bucket_query_router import available_buckets

    return available_buckets()


def op_build_index(bucket_name: str | None = None, **_: Any) -> dict[str, Any]:
    from engine.intelligence.rag.rebuild import rebuild
    from engine.providers.supabase_client import is_enabled as supabase_enabled

    # Vector embeddings need OPENAI_API_KEY; degrade to BM25-only without it.
    # The pgvector dual-write only runs when the Supabase mirror is configured.
    has_openai = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    result = rebuild(
        bucket=bucket_name or "all",
        skip_vectors=not has_openai,
        dual_write_pgvector=supabase_enabled(),
    )
    result["vectors_built"] = has_openai
    if not has_openai:
        result["hint"] = "OPENAI_API_KEY ausente — indice BM25 apenas (busca semantica desativada)."
    return result


def op_compile_dossier(persona: str, **_: Any) -> dict[str, Any]:
    return _run_module_cli(
        ["-m", "engine.intelligence.pipeline.dossier_compiler", "--person", persona]
    )


def op_run_conclave(topic: str, agents: list[str] | None = None, **_: Any) -> dict[str, Any]:
    """Prepare a Conclave session: gather cited evidence per counselor.

    The debate itself runs inside Claude Code (/conclave). This operation
    retrieves the evidence packet each counselor argues from, keeping the
    'No Invention' constitutional rule — positions must cite the base.
    """
    from engine.intelligence.rag.bucket_query_router import query as bucket_query

    counselors = agents or ["critico-metodologico", "advogado-do-diabo", "sintetizador"]
    evidence = bucket_query(topic, bucket="all", top_k=8)
    results = evidence.get("results", []) if isinstance(evidence, dict) else []
    return {
        "ok": True,
        "topic": topic,
        "counselors": counselors,
        "evidence": results,
        "evidence_count": len(results),
        "protocol": (
            "Cada conselheiro argumenta APENAS a partir das evidencias acima, "
            "citando a fonte. O sintetizador consolida em uma recomendacao com "
            "nivel de confianca proporcional a base."
        ),
        "confidence_note": (
            "Base vazia — ingira material antes de deliberar (/ingest)."
            if not results
            else f"Base com {len(results)} evidencias relevantes ao topico."
        ),
    }


def op_ingest(source_path: str, bucket: str | None = None, **_: Any) -> dict[str, Any]:
    script = PROJECT_ROOT / "scripts" / "ingest-with-entity-discovery.py"
    if not script.exists():
        return _err("scripts/ingest-with-entity-discovery.py nao encontrado")
    argv = [str(script), source_path]
    if bucket:
        argv += ["--bucket", bucket]
    return _run_module_cli(argv)


# ---------------------------------------------------------------------------
# Health / preflight operations
# ---------------------------------------------------------------------------


def op_run_preflight(**_: Any) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})

    check(
        "python",
        sys.version_info >= (3, 10),
        f"{sys.version_info.major}.{sys.version_info.minor}",
    )
    for mod in ("yaml", "transitions"):
        try:
            __import__(mod)
            check(f"dep:{mod}", True)
        except ImportError:
            check(f"dep:{mod}", False, "pip install -r requirements.txt")

    env_file = PROJECT_ROOT / ".env"
    check("env-file", env_file.exists(), str(env_file))
    for key, purpose in (
        ("ANTHROPIC_API_KEY", "LLM nucleo"),
        ("OPENAI_API_KEY", "transcricao + embeddings"),
        ("GEMINI_API_KEY", "video (Speaker Visual Gate)"),
    ):
        val = os.environ.get(key, "").strip()
        configured = bool(val) and "xxxx" not in val
        check(f"key:{key}", configured, purpose if configured else f"faltando — {purpose}")

    for rel in ("knowledge/external", "engine/intelligence", ".claude/hooks"):
        check(f"dir:{rel}", (PROJECT_ROOT / rel).is_dir())

    index_dir = PROJECT_ROOT / ".data" / "rag_index"
    check(
        "rag-index",
        index_dir.exists(),
        "" if index_dir.exists() else "rode: mega-brain index",
    )

    failed = [c for c in checks if not c["ok"]]
    return {
        "ok": not failed,
        "status": "READY" if not failed else "DEGRADED",
        "checks": checks,
        "failed": len(failed),
        "hint": "" if not failed else "Falhas sao WARN, nunca bloqueiam (session-preflight rule).",
    }


def op_check_agent_health(agent_id: str | None = None, **_: Any) -> dict[str, Any]:
    if agent_id:
        # Kernel Session Layer: agent = agent.md + soul.md + dna-config.yaml + memory.md
        base = PROJECT_ROOT / "agents"
        matches = list(base.glob(f"*/{agent_id}")) + list(base.glob(f"*/*/{agent_id}"))
        if not matches:
            return _err(
                f"Agente '{agent_id}' nao encontrado em agents/",
                "Rode 'mega-brain health' sem argumento para o score do sistema.",
            )
        agent_dir = matches[0]
        ksl_files = ["agent.md", "soul.md", "dna-config.yaml", "memory.md"]
        present = {f: (agent_dir / f).exists() for f in ksl_files}
        score = sum(present.values()) / len(ksl_files) * 100
        return {
            "ok": True,
            "agent": agent_id,
            "path": str(agent_dir.relative_to(PROJECT_ROOT)),
            "ksl_files": present,
            "score": round(score),
            "grade": "A" if score == 100 else ("B" if score >= 75 else "C"),
        }

    from engine.intelligence.health.health_scorer import HealthScorer

    return HealthScorer(PROJECT_ROOT).compute().to_dict()


def op_check_workspace_health(**_: Any) -> dict[str, Any]:
    import time

    import yaml

    ws = PROJECT_ROOT / "workspace"
    report: dict[str, Any] = {"ok": True, "workspace": str(ws), "configs": {}, "businesses": []}
    for cfg in ("workspace.yaml", "structure.yaml", "relationships.yaml"):
        path = ws / cfg
        try:
            yaml.safe_load(path.read_text()) if path.exists() else None
            report["configs"][cfg] = "OK" if path.exists() else "MISSING"
        except yaml.YAMLError as exc:
            report["configs"][cfg] = f"INVALID: {exc}"
            report["ok"] = False

    ttl_days = {"L0-identity": 365, "L1-strategy": 90, "L2-tactical": 60, "L3-product": 30, "L4-operational": 7}
    now = time.time()
    businesses = ws / "businesses"
    if businesses.is_dir():
        for bu in sorted(p for p in businesses.iterdir() if p.is_dir()):
            layers = {}
            for layer, ttl in ttl_days.items():
                ldir = bu / layer
                if not ldir.is_dir():
                    layers[layer] = "ABSENT"
                    continue
                stale = [
                    f.name
                    for f in ldir.rglob("*")
                    if f.is_file() and (now - f.stat().st_mtime) > ttl * 86400
                ]
                layers[layer] = f"{len(stale)} stale" if stale else "FRESH"
            report["businesses"].append({"bu": bu.name, "layers": layers})
    return report


# ---------------------------------------------------------------------------
# Governance / pipeline operations
# ---------------------------------------------------------------------------


def op_validate_governance(**_: Any) -> dict[str, Any]:
    # validate_layers usa import de irmao em estilo script (`from audit_layers import ...`)
    validation_dir = str(PROJECT_ROOT / "engine" / "intelligence" / "validation")
    if validation_dir not in sys.path:
        sys.path.insert(0, validation_dir)
    from engine.intelligence.validation.validate_layers import validate_repository

    return validate_repository(PROJECT_ROOT)


def op_run_autonomous_pipeline(timeout_seconds: int | None = None, **_: Any) -> dict[str, Any]:
    from engine.intelligence.pipeline.autonomous_processor import AutonomousProcessor, FileQueue

    queue = FileQueue()
    if queue.size() == 0:
        return {
            "ok": True,
            "processed": 0,
            "note": "Fila vazia — nada a processar. Adicione material com /ingest.",
        }
    processor = AutonomousProcessor()
    return processor.run(timeout_seconds=timeout_seconds)


def op_validate_json_integrity(**_: Any) -> dict[str, Any]:
    return _run_module_cli(["-m", "engine.intelligence.validation.validate_json_integrity"])


# ---------------------------------------------------------------------------
# Utility operations
# ---------------------------------------------------------------------------


def op_hash_content(content: str, **_: Any) -> dict[str, Any]:
    from engine.intelligence.pipeline.hashing import canonical_hash

    return {"ok": True, "hash": canonical_hash(content)}


def op_build_aggregation(domain: str | None = None, persona: str | None = None, **_: Any) -> dict[str, Any]:
    from engine.intelligence.pipeline.agg_builder import build_agg_for_domain, build_all_domains

    if domain:
        path = build_agg_for_domain(domain)
        return {"ok": True, "domain": domain, "output": str(path)}
    result = build_all_domains()
    return {"ok": True, "domains": result, "note": persona and f"persona '{persona}' ignorada — agregacao e por dominio" or ""}


# ---------------------------------------------------------------------------
# Registry + dispatch
# ---------------------------------------------------------------------------

OPERATIONS_REGISTRY: dict[str, dict[str, Any]] = {
    # knowledge
    "search_knowledge": {
        "category": "knowledge",
        "description": "Busca hibrida (BM25 + vetorial) nos buckets de conhecimento",
        "handler": op_search_knowledge,
    },
    "available_buckets": {
        "category": "knowledge",
        "description": "Status dos 3 buckets (external/business/personal) e seus indices",
        "handler": op_available_buckets,
    },
    "build_index": {
        "category": "knowledge",
        "description": "Rebuild do indice RAG (BM25 sempre; vetores se OPENAI_API_KEY)",
        "handler": op_build_index,
    },
    "compile_dossier": {
        "category": "knowledge",
        "description": "Compila dossier de persona a partir de INSIGHTS-STATE.json",
        "handler": op_compile_dossier,
    },
    "run_conclave": {
        "category": "knowledge",
        "description": "Prepara sessao do Conclave: evidencias citadas por conselheiro",
        "handler": op_run_conclave,
    },
    # pipeline
    "ingest": {
        "category": "pipeline",
        "description": "Ingere material (arquivo/URL) com entity discovery",
        "handler": op_ingest,
    },
    "run_autonomous_pipeline": {
        "category": "pipeline",
        "description": "Processa a fila do pipeline MCE autonomamente",
        "handler": op_run_autonomous_pipeline,
    },
    "build_aggregation": {
        "category": "pipeline",
        "description": "Constroi agregacao cross-expert por dominio",
        "handler": op_build_aggregation,
    },
    # health
    "run_preflight": {
        "category": "health",
        "description": "Checagem pre-pipeline: deps, chaves, diretorios, indice",
        "handler": op_run_preflight,
    },
    "check_agent_health": {
        "category": "health",
        "description": "Health score do sistema (ou de um agente via KSL)",
        "handler": op_check_agent_health,
    },
    "check_workspace_health": {
        "category": "health",
        "description": "Valida configs do workspace e TTLs das camadas L0-L4",
        "handler": op_check_workspace_health,
    },
    # governance
    "validate_governance": {
        "category": "governance",
        "description": "Valida conformidade de layers dos arquivos git-tracked",
        "handler": op_validate_governance,
    },
    "validate_json_integrity": {
        "category": "governance",
        "description": "Valida integridade de todos os JSONs do repo",
        "handler": op_validate_json_integrity,
    },
    # utils
    "hash_content": {
        "category": "utils",
        "description": "Hash canonico de conteudo (dedup do Ingestion Guard)",
        "handler": op_hash_content,
    },
}


def op_list_operations(category: str | None = None, **_: Any) -> dict[str, Any]:
    return {
        name: {"category": info["category"], "description": info["description"]}
        for name, info in OPERATIONS_REGISTRY.items()
        if category is None or info["category"] == category
    }


OPERATIONS_REGISTRY["list_operations"] = {
    "category": "utils",
    "description": "Lista todas as operacoes registradas",
    "handler": op_list_operations,
}


def dispatch(operation: str, **kwargs: Any) -> Any:
    """Dispatch an operation by name. Never raises across the boundary.

    Handlers may print progress (rebuild, graph builder, etc.); the CLI parses
    our entire stdout as JSON, so handler prints are captured and returned in
    a ``log`` field instead of leaking into the stream.
    """
    import contextlib
    import io

    info = OPERATIONS_REGISTRY.get(operation)
    if info is None:
        return _err(
            f"Operacao desconhecida: '{operation}'",
            f"Validas: {', '.join(sorted(OPERATIONS_REGISTRY))}",
        )
    handler: Callable[..., Any] = info["handler"]
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            result = handler(**{k: v for k, v in kwargs.items() if v is not None})
        log = captured.getvalue().strip()
        if log and isinstance(result, dict) and "log" not in result:
            result["log"] = log[-4000:]
        return result
    except ImportError as exc:
        return _err(
            f"Dependencia ausente para '{operation}': {exc}",
            "pip install -r requirements.txt (deps pesadas de voz/diarizacao sao opcionais)",
        )
    except subprocess.TimeoutExpired:
        return _err(f"Timeout executando '{operation}'")
    except Exception as exc:  # boundary: CLI must receive JSON, not a traceback
        return _err(f"{type(exc).__name__}: {exc}")
