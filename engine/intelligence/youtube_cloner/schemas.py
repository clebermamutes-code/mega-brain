"""Contratos de dados do pipeline youtube_cloner.

Cada estagio do pipeline consome e produz exatamente um destes objetos. Todos
serializam para JSON puro (``to_dict``) porque os artefatos sao gravados em
``artifacts/youtube-cloner/{slug}/`` e reabertos por estagios posteriores,
possivelmente em outra sessao.

Os limiares default vem da secao 3 do extrato de fontes (ver
``docs/architecture/youtube-cloner-spec.md``).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"


def _dump(obj: Any) -> dict:
    data = asdict(obj)
    data["schema_version"] = SCHEMA_VERSION
    return data


@dataclass
class SelectionFilters:
    """Filtros de selecao de canal/video modelo.

    Defaults extraidos das fontes: minimo de 10.000 views, video com ate 190
    dias (tendencia ainda quente) e long-form apenas (Shorts bloqueados).
    """

    min_views: int = 10_000
    max_age_days: int = 190
    min_duration_seconds: int = 180
    max_duration_seconds: int = 3_600
    language: str | None = None
    region_code: str = "BR"
    max_results: int = 25

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VideoCandidate:
    """Um video que passou pelos filtros de descoberta."""

    video_id: str
    channel_id: str
    channel_title: str
    title: str
    published_at: str
    duration_seconds: int
    view_count: int
    like_count: int | None = None
    comment_count: int | None = None
    thumbnail_url: str | None = None
    url: str = ""

    def __post_init__(self) -> None:
        if not self.url:
            self.url = f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def views_per_day(self) -> float:
        """Proxy de velocidade — separa 'viral agora' de 'acumulou em 3 anos'."""
        from datetime import datetime, timezone

        try:
            pub = datetime.fromisoformat(self.published_at.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
        age_days = max((datetime.now(timezone.utc) - pub).days, 1)
        return round(self.view_count / age_days, 2)

    def to_dict(self) -> dict:
        data = _dump(self)
        data["views_per_day"] = self.views_per_day
        return data


@dataclass
class ChannelModel:
    """Canal escolhido como molde + os videos que serao dissecados."""

    channel_id: str
    title: str
    subscriber_count: int | None
    video_count: int | None
    total_views: int | None
    niche: str = ""
    faceless: bool | None = None
    filters: SelectionFilters = field(default_factory=SelectionFilters)
    top_videos: list[VideoCandidate] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "channel_id": self.channel_id,
            "title": self.title,
            "subscriber_count": self.subscriber_count,
            "video_count": self.video_count,
            "total_views": self.total_views,
            "niche": self.niche,
            "faceless": self.faceless,
            "filters": self.filters.to_dict(),
            "top_videos": [v.to_dict() for v in self.top_videos],
        }


@dataclass
class VideoDNA:
    """DNA estrutural destilado de N transcricoes do canal modelo.

    Este objeto e deliberadamente ABSTRATO: guarda padroes (tipo de gancho,
    arco, cadencia), nunca frases literais do original. ``guardrails.py``
    valida isso antes da geracao.
    """

    channel_id: str
    sample_video_ids: list[str]
    audience: str = ""
    hook_pattern: str = ""
    hook_seconds: int = 30
    body_architecture: list[str] = field(default_factory=list)
    tension_rhythm: str = ""
    cta_pattern: str = ""
    words_per_minute: int = 150
    target_duration_minutes: float = 8.0
    seconds_per_visual: tuple[int, int] = (1, 3)
    visual_style: str = ""
    voice_profile: str = ""
    title_formulas: list[str] = field(default_factory=list)
    thumbnail_composition: str = ""
    recurring_themes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = _dump(self)
        data["seconds_per_visual"] = list(self.seconds_per_visual)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> VideoDNA:
        payload = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        spv = payload.get("seconds_per_visual")
        if isinstance(spv, list) and len(spv) == 2:
            payload["seconds_per_visual"] = (int(spv[0]), int(spv[1]))
        return cls(**payload)


@dataclass
class Scene:
    """Uma cena = um bloco de narracao + um visual."""

    index: int
    narration: str
    image_prompt: str = ""
    video_prompt: str = ""
    duration_seconds: float = 0.0
    asset_path: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScriptDraft:
    """Roteiro gerado a partir do DNA + tema novo."""

    topic: str
    language: str
    dna_channel_id: str
    titles: list[str] = field(default_factory=list)
    hook: str = ""
    scenes: list[Scene] = field(default_factory=list)
    cta: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    thumbnail_concept: str = ""
    research_dossier: list[str] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        body = " ".join([self.hook] + [s.narration for s in self.scenes] + [self.cta])
        return len(body.split())

    @property
    def full_narration(self) -> str:
        parts = [self.hook] + [s.narration for s in self.scenes] + [self.cta]
        return "\n\n".join(p.strip() for p in parts if p and p.strip())

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "topic": self.topic,
            "language": self.language,
            "dna_channel_id": self.dna_channel_id,
            "titles": self.titles,
            "hook": self.hook,
            "scenes": [s.to_dict() for s in self.scenes],
            "cta": self.cta,
            "description": self.description,
            "tags": self.tags,
            "thumbnail_concept": self.thumbnail_concept,
            "research_dossier": self.research_dossier,
            "word_count": self.word_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ScriptDraft:
        scenes = [
            Scene(**{k: v for k, v in s.items() if k in Scene.__dataclass_fields__})
            for s in data.get("scenes", [])
        ]
        payload = {
            k: v
            for k, v in data.items()
            if k in cls.__dataclass_fields__ and k != "scenes"
        }
        payload["scenes"] = scenes
        return cls(**payload)


@dataclass
class ImagePromptSet:
    """Prompts de imagem + a ancora de consistencia de personagem."""

    character_reference_prompt: str
    style_suffix: str
    aspect_ratio: str = "16:9"
    prompts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return _dump(self)


@dataclass
class VoiceTrack:
    """Resultado da locucao."""

    audio_path: str
    provider: str
    voice_id: str
    duration_seconds: float | None = None
    word_count: int = 0

    def to_dict(self) -> dict:
        return _dump(self)


@dataclass
class EditManifest:
    """Plano de montagem — consumido por ffmpeg ou importado no CapCut."""

    project_name: str
    fps: int = 30
    resolution: str = "1920x1080"
    audio_path: str = ""
    background_music_gain_db: float = -22.0
    clip_native_gain_db: float = -60.0
    transition: str = "fade"
    transition_seconds: float = 0.25
    subtitle_style: str = "white text, black outline, bottom-center"
    timeline: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return _dump(self)


def write_artifact(obj: Any, path: Path) -> Path:
    """Grava o ``to_dict()`` de um contrato como JSON identado."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = obj.to_dict() if hasattr(obj, "to_dict") else obj
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_artifact(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
