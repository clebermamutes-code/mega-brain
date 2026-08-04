"""Gate de originalidade -- roda entre a geracao e qualquer producao de midia.

As fontes repetem que o processo e "modelar, nunca copiar", mas nao oferecem
nenhum mecanismo de verificacao: a garantia fica na boa intencao do operador.
Este modulo transforma a regra em teste executavel.

Metodo: sobreposicao de n-gramas. Extraimos todos os n-gramas de {n} palavras
do roteiro gerado e das transcricoes de origem; qualquer n-grama presente nos
dois e uma colisao. Duas metricas saem dai:

  - ``overlap_ratio``  -- fracao dos n-gramas do roteiro que colidem.
  - ``longest_match``  -- maior sequencia literal compartilhada, em palavras.

Um n-grama de 8 palavras coincidindo por acaso e raro em texto natural; uma
sequencia de 15+ palavras e reproducao, nao coincidencia. Os limiares default
sao conservadores de proposito -- a penalidade de falso negativo (strike de
conteudo reutilizado no YouTube) e muito maior que a de falso positivo
(reescrever uma frase).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

logger = logging.getLogger("youtube_cloner.guardrails")

NGRAM_SIZE = 8
MAX_OVERLAP_RATIO = 0.02
MAX_LONGEST_MATCH = 14

_WORD = re.compile(r"[^\w\s]", re.UNICODE)


class OriginalityViolation(RuntimeError):
    """O roteiro gerado reproduz trechos literais da fonte."""


def normalize(text: str) -> list[str]:
    """Minusculas, sem acento, sem pontuacao -> lista de palavras.

    Normalizar acento e pontuacao evita que trocar uma virgula ou um acento
    faca um trecho copiado passar pelo detector.
    """
    folded = unicodedata.normalize("NFKD", text or "")
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = _WORD.sub(" ", folded.lower())
    return folded.split()


def ngrams(words: list[str], n: int = NGRAM_SIZE) -> set[tuple[str, ...]]:
    if len(words) < n:
        return set()
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def _longest_common_run(candidate: list[str], source: list[str]) -> int:
    """Maior subsequencia contigua comum, em palavras (DP com 1 linha)."""
    if not candidate or not source:
        return 0
    previous = [0] * (len(source) + 1)
    best = 0
    for i in range(1, len(candidate) + 1):
        current = [0] * (len(source) + 1)
        c_word = candidate[i - 1]
        for j in range(1, len(source) + 1):
            if c_word == source[j - 1]:
                current[j] = previous[j - 1] + 1
                if current[j] > best:
                    best = current[j]
        previous = current
    return best


@dataclass
class OriginalityReport:
    overlap_ratio: float
    longest_match: int
    colliding_samples: list[str] = field(default_factory=list)
    candidate_ngrams: int = 0
    passed: bool = True

    def to_dict(self) -> dict:
        return {
            "overlap_ratio": self.overlap_ratio,
            "longest_match_words": self.longest_match,
            "candidate_ngrams": self.candidate_ngrams,
            "colliding_samples": self.colliding_samples,
            "thresholds": {
                "max_overlap_ratio": MAX_OVERLAP_RATIO,
                "max_longest_match_words": MAX_LONGEST_MATCH,
            },
            "passed": self.passed,
        }


def check_originality(
    generated: str,
    sources: dict[str, str] | list[str],
    *,
    n: int = NGRAM_SIZE,
    max_overlap_ratio: float = MAX_OVERLAP_RATIO,
    max_longest_match: int = MAX_LONGEST_MATCH,
) -> OriginalityReport:
    """Compara o roteiro gerado com as transcricoes de origem."""
    corpus = list(sources.values()) if isinstance(sources, dict) else list(sources)

    cand_words = normalize(generated)
    cand_ngrams = ngrams(cand_words, n)
    if not cand_ngrams:
        return OriginalityReport(0.0, 0, [], 0, True)

    source_ngrams: set[tuple[str, ...]] = set()
    longest = 0
    for text in corpus:
        src_words = normalize(text)
        source_ngrams |= ngrams(src_words, n)
        longest = max(longest, _longest_common_run(cand_words, src_words))

    collisions = cand_ngrams & source_ngrams
    ratio = len(collisions) / len(cand_ngrams)
    samples = [" ".join(g) for g in list(collisions)[:10]]

    report = OriginalityReport(
        overlap_ratio=round(ratio, 4),
        longest_match=longest,
        colliding_samples=samples,
        candidate_ngrams=len(cand_ngrams),
        passed=ratio <= max_overlap_ratio and longest <= max_longest_match,
    )
    logger.info(
        "Originalidade: overlap=%.2f%% longest=%d palavras -> %s",
        ratio * 100,
        longest,
        "PASS" if report.passed else "FAIL",
    )
    return report


def enforce(generated: str, sources: dict[str, str] | list[str]) -> OriginalityReport:
    """Versao bloqueante. Levanta ``OriginalityViolation`` quando reprova."""
    report = check_originality(generated, sources)
    if not report.passed:
        raise OriginalityViolation(
            "Roteiro reprovado no gate de originalidade "
            f"(overlap {report.overlap_ratio:.2%}, maior trecho literal "
            f"{report.longest_match} palavras). Trechos colididos: "
            f"{report.colliding_samples[:3]}. "
            "Regenere o roteiro ou reforce o dossie de pesquisa."
        )
    return report
