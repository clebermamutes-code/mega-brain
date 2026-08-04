"""Stage 3 -- destilacao do VideoDNA a partir das transcricoes."""

from __future__ import annotations

import logging

from engine.intelligence.youtube_cloner import prompts
from engine.intelligence.youtube_cloner.llm import call_json
from engine.intelligence.youtube_cloner.schemas import VideoDNA

logger = logging.getLogger("youtube_cloner.dna")

# Teto por transcricao no corpus. 12 videos x 6k chars ~= 72k chars, o que
# cabe folgado na janela dos modelos usados e mantem o custo previsivel.
MAX_CHARS_PER_TRANSCRIPT = 6_000


def build_corpus(transcripts: dict[str, str]) -> str:
    blocks = []
    for i, (video_id, text) in enumerate(transcripts.items(), start=1):
        excerpt = text[:MAX_CHARS_PER_TRANSCRIPT]
        blocks.append(f"--- VIDEO {i} (id={video_id}) ---\n{excerpt}")
    return "\n\n".join(blocks)


def extract_dna(
    channel_id: str, transcripts: dict[str, str], provider: str | None = None
) -> VideoDNA:
    """Transcricoes -> VideoDNA (estrutura abstrata, sem conteudo literal)."""
    if not transcripts:
        raise ValueError("Nenhuma transcricao fornecida para extrair DNA.")

    prompt = prompts.DNA_EXTRACTION.format(
        n=len(transcripts), corpus=build_corpus(transcripts)
    )
    data = call_json(prompt, step="dna", provider=provider, max_output_tokens=4_000)

    data["channel_id"] = channel_id
    data["sample_video_ids"] = list(transcripts.keys())
    dna = VideoDNA.from_dict(data)

    if not dna.hook_pattern or not dna.body_architecture:
        raise ValueError(
            "DNA incompleto: hook_pattern e body_architecture sao obrigatorios. "
            f"Recebido: {list(data.keys())}"
        )
    logger.info(
        "DNA extraido de %d videos: %d blocos de corpo, %d formulas de titulo",
        len(transcripts),
        len(dna.body_architecture),
        len(dna.title_formulas),
    )
    return dna
