#!/bin/bash

# ============================================================
# GameStation - install_dependencies.sh
#
# Confere e INSTALA tudo que o GameStation precisa num PC novo.
#
# PC:
#   - Faugus Launcher
#   - Proton
#   - gamescope
#
# STEAM:
#   - Steam oficial da Valve
#
# TELA DE CARREGAMENTO:
#   - Python 3
#   - Tkinter
#   - wmctrl
#
# Não cobre emuladores.
# Isso é configurado separadamente, fora do escopo deste script.
#
# Rode com:
#
#   ./install_dependencies.sh
#
# Vai pedir sua senha (sudo) quando precisar instalar
# pacotes do sistema.
# ============================================================

set -uo pipefail


# ============================================================
# Variáveis
# ============================================================

FALHAS=0

APT_ATUALIZADO="nao"


# ============================================================
# Atualiza lista de pacotes uma única vez
# ============================================================

atualizar_apt_uma_vez() {

    if [ "$APT_ATUALIZADO" = "nao" ]; then

        echo ">> Atualizando lista de pacotes (sudo apt update)..."

        if sudo apt update; then

            APT_ATUALIZADO="sim"

        else

            echo "[FALHOU]  sudo apt update falhou."

            FALHAS=$((FALHAS + 1))

        fi

    fi
}


# ============================================================
# Habilita arquitetura i386
#
# Necessária para Steam/Faugus e bibliotecas 32-bit.
# ============================================================

garantir_i386() {

    if ! dpkg --print-foreign-architectures |
        grep -q i386; then

        echo ">> Habilitando arquitetura i386 (Steam/Faugus precisam de libs 32-bit)..."

        if sudo dpkg --add-architecture i386; then

            APT_ATUALIZADO="nao"

        else

            echo "[FALHOU]  não foi possível habilitar a arquitetura i386."

            FALHAS=$((FALHAS + 1))

        fi

    fi
}


# ============================================================
# Instala pacote APT caso o comando não exista
#
# Uso:
#
#   instalar_apt "comando" "pacote"
#
# Exemplo:
#
#   instalar_apt "python3" "python3"
# ============================================================

instalar_apt() {

    local comando="$1"

    local pacotes="$2"


    if command -v "$comando" >/dev/null 2>&1; then

        echo "[OK]      $comando"

        return 0

    fi


    echo "[FALTA]   $comando — instalando ($pacotes)..."


    atualizar_apt_uma_vez


    if sudo apt install -y $pacotes; then

        echo "[OK]      $comando instalado com sucesso."

    else

        echo "[FALHOU]  não foi possível instalar $comando via apt ($pacotes)."

        FALHAS=$((FALHAS + 1))

    fi
}


# ============================================================
# Início
# ============================================================

echo ""
echo "============================================================"
echo " GameStation - Instalação de Dependências"
echo "============================================================"
echo ""


# ============================================================
# Ferramentas essenciais
# ============================================================

echo "=== Ferramentas essenciais ==="

instalar_apt "python3" "python3"

instalar_apt "findmnt" "util-linux"

instalar_apt "lsblk" "util-linux"

instalar_apt "pgrep" "procps"

instalar_apt "unzip" "unzip"

instalar_apt "zenity" "zenity"

instalar_apt "feh" "feh"

instalar_apt "xdg-open" "xdg-utils"

instalar_apt "wget" "wget"

instalar_apt "git" "git"

instalar_apt "pip" "python3-pip"



# ============================================================
# Tela de carregamento do GameStation
#
# Python/Tkinter cria a janela.
#
# wmctrl é usado para detectar as janelas dos jogos
# e do ES-DE.
# ============================================================

echo ""
echo "=== Tela de carregamento do GameStation ==="

instalar_apt "python3" "python3"

instalar_apt "wmctrl" "wmctrl"




