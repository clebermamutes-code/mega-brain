"""
Mega Brain — Supabase PostgREST client (optional mirror)

Supabase is a reactive PARTIAL mirror of the filesystem, never source of
truth (docs/architecture/supabase-role.md). This module is the legacy
PostgREST path used by ``pgvector_store`` when ``DATABASE_URL`` is absent.

Module-level API (consumed as a module object by PgVectorStore):
    is_enabled() -> bool
    upsert(table, record_or_records, on_conflict=...) -> None
    select(table, query_string) -> list[dict]
    rpc(function_name, params) -> list | dict
    delete(table, filter_string) -> None

Disabled (no SUPABASE_URL / key configured) → ``is_enabled()`` is False and
callers transparently fall back to local BM25 (no regression, RNF-2).
Implemented over urllib (stdlib only — hooks-compatible).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from engine.config import get_config


def _base_url() -> str:
    return (get_config("SUPABASE_URL") or "").rstrip("/")


def _key() -> str:
    return get_config("SUPABASE_SERVICE_ROLE_KEY") or get_config("SUPABASE_ANON_KEY") or ""


def is_enabled() -> bool:
    """Mirror active only when both URL and key are configured."""
    return bool(_base_url() and _key())


def _request(
    method: str,
    path: str,
    payload: Any = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> Any:
    if not is_enabled():
        raise RuntimeError("Supabase mirror desabilitado: configure SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY")
    url = f"{_base_url()}/rest/v1/{path}"
    key = _key()
    req_headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        **(headers or {}),
    }
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            return json.loads(body) if body.strip() else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:500]
        raise RuntimeError(f"Supabase {method} {path} → HTTP {exc.code}: {detail}") from exc


def upsert(table: str, records: dict | list[dict], on_conflict: str | None = None) -> None:
    if isinstance(records, dict):
        records = [records]
    path = table + (f"?on_conflict={on_conflict}" if on_conflict else "")
    _request(
        "POST",
        path,
        payload=records,
        headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
    )


def select(table: str, query: str) -> list[dict]:
    rows = _request("GET", f"{table}?{query.lstrip('?')}")
    return rows if isinstance(rows, list) else []


def rpc(function_name: str, params: dict | None = None) -> Any:
    if not is_enabled():
        raise RuntimeError("Supabase mirror desabilitado: configure SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY")
    url = f"{_base_url()}/rest/v1/rpc/{function_name}"
    key = _key()
    req = urllib.request.Request(
        url,
        data=json.dumps(params or {}).encode(),
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode()
            return json.loads(body) if body.strip() else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:500]
        raise RuntimeError(f"Supabase rpc/{function_name} → HTTP {exc.code}: {detail}") from exc


def delete(table: str, filter_query: str) -> None:
    _request(
        "DELETE",
        f"{table}?{filter_query.lstrip('?')}",
        headers={"Prefer": "return=minimal"},
    )
