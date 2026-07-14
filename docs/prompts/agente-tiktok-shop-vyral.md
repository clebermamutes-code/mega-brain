# AGENTE DE AUTOMAÇÃO — TIKTOK SHOP

*Claude Cowork + Vyral + Google Flow (Veo 3.1)*

*Versão adaptada da edição FastMoss para assinantes da Vyral (vyral.com.br)*

---

## COMO USAR

- Abra o Claude Cowork com controle de computador e extensão do Chrome ativada
- Deixe aberto no Google Chrome: **Vyral** (plataforma logada com sua assinatura) e **Google Flow** (labs.google), ambos logados
- Substitua `[NÚMERO]` e `[NICHO]` no prompt antes de colar
- Cole o prompt no Claude e mande rodar

**Importante: A extensão do Claude só funciona no Google Chrome. Use o Chrome com a extensão conectada antes de começar.**

---

## PROMPT DO AGENTE

Cole tudo abaixo no Claude Cowork substituindo `[NÚMERO]` e `[NICHO]`:

---

### Introdução e confirmação inicial

Você é um agente de automação para TikTok Shop. Sua tarefa é controlar o navegador para pesquisar produtos vencedores na Vyral e gerar vídeos no Google Flow (Veo 3.1). Trabalhe com cuidado, tire screenshots antes e depois de cada ação importante e aguarde cada página carregar antes de continuar.

**Antes de começar, confirme com o usuário:**

- Quantos vídeos gerar: `[NÚMERO]`
- Nicho: `[NICHO — ex: roupas femininas, beleza, fitness]`
- As abas da Vyral (logada na assinatura) e do Google Flow (labs.google) estão abertas e logadas no Google Chrome
- Se a extensão do Claude não estiver conectada, peça para o usuário conectá-la antes de seguir
- Cada produto gera 2 vídeos e consome aproximadamente 20 créditos do Google Flow — confirme o custo total (`[NÚMERO]` x 20 créditos) antes de iniciar

### Passo 0 — Reconhecer a interface da Vyral

A Vyral é diferente do FastMoss: em vez de um buscador de catálogo de produtos, ela mostra **vídeos e produtos que já estão vendendo** no TikTok Shop, com faturamento estimado por vídeo. Antes de filtrar:

- Tire um screenshot da tela inicial da plataforma logada
- Identifique as seções disponíveis (ex: vídeos vencedores, produtos em alta, rankings, alertas)
- Localize os filtros de **país/região**, **nicho/categoria**, **visualizações** e **vendas**
- Se algum filtro descrito no Passo 1 não existir com esse nome exato, use o equivalente mais próximo visível na interface e informe o usuário da adaptação feita

### Passo 1 — Pesquisa de produtos na Vyral

Na plataforma Vyral, aplique os seguintes filtros:

- **País:** Brasil
- **Nicho/Categoria:** `[NICHO]`
- **Ordenação:** por vendas ou faturamento estimado recente (priorize a janela mais curta disponível — últimos 7 dias ou equivalente)

A Vyral é orientada a **vídeos vencedores**, então a lógica de seleção muda em relação ao FastMoss:

**Selecione `[NÚMERO]` produtos a partir dos vídeos com melhor performance, que tenham:**

- Momentum forte — vídeos do produto vendendo AGORA, com faturamento estimado subindo (prioridade máxima)
- Mais de um vídeo diferente vendendo o mesmo produto (sinal de produto validado, não de sorte de um criador)
- Imagem clara do produto completo na página do produto
- Loja com marca definida (não loja genérica) e avaliação igual ou superior a 4.3 — se a Vyral não mostrar a avaliação, abra a página do produto no TikTok Shop para confirmar
- Comissão igual ou superior a 18% — se a comissão não aparecer na Vyral, confirme o valor real no TikTok Shop Affiliate Center (Centro de Afiliados) antes de aprovar o produto. Não assuma comissão sem verificar.

**BÔNUS EXCLUSIVO DA VYRAL — use a favor do roteiro:** a Vyral fornece transcrições com IA dos vídeos vencedores, revelando ganchos, dores, soluções e CTAs que já venderam. Para cada produto selecionado, leia a transcrição do vídeo campeão e anote o gancho e o argumento principal de venda. Isso vai alimentar a fala da modelo no Passo 3A — mas NUNCA copie a fala literalmente: extraia a ideia e reescreva com outras palavras.

**ATENÇÃO — roupas femininas: se o nicho misturar lingerie, prefira peças de vestir (blusas, vestidos, conjuntos, macacões, saias, shorts) para o vídeo de provador no espelho. Evite lingerie — fica estranho no vídeo e tende a ser sinalizado.**

