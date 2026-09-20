#!/bin/bash

# ============================================================
# GameStation - uninstall-launch.sh (adaptado pro app nativo)
#
# Handler central para desinstalação de jogos.
#
# Recebe:
#
#   caminho do Uninstall.sh
#
# Fluxo:
#
#   tela de desinstalação
#        ↓
#   executa Uninstall.sh
#        ↓
#   regenera dados.json (o app detecta sozinho via polling e some
#   com o jogo removido da lista de Uninstall)
#        ↓
#   fecha tela de desinstalação
#
# DIFERENÇA da versão ES-DE: NÃO fecha nem reabre o frontend mais —
# nosso app nativo fica rodando o tempo todo, só o dados.json muda.
# ============================================================

set -uo pipefail


# ============================================================
# Configuração
# ============================================================

LIB_DIR="/mnt/GameStation/system"

UNINSTALL_BACKGROUND="/mnt/GameStation/system/uninstall-loading.png"


# ============================================================
# Biblioteca comum
# ============================================================

source "$LIB_DIR/common_play.sh"


# ============================================================
# Verificação
# ============================================================

if [ $# -ne 1 ]; then

    echo "Uso: uninstall-launch.sh <caminho-do-Uninstall.sh>" >&2

    exit 1

fi


UNINSTALL_SCRIPT="$1"


if [ ! -f "$UNINSTALL_SCRIPT" ]; then

    echo "ERRO: Uninstall.sh não encontrado:"
    echo "$UNINSTALL_SCRIPT" >&2

    exit 1

fi


# ============================================================
# Limpeza
# ============================================================

limpar() {

    limpar_tela_carregamento

}


trap limpar EXIT


# ============================================================
# Inicia tela de desinstalação
# ============================================================

iniciar_tela_carregamento "$UNINSTALL_BACKGROUND"


# ============================================================
# Executa a desinstalação real
#
# A variável abaixo impede que o Uninstall.sh chame
# novamente este handler.
# ============================================================

echo "GameStation: desinstalando jogo..."

GAMESTATION_UNINSTALL_RUNNING=1 \
    bash "$UNINSTALL_SCRIPT"


STATUS_DESINSTALACAO=$?


# ============================================================
# Verifica resultado
# ============================================================

if [ "$STATUS_DESINSTALACAO" -ne 0 ]; then

    echo "GameStation: a desinstalação terminou com erro." >&2

    exit "$STATUS_DESINSTALACAO"

fi


# ============================================================
# Regenera dados.json — o app detecta sozinho via polling e
# atualiza a tela, removendo o jogo desinstalado da lista.
# ============================================================

echo "GameStation: atualizando lista..."

python3 "$LIB_DIR/gerar-dados.py" >/dev/null 2>&1 || true


# ============================================================
# Final
#
# O trap limpar() fechará a tela de carregamento.
# ============================================================

exit 0
