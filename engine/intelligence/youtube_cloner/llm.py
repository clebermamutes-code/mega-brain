"""Adaptador fino sobre o ``llm_router`` do MCE.

Existe para dois servicos que todo estagio precisa e que o router nao da:
extrair JSON de uma resposta que veio embrulhada em prosa/cercas, e falhar
com mensagem util quando o modelo devolve algo que nao e JSON.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import re
import sys
from pathlib import Path
from typing import Callable

logger = logging.getLogger("youtube_cloner.llm")

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

_RUN_PROMPT: Callable[..., str] | None = None


def _load_run_prompt() -> Callable[..., str]:
    """Resolve ``llm_router.run_prompt``, tolerando o __init__ pesado do MCE.

    ``engine.intelligence.pipeline.mce.__init__`` importa o orchestrate inteiro,
    que depende de ``transitions``. Nao queremos que a ausencia dessa dependencia
    (irrelevante para este pipeline) derrube o youtube_cloner, entao caimos para
    carregar o modulo direto do arquivo quando o import de pacote falha.
    """
    global _RUN_PROMPT
    if _RUN_PROMPT is not None:
        return _RUN_PROMPT

    try:
        from engine.intelligence.pipeline.mce.llm_router import run_prompt

        _RUN_PROMPT = run_prompt
        return _RUN_PROMPT
    except ImportError as exc:
        logger.debug("Import de pacote do llm_router falhou (%s); usando fallback", exc)

    module_path = (
        Path(__file__).resolve().parents[1] / "pipeline" / "mce" / "llm_router.py"
    )
    if not module_path.exists():
        raise ImportError(f"llm_router nao encontrado em {module_path}")

    spec = importlib.util.spec_from_file_location("_ytclone_llm_router", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Nao consegui carregar {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _RUN_PROMPT = module.run_prompt
    return _RUN_PROMPT


class LLMOutputError(RuntimeError):
    """O modelo respondeu, mas nao em JSON parseavel."""


def extract_json(raw: str) -> dict:
    """Tolera cercas de codigo e prosa em volta do objeto JSON."""
    text = (raw or "").strip()
    if not text:
        raise LLMOutputError("Resposta vazia do modelo.")

    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMOutputError(
                f"JSON invalido na resposta do modelo: {exc}. "
                f"Trecho: {text[start : start + 200]!r}"
            ) from exc
    raise LLMOutputError(f"Nenhum objeto JSON na resposta: {text[:200]!r}")


def call_json(
    prompt: str,
    *,
    step: str,
    provider: str | None = None,
    max_output_tokens: int = 8_000,
) -> dict:
    """Roda o prompt e devolve o JSON ja parseado."""
    logger.info("[%s] chamando LLM (%d chars de prompt)", step, len(prompt))
    raw = _load_run_prompt()(
        prompt,
        step=f"ytclone_{step}",
        provider=provider,
        max_output_tokens=max_output_tokens,
    )
    return extract_json(raw)
