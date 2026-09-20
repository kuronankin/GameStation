#!/usr/bin/env python3
"""
gerar-dados.py - GameStation (app nativo)

Varre Games/Disc-Loader/, Games/SSD/ e uninstall/, e gera
dados.json — o mesmo papel que gerar-metadata-pegasus.sh tinha pro
Pegasus, só que produzindo JSON pro nosso app nativo em vez de
metadata.pegasus.txt.

Reaproveita a MESMA lógica já validada: filtro de extensão por
sistema (extensoes.txt), detecção de jogo-em-pasta tipo GDI
multi-track (prioridade .gdi/.cue/.m3u), consulta de comando de
emulador (emulators.txt) — só que em Python em vez de bash.

Uso: python3 gerar-dados.py
"""

import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import launchbox_scraper

GAMESTATION_DIR = "/mnt/GameStation"
GAMES_DIR = os.path.join(GAMESTATION_DIR, "games")
DISC_LOADER_DIR = os.path.join(GAMES_DIR, "disc-loader")
SSD_DIR = os.path.join(GAMES_DIR, "ssd")
UNINSTALL_DIR = os.path.join(GAMES_DIR, "uninstall")
MEDIA_DIR = os.path.join(GAMESTATION_DIR, "media")
EMULATORS_TXT = os.path.join(GAMESTATION_DIR, "emulators", "emulators.txt")
EXTENSOES_TXT = os.path.join(GAMESTATION_DIR, "emulators", "extensoes.txt")
SYSTEM_DIR = os.path.join(GAMESTATION_DIR, "system")
DADOS_JSON = os.path.join(MEDIA_DIR, "dados.json")

# Índices .gdi/.cue/.m3u são sempre tentados primeiro dentro de uma
# pasta de jogo (GDI multi-track) — representam "o disco inteiro",
# nunca uma faixa de dados avulsa.
EXTENSOES_INDICE_PRIORITARIAS = [".gdi", ".cue", ".m3u"]

# Fundo padrão quando não há screenshot/arte pro jogo específico.
FUNDO_PADRAO = "linear-gradient(135deg,#1a1a2a,#0a0a12)"


def carregar_emuladores(caminho):
    """
    Lê emulators.txt — linhas RETROARCH=/CORES= viram variáveis de
    conveniência expandidas dentro das linhas de sistema (psx=,
    snes=, etc.), que vão pro dicionário devolvido. Também expande
    $HOME e outras variáveis de ambiente reais — o bash fazia isso
    sozinho, o Python precisa que a gente peça explicitamente.
    """
    emulador_cmd = {}
    variaveis = {}

    if not os.path.isfile(caminho):
        return emulador_cmd

    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            if "=" not in linha:
                continue

            chave, valor = linha.split("=", 1)
            chave = chave.strip()
            valor = valor.strip()

            # $HOME e outras variáveis de ambiente reais (não as
            # nossas de conveniência) — o bash expandia isso sozinho
            # via eval, o Python precisa que a gente chame na mão.
            valor = os.path.expandvars(valor)

            # Expande variáveis já carregadas (ex: $RETROARCH, $CORES)
            for nome_var, valor_var in variaveis.items():
                valor = valor.replace(f"${nome_var}", valor_var)

            if chave in ("RETROARCH", "CORES"):
                variaveis[chave] = valor
            else:
                emulador_cmd[chave] = valor

    return emulador_cmd


def carregar_extensoes(caminho):
    """
    Lê extensoes.txt — sistema=extensões aceitas (separadas por
    espaço). Sistema sem entrada não é filtrado (aceita qualquer
    extensão) — cobre o "PC" customizado.
    """
    extensao_sistema = {}

    if not os.path.isfile(caminho):
        return extensao_sistema

    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            if "=" not in linha:
                continue
            chave, valor = linha.split("=", 1)
            extensao_sistema[chave.strip()] = valor.strip().split()

    return extensao_sistema


def montar_launch(comando_sistema, caminho_arquivo):
    """
    Substitui {file.path} no comando do emulador pelo caminho real
    do jogo — mesma lógica de sempre, só que aqui o comando já é
    executado direto pelo Python (subprocess), não escrito num
    metadata.pegasus.txt.
    """
    if not comando_sistema:
        return None
    return comando_sistema.replace("{file.path}", f'"{caminho_arquivo}"')


