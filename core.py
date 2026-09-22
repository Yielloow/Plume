# -*- coding: utf-8 -*-
"""
Plume / core - toute la logique, sans interface.

Rien ici ne charge de moteur web : la recherche passe par yt-dlp en
sous-processus, la lecture par mpv. L'interface (tkinter) reste donc
minuscule en memoire.
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlencode, urlparse

# Dans le paquet autonome, le code voyage a cote de l'executable et non du
# fichier source : PLUME_RACINE le designe.
APP_DIR = Path(os.environ.get("PLUME_RACINE") or
               Path(__file__).resolve().parent).resolve()
CONFIG_FILE = APP_DIR / "config.json"
EN_PAQUET = bool(getattr(sys, "frozen", False))

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

DEFAULT_CONFIG = {
    "moteur_recherche": "https://www.google.com/search?q={q}",
    "qualite_max": 1080,
    "fps_max": 60,
    "nb_resultats": 14,
    "miniatures": True,
    "cookies_navigateur": False,
    "youtube_client": "web_safari",
    "mpv_extra": [],
    # Secondes d'inactivite avant qu'un onglet d'arriere-plan soit gele.
    # 0 desactive la veille. Voir README, « Les onglets qui dorment ».
    "veille_onglets": 90,
    # Ouverture dessinee au lancement. Mettre a false pour demarrer sec.
    "intro": True,
    # Glissement de la page en changeant d'onglet. C'est le geste le plus
    # frequent d'un navigateur : si l'animation gene, ce reglage la coupe.
    "glissement_onglets": True,
    # Volume du lecteur, retenu d'une video a l'autre. Un volume est un
    # reglage de personne, pas de video.
    "volume": 100,
    "muet": False,
    # Langue de l'interface : "fr", "en", ou "auto" pour suivre celle de
    # Windows. L'installateur y ecrit le choix fait a l'installation.
    "langue": "auto",
    # Adresse du fichier version.json publie a cote du telechargement. Vide,
    # Plume n'interroge rien : pas de depot, pas de requete.
    "manifeste_maj": "https://yielloow.github.io/Plume/version.json",
}

# Profil de la vue de navigation, au format Chromium : yt-dlp sait y lire les
# cookies de session. Desactive par defaut, voir cookies_navigateur.
PROFIL_WEB = APP_DIR / "profil" / "EBWebView"

# Logo de Plume : l'etoile a quatre branches, la meme partout.
ICONE = APP_DIR / "icone" / "plume.ico"
# Ce que Windows doit relancer quand on epingle Plume : le lanceur, jamais
# l'interpreteur Python qui le fait tourner.
EXECUTABLE = (sys.executable if EN_PAQUET
              else str(APP_DIR / "Plume.exe"))

# Cookies exportes par le navigateur, au format Netscape. On ne peut pas lire
# la base du profil pendant qu'il tourne : il la verrouille.
FICHIER_COOKIES = APP_DIR / "profil" / "cookies.txt"


def effacer_ancien_export_cookies():
    """Efface le fichier ou les versions precedentes exportaient la session.

    Elles y ecrivaient les cookies YouTube en clair, pour yt-dlp. Il ne lit
    plus YouTube : le fichier n'a plus de raison d'exister, et il ne doit pas
    rester sur le disque de ceux qui mettent a jour. Appele au demarrage de
    l'application, pas a l'import : un import ne doit rien effacer.
    """
    try:
        FICHIER_COOKIES.unlink()
    except OSError:
        pass
# Dans profil/, donc jamais dans le paquet distribue : les favoris disent ou
# l'utilisateur va, c'est personnel.
FICHIER_FAVORIS = APP_DIR / "profil" / "favoris.json"
# Traces du lecteur : le journal de mpv lui-meme, ecrase a chaque lecture, et
# un releve des arrets, celui-ci cumulatif. Sans eux, un lecteur qui s'arrete
# ne laisse rien derriere lui et il n'y a plus qu'a deviner.
DOSSIER_FAVICONS = APP_DIR / "profil" / "favicons"
FICHIER_SESSION = APP_DIR / "profil" / "session.json"
# Historique, dans profil/ comme le reste : il ne quitte jamais la
# machine et ne part jamais dans le paquet distribue.
FICHIER_HISTORIQUE = APP_DIR / "profil" / "historique.json"
FICHIER_ZOOMS = APP_DIR / "profil" / "zooms.json"
FICHIER_TRAVAIL = APP_DIR / "profil" / "groupes-travail.json"
FICHIER_POSITIONS = APP_DIR / "profil" / "positions.json"
# Combien de videos on retient. Au dela, les plus anciennes s'effacent : ce
# fichier est une commodite, pas une archive.
MAX_POSITIONS = 300
# En dessous de trente secondes, il n'y a rien a reprendre : on vient de
# commencer, et proposer une reprise serait plus genant qu'utile.
POSITION_MINIMALE = 30.0
# Trop pres de la fin, la video est finie : la rouvrir doit la reprendre au
# debut, pas au generique.
RESTE_MINIMAL = 45.0
# Au dela de deux mois, on oublie : la position d'une video vue en avril ne
# veut plus rien dire.
AGE_MAX_POSITION = 60 * 24 * 3600
# Un groupe de travail garde au plus ce nombre d'onglets : au dela, les
# rouvrir d'un coup couterait plus de memoire que la machine n'en a.
MAX_ONGLETS_TRAVAIL = 12
# Paliers de zoom, ceux des navigateurs courants.
PALIERS_ZOOM = (0.5, 0.67, 0.8, 0.9, 1.0, 1.1, 1.25, 1.5, 1.75, 2.0)
MAX_HISTORIQUE = 3000
# Page d'accueil, reecrite a chaque ouverture pour refleter les favoris
# et le compteur. Elle vit dans profil/ : rien n'en sort de la machine.
FICHIER_ACCUEIL = APP_DIR / "profil" / "accueil.html"
JOURNAL_MPV = APP_DIR / "profil" / "mpv.log"
JOURNAL_LECTEUR = APP_DIR / "profil" / "lecteur.log"

def charger_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg


CONFIG = charger_config()


# --------------------------------------------------------------------------
# Localisation des binaires (aucun n'est suppose etre dans le PATH)
# --------------------------------------------------------------------------
def _trouver(nom, chemins_probables):
    trouve = shutil.which(nom)
    if trouve:
        return trouve
    for c in chemins_probables:
        p = Path(os.path.expandvars(c))
        # os.path.isfile et non Path.exists : devant un raccourci que Windows
        # refuse de laisser parcourir (WinError 448), Path.exists leve une
        # erreur au lieu de repondre non, et Plume ne demarrait plus.
        if os.path.isfile(str(p)):
            return str(p)
    return None


SCRIPTS_DIR = Path(sys.executable).parent / "Scripts"
EXTERNES = APP_DIR / "outils-externes"      # outils fournis avec le paquet

MPV = _trouver("mpv", [
    str(EXTERNES / "mpv.exe"),
    r"%ProgramFiles%\MPV Player\mpv.exe",
    r"%ProgramFiles%\mpv\mpv.exe",
    r"%LOCALAPPDATA%\Microsoft\WinGet\Links\mpv.exe",
    r"%LOCALAPPDATA%\Programs\mpv\mpv.exe",
])
# Le dossier `yt-dlp/` passe avant le fichier unique : un exe PyInstaller
# « onefile » se decompresse dans %TEMP% puis execute ce qu'il vient d'y
# ecrire, comportement que les antivirus classent en dropper (les amis de
# l'utilisateur ont recu « cheval de Troie »). La forme « onedir » n'a rien
# a extraire, donc rien a signaler.
YTDLP = _trouver("yt-dlp", [str(EXTERNES / "yt-dlp" / "yt-dlp.exe"),
                            str(EXTERNES / "yt-dlp.exe"),
                            str(SCRIPTS_DIR / "yt-dlp.exe")])
STREAMLINK = _trouver("streamlink", [str(SCRIPTS_DIR / "streamlink.exe")])

if EN_PAQUET:
    # plus d'interpreteur separe : l'executable se relance avec un role
    YTDLP_CMD = [YTDLP] if YTDLP else [sys.executable, "--ytdlp"]
    STREAMLINK_CMD = [sys.executable, "--streamlink"]
else:
    YTDLP_CMD = [YTDLP] if YTDLP else [sys.executable, "-m", "yt_dlp"]
    STREAMLINK_CMD = ([STREAMLINK] if STREAMLINK
                      else [sys.executable, "-m", "streamlink"])


def etat_outils():
    return {
        "mpv": MPV or "",
        "yt_dlp": YTDLP or " ".join(YTDLP_CMD),
        "streamlink": STREAMLINK or " ".join(STREAMLINK_CMD),
        "mpv_ok": bool(MPV),
    }


# --------------------------------------------------------------------------
# Reconnaissance de ce que l'utilisateur tape
# --------------------------------------------------------------------------
# file:// compte comme une adresse : la page d'accueil de Plume en est
# une, et sans cela le bouton Accueil lancait une recherche Google sur
# le chemin du fichier.
RE_URL = re.compile(r"^(https?://|file://|www\.)", re.I)
RE_DOMAINE = re.compile(r"^[\w-]+(\.[\w-]+)+(/.*)?$")

SITES_VIDEO = (
    "youtube.com", "youtu.be", "twitch.tv", "kick.com", "vimeo.com",
    "dailymotion.com", "twitter.com", "x.com", "bilibili.com", "odysee.com",
    "soundcloud.com", "rumble.com",
)
SITES_LIVE = ("twitch.tv", "kick.com")
# Les seuls sites lus par mpv. Twitch insere ses pubs dans le flux video, et
# seul streamlink, qui alimente mpv, sait les sauter. Partout ailleurs, le
# lecteur du site coute moins cher : mesure faite sur YouTube, 23 % d'un coeur
# contre 31 %, et trois secondes d'extraction en moins avant l'image.
SITES_MPV = ("twitch.tv",)


def est_url(texte):
    t = texte.strip()
    return bool(RE_URL.match(t) or RE_DOMAINE.match(t))


def normaliser_url(texte):
    t = texte.strip()
    if not RE_URL.match(t):
        return "https://" + t
    if t.lower().startswith("www."):
        return "https://" + t
    return t


def _hote(url):
    return (urlparse(url).hostname or "").lower().replace("www.", "")


def hote(url):
    """Nom d'hote normalise, utilisable comme nom de fichier."""
    return _hote(url)


