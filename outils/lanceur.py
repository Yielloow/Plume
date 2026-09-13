# -*- coding: utf-8 -*-
"""
Plume.exe : lanceur.

Il ne fait qu'une chose, demarrer le navigateur avec pythonw, sans aucune
fenetre de console. Le code de Plume reste donc des fichiers .py modifiables : pas
besoin de tout recompiler pour changer une couleur ou un reglage.

Cherche l'interpreteur dans cet ordre : celui enregistre a la compilation, le
PATH, puis les emplacements habituels d'installation.
"""
import os
import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000
PYTHON_CONNU = r"C:\Users\Fabian\AppData\Local\Programs\Python\Python310\pythonw.exe"


def dossier_application():
    """Dossier de l'exe une fois compile, du script sinon."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def trouver_python():
    candidats = [PYTHON_CONNU]

    chemin_env = os.environ.get("PATH", "")
    for repertoire in chemin_env.split(os.pathsep):
        if repertoire.strip():
            candidats.append(os.path.join(repertoire.strip(), "pythonw.exe"))

    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        base = os.path.join(local, "Programs", "Python")
        if os.path.isdir(base):
            for nom in sorted(os.listdir(base), reverse=True):
                candidats.append(os.path.join(base, nom, "pythonw.exe"))

    for version in ("313", "312", "311", "310", "39"):
        candidats.append(r"C:\Python%s\pythonw.exe" % version)

    for c in candidats:
        if c and os.path.isfile(c):
            return c
    return None


def alerter(message):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "Plume", 0x10)
    except Exception:
        print(message)


def main():
    base = dossier_application()
    script = os.path.join(base, "navigateur.py")
    if not os.path.isfile(script):
        return alerter("navigateur.py est introuvable dans :\n%s\n\n"
                       "Placez Plume.exe dans le dossier de l'application." % base)

    interpreteur = trouver_python()
    if not interpreteur:
        return alerter("Python est introuvable sur cette machine.\n\n"
                       "Plume a besoin de Python 3.10 ou plus recent.")

    try:
        subprocess.Popen([interpreteur, script], cwd=base,
                         creationflags=CREATE_NO_WINDOW,
                         close_fds=True)
    except Exception as e:
        alerter("Le lancement a echoue :\n%s" % e)


if __name__ == "__main__":
    main()
