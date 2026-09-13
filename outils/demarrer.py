# -*- coding: utf-8 -*-
"""
Point d'entree du paquet autonome de Plume.

Un seul executable joue plusieurs roles, choisis par le premier argument. Une
fois compile, il n'y a plus d'interpreteur Python separe sur la machine : pour
lancer streamlink en sous-processus, Plume se relance donc lui-meme avec le
role voulu.

  Plume.exe                    le navigateur
  Plume.exe --recherche        l'interface de recherche video
  Plume.exe --streamlink ...   streamlink, appele par le lecteur
  Plume.exe --ytdlp ...        yt-dlp, en secours si l'exe fourni manque
"""
import os
import sys
from pathlib import Path


def dossier_paquet():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def main():
    base = dossier_paquet()
    # le code de Plume et les outils voyagent a cote de l'executable
    sys.path.insert(0, str(base))
    os.environ.setdefault("PLUME_RACINE", str(base))

    externes = base / "outils-externes"
    if externes.is_dir():
        os.environ["PATH"] = str(externes) + os.pathsep + os.environ.get("PATH", "")

    role = sys.argv[1] if len(sys.argv) > 1 else ""

    if role == "--streamlink":
        del sys.argv[1]
        from streamlink_cli.main import main as streamlink_main
        return streamlink_main()

    if role == "--ytdlp":
        del sys.argv[1]
        from yt_dlp import main as ytdlp_main
        return ytdlp_main()

    if role == "--recherche":
        del sys.argv[1]
        import plume
        return plume.Plume().mainloop()

    import navigateur
    return navigateur.main()


def signaler_panne(erreur):
    """Sans console, une erreur au demarrage serait totalement muette."""
    import traceback
    texte = "".join(traceback.format_exception(
        type(erreur), erreur, erreur.__traceback__))
    try:
        chemin = dossier_paquet() / "erreur-demarrage.txt"
        chemin.write_text(texte, encoding="utf-8")
    except Exception:
        chemin = "(fichier non ecrit)"
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None,
            "Plume n'a pas pu demarrer.\n\n%s\n\nDetail complet dans :\n%s"
            % (str(erreur)[:400], chemin),
            "Plume", 0x10)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except SystemExit:
        raise
    except BaseException as e:
        signaler_panne(e)
        sys.exit(1)
