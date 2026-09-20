#!/usr/bin/env python3
# find_exe.py
# Uso: find_exe.py <pasta_do_jogo>
# Imprime (stdout, 1 linha) o caminho absoluto do executável escolhido.
#
# PRIORIDADE 1: se existir um arquivo chamado exatamente
# "GameStation-launch.bat" em algum lugar da pasta, ele é usado direto,
# sem passar pela heurística nenhuma — é o usuário dizendo explicitamente
# qual é o executável certo (útil pra jogos onde a heurística erraria,
# ex: jogos Unity com UnityCrashHandler64.exe maior que o próprio jogo).
#
# PRIORIDADE 2 (se não houver o .bat): heurística de sempre.

import sys
import os
import re

NOME_BAT_EXPLICITO = "gamestation-launch.bat"

PASTAS_IGNORADAS = re.compile(
    r"(?i)(^|/)(_commonredist|redist|redistributables?|__installer|"
    r"directx|dotnet|vcredist)(/|$)"
)

NOMES_IGNORADOS = re.compile(
    r"(?i)^("
    r"unins.*|"
    r"setup.*|"
    r".*redist.*|"
    r"dxsetup.*|"
    r"dotnetfx.*|"
    r"vcredist.*|"
    r"directx.*|"
    r"oalinst.*|"
    r".*crashreport.*|"
    r".*crashpad.*handler.*|"
    r"unitycrashhandler.*|"
    r"vc_redist.*|"
    r"physxinstall.*|"
    r"ue4prereqsetup.*|"
    r"ueprereqsetup.*"
    r")\.exe$"
)


def buscar_bat_explicito(pasta_raiz):
    for dirpath, dirnames, filenames in os.walk(pasta_raiz):
        for nome in filenames:
            if nome.lower() == NOME_BAT_EXPLICITO:
                return os.path.join(dirpath, nome)
    return None


def listar_exes(pasta_raiz):
    candidatos = []
    for dirpath, dirnames, filenames in os.walk(pasta_raiz):
        rel_dir = os.path.relpath(dirpath, pasta_raiz)
        for nome in filenames:
            if nome.lower().endswith(".exe"):
                caminho_rel = os.path.normpath(os.path.join(rel_dir, nome)) if rel_dir != "." else nome
                caminho_abs = os.path.join(dirpath, nome)
                try:
                    tamanho = os.path.getsize(caminho_abs)
                except OSError:
                    tamanho = 0
                profundidade = caminho_rel.count(os.sep)
                candidatos.append({
                    "abs": caminho_abs,
                    "rel": caminho_rel,
                    "nome": nome,
                    "tamanho": tamanho,
                    "profundidade": profundidade,
                })
    return candidatos


def escolher_exe(pasta_raiz):
    todos = listar_exes(pasta_raiz)
    if not todos:
        return None, []

    filtrados = [
        c for c in todos
        if not PASTAS_IGNORADAS.search(c["rel"].replace(os.sep, "/"))
        and not NOMES_IGNORADOS.match(c["nome"])
    ]

    avisos = []
    pool = filtrados if filtrados else todos
    if not filtrados:
        avisos.append(
            "todos os .exe encontrados bateram com o filtro de exclusão; "
            "usando o maior .exe sem filtro como último recurso — CONFIRA MANUALMENTE."
        )

    pool_ordenado = sorted(pool, key=lambda c: (c["profundidade"], -c["tamanho"]))
    escolhido = pool_ordenado[0]

    if len(pool_ordenado) > 1:
        segundo = pool_ordenado[1]
        if segundo["profundidade"] == escolhido["profundidade"]:
            avisos.append(
                f"mais de um .exe candidato na mesma profundidade "
                f"('{escolhido['rel']}' vs '{segundo['rel']}'); escolhido o maior "
                "em tamanho — confira se é o certo."
            )

    return escolhido, avisos


def main():
    if len(sys.argv) != 2:
        print("Uso: find_exe.py <pasta_do_jogo>", file=sys.stderr)
        sys.exit(1)

    pasta = sys.argv[1]
    if not os.path.isdir(pasta):
        print(f"ERRO: pasta não encontrada: {pasta}", file=sys.stderr)
        sys.exit(1)

    bat_explicito = buscar_bat_explicito(pasta)
    if bat_explicito:
        print(f"AVISO: usando {NOME_BAT_EXPLICITO} encontrado — pulando a heurística de .exe.", file=sys.stderr)
        print(bat_explicito)
        return

    escolhido, avisos = escolher_exe(pasta)
    if escolhido is None:
        print(f"ERRO: nenhum arquivo .exe encontrado em {pasta}", file=sys.stderr)
        sys.exit(1)

    for aviso in avisos:
        print(f"AVISO: {aviso}", file=sys.stderr)

    print(escolhido["abs"])


if __name__ == "__main__":
    main()
