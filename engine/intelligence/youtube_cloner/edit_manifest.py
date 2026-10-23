"""Stage 7 -- manifesto de montagem + render.

Este e o estagio onde as fontes voltam a ser manuais: elas montam no CapCut na
mao. O CapCut nao expoe API publica, entao automatizar aquele passo especifico
so seria possivel dirigindo a UI (fragil e quebra a cada update).

A saida aqui e dupla, para o operador escolher:

  - ``edit-manifest.json`` -- timeline declarativa, legivel, para quem prefere
    montar no CapCut seguindo tempos ja calculados em vez de no olho.
  - ``render.sh``          -- script ffmpeg que monta o video sem editor nenhum.

A regra de ouro das fontes esta codificada em ``clip_native_gain_db=-60``: o
audio nativo dos clipes de IA vai a zero, so a locucao e ouvida.
"""

from __future__ import annotations

import logging
import math
import shlex
from pathlib import Path

from engine.intelligence.youtube_cloner.schemas import (
    EditManifest,
    ScriptDraft,
    VideoDNA,
    VoiceTrack,
)

logger = logging.getLogger("youtube_cloner.edit_manifest")


def build_manifest(
    draft: ScriptDraft,
    dna: VideoDNA,
    voice: VoiceTrack | None,
    *,
    project_name: str,
    resolution: str = "1920x1080",
    fps: int = 30,
) -> EditManifest:
    """Calcula o timeline cena a cena.

    Quando temos a duracao real do audio (via ffprobe), reescalamos as duracoes
    estimadas por contagem de palavras para bater com o audio de verdade —
    caso contrario o video dessincroniza progressivamente ate o fim.
    """
    estimated = [max(s.duration_seconds, 0.5) for s in draft.scenes]
    total_estimated = sum(estimated) or 1.0

    scale = 1.0
    if voice and voice.duration_seconds:
        scale = voice.duration_seconds / total_estimated
        logger.info(
            "Audio real %.2fs vs estimado %.2fs -> fator de escala %.3f",
            voice.duration_seconds,
            total_estimated,
            scale,
        )

    min_visual, max_visual = dna.seconds_per_visual
    timeline: list[dict] = []
    cursor = 0.0
    for scene, est in zip(draft.scenes, estimated):
        duration = round(est * scale, 3)
        # Cena longa demais vira varios cortes: mantem a densidade visual do
        # canal modelo (as fontes citam 1-3s por imagem). `ceil` e nao `round`
        # porque arredondar para baixo produziria slots ACIMA do teto.
        slots = max(1, math.ceil(duration / max(max_visual, 1)))
        slot_duration = round(duration / slots, 3)
        for slot in range(slots):
            timeline.append(
                {
                    "scene_index": scene.index,
                    "slot": slot + 1,
                    "start": round(cursor, 3),
                    "end": round(cursor + slot_duration, 3),
                    "duration": slot_duration,
                    "image_prompt": scene.image_prompt,
                    "video_prompt": scene.video_prompt,
                    "asset_path": scene.asset_path,
                    "narration": scene.narration if slot == 0 else "",
                }
            )
            cursor += slot_duration

    logger.info(
        "Timeline: %d cortes em %.1fs (%.1f cortes/min, alvo %d-%ds por visual)",
        len(timeline),
        cursor,
        len(timeline) / max(cursor / 60, 0.01),
        min_visual,
        max_visual,
    )
    return EditManifest(
        project_name=project_name,
        fps=fps,
        resolution=resolution,
        audio_path=voice.audio_path if voice else "",
        timeline=timeline,
    )


def render_script(manifest: EditManifest, assets_dir: Path, output: Path) -> str:
    """Gera um script ffmpeg que monta o video a partir dos assets numerados.

    Espera assets nomeados ``001.png``, ``002.png``, ... na ordem do timeline.
    Cada slot vira um segmento de imagem estatica com a duracao calculada; a
    locucao entra como faixa de audio unica e define a duracao final.
    """
    lines = [
        "#!/usr/bin/env bash",
        "# Gerado por engine.intelligence.youtube_cloner.edit_manifest",
        "# Requer ffmpeg no PATH. Assets esperados: 001.png, 002.png, ...",
        "set -euo pipefail",
        "",
        f"ASSETS={shlex.quote(str(assets_dir))}",
        f"AUDIO={shlex.quote(manifest.audio_path)}",
        f"OUT={shlex.quote(str(output))}",
        "WORK=$(mktemp -d)",
        'trap "rm -rf $WORK" EXIT',
        "",
        "# 1. Cada slot vira um clipe de duracao exata.",
    ]
    for i, slot in enumerate(manifest.timeline, start=1):
        lines.append(
            f'ffmpeg -y -loop 1 -i "$ASSETS/{i:03d}.png" -t {slot["duration"]} '
            f'-vf "scale={manifest.resolution.replace("x", ":")}:force_original_aspect_ratio=increase,'
            f'crop={manifest.resolution.replace("x", ":")},setsar=1" '
            f"-r {manifest.fps} -c:v libx264 -pix_fmt yuv420p "
            f'"$WORK/{i:03d}.mp4" -loglevel error'
        )
    lines += [
        "",
        "# 2. Concatena os clipes.",
        'for f in "$WORK"/*.mp4; do echo "file \'$f\'" >> "$WORK/list.txt"; done',
        'ffmpeg -y -f concat -safe 0 -i "$WORK/list.txt" -c copy "$WORK/video.mp4" -loglevel error',
        "",
        "# 3. Casa com a locucao. -shortest garante que o video termina com a voz.",
        'ffmpeg -y -i "$WORK/video.mp4" -i "$AUDIO" -c:v copy -c:a aac '
        '-shortest "$OUT" -loglevel error',
        "",
        'echo "Render concluido: $OUT"',
    ]
    return "\n".join(lines) + "\n"


def write_render_script(
    manifest: EditManifest, assets_dir: Path, output_video: Path, script_path: Path
) -> Path:
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(render_script(manifest, assets_dir, output_video), encoding="utf-8")
    script_path.chmod(0o755)
    return script_path
