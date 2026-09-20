#!/bin/bash

# ============================================================
# GameStation - steam_uninstalar.sh
#
# Garante que a Steam já está rodando ANTES de mandar o comando de
# desinstalar — teoria (a confirmar na prática) é que
# "steam://uninstall/" sozinho, com a Steam ainda fechada, não
# funciona direito (a Steam nem tem tempo de processar o comando
# enquanto ainda está subindo).
# ============================================================

set -uo pipefail

if [ $# -lt 1 ]; then
    echo "Uso: steam_uninstalar.sh <appid>" >&2
    exit 1
fi

APPID="$1"

if ! pgrep -x "steam" >/dev/null 2>&1; then
    echo "GameStation: Steam ainda não está rodando — iniciando antes de desinstalar..."

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

    # Dá um tempo extra pro Steam terminar de carregar a biblioteca
    # antes de mandar o comando de desinstalar — subir o processo
    # não significa que já está pronto pra processar comandos.
    sleep 5
fi

echo "GameStation: enviando comando de desinstalar AppID $APPID..."
exec steam "steam://uninstall/$APPID"
