#!/usr/bin/env python3
"""
app.py - GameStation (janela nativa via pywebview)

Abre a interface (index.html) numa janela nativa de verdade (Qt, no
Linux) — sem navegador, sem servidor HTTP. O JavaScript da página
conversa direto com os métodos desta classe Api via
`pywebview.api.<metodo>(...)`.

Uso: python3 app.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import webview

GAMESTATION_DIR = "/mnt/GameStation"
SYSTEM_DIR = os.path.join(GAMESTATION_DIR, "system")
MEDIA_DIR = os.path.join(GAMESTATION_DIR, "media")
DADOS_JSON = os.path.join(MEDIA_DIR, "dados.json")
UNINSTALL_DIR = os.path.join(GAMESTATION_DIR, "games", "uninstall")
FAUGUS_INSTALL_DIR = os.path.join(GAMESTATION_DIR, "faugus")
FAUGUS_RUNNER = "Proton-GE Latest"
LOG_ULTIMO_JOGO = "/tmp/gamestation_ultimo_jogo.log"

sys.path.insert(0, SYSTEM_DIR)
import importlib
gerar_dados = importlib.import_module("gerar-dados")


class Api:
    """
    Métodos expostos pro JavaScript da página chamar diretamente,
    via `pywebview.api.<metodo>(...)` — sem precisar de servidor
    HTTP nem porta de rede, é uma ponte direta.
    """

    def ler_imagem_base64(self, caminho):
        """
        Lê uma imagem local e devolve como data URI base64 — usado
        pelo index.html pra mostrar imagens de fora da pasta system/
        (ex: screenshot baixada em games/.../media/). Motores tipo
        Qt/Chromium bloqueiam file:// entre pastas diferentes por
        segurança; base64 embutido direto no CSS/JS contorna isso
        de vez, sem depender de configuração obscura do navegador.
        """
        import base64
        import mimetypes

        try:
            tipo_mime, _ = mimetypes.guess_type(caminho)
            if not tipo_mime:
                tipo_mime = "image/jpeg"

            with open(caminho, "rb") as f:
                dados = f.read()

            b64 = base64.b64encode(dados).decode("ascii")
            return f"data:{tipo_mime};base64,{b64}"
        except Exception as erro:
            print(f"[app.py] Falha ao ler imagem '{caminho}': {erro}")
            return None

    def __init__(self):
        self._janela = None

    def definir_janela(self, janela):
        self._janela = janela

    def carregar_dados(self):
        """
        Lê o dados.json (gerado pelo gerar-dados.py) e devolve pro
        JavaScript. Se o arquivo ainda não existir, devolve uma
        estrutura vazia em vez de quebrar.
        """
        if not os.path.isfile(DADOS_JSON):
            return {"categorias": []}

        with open(DADOS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)

    def obter_timestamp_dados(self):
        """
        Devolve a última modificação do dados.json — o JavaScript
        confere isso periodicamente pra saber se precisa recarregar
        (ex: depois que o autoplay.sh regenera o arquivo ao inserir/
        remover disco), sem precisar fechar/reabrir a janela toda.
        """
        if not os.path.isfile(DADOS_JSON):
            return None
        return os.path.getmtime(DADOS_JSON)

    def abrir_jogo(self, comando):
        """
        Executa de verdade o comando de launch de um jogo — o mesmo
        comando que o gerar-dados.py já monta a partir do
        emulators.txt, só que agora rodado pelo Python em vez de
        escrito num metadata.pegasus.txt.

        A saída (stdout+stderr) vai pra um arquivo de log fixo, em
        vez de ser descartada — sem isso, qualquer falha no meio do
        caminho (Faugus, gamescope, emulador) acontece em silêncio
        total, sem jeito nenhum de diagnosticar depois.
        """
        try:
            with open(LOG_ULTIMO_JOGO, "w", encoding="utf-8") as arquivo_log:
                subprocess.Popen(
                    comando,
                    shell=True,
                    stdout=arquivo_log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            return {"sucesso": True}
        except Exception as erro:
            return {"sucesso": False, "erro": str(erro)}

    def _capturar_janelas(self):
        try:
            resultado = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=5)
            return {linha.split()[0] for linha in resultado.stdout.strip().split("\n") if linha.strip()}
        except Exception:
            return set()

    def _esperar_janela_nova(self, janelas_antes, limite_segundos=60):
        tempo = 0
        while tempo < limite_segundos:
            if self._capturar_janelas() - janelas_antes:
                return True
            time.sleep(1)
            tempo += 1
        return False

    def abrir_jogo_pc(self, comando):
        """
        Versão BLOQUEANTE de abrir_jogo — usada só pra jogos de PC
        (Faugus/Steam). Sem tela de carregamento em fullscreen (a
        barra de progresso da própria interface já cobre esse papel
        agora) — só espera uma janela nova aparecer (ou um tempo
        limite) antes de devolver o controle pro JavaScript, que aí
        esconde a barra.
        """
        janelas_antes = self._capturar_janelas()

        try:
            with open(LOG_ULTIMO_JOGO, "w", encoding="utf-8") as arquivo_log:
                subprocess.Popen(
                    comando,
                    shell=True,
                    stdout=arquivo_log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        except Exception as erro:
            return {"sucesso": False, "erro": str(erro)}

        encontrou = self._esperar_janela_nova(janelas_antes, 60)
        if not encontrou:
            print("[app.py] abrir_jogo_pc: nenhuma janela nova detectada em 60s — veja o log.")

        return {"sucesso": True}

    def _extrair_caminho_original(self, comando_launch):
        """
        O campo 'launch' de cada jogo é o comando de execução inteiro
        (ex: '/mnt/.../launcher.sh "/caminho/do/arquivo.zip"') — pega
        só o caminho do arquivo de dentro das aspas.
        """
        resultado = re.search(r'"([^"]+)"', comando_launch or "")
        return resultado.group(1) if resultado else None

    def instalar_jogo(self, jogo):
        """
        Instala um jogo do Disc-Loader pra dentro da Library (SSD).

        - PC .zip (Faugus): cria um atalho .sh que chama o
          faugus_launch.sh (novo — extrai/registra na hora que o
          jogo for aberto pela primeira vez, não agora). Guarda
          também um .json do lado com os dados que a desinstalação
          vai precisar depois (mais robusto que gravar comentário
          dentro do .sh, que já deu problema).
        - PC .txt (Steam): cria atalho .sh + .json igual antes.
        - Emulado: copia TODOS os arquivos que compartilham o mesmo
          nome base do arquivo principal (ex: Jogo.cue + Jogo.bin).
        """
        sistema = jogo.get("sistema", "")
        nome = jogo.get("nome", "jogo")
        caminho_original = self._extrair_caminho_original(jogo.get("launch", ""))

        if not caminho_original or not os.path.exists(caminho_original):
            return {"sucesso": False, "mensagem": "Arquivo original não encontrado (disco ainda conectado?)."}

        pasta_ssd_sistema = os.path.join(GAMESTATION_DIR, "games", "ssd", sistema)

        try:
            os.makedirs(pasta_ssd_sistema, exist_ok=True)

            if sistema == "pc":
                extensao = os.path.splitext(caminho_original)[1].lower()
                nome_base = os.path.splitext(os.path.basename(caminho_original))[0]
                caminho_shortcut = os.path.join(pasta_ssd_sistema, f"{nome_base}.sh")
                caminho_manifesto = os.path.join(pasta_ssd_sistema, f"{nome_base}.json")

                if extensao == ".txt":
                    with open(caminho_original, "r", encoding="utf-8") as f:
                        conteudo_txt = f.read()

                    # Formato real do arquivo é shell (APPID=123456),
                    # não só o número puro — confirmado olhando o
                    # steam-launch.sh existente, que faz "source"
                    # nesse arquivo.
                    match_appid = re.search(r"APPID\s*=\s*(\d+)", conteudo_txt)
                    if not match_appid:
                        return {"sucesso": False, "mensagem": f"'{caminho_original}' não tem um APPID válido (esperado: APPID=123456)."}
                    appid = match_appid.group(1)

                    conteudo_sh = (
                        "#!/bin/bash\n"
                        f'exec "{SYSTEM_DIR}/steam_abrir.sh" "{appid}"\n'
                    )
                    manifesto = {"tipo": "steam", "nome": nome_base, "appid": appid}

                    os.makedirs(UNINSTALL_DIR, exist_ok=True)
                    caminho_uninstall_sh = os.path.join(UNINSTALL_DIR, f"{nome_base}.sh")
                    conteudo_uninstall = (
                        "#!/bin/bash\n"
                        f'"{SYSTEM_DIR}/steam_uninstalar.sh" "{appid}"\n'
                        f'rm -f "{caminho_shortcut}"\n'
                        f'rm -f "{caminho_manifesto}"\n'
                        f'rm -f "{caminho_uninstall_sh}"\n'
                    )
                    with open(caminho_uninstall_sh, "w", encoding="utf-8") as f:
                        f.write(conteudo_uninstall)
                    os.chmod(caminho_uninstall_sh, 0o755)

                elif extensao == ".zip":
                    # Extrai e registra no Faugus AGORA (o disco está
                    # garantidamente conectado nesse momento, já que
                    # é o próprio Install rodando) — evita a
                    # complexidade de "e se o disco não estiver mais
                    # lá na próxima vez".
                    resultado_extrair = subprocess.run(
                        ["python3", os.path.join(SYSTEM_DIR, "faugus_extrair.py"), nome_base, caminho_original],
                        capture_output=True, text=True, timeout=300,
                    )
                    if resultado_extrair.returncode != 0:
                        return {
                            "sucesso": False,
                            "mensagem": f"Falha ao instalar: {resultado_extrair.stderr.strip() or 'erro desconhecido'}",
                        }
                    gameid = resultado_extrair.stdout.strip().split("\n")[-1]

                    # Atalho na Library — só abre (já está tudo pronto,
                    # não precisa mais checar/extrair nada).
                    conteudo_sh = (
                        "#!/bin/bash\n"
                        f'exec "{SYSTEM_DIR}/faugus_abrir.sh" "{gameid}"\n'
                    )
                    manifesto = {"tipo": "faugus", "nome": nome_base, "gameid": gameid}

                    # Uninstaller de verdade em games/uninstall/ — apaga
                    # a pasta extraída, remove do Faugus, E apaga os
                    # atalhos da Library e dele mesmo.
                    os.makedirs(UNINSTALL_DIR, exist_ok=True)
                    caminho_uninstall_sh = os.path.join(UNINSTALL_DIR, f"{nome_base}.sh")
                    pasta_faugus_jogo = os.path.join(FAUGUS_INSTALL_DIR, nome_base)
                    conteudo_uninstall = (
                        "#!/bin/bash\n"
                        f'python3 "{SYSTEM_DIR}/faugus_games.py" remove "{nome_base}"\n'
                        f'rm -rf "{pasta_faugus_jogo}"\n'
                        f'rm -f "{caminho_shortcut}"\n'
                        f'rm -f "{caminho_manifesto}"\n'
                        f'rm -f "{caminho_uninstall_sh}"\n'
                    )
                    with open(caminho_uninstall_sh, "w", encoding="utf-8") as f:
                        f.write(conteudo_uninstall)
                    os.chmod(caminho_uninstall_sh, 0o755)

                else:
                    return {"sucesso": False, "mensagem": f"Extensão de PC não suportada: {extensao}"}

                with open(caminho_shortcut, "w", encoding="utf-8") as f:
                    f.write(conteudo_sh)
                os.chmod(caminho_shortcut, 0o755)

                with open(caminho_manifesto, "w", encoding="utf-8") as f:
                    json.dump(manifesto, f)
                # Nada de rodar agora — extração/registro (Faugus) ou
                # abertura (Steam) só acontece quando o jogo for
                # aberto de verdade pela Library depois.

            else:
                pasta_origem = os.path.dirname(caminho_original)
                nome_base_arquivo = os.path.splitext(os.path.basename(caminho_original))[0]

                arquivos_copiados = []
                for nome_arquivo in os.listdir(pasta_origem):
                    nome_base_atual = os.path.splitext(nome_arquivo)[0]
                    if nome_base_atual == nome_base_arquivo:
                        origem = os.path.join(pasta_origem, nome_arquivo)
                        if os.path.isfile(origem):
                            destino = os.path.join(pasta_ssd_sistema, nome_arquivo)
                            shutil.copy2(origem, destino)
                            arquivos_copiados.append(nome_arquivo)

                if not arquivos_copiados:
                    return {"sucesso": False, "mensagem": "Nenhum arquivo encontrado pra copiar."}

        except Exception as erro:
            return {"sucesso": False, "mensagem": f"Falha ao instalar: {erro}"}

        try:
            gerar_dados.main()
        except Exception as erro:
            print(f"[app.py] Falha ao regenerar dados.json após instalar: {erro}")

        return {"sucesso": True, "mensagem": f'"{nome}" instalado na Library.'}

    def desinstalar_jogo(self, jogo):
        """
        Desinstala um jogo da Library. Lê o manifesto .json (mesmo
        nome do .sh, salvo na hora do Install) pra saber o tipo —
        muito mais confiável que ler comentário dentro do .sh, que
        já deu problema antes.

        - Emulado: apaga a ROM (e qualquer arquivo companheiro com o
          mesmo nome base, ex: .cue+.bin) direto.
        - PC/Faugus: apaga a pasta extraída em GameStation/faugus/ E
          remove o registro no games.json do Faugus (via
          faugus_games.py remove, chamado direto — sem depender de
          script externo intermediário).
        - PC/Steam: a Steam no Linux não tem uma forma confiável de
          desinstalar via comando externo (confirmado — nem a
          própria Steam garante isso). Por enquanto só abrimos a
          Steam e avisamos o usuário pra terminar manualmente lá
          dentro.
        """
        sistema = jogo.get("sistema", "")
        nome = jogo.get("nome", "jogo")
        caminho_arquivo = self._extrair_caminho_original(jogo.get("launch", ""))

        if not caminho_arquivo or not os.path.isfile(caminho_arquivo):
            return {"sucesso": False, "mensagem": "Arquivo não encontrado."}

        try:
            if sistema == "pc" and caminho_arquivo.endswith(".sh"):
                caminho_manifesto = os.path.splitext(caminho_arquivo)[0] + ".json"
                manifesto = {}
                if os.path.isfile(caminho_manifesto):
                    with open(caminho_manifesto, "r", encoding="utf-8") as f:
                        manifesto = json.load(f)

                tipo = manifesto.get("tipo")
                nome_manifesto = manifesto.get("nome", nome)

                if tipo == "steam":
                    caminho_uninstall_sh = os.path.join(UNINSTALL_DIR, f"{nome_manifesto}.sh")
                    if os.path.isfile(caminho_uninstall_sh):
                        # Não bloqueia esperando terminar — abrir a
                        # Steam (se ainda não estiver) + processar o
                        # uninstall pode levar um tempo, e isso
                        # acontece em segundo plano, não precisa
                        # travar a interface esperando.
                        subprocess.Popen(
                            ["bash", caminho_uninstall_sh],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True,
                        )
                    else:
                        os.remove(caminho_arquivo)
                        if os.path.isfile(caminho_manifesto):
                            os.remove(caminho_manifesto)
                    return {
                        "sucesso": True,
                        "mensagem": f'Removendo "{nome}" — abrindo a Steam se necessário, pode levar alguns segundos.',
                    }

                elif tipo == "faugus":
                    # O .sh em games/uninstall/ já faz TUDO (apaga a
                    # pasta extraída, remove do Faugus, apaga os
                    # atalhos) — só chama ele, sem duplicar a lógica
                    # aqui.
                    caminho_uninstall_sh = os.path.join(UNINSTALL_DIR, f"{nome_manifesto}.sh")
                    if os.path.isfile(caminho_uninstall_sh):
                        resultado = subprocess.run(
                            ["bash", caminho_uninstall_sh],
                            capture_output=True, text=True, timeout=60,
                        )
                        print(f"[app.py] uninstall .sh código de saída: {resultado.returncode}")
                        print(f"[app.py] uninstall .sh saída:\n{resultado.stdout}\n{resultado.stderr}")
                    else:
                        # Uninstaller não existe por algum motivo —
                        # ainda assim limpa o que dá pra limpar direto,
                        # pra não deixar lixo pra trás.
                        pasta_faugus = os.path.join(FAUGUS_INSTALL_DIR, nome_manifesto)
                        if os.path.isdir(pasta_faugus):
                            shutil.rmtree(pasta_faugus, ignore_errors=True)
                        os.remove(caminho_arquivo)
                        if os.path.isfile(caminho_manifesto):
                            os.remove(caminho_manifesto)

                    return {"sucesso": True, "mensagem": f'"{nome}" desinstalado (Faugus).'}

                else:
                    os.remove(caminho_arquivo)
                    if os.path.isfile(caminho_manifesto):
                        os.remove(caminho_manifesto)
                    return {"sucesso": True, "mensagem": f'"{nome}" removido.'}

            else:
                pasta = os.path.dirname(caminho_arquivo)
                nome_base = os.path.splitext(os.path.basename(caminho_arquivo))[0]
                for nome_arquivo in os.listdir(pasta):
                    if os.path.splitext(nome_arquivo)[0] == nome_base:
                        try:
                            os.remove(os.path.join(pasta, nome_arquivo))
                        except OSError:
                            pass
                return {"sucesso": True, "mensagem": f'"{nome}" desinstalado.'}

        except Exception as erro:
            return {"sucesso": False, "mensagem": f"Falha ao desinstalar: {erro}"}
        finally:
            try:
                gerar_dados.main()
            except Exception as erro:
                print(f"[app.py] Falha ao regenerar dados.json após desinstalar: {erro}")

    def obter_espaco_disco(self):
        """
        Devolve o espaço em disco (total/usado/livre, em bytes) da
        partição onde o GameStation está montado — usado pelo
        Storage Manager pra mostrar a barra de espaço.
        """
        try:
            total, usado, livre = shutil.disk_usage(GAMESTATION_DIR)
            return {"total": total, "usado": usado, "livre": livre}
        except Exception as erro:
            print(f"[app.py] Falha ao obter espaço em disco: {erro}")
            return None

    def alternar_tela_cheia(self):
        """Chamado pelo Alt+Enter do lado do JavaScript."""
        if self._janela is not None:
            self._janela.toggle_fullscreen()
        return {"sucesso": True}

    def sair_para_desktop(self):
        if self._janela is not None:
            self._janela.destroy()

    def reiniciar_sistema(self):
        subprocess.Popen(["systemctl", "reboot"])

    def desligar_sistema(self):
        subprocess.Popen(["systemctl", "poweroff"])


def main():
    # Regrava dados.json do zero toda vez que o app abre — mesma
    # lógica que já usávamos no pegasus-launcher.sh (nunca depender
    # de lembrar de rodar um script separado antes).
    try:
        gerar_dados.main()
    except Exception as erro:
        print(f"[app.py] Falha ao gerar dados.json: {erro}")

    api = Api()

    caminho_html = os.path.join(SYSTEM_DIR, "index.html")

    janela = webview.create_window(
        "GameStation",
        caminho_html,
        js_api=api,
        fullscreen=True,
        frameless=False,
    )
    api.definir_janela(janela)

    webview.start()


if __name__ == "__main__":
    main()
