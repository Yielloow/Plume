# -*- coding: utf-8 -*-
"""Rend la barre de commandes dans des images, pour juger le dessin.

Pourquoi cet outil plutot qu'une capture d'ecran : une capture compose mal les
surfaces de mpv et de WebView2, une interface parfaitement opaque y ressort
delavee, et on s'y est deja laisse prendre deux fois. mpv, lui, sait se
capturer lui-meme avec `screenshot-to-file ... window`, ce qui restitue
exactement ce qu'il dessine, OSD compris.

La source est une mire generee par FFmpeg : aucun reseau, aucune dependance a
YouTube, et une duree connue pour que la ligne de temps ait un sens.

Usage : python outils\\apercu_barre.py [dossier de sortie]
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import core  # noqa: E402

TUYAU = r"\\.\pipe\plume-apercu"
DUREE = 30


def encoder_mire(chemin):
    """Fabrique un clip de test, une seule fois."""
    if chemin.exists():
        return True
    chemin.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [core.MPV, "--no-config", "av://lavfi:testsrc2=size=1280x720",
         "--length=%d" % DUREE, "--of=mp4", "--o=" + str(chemin)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=core.CREATE_NO_WINDOW)
    if not chemin.exists():
        print("echec de l'encodage de la mire :")
        print((r.stdout + r.stderr)[-800:])
        return False
    return True


class Pilote:
    def __init__(self, tube):
        self.tube = tube

    def envoyer(self, commande):
        self.tube.write((json.dumps({"command": commande}) + "\n")
                        .encode("utf-8"))
        time.sleep(0.12)

    def message(self, *args):
        self.envoyer(["script-message", "plume-test"] + [str(a) for a in args])

    def capturer(self, chemin):
        self.envoyer(["screenshot-to-file", str(chemin), "window"])
        for _ in range(40):
            time.sleep(0.1)
            if chemin.exists() and chemin.stat().st_size > 0:
                return True
        return False


def apercu(sortie):
    sortie.mkdir(parents=True, exist_ok=True)
    mire = sortie / "mire.mp4"
    if not encoder_mire(mire):
        return False

    args = [
        core.MPV, "--no-config", str(mire),
        "--osc=no",
        "--script=" + str(RACINE / "osc.lua"),
        "--script-opts=plume-toujours=yes,plume-qualite=1080,plume-fps=60",
        "--input-ipc-server=" + TUYAU,
        "--geometry=1280x720+60+60",
        "--pause=yes", "--start=40%", "--volume=65",
        "--osd-bar=no", "--keep-open=yes",
    ]
    mpv = subprocess.Popen(args, creationflags=core.CREATE_NO_WINDOW)

    tube = None
    for _ in range(80):
        if mpv.poll() is not None:
            print("mpv s'est arrete tout de suite")
            return False
        try:
            tube = open(TUYAU, "r+b", buffering=0)
            break
        except OSError:
            time.sleep(0.25)
    if not tube:
        mpv.kill()
        print("tube IPC jamais apparu")
        return False

    faites = []
    try:
        p = Pilote(tube)
        time.sleep(1.2)

        vues = [
            ("barre.png", lambda: p.message("souris", -1, -1)),
            ("barre-survol-temps.png", lambda: p.message("souris", 760, 667)),
            ("menu-qualite.png", lambda: (p.message("souris", -1, -1),
                                          p.message("menu", "qualite", 1010))),
            ("menu-vitesse.png", lambda: (p.message("menu", "vitesse", 1180),)),
            ("menu-audio.png", lambda: (p.message("menu", "audio", 1100),)),
        ]
        for nom, preparer in vues:
            preparer()
            time.sleep(0.35)
            chemin = sortie / nom
            if chemin.exists():
                chemin.unlink()
            if p.capturer(chemin):
                faites.append(chemin)
                print("  %-26s %6.1f Ko" % (nom, chemin.stat().st_size / 1024))
            else:
                print("  %-26s ECHEC" % nom)
    finally:
        try:
            tube.close()
        except Exception:
            pass
        mpv.terminate()
        try:
            mpv.wait(timeout=5)
        except Exception:
            mpv.kill()

    return len(faites) > 0


if __name__ == "__main__":
    dossier = Path(sys.argv[1]) if len(sys.argv) > 1 else (RACINE / "apercu")
    print("apercu de la barre dans %s" % dossier)
    sys.exit(0 if apercu(dossier) else 1)
