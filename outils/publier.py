# -*- coding: utf-8 -*-
"""Verifie qu'une version est publiable, et dit ce qu'il reste a faire.

Ne publie rien tout seul : creer une Release et pousser sur un depot public
sont des gestes qui engagent, ils restent a la main. Ce script s'assure que ce
qui va partir est coherent, ce qu'on ne voit pas a l'oeil : une empreinte
recalculee apres une reconstruction oubliee, un numero de version qui ne
correspond plus au fichier, un profil qui aurait glisse dans le depot.

Usage :  python outils\\publier.py
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import core  # noqa: E402

PAQUET = RACINE.parent / "Plume-paquet"
MANIFESTE = RACINE / "docs" / "version.json"
DEPOT = "Plume-nav/plume"

sorties = []


def dire(nom, ok, detail=""):
    sorties.append(ok)
    print("  %-52s %-4s %s" % (nom, "OK" if ok else "RATE", detail))


def empreinte(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def main():
    print("Version %s, depot %s" % (core.VERSION, DEPOT))
    print()

    dire("le manifeste existe", MANIFESTE.exists(), str(MANIFESTE))
    if not MANIFESTE.exists():
        return 1
    m = json.loads(MANIFESTE.read_text(encoding="utf-8"))

    dire("le manifeste porte la version du code",
         m.get("version") == core.VERSION,
         "manifeste %s, core.py %s" % (m.get("version"), core.VERSION))

    installeur = PAQUET / ("Plume-%s-installeur.exe" % core.VERSION)
    dire("l'installeur de cette version est construit", installeur.exists(),
         installeur.name)
    if not installeur.exists():
        print("\n  -> python outils\\construire.py")
        return 1

    reelle = empreinte(installeur)
    dire("l'empreinte du manifeste est celle du fichier",
         reelle == m.get("sha256"),
         "sinon le site ferait rejeter un fichier sain")
    if reelle != m.get("sha256"):
        print("     fichier   : %s" % reelle)
        print("     manifeste : %s" % m.get("sha256"))
        print("\n  -> reconstruire : python outils\\construire.py")

    dire("l'adresse de telechargement vise le bon depot",
         DEPOT in m.get("url", "") and core.VERSION in m.get("url", ""),
         m.get("url", ""))

    dire("Plume sait ou chercher ses mises a jour",
         bool(core.CONFIG.get("manifeste_maj")),
         core.CONFIG.get("manifeste_maj") or "reglage vide")

    # Le point qui ne pardonne pas : un depot public garde son historique.
    ignore = RACINE / ".gitignore"
    dire("le profil est exclu du depot",
         ignore.exists() and "profil/" in ignore.read_text(encoding="utf-8"),
         "il contient la session Google en clair")

    suivis = ""
    try:
        suivis = subprocess.run(
            ["git", "-C", str(RACINE), "ls-files", "profil", "cookies.txt"],
            capture_output=True, text=True).stdout.strip()
    except Exception:
        pass
    dire("aucun fichier de profil n'est suivi par git", not suivis,
         suivis.splitlines()[:3] or "aucun")

    print()
    if not all(sorties):
        print("Corriger ce qui precede avant de publier.")
        return 1

    print("Tout est coherent. Il reste a faire, dans cet ordre :")
    print()
    print("  1. pousser le code et le site")
    print("       git add -A && git commit -m \"Plume %s\"" % core.VERSION)
    print("       git push")
    print()
    print("  2. creer la Release et y joindre l'installeur")
    print("       https://github.com/%s/releases/new" % DEPOT)
    print("       etiquette : v%s" % core.VERSION)
    print("       fichier   : %s" % installeur)
    print()
    print("  3. verifier que la page est en ligne")
    print("       %s" % core.CONFIG.get("manifeste_maj", ""))
    print()
    print("  L'adresse annoncee par le manifeste ne repondra qu'apres")
    print("  l'etape 2 : c'est la Release qui la fait exister.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
