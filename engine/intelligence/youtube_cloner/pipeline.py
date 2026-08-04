"""Orquestrador CLI do youtube_cloner.

Cada estagio grava seu artefato em ``artifacts/youtube-cloner/{slug}/`` e o
estagio seguinte le do disco. Isso torna o pipeline retomavel: se a Stage 4
falhar, a Stage 3 nao precisa rodar de novo (nem pagar o LLM de novo).

Uso:

    python3 -m engine.intelligence.youtube_cloner.pipeline discover --query "estoicismo"
    python3 -m engine.intelligence.youtube_cloner.pipeline dna --channel @canal --slug meu-canal
    python3 -m engine.intelligence.youtube_cloner.pipeline script --slug meu-canal --topic "..."
    python3 -m engine.intelligence.youtube_cloner.pipeline visuals --slug meu-canal
    python3 -m engine.intelligence.youtube_cloner.pipeline voice --slug meu-canal
    python3 -m engine.intelligence.youtube_cloner.pipeline assemble --slug meu-canal
    python3 -m engine.intelligence.youtube_cloner.pipeline full --channel @canal --slug x --topic "..."
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

from engine.intelligence.youtube_cloner import (
    discovery,
    dna as dna_stage,
    edit_manifest,
    guardrails,
    script as script_stage,
    transcripts as transcripts_stage,
    visuals,
    voice as voice_stage,
)
from engine.intelligence.youtube_cloner.schemas import (
    ScriptDraft,
    SelectionFilters,
    VideoDNA,
    VoiceTrack,
    read_artifact,
    write_artifact,
)

logger = logging.getLogger("youtube_cloner.pipeline")

ARTIFACT_ROOT = Path(
    os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd())
) / "artifacts" / "youtube-cloner"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "projeto"


def project_dir(slug: str) -> Path:
    path = ARTIFACT_ROOT / slugify(slug)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_env() -> None:
    """Le o .env do projeto sem depender de python-dotenv."""
    env_file = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd())) / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


# --------------------------------------------------------------------------
# Estagios
# --------------------------------------------------------------------------

def cmd_discover(args: argparse.Namespace) -> int:
    filters = SelectionFilters(
        min_views=args.min_views,
        max_age_days=args.max_age_days,
        region_code=args.region,
        max_results=args.limit,
    )
    results = discovery.search_videos(args.query, filters)
    if not results:
        print("Nenhum video passou nos filtros. Afrouxe --min-views ou --max-age-days.")
        return 1
    print(f"\n{len(results)} videos aprovados (ordenados por views/dia):\n")
    for v in results:
        print(
            f"  {v.views_per_day:>10,.0f} v/dia | {v.view_count:>10,} views | "
            f"{v.duration_seconds // 60:>3}min | {v.channel_title[:28]:<28} | {v.title[:60]}"
        )
        print(f"               {v.url}")
    out = ARTIFACT_ROOT / "discovery" / f"{slugify(args.query)}.json"
    write_artifact({"query": args.query, "results": [v.to_dict() for v in results]}, out)
    print(f"\nArtefato: {out}")
    return 0


def cmd_dna(args: argparse.Namespace) -> int:
    out_dir = project_dir(args.slug)
    channel_id = discovery.resolve_channel_id(args.channel)
    model = discovery.build_channel_model(channel_id, sample_size=args.sample_size)
    write_artifact(model, out_dir / "channel-model.json")
    print(f"Canal: {model.title} ({len(model.top_videos)} videos na amostra)")

    ids = [v.video_id for v in model.top_videos]
    texts = transcripts_stage.fetch_many(ids, languages=args.languages)
    transcripts_stage.save(texts, out_dir / "transcripts.json")
    print(f"Transcricoes obtidas: {len(texts)}/{len(ids)}")

    dna = dna_stage.extract_dna(channel_id, texts, provider=args.provider)
    write_artifact(dna, out_dir / "video-dna.json")
    print(f"DNA gravado: {out_dir / 'video-dna.json'}")
    print(f"  Gancho: {dna.hook_pattern[:100]}")
    print(f"  Corpo:  {' -> '.join(dna.body_architecture[:4])}")
    return 0


def cmd_script(args: argparse.Namespace) -> int:
    out_dir = project_dir(args.slug)
    dna = VideoDNA.from_dict(read_artifact(out_dir / "video-dna.json"))

    dossier: list[str] = []
    if args.dossier:
        dossier_path = Path(args.dossier)
        if not dossier_path.exists():
            print(f"Dossie nao encontrado: {dossier_path}", file=sys.stderr)
            return 1
        dossier = [
            l.strip("- ").strip()
            for l in dossier_path.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]

    draft = script_stage.generate_script(
        dna,
        args.topic,
        language=args.language,
        duration_minutes=args.duration,
        dossier=dossier,
        provider=args.provider,
    )

    # Gate bloqueante: nada avanca sem passar no teste de originalidade.
    transcripts_path = out_dir / "transcripts.json"
    if transcripts_path.exists():
        sources = read_artifact(transcripts_path)
        try:
            report = guardrails.enforce(draft.full_narration, sources)
        except guardrails.OriginalityViolation as exc:
            write_artifact(draft, out_dir / "script-REPROVADO.json")
            print(f"\nBLOQUEADO: {exc}", file=sys.stderr)
            return 2
        write_artifact(report, out_dir / "originality-report.json")
        print(
            f"Originalidade OK: overlap {report.overlap_ratio:.2%}, "
            f"maior trecho literal {report.longest_match} palavras"
        )
    else:
        print("AVISO: transcripts.json ausente — gate de originalidade PULADO.")

    write_artifact(draft, out_dir / "script.json")
    (out_dir / "narration.txt").write_text(draft.full_narration, encoding="utf-8")
    print(f"Roteiro: {len(draft.scenes)} cenas, {draft.word_count} palavras")
    print(f"  Titulos sugeridos: {json.dumps(draft.titles[:3], ensure_ascii=False)}")
    return 0


def cmd_visuals(args: argparse.Namespace) -> int:
    out_dir = project_dir(args.slug)
    dna = VideoDNA.from_dict(read_artifact(out_dir / "video-dna.json"))
    draft = ScriptDraft.from_dict(read_artifact(out_dir / "script.json"))

    prompt_set = visuals.generate_image_prompts(
        draft, dna, aspect_ratio=args.aspect_ratio, provider=args.provider
    )
    write_artifact(prompt_set, out_dir / "image-prompts.json")
    write_artifact(draft, out_dir / "script.json")  # cenas agora tem prompts
    (out_dir / "image-prompts.txt").write_text(
        visuals.to_batch_file(prompt_set), encoding="utf-8"
    )
    print(f"Prompts visuais: {len(prompt_set.prompts)} cenas")
    print(f"  Cole em lote: {out_dir / 'image-prompts.txt'}")
    return 0


def cmd_voice(args: argparse.Namespace) -> int:
    out_dir = project_dir(args.slug)
    draft = ScriptDraft.from_dict(read_artifact(out_dir / "script.json"))
    track = voice_stage.synthesize(draft, out_dir, voice_id=args.voice_id)
    write_artifact(track, out_dir / "voice-track.json")
    print(f"Locucao: {track.audio_path} ({track.duration_seconds or '?'}s)")
    return 0


def cmd_assemble(args: argparse.Namespace) -> int:
    out_dir = project_dir(args.slug)
    dna = VideoDNA.from_dict(read_artifact(out_dir / "video-dna.json"))
    draft = ScriptDraft.from_dict(read_artifact(out_dir / "script.json"))

    track = None
    voice_path = out_dir / "voice-track.json"
    if voice_path.exists():
        data = read_artifact(voice_path)
        track = VoiceTrack(
            audio_path=data["audio_path"],
            provider=data["provider"],
            voice_id=data["voice_id"],
            duration_seconds=data.get("duration_seconds"),
            word_count=data.get("word_count", 0),
        )

    manifest = edit_manifest.build_manifest(
        draft, dna, track, project_name=slugify(args.slug)
    )
    write_artifact(manifest, out_dir / "edit-manifest.json")
    script_path = edit_manifest.write_render_script(
        manifest,
        assets_dir=out_dir / "assets",
        output_video=out_dir / f"{slugify(args.slug)}.mp4",
        script_path=out_dir / "render.sh",
    )
    (out_dir / "assets").mkdir(exist_ok=True)
    print(f"Manifesto: {len(manifest.timeline)} cortes")
    print(f"  Coloque as imagens numeradas (001.png...) em {out_dir / 'assets'}")
    print(f"  Depois rode: {script_path}")
    return 0


def cmd_full(args: argparse.Namespace) -> int:
    for step in (cmd_dna, cmd_script, cmd_visuals):
        code = step(args)
        if code != 0:
            print(f"Pipeline interrompido em {step.__name__} (exit {code})", file=sys.stderr)
            return code
    if args.voice_id:
        code = cmd_voice(args)
        if code != 0:
            return code
    else:
        print("Sem --voice-id: pulando locucao. Gere manualmente e rode `voice` depois.")
    return cmd_assemble(args)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="youtube_cloner",
        description="Modelagem estrutural de canais faceless do YouTube.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--slug", required=True, help="Nome do projeto (pasta de artefatos)")
        p.add_argument("--provider", default=None, help="anthropic | openai | gemini")

    d = sub.add_parser("discover", help="Busca videos modelo por nicho")
    d.add_argument("--query", required=True)
    d.add_argument("--min-views", type=int, default=10_000)
    d.add_argument("--max-age-days", type=int, default=190)
    d.add_argument("--region", default="BR")
    d.add_argument("--limit", type=int, default=25)
    d.set_defaults(func=cmd_discover)

    n = sub.add_parser("dna", help="Extrai o DNA estrutural de um canal")
    add_common(n)
    n.add_argument("--channel", required=True, help="URL, @handle ou UC...")
    n.add_argument("--sample-size", type=int, default=12)
    n.add_argument("--languages", nargs="*", default=["pt", "pt-BR", "en"])
    n.set_defaults(func=cmd_dna)

    s = sub.add_parser("script", help="Gera roteiro original a partir do DNA")
    add_common(s)
    s.add_argument("--topic", required=True)
    s.add_argument("--language", default="pt-BR")
    s.add_argument("--duration", type=float, default=None, help="minutos")
    s.add_argument("--dossier", default=None, help="Arquivo de fatos verificados")
    s.set_defaults(func=cmd_script)

    vi = sub.add_parser("visuals", help="Gera prompts de imagem consistentes")
    add_common(vi)
    vi.add_argument("--aspect-ratio", default="16:9")
    vi.set_defaults(func=cmd_visuals)

    vo = sub.add_parser("voice", help="Gera a locucao")
    add_common(vo)
    vo.add_argument("--voice-id", default=None)
    vo.set_defaults(func=cmd_voice)

    a = sub.add_parser("assemble", help="Monta o manifesto de edicao + render.sh")
    add_common(a)
    a.set_defaults(func=cmd_assemble)

    f = sub.add_parser("full", help="dna -> script -> visuals -> voice -> assemble")
    add_common(f)
    f.add_argument("--channel", required=True)
    f.add_argument("--topic", required=True)
    f.add_argument("--language", default="pt-BR")
    f.add_argument("--duration", type=float, default=None)
    f.add_argument("--dossier", default=None)
    f.add_argument("--sample-size", type=int, default=12)
    f.add_argument("--languages", nargs="*", default=["pt", "pt-BR", "en"])
    f.add_argument("--aspect-ratio", default="16:9")
    f.add_argument("--voice-id", default=None)
    f.set_defaults(func=cmd_full)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(name)s] %(message)s",
    )
    _load_env()
    try:
        return args.func(args)
    except (
        discovery.DiscoveryError,
        transcripts_stage.TranscriptUnavailable,
        voice_stage.VoiceError,
    ) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