# ------------------------------------------------------------
# Tkinter não possui um comando próprio para ser detectado
# com command -v.
#
# Portanto verificamos diretamente se o módulo pode ser
# importado pelo Python.
# ------------------------------------------------------------

if python3 -c "import tkinter" >/dev/null 2>&1; then

    echo "[OK]      python3-tk"

else

    echo "[FALTA]   python3-tk — instalando..."

    atualizar_apt_uma_vez

    if sudo apt install -y python3-tk; then

        if python3 -c "import tkinter" >/dev/null 2>&1; then

            echo "[OK]      python3-tk instalado com sucesso."

        else

            echo "[FALHOU]  python3-tk foi instalado, mas o Python não conseguiu importar tkinter."

            FALHAS=$((FALHAS + 1))

        fi

    else

        echo "[FALHOU]  não foi possível instalar python3-tk."

        FALHAS=$((FALHAS + 1))

    fi

fi


# ============================================================
# pywebview
#
# Biblioteca que abre a janela nativa do app.py — a interface
# principal do GameStation (não é mais o ES-DE).
# ============================================================

echo ""
echo "=== pywebview (janela nativa do app principal do GameStation) ==="

if python3 -c "import webview" >/dev/null 2>&1; then

    echo "[OK]      pywebview"

else

    echo "[FALTA]   pywebview — instalando via pip..."

    if pip install pywebview --break-system-packages; then

        if python3 -c "import webview" >/dev/null 2>&1; then

            echo "[OK]      pywebview instalado com sucesso."

        else

            echo "[FALHOU]  pywebview foi instalado, mas o Python não conseguiu importar."

            FALHAS=$((FALHAS + 1))

        fi

    else

        echo "[FALHOU]  não foi possível instalar pywebview via pip."

        FALHAS=$((FALHAS + 1))

    fi

fi


# ============================================================
# Pillow
#
# Usado pelo launchbox_scraper.py pra redimensionar a Clear Logo
# baixada — sem isso, a lista gráfica de jogos fica lenta (imagem
# em resolução alta, repetida várias vezes na tela ao mesmo tempo).
# ============================================================

echo ""
echo "=== Pillow (redimensiona a Clear Logo pra lista gráfica não ficar lenta) ==="

if python3 -c "import PIL" >/dev/null 2>&1; then

    echo "[OK]      Pillow"

else

    echo "[FALTA]   Pillow — instalando via pip..."

    if pip install Pillow --break-system-packages; then

        if python3 -c "import PIL" >/dev/null 2>&1; then

            echo "[OK]      Pillow instalado com sucesso."

        else

            echo "[FALHOU]  Pillow foi instalado, mas o Python não conseguiu importar."

            FALHAS=$((FALHAS + 1))

        fi

    else

        echo "[FALHOU]  não foi possível instalar Pillow via pip."

        FALHAS=$((FALHAS + 1))

    fi

fi


# ============================================================
# Skyscraper (raspador de mídia — Gemba fork, NÃO o muldjord
# original, que parou na 3.7.7 e não tem vários recursos que
# usamos, como o flag "fanarts" e melhorias de compositor)
#
# Precisa de ferramentas de build do Qt ANTES de compilar — sem
# isso, o processo de build falha silenciosamente em vários pontos.
# ============================================================

echo ""
echo "=== Dependências de build do Skyscraper (Qt) ==="

PACOTES_QT="qt5-qmake qtbase5-dev libqt5svg5-dev libqt5concurrent5 build-essential"

if sudo apt install -y $PACOTES_QT; then

    echo "[OK]      Dependências de build do Qt"

else

    echo "[FALHOU]  não foi possível instalar as dependências de build do Qt."

    FALHAS=$((FALHAS + 1))

fi

echo ""
echo "=== Skyscraper (raspador de mídia) ==="

if command -v Skyscraper >/dev/null 2>&1; then

    echo "[OK]      Skyscraper"

