"""Perfis de nicho -- parametros que mudam por vertical, nao por projeto.

Um perfil carrega o que o DNA extraido do canal modelo NAO cobre: exigencias
factuais, restricoes de conteudo e ajustes de voz/visual que vem do nicho e nao
do canal. Dois canais diferentes de narrativa biblica compartilham o mesmo
perfil; o DNA de cada um continua sendo extraido separadamente.

O campo mais importante e ``requires_dossier``. Em nichos onde o publico
verifica a afirmacao (biblico, historico, true crime, saude), gerar roteiro sem
dossie de pesquisa produz citacao inventada -- e citacao inventada nesses nichos
custa o canal, nao so o video.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("youtube_cloner.profiles")

PROFILES_DIR = Path(__file__).parent / "profiles"


@dataclass
class NicheProfile:
    """Restricoes e ajustes que vem do nicho, nao do canal modelo."""

    name: str
    description: str = ""
    requires_dossier: bool = False
    dossier_rationale: str = ""
    forbidden_claims: list[str] = field(default_factory=list)
    content_rules: list[str] = field(default_factory=list)
    voice_hint: str = ""
    visual_hint: str = ""
    recommended_languages: list[str] = field(default_factory=list)
    monetization_notes: list[str] = field(default_factory=list)

    def prompt_block(self) -> str:
        """Bloco injetado no prompt de geracao de roteiro."""
        lines = [f"RESTRICOES DO NICHO ({self.name}):"]
        for rule in self.content_rules:
            lines.append(f"- {rule}")
        if self.forbidden_claims:
            lines.append("")
            lines.append("E PROIBIDO afirmar sem respaldo explicito no dossie:")
            for claim in self.forbidden_claims:
                lines.append(f"- {claim}")
        return "\n".join(lines)


def load(name: str) -> NicheProfile:
    """Carrega um perfil por nome (arquivo YAML em ``profiles/``)."""
    path = PROFILES_DIR / f"{name}.yaml"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in PROFILES_DIR.glob("*.yaml"))) or "nenhum"
        raise FileNotFoundError(
            f"Perfil {name!r} nao encontrado em {PROFILES_DIR}. Disponiveis: {available}"
        )
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise ImportError("PyYAML necessario para carregar perfis de nicho.") from exc

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    payload = {k: v for k, v in data.items() if k in NicheProfile.__dataclass_fields__}
    payload.setdefault("name", name)
    return NicheProfile(**payload)


def available() -> list[str]:
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yaml"))
