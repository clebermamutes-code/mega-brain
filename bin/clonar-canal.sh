#!/usr/bin/env bash
# clonar-canal.sh -- assistente guiado do youtube_cloner.
#
# Feito para ser rodado por quem nao usa terminal no dia a dia: um comando so,
# verifica tudo antes de comecar, e explica em portugues o que fazer quando
# alguma coisa falta. Nada aqui e destrutivo -- so le, instala dependencia e
# grava dentro de artifacts/.
#
# Uso:
#   bash bin/clonar-canal.sh
#   bash bin/clonar-canal.sh --slug meu-projeto --videos caminho/da/lista.txt

set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

SLUG="livro-sagrado"
VIDEOS="engine/intelligence/youtube_cloner/samples/olivrosagrado.txt"

while [ $# -gt 0 ]; do
  case "$1" in
    --slug) SLUG="$2"; shift 2 ;;
    --videos) VIDEOS="$2"; shift 2 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "Opcao desconhecida: $1"; exit 1 ;;
  esac
done

titulo() { printf '\n\033[1m%s\033[0m\n' "$1"; }
ok()     { printf '  \033[32mOK\033[0m    %s\n' "$1"; }
erro()   { printf '  \033[31mFALTA\033[0m %s\n' "$1"; }
info()   { printf '        %s\n' "$1"; }

titulo "1/4  Conferindo o que voce ja tem"

PENDENCIAS=0

if command -v python3 >/dev/null 2>&1; then
  ok "Python $(python3 -c 'import sys;print(".".join(map(str,sys.version_info[:2])))')"
else
  erro "Python 3 nao encontrado"
  info "Instale em https://www.python.org/downloads/ e rode este script de novo."
  exit 1
fi

if python3 -c "import youtube_transcript_api" >/dev/null 2>&1; then
  ok "Biblioteca de transcricao instalada"
else
  info "Instalando a biblioteca de transcricao (leva alguns segundos)..."
  if python3 -m pip install --quiet youtube-transcript-api >/dev/null 2>&1; then
    ok "Biblioteca de transcricao instalada agora"
  else
    erro "Nao consegui instalar youtube-transcript-api"
    info "Tente manualmente: python3 -m pip install youtube-transcript-api"
    PENDENCIAS=1
  fi
fi

CHAVE_ENCONTRADA=""
for k in ANTHROPIC_API_KEY OPENAI_API_KEY GEMINI_API_KEY; do
  if grep -qE "^${k}=.+" .env 2>/dev/null; then CHAVE_ENCONTRADA="$k"; break; fi
done

if [ -n "$CHAVE_ENCONTRADA" ]; then
  ok "Chave de IA configurada ($CHAVE_ENCONTRADA)"
else
  erro "Nenhuma chave de IA no arquivo .env"
  info "O sistema precisa de UMA destas, qualquer uma serve:"
  info "  ANTHROPIC_API_KEY  ->  console.anthropic.com"
  info "  OPENAI_API_KEY     ->  platform.openai.com/api-keys"
  info "  GEMINI_API_KEY     ->  aistudio.google.com/apikey"
  info ""
  info "Depois de copiar a chave do site, abra o arquivo .env na raiz do projeto"
  info "e adicione uma linha assim (sem espacos em volta do =):"
  info "  ANTHROPIC_API_KEY=cole-a-chave-aqui"
  PENDENCIAS=1
fi

if [ -f "$VIDEOS" ]; then
  QTD=$(grep -cE 'youtube\.com|youtu\.be' "$VIDEOS" 2>/dev/null || echo 0)
  ok "Lista de videos encontrada ($QTD videos)"
else
  erro "Lista de videos nao encontrada: $VIDEOS"
  PENDENCIAS=1
fi

if [ "$PENDENCIAS" -ne 0 ]; then
  titulo "Parei aqui"
  echo "  Resolva o que esta marcado como FALTA acima e rode de novo:"
  echo "    bash bin/clonar-canal.sh"
  exit 1
fi

titulo "2/4  Baixando as transcricoes e extraindo o DNA"
info "Isso leva de 2 a 5 minutos. Pode deixar rodando."
echo

if ! python3 -m engine.intelligence.youtube_cloner.pipeline dna \
       --slug "$SLUG" --videos "$VIDEOS"; then
  titulo "Nao deu certo"
  echo "  Copie a mensagem de erro acima e me mande no chat que eu resolvo."
  exit 1
fi

DESTINO="artifacts/youtube-cloner/${SLUG}"

titulo "3/4  Pronto"
ok "DNA extraido"
info "Arquivo: ${DESTINO}/video-dna.json"

titulo "4/4  Proximo passo"
cat <<FIM
  Abra o arquivo abaixo e me mande o conteudo no chat:

    ${DESTINO}/video-dna.json

  Eu confiro se a extracao pegou a formula de verdade ou se veio generica
  (nesse caso a amostra precisa mudar antes de gastar geracao de roteiro).

  Para copiar o conteudo pelo terminal:
    cat ${DESTINO}/video-dna.json
FIM