def est_video(url):
    h = _hote(url)
    return any(h == s or h.endswith("." + s) for s in SITES_VIDEO)


def lu_par_mpv(url):
    """Vrai si cette page confie sa video a mpv plutot qu'a son lecteur."""
    h = _hote(url)
    return any(h == s or h.endswith("." + s) for s in SITES_MPV)


def est_live(url):
    h = _hote(url)
    return any(h == s or h.endswith("." + s) for s in SITES_LIVE)


# Parametres que les sites ajoutent ou retirent tout seuls apres le
# chargement, et qui ne designent pas une autre video.
PARAMS_VOLATILS = {
    "themerefresh", "pp", "feature", "ab_channel", "si", "spm", "gclid",
    "fbclid", "igshid",
}
# Familles entieres de parametres de suivi : utm_source, tt_medium, etc.
PREFIXES_VOLATILS = ("utm_", "tt_", "_ga")


def _volatil(nom):
    nom = nom.lower()
    return nom in PARAMS_VOLATILS or nom.startswith(PREFIXES_VOLATILS)


def cle_video(url):
    """Identite stable d'une video, pour ne pas relancer le lecteur pour rien.

    Mesure du 2026-09-05 : sur une page YouTube, l'adresse change trois fois
    en trois secondes. Le site ajoute `&themeRefresh=1` puis le retire. En
    comparant les adresses brutes, Plume croyait a trois videos differentes et
    relancait mpv a chaque fois, tuant le precedent en plein chargement : la
    lecture ne demarrait jamais.
    """
    if not url:
        return ""
    try:
        p = urlparse(url)
        hote = (p.hostname or "").lower().replace("www.", "")
        parametres = parse_qs(p.query)
    except Exception:
        return url
    if hote.endswith("youtube.com") and p.path == "/watch":
        v = parametres.get("v")
        if v:
            return "youtube:" + v[0]
    if hote == "youtu.be" and p.path.strip("/"):
        return "youtube:" + p.path.strip("/").split("/")[0]
    gardes = sorted((c, v[0]) for c, v in parametres.items()
                    if v and not _volatil(c))
    return "%s%s?%s" % (hote, p.path.rstrip("/"), urlencode(gardes))


def url_recherche_web(requete):
    return CONFIG["moteur_recherche"].format(q=quote_plus(requete))


# --------------------------------------------------------------------------
# Favoris
# --------------------------------------------------------------------------
def duree_texte(secondes):
    """Une duree en h:mm:ss, ou m:ss quand il n'y a pas d'heure."""
    try:
        total = max(0, int(float(secondes)))
    except (TypeError, ValueError):
        return "0:00"
    heures, reste = divmod(total, 3600)
    minutes, sec = divmod(reste, 60)
    if heures:
        return "%d:%02d:%02d" % (heures, minutes, sec)
    return "%d:%02d" % (minutes, sec)


