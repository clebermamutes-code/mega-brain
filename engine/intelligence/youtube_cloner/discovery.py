"""Stage 1 -- descoberta e filtragem de canais/videos modelo.

Usa a YouTube Data API v3 (chave em ``YOUTUBE_API_KEY``). Toda a filtragem
numerica das fontes vive aqui e e deterministica -- nenhum LLM decide o que
entra: views minimas, idade maxima, e bloqueio de Shorts por duracao.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from engine.intelligence.youtube_cloner.schemas import (
    ChannelModel,
    SelectionFilters,
    VideoCandidate,
)

logger = logging.getLogger("youtube_cloner.discovery")

API_ROOT = "https://www.googleapis.com/youtube/v3"
_ISO_DURATION = re.compile(
    r"P(?:(?P<days>\d+)D)?T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?"
)


class DiscoveryError(RuntimeError):
    """Falha de rede, quota ou credencial na YouTube Data API."""


def _api_key() -> str:
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        raise DiscoveryError(
            "YOUTUBE_API_KEY ausente. Adicione ao .env "
            "(console.cloud.google.com > APIs > YouTube Data API v3)."
        )
    return key


def _get(endpoint: str, params: dict) -> dict:
    params = {**params, "key": _api_key()}
    url = f"{API_ROOT}/{endpoint}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - rede
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise DiscoveryError(f"YouTube API {endpoint} -> HTTP {exc.code}: {detail}") from exc
    except OSError as exc:  # pragma: no cover - rede
        raise DiscoveryError(f"YouTube API {endpoint} indisponivel: {exc}") from exc


def parse_iso_duration(value: str) -> int:
    """``PT8M32S`` -> 512 segundos. Retorna 0 quando nao parseavel."""
    match = _ISO_DURATION.fullmatch(value or "")
    if not match:
        return 0
    parts = {k: int(v) for k, v in match.groupdict(default="0").items()}
    return (
        parts["days"] * 86_400
        + parts["h"] * 3_600
        + parts["m"] * 60
        + parts["s"]
    )


def _hydrate(video_ids: list[str]) -> list[VideoCandidate]:
    """search.list nao devolve views/duracao — videos.list devolve."""
    out: list[VideoCandidate] = []
    for chunk_start in range(0, len(video_ids), 50):
        chunk = video_ids[chunk_start : chunk_start + 50]
        data = _get(
            "videos",
            {"part": "snippet,statistics,contentDetails", "id": ",".join(chunk)},
        )
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            thumbs = snippet.get("thumbnails", {})
            best = thumbs.get("maxres") or thumbs.get("high") or thumbs.get("default") or {}
            out.append(
                VideoCandidate(
                    video_id=item["id"],
                    channel_id=snippet.get("channelId", ""),
                    channel_title=snippet.get("channelTitle", ""),
                    title=snippet.get("title", ""),
                    published_at=snippet.get("publishedAt", ""),
                    duration_seconds=parse_iso_duration(
                        item.get("contentDetails", {}).get("duration", "")
                    ),
                    view_count=int(stats.get("viewCount", 0)),
                    like_count=int(stats["likeCount"]) if "likeCount" in stats else None,
                    comment_count=(
                        int(stats["commentCount"]) if "commentCount" in stats else None
                    ),
                    thumbnail_url=best.get("url"),
                )
            )
    return out


def apply_filters(
    candidates: list[VideoCandidate], filters: SelectionFilters
) -> list[VideoCandidate]:
    """Gate deterministico. Sem LLM, sem 'quase la'."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=filters.max_age_days)
    kept: list[VideoCandidate] = []
    for c in candidates:
        if c.view_count < filters.min_views:
            continue
        # Shorts sao bloqueados pelo piso de duracao (fontes: long-form apenas).
        if not (
            filters.min_duration_seconds
            <= c.duration_seconds
            <= filters.max_duration_seconds
        ):
            continue
        try:
            published = datetime.fromisoformat(c.published_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if published < cutoff:
            continue
        kept.append(c)
    kept.sort(key=lambda v: v.views_per_day, reverse=True)
    return kept


def search_videos(
    query: str, filters: SelectionFilters | None = None
) -> list[VideoCandidate]:
    """Busca por nicho e devolve apenas o que sobrevive aos filtros."""
    filters = filters or SelectionFilters()
    published_after = (
        datetime.now(timezone.utc) - timedelta(days=filters.max_age_days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "part": "id",
        "q": query,
        "type": "video",
        "videoDuration": "medium",  # exclui Shorts na origem
        "order": "viewCount",
        "maxResults": min(filters.max_results, 50),
        "publishedAfter": published_after,
        "regionCode": filters.region_code,
    }
    if filters.language:
        params["relevanceLanguage"] = filters.language
    data = _get("search", params)
    ids = [i["id"]["videoId"] for i in data.get("items", []) if i.get("id", {}).get("videoId")]
    if not ids:
        logger.warning("Nenhum video retornado para query=%r", query)
        return []
    return apply_filters(_hydrate(ids), filters)


def top_videos_of_channel(
    channel_id: str, filters: SelectionFilters | None = None
) -> list[VideoCandidate]:
    """Os videos mais vistos de um canal — a amostra para extrair o DNA."""
    filters = filters or SelectionFilters()
    data = _get(
        "search",
        {
            "part": "id",
            "channelId": channel_id,
            "type": "video",
            "order": "viewCount",
            "maxResults": min(filters.max_results, 50),
        },
    )
    ids = [i["id"]["videoId"] for i in data.get("items", []) if i.get("id", {}).get("videoId")]
    if not ids:
        return []
    hydrated = _hydrate(ids)
    # Para amostragem de DNA a idade nao importa: a formula que funcionou ha
    # 2 anos ainda ensina estrutura. So o piso de duracao permanece.
    duration_only = SelectionFilters(
        min_views=filters.min_views,
        max_age_days=36_500,
        min_duration_seconds=filters.min_duration_seconds,
        max_duration_seconds=filters.max_duration_seconds,
    )
    return apply_filters(hydrated, duration_only)


def build_channel_model(
    channel_id: str, filters: SelectionFilters | None = None, sample_size: int = 12
) -> ChannelModel:
    """Monta o ChannelModel (Stage 1 -> artefato ``channel-model.json``)."""
    filters = filters or SelectionFilters()
    data = _get("channels", {"part": "snippet,statistics", "id": channel_id})
    items = data.get("items", [])
    if not items:
        raise DiscoveryError(f"Canal {channel_id} nao encontrado ou sem acesso.")
    snippet = items[0].get("snippet", {})
    stats = items[0].get("statistics", {})
    videos = top_videos_of_channel(channel_id, filters)[:sample_size]
    return ChannelModel(
        channel_id=channel_id,
        title=snippet.get("title", ""),
        subscriber_count=(
            int(stats["subscriberCount"]) if "subscriberCount" in stats else None
        ),
        video_count=int(stats["videoCount"]) if "videoCount" in stats else None,
        total_views=int(stats["viewCount"]) if "viewCount" in stats else None,
        filters=filters,
        top_videos=videos,
    )


def resolve_channel_id(url_or_id: str) -> str:
    """Aceita ``UC...``, ``/channel/UC...``, ``/@handle`` ou URL de video."""
    value = url_or_id.strip()
    if value.startswith("UC") and "/" not in value:
        return value
    match = re.search(r"/channel/(UC[\w-]+)", value)
    if match:
        return match.group(1)
    handle = re.search(r"@([\w.-]+)", value)
    if handle:
        data = _get("channels", {"part": "id", "forHandle": f"@{handle.group(1)}"})
        items = data.get("items", [])
        if items:
            return items[0]["id"]
    video = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", value)
    if video:
        data = _get("videos", {"part": "snippet", "id": video.group(1)})
        items = data.get("items", [])
        if items:
            return items[0]["snippet"]["channelId"]
    raise DiscoveryError(f"Nao consegui resolver channel_id a partir de: {url_or_id!r}")
