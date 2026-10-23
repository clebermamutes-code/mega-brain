# YouTube Cloner — Especificação de Pipeline

Modelagem estrutural de canais faceless do YouTube: descobre um canal modelo,
destila o DNA estrutural dos seus melhores vídeos e reemite esse DNA como
roteiro, camada visual e locução **originais** sobre um tema novo.

Origem: extração das fontes do NotebookLM (stack de ferramentas, pipeline
end-to-end, critérios de seleção, anatomia de roteiro, camadas visual/áudio,
regras éticas e heurísticas), convertida em contratos executáveis.

---

## 1. Onde vive

```
mega-brain/
└── engine/
    └── intelligence/
        └── youtube_cloner/
            ├── __init__.py          → exporta os contratos de dados
            ├── schemas.py           → ChannelModel, VideoDNA, ScriptDraft, ...
            ├── discovery.py         → Stage 1: YouTube Data API + filtros
            ├── transcripts.py       → Stage 2: coleta de transcrições
            ├── dna.py               → Stage 3: destilação do DNA
            ├── guardrails.py        → GATE: originalidade (bloqueante)
            ├── script.py            → Stage 4: geração de roteiro
            ├── visuals.py           → Stage 5: prompts de imagem/vídeo
            ├── voice.py             → Stage 6: locução (TTS)
            ├── edit_manifest.py     → Stage 7: timeline + render.sh
            ├── prompts.py           → todos os prompts, centralizados
            ├── llm.py               → adaptador sobre o llm_router do MCE
            ├── pipeline.py          → orquestrador CLI
            └── tests/
                └── test_guardrails.py
```

Saídas em `artifacts/youtube-cloner/{slug}/` (gitignored).

## 2. X-Ray

| Pergunta | Resposta |
|---|---|
| O que é | Pipeline de 7 estágios que converte um canal de referência em molde estrutural reutilizável |
| Onde vive | `engine/intelligence/youtube_cloner/` |
| A que se conecta | `engine/intelligence/pipeline/mce/llm_router.py` (LLM), YouTube Data API v3, ElevenLabs, ffmpeg |
| Quem dispara | `python3 -m engine.intelligence.youtube_cloner.pipeline <stage>` |
| O que tem dentro | 12 módulos Python (stdlib + o llm_router existente) |
| Formato dos artefatos | JSON por estágio, retomável entre sessões |
| O que quebra se apagar | Nada mais no repo depende dele — é aditivo, sem alterar o MCE |

## 3. Estágios

| # | Estágio | Input | Output | Determinístico? |
|---|---------|-------|--------|-----------------|
| 1 | `discover` | nicho (string) | `discovery/{query}.json` | Sim — filtros puros |
| 2 | (dentro de `dna`) | video_ids | `transcripts.json` | Sim — I/O |
| 3 | `dna` | transcrições | `video-dna.json` | Não — LLM |
| — | **gate originalidade** | roteiro + transcrições | `originality-report.json` | Sim — n-gramas |
| 4 | `script` | DNA + tema + dossiê | `script.json`, `narration.txt` | Não — LLM |
| 5 | `visuals` | roteiro + DNA | `image-prompts.json/.txt` | Não — LLM |
| 6 | `voice` | roteiro | `narration.mp3` | Não — TTS |
| 7 | `assemble` | roteiro + DNA + áudio | `edit-manifest.json`, `render.sh` | Sim — aritmética |

Cada estágio lê do disco e grava no disco: falha na 4 não obriga a repetir a 3
(nem a pagar o LLM de novo).

## 4. Filtros de seleção (Stage 1)

Valores default, extraídos das fontes:

| Filtro | Default | Origem |
|--------|---------|--------|
| Views mínimas | 10.000 | fontes |
| Idade máxima do vídeo | 190 dias | fontes |
| Duração mínima | 180s | bloqueio de Shorts |
| Duração máxima | 3.600s | limite prático |
| Ordenação | views/dia | derivada — separa "viral agora" de "acumulou em 3 anos" |

Na amostragem de DNA (`top_videos_of_channel`) o filtro de idade é
deliberadamente suspenso: a fórmula que funcionou há dois anos ainda ensina
estrutura. Só o piso de duração permanece.

## 5. O gate de originalidade

As fontes repetem que o processo é "modelar, nunca copiar", mas não oferecem
nenhum mecanismo de verificação — a garantia fica na intenção do operador.
Este pipeline transforma a regra em teste executável.

**Método:** sobreposição de n-gramas de 8 palavras entre o roteiro gerado e as
transcrições de origem, sobre texto normalizado (minúsculas, sem acento, sem
pontuação — para que trocar uma vírgula não drible o detector).

| Métrica | Limiar | Significado |
|---------|--------|-------------|
| `overlap_ratio` | ≤ 2% | fração dos n-gramas do roteiro que colidem com a fonte |
| `longest_match` | ≤ 14 palavras | maior sequência literal compartilhada |

Reprovar bloqueia o pipeline (`exit 2`) e grava `script-REPROVADO.json`. Os
limiares são conservadores de propósito: a penalidade de falso negativo (strike
de conteúdo reutilizado) é muito maior que a de falso positivo (reescrever uma
frase).

Duas defesas adicionais, antes do gate:
- O prompt de extração de DNA proíbe explicitamente conteúdo literal e exige
  `title_formulas` com placeholders (`O <NUMERO> <OBJETO> que <CONSEQUENCIA>`).
- `script._dna_summary()` omite `recurring_themes` do prompt de geração — o
  gerador recebe a forma do canal modelo, não os assuntos dele.

## 6. Intervenção humana

