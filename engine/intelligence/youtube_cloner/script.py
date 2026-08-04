"""Stage 4 -- geracao do roteiro original a partir do DNA + tema novo."""

from __future__ import annotations

import json
import logging

from engine.intelligence.youtube_cloner import prompts
from engine.intelligence.youtube_cloner.llm import call_json
from engine.intelligence.youtube_cloner.schemas import Scene, ScriptDraft, VideoDNA

logger = logging.getLogger("youtube_cloner.script")

SECONDS_PER_SCENE = 10


def _dna_summary(dna: VideoDNA) -> str:
    """So os campos estruturais entram no prompt de geracao.

    ``sample_video_ids`` e ``recurring_themes`` ficam de fora de proposito:
    nao queremos o gerador ancorado nos temas do canal original, so na forma.
    """
    payload = {
        "audience": dna.audience,
        "hook_pattern": dna.hook_pattern,
        "hook_seconds": dna.hook_seconds,
        "body_architecture": dna.body_architecture,
        "tension_rhythm": dna.tension_rhythm,
        "cta_pattern": dna.cta_pattern,
        "title_formulas": dna.title_formulas,
        "voice_profile": dna.voice_profile,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def generate_script(
    dna: VideoDNA,
    topic: str,
    *,
    language: str = "pt-BR",
    duration_minutes: float | None = None,
    dossier: list[str] | None = None,
    provider: str | None = None,
) -> ScriptDraft:
    """DNA + tema -> ScriptDraft com cenas ja fatiadas."""
    duration = duration_minutes or dna.target_duration_minutes
    wpm = dna.words_per_minute or 150
    target_words = int(duration * wpm)
    words_per_scene = max(int(wpm * SECONDS_PER_SCENE / 60), 10)

    dossier_block = (
        prompts.DOSSIER_BLOCK.format(dossier="\n".join(f"- {d}" for d in dossier))
        if dossier
        else prompts.DOSSIER_MISSING
    )

    prompt = prompts.SCRIPT_GENERATION.format(
        dna=_dna_summary(dna),
        topic=topic,
        language=language,
        duration=duration,
        wpm=wpm,
        target_words=target_words,
        words_per_scene=words_per_scene,
        dossier_block=dossier_block,
    )
    data = call_json(prompt, step="script", provider=provider, max_output_tokens=16_000)

    scenes = [
        Scene(
            index=int(s.get("index", i)),
            narration=(s.get("narration") or "").strip(),
            image_prompt=s.get("image_prompt", ""),
            video_prompt=s.get("video_prompt", ""),
        )
        for i, s in enumerate(data.get("scenes", []), start=1)
    ]
    scenes = [s for s in scenes if s.narration]
    if not scenes:
        raise ValueError("O modelo nao devolveu nenhuma cena com narracao.")

    for scene in scenes:
        scene.duration_seconds = round(len(scene.narration.split()) / wpm * 60, 2)

    draft = ScriptDraft(
        topic=topic,
        language=language,
        dna_channel_id=dna.channel_id,
        titles=data.get("titles", []),
        hook=(data.get("hook") or "").strip(),
        scenes=scenes,
        cta=(data.get("cta") or "").strip(),
        description=data.get("description", ""),
        tags=data.get("tags", []),
        thumbnail_concept=data.get("thumbnail_concept", ""),
        research_dossier=dossier or [],
    )
    drift = abs(draft.word_count - target_words) / max(target_words, 1)
    if drift > 0.35:
        logger.warning(
            "Roteiro com %d palavras vs alvo %d (%.0f%% de desvio). "
            "Considere regenerar ou ajustar duration_minutes.",
            draft.word_count,
            target_words,
            drift * 100,
        )
    logger.info("Roteiro: %d cenas, %d palavras", len(scenes), draft.word_count)
    return draft
