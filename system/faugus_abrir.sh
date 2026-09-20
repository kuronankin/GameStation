#!/bin/bash

# ============================================================
# GameStation - faugus_abrir.sh
#
# Abre um jogo de PC (Faugus) que JÁ foi instalado antes — não
# checa nem extrai nada, só abre direto. Sem tela de carregamento
# em fullscreen — quem espera a janela aparecer e mostra progresso
# agora é o app.py (abrir_jogo_pc) do lado Python/interface.
# ============================================================

set -uo pipefail

if [ $# -lt 1 ]; then
    echo "Uso: faugus_abrir.sh <gameid>" >&2
    exit 1
fi

GAMEID="$1"

if command -v gamescope >/dev/null 2>&1; then
    exec gamescope -W 1920 -H 1080 -O 1920x1080 -S auto -f \
        -- faugus-launcher --game "$GAMEID"
else
    exec faugus-launcher --game "$GAMEID"
fi