def escanear_sistema(pasta_sistema, emulador_cmd, extensao_sistema, forcar_atualizacao=False):
    """
    Escaneia UMA pasta de sistema (ex: Games/SSD/psx/), devolvendo a
    lista de jogos encontrados — já filtrados por extensão, já
    resolvendo pasta-de-jogo tipo GDI multi-track, já com o launch
    certo.
    """
    nome_sistema = os.path.basename(pasta_sistema.rstrip("/"))
    comando_sistema = emulador_cmd.get(nome_sistema)
    extensoes_aceitas = extensao_sistema.get(nome_sistema)

    jogos = []

    if not os.path.isdir(pasta_sistema):
        return jogos

    # "pc" não usa o Skyscraper — jogos indie não batem por nome de
    # arquivo do jeito que ROM de console bate. Usa o auto-scraper do
    # LaunchBox nesse caso específico (chamado por jogo, mais abaixo).
    if nome_sistema != "pc":
        executar_skyscraper(nome_sistema, pasta_sistema, forcar_atualizacao)

    for nome_item in sorted(os.listdir(pasta_sistema)):
        if nome_item in ("systeminfo.txt", "media", "skraper", "dados.json"):
            continue

        caminho_item = os.path.join(pasta_sistema, nome_item)

        if os.path.isdir(caminho_item):
            # Jogo em formato PASTA (GDI multi-track) — procura o
            # arquivo índice certo, ignorando as faixas de dados.
            arquivo_indice = None

            for ext in EXTENSOES_INDICE_PRIORITARIAS:
                candidatos = [
                    f for f in os.listdir(caminho_item)
                    if f.lower().endswith(ext)
                ]
                if candidatos:
                    arquivo_indice = os.path.join(caminho_item, candidatos[0])
                    break

            if arquivo_indice is None and extensoes_aceitas:
                for ext in extensoes_aceitas:
                    candidatos = [
                        f for f in os.listdir(caminho_item)
                        if f.lower().endswith(ext)
                    ]
                    if candidatos:
                        arquivo_indice = os.path.join(caminho_item, candidatos[0])
                        break

            if arquivo_indice is None:
                continue  # pasta sem arquivo índice reconhecido — ignora

            nome_jogo = nome_item  # nome da PASTA, não do arquivo índice
            caminho_final = arquivo_indice
        else:
            extensao = os.path.splitext(nome_item)[1].lower()

            if extensao not in (".sh", ".txt") and extensoes_aceitas:
                if extensao not in extensoes_aceitas:
                    continue

            nome_jogo = os.path.splitext(nome_item)[0]
            caminho_final = caminho_item

        nome_arquivo_bruto = nome_jogo  # sem NENHUMA conversão — usado como legenda

        # "pc" usa o LaunchBox (por jogo) — os outros já vieram do
        # Skyscraper (por sistema inteiro, lá em cima).
        nome_base_arquivo = os.path.splitext(nome_item)[0]
        if nome_sistema == "pc":
            launchbox_scraper.processar_jogo_pc(nome_base_arquivo)

        # Miximage (uma imagem só, combinando screenshot+capa+logo,
        # gerada pelo Skyscraper via artwork.xml) pro centro da tela,
        # e logo (wheel) separado pro carrossel de navegação embaixo.
        # Mesmo formato de pasta pros dois casos (Skyscraper ou
        # LaunchBox), então a busca abaixo funciona igual.
        snapshot = buscar_midia_skyscraper(nome_sistema, nome_base_arquivo, "screenshots")
        logo = buscar_midia_skyscraper(nome_sistema, nome_base_arquivo, "wheels")

        jogo_montado = {
            "nome": nome_jogo,
            "nomeArquivo": nome_arquivo_bruto,
            "sistema": nome_sistema,
            "snapshot": snapshot,
            "logo": logo,
            "launch": montar_launch(comando_sistema, caminho_final),
        }

        # Só faz sentido pra PC do Disc-Loader — usado pelo frontend
        # pra decidir se mostra "Install" (ainda não instalado) ou
        # "Play" (já instalado, atalho existe na Library).
        if nome_sistema == "pc" and "disc-loader" in pasta_sistema:
            caminho_ssd_esperado = os.path.join(SSD_DIR, "pc", f"{nome_jogo}.sh")
            jogo_montado["instalado"] = os.path.isfile(caminho_ssd_esperado)

        jogos.append(jogo_montado)

    return jogos


