#!/bin/bash

# ============================================================
# GameStation - game-install.sh
#
# Recebe diretamente o arquivo .zip selecionado pelo ES-DE.
# ============================================================

set -uo pipefail


# ============================================================
# Verificação
# ============================================================

if [ $# -ne 1 ]; then

    echo "Uso: game-install.sh <caminho-do-jogo.zip>" >&2

    exit 1

fi


ZIP_PATH="$1"


if [ ! -f "$ZIP_PATH" ]; then

    echo "ERRO: arquivo ZIP não encontrado:"
    echo "$ZIP_PATH" >&2

    exit 1

fi


# ============================================================
# Informações
# ============================================================

NOME_JOGO="$(basename "$ZIP_PATH")"

NOME_JOGO="${NOME_JOGO%.*}"


SCRIPT_DIR="$(cd "$(dirname "$ZIP_PATH")" && pwd)"


# ============================================================
# Diretórios
# ============================================================

LIB_DIR="/mnt/GameStation/system"

FAUGUS_INSTALL_DIR="/mnt/GameStation/faugus"

UNINSTALL_DIR="/mnt/GameStation/games/uninstall"

UNINSTALL_HANDLER="/mnt/GameStation/system/uninstall-launch.sh"


# ============================================================
# Configuração
# ============================================================

FAUGUS_RUNNER="Proton-GE Latest"

USAR_GAMESCOPE="sim"


# ============================================================
# Biblioteca comum
# ============================================================

source "$LIB_DIR/common_play.sh"


# ============================================================
# Variáveis
# ============================================================

LOADING_PID=""

STDERR_TMP=""


# ============================================================
# Limpeza
# ============================================================

limpar() {

    limpar_tela_carregamento


    if [ -n "$STDERR_TMP" ]; then

        rm -f "$STDERR_TMP"

    fi

}


trap limpar EXIT


# ============================================================
# Função de erro
# ============================================================

erro() {

    echo "ERRO: $1" >&2

    exit 1

}


# ============================================================
# Captura janelas existentes
#
# Fazemos isso ANTES de iniciar o Faugus.
# ============================================================

JANELAS_ANTES="$(
    capturar_janelas
)"


# ============================================================
# Tela de carregamento
# ============================================================

iniciar_tela_carregamento


# ============================================================
# Verifica Faugus
# ============================================================

if ! command -v faugus-launcher >/dev/null 2>&1; then

    erro "comando 'faugus-launcher' não encontrado no PATH."

fi


# ============================================================
# Verifica arquivos auxiliares
# ============================================================

for script in find_exe.py faugus_games.py; do

    if [ ! -f "$LIB_DIR/$script" ]; then

        erro "$script não encontrado em $LIB_DIR"

    fi

done


# ============================================================
# Verifica handler de desinstalação
# ============================================================

if [ ! -f "$UNINSTALL_HANDLER" ]; then

    erro "uninstall-launch.sh não encontrado em $UNINSTALL_HANDLER"

fi


# ============================================================
# Pasta do jogo
# ============================================================

PASTA_JOGO="$FAUGUS_INSTALL_DIR/$NOME_JOGO"


# ============================================================
# Verifica instalação existente
# ============================================================

if [ -d "$PASTA_JOGO" ] &&
   [ -n "$(ls -A "$PASTA_JOGO" 2>/dev/null)" ]; then

    JA_INSTALADO="sim"

else

    JA_INSTALADO="nao"

fi


# ============================================================
# Extrai o ZIP se necessário
# ============================================================

if [ "$JA_INSTALADO" = "nao" ]; then

    mkdir -p "$PASTA_JOGO"


    # --------------------------------------------------------
    # unzip
    # --------------------------------------------------------

    if command -v unzip >/dev/null 2>&1; then

        if ! unzip -q -o "$ZIP_PATH" -d "$PASTA_JOGO"; then

            erro "falha ao extrair $ZIP_PATH para $PASTA_JOGO"

        fi


    # --------------------------------------------------------
    # Python fallback
    # --------------------------------------------------------

    else

        if ! python3 -c "
import zipfile
import sys

with zipfile.ZipFile(sys.argv[1]) as z:
    z.extractall(sys.argv[2])
