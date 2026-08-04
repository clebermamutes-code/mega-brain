"""youtube_cloner -- modelagem estrutural de canais faceless do YouTube.

O pacote implementa o pipeline descrito em
``docs/architecture/youtube-cloner-spec.md``: descobrir um canal modelo,
destilar o DNA estrutural dos seus melhores videos e reemitir esse DNA como
roteiro/visual/audio ORIGINAL para um tema novo.

Principio nao-negociavel: reusa-se ESTRUTURA (gancho, ritmo, arco, densidade
de corte). Nunca texto, imagem ou trecho do video original -- ver
``guardrails.py``, que roda como gate bloqueante entre a Stage 3 (DNA) e a
Stage 4 (geracao).
"""

from engine.intelligence.youtube_cloner.schemas import (
    ChannelModel,
    EditManifest,
    ImagePromptSet,
    ScriptDraft,
    VideoCandidate,
    VideoDNA,
    VoiceTrack,
)

__all__ = [
    "ChannelModel",
    "EditManifest",
    "ImagePromptSet",
    "ScriptDraft",
    "VideoCandidate",
    "VideoDNA",
    "VoiceTrack",
]