def executar_skyscraper(nome_sistema, pasta_sistema, forcar_atualizacao=False):
    """
    Roda o Skyscraper de verdade pra esse sistema — raspa (busca no
    ScreenScraper) e gera (grava os arquivos de mídia de verdade na
    pasta configurada). Silencioso (--flags unattend), não pede
    confirmação nem trava esperando input.

    forcar_atualizacao=True adiciona "--cache refresh" no passo de
    raspagem — usado pro Disc-Loader, onde já vimos na prática o
    cache local ficar com o metadado do jogo salvo mas SEM a imagem
    de verdade baixada (então "Cover/Screenshot/Wheel: NO" mesmo pro
    jogo já ter sido raspado com sucesso antes). Fixo/Library não
    usa isso, pra não perder tempo rebaixando tudo de novo sempre.

    Se o Skyscraper não estiver instalado, ou o sistema não for
    reconhecido por ele, só avisa no console e segue em frente sem
    quebrar o resto do processo.
    """
    # No Disc-Loader, pasta_sistema é um LINK SIMBÓLICO (criado pelo
    # autoplay.sh apontando pra mídia removível) — o Skyscraper tem
    # um bug/comportamento conhecido de não enxergar arquivos quando
    # a pasta de entrada em si é um link. Resolve pro caminho real
    # por trás do link antes de passar adiante; na Library isso não
    # muda nada (já é um caminho real).
    pasta_sistema_real = os.path.realpath(pasta_sistema)
    if pasta_sistema_real != os.path.abspath(pasta_sistema):
        print(f"[gerar-dados] '{pasta_sistema}' é um link — usando caminho real: '{pasta_sistema_real}'")

    pasta_media_sistema = os.path.join(MEDIA_DIR, nome_sistema)
    os.makedirs(pasta_media_sistema, exist_ok=True)

    comando_base = [
        "Skyscraper",
        "-p", nome_sistema,
        "-i", pasta_sistema_real,
        "-o", pasta_media_sistema,
        "--flags", "unattend",
    ]

    comando_raspar = comando_base + ["-s", "screenscraper"]
    if forcar_atualizacao:
        comando_raspar += ["--cache", "refresh"]

    try:
        # Passo 1: raspa (busca no ScreenScraper, preenche o cache local)
        print(f"[gerar-dados] Skyscraper: raspando '{nome_sistema}'...")
        resultado_raspar = subprocess.run(
            comando_raspar,
            capture_output=True, text=True, timeout=600,
        )
        print(f"[gerar-dados] Skyscraper (raspar) código de saída: {resultado_raspar.returncode}")
        if resultado_raspar.stdout:
            print(f"[gerar-dados] Skyscraper (raspar) saída:\n{resultado_raspar.stdout}")
        if resultado_raspar.stderr:
            print(f"[gerar-dados] Skyscraper (raspar) erro:\n{resultado_raspar.stderr}")

        # Passo 2: gera (grava os arquivos de mídia de verdade a
        # partir do cache) — sem "-s", usa só o cache local
        print(f"[gerar-dados] Skyscraper: gerando mídia pra '{nome_sistema}'...")
        resultado_gerar = subprocess.run(
            comando_base,
            capture_output=True, text=True, timeout=300,
        )
        print(f"[gerar-dados] Skyscraper (gerar) código de saída: {resultado_gerar.returncode}")
        if resultado_gerar.stdout:
            print(f"[gerar-dados] Skyscraper (gerar) saída:\n{resultado_gerar.stdout}")
        if resultado_gerar.stderr:
            print(f"[gerar-dados] Skyscraper (gerar) erro:\n{resultado_gerar.stderr}")
    except FileNotFoundError:
        print("[gerar-dados] Skyscraper não encontrado no PATH — pulando scraping automático.")
    except subprocess.TimeoutExpired:
        print(f"[gerar-dados] Skyscraper demorou demais pra '{nome_sistema}' — pulando.")
    except Exception as erro:
        print(f"[gerar-dados] Falha ao rodar Skyscraper pra '{nome_sistema}': {erro}")


