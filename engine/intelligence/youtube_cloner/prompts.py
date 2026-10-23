"""Prompts do pipeline, centralizados.

Todos os prompts vivem aqui (e nao inline nos estagios) por dois motivos:
sao o parametro mais ajustado do sistema, e precisam ser auditaveis em bloco
quando o guardrail de originalidade reprova uma geracao.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Stage 3 -- destilacao de DNA
# --------------------------------------------------------------------------

DNA_EXTRACTION = """Voce e um analista de engenharia reversa de canais do YouTube.

Recebe abaixo {n} transcricoes dos videos de maior performance de um mesmo canal.
Sua tarefa e destilar a FORMULA ESTRUTURAL compartilhada por eles.

REGRA ABSOLUTA DE SAIDA:
Descreva PADROES, nunca conteudo. E proibido copiar frases, nomes proprios,
dados, exemplos ou qualquer trecho literal das transcricoes. Se voce se pegar
citando, reescreva como descricao abstrata do padrao.
  RUIM:  hook_pattern = "Em 1943, um submarino alemao desapareceu no Atlantico"
  BOM:   hook_pattern = "Abre com um fato historico datado e nao resolvido,
          apresentado como anomalia, antes de qualquer contexto"

Responda SOMENTE com um objeto JSON valido, sem cercas de codigo, no formato:

{{
  "audience": "quem assiste, em uma frase",
  "hook_pattern": "estrutura dos primeiros 30s, abstrata",
  "hook_seconds": 30,
  "body_architecture": ["bloco 1", "bloco 2", "bloco 3"],
  "tension_rhythm": "como tensao sobe e alivia ao longo do video",
  "cta_pattern": "como o video fecha",
  "words_per_minute": 150,
  "target_duration_minutes": 8.0,
  "seconds_per_visual": [1, 3],
  "visual_style": "estetica dominante em uma frase",
  "voice_profile": "tom, energia e ritmo da narracao",
  "title_formulas": ["esqueleto de titulo com <PLACEHOLDERS>", "..."],
  "thumbnail_composition": "composicao tipica da capa",
  "recurring_themes": ["tema", "..."],
  "notes": ["observacao relevante que nao coube nos campos acima"]
}}

Em "title_formulas" use PLACEHOLDERS em maiusculas para as partes variaveis
(ex: "O <NUMERO> <OBJETO> que <CONSEQUENCIA_INESPERADA>"). Nunca titulos reais.

TRANSCRICOES:
{corpus}
"""


# --------------------------------------------------------------------------
# Stage 4 -- geracao de roteiro
# --------------------------------------------------------------------------

SCRIPT_GENERATION = """Voce escreve roteiros para um canal faceless do YouTube.

Voce recebe (a) o DNA ESTRUTURAL de um canal de referencia e (b) um TEMA NOVO.
Escreva um roteiro ORIGINAL sobre o tema novo que siga a estrutura do DNA.

DNA ESTRUTURAL:
{dna}

TEMA NOVO: {topic}
IDIOMA DE SAIDA: {language}
DURACAO ALVO: {duration} minutos a ~{wpm} palavras/minuto
 => aproximadamente {target_words} palavras no total.

{dossier_block}

RESTRICOES NAO-NEGOCIAVEIS:
1. Reuso de ESTRUTURA apenas. Zero frases, exemplos ou dados do canal original.
2. Toda afirmacao factual deve vir do dossie de pesquisa acima. Se o dossie nao
   cobre um ponto, escreva o roteiro sem esse ponto -- nunca invente numero,
   data, estudo ou citacao.
3. Cada cena cobre 8 a 12 segundos de narracao (~{words_per_scene} palavras).
4. A narracao e para ser LIDA EM VOZ ALTA: frases curtas, sem marcadores, sem
   titulos de secao, sem emoji, sem texto entre parenteses.

Responda SOMENTE com JSON valido, sem cercas de codigo:

{{
  "titles": ["10 titulos seguindo as title_formulas do DNA"],
  "hook": "texto dos primeiros 30 segundos",
  "scenes": [
    {{"index": 1, "narration": "...", "image_prompt": "", "video_prompt": ""}}
  ],
  "cta": "fechamento",
  "description": "descricao do video para o YouTube",
  "tags": ["tag", "..."],
  "thumbnail_concept": "descricao da capa"
}}
"""

DOSSIER_BLOCK = """DOSSIE DE PESQUISA (unica fonte factual permitida):
{dossier}
"""

DOSSIER_MISSING = """DOSSIE DE PESQUISA: nao fornecido.
Portanto: escreva o roteiro em registro conceitual/analitico. E PROIBIDO citar
datas, numeros, estudos, nomes de pessoas reais ou eventos especificos.
"""


# --------------------------------------------------------------------------
# Stage 5 -- camada visual
# --------------------------------------------------------------------------

VISUAL_PROMPTS = """Voce dirige a arte de um video faceless do YouTube.

ESTILO VISUAL ALVO (destilado do canal de referencia):
{visual_style}

Gere prompts de imagem em INGLES para as cenas abaixo. Requisitos:
- Um prompt por cena, na mesma ordem, cobrindo o que a narracao descreve.
- Consistencia: todas as cenas partilham o mesmo personagem-ancora e o mesmo
  mundo. Descreva o personagem por completo em "character_reference_prompt";
  nas cenas, refira-se a ele de forma consistente e repita os tracos fisicos.
- Proporcao {aspect_ratio}, sem texto renderizado na imagem, sem marca d'agua.
- "video_prompt" descreve UM movimento de camera ou acao sutil de ~6 segundos.

Responda SOMENTE com JSON valido, sem cercas de codigo:

{{
  "character_reference_prompt": "descricao completa do personagem-ancora",
  "style_suffix": "sufixo de estilo repetido em todos os prompts",
  "prompts": [
    {{"index": 1, "image_prompt": "...", "video_prompt": "..."}}
  ]
}}

CENAS:
{scenes}
"""
