"""Stage 2 -- coleta de transcricoes dos videos modelo.

Substitui a extensao manual "YouTube Summary" das fontes. Tres caminhos, em
ordem de preferencia, porque nenhum deles e estavel sozinho:

  1. ``youtube_transcript_api`` (pip) -- mais limpo quando ha legenda publica.
  2. ``yt-dlp`` (binario) -- pega auto-legenda e converte VTT em texto.
  3. Falha explicita -- nunca inventamos transcricao (Constituicao Art. IV).

As transcricoes sao material de ANALISE. Elas alimentam a destilacao de
estrutura e sao descartadas antes da geracao -- ver ``guardrails.py``.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger("youtube_cloner.transcripts")

_VTT_TIMESTAMP = re.compile(r"^\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->")
_VTT_TAG = re.compile(r"<[^>]+>")


class TranscriptUnavailable(RuntimeError):
    """Nenhum caminho conseguiu obter a transcricao deste video."""


def _via_api(video_id: str, languages: list[str]) -> str | None:
    """Suporta as duas APIs da lib.

    A v1.x trocou o classmethod ``get_transcript`` por ``YouTubeTranscriptApi().fetch``,
    que devolve objetos com atributo ``.text`` em vez de dicts. Tentamos a nova
    primeiro e caimos para a antiga, porque nao controlamos qual versao o
    operador tem instalada.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    except ImportError:
        return None

    try:
        if hasattr(YouTubeTranscriptApi, "fetch"):  # v1.x
            snippets = YouTubeTranscriptApi().fetch(video_id, languages=languages)
            return " ".join(s.text.strip() for s in snippets if getattr(s, "text", ""))
        chunks = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        return " ".join(c.get("text", "").strip() for c in chunks if c.get("text"))
    except Exception as exc:  # a lib levanta ~8 excecoes distintas
        logger.debug("youtube_transcript_api falhou para %s: %s", video_id, exc)
        return None


def _vtt_to_text(vtt: str) -> str:
    lines: list[str] = []
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line or line == "WEBVTT" or _VTT_TIMESTAMP.match(line):
            continue
        if line.startswith(("Kind:", "Language:", "NOTE")) or line.isdigit():
            continue
        clean = _VTT_TAG.sub("", line).strip()
        if clean and (not lines or lines[-1] != clean):
            lines.append(clean)
    return " ".join(lines)


def _via_ytdlp(video_id: str, languages: list[str]) -> str | None:
    if not shutil.which("yt-dlp"):
        return None
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-subs",
            "--write-subs",
            "--sub-langs",
            ",".join(languages) + ",en",
            "--sub-format",
            "vtt",
            "-o",
            str(Path(tmp) / "%(id)s.%(ext)s"),
            url,
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=180, check=False)
        except subprocess.TimeoutExpired:
            logger.warning("yt-dlp timeout em %s", video_id)
            return None
        for vtt in sorted(Path(tmp).glob("*.vtt")):
            text = _vtt_to_text(vtt.read_text(encoding="utf-8", errors="replace"))
            if text:
                return text
    return None


def fetch_transcript(video_id: str, languages: list[str] | None = None) -> str:
    """Devolve a transcricao como texto corrido. Levanta se nao houver."""
    languages = languages or ["pt", "pt-BR", "en"]
    for loader in (_via_api, _via_ytdlp):
        text = loader(video_id, languages)
        if text and len(text.split()) > 50:
            logger.info("Transcricao obtida para %s via %s", video_id, loader.__name__)
            return text
    raise TranscriptUnavailable(
        f"Sem transcricao para {video_id}. Instale `youtube-transcript-api` ou "
        "`yt-dlp`, ou remova este video da amostra."
    )


def fetch_many(
    video_ids: list[str], languages: list[str] | None = None
) -> dict[str, str]:
    """Best-effort: videos sem legenda sao pulados com WARN, nao derrubam o lote."""
    out: dict[str, str] = {}
    for vid in video_ids:
        try:
            out[vid] = fetch_transcript(vid, languages)
        except TranscriptUnavailable as exc:
            logger.warning("%s", exc)
    if not out:
        raise TranscriptUnavailable(
            "Nenhum video da amostra tinha transcricao acessivel."
        )
    return out


_VIDEO_ID = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/)([\w-]{11})")


def parse_video_ids(text: str) -> list[str]:
    """Extrai video_ids de uma lista de URLs (uma por linha).

    Tolera parametros de tracking colados na URL (``&pp=...``, ``?si=...``),
    ignora linhas vazias e comentarios com ``#``, e remove duplicatas
    preservando a ordem original.
    """
    ids: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = _VIDEO_ID.search(line)
        if match:
            candidate = match.group(1)
        elif re.fullmatch(r"[\w-]{11}", line):
            candidate = line  # id cru, sem URL
        else:
            logger.warning("Linha ignorada (sem video_id reconhecivel): %s", line[:60])
            continue
        if candidate not in ids:
            ids.append(candidate)
    return ids


def save(transcripts: dict[str, str], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(transcripts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path
