#!/bin/bash

# ============================================================
# GameStation - steam_abrir.sh
#
# Abre um jogo da Steam pelo AppID. Sem tela de carregamento em
# fullscreen — quem espera a janela aparecer e mostra progresso
# agora é o app.py (abrir_jogo_pc) do lado Python/interface.
#
# Garante que a Steam já está rodando ANTES de mandar o comando de
# abrir o jogo (senão "steam://run/" pode chegar cedo demais, com a
# Steam ainda inicializando) — envolve a Steam INTEIRA com gamescope
# na primeira vez, pra todo jogo lançado depois herdar o mesmo
# ambiente automaticamente (mesmo padrão do Steam Deck).
# ============================================================

set -uo pipefail

if [ $# -lt 1 ]; then
    echo "Uso: steam_abrir.sh <appid>" >&2
    exit 1
fi

APPID="$1"

if ! pgrep -x "steam" >/dev/null 2>&1; then
    echo "GameStation: Steam ainda não está rodando — iniciando..."

    if command -v gamescope >/dev/null 2>&1; then
        nohup gamescope -W 1920 -H 1080 -O 1920x1080 -S auto -f \
            -- steam -silent \
            >/dev/null 2>&1 &
    else
        nohup steam -silent >/dev/null 2>&1 &
    fi

    TEMPO=0
    while [ "$TEMPO" -lt 30 ]; do
        if pgrep -x "steam" >/dev/null 2>&1; then
            break
        fi
        sleep 1
        TEMPO=$((TEMPO + 1))
    done

    sleep 3
fi

echo "GameStation: iniciando Steam AppID $APPID..."
exec steam "steam://run/$APPID"
