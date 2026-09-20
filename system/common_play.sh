#!/bin/bash

# ============================================================
# GameStation - common_play.sh (adaptado pro app nativo)
#
# Biblioteca comum para as telas de carregamento do GameStation.
#
# Imagem padrão:
#
#   /mnt/GameStation/system/loading.png
#
# A função iniciar_tela_carregamento pode receber uma imagem
# diferente como argumento.
#
# Exemplo:
#
#   iniciar_tela_carregamento
#
# usa loading.png
#
#   iniciar_tela_carregamento "/mnt/GameStation/system/uninstall-loading.png"
#
# usa uninstall-loading.png
#
# DIFERENÇA da versão ES-DE: NÃO fecha mais o frontend aqui — nosso
# app nativo fica rodando o tempo todo (é uma janela pywebview, não
# algo que precise ser morto/reaberto pra "atualizar"). A tela de
# carregamento só cobre visualmente por cima enquanto o processo
# roda; quem precisar recarregar dados chama o gerar-dados.py
# separadamente (o próprio app detecta sozinho via polling).
# ============================================================

ZENITY_PID=""
FEH_PID=""
LOADING_PID=""

GAMESTATION_LOADING_SCRIPT="/mnt/GameStation/system/gamestation-loading.py"


# ============================================================
# Inicia tela de carregamento
# ============================================================

iniciar_tela_carregamento() {

    local IMAGEM="${1:-/mnt/GameStation/system/loading.png}"


    if [ ! -f "$IMAGEM" ]; then

        echo "AVISO: imagem de carregamento não encontrada:"
        echo "$IMAGEM" >&2

        return 0

    fi


    if [ ! -f "$GAMESTATION_LOADING_SCRIPT" ]; then

        echo "AVISO: script de carregamento não encontrado:"
        echo "$GAMESTATION_LOADING_SCRIPT" >&2

        return 0

    fi


    python3 \
        "$GAMESTATION_LOADING_SCRIPT" \
        "$IMAGEM" \
        >/dev/null 2>&1 &

    LOADING_PID=$!


    sleep 1

}


# ============================================================
# Fecha tela de carregamento
# ============================================================

limpar_tela_carregamento() {

    if [ -n "${LOADING_PID:-}" ]; then

        kill "$LOADING_PID" 2>/dev/null || true

        LOADING_PID=""

    fi


    sleep 0.2


    pkill -f "gamestation-loading.py" 2>/dev/null || true

}


# ============================================================
# Captura as janelas atualmente existentes
# ============================================================

capturar_janelas() {

    if command -v wmctrl >/dev/null 2>&1; then

        wmctrl -l \
            2>/dev/null |
            awk '{print $1}'

        return 0

    fi


    if command -v xdotool >/dev/null 2>&1; then

        xdotool search --onlyvisible --name ".*" \
            2>/dev/null

        return 0

    fi


    return 0
}


# ============================================================
# Verifica se existe uma janela nova
# ============================================================

existe_janela_nova() {

    local JANELAS_ANTES="$1"

    local JANELA=""
    local NOVA=0


    if command -v wmctrl >/dev/null 2>&1; then

        while read -r JANELA; do

            [ -z "$JANELA" ] && continue


            if ! echo "$JANELAS_ANTES" |
               grep -Fxq "$JANELA"; then

                NOVA=1

                break

            fi

        done < <(
            wmctrl -l 2>/dev/null |
            awk '{print $1}'
        )

    fi


    if [ "$NOVA" -eq 1 ]; then

        return 0

    fi


    return 1
}


# ============================================================
# Espera uma nova janela gráfica
# ============================================================

esperar_janela_do_jogo() {

    local JANELAS_ANTES="$1"

    local LIMITE="${2:-180}"

    local TEMPO=0


    if ! command -v wmctrl >/dev/null 2>&1; then

        echo "AVISO: wmctrl não está instalado." >&2

        return 1

    fi


    while [ "$TEMPO" -lt "$LIMITE" ]; do

        if existe_janela_nova "$JANELAS_ANTES"; then

            return 0

        fi


        sleep 1

        TEMPO=$((TEMPO + 1))

    done


    return 1
}