| Ponto | Por quê |
|-------|---------|
| Após `dna` | Ler o DNA. Se veio genérico, a amostra estava ruim — trocar antes de gastar geração |
| Antes de `script` | Montar o dossiê de pesquisa. Sem ele o pipeline se recusa a citar fatos |
| Após o gate | Se reprovou, decidir entre regenerar ou reforçar o dossiê |
| Após `visuals` | Aprovar o personagem-âncora antes de gerar dezenas de imagens |
| Geração de imagens | Manual, por design — ver seção 8 |

## 7. Modos de falha

| Estágio | Falha | Detecção | Fallback |
|---------|-------|----------|----------|
| discover | quota/chave da API | `DiscoveryError` com HTTP | usar `--channel` direto |
| transcripts | sem legenda | `TranscriptUnavailable` | 3 caminhos em cascata; vídeos sem legenda são pulados com WARN |
| dna | JSON malformado | `LLMOutputError` | `extract_json` tolera cercas e prosa |
| dna | DNA incompleto | validação de campos obrigatórios | erro explícito |
| script | roteiro fora do alvo | desvio > 35% no total de palavras | WARN + sugestão de ajuste |
| script | plágio | gate de originalidade | **bloqueio** |
| visuals | cena sem prompt | check por índice | fallback derivado da narração |
| voice | texto acima do limite | chunking por parágrafo | nunca corta no meio da frase |
| voice | sem ffmpeg | `shutil.which` | append binário + WARN |
| assemble | dessincronização áudio/vídeo | `ffprobe` mede o áudio real | timeline reescalado pelo fator real/estimado |

## 8. O gargalo honesto: a edição

O CapCut não tem API pública. Automatizar aquele passo específico só seria
possível dirigindo a UI via browser — frágil e quebra a cada update.

A saída aqui é dupla, e a escolha é do operador:

- `edit-manifest.json` — timeline declarativa com tempos já calculados, para
  montar no CapCut sem cronometrar no olho.
- `render.sh` — script ffmpeg que monta o vídeo sem editor nenhum, a partir de
  assets numerados (`001.png`, `002.png`, ...).

A geração de imagens também fica fora do código: Google Flow, Leonardo e
similares não têm API estável o bastante para valer o acoplamento. O pipeline
entrega os prompts em `image-prompts.txt`, um por linha e numerados, no formato
que as ferramentas de geração em lote esperam receber.

As regras de mixagem das fontes estão codificadas no manifesto:
`clip_native_gain_db = -60` (áudio nativo dos clipes de IA a zero) e
`background_music_gain_db = -22` (trilha como suporte, não concorrente da voz).

## 9. Métricas por vídeo

Para saber se o molde funciona — e não só se o pipeline rodou:

| Métrica | Onde | Sinal |
|---------|------|-------|
| `overlap_ratio` | `originality-report.json` | risco de strike |
| cortes por minuto | `edit-manifest.json` | densidade visual vs. o canal modelo |
| palavras vs. alvo | log da Stage 4 | aderência à duração |
| retenção aos 30s | YouTube Analytics | o gancho pegou? |
| CTR da thumbnail | YouTube Analytics | a capa pegou? |

A heurística das fontes — 30 a 60 dias sem resultado expressivo significa parar
e reler as métricas em vez de continuar publicando — depende das duas últimas
linhas, que só existem depois da publicação.

## 10. Uso

```bash
# 1. Achar candidatos num nicho
python3 -m engine.intelligence.youtube_cloner.pipeline discover \
  --query "estoicismo pratico" --min-views 10000 --max-age-days 190

# 2. Extrair o DNA de um canal escolhido
python3 -m engine.intelligence.youtube_cloner.pipeline dna \
  --channel "@nomedocanal" --slug meu-projeto

# 3. Gerar roteiro (com dossiê de fatos verificados)
python3 -m engine.intelligence.youtube_cloner.pipeline script \
  --slug meu-projeto --topic "Por que adiamos o que importa" \
  --dossier pesquisa.md --duration 8

# 4-6. Visual, voz, montagem
python3 -m engine.intelligence.youtube_cloner.pipeline visuals --slug meu-projeto
python3 -m engine.intelligence.youtube_cloner.pipeline voice --slug meu-projeto --voice-id <id>
python3 -m engine.intelligence.youtube_cloner.pipeline assemble --slug meu-projeto

# Ou tudo de uma vez
python3 -m engine.intelligence.youtube_cloner.pipeline full \
  --channel "@nomedocanal" --slug meu-projeto --topic "..." --voice-id <id>
```

Credenciais (todas opcionais, cada uma habilita um estágio):
`YOUTUBE_API_KEY`, `ANTHROPIC_API_KEY` (ou `OPENAI_API_KEY`/`GEMINI_API_KEY`
via `llm_router`), `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`.

Testes: `python3 -m engine.intelligence.youtube_cloner.tests.test_guardrails`

## 11. Analogia

O canal modelo é um concorrente cujo processo comercial funciona. O DNA é o
**playbook de vendas** dele — a estrutura da abordagem, a ordem das objeções, o
ritmo do fechamento. Você pode adotar o playbook; não pode usar a carteira de
clientes nem o pitch decorado palavra por palavra. O gate de originalidade é o
jurídico conferindo, antes de cada proposta sair, que você levou o método e não
o material.

## 12. Lacunas conhecidas

Herdadas do extrato de fontes, não resolvidas aqui:

- Cadastro e configuração fiscal do AdSense
- SEO/metadados do YouTube (tags e descrição saem do LLM, sem otimização orgânica)
- Correção de defeitos de geração de imagem (mãos, texto, distorções)
- Licenciamento de trilha e SFX — o manifesto reserva a faixa, não fornece o áudio
- Upload automatizado (a YouTube Data API suporta; não implementado)