" "$ZIP_PATH" "$PASTA_JOGO"; then

            erro "falha ao extrair $ZIP_PATH para $PASTA_JOGO"

        fi

    fi


    # --------------------------------------------------------
    # Detecta pasta embrulhada
    # --------------------------------------------------------

    mapfile -t CONTEUDO_EXTRAIDO < <(
        find "$PASTA_JOGO" \
            -mindepth 1 \
            -maxdepth 1
    )


    if [ "${#CONTEUDO_EXTRAIDO[@]}" -eq 1 ] &&
       [ -d "${CONTEUDO_EXTRAIDO[0]}" ]; then

        SUBPASTA="${CONTEUDO_EXTRAIDO[0]}"


        echo "Pasta embrulhada extra detectada:"
        echo "$SUBPASTA"

        echo "Achatando pasta..."


        shopt -s dotglob

        mv "$SUBPASTA"/* "$PASTA_JOGO"/ 2>/dev/null

        shopt -u dotglob


        rmdir "$SUBPASTA" 2>/dev/null

    fi

fi


# ============================================================
# Procura EXE
# ============================================================

STDERR_TMP="$(mktemp)"


EXE_PATH="$(
    python3 \
        "$LIB_DIR/find_exe.py" \
        "$PASTA_JOGO" \
        2>"$STDERR_TMP"
)"


cat "$STDERR_TMP" >&2


if [ -z "$EXE_PATH" ]; then

    erro "não foi possível localizar um .exe em $PASTA_JOGO. Detalhes: $(cat "$STDERR_TMP")"

fi


# ============================================================
# Adiciona ao Faugus
# ============================================================

mapfile -t SAIDA_FAUGUS < <(

    python3 \
        "$LIB_DIR/faugus_games.py" \
        add \
        "$NOME_JOGO" \
        "$EXE_PATH" \
        "$FAUGUS_RUNNER" \
        2>"$STDERR_TMP"

)


cat "$STDERR_TMP" >&2


GAMEID_FAUGUS="${SAIDA_FAUGUS[1]:-}"


if [ -z "$GAMEID_FAUGUS" ]; then

    erro "faugus_games.py não retornou um gameid válido"

fi


# ============================================================
# Diretório de desinstalação
# ============================================================

mkdir -p "$UNINSTALL_DIR"


# ============================================================
# Cria desinstalador
# ============================================================

cat > "$UNINSTALL_DIR/$NOME_JOGO.sh" <<EOF_UNINSTALL
#!/bin/bash

set -uo pipefail


# ============================================================
# Impede execução direta da lógica de desinstalação.
#
# Quando o ES-DE executa este arquivo, ele primeiro chama
# o handler central.
# ============================================================

if [ "\${GAMESTATION_UNINSTALL_RUNNING:-0}" != "1" ]; then

    exec bash "$UNINSTALL_HANDLER" "\$0"

fi


# ============================================================
# Informações
# ============================================================

PASTA_JOGO="$PASTA_JOGO"

NOME_JOGO="$NOME_JOGO"

LIB_DIR="$LIB_DIR"

FAUGUS_INSTALL_DIR="$FAUGUS_INSTALL_DIR"


# ============================================================
# Remove entrada do Faugus
# ============================================================

if [ -f "\$LIB_DIR/faugus_games.py" ]; then

    mapfile -t SAIDA_FAUGUS < <(
        python3 "\$LIB_DIR/faugus_games.py" remove "\$NOME_JOGO"
    )


    STATUS_FAUGUS="\${SAIDA_FAUGUS[0]:-NADA}"


    if [ "\$STATUS_FAUGUS" = "REMOVIDO" ]; then

        echo "Entrada removida do Faugus Launcher."


        for PASTA_PREFIXO in "\${SAIDA_FAUGUS[@]:1}"; do

            [ -z "\$PASTA_PREFIXO" ] && continue


            case "\$PASTA_PREFIXO" in

                "\$HOME/Faugus"/*)

                    if [ -d "\$PASTA_PREFIXO" ]; then

                        rm -rf "\$PASTA_PREFIXO"

                        echo "Prefixo removido: \$PASTA_PREFIXO"

                    fi

                    ;;


                *)

                    echo "AVISO: prefixo '\$PASTA_PREFIXO' fora de \$HOME/Faugus — não removido por segurança." >&2

                    ;;

            esac

        done

    fi

fi


# ============================================================
# Proteções de segurança
# ============================================================

if [ "\$PASTA_JOGO" = "$FAUGUS_INSTALL_DIR" ] ||
   [ "\$PASTA_JOGO" = "$FAUGUS_INSTALL_DIR/" ]; then

    echo "ERRO: pasta calculada é a raiz de $FAUGUS_INSTALL_DIR — abortando por segurança."

    exit 1

fi


case "\$PASTA_JOGO" in

    "$FAUGUS_INSTALL_DIR"/*)
        ;;

    *)

        echo "ERRO: pasta '\$PASTA_JOGO' não está dentro de $FAUGUS_INSTALL_DIR — abortando por segurança."

        exit 1

        ;;

esac


# ============================================================
# Remove pasta do jogo
# ============================================================

if [ -d "\$PASTA_JOGO" ]; then

    rm -rf "\$PASTA_JOGO"

    echo "Pasta do jogo removida: \$PASTA_JOGO"

fi


# ============================================================
# Remove o próprio desinstalador
# ============================================================

rm -f "\$0"

EOF_UNINSTALL


chmod +x "$UNINSTALL_DIR/$NOME_JOGO.sh"


# ============================================================
# Regenera dados.json — o app nativo detecta a mudança sozinho
# (polling) e atualiza a categoria Uninstall na tela, sem precisar
# fechar/reabrir nada.
# ============================================================

python3 "$LIB_DIR/gerar-dados.py" >/dev/null 2>&1 || true


# ============================================================
# Entra na pasta do EXE
# ============================================================

cd "$(dirname "$EXE_PATH")" ||
    erro "não foi possível entrar na pasta do jogo para abrir via Faugus."


# ============================================================
# Inicia Faugus
# ============================================================

echo "GameStation: iniciando $NOME_JOGO..."


if [ "$USAR_GAMESCOPE" = "sim" ] &&
   command -v gamescope >/dev/null 2>&1; then

    nohup gamescope \
        -W 1920 \
        -H 1080 \
        -O 1920x1080 \
        -S auto \
        -f \
        -- faugus-launcher \
        --game "$GAMEID_FAUGUS" \
        >/dev/null 2>&1 &

else

    nohup faugus-launcher \
        --game "$GAMEID_FAUGUS" \
        >/dev/null 2>&1 &

fi


# ============================================================
# Aguarda a janela do jogo
# ============================================================

echo "GameStation: aguardando a janela do jogo..."


if esperar_janela_do_jogo "$JANELAS_ANTES" 180; then

    echo "GameStation: janela do jogo detectada."

else

    echo "GameStation: janela do jogo não detectada após 180 segundos." >&2

fi


# ============================================================
# Final
# ============================================================

exit 0
