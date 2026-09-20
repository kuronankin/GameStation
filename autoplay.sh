#!/bin/bash
# autoplay.sh - GameStation (app nativo)
#
# Detecta disco/pendrive inserido, espelha cada subpasta de "sistema"
# encontrada na mídia pra dentro de games/disc-loader/<sistema>/
# (link simbólico), regenera o dados.json, e FECHA+REABRE o app.py —
# igual o comportamento de sempre da época do ES-DE. Ao remover a
# mídia, o mesmo acontece: fecha, atualiza a lista, reabre.
#
# A presença de um .desktop na mídia é só o SINAL de "isso é um
# disco/pendrive do GameStation" — não lemos nem rodamos o que está
# escrito no Exec= dele. Isso deixa discos ANTIGOS (gravados na época
# do ES-DE, com Exec= apontando pra coisa que não existe mais aqui)
# funcionando igual aos novos: sempre abrimos nosso próprio app.py
# com o mesmo comando fixo, não importa o que o .desktop diga.

GAMESTATION_DIR="/mnt/GameStation"
GAMES_DIR="$GAMESTATION_DIR/games"
DISC_LOADER_DIR="$GAMES_DIR/disc-loader"
LIB_DIR="$GAMESTATION_DIR/system"

COMANDO_APP="python3 $GAMESTATION_DIR/app.py"

# Nomes que nunca são espelhados, mesmo se a mídia tiver uma pasta
# com esse nome — são reservados pra nossa própria estrutura interna.
NOMES_RESERVADOS=("ssd" "disc-loader" "uninstall")

REFRESH_BACKGROUND="$LIB_DIR/refresh.png"

ULTIMO_ESTADO="vazio"
ARQUIVO_LINKS_ATIVOS="/tmp/gamestation_links_ativos.txt"

sleep 3

[ ! -d "$DISC_LOADER_DIR" ] && mkdir -p "$DISC_LOADER_DIR"

source "$LIB_DIR/common_play.sh"
LOADING_PID=""

eh_nome_reservado() {
    local nome="$1"
    for reservado in "${NOMES_RESERVADOS[@]}"; do
        [ "$nome" = "$reservado" ] && return 0
    done
    return 1
}

regenerar_dados() {
    python3 "$LIB_DIR/gerar-dados.py" >/dev/null 2>&1 || true
}

matar_app() {
    pkill -f "python3.*app\.py" 2>/dev/null || true
    sleep 1
}

abrir_app() {
    local janelas_antes
    janelas_antes="$(capturar_janelas)"

    (sh -c "$COMANDO_APP" &)

    # Espera a janela de verdade aparecer (até 30s) antes de devolver
    # o controle — evita fechar a tela de loading cedo demais,
    # enquanto o app ainda está inicializando (pywebview + carregar
    # dados.json demora mais que um tempo fixo arbitrário).
    esperar_janela_do_jogo "$janelas_antes" 30
}

