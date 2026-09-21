# -*- coding: utf-8 -*-
"""
Construit un paquet autonome de Plume, a donner tel quel.

Le resultat est un dossier que l'on copie ou que l'on compresse : il contient
Python, les bibliotheques et mpv. Rien a installer sur la machine
d'arrivee, hormis le runtime WebView2, present d'origine sur Windows 11.

Ce qui n'y entre jamais : le dossier `profil/`, qui contient les cookies de
session du compte Google. Le distribuer reviendrait a donner l'acces au compte.

Usage : python outils\\construire.py
"""
import ast
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import core          # noqa: E402  (apres l'ajout de RACINE au chemin)

VERSION = core.VERSION
# Le depot ou vivent les Releases et la page. Une seule source : le manifeste
# et le site en decoulent.
DEPOT = "Yielloow/Plume"
SORTIE = RACINE.parent / "Plume-paquet"
TRAVAIL = Path(os.environ.get("TEMP", ".")) / "plume-build"

# Fichiers du projet a embarquer tels quels
SOURCES = ["navigateur.py", "interface.py", "incrustation.py", "core.py",
           "langues.py", "plume.py", "barre_taches.py", "osc.lua",
           "config.json", "README.md"]

INTERDITS = {"profil", "cookies.txt", "diagnostic.txt", "__pycache__"}


def trouver(nom, chemins):
    depuis_path = shutil.which(nom)
    if depuis_path:
        return Path(depuis_path)
    for c in chemins:
        p = Path(os.path.expandvars(c))
        if p.exists():
            return p
    return None


def journal(texte):
    print("  " + texte)


def ecrire_empreintes(dossier):
    """Liste les empreintes SHA-256 des executables livres.

    Le paquet n'est pas signe, donc un antivirus peut le prendre pour un
    cheval de Troie. Le destinataire doit pouvoir verifier lui-meme que le
    fichier recu est bien celui qui a ete construit avant de passer outre.
    """
    lignes = ["Empreintes SHA-256 des executables de ce paquet.",
              "",
              "Verification, dans PowerShell, depuis ce dossier :",
              "    Get-FileHash .\\Plume.exe -Algorithm SHA256",
              "",
              "Si une empreinte ne correspond pas, le fichier a ete altere",
              "en chemin : ne le lancez pas.",
              ""]
    for chemin in sorted(dossier.rglob("*.exe")):
        h = hashlib.sha256(chemin.read_bytes()).hexdigest()
        lignes.append("%s  %s" % (h, chemin.relative_to(dossier)))
    (dossier / "EMPREINTES.txt").write_text(
        "\n".join(lignes) + "\n", encoding="utf-8")
    return len(lignes) - 8


