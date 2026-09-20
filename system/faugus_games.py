#!/usr/bin/env python3
# faugus_games.py
# Lê/escreve com segurança o games.json do Faugus Launcher
# (~/.local/share/faugus-launcher/games.json — confirmado direto na
# máquina do usuário, formato: lista de objetos JSON).
#
# Uso via CLI:
#   faugus_games.py add <title> <exe_path> <runner> [prefix]
#       Adiciona (ou atualiza se já existir por path) uma entrada.
#       Se prefix for omitido, usa ~/Faugus/<gameid> (mesmo padrão do
#       próprio Faugus quando você deixa o campo "Prefixo" em branco).
#       Imprime "NOVO" ou "EXISTENTE" em stdout.
#   faugus_games.py remove <title>
#       Remove a entrada com esse título exato (e o ícone associado,
#       se existir). Imprime "REMOVIDO" ou "NADA" em stdout.
#
# SEGURANÇA: sempre faz backup com timestamp antes de sobrescrever,
# escreve num temporário, relê pra confirmar JSON válido, só então
# substitui o original (os.replace, atômico).

import sys
import os
import re
import json
import shutil
import datetime

GAMES_JSON_PATH = os.path.expanduser("~/.local/share/faugus-launcher/games.json")
FAUGUS_DATA_DIR = os.path.expanduser("~/.local/share/faugus-launcher")
DEFAULT_PREFIX_ROOT = os.path.expanduser("~/Faugus")


class FaugusGamesError(Exception):
    pass


def log(msg):
    print(msg, file=sys.stderr)


def slugify(title: str) -> str:
    """Aproximação do slug que o próprio Faugus gera a partir do
    título (minúsculas, espaços viram hífen). Só usada como padrão
    quando NÃO recebemos um gameid/prefix explícito — se um dia isso
    divergir do algoritmo real do Faugus, não quebra nada, só faz o
    nome da pasta ficar levemente diferente do que a GUI geraria."""
    s = title.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "jogo"


def backup_file(path):
    if not os.path.exists(path):
        return None
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{path}.bak-{ts}"
    shutil.copy2(path, backup_path)
    log(f"backup criado: {backup_path}")
    return backup_path


def load_games():
    if not os.path.exists(GAMES_JSON_PATH):
        return []
    with open(GAMES_JSON_PATH, "r", encoding="utf-8") as f:
        texto = f.read()
    if not texto.strip():
        return []
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as e:
        raise FaugusGamesError(
            f"{GAMES_JSON_PATH} existe mas não deu parse (JSON inválido): {e}. "
            "Abortando sem tocar no arquivo."
        )
    if not isinstance(dados, list):
        raise FaugusGamesError(f"{GAMES_JSON_PATH} não é uma lista JSON — formato inesperado.")
    return dados


def save_games(games_list):
    texto_final = json.dumps(games_list, indent=4, ensure_ascii=False)

    tmp_path = GAMES_JSON_PATH + ".tmp-writing"
    os.makedirs(os.path.dirname(GAMES_JSON_PATH), exist_ok=True)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(texto_final)

    # Relê pra confirmar que o que escrevemos é JSON válido e ainda é lista
    with open(tmp_path, "r", encoding="utf-8") as f:
        reread = json.load(f)
    if not isinstance(reread, list):
        os.remove(tmp_path)
        raise FaugusGamesError("verificação pós-escrita falhou: resultado não é uma lista JSON")

    backup_file(GAMES_JSON_PATH)
    os.replace(tmp_path, GAMES_JSON_PATH)


