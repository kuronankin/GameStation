#!/usr/bin/env python3

import sys
import tkinter as tk


if len(sys.argv) < 2:
    sys.exit(1)

IMAGE_PATH = sys.argv[1]


# ============================================================
# CRIA JANELA
# ============================================================

root = tk.Tk()

root.overrideredirect(True)
root.configure(bg="black")


# ============================================================
# DESCOBRE RESOLUÇÃO DA TELA
# ============================================================

screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()


# ============================================================
# FORÇA A JANELA A OCUPAR A TELA INTEIRA
# ============================================================

root.geometry(
    f"{screen_width}x{screen_height}+0+0"
)

root.minsize(screen_width, screen_height)
root.maxsize(screen_width, screen_height)

root.attributes("-topmost", True)


# ============================================================
# CARREGA PNG
# ============================================================

try:
    image = tk.PhotoImage(file=IMAGE_PATH)
except Exception as e:
    print("Erro ao carregar background:", e)
    root.destroy()
    sys.exit(1)


# ============================================================
# TAMANHO DA IMAGEM
# ============================================================

image_width = image.width()
image_height = image.height()


# ============================================================
# CENTRALIZA A IMAGEM
# ============================================================

x = (screen_width - image_width) // 2
y = (screen_height - image_height) // 2


# ============================================================
# IMAGEM
# ============================================================

label = tk.Label(
    root,
    image=image,
    bg="black",
    bd=0,
    highlightthickness=0
)

label.place(
    x=x,
    y=y
)


# ============================================================
# MANTÉM NO TOPO
# ============================================================

def manter_no_topo():

    try:
        root.attributes("-topmost", True)
        root.lift()
        root.after(100, manter_no_topo)

    except tk.TclError:
        pass


# ============================================================
# MOSTRA
# ============================================================

root.update_idletasks()

root.lift()
root.attributes("-topmost", True)

root.after(100, manter_no_topo)

root.mainloop()