def modules_oublies():
    """Modules du projet importes par une source, mais absents de SOURCES.

    Un fichier ajoute au projet et oublie ici donne un paquet qui se construit
    sans rien dire et tombe au demarrage chez celui qui le recoit. La
    verification coute une lecture de chaque source et ferme la porte.
    """
    embarques = {n[:-3] for n in SOURCES if n.endswith(".py")}
    du_projet = {f.stem for f in RACINE.glob("*.py")}
    manquants = set()
    for nom in SOURCES:
        if not nom.endswith(".py"):
            continue
        try:
            arbre = ast.parse((RACINE / nom).read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for noeud in ast.walk(arbre):
            vises = []
            if isinstance(noeud, ast.Import):
                vises = [a.name.split(".")[0] for a in noeud.names]
            elif isinstance(noeud, ast.ImportFrom) and noeud.level == 0:
                vises = [(noeud.module or "").split(".")[0]]
            for vise in vises:
                if vise in du_projet and vise not in embarques:
                    manquants.add("%s (importe par %s)" % (vise, nom))
    return sorted(manquants)


def construire():
    if SORTIE.exists():
        shutil.rmtree(SORTIE, ignore_errors=True)
    SORTIE.mkdir(parents=True, exist_ok=True)

    lib_webview = Path(importlib.util.find_spec("webview").origin).parent / "lib"

    print("1. compilation du lanceur et des bibliotheques")
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--noconsole", "--name", "Plume",
        # UPX comprime l'executable, et cette compression est l'un des
        # declencheurs les plus surs des heuristiques antivirus : un binaire
        # qui se decompresse en memoire ressemble a un paquet malveillant.
        # PyInstaller l'utilise des qu'il le trouve dans le PATH. Il n'y est
        # pas sur cette machine, mais l'exclure explicitement evite qu'une
        # installation future ne le reintroduise sans qu'on s'en apercoive.
        "--noupx",
        "--icon", str(RACINE / "icone" / "plume.ico"),
        "--distpath", str(SORTIE), "--workpath", str(TRAVAIL),
        "--specpath", str(TRAVAIL),
        # pythonnet et WebView2 ne sont pas detectes automatiquement
        "--hidden-import", "clr",
        "--hidden-import", "pythonnet",
        "--hidden-import", "yt_dlp",
        "--hidden-import", "streamlink",
        "--collect-all", "pythonnet",
        "--collect-all", "clr_loader",
        "--collect-submodules", "yt_dlp",
        "--collect-submodules", "streamlink",
        "--add-data", "%s%s%s" % (lib_webview, os.pathsep, "webview/lib"),
        str(RACINE / "outils" / "demarrer.py"),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("ECHEC de la compilation :")
        for ligne in (r.stdout + r.stderr).splitlines()[-25:]:
            print("   " + ligne)
        return False

    interne = SORTIE / "Plume" / "_internal"
    dossier = SORTIE / "Plume"
    journal("compile dans %s" % dossier)

    # L'installateur ecrit la langue choisie dans config.json en passant par
    # une chaine d'octets : le fichier doit donc rester en pur ASCII, sinon
    # les accents en ressortiraient abimes. On le verifie plutot que de
    # l'esperer.
    brut = (RACINE / "config.json").read_bytes()
    try:
        brut.decode("ascii")
    except UnicodeDecodeError:
        print("   config.json contient des caracteres non ASCII, arret :")
        print("     l'installateur les abimerait en y ecrivant la langue")
        return False

    oublies = modules_oublies()
    if oublies:
        print("   DES MODULES DU PROJET NE SERAIENT PAS EMBARQUES, arret :")
        for m in oublies:
            print("     " + m)
        print("   -> les ajouter a SOURCES dans outils/construire.py")
        return False

    print("2. copie du code de Plume")
    for nom in SOURCES:
        source = RACINE / nom
        if source.exists():
            shutil.copy2(source, dossier / nom)
    shutil.copytree(RACINE / "icone", dossier / "icone", dirs_exist_ok=True)
    shutil.copy2(RACINE / "outils" / "LISEZ-MOI.txt", dossier / "LISEZ-MOI.txt")
    journal("%d fichiers, plus la notice" % len(SOURCES))

    print("3. copie des outils externes")
    # mpv seul : il ne lit plus que Twitch, alimente par streamlink, que
    # l'executable fait tourner lui-meme. Le yt-dlp autonome et Deno ne
    # servaient qu'a lui faire lire YouTube ; la recherche, elle, passe par
    # `Plume.exe --ytdlp`.
    mpv = trouver("mpv", [r"%ProgramFiles%\MPV Player\mpv.exe"])

    outils = dossier / "outils-externes"
    outils.mkdir(exist_ok=True)
    for nom, chemin in (("mpv.exe", mpv),):
        if chemin and chemin.exists():
            shutil.copy2(chemin, outils / nom)
            journal("%-12s %6.1f Mo" % (nom, chemin.stat().st_size / 1048576))
        else:
            journal("%-12s ABSENT" % nom)

    print("4. verification : aucune donnee personnelle")
    fuites = []
    for chemin in dossier.rglob("*"):
        if chemin.name in INTERDITS or "profil" in chemin.parts:
            fuites.append(chemin)
    if fuites:
        print("   DES DONNEES PERSONNELLES SONT PRESENTES, arret :")
        for f in fuites[:10]:
            print("     " + str(f))
        return False
    journal("aucun profil, aucun cookie")

    print("5. empreintes des executables")
    n = ecrire_empreintes(dossier)
    journal("EMPREINTES.txt : %d executables listes" % n)

    print("6. installeur")
    installeur = construire_installeur(dossier)

    print("7. compression")
    archive = SORTIE / "Plume.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for chemin in dossier.rglob("*"):
            if chemin.is_file():
                z.write(chemin, chemin.relative_to(dossier.parent))
    taille = archive.stat().st_size / 1048576
    journal("%s  (%.0f Mo)" % (archive, taille))

    print("8. manifeste de mise a jour")
    ecrire_manifeste(installeur or archive)
    return True


def construire_installeur(dossier):
    """Compile l'installeur Inno Setup, s'il est installe sur cette machine.

    Absent, on ne fait pas echouer la construction : le zip reste distribuable,
    et l'installeur n'est qu'un confort de plus.
    """
    iscc = trouver("ISCC", [
        # winget installe Inno Setup par utilisateur : c'est la qu'il atterrit
        # en pratique, et pas dans Program Files.
        r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe",
        r"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe",
        r"%ProgramFiles%\Inno Setup 6\ISCC.exe"])
    if not iscc:
        journal("Inno Setup absent : pas d'installeur")
        journal("  a installer une fois : winget install JRSoftware.InnoSetup")
        return None
    r = subprocess.run(
        [str(iscc), "/DMaVersion=" + VERSION,
         str(RACINE / "outils" / "plume.iss")],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        for ligne in (r.stdout + r.stderr).splitlines()[-12:]:
            journal("  " + ligne)
        journal("ECHEC de l'installeur")
        return None
    sortie = SORTIE / ("Plume-%s-installeur.exe" % VERSION)
    if not sortie.exists():
        journal("installeur introuvable apres compilation")
        return None
    journal("%s  (%.0f Mo)" % (sortie.name, sortie.stat().st_size / 1048576))
    return sortie


def ecrire_manifeste(fichier):
    """Ecrit docs/version.json : ce que Plume interroge, et ce que le site lit.

    Une seule source pour le numero de version, l'adresse et l'empreinte.
    Publier une version sans mettre la page a jour devient donc impossible a
    rater : la page se remplit depuis ce fichier.
    """
    h = hashlib.sha256()
    with open(fichier, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    manifeste = {
        "version": VERSION,
        # L'adresse definitive n'est connue qu'une fois le depot cree. Elle
        # est reecrite par outils/publier.py au moment de la publication.
        "url": "https://github.com/%s/releases/download/v%s/%s"
               % (DEPOT, VERSION, fichier.name),
        "sha256": h.hexdigest(),
        "taille_mo": round(fichier.stat().st_size / 1048576),
        "date": datetime.date.today().isoformat(),
        "notes": "",
    }
    # `docs` et non `site` : GitHub Pages ne sait servir une branche que
    # depuis la racine ou depuis ce dossier-la, et mettre le site a la racine
    # du depot melangerait la page et le code.
    cible = RACINE / "docs" / "version.json"
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(json.dumps(manifeste, ensure_ascii=False, indent=2)
                     + "\n", encoding="utf-8")
    journal("docs/version.json : %s, %s" % (VERSION, manifeste["sha256"][:16]))
    journal("  telechargement : %s" % manifeste["url"])


if __name__ == "__main__":
    sys.exit(0 if construire() else 1)