def buscar_midia_skyscraper(nome_sistema, nome_base, subpasta):
    """
    Procura mídia no formato NATIVO do Skyscraper — pasta por tipo
    (screenshots/covers/wheels/fanart), nome de arquivo EXATO igual
    ao nome da ROM (sem extensão), sem sufixo nenhum. Tentado antes
    do nosso próprio formato (scraper do LaunchBox), já que o
    Skyscraper tende a achar imagem certa com mais frequência.
    """
    candidato_base = os.path.join(MEDIA_DIR, nome_sistema, subpasta, nome_base)
    for extensao in (".png", ".jpg", ".jpeg"):
        candidato = candidato_base + extensao
        if os.path.isfile(candidato):
            return f"file://{candidato}"
    return None


def montar_categoria_colecao(nome_collection, pasta_raiz, emulador_cmd, extensao_sistema):
    """
    Monta uma categoria achatada (Disc-Loader ou Library), varrendo
    todas as subpastas de sistema dentro de pasta_raiz.

    Só reconhece pastas cujo nome seja um sistema de verdade (tem
    entrada no emulators.txt) — qualquer outra pasta (ex: "music",
    posta sem querer junto no disco) é ignorada, evitando ela virar
    um "sistema" fantasma na interface.
    """
    # Disc-Loader troca de mídia toda vez — força re-raspar sempre
    # (--cache refresh), já que o cache local pode ficar com
    # metadado salvo mas sem a imagem de verdade baixada ainda
    # (aconteceu na prática). Library é fixa, não precisa disso.
    forcar_atualizacao = (nome_collection == "Disc-Loader")

    jogos = []
    if os.path.isdir(pasta_raiz):
        for nome_sistema in sorted(os.listdir(pasta_raiz)):
            pasta_sistema = os.path.join(pasta_raiz, nome_sistema)
            if not os.path.isdir(pasta_sistema):
                continue
            if nome_sistema not in emulador_cmd:
                print(f"[gerar-dados] '{nome_sistema}' não é um sistema reconhecido (sem entrada no emulators.txt) — ignorando.")
                continue
            jogos.extend(escanear_sistema(pasta_sistema, emulador_cmd, extensao_sistema, forcar_atualizacao))
    return jogos


def calcular_tamanho_bytes(caminho):
    """
    Tamanho em disco de um item da Library. Pra atalho .sh do Faugus
    (jogo de PC instalado via .zip), o arquivo em si é minúsculo — o
    jogo de verdade está extraído em GameStation/faugus/<nome>/, então
    soma o tamanho de LÁ em vez do .sh.
    """
    if caminho.endswith(".sh"):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                conteudo = f.read()
            if "GAMESTATION_TIPO=faugus" in conteudo:
                nome_encontrado = re.search(r"# GAMESTATION_NOME=(.+)", conteudo)
                if nome_encontrado:
                    pasta_faugus = os.path.join(GAMESTATION_DIR, "faugus", nome_encontrado.group(1).strip())
                    if os.path.isdir(pasta_faugus):
                        caminho = pasta_faugus
        except Exception:
            pass

    if os.path.isfile(caminho):
        return os.path.getsize(caminho)
    elif os.path.isdir(caminho):
        total = 0
        for pasta_atual, _, arquivos in os.walk(caminho):
            for nome_arquivo in arquivos:
                try:
                    total += os.path.getsize(os.path.join(pasta_atual, nome_arquivo))
                except OSError:
                    pass
        return total
    return 0


def formatar_tamanho(tamanho_bytes):
    for unidade in ("B", "KB", "MB", "GB"):
        if tamanho_bytes < 1024:
            return f"{tamanho_bytes:.1f} {unidade}"
        tamanho_bytes /= 1024
    return f"{tamanho_bytes:.1f} TB"


def montar_categoria_storage_manager(jogos_library):
    """
    Reaproveita a MESMA lista de jogos que a Library já montou (evita
    escanear/raspar tudo de novo) — só adiciona tamanho em disco de
    cada um, e ordena do maior pro menor.
    """
    itens = []
    for jogo in jogos_library:
        caminho = extrair_caminho_do_launch(jogo.get("launch", ""))
        tamanho_bytes = calcular_tamanho_bytes(caminho) if caminho else 0
        itens.append({
            **jogo,
            "tamanhoBytes": tamanho_bytes,
            "tamanhoTexto": formatar_tamanho(tamanho_bytes),
        })

    itens.sort(key=lambda j: j["tamanhoBytes"], reverse=True)
    return itens


