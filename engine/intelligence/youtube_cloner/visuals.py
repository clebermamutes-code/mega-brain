"""Stage 5 -- prompts de imagem/video com ancora de consistencia.

O modulo produz PROMPTS, nao pixels. A geracao propriamente dita fica com a
ferramenta que o operador usa (Google Flow, Leonardo, Higgsfield): todas
consomem prompt em texto + uma imagem de referencia, e nenhuma delas tem uma
API estavel o bastante para valer acoplamento aqui.

A ancora de personagem e o ponto critico -- e a falha #1 reportada nas fontes
(personagem muda de cara entre cenas). Resolvemos repetindo o
``character_reference_prompt`` e o ``style_suffix`` em toda cena.
"""

from __future__ import annotations

import json
import logging

from engine.intelligence.youtube_cloner import prompts as P
from engine.intelligence.youtube_cloner.llm import call_json
from engine.intelligence.youtube_cloner.schemas import (
    ImagePromptSet,
    ScriptDraft,
    VideoDNA,
)

logger = logging.getLogger("youtube_cloner.visuals")


def generate_image_prompts(
    draft: ScriptDraft,
    dna: VideoDNA,
    *,
    aspect_ratio: str = "16:9",
    provider: str | None = None,
) -> ImagePromptSet:
    """Roteiro -> conjunto ordenado de prompts visuais consistentes."""
    scenes_payload = json.dumps(
        [{"index": s.index, "narration": s.narration} for s in draft.scenes],
        ensure_ascii=False,
        indent=2,
    )
    prompt = P.VISUAL_PROMPTS.format(
        visual_style=dna.visual_style or "cinematic, soft lighting, high detail",
        aspect_ratio=aspect_ratio,
        scenes=scenes_payload,
    )
    data = call_json(prompt, step="visuals", provider=provider, max_output_tokens=16_000)

    style_suffix = data.get("style_suffix", "").strip()
    char_ref = data.get("character_reference_prompt", "").strip()
    if not char_ref:
        raise ValueError(
            "Sem character_reference_prompt: a ancora de consistencia e "
            "obrigatoria, senao o personagem muda de cena para cena."
        )

    by_index = {int(p.get("index", 0)): p for p in data.get("prompts", [])}
    enriched: list[dict] = []
    for scene in draft.scenes:
        raw = by_index.get(scene.index, {})
        image_prompt = (raw.get("image_prompt") or "").strip()
        if not image_prompt:
            logger.warning("Cena %d sem image_prompt — usando fallback de estilo", scene.index)
            image_prompt = f"scene illustrating: {scene.narration[:180]}"
        # Sufixo de estilo repetido em toda cena = consistencia de mundo.
        if style_suffix and style_suffix.lower() not in image_prompt.lower():
            image_prompt = f"{image_prompt}, {style_suffix}"
        scene.image_prompt = image_prompt
        scene.video_prompt = (raw.get("video_prompt") or "").strip()
        enriched.append(
            {
                "index": scene.index,
                "image_prompt": image_prompt,
                "video_prompt": scene.video_prompt,
                "duration_seconds": scene.duration_seconds,
            }
        )

    logger.info("Prompts visuais gerados para %d cenas", len(enriched))
    return ImagePromptSet(
        character_reference_prompt=char_ref,
        style_suffix=style_suffix,
        aspect_ratio=aspect_ratio,
        prompts=enriched,
    )


def to_batch_file(prompt_set: ImagePromptSet) -> str:
    """Serializa os prompts para colar em lote (Google Flow / Leonardo).

    Uma linha por cena, prefixada pelo indice — e assim que as ferramentas de
    geracao em lote das fontes esperam receber.
    """
    lines = [f"# CHARACTER REFERENCE\n{prompt_set.character_reference_prompt}", ""]
    lines.append(f"# ASPECT RATIO: {prompt_set.aspect_ratio}")
    lines.append("# SCENE PROMPTS")
    for item in prompt_set.prompts:
        lines.append(f"{item['index']:03d}. {item['image_prompt']}")
    return "\n".join(lines)
