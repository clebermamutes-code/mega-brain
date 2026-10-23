"""Stage 6 -- locucao (TTS).

ElevenLabs via HTTP direto (sem SDK; a chave ja existe no .env do projeto como
``ELEVENLABS_API_KEY``). O texto e enviado em blocos por cena e concatenado,
porque a API tem teto de caracteres por request e porque manter fronteira de
cena no audio facilita o alinhamento na Stage 7.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from engine.intelligence.youtube_cloner.schemas import ScriptDraft, VoiceTrack

logger = logging.getLogger("youtube_cloner.voice")

ELEVEN_ROOT = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL = "eleven_multilingual_v2"
MAX_CHARS_PER_REQUEST = 4_500


class VoiceError(RuntimeError):
    """Falha de credencial, quota ou rede na geracao de locucao."""


def _api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise VoiceError(
            "ELEVENLABS_API_KEY ausente. Adicione ao .env, ou rode a Stage 6 "
            "manualmente no Google AI Studio usando o arquivo narration.txt."
        )
    return key


def chunk_text(text: str, limit: int = MAX_CHARS_PER_REQUEST) -> list[str]:
    """Fatia por paragrafo, nunca no meio de uma frase."""
    chunks: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 > limit and current:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def _synthesize(text: str, voice_id: str, model: str, stability: float, similarity: float) -> bytes:
    payload = json.dumps(
        {
            "text": text,
            "model_id": model,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity,
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{ELEVEN_ROOT}/text-to-speech/{voice_id}",
        data=payload,
        headers={
            "xi-api-key": _api_key(),
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:  # pragma: no cover - rede
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise VoiceError(f"ElevenLabs HTTP {exc.code}: {detail}") from exc
    except OSError as exc:  # pragma: no cover - rede
        raise VoiceError(f"ElevenLabs indisponivel: {exc}") from exc


def _concat(parts: list[Path], target: Path) -> Path:
    """Concatena os MP3 com ffmpeg; sem ffmpeg, faz append binario.

    Append binario de MP3 funciona para reproducao mas deixa o header de
    duracao errado — por isso ffmpeg e o caminho preferido.
    """
    if len(parts) == 1:
        parts[0].rename(target)
        return target
    if shutil_which("ffmpeg"):
        listing = target.with_suffix(".txt")
        listing.write_text(
            "\n".join(f"file '{p.resolve()}'" for p in parts), encoding="utf-8"
        )
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-c", "copy", str(target)],
            capture_output=True,
            check=False,
        )
        listing.unlink(missing_ok=True)
        if target.exists():
            for p in parts:
                p.unlink(missing_ok=True)
            return target
    logger.warning("ffmpeg ausente — concatenando MP3 por append binario.")
    with target.open("wb") as out:
        for p in parts:
            out.write(p.read_bytes())
            p.unlink(missing_ok=True)
    return target


def shutil_which(cmd: str) -> str | None:
    import shutil

    return shutil.which(cmd)


def probe_duration(path: Path) -> float | None:
    """Duracao real via ffprobe. ``None`` quando ffprobe nao esta instalado."""
    if not shutil_which("ffprobe"):
        return None
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return round(float(result.stdout.strip()), 2)
    except (ValueError, AttributeError):
        return None


def synthesize(
    draft: ScriptDraft,
    out_dir: Path,
    *,
    voice_id: str | None = None,
    model: str = DEFAULT_MODEL,
    stability: float = 0.45,
    similarity: float = 0.8,
) -> VoiceTrack:
    """Roteiro -> arquivo de narracao unico."""
    voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    if not voice_id:
        raise VoiceError(
            "voice_id nao informado (use --voice-id ou ELEVENLABS_VOICE_ID). "
            "Use a MESMA voz em todos os videos do canal."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    narration = draft.full_narration
    (out_dir / "narration.txt").write_text(narration, encoding="utf-8")

    parts: list[Path] = []
    for i, chunk in enumerate(chunk_text(narration), start=1):
        logger.info("TTS bloco %d (%d chars)", i, len(chunk))
        audio = _synthesize(chunk, voice_id, model, stability, similarity)
        part = out_dir / f"_voice_part_{i:03d}.mp3"
        part.write_bytes(audio)
        parts.append(part)

    final = _concat(parts, out_dir / "narration.mp3")
    return VoiceTrack(
        audio_path=str(final),
        provider="elevenlabs",
        voice_id=voice_id,
        duration_seconds=probe_duration(final),
        word_count=len(narration.split()),
    )
