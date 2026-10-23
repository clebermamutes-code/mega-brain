"""Testes do gate de originalidade e dos filtros deterministicos.

Rodar: python3 -m engine.intelligence.youtube_cloner.tests.test_guardrails
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from engine.intelligence.youtube_cloner import guardrails
from engine.intelligence.youtube_cloner.discovery import apply_filters, parse_iso_duration
from engine.intelligence.youtube_cloner.schemas import SelectionFilters, VideoCandidate

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        FAILURES.append(name)


SOURCE = (
    "Em mil novecentos e quarenta e tres um submarino alemao desapareceu no "
    "atlantico sul sem deixar rastro algum e ninguem soube explicar o motivo "
    "ate hoje os pesquisadores discutem o que realmente aconteceu naquela noite"
)


def test_identical_text_fails() -> None:
    report = guardrails.check_originality(SOURCE, [SOURCE])
    check("copia literal reprova", not report.passed)
    check(
        "copia literal tem overlap total",
        report.overlap_ratio > 0.9,
        f"(overlap={report.overlap_ratio})",
    )


def test_original_text_passes() -> None:
    generated = (
        "As placas tectonicas se movimentam poucos centimetros por ano mas essa "
        "lentidao esconde uma forca capaz de reorganizar continentes inteiros ao "
        "longo de milhoes de anos e mudar completamente o clima do planeta"
    )
    report = guardrails.check_originality(generated, [SOURCE])
    check("texto original aprova", report.passed)
    check("texto original tem overlap zero", report.overlap_ratio == 0.0)


def test_accent_and_punctuation_evasion() -> None:
    """Trocar acento/pontuacao nao deve driblar o detector."""
    evasive = SOURCE.replace("alemao", "alemão").replace("atlantico", "atlântico!")
    report = guardrails.check_originality(evasive, [SOURCE])
    check("evasao por acento/pontuacao reprova", not report.passed)


def test_longest_match_detection() -> None:
    generated = (
        "Vamos falar de outra coisa totalmente diferente hoje mas antes lembre "
        "que um submarino alemao desapareceu no atlantico sul sem deixar rastro "
        "algum e ninguem soube explicar o motivo e isso muda tudo que sabemos"
    )
    report = guardrails.check_originality(generated, [SOURCE])
    check(
        "trecho longo colado e detectado",
        report.longest_match >= guardrails.MAX_LONGEST_MATCH,
        f"(longest={report.longest_match})",
    )
    check("trecho longo colado reprova", not report.passed)


def test_enforce_raises() -> None:
    try:
        guardrails.enforce(SOURCE, [SOURCE])
    except guardrails.OriginalityViolation:
        check("enforce levanta em violacao", True)
        return
    check("enforce levanta em violacao", False)


def test_short_text_is_safe() -> None:
    report = guardrails.check_originality("texto curto", [SOURCE])
    check("texto menor que o n-grama nao quebra", report.passed and report.candidate_ngrams == 0)


def _candidate(**kw) -> VideoCandidate:
    base = dict(
        video_id="abc12345678",
        channel_id="UC123",
        channel_title="Canal",
        title="Titulo",
        published_at=(datetime.now(timezone.utc) - timedelta(days=10)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        duration_seconds=600,
        view_count=50_000,
    )
    base.update(kw)
    return VideoCandidate(**base)


def test_filters() -> None:
    f = SelectionFilters()
    check("video valido passa", len(apply_filters([_candidate()], f)) == 1)
    check(
        "abaixo de 10k views reprova",
        len(apply_filters([_candidate(view_count=9_999)], f)) == 0,
    )
    check(
        "short (45s) reprova",
        len(apply_filters([_candidate(duration_seconds=45)], f)) == 0,
    )
    old = (datetime.now(timezone.utc) - timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ")
    check(
        "video com mais de 190 dias reprova",
        len(apply_filters([_candidate(published_at=old)], f)) == 0,
    )
    check(
        "published_at invalido reprova em vez de explodir",
        len(apply_filters([_candidate(published_at="lixo")], f)) == 0,
    )


def test_duration_parser() -> None:
    check("PT8M32S = 512s", parse_iso_duration("PT8M32S") == 512)
    check("PT1H2M3S = 3723s", parse_iso_duration("PT1H2M3S") == 3_723)
    check("PT45S = 45s", parse_iso_duration("PT45S") == 45)
    check("invalido = 0", parse_iso_duration("banana") == 0)


def test_video_id_parser() -> None:
    from engine.intelligence.youtube_cloner.transcripts import parse_video_ids

    check(
        "URL padrao",
        parse_video_ids("https://www.youtube.com/watch?v=y1Nt7ZTwya0") == ["y1Nt7ZTwya0"],
    )
    check(
        "parametro de tracking &pp= e descartado",
        parse_video_ids("https://www.youtube.com/watch?v=ePHtuxHVANg&pp=0gcJCaML")
        == ["ePHtuxHVANg"],
    )
    check(
        "youtu.be com ?si=",
        parse_video_ids("https://youtu.be/j2NbfGGIw-k?si=abc") == ["j2NbfGGIw-k"],
    )
    check("id cru sem URL", parse_video_ids("y1Nt7ZTwya0") == ["y1Nt7ZTwya0"])
    check(
        "duplicata removida preservando ordem",
        parse_video_ids(
            "https://youtu.be/aaaaaaaaaaa\nhttps://youtu.be/bbbbbbbbbbb\nhttps://youtu.be/aaaaaaaaaaa"
        )
        == ["aaaaaaaaaaa", "bbbbbbbbbbb"],
    )
    check("comentario ignorado", parse_video_ids("# nota\n") == [])
    check("linha invalida nao quebra", parse_video_ids("lixo aqui") == [])


def test_sample_file() -> None:
    from pathlib import Path

    from engine.intelligence.youtube_cloner.transcripts import parse_video_ids

    sample = Path(__file__).parent.parent / "samples" / "olivrosagrado.txt"
    if not sample.exists():
        check("amostra olivrosagrado presente", False, "(arquivo ausente)")
        return
    ids = parse_video_ids(sample.read_text(encoding="utf-8"))
    check("amostra tem 27 videos", len(ids) == 27, f"(achou {len(ids)})")
    check("amostra sem duplicatas", len(set(ids)) == len(ids))


def main() -> int:
    print("\n== guardrails ==")
    test_identical_text_fails()
    test_original_text_passes()
    test_accent_and_punctuation_evasion()
    test_longest_match_detection()
    test_enforce_raises()
    test_short_text_is_safe()
    print("\n== discovery ==")
    test_filters()
    test_duration_parser()
    print("\n== parser de video_id ==")
    test_video_id_parser()
    test_sample_file()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} teste(s) falharam: {FAILURES}")
        return 1
    print("Todos os testes passaram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