def extrair_caminho_do_launch(comando_launch):
    resultado = re.search(r'"([^"]+)"', comando_launch or "")
    return resultado.group(1) if resultado else None


def obter_espaco_disco():
    """
    Espaço em disco (bytes) da partição onde o GameStation está —
    mostrado no topo do Storage Manager.
    """
    try:
        total, usado, livre = shutil.disk_usage(GAMESTATION_DIR)
        return {
            "totalBytes": total,
            "usadoBytes": usado,
            "livreBytes": livre,
            "totalTexto": formatar_tamanho(total),
            "usadoTexto": formatar_tamanho(usado),
            "livreTexto": formatar_tamanho(livre),
        }
    except Exception as erro:
        print(f"[gerar-dados] Falha ao obter espaço em disco: {erro}")
        return None


def montar_categoria_power():
    return [
        {"nome": "Exit to Desktop", "sistema": "", "fundo": "linear-gradient(135deg,#2a2a2a,#0f0f0f)"},
        {"nome": "Restart", "sistema": "", "fundo": "linear-gradient(135deg,#2a2418,#12100a)"},
        {"nome": "Shutdown", "sistema": "", "fundo": "linear-gradient(135deg,#3a1616,#150808)"},
    ]


def ler_rotulo_disco():
    caminho = os.path.join(DISC_LOADER_DIR, ".rotulo-disco.txt")
    if os.path.isfile(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            rotulo = f.read().strip()
            return rotulo or None
    return None


def procurar_icone_disco_customizado():
    """
    Procura o ícone customizado que o autoplay.sh copiou pra um
    nome fixo (.icone-disco.png ou .icone-disco.ico) — o disco
    original pode trazer qualquer um dos dois formatos na raiz dele
    (icon.png ou icon.ico), o autoplay.sh já normaliza pra esse
    nome fixo em disc-loader/ diretamente.
    """
    for extensao in (".png", ".ico"):
        candidato = os.path.join(DISC_LOADER_DIR, f".icone-disco{extensao}")
        if os.path.isfile(candidato):
            return f"img:file://{candidato}"
    return None


def main():
    emulador_cmd = carregar_emuladores(EMULATORS_TXT)
    extensao_sistema = carregar_extensoes(EXTENSOES_TXT)

    jogos_disc_loader = montar_categoria_colecao("Disc-Loader", DISC_LOADER_DIR, emulador_cmd, extensao_sistema)
    jogos_library = montar_categoria_colecao("Biblioteca", SSD_DIR, emulador_cmd, extensao_sistema)

    rotulo_disco = ler_rotulo_disco()
    icone_disco_customizado = procurar_icone_disco_customizado()

    categorias = [
        {
            "nome": "Disc-Loader",
            # Ícone customizado do disco (se existir) ou o padrão —
            # estrutura uniforme com as outras categorias agora
            # (icone + jogos), sem mais campos especiais.
            "icone": icone_disco_customizado or "img:assets/disco-padrao.png",
            "rotulo": rotulo_disco,
            "jogos": jogos_disc_loader,
        },
        {
            "nome": "Library",
            "icone": "img:assets/library.png",
            "jogos": jogos_library,
        },
        {
            "nome": "Storage Manager",
            "icone": "img:assets/uninstall.png",
            "jogos": montar_categoria_storage_manager(jogos_library),
            "espacoDisco": obter_espaco_disco(),
        },
        {
            "nome": "Power",
            "icone": "img:assets/power.svg",
            "jogos": montar_categoria_power(),
        },
    ]

    os.makedirs(MEDIA_DIR, exist_ok=True)
    with open(DADOS_JSON, "w", encoding="utf-8") as f:
        json.dump({"categorias": categorias}, f, ensure_ascii=False, indent=2)

    total_jogos = sum(len(c.get("jogos", c.get("jogosComDisco", []))) for c in categorias)
    print(f"dados.json regravado: {total_jogos} jogo(s)/item(ns) no total.")


if __name__ == "__main__":
    main()