else

    echo "[FALTA]   Skyscraper — baixando e compilando (fork Gemba)..."

    PASTA_BUILD_SKYSCRAPER="/tmp/gamestation_skysource"
    rm -rf "$PASTA_BUILD_SKYSCRAPER"
    mkdir -p "$PASTA_BUILD_SKYSCRAPER"

    if (cd "$PASTA_BUILD_SKYSCRAPER" && wget -q -O - https://raw.githubusercontent.com/Gemba/skyscraper/master/update_skyscraper.sh | bash); then

        if command -v Skyscraper >/dev/null 2>&1; then

            echo "[OK]      Skyscraper instalado com sucesso."

        else

            echo "[FALHOU]  Skyscraper foi compilado, mas o comando não ficou disponível."

            FALHAS=$((FALHAS + 1))

        fi

    else

        echo "[FALHOU]  não foi possível baixar/compilar o Skyscraper."

        FALHAS=$((FALHAS + 1))

    fi

    rm -rf "$PASTA_BUILD_SKYSCRAPER"

fi


# ============================================================
# artwork.xml do Skyscraper
#
# Configura o Skyscraper pra gerar só screenshot (com a capa
# sobreposta) + wheel, no formato que nosso index.html espera —
# sem isso ele usa o padrão dele, que não bate com o que
# precisamos. Guardado como parte do próprio projeto
# (system/skyscraper-artwork.xml), copiado pra onde o Skyscraper
# realmente lê.
# ============================================================

echo ""
echo "=== Configurando artwork.xml do Skyscraper ==="

ARTWORK_ORIGEM="$(dirname "$0")/system/skyscraper-artwork.xml"
ARTWORK_DESTINO="$HOME/.skyscraper/artwork.xml"

if [ -f "$ARTWORK_ORIGEM" ]; then

    mkdir -p "$HOME/.skyscraper"
    cp "$ARTWORK_ORIGEM" "$ARTWORK_DESTINO"
    echo "[OK]      artwork.xml copiado pra $ARTWORK_DESTINO"

else

    echo "[AVISO]   system/skyscraper-artwork.xml não encontrado no projeto — pulei essa etapa."

fi



# ============================================================
# gamescope
#
# Força tela cheia mantendo a proporção original do jogo.
#
# Útil principalmente para jogos 4:3 que abrem em janela.
# ============================================================

echo ""
echo "=== gamescope (força tela cheia mantendo a proporção original do jogo"
echo "    — útil pra jogos 4:3 que só abrem em janela) ==="


if command -v gamescope >/dev/null 2>&1; then

    echo "[OK]      gamescope"

else

    echo "[FALTA]   gamescope — não vem nos repositórios padrão do Mint/Ubuntu,"

    echo "          instalando via PPA (confirmado funcionando no Mint 22)..."


    if ! command -v add-apt-repository >/dev/null 2>&1; then

        atualizar_apt_uma_vez

        if ! sudo apt install -y software-properties-common; then

            echo "[FALHOU]  não foi possível instalar software-properties-common."

            FALHAS=$((FALHAS + 1))

        fi

    fi


    if sudo add-apt-repository -y ppa:3v1n0/gamescope; then

        APT_ATUALIZADO="nao"

        atualizar_apt_uma_vez


        if sudo apt install -y vulkan-tools gamescope; then

            echo "[OK]      gamescope instalado com sucesso."

        else

            echo "[FALHOU]  apt install do gamescope falhou."

            FALHAS=$((FALHAS + 1))

        fi

    else

        echo "[FALHOU]  não foi possível adicionar o PPA do gamescope (ppa:3v1n0/gamescope)."

        FALHAS=$((FALHAS + 1))

    fi

fi


# ============================================================
# Faugus Launcher
#
# GUI opcional para configuração/depuração.
#
# A automação do GameStation usa a CLI.
#
# O Faugus já possui gerenciamento de GE-Proton.
# ============================================================

echo ""
echo "=== Faugus Launcher (GUI opcional — só pra configurar/depurar um jogo"
echo "    específico que não abriu direito; a automação via CLI não depende"
echo "    dele. Já vem com gerenciador de GE-Proton embutido, então cobre o"
echo "    que o ProtonUp-Qt/ProtonPlus fariam, sem precisar instalar os dois) ==="


if command -v faugus-launcher >/dev/null 2>&1; then

    echo "[OK]      faugus-launcher"

else

    echo "[FALTA]   faugus-launcher — instalando via .deb oficial..."


    garantir_i386

    atualizar_apt_uma_vez


    FAUGUS_DEB_TMP="$(mktemp --suffix=.deb)"


    if wget -q -O "$FAUGUS_DEB_TMP" \
        "https://github.com/Faugus/faugus-launcher/releases/download/2.2.0/faugus-launcher_2.2.0-1_all.deb"; then


        if sudo apt install -y "$FAUGUS_DEB_TMP"; then

            echo "[OK]      faugus-launcher instalado com sucesso."

        else

            echo "[FALHOU]  apt install do faugus-launcher.deb falhou."

            FALHAS=$((FALHAS + 1))

        fi

    else

        echo "[FALHOU]  não foi possível baixar o faugus-launcher.deb (verifique sua conexão)."

        FALHAS=$((FALHAS + 1))

    fi


    rm -f "$FAUGUS_DEB_TMP"

fi


# ============================================================
# Steam
#
# Necessário para discos tipo STEAM.
# ============================================================

echo ""
echo "=== Steam (necessário para discos tipo STEAM — via .deb oficial da Valve) ==="


if command -v steam >/dev/null 2>&1; then

    echo "[OK]      steam"

else

    echo "[FALTA]   steam — instalando via .deb oficial..."


    garantir_i386

    atualizar_apt_uma_vez


    STEAM_DEB_TMP="$(mktemp --suffix=.deb)"


    if wget -q -O "$STEAM_DEB_TMP" \
        "https://cdn.akamai.steamstatic.com/client/installer/steam.deb"; then


        if sudo apt install -y "$STEAM_DEB_TMP"; then

            echo "[OK]      steam instalado com sucesso."

        else

            echo "[FALHOU]  apt install do steam.deb falhou."

            FALHAS=$((FALHAS + 1))

        fi

    else

        echo "[FALHOU]  não foi possível baixar o steam.deb (verifique sua conexão)."

        FALHAS=$((FALHAS + 1))

    fi


    rm -f "$STEAM_DEB_TMP"

fi


# ============================================================
# Detecção da pasta userdata do Steam
#
# Só relevante para discos tipo STEAM.
# ============================================================

echo ""
echo "=== Detecção da pasta userdata do Steam (só relevante pro tipo STEAM) ==="


CANDIDATOS_STEAM=(
    "$HOME/.local/share/Steam/userdata"
    "$HOME/.steam/steam/userdata"
)


ACHOU_STEAM_DIR=""


for c in "${CANDIDATOS_STEAM[@]}"; do

    if [ -d "$c" ]; then

        ACHOU_STEAM_DIR="$c"

        break

    fi

done


if [ -n "$ACHOU_STEAM_DIR" ]; then

    echo "[OK]      pasta userdata encontrada: $ACHOU_STEAM_DIR"

else

    echo "[AVISO]   pasta userdata do Steam ainda não existe — abra o Steam e faça"

    echo "          login pelo menos uma vez antes de usar os discos."

fi


# ============================================================
# Resultado final
# ============================================================

echo ""

if [ "$FALHAS" -eq 0 ]; then

    echo "============================================================"
    echo " Tudo pronto — nenhuma falha durante a instalação."
    echo "============================================================"

    exit 0

else

    echo "============================================================"
    echo " $FALHAS etapa(s) falharam."
    echo " Revise as mensagens [FALHOU] acima antes de confiar nos discos."
    echo "============================================================"

    exit 1

fi
