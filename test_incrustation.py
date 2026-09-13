# -*- coding: utf-8 -*-
"""Test isole de l'incrustation : mpv doit dessiner dans la fenetre tkinter."""
import ctypes
import sys
import tkinter as tk
from ctypes import wintypes

import core
import incrustation

user32 = ctypes.WinDLL("user32", use_last_error=True)


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=V6wWEx9nY_0"

    racine = tk.Tk()
    racine.title("Test incrustation Plume")
    racine.geometry("1000x640")
    racine.configure(bg="#12131a")

    tk.Label(racine, text="La video doit apparaitre dans le cadre ci-dessous",
             bg="#12131a", fg="#e6e8ef", font=("Segoe UI", 11)).pack(pady=10)

    zone = tk.Frame(racine, bg="#000000", width=880, height=495)
    zone.pack()
    zone.pack_propagate(False)

    info = tk.Label(racine, text="", bg="#12131a", fg="#9aa0b4",
                    font=("Consolas", 9), justify="left")
    info.pack(pady=10)

    racine.update()   # les fenetres doivent exister avant de chercher leur handle

    lignes = []
    inc = incrustation.Incrustation(parent=racine.winfo_id())

    trouvee = incrustation.fenetre_du_processus()
    lignes.append("fenetre_du_processus() -> %s" % trouvee)
    lignes.append("winfo_id() de la racine  -> %s" % racine.winfo_id())
    lignes.append("winfo_id() du cadre      -> %s" % zone.winfo_id())

    ok = inc._assurer_conteneur()
    lignes.append("_assurer_conteneur()     -> %s" % ok)
    lignes.append("parent retenu            -> %s" % inc.parent)
    lignes.append("conteneur cree           -> %s" % inc.conteneur)
    lignes.append("erreur Win32             -> %s" % ctypes.get_last_error())

    if ok:
        r = inc.demarrer(url, "Test")
        lignes.append("demarrer()               -> %s" % r)

        def suivre():
            # place le conteneur sur le cadre noir, en coordonnees de la racine
            x = zone.winfo_rootx() - racine.winfo_rootx()
            y = zone.winfo_rooty() - racine.winfo_rooty()
            inc.placer(x, y, zone.winfo_width(), zone.winfo_height())
            racine.after(150, suivre)

        suivre()

    info.configure(text="\n".join(lignes))
    print("\n".join(lignes))

    racine.protocol("WM_DELETE_WINDOW", lambda: (inc.detruire(), racine.destroy()))
    racine.mainloop()


if __name__ == "__main__":
    main()