while true; do
    PONTO_ORIGEM=""

    # 1. Procura em /mnt/cdrom se o DVD fixo estiver montado
    if findmnt -M "/mnt/cdrom" >/dev/null 2>&1; then
        if find "/mnt/cdrom" -maxdepth 1 -name "*.desktop" 2>/dev/null | grep -q .; then
            PONTO_ORIGEM="/mnt/cdrom"
        fi
    fi

    # 2. Se não achou em /mnt/cdrom, busca o .desktop em até 3 níveis
    # abaixo de /media/ e /run/media/ (nunca dentro de games/, que é
    # nosso próprio destino de espelhamento — evita se auto-detectar)
    if [ -z "$PONTO_ORIGEM" ]; then
        ARQUIVO_ENCONTRADO=$(find /media /run/media -maxdepth 3 -name "*.desktop" 2>/dev/null | grep -v "$GAMES_DIR" | head -n 1)
        if [ -n "$ARQUIVO_ENCONTRADO" ]; then
            PONTO_ORIGEM=$(dirname "$ARQUIVO_ENCONTRADO")
        fi
    fi

    # 3. MÍDIA INSERIDA
    if [ -n "$PONTO_ORIGEM" ]; then
        if [ "$ULTIMO_ESTADO" == "vazio" ]; then
            iniciar_tela_carregamento "$REFRESH_BACKGROUND"

            matar_app

            > "$ARQUIVO_LINKS_ATIVOS"

            # Pra cada subpasta de "sistema" na mídia (psx, snes,
            # pc...), cria um link simbólico dentro de
            # games/disc-loader/<sistema>/ — nomes minúsculos, batendo
            # com a convenção que já usamos em toda a estrutura.
            for SUBPASTA_MIDIA in "$PONTO_ORIGEM"/*/; do
                [ -d "$SUBPASTA_MIDIA" ] || continue
                NOME_SISTEMA="$(basename "$SUBPASTA_MIDIA")"
                NOME_SISTEMA_MINUSCULO="$(echo "$NOME_SISTEMA" | tr '[:upper:]' '[:lower:]')"

                if eh_nome_reservado "$NOME_SISTEMA_MINUSCULO"; then
                    echo "AVISO: mídia tem uma pasta chamada '$NOME_SISTEMA' (nome reservado) — ignorando, não espelhada." >&2
                    continue
                fi

                DESTINO="$DISC_LOADER_DIR/$NOME_SISTEMA_MINUSCULO"
                ln -sfn "$SUBPASTA_MIDIA" "$DESTINO"
                echo "$DESTINO" >> "$ARQUIVO_LINKS_ATIVOS"
            done

            # Ícone customizado do disco — aceita icon.png OU icon.ico
            # na raiz da mídia. Copia pra um nome fixo dentro de
            # disc-loader/ (não um link, já que a mídia pode ser
            # removida) — o gerar-dados.py procura por esse nome fixo.
            rm -f "$DISC_LOADER_DIR/.icone-disco.png" "$DISC_LOADER_DIR/.icone-disco.ico" "$DISC_LOADER_DIR/.icone-disco-fallback.png"
            if [ -f "$PONTO_ORIGEM/icon.png" ]; then
                cp "$PONTO_ORIGEM/icon.png" "$DISC_LOADER_DIR/.icone-disco.png"
            elif [ -f "$PONTO_ORIGEM/icon.ico" ]; then
                cp "$PONTO_ORIGEM/icon.ico" "$DISC_LOADER_DIR/.icone-disco.ico"
            fi

            # Label/rótulo do disco (nome dado a ele na hora de
            # gravar/formatar) — mostrado abaixo de "DISC-LOADER" na
            # tela. Salvo num arquivo fixo, mesma lógica do ícone.
            DISPOSITIVO=$(findmnt -n -o SOURCE -M "$PONTO_ORIGEM" 2>/dev/null)
            ROTULO_DISCO=""
            [ -n "$DISPOSITIVO" ] && ROTULO_DISCO=$(lsblk -no LABEL "$DISPOSITIVO" 2>/dev/null | xargs)
            [ -z "$ROTULO_DISCO" ] && ROTULO_DISCO=$(basename "$PONTO_ORIGEM")
            echo "$ROTULO_DISCO" > "$DISC_LOADER_DIR/.rotulo-disco.txt"

            regenerar_dados
            abrir_app

            limpar_tela_carregamento

            ULTIMO_ESTADO="ocupado"
        fi
    else
        # 4. MÍDIA REMOVIDA
        if [ "$ULTIMO_ESTADO" == "ocupado" ]; then
            iniciar_tela_carregamento "$REFRESH_BACKGROUND"

            matar_app

            # Remove só os links criados nesta sessão, preservando
            # tudo que é permanente (ssd/, uninstall/).
            if [ -f "$ARQUIVO_LINKS_ATIVOS" ]; then
                while read -r LINK; do
                    [ -L "$LINK" ] && rm -f "$LINK"
                done < "$ARQUIVO_LINKS_ATIVOS"
                rm -f "$ARQUIVO_LINKS_ATIVOS"
            fi

            rm -f "$DISC_LOADER_DIR/.icone-disco.png" "$DISC_LOADER_DIR/.icone-disco.ico" "$DISC_LOADER_DIR/.icone-disco-fallback.png" "$DISC_LOADER_DIR/.rotulo-disco.txt"

            regenerar_dados
            abrir_app

            limpar_tela_carregamento
        fi
        ULTIMO_ESTADO="vazio"
    fi

    sleep 3
done