def build_entry(title, exe_path, runner, prefix=None):
    gameid = slugify(title)
    if prefix is None:
        prefix = os.path.join(DEFAULT_PREFIX_ROOT, gameid)
    return {
        "gameid": gameid,
        "title": title,
        "path": exe_path,
        "prefix": prefix,
        "launch_arguments": "",
        "game_arguments": "",
        "mangohud": "",
        "gamemode": "",
        "sdl_enabled": "",
        "protonfix": "",
        "runner": runner,
        "addapp_enabled": "",
        "addapp": "",
        "addapp_bat": "",
        "addapp_delay": "",
        "addapp_first": False,
        "cover": "",
        "lossless_enabled": False,
        "lossless_multiplier": 1,
        "lossless_flow": 100,
        "lossless_performance": False,
        "lossless_hdr": False,
        "lossless_present": False,
        "playtime": 0,
        "hidden": False,
        "no_sleep": "",
        "category": False,
        "icon": "",
        "steamgriddb_id": "",
        "pre_launch": "",
        "post_launch": "",
        "steam_user": "",
        "disable_umu": "",
    }


def add_or_update(title, exe_path, runner, prefix=None):
    """Retorna (status, gameid). status é 'NOVO' ou 'EXISTENTE'. O
    gameid é o que o `faugus-launcher --game <gameid>` espera receber
    — confirmado na prática que --game usa o gameid (slug), NÃO o
    título."""
    games = load_games()

    # Idempotência: procura por path (mais confiável que title, já que
    # o path é único de verdade por jogo instalado).
    for i, g in enumerate(games):
        if g.get("path") == exe_path:
            games[i]["title"] = title
            games[i]["runner"] = runner
            if prefix is not None:
                games[i]["prefix"] = prefix
            save_games(games)
            gameid_existente = g.get("gameid", slugify(title))
            log(f"entrada existente atualizada para '{title}' (gameid={gameid_existente}).")
            return "EXISTENTE", gameid_existente

    nova = build_entry(title, exe_path, runner, prefix)
    games.append(nova)
    save_games(games)
    log(f"nova entrada criada para '{title}' (gameid={nova['gameid']}).")
    return "NOVO", nova["gameid"]


def remove_by_title(title):
    """Retorna (status, lista_de_prefixos_removidos). status é
    'REMOVIDO' ou 'NADA'. Os prefixos retornados são os que o PRÓPRIO
    Faugus tinha registrado pra esse jogo (não recalculados por nós),
    já que o usuário pode ter trocado o local pela GUI."""
    games = load_games()
    removidos = [g for g in games if g.get("title") == title]
    restantes = [g for g in games if g.get("title") != title]

    if not removidos:
        log(f"nenhuma entrada com title='{title}' encontrada.")
        return "NADA", []

    save_games(restantes)
    log(f"removida(s) {len(removidos)} entrada(s) com title='{title}'.")

    prefixos = []
    for g in removidos:
        icone = g.get("icon")
        if icone and os.path.isfile(icone):
            try:
                os.remove(icone)
                log(f"ícone removido: {icone}")
            except OSError:
                pass
        prefixo = g.get("prefix")
        if prefixo:
            prefixos.append(prefixo)

    return "REMOVIDO", prefixos


def main():
    if len(sys.argv) < 2:
        log("Uso: faugus_games.py add <title> <exe_path> <runner> [prefix]")
        log("     faugus_games.py remove <title>")
        sys.exit(1)

    acao = sys.argv[1]
    try:
        if acao == "add":
            if len(sys.argv) not in (5, 6):
                log("Uso: faugus_games.py add <title> <exe_path> <runner> [prefix]")
                sys.exit(1)
            title, exe_path, runner = sys.argv[2], sys.argv[3], sys.argv[4]
            prefix = sys.argv[5] if len(sys.argv) == 6 else None
            status, gameid = add_or_update(title, exe_path, runner, prefix)
            print(status)
            print(gameid)
        elif acao == "remove":
            if len(sys.argv) != 3:
                log("Uso: faugus_games.py remove <title>")
                sys.exit(1)
            status, prefixos = remove_by_title(sys.argv[2])
            print(status)
            for p in prefixos:
                print(p)
        else:
            log(f"Ação desconhecida: {acao}")
            sys.exit(1)
    except FaugusGamesError as e:
        log(f"ERRO: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