def charger_positions():
    """Ou l'on en etait dans chaque video, par identite de video.

    Forme : {cle: {"position": s, "duree": s, "titre": str, "date": t}}. La
    cle est celle de `cle_video`, pas l'adresse : YouTube ajoute et retire des
    parametres, et la meme video doit se retrouver quoi qu'il arrive.
    """
    try:
        donnees = json.loads(FICHIER_POSITIONS.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(donnees, dict):
        return {}
    propres, maintenant = {}, time.time()
    for cle, brut in donnees.items():
        if not isinstance(brut, dict):
            continue
        try:
            position = float(brut.get("position") or 0)
            duree = float(brut.get("duree") or 0)
            date = float(brut.get("date") or 0)
        except (TypeError, ValueError):
            continue
        if position <= 0 or maintenant - date > AGE_MAX_POSITION:
            continue
        propres[str(cle)] = {
            "position": position, "duree": duree, "date": date,
            "titre": str(brut.get("titre") or "")[:120],
        }
    return propres


def enregistrer_positions(positions):
    """Ecrit les positions, les plus recentes d'abord."""
    try:
        gardees = sorted(positions.items(), key=lambda kv: -kv[1]["date"])
        gardees = dict(gardees[:MAX_POSITIONS])
        FICHIER_POSITIONS.parent.mkdir(parents=True, exist_ok=True)
        FICHIER_POSITIONS.write_text(
            json.dumps(gardees, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8")
        return True
    except Exception:
        return False


def noter_position(positions, cle, position, duree, titre=""):
    """Retient une position, ou l'oublie si la video est finie ou a peine vue.

    Renvoie vrai si quelque chose a change, pour ne pas reecrire le fichier
    pour rien.
    """
    if not cle:
        return False
    try:
        position, duree = float(position), float(duree)
    except (TypeError, ValueError):
        return False
    fini = duree > 0 and duree - position < RESTE_MINIMAL
    if position < POSITION_MINIMALE or fini:
        # Rien a retenir : et s'il y avait quelque chose, c'est maintenant
        # faux, donc on l'enleve.
        return positions.pop(cle, None) is not None
    ancienne = positions.get(cle)
    if ancienne and abs(ancienne["position"] - position) < 1.0:
        return False
    positions[cle] = {"position": position, "duree": duree,
                      "date": time.time(), "titre": str(titre or "")[:120]}
    return True


def position_reprise(positions, cle):
    """Ou reprendre cette video, ou 0 s'il n'y a rien de pertinent."""
    entree = positions.get(cle or "")
    if not entree:
        return 0.0
    position = entree.get("position") or 0.0
    duree = entree.get("duree") or 0.0
    if position < POSITION_MINIMALE:
        return 0.0
    if duree > 0 and duree - position < RESTE_MINIMAL:
        return 0.0
    return float(position)


# Le nombre de teintes de la palette, repris de interface.COULEURS_GROUPE.
# Declare ici pour que la lecture du fichier ne depende pas du module de
# dessin : `core` doit pouvoir etre lu sans interface graphique.
NB_COULEURS_GROUPE = 6


def charger_groupes_travail():
    """Groupes de travail : nom, couleur, et les adresses a rouvrir.

    Forme : [{"nom": str, "couleur": int, "couleurs": [int],
              "onglets": [{"url", "titre"}]}].

    `couleurs` porte une ou deux teintes choisies ; `couleur` reste ecrit a
    cote, pour qu'une version anterieure relisant ce fichier y retrouve son
    compte.
    Un groupe est une habitude, pas une session : on y range les pages qu'on
    rouvre chaque fois qu'on se remet a la meme chose.
    """
    try:
        donnees = json.loads(FICHIER_TRAVAIL.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(donnees, dict):
        donnees = donnees.get("groupes") or []
    if not isinstance(donnees, list):
        return []
    propres = []
    for brut in donnees:
        if not isinstance(brut, dict):
            continue
        nom = str(brut.get("nom") or "").strip()[:28]
        if not nom:
            continue
        onglets = []
        for o in (brut.get("onglets") or [])[:MAX_ONGLETS_TRAVAIL]:
            if isinstance(o, dict) and o.get("url"):
                onglets.append({"url": str(o["url"]),
                                "titre": str(o.get("titre") or o["url"])[:90]})
        try:
            couleur = int(brut.get("couleur") or 0)
        except (TypeError, ValueError):
            couleur = 0
        # Une ou deux teintes, toujours ramenees dans la palette. Un
        # fichier ancien n'a que `couleur` : elle devient la premiere.
        brutes = brut.get("couleurs")
        if not isinstance(brutes, list):
            brutes = [couleur]
        couleurs = []
        for c in brutes[:2]:
            try:
                couleurs.append(int(c) % NB_COULEURS_GROUPE)
            except (TypeError, ValueError):
                pass
        if not couleurs:
            couleurs = [couleur % NB_COULEURS_GROUPE]
        propres.append({"nom": nom, "couleur": couleurs[0],
                        "couleurs": couleurs, "onglets": onglets})
    return propres


def enregistrer_groupes_travail(groupes):
    try:
        FICHIER_TRAVAIL.parent.mkdir(parents=True, exist_ok=True)
        FICHIER_TRAVAIL.write_text(
            json.dumps(groupes, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        return True
    except Exception:
        return False


def groupe_travail(groupes, nom):
    for groupe in groupes:
        if groupe["nom"] == nom:
            return groupe
    return None


def charger_zooms():
    """Facteur de zoom retenu pour chaque site."""
    try:
        donnees = json.loads(FICHIER_ZOOMS.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(donnees, dict):
        return {}
    propres = {}
    for hote, facteur in donnees.items():
        try:
            valeur = float(facteur)
        except (TypeError, ValueError):
            continue
        if 0.25 <= valeur <= 4.0:
            propres[str(hote)] = valeur
    return propres


def enregistrer_zooms(zooms):
    try:
        FICHIER_ZOOMS.parent.mkdir(parents=True, exist_ok=True)
        FICHIER_ZOOMS.write_text(json.dumps(zooms, ensure_ascii=False),
                                 encoding="utf-8")
        return True
    except Exception:
        return False


def palier_zoom(actuel, sens):
    """Palier suivant ou precedent, sans sortir de la liste."""
    proche = min(range(len(PALIERS_ZOOM)),
                 key=lambda i: abs(PALIERS_ZOOM[i] - actuel))
    indice = max(0, min(len(PALIERS_ZOOM) - 1, proche + sens))
    return PALIERS_ZOOM[indice]


def charger_historique():
    """Adresses visitees, de la plus recente a la plus ancienne."""
    try:
        donnees = json.loads(FICHIER_HISTORIQUE.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(donnees, list):
        return []
    propre = []
    for e in donnees[:MAX_HISTORIQUE]:
        if isinstance(e, dict) and e.get("url"):
            propre.append({"url": str(e["url"]),
                           "titre": str(e.get("titre") or ""),
                           "vues": int(e.get("vues") or 1)})
    return propre


def enregistrer_historique(entrees):
    try:
        FICHIER_HISTORIQUE.parent.mkdir(parents=True, exist_ok=True)
        FICHIER_HISTORIQUE.write_text(
            json.dumps(entrees[:MAX_HISTORIQUE], ensure_ascii=False),
            encoding="utf-8")
        return True
    except Exception:
        return False


def resume_url(url):
    """Version courte et lisible d'une adresse, pour une liste."""
    try:
        p = urlparse(url)
        hote = (p.hostname or "").replace("www.", "")
        chemin = p.path.rstrip("/")
        if p.query:
            chemin += "?" + p.query[:40]
        return (hote + chemin) or url
    except Exception:
        return url


def charger_session():
    """Onglets ouverts au dernier arret, par fenetre.

    Forme : {"fenetres": [{"onglets": [url, ...], "actif": indice}]}. La liste
    de fenetres existe des maintenant pour ne pas avoir a tout reecrire quand
    Plume en ouvrira plusieurs.
    """
    try:
        donnees = json.loads(FICHIER_SESSION.read_text(encoding="utf-8"))
    except Exception:
        return {"fenetres": []}
    if not isinstance(donnees, dict):
        return {"fenetres": []}
    fenetres = []
    for f in donnees.get("fenetres") or []:
        if not isinstance(f, dict):
            continue
        onglets = [str(u) for u in (f.get("onglets") or []) if u]
        if not onglets:
            continue
        entree = {"onglets": onglets, "actif": int(f.get("actif") or 0)}
        bornes = f.get("bornes")
        if isinstance(bornes, (list, tuple)) and len(bornes) == 4:
            try:
                entree["bornes"] = [int(v) for v in bornes]
                entree["agrandie"] = bool(f.get("agrandie"))
            except (TypeError, ValueError):
                pass
        fenetres.append(entree)
    return {"fenetres": fenetres}


def enregistrer_session(session):
    try:
        FICHIER_SESSION.parent.mkdir(parents=True, exist_ok=True)
        FICHIER_SESSION.write_text(
            json.dumps(session, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        return True
    except Exception:
        return False


def charger_favoris():
    """Renvoie {"barre_visible": bool, "elements": [{"url", "titre"}]}.

    Tolere un fichier absent, illisible ou ecrit dans l'ancien format en simple
    liste : un favori perdu ne doit pas empecher le navigateur de demarrer.
    """
    defaut = {"barre_visible": True, "elements": []}
    try:
        donnees = json.loads(FICHIER_FAVORIS.read_text(encoding="utf-8"))
    except Exception:
        return defaut
    if isinstance(donnees, list):
        donnees = {"barre_visible": True, "elements": donnees}
    if not isinstance(donnees, dict):
        return defaut
    elements = []
    for e in donnees.get("elements") or []:
        if isinstance(e, dict) and e.get("url"):
            elements.append({"url": str(e["url"]),
                             "titre": str(e.get("titre") or e["url"])})
    return {"barre_visible": bool(donnees.get("barre_visible", True)),
            "elements": elements}


def enregistrer_favoris(favoris):
    try:
        FICHIER_FAVORIS.parent.mkdir(parents=True, exist_ok=True)
        FICHIER_FAVORIS.write_text(
            json.dumps(favoris, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# Lecture : mpv fait tout le travail lourd
# --------------------------------------------------------------------------
def options_youtube():
    """Options yt-dlp requises pour que YouTube accepte de servir le flux.

    YouTube exige deux choses, et il faut les deux ensemble :

    1. une session authentifiee, sinon « Sign in to confirm you're not a bot ».
       Les cookies viennent du fichier exporte par le navigateur, pas de la base
       du profil, qu'il verrouille tant qu'il tourne ;
    2. la resolution d'un defi JavaScript, sinon « The page needs to be
       reloaded ». yt-dlp la delegue a Deno et a un script qu'il telecharge
       depuis son depot GitHub, ce qu'active --remote-components.

    Mesure le 2026-09-04 : cookies seuls -> echec, solveur seul -> echec, les
    deux -> lecture correcte.
    """
    options = []
    if CONFIG.get("cookies_navigateur") and FICHIER_COOKIES.exists():
        options += ["--cookies", str(FICHIER_COOKIES)]
    if CONFIG.get("solveur_distant"):
        options += ["--remote-components", "ejs:github"]
    # `youtube_client` vide : on laisse yt-dlp choisir.
    #
    # Ce reglage s'inverse au gre des changements de YouTube, ne pas s'y fier
    # de memoire, le remesurer. Historique :
    #   2026-09-04  web_safari, car le client par defaut donnait des URLs
    #               refusees au telechargement (HTTP 403), 2 lectures sur 5
    #               contre 5 sur 5.
    #   2026-09-05  l'inverse. web_safari et web ne renvoient plus AUCUN format
    #               lisible, seulement des storyboards, donc « Requested format
    #               is not available » ; tv reclame un rechargement de page ;
    #               mweb, android_vr et tv_simply se limitent au format 18, en
    #               360p. Mesure de bout en bout : defaut 4 lectures sur 4 en
    #               1080p et 3,0 s de demarrage, web_safari 0 sur 4.
    #
    # Symptome trompeur quand ce reglage est mauvais : l'erreur parle de format
    # indisponible, ce qui fait chercher du cote de --ytdl-format alors que le
    # probleme est le client. Verifier d'abord avec `yt-dlp -F` : s'il ne sort
    # que des lignes `sb0` a `sb3`, aucun format video n'a ete extrait.
    clients = (CONFIG.get("youtube_client") or "").strip()
    if clients:
        options += ["--extractor-args", "youtube:player_client=" + clients]
    return options


def construire_args_mpv(titre=None, avec_cookies=False):
    """Arguments de mpv. Les cookies ne sont joints que si on les demande.

    Mesure du 2026-09-05, sur quatre videos : avec la session authentifiee,
    2 lectures sur 4, les autres refusees en HTTP 403 au telechargement du
    flux ; sans cookies, 4 sur 4 en 1080p. Envoyer la session durcit les
    controles de YouTube. Les cookies restent indispensables aux videos a
    restriction d'age et au contournement du controle anti-robot, d'ou le
    repli automatique gere par `incrustation.py`.
    """
    q, fps = CONFIG["qualite_max"], CONFIG["fps_max"]
    args = [
        "--hwdec=auto-safe",          # decodage materiel : le GPU, pas le CPU
        "--vo=gpu",
        "--cache=yes",
        "--demuxer-max-bytes=48MiB",  # plafonne le tampon memoire
        "--demuxer-readahead-secs=3",   # 20 s retardait le demarrage
        "--force-window=immediate",   # fenetre visible sans attendre le reseau
        "--keep-open=no",
        "--ytdl-format=bestvideo[height<=?%d][fps<=?%d]+bestaudio/best" % (q, fps),
    ]
    if YTDLP:
        args.append("--script-opts=ytdl_hook-ytdl_path=" + YTDLP)
    if (avec_cookies and CONFIG.get("cookies_navigateur")
            and FICHIER_COOKIES.exists()):
        args.append("--ytdl-raw-options-append=cookies=" + str(FICHIER_COOKIES))
    if CONFIG.get("solveur_distant"):
        args.append("--ytdl-raw-options-append=remote-components=ejs:github")
    clients = (CONFIG.get("youtube_client") or "").strip()
    if clients:
        args.append("--ytdl-raw-options-append="
                    "extractor-args=youtube:player_client=" + clients)
    if titre:
        args.append("--force-media-title=" + titre)
    args.extend(CONFIG.get("mpv_extra", []))
    return args


def lancer_mpv(url, titre=None):
    if not MPV:
        return {"ok": False, "erreur": "mpv introuvable (winget install shinchiro.mpv)"}
    try:
        subprocess.Popen([MPV] + construire_args_mpv(titre) + [url],
                         creationflags=CREATE_NO_WINDOW)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


def lancer_streamlink(url, qualite="best"):
    """Les lives passent par streamlink : plus fiable que yt-dlp sur Twitch/Kick."""
    if not MPV:
        return {"ok": False, "erreur": "mpv introuvable."}
    try:
        cmd = STREAMLINK_CMD + [
            "--player", MPV,
            "--player-args", " ".join(construire_args_mpv()) + " {playerinput}",
            "--stream-segment-threads", "2",
            "--hls-live-edge", "3",
            url, qualite,
        ]
        subprocess.Popen(cmd, creationflags=CREATE_NO_WINDOW)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


def lire(url, titre=None):
    if est_live(url):
        return lancer_streamlink(url)
    return lancer_mpv(url, titre)


PORT_NAVIGATEUR = 47821


def ouvrir_navigation(url):
    """Ouvre l'URL dans le navigateur : un onglet, jamais une fenetre de plus.

    Si une fenetre Plume ecoute deja, on lui passe l'URL par le canal local et
    elle en fait un onglet. Sinon on lance le navigateur, dans un processus
    distinct de Plume : WebView2 est lourd, et le fermer doit rendre toute sa
    memoire sans toucher a l'interface, qui reste a 35 Mo.
    """
    try:
        lien = socket.create_connection(("127.0.0.1", PORT_NAVIGATEUR), timeout=1.0)
        lien.sendall((url or "").encode("utf-8"))
        lien.recv(16)
        lien.close()
        return {"ok": True, "onglet": True}
    except OSError:
        pass                       # aucune fenetre ouverte : on la lance

    if EN_PAQUET:
        commande = [sys.executable, url]
    else:
        exe = Path(sys.executable)
        pythonw = exe.parent / "pythonw.exe"
        interpreteur = str(pythonw if pythonw.exists() else exe)
        commande = [interpreteur, str(APP_DIR / "navigateur.py"), url]
    try:
        subprocess.Popen(commande, creationflags=CREATE_NO_WINDOW)
        return {"ok": True, "onglet": False}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


# --------------------------------------------------------------------------
# Recherche
# --------------------------------------------------------------------------
def _formater_duree(secondes):
    if not secondes:
        return ""
    s = int(secondes)
    h, reste = divmod(s, 3600)
    m, sec = divmod(reste, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, sec)
    return "%d:%02d" % (m, sec)


def _formater_vues(n):
    if not n:
        return ""
    for seuil, suffixe in ((1000000000, "Md"), (1000000, "M"), (1000, "k")):
        if n >= seuil:
            return ("%.1f" % (float(n) / seuil)).rstrip("0").rstrip(".") + " %s vues" % suffixe
    return "%d vues" % n


def chercher_youtube(requete, nb=None):
    """Recherche via yt-dlp : pas de cle API, aucune page web chargee."""
    nb = nb or CONFIG["nb_resultats"]
    cmd = YTDLP_CMD + [
        "ytsearch%d:%s" % (nb, requete),
        "--flat-playlist", "-J",
        "--no-warnings", "--ignore-errors",
        "--socket-timeout", "15",
    ]
    cmd += options_youtube()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90,
                           encoding="utf-8", errors="replace",
                           creationflags=CREATE_NO_WINDOW)
        if not (r.stdout or "").strip():
            return {"ok": False, "erreur": (r.stderr or "aucune reponse")[:300]}
        data = json.loads(r.stdout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "erreur": "recherche trop longue (reseau ?)"}
    except Exception as e:
        return {"ok": False, "erreur": str(e)[:300]}

    resultats = []
    for e in (data.get("entries") or []):
        if not e:
            continue
        vid = e.get("id") or ""
        url = e.get("url") or ""
        if not url and vid:
            url = "https://www.youtube.com/watch?v=" + vid
        resultats.append({
            "titre": e.get("title") or "(sans titre)",
            "url": url,
            "duree": _formater_duree(e.get("duration")),
            "chaine": e.get("channel") or e.get("uploader") or "",
            "vues": _formater_vues(e.get("view_count")),
            "miniature": ("https://i.ytimg.com/vi/%s/mqdefault.jpg" % vid) if vid else "",
        })
    return {"ok": True, "resultats": resultats}


# --------------------------------------------------------------------------
# Mesure memoire (pour l'indicateur de l'interface)
# --------------------------------------------------------------------------
def memoire_mo():
    """RAM de ce processus + les mpv en cours, en Mo.

    Passe par l'API Windows plutot que par `tasklist` : aucun sous-processus
    n'est cree, donc aucune fenetre de console ne peut apparaitre, meme
    fugitivement, et la mesure ne coute quasiment rien.
    """
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        PROCESS_QUERY_LIMITED = 0x1000
        PROCESS_VM_READ = 0x0010
        psapi = ctypes.WinDLL("psapi.dll")
        kernel32 = ctypes.WinDLL("kernel32.dll")

        def mesurer(pid):
            h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED | PROCESS_VM_READ, False, pid)
            if not h:
                h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
                if not h:
                    return 0, ""
            try:
                nom = ctypes.create_unicode_buffer(260)
                psapi.GetModuleBaseNameW(h, None, nom, 260)
                c = PROCESS_MEMORY_COUNTERS()
                c.cb = ctypes.sizeof(c)
                if psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb):
                    return c.WorkingSetSize, nom.value.lower()
                return 0, nom.value.lower()
            finally:
                kernel32.CloseHandle(h)

        total = mesurer(os.getpid())[0]

        # enumeration des processus, pour retrouver les mpv en cours
        tableau = (wintypes.DWORD * 2048)()
        rendu = wintypes.DWORD()
        if psapi.EnumProcesses(ctypes.byref(tableau), ctypes.sizeof(tableau),
                               ctypes.byref(rendu)):
            for i in range(rendu.value // ctypes.sizeof(wintypes.DWORD)):
                pid = tableau[i]
                if not pid:
                    continue
                octets, nom = mesurer(pid)
                if nom.startswith("mpv"):
                    total += octets
    except Exception:
        return 0
    return round(total / 1048576)

# --------------------------------------------------------------------------
# Version, et recherche d'une version plus recente
# --------------------------------------------------------------------------
# Trois nombres : rupture, ajout, correction. Le fichier `version.json` publie
# a cote du telechargement porte le meme, et c'est leur comparaison qui dit
# s'il y a du neuf.
VERSION = "1.0.13"

# Delai entre deux verifications. Une par jour suffit largement : Plume n'est
# pas un service, et interroger le reseau a chaque lancement serait une
# indiscretion pour rien.
DELAI_VERIFICATION = 24 * 3600
FICHIER_MAJ = APP_DIR / "profil" / "maj.json"


def version_en_nombres(texte):
    """« 1.12.3 » devient (1, 12, 3), comparable comme il se doit.

    Compare par nombres et non par texte : « 1.12 » est posterieur a « 1.9 »,
    alors que l'ordre alphabetique dirait le contraire. Ce qui n'est pas un
    nombre vaut zero, plutot que de faire echouer toute la verification.
    """
    nombres = []
    for morceau in str(texte or "").strip().lstrip("vV").split("."):
        chiffres = ""
        for c in morceau:
            if not c.isdigit():
                break
            chiffres += c
        nombres.append(int(chiffres) if chiffres else 0)
    while len(nombres) < 3:
        nombres.append(0)
    return tuple(nombres[:3])


def version_plus_recente(proposee, courante=None):
    """Vrai si `proposee` est strictement posterieure a `courante`."""
    courante = VERSION if courante is None else courante
    return version_en_nombres(proposee) > version_en_nombres(courante)


def oublier_verification_maj():
    """Efface la date du dernier controle : le prochain aura lieu aussitot."""
    try:
        FICHIER_MAJ.unlink()
    except OSError:
        pass


def lire_manifeste(texte):
    """Valide un manifeste de mise a jour, et renvoie None s'il ne va pas.

    Le manifeste vient du reseau : rien de ce qu'il contient n'est cru sur
    parole. Une adresse doit etre en https, et l'empreinte doit avoir la forme
    d'une empreinte, sans quoi on ne saurait pas verifier ce qu'on telecharge.
    """
    try:
        m = json.loads(texte)
    except (ValueError, TypeError):
        return None
    if not isinstance(m, dict):
        return None
    version = str(m.get("version", "")).strip()
    url = str(m.get("url", "")).strip()
    empreinte = str(m.get("sha256", "")).strip().lower()
    if not version or version_en_nombres(version) == (0, 0, 0):
        return None
    if not url.startswith("https://"):
        return None
    if len(empreinte) != 64 or any(c not in "0123456789abcdef"
                                   for c in empreinte):
        return None
    return {"version": version, "url": url, "sha256": empreinte,
            "notes": str(m.get("notes", ""))[:2000]}


def chercher_mise_a_jour(url_manifeste, maintenant=None, lecteur=None,
                         rapport=None):
    """Regarde s'il existe une version plus recente. Ne leve jamais.

    `rapport`, un dictionnaire facultatif, recoit la raison sous la cle
    « etat » : « neuf », « a_jour », « echec » ou « trop_tot ». Le bouton des
    parametres en a besoin pour dire la verite ; le demarrage, lui, se tait.

    Renvoie le manifeste s'il y a du neuf, sinon None. La verification est
    freinee a une par jour, et son horodatage vit dans profil/maj.json : une
    panne de reseau ne doit pas la relancer a chaque ouverture d'onglet.
    """
    rapport = {} if rapport is None else rapport
    rapport["etat"] = "echec"
    if not url_manifeste:
        return None
    maintenant = time.time() if maintenant is None else maintenant
    try:
        vu = json.loads(FICHIER_MAJ.read_text(encoding="utf-8"))
        if maintenant - float(vu.get("verifie", 0)) < DELAI_VERIFICATION:
            rapport["etat"] = "trop_tot"
            return None
    except Exception:
        pass
    try:
        if lecteur is None:
            import urllib.request
            with urllib.request.urlopen(url_manifeste, timeout=8) as r:
                texte = r.read(64 * 1024).decode("utf-8", "replace")
        else:
            texte = lecteur(url_manifeste)
    except Exception:
        return None
    finally:
        try:
            FICHIER_MAJ.parent.mkdir(parents=True, exist_ok=True)
            FICHIER_MAJ.write_text(
                json.dumps({"verifie": maintenant}), encoding="utf-8")
        except Exception:
            pass
    manifeste = lire_manifeste(texte)
    if manifeste is None:
        return None
    if version_plus_recente(manifeste["version"]):
        rapport["etat"] = "neuf"
        return manifeste
    rapport["etat"] = "a_jour"
    return None


# --------------------------------------------------------------------------
# Langue de l'interface
# --------------------------------------------------------------------------
import langues as _langues            # noqa: E402  (apres DEFAULT_CONFIG)

LANGUES = ("fr", "en")


def langue_systeme():
    """La langue de Windows, ramenee a celles que Plume parle.

    Tout ce qui n'est pas du francais donne de l'anglais : c'est la langue de
    repli, pas une preference. Un utilisateur allemand lira l'anglais, ce qui
    vaut mieux qu'un francais qu'il ne lit pas.
    """
    try:
        import ctypes
        # La langue de l'INTERFACE de Windows, pas le format regional : on
        # veut savoir dans quelle langue la personne lit, pas comment elle
        # ecrit ses dates.
        nom = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "fr" if (nom & 0x3FF) == 0x0C else "en"   # 0x0C = francais
    except Exception:
        pass
    try:
        import locale
        code = (locale.getdefaultlocale()[0] or "")
        return "fr" if code.lower().startswith("fr") else "en"
    except Exception:
        return "en"


def langue():
    """La langue a employer maintenant."""
    choix = str(CONFIG.get("langue", "auto") or "auto").lower()
    if choix in LANGUES:
        return choix
    return langue_systeme()


def t(cle, *args):
    """Le texte de cette cle, dans la langue en cours.

    Une cle absente renvoie la cle elle-meme plutot que de lever : une phrase
    manquante doit se voir a l'ecran, pas faire tomber la fenetre qui allait
    l'afficher.
    """
    table = _langues.TEXTES.get(langue()) or _langues.TEXTES["en"]
    texte = table.get(cle)
    if texte is None:
        texte = _langues.TEXTES["en"].get(cle, cle)
    if not args:
        return texte
    try:
        return texte % args
    except (TypeError, ValueError):
        return texte


def marques_pluriel(cle, nombre):
    """Les marques de pluriel qu'attend cette phrase, dans cette langue.

    Le francais accorde le nom ET l'adjectif, l'anglais le nom seul : la meme
    phrase n'a donc pas le meme nombre de trous d'une langue a l'autre.
    """
    combien = _langues.PLURIELS.get(cle, {}).get(langue(), 1)
    marque = "" if abs(nombre) <= 1 else "s"
    return tuple([marque] * combien)


def ecrire_config():
    """Enregistre la configuration telle qu'elle est en memoire.

    Vrai si le fichier a bien ete ecrit. Un echec n'arrete rien : le reglage
    reste actif pour la session en cours, il sera simplement oublie a la
    fermeture, ce qui vaut mieux qu'une fenetre qui tombe.
    """
    try:
        CONFIG_FILE.write_text(
            json.dumps(CONFIG, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        return True
    except Exception:
        return False


def definir_reglage(cle, valeur):
    """Change un reglage et l'enregistre. Vrai si quelque chose a change.

    La langue garde sa propre fonction : en changer demande aussi de reecrire
    les pages deja affichees, ce qui ne regarde pas ce module.
    """
    if CONFIG.get(cle) == valeur:
        return False
    CONFIG[cle] = valeur
    ecrire_config()
    return True


def definir_langue(code):
    """Change la langue et l'enregistre. Vrai si le reglage a change."""
    code = str(code or "").lower()
    if code not in LANGUES and code != "auto":
        return False
    if CONFIG.get("langue") == code:
        return False
    CONFIG["langue"] = code
    return ecrire_config()


def ouvrir_reglages_defaut():
    """Ouvre la page de Windows ou l'on choisit son navigateur par defaut.

    Plume ne peut pas se designer elle-meme, et aucun programme ne le peut :
    depuis Windows 10, l'association des protocoles http et https n'est
    modifiable que par un choix explicite de l'utilisateur, dans les
    Parametres. L'ecrire directement dans le registre ne fonctionne pas, et
    ferait de Plume un logiciel qui force la main.

    Ce qu'on fait a la place : l'installateur declare Plume dans
    RegisteredApplications, ce qui la fait APPARAITRE dans la liste, et ce
    lien emmene sur la bonne page, Plume deja designee.
    """
    import subprocess
    for adresse in ("ms-settings:defaultapps?registeredAppUser=Plume",
                    "ms-settings:defaultapps"):
        try:
            subprocess.Popen(["cmd", "/c", "start", "", adresse],
                             creationflags=CREATE_NO_WINDOW)
            return True
        except Exception:
            continue
    return False


def _exe_de_commande(commande):
    """Le chemin de l'executable dans une ligne de commande du registre.

    Les commandes du shell s'ecrivent «"C:\\...\\prog.exe" "%1"». Le chemin
    entre guillemets se prend tel quel ; sans guillemets, on s'arrete au
    premier espace, ce qui suffit pour les commandes que Windows y ecrit.
    """
    commande = (commande or "").strip()
    if not commande:
        return ""
    if commande.startswith('"'):
        fin = commande.find('"', 1)
        return commande[1:fin] if fin > 0 else commande[1:]
    return commande.split(" ")[0]


def _commande_du_progid(progid):
    """La commande d'ouverture associee a ce ProgID, ou une chaine vide.

    On regarde les trois endroits ou le shell la cherche, dans son ordre :
    les classes de l'utilisateur d'abord, puis celles de la machine.
    """
    if not progid:
        return ""
    try:
        import winreg
    except ImportError:
        return ""
    chemin = r"%s\shell\open\command" % progid
    for ruche, base in ((winreg.HKEY_CURRENT_USER, r"Software\Classes"),
                        (winreg.HKEY_CLASSES_ROOT, ""),
                        (winreg.HKEY_LOCAL_MACHINE, r"Software\Classes")):
        try:
            complet = ("%s\\%s" % (base, chemin)) if base else chemin
            with winreg.OpenKey(ruche, complet) as cle:
                valeur = winreg.QueryValueEx(cle, "")[0]
                if valeur:
                    return valeur
        except OSError:
            continue
    return ""


def _exe_associe(protocole):
    """L'executable que le shell designe pour ce protocole, ou une chaine vide.

    C'est la question que Windows se pose quand on clique un lien, posee telle
    quelle. Elle traverse toute sa resolution, alors que lire une cle n'en
    regarde qu'un morceau.
    """
    try:
        import ctypes
        from ctypes import wintypes
        shlwapi = ctypes.WinDLL("shlwapi", use_last_error=True)
        shlwapi.AssocQueryStringW.argtypes = [
            ctypes.c_uint, ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR,
            wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        shlwapi.AssocQueryStringW.restype = ctypes.c_long
        ASSOCF_IS_PROTOCOL = 0x00001000
        ASSOCSTR_EXECUTABLE = 2
        taille = wintypes.DWORD(1024)
        tampon = ctypes.create_unicode_buffer(1024)
        if shlwapi.AssocQueryStringW(ASSOCF_IS_PROTOCOL, ASSOCSTR_EXECUTABLE,
                                     protocole, None, tampon,
                                     ctypes.byref(taille)) != 0:
            return ""
        return tampon.value or ""
    except Exception:
        return ""


def _meme_fichier(un, autre):
    """Vrai si ces deux chemins designent le meme programme."""
    try:
        return (os.path.normcase(os.path.abspath(str(un)))
                == os.path.normcase(os.path.abspath(str(autre))))
    except Exception:
        return False


def est_navigateur_par_defaut():
    """Vrai si les liens https s'ouvrent avec CET executable.

    On demande au shell, pas au registre : la cle `UserChoice` n'est qu'un des
    elements de sa resolution, et elle a deja dit une chose pendant que les
    Parametres en affichaient une autre.

    Le registre sert de repli quand l'appel echoue : une reponse imparfaite
    vaut mieux que pas de reponse.

    Annoncer « c'est fait » alors que les liens partent ailleurs serait le pire
    des deux mondes : la personne cesserait de chercher.
    """
    exe = _exe_associe("https")
    # OpenWith.exe est la reponse de Windows quand aucun programme n'est
    # designe : ce n'est pas un navigateur, c'est le selecteur.
    if exe and not exe.lower().endswith("openwith.exe"):
        return _meme_fichier(exe, EXECUTABLE)

    try:
        import winreg
        chemin = (r"Software\Microsoft\Windows\Shell\Associations"
                  r"\UrlAssociations\https\UserChoice")
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chemin) as cle:
            progid = winreg.QueryValueEx(cle, "ProgId")[0]
    except Exception:
        return False
    if not progid:
        return False
    depuis_cle = _exe_de_commande(_commande_du_progid(progid))
    if not depuis_cle:
        return str(progid) == "PlumeHTML"
    return _meme_fichier(depuis_cle, EXECUTABLE)


def _porte_une_icone(chemin):
    """Vrai si ce fichier contient au moins une icone extractible."""
    try:
        import ctypes
        from ctypes import wintypes
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        shell32.ExtractIconExW.argtypes = [
            wintypes.LPCWSTR, ctypes.c_int,
            ctypes.POINTER(wintypes.HICON), ctypes.POINTER(wintypes.HICON),
            wintypes.UINT]
        shell32.ExtractIconExW.restype = wintypes.UINT
        grande, petite = wintypes.HICON(), wintypes.HICON()
        shell32.ExtractIconExW(str(chemin), 0, ctypes.byref(grande),
                               ctypes.byref(petite), 1)
        trouvee = bool(grande.value or petite.value)
        for h in (grande, petite):
            if h.value:
                user32.DestroyIcon(h)
        return trouvee
    except Exception:
        return False


def ressource_icone():
    """Ce qu'on declare a la barre des taches, sous la forme « module,index ».

    L'executable d'abord : c'est la forme que le shell sait lire partout, et
    PyInstaller y grave l'icone a la construction. Le fichier .ico ne sert que
    de repli, pour le cas ou l'executable n'en porterait pas.
    """
    try:
        exe = Path(EXECUTABLE)
        if exe.exists() and _porte_une_icone(exe):
            return "%s,0" % exe
    except Exception:
        pass
    return "%s,0" % ICONE


# Le volume est tire au curseur, donc il change en continu. Une ecriture par
# pixel parcouru n'aurait aucun sens : on retient la valeur tout de suite, on
# l'ecrit avec un frein.
_SON_ECRIT = [0.0]
# Vrai quand la memoire porte une valeur que le disque n'a pas encore.
_SON_SALE = [False]
FREIN_SON = 3.0


def noter_volume(volume, muet=None, maintenant=None):
    """Retient le volume du lecteur. Vrai si le fichier a ete reecrit.

    Les valeurs hors bornes sont ramenees dans [0, 150] : mpv accepte de
    depasser cent, mais une valeur aberrante venue du tube ne doit pas
    devenir le volume de demain.
    """
    try:
        volume = max(0, min(150, int(round(float(volume)))))
    except (TypeError, ValueError):
        return False
    maintenant = time.time() if maintenant is None else maintenant
    if CONFIG.get("volume") != volume:
        _SON_SALE[0] = True
    CONFIG["volume"] = volume
    if muet is not None:
        muet = bool(muet)
        if CONFIG.get("muet") != muet:
            _SON_SALE[0] = True
        CONFIG["muet"] = muet
    if not _SON_SALE[0]:
        return False
    if maintenant - _SON_ECRIT[0] < FREIN_SON:
        return False        # le drapeau reste leve : rien n'est perdu
    return ecrire_son(maintenant)


def ecrire_son(maintenant=None):
    """Pose sur le disque le volume retenu, s'il ne s'y trouve pas deja.

    Appele par le frein, et sans condition a la fermeture : le dernier reglage
    ne doit pas se perdre parce qu'il est arrive trois secondes avant la fin.
    """
    if not _SON_SALE[0]:
        return False
    _SON_ECRIT[0] = time.time() if maintenant is None else maintenant
    try:
        CONFIG_FILE.write_text(
            json.dumps(CONFIG, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        _SON_SALE[0] = False
        return True
    except Exception:
        return False


def volume_retenu():
    """Le volume et l'etat muet a poser au prochain lancement de mpv."""
    try:
        volume = max(0, min(150, int(CONFIG.get("volume", 100))))
    except (TypeError, ValueError):
        volume = 100
    return volume, bool(CONFIG.get("muet"))


# --------------------------------------------------------------------------
# Telechargement d'une mise a jour
# --------------------------------------------------------------------------
TAILLE_MAX_MAJ = 400 * 1024 * 1024     # octets, garde-fou grossier


def telecharger_mise_a_jour(manifeste, dossier=None, progression=None):
    """Recupere l'installeur annonce, et ne le rend que s'il est le bon.

    `progression` est appele avec (recus, total) pendant la descente, pour que
    l'interface puisse dire ou on en est sans que cette fonction connaisse
    l'interface.

    Renvoie (chemin, raison) : le chemin du fichier verifie et None, ou None
    et la raison de l'echec. Trois raisons possibles, et il vaut mieux les
    distinguer : « manifeste » si l'annonce elle-meme est mal formee,
    « reseau » si le fichier n'a pas pu etre recupere, « empreinte » s'il ne
    correspond pas a ce qui a ete publie. Les deux premieres sont des
    contretemps, la troisieme est un avertissement.

    En cas d'ecart d'empreinte, le fichier est efface : un installeur douteux
    ne doit pas rester a trainer sur le disque, ou quelqu'un finirait par le
    lancer.
    """
    if not manifeste:
        return None, "manifeste"
    url = str(manifeste.get("url") or "")
    attendue = str(manifeste.get("sha256") or "").lower()
    if not url.startswith("https://") or len(attendue) != 64:
        return None, "manifeste"

    dossier = Path(dossier) if dossier else (APP_DIR / "profil")
    try:
        dossier.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None, "reseau"
    nom = url.split("/")[-1] or "Plume-installeur.exe"
    # Le nom vient du reseau : on n'en garde que ce qui ne peut pas designer
    # un autre endroit du disque.
    nom = "".join(c for c in nom if c.isalnum() or c in "-_.")[:80]
    if not nom.lower().endswith(".exe"):
        nom += ".exe"
    cible = dossier / nom

    import hashlib
    import urllib.request
    h = hashlib.sha256()
    recus = 0
    try:
        with urllib.request.urlopen(url, timeout=30) as reponse:
            total = int(reponse.headers.get("Content-Length") or 0)
            if total and total > TAILLE_MAX_MAJ:
                return None, "reseau"
            with open(cible, "wb") as f:
                while True:
                    bloc = reponse.read(256 * 1024)
                    if not bloc:
                        break
                    recus += len(bloc)
                    if recus > TAILLE_MAX_MAJ:
                        raise ValueError("fichier trop gros")
                    h.update(bloc)
                    f.write(bloc)
                    if progression:
                        try:
                            progression(recus, total)
                        except Exception:
                            pass
    except Exception:
        try:
            cible.unlink()
        except OSError:
            pass
        return None, "reseau"

    if h.hexdigest().lower() != attendue:
        try:
            cible.unlink()
        except OSError:
            pass
        return None, "empreinte"
    return cible, None


def dossier_installe():
    """Le dossier ou Plume est installee, pour y reposer la mise a jour.

    C'est celui de l'executable en cours. L'installeur le recevra par /DIR :
    sans cela il proposerait son emplacement par defaut, et une mise a jour
    creerait une seconde installation ailleurs.
    """
    try:
        return str(Path(EXECUTABLE).parent)
    except Exception:
        return str(APP_DIR)