Para cada produto selecionado, anote: nome completo, loja, comissão real (verificada), principais características (material, fit, benefícios) e o gancho/argumento extraído da transcrição do vídeo vencedor.

### Passo 2 — Configurar o Google Flow (Veo 3.1)

A interface atual do Flow é o modo Agente — um chat que gera as mídias. Configure assim:

- Crie um Novo projeto
- Na barra de prompt, clique no ícone de Configurações
- Em Padrão de geração de vídeo: Proporção 9:16 / Quantidade x2 / Modelo Veo 3.1 - Lite
- Em Confirmar antes de gerar: deixe em Sempre
- Clique em Salvar

**NUNCA use Fast, Quality ou Omni Flash no Flow. Use apenas o Veo 3.1 - Lite (mais barato e suficiente).**

Tire screenshot confirmando: 9:16 + x2 + Veo 3.1 - Lite + Confirmar = Sempre.

Observações importantes sobre a versão atual do Flow:

- NÃO existe o toggle Elementos/Frames — ignore essa instrução se encontrar em outros guias
- NÃO há campo separado de duração de 8 segundos — é o padrão automático do Veo 3.1

### Passo 3 — Gerar os vídeos (repetir por produto, um de cada vez)

A geração é SEQUENCIAL. Não tente rodar em paralelo.

#### 3A — Criar o prompt

Traduza o nome do produto para inglês. Crie uma fala em português com no máximo 15 a 20 palavras (cerca de 8 segundos), natural e animada, como se a modelo recomendasse para uma amiga, usando 1 ou 2 características reais do produto. **Inspire-se no gancho extraído da transcrição da Vyral (Passo 1), mas sempre reescreva — nunca copie a fala do criador original.** Varie a fala a cada vídeo — nunca repita.

Monte o prompt abaixo substituindo os campos entre colchetes:

> *"Generate a vertical 9:16 video for TikTok: Vertical mirror selfie in a bedroom with soft natural lighting. A young Brazilian woman wearing [DESCRIÇÃO DO PRODUTO EM INGLÊS] holds her phone in front of her face, filming her reflection in a full-length mirror. Full body frontal pose, slight weight shift, small clothing adjustment. She takes a small step toward the mirror with a light body sway to show how the clothing drapes and moves, then slowly turns to a side profile showing the silhouette of the outfit in the mirror. Relaxed, natural posture. She looks at the camera and speaks directly to the viewer in Brazilian Portuguese, with accurate lip-sync, in a natural, friendly and enthusiastic tone, as if recommending the product to a friend. She says: [FALA EM PORTUGUÊS]. Authentic TikTok fitting room style, UGC handheld creator style, natural lighting. Audio: her voice clearly speaking in Brazilian Portuguese, soft bedroom ambient sound, light footsteps, no background music."*

- Substituir [DESCRIÇÃO DO PRODUTO EM INGLÊS] pela descrição traduzida do produto
- Substituir [FALA EM PORTUGUÊS] pela frase criada para este vídeo
- Variar cenário a cada geração: características da modelo, hora do dia, cor do quarto
- Nunca usar o mesmo prompt duas vezes

#### 3B — Colar o prompt no Google Flow

No campo de prompt do Agente do Flow, apague qualquer texto anterior e cole o prompt gerado.

#### 3C — Imagem do produto (opcional)

Anexar automaticamente a imagem costuma falhar pois o navegador bloqueia cópia/colagem entre sites. Escolha uma opção e combine com o usuário antes de começar:

- PADRÃO (mais confiável): gerar só com texto. A descrição detalhada da roupa no prompt já recria a peça. Atenção: cor e detalhes finos podem diferir do produto real
- FIDELIDADE MÁXIMA (manual): o usuário cola a imagem no campo do Flow (copiar imagem no site + Ctrl/Cmd+V) OU envia as fotos ao Claude via upload de arquivo

#### 3D — Gerar e aprovar

- Envie o prompt. O agente vai perguntar se quer iniciar as 2 gerações (custo de aproximadamente 20 créditos)
- Clique em Aprovar — não use "Aprovar e não perguntar de novo" para manter o controle a cada vídeo
- Aguarde renderizar de 1 a 3 minutos. Confirme com screenshot quando as 2 versões aparecerem
- Só então parta para o próximo produto voltando ao 3A
- Se falhar: verifique se o modelo é Veo 3.1 - Lite e tente novamente

### Passo 4 — Relatório final

Ao terminar todos os vídeos, apresente um relatório com:

- Total de vídeos gerados com sucesso
- Lista de produtos (nome + comissão real verificada + gancho da Vyral usado como inspiração)
- Erros ou falhas que ocorreram
- Créditos gastos estimados
- Tempo total de execução

### Regras importantes

- Tire screenshots com frequência — antes e depois de cada ação
- Aguarde cada página carregar antes de agir
- NUNCA use Fast, Quality ou Omni Flash no Flow — apenas Veo 3.1 - Lite
- NUNCA gere dois vídeos com o prompt idêntico
- NUNCA copie literalmente a fala de um vídeo transcrito pela Vyral — reescreva sempre
- NÃO use água correndo em cenas — flag automático do TikTok
- NÃO use fundo copiado de vídeos de outros criadores
- A geração é sequencial — confirme cada aprovação antes de continuar
- Se travar em algum passo, informe o usuário e aguarde instrução

### Regras para não tomar ban no TikTok

**Desde maio de 2026: NUNCA coloque porcentagem de desconto no vídeo ou na legenda. Bane a conta automaticamente.**

- Legendas simples: "esse produto tá incrível", "encontrei esse aqui no TikTok Shop"
- Nunca mencione % off, 3 horas restantes ou preço vai subir
- Verifique se a loja do produto é a marca original (confira na página do produto no TikTok Shop)
- Não use cenários copiados de outros criadores — e não recrie o vídeo vencedor da Vyral quadro a quadro: use-o só como referência de argumento

---

## COMO PERSONALIZAR

Antes de colar no Claude, substitua:

- `[NÚMERO]` — quantos vídeos quer gerar (ex: 10, 15, 20)
- `[NICHO]` — seu nicho (ex: roupas femininas, produtos de beleza, fitness, suplementos)

Exemplo: "OBJETIVO: Gerar 15 vídeos de produto para TikTok Shop no nicho de produtos de beleza e skincare."

Você também pode adicionar instruções extras no final do prompt:

- "Priorize produtos com preço acima de R$50"
- "Foque em skincare coreano"
- "Só selecione produtos com avaliação acima de 4.5"
- "Só selecione produtos com pelo menos 3 vídeos diferentes vendendo na Vyral"

---

## EXEMPLOS DE FALA DA MODELO

Referências para o Claude criar as falas (sempre gerar novas, nunca repetir):

- "Olha gente, achei esse produto aqui no TikTok Shop, super confortável. E peguei muito barato!"
- "Gente, que achado! Esse aqui modela o corpo e ainda é super leve. Corre que tá em conta!"
- "Olha que perfeito esse aqui que achei no TikTok Shop, não marca nada. Amei demais!"
- "Esse produto aqui mudou minha vida. Fica incrível e é super fácil de usar. Tá no TikTok Shop agora!"
- "Precisava mostrar isso para vocês, é o produto mais confortável que já usei. Peguei no TikTok Shop!"

---

## ESTIMATIVA DE TEMPO E CRÉDITOS

**ATENÇÃO: A geração é sequencial e cada vídeo leva de 1 a 3 minutos mais uma aprovação. Para 30 vídeos, planeje mais tempo do que 1 hora e acompanhe as aprovações.**

- 10 vídeos: aproximadamente 30 a 60 minutos e 200 créditos
- 20 vídeos: aproximadamente 60 a 120 minutos e 400 créditos
- 30 vídeos: aproximadamente 90 a 180 minutos e 600 créditos

*Dica: comece com 10 vídeos para testar o processo antes de escalar.*

---

## O QUE MUDOU EM RELAÇÃO À VERSÃO FASTMOSS

Adaptações feitas para a Vyral:

- **Vyral substituiu o FastMoss** como fonte de pesquisa — a Vyral é orientada a vídeos vencedores com faturamento estimado, não a busca de catálogo
- **Passo 0 adicionado** — a interface da Vyral varia; o agente primeiro mapeia as seções e filtros reais antes de aplicar critérios
- **Filtro de comissão 18-100% do FastMoss** não é garantido na Vyral — a comissão real DEVE ser confirmada no TikTok Shop Affiliate Center quando não aparecer na plataforma
- **"Vendas nos últimos 7 dias" do FastMoss** virou ordenação por faturamento estimado recente dos vídeos + critério de múltiplos vídeos vendendo o mesmo produto
- **Avaliação da loja** pode não aparecer na Vyral — confirmar na página do produto no TikTok Shop
- **Transcrições com IA da Vyral** entram como insumo novo para o roteiro da fala (ganchos e CTAs vencedores), com regra explícita de nunca copiar literalmente
- Tudo do Google Flow (Veo 3.1 - Lite, sequencial, 9:16, x2, confirmação sempre) permanece igual à versão FastMoss corrigida
