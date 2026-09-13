# -*- coding: utf-8 -*-
"""
Plume : navigateur de bureau, fenetre unique a onglets, bati sur WebView2.

Google est la page de depart. Chaque onglet possede son propre controle
WebView2 : basculer n'entraine aucun rechargement, les pages restent vivantes,
la video continue. Tout reste dans l'application : une demande venue de
l'interface de recherche, comme un lien qui voudrait ouvrir une fenetre,
devient un onglet.

Sur une page video, le lecteur du site est neutralise et mpv vient dessiner
exactement a sa place. Le reste de la page est intact : titre, description,
recommandations, commentaires, chat.

La session est persistante : cookies et connexions survivent a la fermeture.

WinForms et WebView2 exigent un fil COM en mode STA, que Python n'a pas par
defaut : la boucle tourne donc dans un fil .NET dont on fixe l'appartement,
sinon WebView2 leve RPC_E_CHANGED_MODE.

Usage : pythonw navigateur.py [url]
"""
import ctypes
import importlib.util
import json
import base64
import math
import os
import socket
import subprocess
import sys
import threading
import time

import clr

import barre_taches                                              # noqa: E402

APPID = "Plume.Navigateur"

# Sans identite propre, Windows groupe la fenetre sous Python et affiche son
# icone dans la barre des taches. La declarer avant toute creation de fenetre.
barre_taches.identifier_processus(APPID)

def _dossier_dll():
    """Ou trouver les assemblages WebView2.

    On evite d'importer webview : son chargement fixerait le mode COM du fil,
    et WebView2 exige STA. Dans le paquet autonome, le module n'est meme pas
    installe : seules ses DLL ont ete copiees a cote de l'executable.
    """
    embarque = getattr(sys, "_MEIPASS", None)
    if embarque:
        candidat = os.path.join(embarque, "webview", "lib")
        if os.path.isdir(candidat):
            return candidat
    spec = importlib.util.find_spec("webview")
    if spec and spec.origin:
        return os.path.join(os.path.dirname(spec.origin), "lib")
    for base in (os.path.dirname(os.path.abspath(sys.executable)),
                 os.path.dirname(os.path.abspath(__file__))):
        candidat = os.path.join(base, "webview", "lib")
        if os.path.isdir(candidat):
            return candidat
    raise RuntimeError("assemblages WebView2 introuvables")


LIB = _dossier_dll()
os.environ["PATH"] = (os.path.join(LIB, "runtimes", "win-x64", "native")
                      + os.pathsep + os.environ["PATH"])

clr.AddReference("System")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")
clr.AddReference(os.path.join(LIB, "Microsoft.Web.WebView2.Core.dll"))
clr.AddReference(os.path.join(LIB, "Microsoft.Web.WebView2.WinForms.dll"))

from System import (AppDomain, Action, DateTime, DateTimeKind,   # noqa: E402
                    IntPtr, Uri)
from System.Drawing import (Bitmap, Font, FontStyle, Graphics,  # noqa: E402
                            Icon, Image, Point, Rectangle, Region, Size)
from System.Drawing.Imaging import ImageFormat                     # noqa: E402
from System.IO import MemoryStream                                 # noqa: E402
from System.Threading import ApartmentState, Thread, ThreadStart   # noqa: E402
from System.Threading.Tasks import Task                            # noqa: E402
from System.Windows.Forms import (                                 # noqa: E402
    Application, ApplicationContext, BorderStyle, Cursor, DockStyle, Form,
    FormBorderStyle, FormWindowState, Keys, MouseButtons, Padding, Panel,
    FormStartPosition, Screen, TextBox, Timer, ToolTip,
    UnhandledExceptionMode)
from Microsoft.Web.WebView2.Core import (                          # noqa: E402
    CoreWebView2FaviconImageFormat, CoreWebView2MemoryUsageTargetLevel,
    CoreWebView2WebResourceContext)
from Microsoft.Web.WebView2.WinForms import (                      # noqa: E402
    CoreWebView2CreationProperties, WebView2)

import core                                                        # noqa: E402
import interface as ui                                             # noqa: E402
from incrustation import Incrustation                              # noqa: E402

PROFIL = str(core.APP_DIR / "profil")

# WebView2 lit ce dossier de profil au demarrage. Le declarer ainsi evite
# CoreWebView2Environment.CreateAsync().Result, qui bloque le fil d'interface en
# attendant une operation ayant elle-meme besoin de ce fil : Windows finissait
# par tuer la fenetre avec un « Application Hang ».
os.environ["WEBVIEW2_USER_DATA_FOLDER"] = PROFIL
PORT = 47821                       # canal local pour recevoir de nouveaux onglets
# Page d'accueil locale : un fichier du profil, jamais une page distante.
# C'est aussi ce qui permet a la barre d'adresse de garder le focus a
# l'ouverture d'un onglet, une page web le lui prenant des qu'elle a charge.
ACCUEIL = core.FICHIER_ACCUEIL.as_uri()

# origine des horodatages Unix, pour convertir les dates des cookies
EPOCH = DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)

# Requetes publicitaires et de pistage, bloquees avant meme d'etre emises.
# Les motifs sont ceux acceptes par WebView2 : * remplace n'importe quoi.
MOTIFS_PUBS = [
    "*://*.doubleclick.net/*",
    "*://*.googlesyndication.com/*",
    "*://*.googleadservices.com/*",
    "*://*.google-analytics.com/*",
    "*://*.adservice.google.*/*",
    "*://*.moatads.com/*",
    "*://*.scorecardresearch.com/*",
    "*://*/pagead/*",
    "*://*/ptracking*",
    "*://*.youtube.com/api/stats/ads*",
    "*://*.youtube.com/get_midroll_info*",
    "*://*.youtube.com/youtubei/v1/player/ad_break*",
    "*://*.twitch.tv/*/ads*",
    "*://*.amazon-adsystem.com/*",
]

class POINT_WIN(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT_WIN(ctypes.Structure):
    _fields_ = [("gauche", ctypes.c_long), ("haut", ctypes.c_long),
                ("droite", ctypes.c_long), ("bas", ctypes.c_long)]


class INFOS_ECRAN(ctypes.Structure):
    _fields_ = [("taille", ctypes.c_ulong), ("ecran", RECT_WIN),
                ("travail", RECT_WIN), ("drapeaux", ctypes.c_ulong)]


class INFOS_MINMAX(ctypes.Structure):
    """Ce que Windows demande avant d'agrandir : ou, et jusqu'ou."""
    _fields_ = [("reserve", POINT_WIN), ("taille_max", POINT_WIN),
                ("position_max", POINT_WIN), ("mini", POINT_WIN),
                ("maxi", POINT_WIN)]


# WindowFromPoint prend la structure par valeur : elle doit donc etre declaree
# avant. GA_ROOT remonte du controle survole a la fenetre qui le contient.
user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.WindowFromPoint.restype = ctypes.c_void_p
user32.WindowFromPoint.argtypes = [POINT_WIN]
user32.GetAncestor.restype = ctypes.c_void_p
user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
user32.SetForegroundWindow.restype = ctypes.c_int
GA_ROOT = 2

# Mesure faite : pythonnet ne redirige PAS vers Python les methodes
# virtuelles protegees d'une classe .NET derivee. `Navigateur.WndProc` n'a
# donc jamais ete appele une seule fois, ni les bords saisissables, ni rien
# de ce qui en dependait n'a jamais fonctionne. On installe donc notre propre
# procedure de fenetre, par la voie native, et on chaine vers l'ancienne.
TYPE_PROCEDURE = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_void_p,
                                    ctypes.c_uint, ctypes.c_void_p,
                                    ctypes.c_void_p)
GWLP_WNDPROC = -4
user32.CallWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_uint, ctypes.c_void_p,
                                   ctypes.c_void_p]
user32.CallWindowProcW.restype = ctypes.c_longlong

user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
user32.MonitorFromWindow.restype = ctypes.c_void_p
user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p,
                                   ctypes.POINTER(INFOS_ECRAN)]
user32.GetMonitorInfoW.restype = ctypes.c_int

# Montrer une fenetre sans lui donner le focus : sinon l'apercu qui suit le
# curseur volerait la capture de la souris et interromprait le glissement.
user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_uint]
# Deplacer plusieurs fenetres en une seule fois. Deux SetWindowPos separes
# sont deux repeintures : pendant un glissement, les deux pages se decalent
# alors d'une image l'une par rapport a l'autre, et cela se lit comme un saut.
user32.BeginDeferWindowPos.argtypes = [ctypes.c_int]
user32.BeginDeferWindowPos.restype = ctypes.c_void_p
user32.DeferWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.DeferWindowPos.restype = ctypes.c_void_p
user32.EndDeferWindowPos.argtypes = [ctypes.c_void_p]
user32.EndDeferWindowPos.restype = ctypes.c_int
SWP_NOZORDER = 0x0004
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002

# Une fenetre WS_EX_TRANSPARENT est ignoree par WindowFromPoint : sans cela la
# vignette, posee sous le curseur, se designait elle-meme comme cible.
GWL_EXSTYLE = -20
# Windows n'accroche aux bords que ce qu'il tient pour redimensionnable et
# agrandissable. Une fenetre sans bordure systeme, comme celle de Plume, n'a
# aucun de ces styles : Win+fleche, le glissement vers un bord, les dispositions
# d'ancrage et l'assistant qui propose de remplir l'autre moitie lui sont donc
# tous refuses. On remet les styles, et on efface le cadre qu'ils apportent en
# repondant nous-memes a WM_NCCALCSIZE.
WS_THICKFRAME = 0x00040000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
GWL_STYLE = -16
WM_NCCALCSIZE = 0x0083
WM_GETMINMAXINFO = 0x0024
WM_NCHITTEST = 0x0084
SWP_FRAMECHANGED = 0x0020
HTCLIENT = 1
HTCAPTION = 2
# Dire a Windows « on vient d'appuyer sur la barre de titre » : il prend alors
# le deplacement en charge, avec l'ancrage aux bords, le secouement et le
# retour a la taille normale quand on tire une fenetre agrandie vers le bas.
WM_NCLBUTTONDOWN = 0x00A1
user32.ReleaseCapture.argtypes = []
user32.ReleaseCapture.restype = ctypes.c_int
user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                ctypes.c_void_p, ctypes.c_void_p]
user32.SendMessageW.restype = ctypes.c_longlong
HTMAXBUTTON = 9
MONITOR_AU_PLUS_PRES = 2

# La bordure que Windows 11 dessine autour des fenetres redimensionnables.
# Elle n'appartient pas a la zone client : seul le gestionnaire de fenetres
# peut la changer, et seulement par cet attribut.
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
dwmapi.DwmSetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                         ctypes.c_void_p, ctypes.c_uint]
dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_COLOR_NONE = 0xFFFFFFFE
# Le cadre sombre. 20 depuis Windows 10 20H1, 19 avant : on tente les deux,
# le refus de l'un n'etant pas une erreur.
DWMWA_MODE_SOMBRE = 20
DWMWA_MODE_SOMBRE_ANCIEN = 19

WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
if ctypes.sizeof(ctypes.c_void_p) == 8:
    _lire_style = user32.GetWindowLongPtrW
    _ecrire_style = user32.SetWindowLongPtrW
    _lire_style.restype = ctypes.c_longlong
    _ecrire_style.restype = ctypes.c_longlong
    _ecrire_style.argtypes = [ctypes.c_void_p, ctypes.c_int,
                              ctypes.c_longlong]
else:
    _lire_style = user32.GetWindowLongW
    _ecrire_style = user32.SetWindowLongW
_lire_style.argtypes = [ctypes.c_void_p, ctypes.c_int]


def borner(valeur, mini, maxi):
    return max(mini, min(valeur, maxi)) if maxi >= mini else mini


def _echapper(texte):
    return (str(texte).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# La page d'accueil. Volontairement sobre et sans rien de distant : ni police,
# ni feuille de style, ni image venue d'ailleurs. Ce qu'elle affiche est
# verifiable, on ne promet rien qu'on ne tienne.
def _echapper_js(texte):
    """Chaine JavaScript posee DANS un attribut HTML.

    Deux echappements, pas un : `json.dumps` rend la chaine sure pour
    JavaScript, mais ses guillemets doubles refermaient l'attribut qui la
    contient. Le gestionnaire onclick se retrouvait coupe en deux, sans la
    moindre erreur visible : le clic ne faisait simplement rien. Meme famille
    que le bandeau qui n'avait jamais fonctionne.
    """
    return (json.dumps(texte or "")
            .replace("<", "\\u003c")
            .replace("&", "&amp;")
            .replace('"', "&quot;"))


MODELE_ACCUEIL = """<!doctype html>
<html lang="%(langue_page)s"><head><meta charset="utf-8"><title>Plume</title>
<style>
 :root { color-scheme: dark; }
 body { margin:0; min-height:100vh; display:flex; flex-direction:column;
        align-items:center; justify-content:center; gap:26px;
        background:#12131a; color:#fbfbfe;
        font:15px "Segoe UI",system-ui,sans-serif; }
 h1 { margin:0; font-size:44px; font-weight:600; letter-spacing:-0.5px; }
 h1 span { color:#a78bfa; }
 form { width:min(560px,80vw); display:flex; }
 input { flex:1; padding:13px 18px; border-radius:999px;
         border:1px solid #3a3944; background:#1c1b22; color:#fbfbfe;
         font-size:15px; outline:none; }
 input:focus { border-color:#7c5cff; }
 .tuiles { display:flex; flex-wrap:wrap; gap:10px; justify-content:center;
           width:min(720px,86vw); }
 .tuile { display:flex; align-items:center; gap:9px; padding:9px 14px;
          border-radius:10px; background:#1c1b22; border:1px solid #2b2a33;
          color:#d6d6e0; text-decoration:none; font-size:13px; }
 .tuile:hover { background:#35343f; color:#fbfbfe; }
 .tuile img { width:16px; height:16px; }
 .etoile { color:#a78bfa; }
 .vide { color:#8f8f9e; font-size:13px; }
 .travaux { display:flex; flex-wrap:wrap; gap:12px; justify-content:center;
            width:min(760px,88vw); }
 .titre-section { color:#8f8f9e; font-size:12px; letter-spacing:1.4px;
                  text-transform:uppercase; margin:0 0 -14px; }
 .travail { position:relative; display:flex; align-items:center; gap:11px;
            flex-wrap:wrap;
            padding:13px 42px 13px 16px; border-radius:12px;
            background:#1c1b22; border:1px solid #2b2a33; cursor:pointer;
            min-width:168px; text-align:left; color:#d6d6e0;
            font:inherit; font-size:14px; }
 .travail:hover { background:#35343f; color:#fbfbfe; }
 .travail .pastille { width:10px; height:10px; border-radius:50%%;
                      flex:0 0 auto; }
 .travail .compte { color:#8f8f9e; font-size:12px; }
 .travail .retirer { position:absolute; right:8px; top:50%%;
                     transform:translateY(-50%%); width:24px; height:24px;
                     border:0; border-radius:7px; background:transparent;
                     color:#8f8f9e; font-size:14px; line-height:1;
                     cursor:pointer; }
 .travail .retirer:hover { background:#52515f; color:#fbfbfe; }
 .travail .pastille { cursor:pointer; }
 .travail .palette { display:none; width:100%%; gap:6px; margin-top:8px;
                     padding-top:8px; border-top:1px solid #3a3944;
                     align-items:center; }
 .travail.ouverte .palette { display:flex; }
 .palette .teinte { width:18px; height:18px; border-radius:50%%;
                    border:2px solid transparent; cursor:pointer; padding:0; }
 .palette .teinte.prise { border-color:#fbfbfe; }
 .palette .valider { margin-left:auto; background:#7c5cff; color:#fff;
                     border:0; border-radius:6px; width:24px; height:22px;
                     cursor:pointer; font-size:12px; line-height:1; }
 .palette .valider:hover { background:#8f74ff; }
 footer { position:fixed; bottom:26px; text-align:center; color:#8f8f9e;
          font-size:12px; line-height:1.7; max-width:min(640px,86vw); }
 footer b { color:#d6d6e0; font-weight:600; }
 .reglages { position:fixed; top:18px; right:20px; display:flex; gap:14px;
             align-items:center; font-size:12px; color:#8f8f9e; }
 .reglages button { background:none; border:1px solid transparent;
                    color:#8f8f9e; font:inherit; padding:4px 9px;
                    border-radius:7px; cursor:pointer; }
 .reglages button:hover { color:#fbfbfe; }
 .reglages button[aria-pressed="true"] { color:#fbfbfe; background:#26252f;
                                         border-color:#3a3944; }
 .reglages .defaut { display:inline-flex; align-items:center; gap:7px;
                     border:1px solid #3a3944; border-radius:999px;
                     padding:7px 15px 7px 11px; color:#c9c3dd;
                     background:linear-gradient(180deg,#26252f,#1c1b22);
                     transition:border-color .18s, color .18s, box-shadow .25s,
                                transform .12s; }
 .reglages .defaut svg { opacity:.65; transition:opacity .18s,
                                                 transform .35s; }
 .reglages .defaut:hover { color:#fbfbfe; border-color:#7c5cff;
                           transform:translateY(-1px);
                           box-shadow:0 4px 18px -6px rgba(124,92,255,.85); }
 .reglages .defaut:hover svg { opacity:1; transform:rotate(90deg) scale(1.1); }
 .reglages .defaut:active { transform:translateY(0); }
</style></head><body>
 <div class="reglages">
%(bouton_defaut)s
   <span>%(langue_nom)s</span>
   <button data-langue="fr" aria-pressed="%(fr_choisie)s"
           onclick="changerLangue('fr')">FR</button>
   <button data-langue="en" aria-pressed="%(en_choisie)s"
           onclick="changerLangue('en')">EN</button>
 </div>
 <h1>Plume<span>.</span></h1>
 <form onsubmit="chercher(event)">
   <input id="q" placeholder="%(recherche)s" autocomplete="off">
 </form>
 %(tuiles)s
%(travaux)s
 <footer>
   %(pied_pubs)s<br>
   %(pied_vie_privee)s
 </footer>
<script>
 var moteur = "%(moteur)s";
 function poster(o) {
   try { window.chrome.webview.postMessage(JSON.stringify(o)); }
   catch (e) {}
 }
 function ouvrirTravail(nom) { poster({type:"travail", action:"ouvrir",
                                       nom:nom}); }
 function retirerTravail(e, nom) {
   e.stopPropagation();
   poster({type:"travail", action:"supprimer", nom:nom});
 }
 function ouvrirPalette(e, pastille) {
   e.stopPropagation();
   pastille.closest(".travail").classList.toggle("ouverte");
 }
 function choisirTeinte(e, bouton) {
   e.stopPropagation();
   var palette = bouton.parentNode;
   var prises = palette.querySelectorAll(".teinte.prise");
   if (bouton.classList.contains("prise")) {
     if (prises.length > 1) { bouton.classList.remove("prise"); }
   } else {
     // Deux au maximum : la plus ancienne cede sa place, sans quoi il
     // faudrait deselectionner avant de selectionner.
     if (prises.length >= 2) { prises[0].classList.remove("prise"); }
     bouton.classList.add("prise");
   }
 }
 function validerTeintes(e, nom) {
   e.stopPropagation();
   var palette = e.target.parentNode;
   var indices = [];
   palette.querySelectorAll(".teinte.prise").forEach(function (b) {
     indices.push(parseInt(b.dataset.i, 10));
   });
   if (indices.length) {
     poster({type:"travail", action:"couleurs", nom:nom, indices:indices});
   }
 }
 function changerLangue(code) {
   poster({type:"reglage", cle:"langue", valeur:code});
 }
 function devenirDefaut() {
   poster({type:"reglage", cle:"defaut"});
 }
 function chercher(e) {
   e.preventDefault();
   var t = document.getElementById("q").value.trim();
   if (!t) return;
   if (/^https?:\/\//i.test(t) || /^[\w.-]+\.[a-z]{2,}(\/|$)/i.test(t)) {
     location.href = /^https?:\/\//i.test(t) ? t : "https://" + t;
   } else {
     location.href = moteur.replace("{q}", encodeURIComponent(t));
   }
 }
</script>
</body></html>
"""

H_ONGLETS = 40
H_NAV = 48
H_FAVORIS = 32
SEUIL_GLISSE = 8      # pixels avant qu'un appui devienne un deplacement
MARGE_TEXTE = 32      # de la gauche d'un favori a son titre
MAX_RESTAURES = 20    # au-dela, rouvrir la session couterait trop de memoire
MAX_FENETRES = 4      # meme raison : chaque onglet pese environ 390 Mo
SEUIL_DETACHE = 26    # pixels sous la barre avant qu'un onglet s'en detache
MAX_SUGGESTIONS = 8
# La veille est verifiee a intervalle regulier plutot qu'a chaque evenement :
# un onglet endormi n'a plus rien qui puisse nous prevenir.
PERIODE_VEILLE = 15000       # ms
# Animation des onglets. Deux durees et deux courbes : l'ouverture ralentit en
# arrivant, la fermeture accelere en partant. Une seule courbe pour les deux
# donne un mouvement mou, on l'a deja mesure sur l'animation du lecteur.
PERIODE_ANIM = 16            # ms, soit environ 60 images par seconde
DUREE_OUVERTURE = 0.17       # s
DUREE_FERMETURE = 0.14       # s
DUREE_FENETRE_OUVRE = 0.22   # s, apparition de la fenetre
DUREE_FENETRE_FERME = 0.15   # s, effacement avant fermeture reelle
# Changer d'onglet est le geste le plus frequent d'un navigateur : l'animation
# doit etre finie avant qu'on s'impatiente. Au dela de deux dixiemes, elle
# devient une attente.
DUREE_GLISSE_PAGE = 0.30
# Une page qui tombe va plus vite qu'une page qui glisse : elle accelere, et
# une chute qui s'eternise ne ressemble plus a une chute.
DUREE_CHUTE_PAGE = 0.26   # au-dela, la liste cesse d'aider et encombre
H_SUGGESTION = 34
H_MENU = 30                  # hauteur d'une ligne de menu
H_SEPARATEUR = 9
FENETRES = []         # fenetres Plume ouvertes, dans l'ordre de creation
DERNIERE = [None]     # derniere fenetre activee, cible des ouvertures
MARGE_CROIX = 26      # place reservee a droite pour la croix
ONGLET_MAX = 240
ONGLET_MIN = 88

_JOURNAL = os.environ.get("PLUME_DEBUG")
# Contrairement au journal, celui-ci est toujours ecrit : c'est la seule trace
# qui restera d'un plantage survenu chez quelqu'un d'autre.
LIGNE = chr(10)              # evite un antislash dans un gabarit
FICHIER_PLANTAGES = core.APP_DIR / "profil" / "plantages.txt"
MAX_PLANTAGES = 200 * 1024   # octets, au dela on repart d'un fichier vide


# Positions de lecture, partagees par toutes les fenetres. Chargees une fois,
# ecrites avec un frein : elles changent toutes les cinq secondes par video en
# cours, et cela ne justifie pas une ecriture disque a chaque fois.
_POSITIONS = [None]
_POSITIONS_ECRITES = [0.0]


def positions():
    if _POSITIONS[0] is None:
        _POSITIONS[0] = core.charger_positions()
    return _POSITIONS[0]


def ecrire_positions(force=False):
    if _POSITIONS[0] is None:
        return
    maintenant = time.time()
    if not force and maintenant - _POSITIONS_ECRITES[0] < 20.0:
        return
    _POSITIONS_ECRITES[0] = maintenant
    core.enregistrer_positions(_POSITIONS[0])


def _couleur_win32(couleur):
    """Une couleur .NET en COLORREF, soit 0x00BBGGRR et non l'inverse."""
    return (couleur.B << 16) | (couleur.G << 8) | couleur.R


def _poser_attribut(poignee, attribut, valeur):
    """Pose un attribut entier sur la fenetre. Vrai si le systeme accepte."""
    brut = ctypes.c_uint(valeur)
    try:
        return dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(poignee), attribut,
            ctypes.byref(brut), ctypes.sizeof(brut)) == 0
    except Exception:
        return False


def habiller_cadre(poignee, bordure, fond):
    """Donne au cadre systeme les couleurs de Plume, avant tout dessin.

    Trois attributs, pour trois morceaux que nous ne peignons pas :

    - la bordure, sinon claire et changeante selon que la fenetre est active ;
    - la zone de titre, qui apparaissait en bandeau clair a l'ouverture, le
      temps que notre premier dessin la recouvre ;
    - le mode sombre, qui accorde le reste du cadre au theme de Plume.

    Aucun de ces morceaux n'appartient a la zone client : ni notre dessin ni
    WM_NCCALCSIZE ne les atteignent, seuls ces attributs les changent.
    """
    if not _poser_attribut(poignee, DWMWA_MODE_SOMBRE, 1):
        _poser_attribut(poignee, DWMWA_MODE_SOMBRE_ANCIEN, 1)
    _poser_attribut(poignee, DWMWA_CAPTION_COLOR, _couleur_win32(fond))
    return _poser_attribut(poignee, DWMWA_BORDER_COLOR,
                           _couleur_win32(bordure))


def teinter_bordure(poignee, couleur=None):
    """Donne a la bordure systeme la couleur voulue, ou l'efface.

    Renvoie vrai si le gestionnaire de fenetres a accepte. Il refuse sur les
    Windows anterieurs a 11, ou l'attribut n'existe pas : ce n'est pas une
    erreur, il n'y a simplement pas de bordure a teindre.

    On ne peut pas relire la couleur posee : `DwmGetWindowAttribute` rejette
    cet attribut, qui est en ecriture seule. Mesure faite. Le code de retour de
    l'ecriture est donc la seule verification possible.
    """
    valeur = ctypes.c_uint(DWMWA_COLOR_NONE if couleur is None
                           else _couleur_win32(couleur))
    try:
        return dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(poignee), DWMWA_BORDER_COLOR,
            ctypes.byref(valeur), ctypes.sizeof(valeur)) == 0
    except Exception:
        return False


def _resultat(tache):
    """Valeur rendue par un script de page, ou la raison de son absence."""
    try:
        return str(tache.Result)
    except Exception as e:
        return "illisible : %r" % (e,)


def plantage(ou, erreur=None):
    """Ecrit la pile complete d'une erreur, avec l'endroit d'ou elle vient.

    N'interrompt jamais l'appelant : un incident pendant l'ecriture du rapport
    d'incident ne doit pas remplacer l'incident.
    """
    try:
        import traceback
        if erreur is None:
            texte = traceback.format_exc()
        else:
            texte = "".join(traceback.format_exception(
                type(erreur), erreur, getattr(erreur, "__traceback__", None)))
        journal("PLANTAGE %s : %s" % (ou, texte.strip().splitlines()[-1:]))
        FICHIER_PLANTAGES.parent.mkdir(parents=True, exist_ok=True)
        try:
            if FICHIER_PLANTAGES.stat().st_size > MAX_PLANTAGES:
                FICHIER_PLANTAGES.unlink()
        except OSError:
            pass
        with open(FICHIER_PLANTAGES, "a", encoding="utf-8") as f:
            f.write(LIGNE + "===== %s  %s ====="
                    % (time.strftime("%Y-%m-%d %H:%M:%S"), ou)
                    + LIGNE + texte + LIGNE)
    except Exception:
        pass


def journal(message):
    if not _JOURNAL:
        return
    try:
        with open(_JOURNAL, "a", encoding="utf-8") as f:
            f.write("%.1f  %s\n" % (time.time() % 10000, message))
    except Exception:
        pass


# --------------------------------------------------------------------------
# Script injecte AVANT le chargement de chaque page. C'est l'avantage decisif
# de piloter WebView2 directement : le lecteur du site est musele avant meme
# d'avoir pu demarrer, au lieu d'etre coupe apres coup.
# --------------------------------------------------------------------------
# Mode theatre : c'est la PAGE qui l'implemente, pas nous. On appuie sur son
# propre bouton quand il existe, sinon on lui envoie la touche qu'elle attend.
# mpv suivra tout seul : le script de page renvoie la nouvelle zone du lecteur
# a chaque changement de mise en page.
SCRIPT_THEATRE = r"""
(function () {
  var b = document.querySelector(
    ".ytp-size-button, button[data-a-target='player-theatre-mode-button']");
  if (b) { try { b.click(); return "bouton"; } catch (e) {} }
  var cible = document.querySelector("#movie_player, .video-player")
              || document.body;
  ["keydown", "keyup"].forEach(function (genre) {
    try {
      cible.dispatchEvent(new KeyboardEvent(genre, {
        key: "t", code: "KeyT", keyCode: 84, which: 84,
        bubbles: true, cancelable: true
      }));
    } catch (e) {}
  });
  return "touche";
})();
"""

# Fin d'une video : si la page est une playlist, passer a la suivante.
#
# Le lecteur du site est muselé, donc la page ne sait pas que la video est
# finie et n'enchaine jamais d'elle-meme : une playlist s'arretait au premier
# titre. C'est mpv qui previent, et c'est la page qui navigue, parce qu'elle
# seule connait l'ordre de la liste.
#
# Aucun repli sur « index + 1 » : YouTube ramene un index hors bornes au debut
# de la liste, ce qui ferait tourner la playlist en boucle sans fin. Mieux vaut
# s'arreter que de ne plus savoir s'arreter.
# Demande a la page de se re-annoncer. Le script de page ne signale sa video
# qu'au CHANGEMENT d'adresse ; or un onglet cache voit son annonce jetee
# (`onglet is not self.actif`), et WebView2 gele de toute facon les onglets
# invisibles. Au retour sur l'onglet, la page croyait donc avoir deja tout dit,
# et le lecteur ne demarrait jamais : il fallait rafraichir a la main.
# Remettre l'adresse memorisee a zero suffit : le battement suivant, dans les
# 120 ms, refait l'annonce complete, museler compris.
SCRIPT_REANNONCE = r"""
(function () {
  try {
    if (window.__plume) { window.__plume.url = ""; return "relance"; }
    return "pas de script";
  } catch (e) { return "erreur"; }
})();
"""

SCRIPT_SUIVANT = r"""
(function () {
  try {
    var u = new URL(location.href);
    var liste = u.searchParams.get("list");
    if (!liste) return "hors-liste";
    var courant = u.searchParams.get("v") || "";

    // Toute navigation passe par ici : la liste doit survivre, sinon
    // l'enchainement s'arrete a la video suivante apres avoir eu l'air de
    // marcher. Mesure faite sur une mix : les liens de la page ne la portent
    // pas toujours.
    function aller(href) {
      var cible = new URL(href, location.href);
      if (!cible.searchParams.get("list")) {
        cible.searchParams.set("list", liste);
        var rang = parseInt(u.searchParams.get("index") || "0", 10);
        if (rang > 0) cible.searchParams.set("index", String(rang + 1));
      }
      location.href = cible.href;
    }

    // 1. Le panneau de playlist, quand il est rendu.
    var liens = document.querySelectorAll(
      "ytd-playlist-panel-video-renderer a#wc-endpoint, " +
      "ytd-playlist-panel-renderer a#wc-endpoint, " +
      "#playlist-items a#wc-endpoint");
    for (var i = 0; i < liens.length; i++) {
      var h = liens[i].getAttribute("href") || "";
      if (courant && h.indexOf("v=" + courant) !== -1) {
        var suivant = liens[i + 1];
        if (!suivant || !suivant.href) return "fin-de-liste";
        aller(suivant.href);
        return "panneau";
      }
    }

    // 2. Les donnees de la page. YouTube y decrit sa playlist entiere, que le
    //    panneau soit rendu ou non : c'est la source la plus sure, et la seule
    //    qui sache dire « c'etait la derniere ».
    try {
      var d = window.ytInitialData;
      var pl = d && d.contents
               && d.contents.twoColumnWatchNextResults
               && d.contents.twoColumnWatchNextResults.playlist
               && d.contents.twoColumnWatchNextResults.playlist.playlist;
      var items = (pl && pl.contents) || [];
      var ids = [];
      for (var j = 0; j < items.length; j++) {
        var r = items[j] && items[j].playlistPanelVideoRenderer;
        if (r && r.videoId) ids.push(r.videoId);
      }
      var k = ids.indexOf(courant);
      if (k !== -1 && k + 1 < ids.length) {
        aller("/watch?v=" + encodeURIComponent(ids[k + 1]));
        return "donnees";
      }
      if (k !== -1) return "fin-de-liste";
    } catch (e) {}

    // 3. Le bouton « suivant » du lecteur du site. Son adresse d'abord : un
    //    clic navigue par l'application du site, qui perd la liste quand son
    //    lecteur est musele. Mesure faite : on repartait sans playlist, et
    //    l'enchainement s'arretait la.
    var b = document.querySelector(".ytp-next-button");
    if (b && b.getAttribute("aria-disabled") === "true") return "fin-de-liste";
    if (b && b.href) { aller(b.href); return "bouton-adresse"; }
    if (b) { b.click(); return "bouton-clic"; }
    return "introuvable";
  } catch (e) {
    return "erreur";
  }
})();
"""

JS = r"""
(function () {
  if (window.__plume) return;
  // Choix de l'utilisateur, garde par le site lui-meme : une seule source de
  // verite, et la preference suit naturellement le domaine.
  try {
    if (localStorage.getItem("__plume_lecteur") === "site") return;
  } catch (e) {}
  window.__plume = { url: "", actif: false };

  function envoyer(type, charge) {
    try {
      charge = charge || {};
      charge.type = type;
      window.chrome.webview.postMessage(JSON.stringify(charge));
    } catch (e) {}
  }

  var vraiPlay = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    if (window.__plume.actif) return Promise.resolve();
    return vraiPlay.apply(this, arguments);
  };

  function museler() {
    var v = document.querySelector("video");
    if (!v) return;
    try {
      v.pause();
      v.muted = true;
      if (v.src || v.currentSrc) { v.removeAttribute("src"); v.load(); }
    } catch (e) {}
  }

  // Vider la balise video pourrait faire croire au site que la lecture est
  // terminee, et declencher un enchainement. On retient donc cet evenement,
  // et lui seul : bloquer les autres (error, stalled, suspend) perturbe le
  // fonctionnement normal de la page pour rien.
  document.addEventListener("ended", function (e) {
    if (window.__plume.actif && e.target && e.target.tagName === "VIDEO") {
      e.stopImmediatePropagation();
    }
  }, true);


  // ---- publicites : les masquer et ne jamais les attendre --------------
  // mpv lit le flux de la video, jamais les publicites : yt-dlp ne les
  // recupere pas. Le probleme vient de la page, qui deroule son scenario
  // publicitaire pendant ce temps. On le neutralise.
  var CSS_PUBS = ".video-ads,.ytp-ad-module,.ytp-ad-overlay-container," +
    ".ytp-ad-image-overlay,.ytp-ad-text-overlay,ytd-promoted-video-renderer," +
    "ytd-display-ad-renderer,ytd-ad-slot-renderer,ytd-in-feed-ad-layout-renderer," +
    "ytd-banner-promo-renderer,#masthead-ad,#player-ads," +
    "[data-a-target='video-ad-label'],[data-a-target='video-ad-countdown']" +
    "{display:none!important}";

  function masquerPubs() {
    if (document.getElementById("__plume_css_pubs")) return;
    var s = document.createElement("style");
    s.id = "__plume_css_pubs";
    s.textContent = CSS_PUBS;
    (document.head || document.documentElement).appendChild(s);
  }

  function passerPub() {
    // bouton « Passer les annonces », quel que soit son nom du moment
    var b = document.querySelector(
      ".ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button");
    if (b) { try { b.click(); } catch (e) {} }
    // une publicite en cours : la faire defiler instantanement
    var p = document.querySelector(".ad-showing video, .ytp-ad-player-overlay");
    if (p) {
      var v = document.querySelector("video");
      if (v && v.duration && isFinite(v.duration)) {
        try { v.currentTime = v.duration; } catch (e) {}
      }
    }
  }

  var SELECTEURS = ["#movie_player", ".html5-video-player",
    '[data-a-target="video-player"]', ".video-player__container",
    ".player-container", "video"];

  function zone() {
    for (var i = 0; i < SELECTEURS.length; i++) {
      var el = document.querySelector(SELECTEURS[i]);
      if (!el) continue;
      var r = el.getBoundingClientRect();
      if (r.width > 120 && r.height > 80) return r;
    }
    return null;
  }

  var TWITCH_RESERVES = ["directory","videos","settings","following","subscriptions",
    "u","p","store","subs","drops","downloads","turbo","friends","wallet","prime",
    "search","team","jobs","legal","privacy","security","login","signup","popout",
    "moderator","payments","inventory","clips"];

  function estPageVideo(u) {
    if (/youtube\.com\/(watch\?|shorts\/|live\/)/.test(u)) return true;
    if (/youtu\.be\/[\w-]+/.test(u)) return true;
    if (/vimeo\.com\/\d+/.test(u)) return true;
    if (/dailymotion\.com\/video\//.test(u)) return true;
    var m = u.match(/^https?:\/\/(?:www\.)?twitch\.tv\/([A-Za-z0-9_]+)(?:[\/?#]|$)/i);
    if (m && TWITCH_RESERVES.indexOf(m[1].toLowerCase()) === -1) return true;
    if (/^https?:\/\/(?:www\.)?kick\.com\/[A-Za-z0-9_-]+$/i.test(u)) return true;
    return false;
  }

  function titreVideo() {
    var h = document.querySelector("h1.ytd-watch-metadata, h1 .style-scope");
    return (h ? h.textContent : document.title || "").trim().slice(0, 120);
  }

  function battement() {
    var u = location.href;
    if (u !== window.__plume.url) {
      window.__plume.url = u;
      if (estPageVideo(u)) {
        window.__plume.actif = true;
        museler();
        envoyer("page_video", { url: u, titre: titreVideo() });
      } else {
        window.__plume.actif = false;
        envoyer("hors_video", {});
      }
      envoyer("url", { url: u, titre: document.title || "",
                      lecteur: "plume" });
    }
    if (window.__plume.actif) {
      museler();
      masquerPubs();
      passerPub();
      var r = zone();
      var d = window.devicePixelRatio || 1;
      if (r) {
        // Les bords proches sont arrondis vers le bas, les bords lointains
        // vers le haut : le rectangle couvre alors TOUJOURS le lecteur du
        // site, au lieu de lui etre parfois inferieur d'un pixel. Arrondir
        // separement la position et la largeur, comme avant, laissait
        // apparaitre un liron de la barre de progression rouge de YouTube.
        // Deux pixels de debord par-dessus : la marge du lecteur est noire,
        // ce surplus ne se voit pas, un manque si.
        var DEBORD = 2;
        var g = Math.floor(r.left * d) - DEBORD;
        var h = Math.floor(r.top * d) - DEBORD;
        var dr = Math.ceil((r.left + r.width) * d) + DEBORD;
        var b = Math.ceil((r.top + r.height) * d) + DEBORD;
        envoyer("zone", { x: g, y: h, l: dr - g, h: b - h });
      } else {
        envoyer("zone", { x: 0, y: 0, l: 0, h: 0 });
      }
    }
  }

  setInterval(battement, 120);
  addEventListener("scroll", battement, true);
  addEventListener("resize", battement);
  addEventListener("DOMContentLoaded", function () {
    museler();
    masquerPubs();
    envoyer("url", { url: location.href, titre: document.title || "",
                     lecteur: "plume" });
  });
})();
"""


class Onglet(object):
    """Un onglet : sa vue WebView2, son favicon, et sa vignette dessinee."""

    def __init__(self, navigateur, url):
        self.nav = navigateur
        self.url = url
        self.titre = "Nouvel onglet"
        self.favicon = None
        # Chaque onglet a son lecteur : changer d'onglet ne doit pas tuer la
        # video, seulement la mettre de cote. Au retour, elle reprend ou elle
        # en etait au lieu de tout recharger.
        self.incrustation = Incrustation(au_probleme=navigateur.signaler,
                                         au_action=self.au_action_lecteur)
        self.zone_page = None        # zone du lecteur, en coordonnees de page
        # Taille de la zone de page au moment de cette mesure. Une vue cachee
        # ne refait pas sa mise en page : au retour, la zone peut dater d'une
        # autre taille de fenetre, voire d'un autre ecran.
        self.taille_mesure = None
        self.survole = False
        self.survol_croix = False
        self.endormi = False
        self.derniere_activite = time.time()
        # Part de sa largeur finale, de 0 a 1. L'onglet s'ouvre en s'ecartant.
        self.echelle = 1.0
        self._ouverture = None
        self._fin_traitee = None     # video dont la fin a deja ete enchainee
        # 0 : rien en cours. Sinon, avancement de 0 a 1, pose par etapes au
        # fil des evenements de WebView2 plutot que par un minuteur : une
        # animation a trente images par seconde pour un fil de deux pixels
        # coute plus cher que ce qu'elle apporte.
        self.progression = 0.0
        # « site » quand la page a demande le lecteur d'origine. Le script se
        # tait dans ce cas, donc l'absence de nouvelle vaut « site ».
        self.lecteur_site = False
        self.rect = Rectangle(0, 0, 0, 0)

        self.vue = WebView2()
        # WebView2 peint en BLANC tant que la page n'a rien rendu : sur une
        # interface sombre, chaque onglet neuf lancait un eclair blanc en plein
        # ecran. La couleur de fond par defaut supprime l'eclair sans rien
        # changer aux pages, qui posent la leur par dessus.
        try:
            self.vue.DefaultBackgroundColor = ui.FOND_PAGE
        except Exception as e:
            journal("fond de la vue : %s" % e)
        if navigateur.privee:
            # Meme dossier de profil, mais session privee : WebView2 garde
            # cookies, cache et stockage local en memoire et les jette a la
            # fermeture. A poser avant EnsureCoreWebView2Async, apres quoi la
            # vue n'accepte plus de proprietes de creation.
            options = CoreWebView2CreationProperties()
            options.UserDataFolder = PROFIL
            options.IsInPrivateModeEnabled = True
            self.vue.CreationProperties = options
        self.vue.Dock = DockStyle.Fill
        self.vue.Visible = False
        navigateur.contenu.Controls.Add(self.vue)

        # KeyPreview du formulaire ne voit RIEN quand la page a le focus :
        # WebView2 traite les frappes dans son propre processus. Les raccourcis
        # du navigateur (Ctrl+L, Ctrl+T, Ctrl+W, F5...) etaient donc muets des
        # qu'on avait clique dans la page. Le controle WinForms reexpose les
        # touches d'accelerateur : on s'y branche.
        self.vue.KeyDown += navigateur.au_clavier

        self.vue.CoreWebView2InitializationCompleted += self.au_pret
        self.vue.EnsureCoreWebView2Async(None)
        self.vue.Source = Uri(url)

    # ------------------------------------------------------------------
    def au_pret(self, envoyeur, args):
        try:
            noyau = self.vue.CoreWebView2
            noyau.AddScriptToExecuteOnDocumentCreatedAsync(JS)
            noyau.WebMessageReceived += self.au_message
            noyau.NewWindowRequested += self.au_nouvelle_fenetre
            noyau.NavigationStarting += self.au_depart_navigation
            noyau.ContentLoading += self.au_contenu
            noyau.DOMContentLoaded += self.au_dom
            noyau.NavigationCompleted += self.a_la_fin_navigation
            noyau.DocumentTitleChanged += self.au_titre
            noyau.FaviconChanged += self.au_favicon
            noyau.DownloadStarting += self.au_telechargement
            noyau.Settings.IsStatusBarEnabled = False
            # Un filtre par motif plutot qu'un filtre « * » : seules les
            # requetes visees declenchent l'evenement, le reste du trafic n'est
            # pas ralenti.
            for motif in MOTIFS_PUBS:
                try:
                    noyau.AddWebResourceRequestedFilter(
                        motif, CoreWebView2WebResourceContext.All)
                except Exception:
                    pass
            noyau.WebResourceRequested += self.au_requete
        except Exception as e:
            journal("init onglet : %s" % e)

    def endormir(self):
        """Gele l'onglet : la page reste entiere, mais elle cesse de tourner.

        Suspendre n'est pas decharger. Le DOM, le defilement et les champs
        remplis restent en place ; ce sont les minuteurs, les scripts et les
        connexions qui s'arretent, et c'est la que passe la memoire d'un onglet
        qu'on ne regarde pas. Le retour est instantane, sans rechargement.
        """
        if self.endormi:
            return
        try:
            noyau = self.vue.CoreWebView2
            if noyau is None:
                journal("veille : %s sans noyau" % str(self.url)[:70])
                return
            if noyau.IsSuspended:
                # Deja suspendu sans que Plume l'ait su : l'etat local
                # rattrape le vrai, sinon l'onglet reste « eveille » pour
                # toujours dans nos comptes.
                journal("veille : %s deja suspendu" % str(self.url)[:70])
                self.endormi = True
                self.nav.rafraichir_onglets()
                return
            # A demander avant : une fois suspendu, plus rien ne repond.
            noyau.MemoryUsageTargetLevel = (
                CoreWebView2MemoryUsageTargetLevel.Low)
            tache = noyau.TrySuspendAsync()
        except Exception as e:
            journal("veille : refus pour %s : %r" % (self.url, e))
            return

        def quand_pret(terminee):
            # Le resultat se lit sur le fil qui possede la fenetre, comme tout
            # le reste de WebView2.
            try:
                if not terminee.Result:
                    journal("veille : refusee pour %s" % self.url)
                    return
                self.endormi = True
                journal("veille : %s endormi" % str(self.url)[:70])
                self.nav.rafraichir_onglets()
            except Exception as e:
                journal("veille : suite impossible : %r" % (e,))

        try:
            tache.ContinueWith(Action[Task](quand_pret))
        except Exception as e:
            journal("veille : suite refusee : %r" % (e,))

    def reveiller(self):
        """Rend l'onglet a la vie : il etait gele, pas ferme, rien a recharger."""
        self.derniere_activite = time.time()
        if not self.endormi:
            return
        self.endormi = False
        try:
            noyau = self.vue.CoreWebView2
            if noyau is not None:
                noyau.Resume()
                noyau.MemoryUsageTargetLevel = (
                    CoreWebView2MemoryUsageTargetLevel.Normal)
            journal("veille : %s reveille" % str(self.url)[:70])
        except Exception as e:
            journal("veille : reveil impossible : %r" % (e,))

    def au_action_lecteur(self, nom, valeur):
        """Ce que la barre de mpv demande a la page.

        Appele depuis le fil qui ecoute le tube de mpv : tout ce qui touche a
        WebView2 doit repasser par le fil de la fenetre, sans quoi l'appel
        echoue ou fige l'application.
        """
        if nom == "position":
            # Deux nombres : ou en est la lecture, et la duree totale.
            morceaux = str(valeur or "").split("/")
            if len(morceaux) == 2:
                try:
                    self.nav.noter_position(self, float(morceaux[0]),
                                            float(morceaux[1]))
                except ValueError:
                    pass
            return
        if nom == "son":
            # « volume/muet » : le lecteur signale que l'un des deux a change.
            morceaux = str(valeur or "").split("/")
            if len(morceaux) == 2:
                core.noter_volume(morceaux[0], morceaux[1] == "1")
            return
        if nom == "defiler":
            try:
                pas = int(float(valeur))
            except (TypeError, ValueError):
                return
            script = ("window.scrollBy({top:%d,left:0,behavior:'instant'});"
                      % pas)
        elif nom == "theatre":
            script = SCRIPT_THEATRE
        elif nom == "fini":
            # Une meme video ne doit enchainer qu'une fois : `eof-reached`
            # repasse a vrai si la lecture est relancee sur place.
            cle = core.cle_video(self.url or "")
            if cle and cle == self._fin_traitee:
                return
            self._fin_traitee = cle
            # Vue jusqu'au bout : plus rien a reprendre.
            if cle and positions().pop(cle, None) is not None:
                ecrire_positions(force=True)
            script = SCRIPT_SUIVANT
        else:
            return

        def executer():
            try:
                noyau = self.vue.CoreWebView2
                if noyau is None:
                    return
                tache = noyau.ExecuteScriptAsync(script)
            except Exception as e:
                journal("action lecteur : %s" % e)
                return
            if nom != "defiler":
                # Le script dit ce qu'il a fait. Sans cette trace, une
                # playlist qui n'enchaine pas ne laisse rien a lire : on ne
                # sait meme pas quelle branche a ete prise.
                try:
                    tache.ContinueWith(Action[Task](
                        lambda t: journal("action %s -> %s"
                                          % (nom, _resultat(t)))))
                except Exception:
                    pass

        try:
            self.nav.BeginInvoke(Action(executer))
        except Exception as e:
            journal("action lecteur : renvoi impossible : %s" % e)

    def au_requete(self, envoyeur, args):
        """Refuse les requetes publicitaires, sans meme les emettre."""
        try:
            noyau = self.vue.CoreWebView2
            args.Response = noyau.Environment.CreateWebResourceResponse(
                None, 403, "Blocked by Plume", "")
            self.nav.pubs_bloquees += 1
        except Exception:
            pass

    def avancer_a(self, valeur):
        self.progression = valeur
        self.derniere_activite = time.time()
        if self.nav.actif is self:
            self.nav.rafraichir_navigation()

    def au_depart_navigation(self, envoyeur, args):
        self.avancer_a(0.08)

    def au_contenu(self, envoyeur, args):
        self.avancer_a(0.45)

    def au_dom(self, envoyeur, args):
        self.avancer_a(0.8)

    def a_la_fin_navigation(self, envoyeur, args):
        self.avancer_a(0.0)

    def au_titre(self, envoyeur, args):
        try:
            self.definir_titre(self.vue.CoreWebView2.DocumentTitle)
        except Exception:
            pass

    def au_favicon(self, envoyeur, args):
        """Recupere l'icone du site.

        WebView2 exige d'etre appele depuis le fil qui possede la fenetre. Cet
        evenement s'y trouve deja : on lance la tache ici, et surtout on ne
        l'attend pas. Un `.Result` depuis un fil annexe figeait toute
        l'application, que Windows finissait par tuer.
        """
        try:
            tache = self.vue.CoreWebView2.GetFaviconAsync(
                CoreWebView2FaviconImageFormat.Png)
        except Exception as e:
            journal("favicon : demande refusee : %r" % (e,))
            return

        def quand_pret(terminee):
            try:
                flux = terminee.Result
                if flux is None:
                    journal("favicon : flux vide pour %s" % self.url)
                    return
                # Le flux rendu par WebView2 n'est pas repositionnable, et
                # Image.FromStream l'exige : il levait NotImplementedException,
                # avale par le try, et aucun onglet n'a jamais eu d'icone.
                tampon = MemoryStream()
                flux.CopyTo(tampon)
                tampon.Position = 0
                brute = Image.FromStream(tampon)
                self.favicon = Bitmap(brute)   # copie autonome du tampon
                brute.Dispose()
                tampon.Dispose()
                journal("favicon : recu pour %s" % self.url)
                self.nav.memoriser_favicon(self.url, self.favicon)
                self.nav.rafraichir_onglets()
            except Exception as e:
                journal("favicon : lecture impossible : %r" % (e,))

        try:
            tache.ContinueWith(Action[Task](quand_pret))
        except Exception as e:
            journal("favicon : suite impossible : %r" % (e,))

    def au_telechargement(self, envoyeur, args):
        """Rend un telechargement visible.

        Le fichier arrivait bien dans le dossier Telechargements, mais rien ne
        le disait : ni progression, ni chemin, ni echec. WebView2 sait afficher
        sa propre fenetre de telechargements, elle ne s'ouvre simplement pas
        toute seule.
        """
        try:
            operation = args.DownloadOperation
        except Exception:
            return
        try:
            self.vue.CoreWebView2.OpenDefaultDownloadDialog()
        except Exception as e:
            journal("telechargement : fenetre indisponible : %r" % (e,))

        def au_changement(envoyeur2, args2):
            try:
                etat = str(operation.State)
                if etat == "Completed":
                    chemin = operation.ResultFilePath or ""
                    nom = chemin.replace("\\", "/").split("/")[-1]
                    dossier = chemin[:len(chemin) - len(nom)].rstrip("/\\")
                    self.nav.signaler("Telecharge : %s  (dans %s)"
                                      % (nom, dossier), erreur=False)
                    journal("telechargement termine : %s" % chemin)
                elif etat == "Interrupted":
                    self.nav.signaler("Telechargement interrompu : %s"
                                      % operation.InterruptReason)
                    journal("telechargement interrompu : %s"
                            % operation.InterruptReason)
            except Exception:
                pass

        try:
            operation.StateChanged += au_changement
        except Exception as e:
            journal("telechargement : suivi impossible : %r" % (e,))

    def au_nouvelle_fenetre(self, envoyeur, args):
        """Un lien voulant une fenetre devient un onglet : rien ne sort de l'app.

        Encore faut-il que l'utilisateur l'ait demande. Sans le filtre
        `IsUserInitiated`, tout script appelant `window.open` ouvrait un onglet :
        publicites passees entre les mailles, ouvertures automatiques de
        certains sites. Des onglets apparaissaient donc tout seuls.
        """
        try:
            args.Handled = True          # rien ne sort de l'application
            if not args.IsUserInitiated:
                journal("popup de script refusee : %s" % str(args.Uri)[:90])
                return
            journal("nouvel onglet demande par la page : %s"
                    % str(args.Uri)[:90])
            self.nav.nouvel_onglet(str(args.Uri))
        except Exception as e:
            journal("nouvelle fenetre : %s" % e)

    def au_message(self, envoyeur, args):
        try:
            message = json.loads(args.TryGetWebMessageAsString())
        except Exception:
            return
        self.nav.traiter(self, message)

    # ------------------------------------------------------------------
    def definir_titre(self, titre):
        self.titre = (titre or "Onglet").strip() or "Onglet"
        self.nav.rafraichir_onglets()

    def detruire(self):
        try:
            self.incrustation.detruire()
        except Exception:
            pass
        try:
            self.vue.Dispose()
        except Exception:
            pass
        try:
            self.nav.contenu.Controls.Remove(self.vue)
        except Exception:
            pass


class Navigateur(Form):
    def __init__(self, depart=None, session_fenetre=None, bornes=None,
                 privee=False, vide=False):
        super(Navigateur, self).__init__()
        self._session_fenetre = session_fenetre
        # Taille imposee des la construction. La poser apres Show() ne suffit
        # pas : l'evenement Shown, qui agrandit la fenetre, arrive APRES le
        # retour de Show(), et ecrasait donc la taille demandee.
        self._bornes_voulues = bornes
        self._agrandie_voulue = False
        if bornes is None and session_fenetre:
            memoire = session_fenetre.get("bornes")
            if memoire:
                self._bornes_voulues = Rectangle(*[int(v) for v in memoire])
                self._agrandie_voulue = bool(session_fenetre.get("agrandie"))
        self.privee = privee
        # Une fenetre nee d'un onglet tire n'a pas de fondu : le geste fait
        # deja la transition, et faire apparaitre en fondu une fenetre qui
        # porte une video deja visible donnait un clignotement.
        self._sans_fondu = bool(vide)
        # Vrai une fois que `au_demarrage` a pose la taille definitive. Tant
        # qu'il est faux, `Bounds` est encore celui du constructeur.
        self._pose = False
        # Elle apparait en fondu : posee a zero des la construction, sinon un
        # cadre opaque serait deja a l'ecran quand l'animation demarre.
        self.Opacity = 1.0 if vide else 0.0
        self.Text = "Plume, fenetre privee" if privee else "Plume"
        self.Size = Size(1440, 900)
        self.MinimumSize = Size(900, 560)
        # Un pixel de marge tout autour, rempli par le fond du formulaire :
        # c'est le contour de la fenetre. Les panneaux ancres se placent a
        # l'interieur de cette marge, qui reste donc visible.
        self.BackColor = ui.BORD_PRIVE if privee else ui.BORD_FENETRE
        self.Padding = Padding(1)
        # Plus de barre de titre systeme : les boutons de fenetre sont dessines
        # dans la barre d'onglets, comme dans les navigateurs.
        self.FormBorderStyle = getattr(FormBorderStyle, "None")
        # la maximisation attend au_demarrage : il faut d'abord borner la zone,
        # sinon une fenetre sans bordure recouvre la barre des taches
        try:
            if core.ICONE.exists():
                self.Icon = Icon(str(core.ICONE))
        except Exception:
            pass

        self.onglets = []
        self.actif = None
        self._survol_bouton = None
        self.rect_plus = Rectangle(0, 0, 0, 0)
        self.rect_fenetre = {}       # boutons reduire/agrandir/fermer
        self.pubs_bloquees = 0
        # `_maximise` n'est plus un etat que nous tenons : c'est Windows qui
        # agrandit, et lui seul sait ou il en est. Voir la propriete plus bas.
        # Ce que le systeme repondait la derniere fois qu'on a regarde. Sert
        # a ne reecrire la page d'accueil que lorsque la reponse change.
        self._defaut_connu = None
        self._maj = None                # manifeste en attente, s'il y en a un
        self._maj_en_cours = False
        self._maj_annulee = False
        self._procedure = None          # notre procedure de fenetre
        self._ancienne_procedure = None  # celle de WinForms, que l'on chaine
        self._avant_agrandissement = None
        self._cookies_exportes = 0.0
        # Le deplacement de la fenetre appartient a Windows depuis que la
        # partie libre de la barre repond HTCAPTION : il n'y a plus d'etat a
        # tenir ici. Seul le deplacement d'un ONGLET reste a nous.
        self._glisse_onglet = None    # onglet en train d'etre tire
        self._vient_de_detacher = False
        self._apercu = None           # vignette qui suit le curseur
        self._depot_actif = False     # cette fenetre est la cible visee
        self._selection_champ = False
        self._session_ecrite = 0.0
        self._restauration = True     # ne rien enregistrer pendant la reprise
        self.favoris = core.charger_favoris()
        self._rects_favoris = []      # (cadre, croix) de chaque favori affiche
        self._favicons = {}           # hote -> Image, ou False si aucune
        self._survol_favori = None
        self._rect_etoile = Rectangle(0, 0, 0, 0)
        self._survol_etoile = False
        self._rect_lecteur = Rectangle(0, 0, 0, 0)
        self._survol_lecteur = False
        self._infobulle_posee = None
        self.historique = core.charger_historique()
        self._historique_ecrit = 0.0
        self._suggestions = []        # ce que la liste propose en ce moment
        self._choix_suggestion = -1   # -1 : aucune, on garde la saisie
        self._survol_suggestion = -1
        self._liste = None            # fenetre de la liste, creee au besoin
        self._maj_programmee = False  # vrai quand c'est nous qui ecrivons
        self.zooms = core.charger_zooms()
        self.minuteur_veille = None
        self.minuteur_anim = None
        self._fantomes = []       # onglets fermes, le temps de se retirer
        self._glisse_page = None  # glissement de page en cours, s'il y en a
        self._chute = None        # page d'un onglet ferme, en train de tomber
        self.travail = core.charger_groupes_travail()
        self._menu = None         # fenetre du menu contextuel
        self._anim_fenetre = None   # minuteur d'apparition et d'effacement
        self._ferme_pour_de_bon = False
        self._items_menu = []
        self._survol_menu = -1
        self._fermes = []             # adresses des onglets fermes, pour Ctrl+Maj+T

        self.police = Font("Segoe UI", 9.0)
        # Segoe UI Symbol porte les fleches et la croix. Les polices d'icones
        # de Windows (Segoe Fluent Icons, Segoe MDL2 Assets) ne sont PAS
        # rendues par GDI+ : elles n'affichent que des rectangles vides.
        self.police_icone = Font("Segoe UI Symbol", 11.0)
        self.police_croix = Font("Segoe UI Symbol", 9.0)
        self.police_plus = Font("Segoe UI", 12.0)
        self.police_petite = Font("Segoe UI", 8.0)

        # zone des pages : ajoutee en premier pour que Dock.Fill prenne le reste
        self.contenu = Panel()
        self.contenu.Dock = DockStyle.Fill
        self.contenu.BackColor = ui.FOND_PAGE
        self.Controls.Add(self.contenu)

        self._construire_favoris()
        self._construire_navigation()
        self._construire_onglets()
        # Avec DockStyle.Top, le dernier ajoute se place le plus haut : les
        # favoris doivent donc entrer avant la barre d'adresse.
        self.Controls.Add(self.barre_favoris)
        self.Controls.Add(self.barre_nav)
        self.Controls.Add(self.barre_onglets)

        self.KeyPreview = True
        self.KeyDown += self.au_clavier
        # le lecteur doit coller a la fenetre, pas la suivre avec un temps de retard
        self.Activated += self.a_ete_activee
        self.Move += self.au_deplacement
        self.Resize += self.au_redimensionnement
        self.Shown += self.au_demarrage
        self.FormClosing += self.a_la_fermeture

        self.maj_barre_favoris()
        FENETRES.append(self)
        # `vide` : la fenetre attend l'onglet qu'on lui apporte. Lui en ouvrir
        # un d'abord le ferait apparaitre puis disparaitre, et surtout le
        # chargement d'une page pour rien.
        if not vide:
            self.restaurer_session(depart)
        self._restauration = False
        self.demarrer_veille()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _construire_onglets(self):
        self.barre_onglets = Panel()
        self.barre_onglets.Dock = DockStyle.Top
        self.barre_onglets.Height = H_ONGLETS
        self.barre_onglets.BackColor = ui.FOND_ONGLETS
        self.barre_onglets.Paint += self.peindre_onglets
        self.barre_onglets.MouseMove += self.souris_onglets
        self.barre_onglets.MouseLeave += self.sortie_onglets
        self.barre_onglets.MouseClick += self.clic_onglets
        self.barre_onglets.MouseDown += self.appui_onglets
        self.barre_onglets.MouseUp += self.relache_onglets
        self.barre_onglets.MouseDoubleClick += self.double_clic_onglets
        self.barre_onglets.Resize += lambda e, a: self.barre_onglets.Invalidate()
        ui.double_tampon(self.barre_onglets)

    def _construire_favoris(self):
        """Barre des favoris, sous la barre d'adresse."""
        self.barre_favoris = Panel()
        self.barre_favoris.Dock = DockStyle.Top
        self.barre_favoris.Height = H_FAVORIS
        self.barre_favoris.BackColor = ui.FOND_NAV
        self.barre_favoris.Visible = False
        self.barre_favoris.Paint += self.peindre_favoris
        self.barre_favoris.MouseMove += self.souris_favoris
        self.barre_favoris.MouseLeave += self.sortie_favoris
        self.barre_favoris.MouseClick += self.clic_favoris
        self.barre_favoris.Resize += (
            lambda e, a: self.barre_favoris.Invalidate())
        ui.double_tampon(self.barre_favoris)

    def _construire_navigation(self):
        self.barre_nav = Panel()
        self.barre_nav.Dock = DockStyle.Top
        self.barre_nav.Height = H_NAV
        self.barre_nav.BackColor = ui.FOND_NAV
        self.barre_nav.Paint += self.peindre_navigation
        self.barre_nav.MouseMove += self.souris_navigation
        self.barre_nav.MouseLeave += self.sortie_navigation
        self.barre_nav.MouseClick += self.clic_navigation
        self.barre_nav.Resize += lambda e, a: self.placer_champ()
        ui.double_tampon(self.barre_nav)

        self.champ = TextBox()
        # "None" est un mot-cle Python : impossible en attribut direct
        self.champ.BorderStyle = getattr(BorderStyle, "None")
        self.champ.BackColor = ui.CHAMP_FOND
        self.champ.ForeColor = ui.TEXTE
        self.champ.Font = Font("Segoe UI", 10.5)
        self.champ.KeyDown += self.au_clavier_champ
        self.champ.GotFocus += self.champ_prend_focus
        self.champ.LostFocus += self.champ_perd_focus
        self.champ.MouseUp += self.champ_souris_relachee
        self.champ.TextChanged += self.champ_texte_change
        self.barre_nav.Controls.Add(self.champ)

        # Les elements de la barre sont dessines, donc invisibles pour
        # l'accessibilite comme pour l'infobulle native : on la pose sur le
        # panneau et on change son texte selon ce qui est survole.
        self.infobulle = ToolTip()
        self.infobulle.InitialDelay = 500
        self.infobulle.ReshowDelay = 200

        # gauche : reculer, avancer, recharger, accueil
        self.boutons = [("prec", "←", 12), ("suiv", "→", 50),
                        ("rech", "↻", 88), ("accueil", "⌂", 126)]

    def placer_champ(self):
        r = self.rect_champ()
        self.champ.Location = Point(r.X + 38, r.Y + (r.Height - 19) // 2)
        # 52 px de plus reserves a droite : l'etoile des favoris et, sur une
        # page video, le choix du lecteur.
        self.champ.Width = max(120, r.Width - 54 - 52)
        self.barre_nav.Invalidate()

    def champ_prend_focus(self, envoyeur, args):
        """Selectionne toute l'adresse, comme dans les autres navigateurs.

        Le clic qui donne le focus repose ensuite le curseur et annule la
        selection : il faut donc la remettre au relachement du bouton, sans
        quoi seul le passage au clavier selectionnerait quelque chose.
        """
        self._selection_champ = True
        self.champ.SelectAll()
        self.barre_nav.Invalidate()

    def champ_texte_change(self, envoyeur, args):
        self.barre_nav.Invalidate()
        # seulement quand l'utilisateur tape : une adresse posee par la
        # navigation ne doit pas faire surgir la liste
        if self.champ.Focused and not self._maj_programmee:
            self.montrer_suggestions()

    def champ_perd_focus(self, envoyeur, args):
        self._selection_champ = False
        self.cacher_suggestions()
        self.barre_nav.Invalidate()

    def champ_souris_relachee(self, envoyeur, args):
        if self._selection_champ:
            self._selection_champ = False
            self.champ.SelectAll()

    def rect_champ(self):
        return Rectangle(168, 9, max(160, self.barre_nav.Width - 184), H_NAV - 18)

    # ------------------------------------------------------------------
    # Dessin
    # ------------------------------------------------------------------
    def peindre_navigation(self, envoyeur, args):
        g = args.Graphics
        ui.preparer(g)

        # Fil de progression, au ras du bas de la barre : visible sans
        # occuper de place, et absent des qu'il n'y a rien a dire.
        avancement = getattr(self.actif, "progression", 0.0) if self.actif \
            else 0.0
        if avancement > 0:
            large = int(envoyeur.Width * min(1.0, avancement))
            ui.remplir_arrondi(g, ui.ACCENT, 0, envoyeur.Height - 2,
                               max(2, large), 2, 1)

        for nom, glyphe, x in self.boutons:
            actif = (self._survol_bouton == nom)
            if actif:
                ui.remplir_arrondi(g, ui.ONGLET_SURVOL, x, 10, 30, 28, 8)
            ui.centrer(g, glyphe, self.police_icone,
                       ui.TEXTE if actif else ui.TEXTE2,
                       Rectangle(x, 10, 30, 28))

        r = self.rect_champ()
        if self.champ.Focused:
            ui.remplir_arrondi(g, ui.ACCENT, r.X - 2, r.Y - 2,
                               r.Width + 4, r.Height + 4, 0, "pilule")
        else:
            ui.remplir_arrondi(g, ui.CHAMP_BORD, r.X - 1, r.Y - 1,
                               r.Width + 2, r.Height + 2, 0, "pilule")
        ui.remplir_arrondi(g, ui.CHAMP_FOND, r.X, r.Y, r.Width, r.Height,
                           0, "pilule")
        ui.cadenas(g, ui.TEXTE2, r.X + 15, r.Y + (r.Height - 11) / 2.0)

        self._rect_lecteur = Rectangle(0, 0, 0, 0)
        if self.actif and core.est_video(self.actif.url or ""):
            self._rect_lecteur = Rectangle(r.Right - 56,
                                           r.Y + (r.Height - 20) // 2, 22, 20)
            plume = not self.actif.lecteur_site
            if plume:
                couleur = ui.ACCENT_PALE
            else:
                couleur = ui.TEXTE if self._survol_lecteur else ui.TEXTE2
            ui.ecran_lecteur(g, couleur, self._rect_lecteur.X + 1,
                             self._rect_lecteur.Y + 1, 20, 18, plume)

        # Pas d'etoile sur la page d'accueil : la mettre en favori n'aurait
        # aucun sens, c'est un fichier local propre a chaque installation.
        self._rect_etoile = Rectangle(0, 0, 0, 0)
        if self.actif and self.actif.url and self.actif.url != ACCUEIL:
            self._rect_etoile = Rectangle(r.Right - 30,
                                          r.Y + (r.Height - 22) // 2, 22, 22)
            marque = self.favori_courant() is not None
            if marque:
                couleur = ui.ACCENT_PALE
            else:
                couleur = ui.TEXTE if self._survol_etoile else ui.TEXTE2
            ui.etoile(g, couleur, self._rect_etoile.X + 11,
                      self._rect_etoile.Y + 11, 8, marque)

    def peindre_favoris(self, envoyeur, args):
        g = args.Graphics
        ui.preparer(g)
        self._rects_favoris = []
        x = 10
        for i, favori in enumerate(self.favoris["elements"]):
            titre = favori.get("titre") or favori["url"]
            # Largeur mesuree et non estimee au nombre de lettres : une
            # estimation tronquait des titres qui tenaient largement.
            mesure = g.MeasureString(titre, self.police).Width
            # +6 de jeu : sans cela un titre tombant pile sur la largeur
            # mesuree ressortait quand meme coupe (« Goo... » pour Google).
            largeur = int(min(220, max(88, MARGE_TEXTE + mesure
                                       + MARGE_CROIX + 6)))
            if x + largeur > self.barre_favoris.Width - 10:
                break
            cadre = Rectangle(x, 3, largeur, H_FAVORIS - 6)
            survole = (self._survol_favori == i)
            if survole:
                ui.remplir_arrondi(g, ui.ONGLET_SURVOL, cadre.X, cadre.Y,
                                   cadre.Width, cadre.Height, 7)
            icone = self.favicon_de(favori["url"])
            milieu_y = cadre.Y + (cadre.Height - 16) // 2
            if icone is not None:
                try:
                    g.DrawImage(icone, cadre.X + 9, milieu_y, 16, 16)
                except Exception:
                    icone = None
            if icone is None:      # site jamais visite depuis l'ajout
                ui.etoile(g, ui.ACCENT_PALE, cadre.X + 17,
                          cadre.Y + cadre.Height / 2.0, 6, True)
            croix = Rectangle(cadre.Right - 21, cadre.Y + 5, 16, 16)
            # La place de la croix est reservee en permanence, sinon le titre
            # se raccourcit au passage de la souris.
            ui.texte_tronque(g, titre, self.police,
                             ui.TEXTE if survole else ui.TEXTE2,
                             cadre.X + MARGE_TEXTE, cadre.Y,
                             cadre.Width - MARGE_TEXTE - MARGE_CROIX,
                             cadre.Height, milieu=True)
            if survole:
                ui.centrer(g, "\u2715", self.police_croix, ui.TEXTE, croix)
            self._rects_favoris.append((cadre, croix))
            x += largeur + 4

    def souris_favoris(self, envoyeur, args):
        trouve = None
        for i, (cadre, _croix) in enumerate(self._rects_favoris):
            if cadre.Contains(args.Location):
                trouve = i
                break
        if trouve != self._survol_favori:
            self._survol_favori = trouve
            self.barre_favoris.Invalidate()

    def sortie_favoris(self, envoyeur, args):
        if self._survol_favori is not None:
            self._survol_favori = None
            self.barre_favoris.Invalidate()

    def clic_favoris(self, envoyeur, args):
        for i, (cadre, croix) in enumerate(self._rects_favoris):
            if not cadre.Contains(args.Location):
                continue
            if i >= len(self.favoris["elements"]):
                return
            url = self.favoris["elements"][i]["url"]
            if args.Button == MouseButtons.Middle:
                self.nouvel_onglet(url)
            elif croix.Contains(args.Location):
                del self.favoris["elements"][i]
                self._survol_favori = None
                self.enregistrer_favoris()
            else:
                self.aller(url)
            return

    # ------------------------------------------------------------------
    # Favoris
    # ------------------------------------------------------------------
    def memoriser_favicon(self, url, image):
        """Garde l'icone d'un site, pour l'afficher dans les favoris.

        Une icone est propre au site, pas a la page : elle est rangee sous le
        nom d'hote et sert a tous les favoris du meme domaine. Ecrite une seule
        fois, cet evenement se declenchant a chaque chargement de page.
        """
        h = core.hote(url or "")
        if not h or image is None:
            return
        # Seulement les sites mis en favori : garder l'icone de tout ce qui est
        # visite ferait grossir le dossier sans fin, et reviendrait a tenir une
        # liste des sites frequentes.
        if not any(core.hote(f.get("url") or "") == h
                   for f in self.favoris["elements"]):
            return
        chemin = core.DOSSIER_FAVICONS / (h + ".png")
        if chemin.exists():
            return
        try:
            core.DOSSIER_FAVICONS.mkdir(parents=True, exist_ok=True)
            image.Save(str(chemin), ImageFormat.Png)
            self._favicons.pop(h, None)
            self.rafraichir_favoris()
        except Exception:
            pass

    def favicon_de(self, url):
        """Icone du site, chargee a la demande, ou None."""
        h = core.hote(url or "")
        if not h:
            return None
        if h in self._favicons:
            return self._favicons[h] or None
        image = None
        chemin = core.DOSSIER_FAVICONS / (h + ".png")
        if chemin.exists():
            try:
                # copie en memoire : Image.FromFile garderait le fichier
                # verrouille, et l'icone ne pourrait plus etre remplacee
                original = Image.FromFile(str(chemin))
                image = Bitmap(original)
                original.Dispose()
            except Exception:
                image = None
        self._favicons[h] = image or False
        return image

    def rafraichir_favoris(self):
        try:
            if self.barre_favoris.InvokeRequired:
                self.barre_favoris.Invoke(
                    Action(self.barre_favoris.Invalidate))
            else:
                self.barre_favoris.Invalidate()
        except Exception:
            pass

    def favori_courant(self):
        """Indice du favori correspondant a la page affichee, ou None."""
        if not self.actif or not self.actif.url:
            return None
        url = self.actif.url.rstrip("/")
        for i, favori in enumerate(self.favoris["elements"]):
            if (favori.get("url") or "").rstrip("/") == url:
                return i
        return None

    def basculer_favori(self):
        if not self.actif or not self.actif.url:
            return
        i = self.favori_courant()
        if i is None:
            self.favoris["elements"].append(
                {"url": self.actif.url,
                 "titre": self.actif.titre or self.actif.url})
            # l'onglet a deja l'icone du site : la garder tout de suite, sinon
            # le favori resterait sans icone jusqu'au prochain passage
            self.memoriser_favicon(self.actif.url, self.actif.favicon)
        else:
            del self.favoris["elements"][i]
        self.enregistrer_favoris()

    def basculer_barre_favoris(self):
        self.favoris["barre_visible"] = not self.favoris["barre_visible"]
        self.enregistrer_favoris()
        if not self.favoris["elements"]:
            self.signaler("Aucun favori pour l'instant : cliquez l'etoile "
                          "dans la barre d'adresse pour en ajouter un.")

    def enregistrer_favoris(self):
        core.enregistrer_favoris(self.favoris)
        self.maj_barre_favoris()

    def maj_barre_favoris(self):
        visible = bool(self.favoris["elements"]) and \
            self.favoris["barre_visible"]
        if self.barre_favoris.Visible != visible:
            self.barre_favoris.Visible = visible
            self.replacer()
        self.barre_favoris.Invalidate()
        self.barre_nav.Invalidate()

    def _plan_onglets(self, largeur):
        """Place onglets et fantomes, sans rien dessiner.

        Le calcul precede le dessin : la fin de la barre, ou se posent le
        bouton « + » et le reste, n'est connue qu'une fois tout le monde place.
        """
        rangs = list(self.onglets)
        for fantome in sorted(self._fantomes, key=lambda f: f["indice"]):
            place = min(max(0, fantome["indice"]), len(rangs))
            rangs.insert(place, fantome)

        plan = []
        x = 8
        for element in rangs:
            if isinstance(element, dict):
                lf = max(0, int(largeur * element["echelle"]))
                plan.append(("fantome", element, x, lf))
                x += lf + 2
                continue
            lv = max(0, int(largeur * element.echelle))
            element.rect = Rectangle(x, 6, lv, H_ONGLETS - 6)
            plan.append(("onglet", element, x, lv))
            x += lv + 2
        return plan, x

    def peindre_onglets(self, envoyeur, args):
        g = args.Graphics
        ui.preparer(g)

        # Cette fenetre est visee par un onglet en cours de deplacement :
        # on le montre, sinon rien ne dit ou il va atterrir.
        if self._depot_actif:
            large = max(4, self.barre_onglets.Width - 4)
            ui.remplir_arrondi(g, ui.ONGLET_SURVOL, 2, 2, large,
                               H_ONGLETS - 4, 10)
            # Un fond a peine plus clair ne se remarque pas : le contour, si.
            ui.contour_arrondi(g, ui.ACCENT, 2, 2, large, H_ONGLETS - 4, 10, 2)

        tire = (self._glisse_onglet or {}).get("onglet")
        largeur = self.largeur_onglet()
        plan, fin = self._plan_onglets(largeur)

        x = fin
        for genre, element, xe, largeur_vue in plan:
            x = xe
            if genre == "fantome":
                # fantome : la place se referme, rien de cliquable dedans
                if largeur_vue > 6:
                    ui.remplir_arrondi(g, ui.FOND_ONGLETS, x, 6, largeur_vue,
                                       H_ONGLETS - 6, 9, "haut")
                    part = element["echelle"]
                    ui.etincelle(g, ui.avec_alpha(ui.ACCENT_PALE, 190 * part),
                                 x + largeur_vue / 2.0, 22, 11.0 * part)
                continue
            onglet = element
            actif = (onglet is self.actif)
            naissance = onglet._ouverture is not None
            if onglet is tire:
                # l'onglet suit le curseur : sa place reste marquee, en creux
                ui.remplir_arrondi(g, ui.FOND_ONGLETS, x, 6, largeur_vue,
                                   H_ONGLETS - 6, 9, "haut")
                continue
            if largeur_vue < 12:
                # trop etroit pour montrer quoi que ce soit sans bavure
                continue
            if actif:
                ui.remplir_arrondi(g, ui.ONGLET_ACTIF_TEINTE, x, 6,
                                   largeur_vue, H_ONGLETS - 6, 9, "haut")
                # Le contour fait tout le tour de l'onglet, au lieu du trait
                # coupe qui ne couvrait que le haut. Il descend trois pixels
                # plus bas que la barre : son trait du bas tombe donc hors du
                # panneau, et l'onglet reste ouvert vers la page, comme il
                # doit l'etre.
                ui.contour_arrondi(g, ui.ACCENT, x, 6, largeur_vue - 1,
                                   H_ONGLETS - 3, 9, 2, "haut")
            elif onglet.survole:
                ui.remplir_arrondi(g, ui.ONGLET_SURVOL, x, 6, largeur_vue,
                                   H_ONGLETS - 6, 9, "haut")

            decalage = 11
            if naissance:
                # L'etincelle prend la place de l'icone pendant l'ouverture :
                # sans cette reserve, elle se dessinait sur le titre.
                decalage = 33
            elif onglet.favicon is not None:
                try:
                    g.DrawImage(onglet.favicon, Rectangle(x + 11, 15, 16, 16))
                    decalage = 33
                except Exception:
                    decalage = 11

            if onglet.endormi:
                couleur_titre = ui.TEXTE3
            elif actif:
                couleur_titre = ui.TEXTE
            else:
                couleur_titre = ui.TEXTE2
            if naissance:
                # Le titre entre en fondu derriere l'etincelle, au lieu
                # d'apparaitre d'un bloc a la fin de l'animation.
                couleur_titre = ui.avec_alpha(
                    couleur_titre, 255 * onglet.echelle * onglet.echelle)
            ui.texte_tronque(g, onglet.titre, self.police, couleur_titre,
                             x + decalage, 14, largeur_vue - decalage - 28, 18)
            if onglet.endormi:
                # Un point en retrait vaut mieux qu'une icone : il dit « en
                # veille » sans laisser croire que l'onglet est casse.
                ui.remplir_arrondi(g, ui.TEXTE3, x + 4, 21, 4, 4, 2)

            if naissance:
                # La marque de Plume eclot a la place de l'icone, et un trait
                # d'accent balaye le haut de l'onglet : une ouverture qui se
                # voit, sans rien couter une fois l'animation finie.
                part = onglet.echelle
                ui.etincelle(g, ui.avec_alpha(ui.ACCENT_PALE,
                                              255 * (1.0 - part)),
                             x + 19, 23, 10.0 * math.sin(math.pi * part))
                balai = max(18, int(largeur_vue * 0.34))
                ui.remplir_arrondi(
                    g, ui.avec_alpha(ui.ACCENT, 210 * (1.0 - part * part)),
                    x + int((largeur_vue - balai) * part), 6, balai, 3, 1.5)

            if (actif or onglet.survole) and largeur_vue > 70:
                if onglet.survol_croix:
                    ui.remplir_arrondi(g, ui.CROIX_SURVOL,
                                       x + largeur_vue - 28, 13, 21, 21, 6)
                ui.centrer(g, "✕", self.police_croix,
                           ui.TEXTE if onglet.survol_croix else ui.TEXTE2,
                           Rectangle(x + largeur_vue - 28, 13, 21, 21))

        # La boucle a laisse `x` sur le dernier element dessine : la suite se
        # place apres le dernier onglet, pas dessus.
        x = fin
        if self._depot_actif:
            # trait d'insertion : la ou l'onglet se posera
            ui.remplir_arrondi(g, ui.ACCENT, x + 1, 8, 3, H_ONGLETS - 12, 2)

        self.rect_plus = Rectangle(x + 2, 9, 30, 26)
        survol = (self._survol_bouton == "plus")
        if survol:
            ui.remplir_arrondi(g, ui.ONGLET_SURVOL, self.rect_plus.X,
                               self.rect_plus.Y, 30, 26, 8)
        ui.centrer(g, "+", self.police_plus,
                   ui.TEXTE if survol else ui.TEXTE2, self.rect_plus)

        if self.privee:
            # Marque explicite : une fenetre privee qui ne se distingue pas
            # d'une autre est un piege, on finit par taper au mauvais endroit.
            insigne = Rectangle(self.rect_plus.Right + 8, 11, 66, 22)
            if insigne.Right < self.barre_onglets.Width - 140:
                ui.remplir_arrondi(g, ui.BORD_PRIVE, insigne.X, insigne.Y,
                                   insigne.Width, insigne.Height, 11)
                ui.centrer(g, "prive", self.police, ui.TEXTE, insigne)

        # boutons de fenetre, cales a droite
        largeur_b = 44
        droite = self.barre_onglets.Width
        maximisee = self._maximise
        genres = ("reduire", "restaurer" if maximisee else "agrandir", "fermer")
        self.rect_fenetre = {}
        for i, genre in enumerate(genres):
            r = Rectangle(droite - largeur_b * (3 - i), 0, largeur_b, H_ONGLETS)
            self.rect_fenetre[genre] = r
            ui.bouton_fenetre(g, genre, r, ui.TEXTE2,
                              survole=(self._survol_bouton == genre))

    def largeur_onglet(self):
        if not self.onglets:
            return ONGLET_MAX
        place = max(self.barre_onglets.Width - 60 - 132, 200)   # 132 : boutons
        # Un onglet qui se retire compte encore pour la place qu'il occupe :
        # sans cela les autres sauteraient d'un coup a leur nouvelle largeur.
        compte = (len(self.onglets)
                  + sum(f["echelle"] for f in self._fantomes))
        return int(max(ONGLET_MIN,
                       min(ONGLET_MAX, place / max(1.0, compte) - 2)))

    def rafraichir_navigation(self):
        try:
            if self.barre_nav.InvokeRequired:
                self.barre_nav.Invoke(Action(self.barre_nav.Invalidate))
            else:
                self.barre_nav.Invalidate()
        except Exception:
            pass

    def rafraichir_onglets(self):
        try:
            if self.barre_onglets.InvokeRequired:
                self.barre_onglets.Invoke(Action(self.barre_onglets.Invalidate))
            else:
                self.barre_onglets.Invalidate()
        except Exception:
            pass

    @property
    def _maximise(self):
        """Vrai si la fenetre est agrandie, selon Windows lui-meme.

        Plume tenait cet etat a la main et posait les dimensions elle-meme,
        pour contourner un defaut de `MaximizedBounds`. Le contournement
        interdisait l'ancrage systeme : une fenetre dont l'etat reste Normal
        n'est jamais rendue a sa taille par Win+fleche. Le defaut est
        maintenant traite a sa source, dans `_bornes_agrandissement`.
        """
        try:
            return self.WindowState == FormWindowState.Maximized
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Souris
    # ------------------------------------------------------------------
    def souris_onglets(self, envoyeur, args):
        if self._glisse_onglet:
            # On ne decide rien avant le relachement : c'est ce qui permet de
            # deposer l'onglet dans la barre d'une autre fenetre plutot que de
            # le detacher des qu'il descend.
            ecran = self.barre_onglets.PointToScreen(args.Location)
            depart = self._glisse_onglet["depart"]
            if (abs(ecran.X - depart[0]) > 12
                    or abs(ecran.Y - depart[1]) > 12):
                if not self._glisse_onglet["actif"]:
                    self._glisse_onglet["actif"] = True
                    self._ouvrir_apercu(self._glisse_onglet["onglet"])
                    self.barre_onglets.Invalidate()
                self._deplacer_apercu(ecran.X, ecran.Y)
                cible = self._fenetre_sous(ecran.X, ecran.Y)
                self._viser(cible)
                # Tant que le curseur reste sur NOTRE barre, le geste range
                # les onglets. Des qu'il vise une autre fenetre ou qu'il
                # descend vers la page, il redevient un deplacement.
                if cible is None and -8 <= args.Y <= H_ONGLETS + SEUIL_DETACHE:
                    if self._reordonner(self._glisse_onglet["onglet"],
                                        args.X):
                        self._glisse_onglet["reordonne"] = True
                        self.barre_onglets.Invalidate()
            return
        change = False
        for onglet in self.onglets:
            dedans = onglet.rect.Contains(args.Location)
            croix = dedans and args.X >= onglet.rect.Right - 30
            if dedans != onglet.survole or croix != onglet.survol_croix:
                onglet.survole, onglet.survol_croix = dedans, croix
                change = True
        nom = None
        for genre, r in self.rect_fenetre.items():
            if r.Contains(args.Location):
                nom = genre
                break
        if nom is None and self.rect_plus.Contains(args.Location):
            nom = "plus"
        if nom != self._survol_bouton:
            self._survol_bouton = nom
            change = True
        if change:
            self.barre_onglets.Invalidate()

    def _reordonner(self, onglet, x):
        """Place l'onglet tire la ou le curseur le designe. Vrai s'il a bouge.

        La place se decide par rapport au MILIEU des autres onglets : un
        onglet passe devant son voisin des que le curseur depasse le centre de
        celui-ci, et pas avant. Se fier au bord gauche ferait permuter dix
        fois pour un mouvement d'un pixel autour de la frontiere.
        """
        if onglet not in self.onglets or len(self.onglets) < 2:
            return False
        # La place se calcule sur la geometrie de la barre, PAS sur les
        # rectangles des onglets : ceux-ci ne sont mis a jour qu'au prochain
        # dessin, or `Invalidate` ne dessine pas tout de suite. Deux mouvements
        # de souris avant une repeinture lisaient donc des positions perimees,
        # et les onglets permutaient dans un sens puis dans l'autre.
        #
        # Ici la place est une fonction pure de l'abscisse : un meme point
        # designe toujours la meme place. La frontiere tombe a mi-chemin entre
        # deux centres, ce qui donne le comportement attendu, un onglet passe
        # devant son voisin quand il a franchi la moitie du chemin.
        largeur = self.largeur_onglet()
        pas = largeur + 2.0
        cible = int(math.floor((x - 8 - largeur / 2.0) / pas + 0.5))
        cible = max(0, min(len(self.onglets) - 1, cible))
        if self.onglets.index(onglet) == cible:
            return False
        self.onglets.remove(onglet)
        self.onglets.insert(cible, onglet)
        return True

    def sortie_onglets(self, envoyeur, args):
        for onglet in self.onglets:
            onglet.survole = onglet.survol_croix = False
        self._survol_bouton = None
        self.barre_onglets.Invalidate()

    def montrer_suggestions(self):
        """Affiche la liste sous la barre d'adresse, ou la referme si vide.

        C'est une fenetre a part, et non un panneau : un controle WinForms ne
        peut pas se dessiner au-dessus de WebView2, qui possede sa propre
        fenetre. Meme contrainte que pour le lecteur mpv.
        """
        self._suggestions = self.calculer_suggestions(self.champ.Text)
        self._choix_suggestion = -1
        self._survol_suggestion = -1
        if not self._suggestions or not self.champ.Focused:
            self.cacher_suggestions()
            return
        hauteur = len(self._suggestions) * H_SUGGESTION + 8
        r = self.rect_champ()
        try:
            origine = self.barre_nav.PointToScreen(Point(r.X, r.Bottom + 4))
        except Exception:
            return
        if self._liste is None:
            self._liste = self._creer_liste()
            if self._liste is None:
                return
        self._liste.Size = Size(r.Width, hauteur)
        poignee = self._liste.Handle.ToInt64()
        user32.SetWindowPos(ctypes.c_void_p(poignee),
                            ctypes.c_void_p(HWND_TOPMOST),
                            origine.X, origine.Y, r.Width, hauteur,
                            SWP_NOACTIVATE | SWP_SHOWWINDOW)
        self._liste.Invalidate()

    def _creer_liste(self):
        try:
            liste = Form()
            liste.FormBorderStyle = getattr(FormBorderStyle, "None")
            liste.StartPosition = FormStartPosition.Manual
            liste.ShowInTaskbar = False
            # Pas de TopMost par WinForms : son affectation active la fenetre,
            # et la barre d'adresse perdait le focus des l'apparition de la
            # liste. On passe uniquement par SetWindowPos, qui sait ne pas
            # activer.
            liste.BackColor = ui.FOND_NAV
            liste.Paint += self._peindre_suggestions
            liste.MouseMove += self._souris_suggestions
            liste.MouseClick += self._clic_suggestions
            liste.MouseLeave += self._sortie_suggestions
            ui.double_tampon(liste)
            poignee = liste.Handle.ToInt64()
            # NOACTIVATE et rien d'autre : la liste doit recevoir les clics,
            # mais jamais le focus, sinon la barre d'adresse le perdrait et la
            # liste se refermerait sous le doigt.
            style = _lire_style(ctypes.c_void_p(poignee), GWL_EXSTYLE)
            _ecrire_style(ctypes.c_void_p(poignee), GWL_EXSTYLE,
                          int(style) | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
            return liste
        except Exception as e:
            journal("suggestions : %s" % e)
            return None

    def cacher_suggestions(self):
        self._suggestions = []
        self._choix_suggestion = -1
        if self._liste is None:
            return
        try:
            user32.ShowWindow(ctypes.c_void_p(self._liste.Handle.ToInt64()), 0)
        except Exception:
            pass

    def _peindre_suggestions(self, envoyeur, args):
        g = args.Graphics
        ui.preparer(g)
        largeur = envoyeur.Width
        ui.remplir_arrondi(g, ui.FOND_NAV, 0, 0, largeur, envoyeur.Height, 10)
        ui.contour_arrondi(g, ui.CHAMP_BORD, 0, 0, largeur - 1,
                           envoyeur.Height - 1, 10, 1)
        for i, (genre, url, titre) in enumerate(self._suggestions):
            y = 4 + i * H_SUGGESTION
            if i == self._choix_suggestion or i == self._survol_suggestion:
                ui.remplir_arrondi(g, ui.ONGLET_SURVOL, 4, y,
                                   largeur - 8, H_SUGGESTION, 7)
            if genre == "recherche":
                # loupe sommaire : un cercle et sa poignee, dessines a la main
                # plutot qu'une police d'icones qui manquerait ailleurs
                ui.cercle(g, ui.TEXTE2, 18, y + H_SUGGESTION / 2.0 - 2, 5, 1.4)
                ui.trait(g, ui.TEXTE2, 21, y + H_SUGGESTION / 2.0 + 2,
                         25, y + H_SUGGESTION / 2.0 + 6, 1.4)
            elif genre == "favori":
                ui.etoile(g, ui.ACCENT_PALE, 18, y + H_SUGGESTION / 2.0, 6,
                          True)
            else:
                ui.etoile(g, ui.TEXTE2, 18, y + H_SUGGESTION / 2.0, 5, False,
                          1.2)
            ui.texte_tronque(g, titre, self.police, ui.TEXTE, 34, y + 3,
                             largeur - 44, 16)
            ui.texte_tronque(g, core.resume_url(url), self.police_petite,
                             ui.TEXTE2, 34, y + 17, largeur - 44, 14)

    def _ligne_sous(self, y):
        i = (y - 4) // H_SUGGESTION
        return i if 0 <= i < len(self._suggestions) else -1

    def _souris_suggestions(self, envoyeur, args):
        i = self._ligne_sous(args.Y)
        if i != self._survol_suggestion:
            self._survol_suggestion = i
            envoyeur.Invalidate()

    def _sortie_suggestions(self, envoyeur, args):
        if self._survol_suggestion != -1:
            self._survol_suggestion = -1
            envoyeur.Invalidate()

    def _clic_suggestions(self, envoyeur, args):
        i = self._ligne_sous(args.Y)
        if i < 0:
            return
        url = self._suggestions[i][1]
        self.cacher_suggestions()
        self.aller(url)

    def deplacer_choix(self, pas):
        """Deplace la selection dans la liste, en repartant de la saisie."""
        if not self._suggestions:
            return False
        total = len(self._suggestions)
        self._choix_suggestion += pas
        if self._choix_suggestion < -1:
            self._choix_suggestion = total - 1
        elif self._choix_suggestion >= total:
            self._choix_suggestion = -1
        if self._liste is not None:
            self._liste.Invalidate()
        return True

    def _ouvrir_apercu(self, onglet):
        """Petite vignette de l'onglet, qui suivra le curseur.

        Montree par SetWindowPos et non par Show() : afficher normalement une
        fenetre lui donne le focus, ce qui romprait la capture de la souris et
        donc le glissement en cours.
        """
        try:
            vignette = Form()
            vignette.FormBorderStyle = getattr(FormBorderStyle, "None")
            vignette.StartPosition = FormStartPosition.Manual
            vignette.ShowInTaskbar = False
            vignette.TopMost = True
            vignette.Size = Size(228, 34)
            vignette.BackColor = ui.ONGLET_ACTIF
            vignette.Opacity = 0.92
            vignette.Tag = onglet
            vignette.Paint += self._peindre_apercu
            poignee = vignette.Handle.ToInt64()   # force la creation
            style = _lire_style(ctypes.c_void_p(poignee), GWL_EXSTYLE)
            _ecrire_style(ctypes.c_void_p(poignee), GWL_EXSTYLE,
                          int(style) | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
                          | WS_EX_NOACTIVATE)
            user32.SetWindowPos(ctypes.c_void_p(poignee),
                                ctypes.c_void_p(HWND_TOPMOST), 0, 0, 0, 0,
                                SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
            self._apercu = vignette
        except Exception as e:
            journal("apercu : %s" % e)
            self._apercu = None

    def _peindre_apercu(self, envoyeur, args):
        g = args.Graphics
        ui.preparer(g)
        onglet = envoyeur.Tag
        ui.remplir_arrondi(g, ui.ONGLET_ACTIF, 0, 0, 228, 34, 9)
        ui.souligner(g, ui.ACCENT, 10, 1, 208)
        decalage = 11
        if onglet is not None and onglet.favicon is not None:
            try:
                g.DrawImage(onglet.favicon, Rectangle(11, 9, 16, 16))
                decalage = 33
            except Exception:
                decalage = 11
        titre = onglet.titre if onglet is not None else ""
        ui.texte_tronque(g, titre, self.police, ui.TEXTE,
                         decalage, 8, 228 - decalage - 12, 18)

    def _deplacer_apercu(self, ecran_x, ecran_y):
        if self._apercu is None:
            return
        try:
            poignee = self._apercu.Handle.ToInt64()
            user32.SetWindowPos(ctypes.c_void_p(poignee),
                                ctypes.c_void_p(HWND_TOPMOST),
                                int(ecran_x) - 40, int(ecran_y) - 17, 0, 0,
                                SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        except Exception:
            pass

    def _fermer_apercu(self):
        vignette, self._apercu = self._apercu, None
        if vignette is None:
            return
        try:
            vignette.Close()
            vignette.Dispose()
        except Exception:
            pass

    def _viser(self, cible):
        """Marque la fenetre qui recevrait l'onglet, pour qu'elle le montre."""
        for fenetre in FENETRES:
            voulu = (fenetre is cible)
            if fenetre._depot_actif != voulu:
                fenetre._depot_actif = voulu
                try:
                    fenetre.barre_onglets.Invalidate()
                except Exception:
                    pass

    def _fenetre_sous(self, ecran_x, ecran_y):
        """Fenetre Plume dont la barre d'onglets est sous ce point.

        On demande a Windows quelle fenetre occupe reellement ce point, plutot
        que de parcourir les notres : deux peuvent se recouvrir, et seule celle
        du dessus doit recevoir l'onglet.
        """
        try:
            sous = user32.WindowFromPoint(POINT_WIN(int(ecran_x),
                                                    int(ecran_y)))
            racine = int(user32.GetAncestor(sous, GA_ROOT) or 0)
        except Exception:
            return None
        if not racine:
            return None
        for fenetre in FENETRES:
            if fenetre is self:
                continue
            try:
                if fenetre.IsDisposed or fenetre.Handle.ToInt64() != racine:
                    continue
                origine = fenetre.barre_onglets.PointToScreen(Point(0, 0))
                taille = fenetre.barre_onglets.Size
            except Exception:
                continue
            if (origine.X <= ecran_x <= origine.X + taille.Width
                    and origine.Y <= ecran_y <= origine.Y + taille.Height):
                return fenetre
        return None

    def deposer_onglet(self, onglet, ecran_x, ecran_y, y_local):
        """Decide du sort d'un onglet relache : autre fenetre, ou la sienne."""
        cible = self._fenetre_sous(ecran_x, ecran_y)
        if cible is not None:
            return self.transferer_onglet(onglet, cible)
        if y_local > H_ONGLETS + SEUIL_DETACHE:
            return self.detacher_onglet(onglet, ecran_x, ecran_y)
        return False

    def accueillir_onglet(self, onglet):
        """Recoit un onglet venu d'une autre fenetre, sans le recharger.

        Le controle WebView2 change simplement de parent : les deux fenetres
        vivent sur le meme fil, WinForms se contente donc d'un `SetParent` et
        ne recree pas la poignee. La page continue exactement ou elle en
        etait, defilement et lecture video compris.
        """
        ancien = onglet.nav
        # Si le moteur etait vivant avant, il doit l'etre encore apres. Le
        # risque du deplacement est que WinForms recree la poignee du
        # controle : la page deviendrait blanche, ce qui serait pire qu'un
        # rechargement. On verifie, et on revient en arriere le cas echeant.
        try:
            avait_noyau = onglet.vue.CoreWebView2 is not None
        except Exception:
            avait_noyau = False
        try:
            onglet.vue.KeyDown -= ancien.au_clavier
        except Exception:
            pass
        try:
            self.contenu.Controls.Add(onglet.vue)
        except Exception as e:
            journal("accueil d'onglet : %s" % e)
            try:
                onglet.vue.KeyDown += ancien.au_clavier
            except Exception:
                pass
            return False
        if avait_noyau:
            try:
                perdu = onglet.vue.CoreWebView2 is None
            except Exception:
                perdu = True
            if perdu:
                journal("accueil d'onglet : le moteur n'a pas survecu au "
                        "deplacement, retour en arriere")
                try:
                    ancien.contenu.Controls.Add(onglet.vue)
                    onglet.vue.KeyDown += ancien.au_clavier
                except Exception:
                    pass
                return False
        onglet.nav = self
        onglet.echelle = 1.0
        onglet._ouverture = None
        onglet.survole = False
        onglet.survol_croix = False
        try:
            onglet.vue.KeyDown += self.au_clavier
        except Exception:
            pass
        try:
            onglet.incrustation.au_probleme = self.signaler
        except Exception:
            pass
        self.onglets.append(onglet)
        self.activer(onglet)
        self.enregistrer_session(force=True)
        return True

    def ceder_onglet(self, onglet, cible):
        """Donne un onglet a une autre fenetre. Vrai si le transfert a eu lieu.

        En cas d'echec, rien ne bouge : l'appelant retombe sur l'ancienne
        methode, qui rouvre l'adresse. Mieux vaut une page rechargee qu'un
        onglet perdu entre deux fenetres.
        """
        if onglet not in self.onglets or cible is self:
            return False
        indice = self.onglets.index(onglet)
        self.onglets.remove(onglet)
        if not cible.accueillir_onglet(onglet):
            self.onglets.insert(indice, onglet)
            return False
        self._fantomes.append({"indice": indice, "echelle": 1.0,
                               "debut": time.time()})
        del self._fantomes[:-6]
        self.animer()
        if not self.onglets:
            # c'etait le dernier : la fenetre n'a plus de raison d'etre
            self.BeginInvoke(Action(self.Close))
        elif onglet is self.actif:
            self.activer(self.onglets[min(indice, len(self.onglets) - 1)])
        else:
            self.barre_onglets.Invalidate()
        self.enregistrer_session(force=True)
        return True

    def mettre_en_avant(self):
        """Amene cette fenetre devant, et lui rend le clavier.

        `Activate()` seul ne suffit pas quand une autre fenetre du meme
        programme vient de reclamer le focus : c'est exactement ce que fait
        `fermer()`, qui rend la main a la vue restante. D'ou l'appel explicite
        au premier plan, apres coup.
        """
        try:
            self.Activate()
            user32.SetForegroundWindow(
                ctypes.c_void_p(self.Handle.ToInt64()))
            if self.actif is not None:
                self.actif.vue.Focus()
        except Exception as e:
            journal("premier plan : %s" % e)

    def transferer_onglet(self, onglet, cible):
        """Fait passer un onglet dans une autre fenetre deja ouverte."""
        if cible is self or not onglet.url:
            return False
        if self.ceder_onglet(onglet, cible):
            cible.mettre_en_avant()
            return True
        # Repli : l'adresse est rouverte de l'autre cote. La page repart de
        # zero, mais l'onglet arrive.
        journal("transfert : repli sur une reouverture")
        try:
            cible.nouvel_onglet(onglet.url)
        except Exception as e:
            journal("transfert : %s" % e)
            return False
        if len(self.onglets) <= 1:
            # c'etait le dernier : la fenetre n'a plus de raison d'etre
            self.BeginInvoke(Action(self.Close))
        else:
            self.fermer(onglet)
        # APRES la fermeture, jamais avant : `fermer` rend le focus a la vue
        # restante de CETTE fenetre, et reprenait donc le premier plan a celle
        # qui venait de recevoir l'onglet.
        cible.mettre_en_avant()
        return True

    def detacher_onglet(self, onglet, ecran_x, ecran_y):
        """Sort un onglet dans une fenetre a lui, posee sous le curseur.

        La page est rouverte plutot que deplacee : un controle WebView2 ne se
        reparente pas sans risque, et l'adresse suffit a retrouver ou l'on en
        etait. L'historique de l'onglet, lui, est perdu.
        """
        if len(self.onglets) <= 1 or len(FENETRES) >= MAX_FENETRES:
            return False
        url = onglet.url
        if not url:
            return False
        try:
            zone = self._zone_ecran(ecran_x, ecran_y)
            largeur = min(1440, int(zone.Width * 0.78))
            hauteur = min(900, int(zone.Height * 0.82))
            gauche = borner(int(ecran_x - largeur * 0.3),
                            zone.Left, zone.Right - largeur)
            haut = borner(int(ecran_y - 18), zone.Top, zone.Bottom - hauteur)
            bornes = Rectangle(gauche, haut, largeur, hauteur)
        except Exception:
            bornes = None
        # La fenetre nait vide et recoit l'onglet tel quel : la page n'est
        # pas rechargee, et la video ne repart pas du debut.
        autre = self.nouvelle_fenetre(None, bornes, vide=True)
        if autre is not None and self.ceder_onglet(onglet, autre):
            autre.mettre_en_avant()
            return True
        if autre is not None:
            journal("detachement : repli sur une reouverture")
            autre.nouvel_onglet(url)
        else:
            autre = self.nouvelle_fenetre(url, bornes)
        if autre is None:
            return False
        self.fermer(onglet)
        # Meme raison que pour le transfert : `fermer` vient de rendre le focus
        # a cette fenetre-ci, et la fenetre detachee se retrouvait derriere
        # alors qu'on vient tout juste de la creer d'un geste.
        autre.mettre_en_avant()
        return True

    def clic_onglets(self, envoyeur, args):
        self.fermer_menu()
        if args.Button == MouseButtons.Right:
            for onglet in list(self.onglets):
                if onglet.rect.Contains(args.Location):
                    ecran = self.barre_onglets.PointToScreen(args.Location)
                    self.menu_onglet(onglet, ecran.X, ecran.Y)
                    return
            return
        if self._vient_de_detacher:
            # le clic qui suit un detachement ne doit ni activer ni fermer
            self._vient_de_detacher = False
            return
        for genre, r in self.rect_fenetre.items():
            if r.Contains(args.Location):
                if genre == "reduire":
                    self.WindowState = FormWindowState.Minimized
                elif genre == "fermer":
                    self.Close()
                else:
                    self.basculer_taille()
                return
        if self.rect_plus.Contains(args.Location):
            return self.nouvel_onglet(ACCUEIL)
        for onglet in list(self.onglets):
            if onglet.rect.Contains(args.Location):
                # Le clic du milieu ferme, comme partout ailleurs : c'est le
                # geste qu'on fait sans y penser pour vider une barre chargee.
                if args.Button == MouseButtons.Middle:
                    self.fermer(onglet)
                elif args.X >= onglet.rect.Right - 30:
                    self.fermer(onglet)
                else:
                    self.activer(onglet, glisser=True)
                return

    def zone_libre(self, point):
        """Vrai si le point n'est sur aucun element : la ou l'on saisit la fenetre."""
        if self.rect_plus.Contains(point):
            return False
        for r in self.rect_fenetre.values():
            if r.Contains(point):
                return False
        for onglet in self.onglets:
            if onglet.rect.Contains(point):
                return False
        return True

    def appui_onglets(self, envoyeur, args):
        """Debut d'un deplacement de fenetre, confie a Windows.

        Repondre HTCAPTION depuis le formulaire ne suffit pas : la barre
        d'onglets est un controle a fenetre propre, c'est donc ELLE qui recoit
        le test de position, et le formulaire n'est jamais consulte pour un
        point qui la survole. Le clic dans le haut ne deplacait alors plus rien.

        On previent donc Windows nous-memes, par WM_NCLBUTTONDOWN. Il prend la
        suite : deplacement, accrochage aux bords, secouement, et retour a la
        taille normale quand on tire une fenetre agrandie vers le bas. Ce que
        le code faisait autrefois, avant de l'abandonner parce que la fenetre
        restait a l'etat Normal pendant qu'on posait nous-memes ses
        dimensions ; ce n'est plus le cas.
        """
        if args.Button != MouseButtons.Left:
            return
        if not self.zone_libre(args.Location):
            # appui sur un onglet : peut-etre le debut d'un detachement
            for onglet in self.onglets:
                if (onglet.rect.Contains(args.Location)
                        and args.X < onglet.rect.Right - 30):
                    ecran = self.barre_onglets.PointToScreen(args.Location)
                    self._glisse_onglet = {
                        "onglet": onglet,
                        "depart": (ecran.X, ecran.Y),
                        "actif": False,
                    }
                    self.barre_onglets.Capture = True
                    break
            return
        self.deplacer_par_windows()

    def deplacer_par_windows(self):
        """Passe la main a Windows pour deplacer la fenetre.

        `ReleaseCapture` d'abord : sans cela le controle garde la souris et la
        boucle de deplacement du systeme ne recoit rien.
        """
        try:
            user32.ReleaseCapture()
            user32.SendMessageW(ctypes.c_void_p(self.Handle.ToInt64()),
                                WM_NCLBUTTONDOWN,
                                ctypes.c_void_p(HTCAPTION), None)
        except Exception as e:
            journal("deplacement : %s" % e)

    def _zone_ecran(self, x, y):
        return Screen.FromPoint(Point(int(x), int(y))).WorkingArea

    def relache_onglets(self, envoyeur, args):
        glisse = self._glisse_onglet
        self._glisse_onglet = None
        self._fermer_apercu()
        self._viser(None)
        if glisse and glisse["actif"]:
            try:
                self.barre_onglets.Capture = False
            except Exception:
                pass
            ecran = self.barre_onglets.PointToScreen(args.Location)
            self._vient_de_detacher = self.deposer_onglet(
                glisse["onglet"], ecran.X, ecran.Y, args.Y)
            # Un onglet range reste range au prochain lancement : l'ordre des
            # onglets fait partie de la session, au meme titre que leurs
            # adresses.
            if glisse.get("reordonne") and not self._vient_de_detacher:
                self.barre_onglets.Invalidate()
                self.enregistrer_session(force=True)
            return
        try:
            self.barre_onglets.Capture = False
        except Exception:
            pass

    def double_clic_onglets(self, envoyeur, args):
        if self.zone_libre(args.Location):
            self.basculer_taille()

    def basculer_taille(self):
        """Agrandit ou restaure, par l'etat de fenetre de Windows.

        C'etait fait a la main : `MaximizedBounds` fige des coordonnees
        absolues, et une fenetre agrandie sur un second ecran repartait sur le
        premier. Mais une fenetre dont l'etat reste Normal n'est jamais rendue
        a sa taille par Win+fleche, ni proposee par l'assistant d'ancrage : le
        contournement coutait tout l'ancrage systeme. Le defaut est desormais
        traite la ou il se pose, dans `_bornes_agrandissement`, qui repond a
        Windows avec l'ecran courant.
        """
        if self._maximise:
            self.WindowState = FormWindowState.Normal
        else:
            self._avant_agrandissement = self.Bounds
            self.WindowState = FormWindowState.Maximized
        self.barre_onglets.Invalidate()
        self.replacer()
        self.enregistrer_session()

    def souris_navigation(self, envoyeur, args):
        nom = None
        for cle, _glyphe, x in self.boutons:
            if Rectangle(x, 10, 30, 28).Contains(args.Location):
                nom = cle
                break
        etoile = self._rect_etoile.Contains(args.Location)
        lecteur = self._rect_lecteur.Contains(args.Location)
        if (nom != self._survol_bouton or etoile != self._survol_etoile
                or lecteur != self._survol_lecteur):
            self._survol_bouton = nom
            self._survol_etoile = etoile
            self._survol_lecteur = lecteur
            self.maj_infobulle()
            self.barre_nav.Invalidate()

    def maj_infobulle(self):
        """Texte de l'infobulle, selon ce que survole la souris."""
        if self._survol_lecteur:
            texte = ("Lire avec le lecteur du site"
                     if not (self.actif and self.actif.lecteur_site)
                     else "Lire avec le lecteur de Plume")
        elif self._survol_etoile:
            texte = ("Retirer des favoris"
                     if self.favori_courant() is not None
                     else "Ajouter aux favoris")
        else:
            texte = {"prec": "Reculer", "suiv": "Avancer",
                     "rech": "Recharger (F5)",
                     "accueil": "Page d'accueil"}.get(self._survol_bouton, "")
        if texte != self._infobulle_posee:
            self._infobulle_posee = texte
            try:
                self.infobulle.SetToolTip(self.barre_nav, texte)
            except Exception:
                pass

    def basculer_lecteur(self):
        """Passe d'un lecteur a l'autre, et recharge la page.

        Le choix est ecrit dans le stockage local du site : le script injecte
        le relit avant que la page ne s'execute, ce qui est le seul moment ou
        l'on peut encore decider de museler le lecteur d'origine.
        """
        if not self.actif:
            return
        vers_site = not self.actif.lecteur_site
        self.actif.lecteur_site = vers_site
        script = ("try{localStorage.setItem('__plume_lecteur','%s');}"
                  "catch(e){} location.reload();"
                  % ("site" if vers_site else "plume"))
        try:
            self.actif.incrustation.arreter()
            self.actif.vue.CoreWebView2.ExecuteScriptAsync(script)
        except Exception as e:
            journal("lecteur : %s" % e)
        self.barre_nav.Invalidate()

    def sortie_navigation(self, envoyeur, args):
        if self._survol_bouton or self._survol_etoile or self._survol_lecteur:
            self._survol_bouton = None
            self._survol_etoile = False
            self._survol_lecteur = False
            self.barre_nav.Invalidate()

    def clic_navigation(self, envoyeur, args):
        for cle, _glyphe, x in self.boutons:
            if Rectangle(x, 10, 30, 28).Contains(args.Location):
                {"prec": self.reculer, "suiv": self.avancer,
                 "rech": self.recharger,
                 "accueil": self.aller_accueil}[cle]()
                return
        if self._rect_lecteur.Contains(args.Location):
            self.basculer_lecteur()
            return
        if self._rect_etoile.Contains(args.Location):
            self.basculer_favori()
            return
        if self.rect_champ().Contains(args.Location):
            self.champ.Focus()
            self.champ.SelectAll()

    # ------------------------------------------------------------------
    # Onglets
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Page d'accueil
    # ------------------------------------------------------------------
    def _tuiles_favoris(self):
        """Favoris en vignettes, icones incluses en base64.

        Incluses plutot que liees : une page file:// n'a pas toujours le droit
        de lire d'autres fichiers locaux, et une icone manquante ferait
        mediocre.
        """
        morceaux = []
        for favori in self.favoris["elements"][:12]:
            url = favori.get("url") or ""
            titre = (favori.get("titre") or url)[:38]
            chemin = core.DOSSIER_FAVICONS / (core.hote(url) + ".png")
            icone = ""
            if chemin.exists():
                try:
                    donnees = base64.b64encode(chemin.read_bytes()).decode()
                    icone = ('<img src="data:image/png;base64,%s" alt="">'
                             % donnees)
                except Exception:
                    icone = ""
            if not icone:
                icone = '<span class="etoile">*</span>'
            morceaux.append(
                '<a class="tuile" href="%s">%s<span>%s</span></a>'
                % (_echapper(url), icone, _echapper(titre)))
        if not morceaux:
            return ('<p class="vide">Aucun favori pour l\'instant. '
                    'L\'etoile, a droite de la barre d\'adresse, en ajoute un.'
                    '</p>')
        return '<div class="tuiles">%s</div>' % "".join(morceaux)

    def _cartes_travail(self):
        """Groupes de travail, en cartes cliquables.

        Rien de distant ici non plus : la couleur vient de la palette de Plume,
        et le clic repart vers l'application par le canal de la page.
        """
        self.recharger_travail()
        if not self.travail:
            return ('<p class="vide">Aucun groupe de travail. Clic droit sur '
                    'un onglet pour en creer un : il rouvrira toutes ses pages '
                    'd\'un seul geste.</p>')
        def teinte(indice):
            c = ui.couleur_groupe(indice)
            return "#%02x%02x%02x" % (c.R, c.G, c.B)

        morceaux = []
        for groupe in self.travail:
            choisies = groupe.get("couleurs") or [groupe["couleur"]]
            # Une seule teinte donne un aplat, deux donnent un degrade. Le
            # fond reste tres pale : la carte doit se distinguer, pas crier.
            if len(choisies) > 1:
                fond = ("linear-gradient(115deg,%s33,%s33)"
                        % (teinte(choisies[0]), teinte(choisies[1])))
                bord = teinte(choisies[1])
            else:
                fond = "%s22" % teinte(choisies[0])
                bord = teinte(choisies[0])
            pastilles = "".join(
                '<button class="teinte%(actif)s" style="background:%(c)s" '
                'data-i="%(i)d" onclick="choisirTeinte(event,this)" '
                'title="%(t)s"></button>'
                % {"c": teinte(i), "i": i,
                   "actif": " prise" if i in choisies else "",
                   "t": _echapper(core.t("accueil_teinte"))}
                for i in range(core.NB_COULEURS_GROUPE))
            nombre = len(groupe["onglets"])
            morceaux.append(
                '<div class="travail" role="button" tabindex="0" '
                'style="background:%(fond)s;border-color:%(bord)s55" '
                'onclick="ouvrirTravail(%(js)s)">'
                '<span class="pastille" style="background:%(c)s" '
                'title="%(tp)s" onclick="ouvrirPalette(event,this)"></span>'
                '<span>%(nom)s</span>'
                '<span class="compte">%(n)d page%(s)s</span>'
                '<button class="retirer" title="%(ts)s" '
                'onclick="retirerTravail(event, %(js)s)">\u2715</button>'
                '<div class="palette" onclick="event.stopPropagation()">'
                '%(pastilles)s'
                '<button class="valider" onclick="validerTeintes(event,%(js)s)"'
                ' title="%(tv)s">\u2713</button>'
                '</div>'
                '</div>'
                % {"js": _echapper_js(groupe["nom"]),
                   "c": teinte(choisies[0]), "fond": fond, "bord": bord,
                   "nom": _echapper(groupe["nom"]),
                   "n": nombre, "s": "s" if nombre > 1 else "",
                   "pastilles": pastilles,
                   "tp": _echapper(core.t("accueil_changer_teinte")),
                   "ts": _echapper(core.t("accueil_supprimer_groupe")),
                   "tv": _echapper(core.t("accueil_valider_teintes"))})
        return ('<p class="titre-section">%s</p>' % _echapper(
                    core.t("accueil_groupes")) +
                '<div class="travaux">%s</div>' % "".join(morceaux))

    def definir_couleurs_travail(self, nom, indices):
        """Retient les teintes choisies pour ce groupe.

        Une ou deux, pas plus : au dela, un degrade cesse de se lire comme une
        couleur et devient un motif.
        """
        propres = []
        for i in list(indices)[:2]:
            try:
                propres.append(int(i) % core.NB_COULEURS_GROUPE)
            except (TypeError, ValueError):
                pass
        if not propres:
            return False
        self.recharger_travail()
        for groupe in self.travail:
            if groupe["nom"] == nom:
                groupe["couleurs"] = propres
                groupe["couleur"] = propres[0]
                self.enregistrer_travail()
                for fenetre in list(FENETRES):
                    try:
                        fenetre.ecrire_accueil()
                    except Exception:
                        pass
                return True
        return False

    def appliquer_langue(self):
        """Rejoue l'interface dans la nouvelle langue, sans redemarrer.

        La barre d'onglets et les menus se redessinent a la demande, il suffit
        donc de les invalider. La page d'accueil, elle, est un fichier : il
        faut la reecrire, et recharger les onglets qui l'affichent.
        """
        for fenetre in list(FENETRES):
            try:
                fenetre.ecrire_accueil()
                fenetre.barre_onglets.Invalidate()
                fenetre.barre_nav.Invalidate()
                for onglet in fenetre.onglets:
                    if onglet.url == ACCUEIL:
                        noyau = onglet.vue.CoreWebView2
                        if noyau is not None:
                            noyau.Reload()
            except Exception as e:
                journal("changement de langue : %s" % e)

    def ecrire_accueil(self):
        """Reecrit la page d'accueil avec les favoris et le compteur du moment."""
        try:
            langue = core.langue()
            # Une fois Plume choisie, le bouton n'a plus rien a proposer : il
            # disparait, au lieu de rester grise a repeter un etat.
            deja = core.est_navigateur_par_defaut()
            bouton = "" if deja else (
                '   <button class="defaut" onclick="devenirDefaut()"\n'
                '           title="%s">\n'
                '     <svg viewBox="-1 -1 2 2" width="13" height="13"'
                ' aria-hidden="true"><path fill="#a78bfa"'
                ' d="M0,-1 Q0.16,-0.16 1,0 Q0.16,0.16 0,1'
                ' Q-0.16,0.16 -1,0 Q-0.16,-0.16 0,-1 Z"/></svg>\n'
                '     %s\n   </button>'
                % (_echapper(core.t("accueil_defaut_aide")),
                   _echapper(core.t("accueil_defaut"))))
            page = MODELE_ACCUEIL % {
                "moteur": _echapper(core.CONFIG.get("moteur_recherche", "")),
                "tuiles": self._tuiles_favoris(),
                "travaux": self._cartes_travail(),
                "langue_page": langue,
                "recherche": _echapper(core.t("accueil_recherche")),
                "langue_nom": _echapper(core.t("accueil_langue")),
                "fr_choisie": "true" if langue == "fr" else "false",
                "en_choisie": "true" if langue == "en" else "false",
                "bouton_defaut": bouton,
                "pied_pubs": _echapper(
                    core.t("accueil_pubs", self.pubs_bloquees,
                           *core.marques_pluriel("accueil_pubs",
                                                 self.pubs_bloquees))),
                "pied_vie_privee": _echapper(core.t("accueil_vie_privee")),
            }
            core.FICHIER_ACCUEIL.parent.mkdir(parents=True, exist_ok=True)
            core.FICHIER_ACCUEIL.write_text(page, encoding="utf-8")
        except Exception as e:
            journal("accueil : %s" % e)

    # ------------------------------------------------------------------
    # Session : les onglets survivent a la fermeture
    # ------------------------------------------------------------------
    def restaurer_session(self, depart):
        """Rouvre les onglets confies a cette fenetre, sinon l'accueil.

        La lecture du fichier appartient a `boucle`, qui repartit les fenetres :
        chacune ne connait que la sienne.
        """
        f = self._session_fenetre or {}
        onglets = (f.get("onglets") or [])[:MAX_RESTAURES]
        actif = f.get("actif", 0)

        demande = None
        if depart and depart.rstrip("/") != ACCUEIL.rstrip("/"):
            demande = depart           # un lien a ouvrir, en plus de la reprise

        if not onglets:
            self.nouvel_onglet(demande or depart or ACCUEIL)
            return
        for url in onglets:
            # Le chemin du profil change entre la version de travail et le
            # paquet : une page d'accueil enregistree ailleurs doit rouvrir la
            # page d'accueil d'ici, pas un fichier qui n'existe plus.
            if url.endswith("/accueil.html"):
                url = ACCUEIL
            self.nouvel_onglet(url)
        if 0 <= actif < len(self.onglets):
            self.activer(self.onglets[actif])
        if demande:
            self.nouvel_onglet(demande)
        journal("session : %d onglet(s) repris" % len(onglets))

    def noter_historique(self, url, titre=""):
        """Retient une adresse visitee, la plus recente en tete.

        Les pages locales et la page d'accueil n'y entrent pas : elles ne
        servent a rien comme suggestion.
        """
        if self.privee:
            return
        if not url or not url.startswith(("http://", "https://")):
            return
        cle = url.rstrip("/")
        for i, entree in enumerate(self.historique):
            if entree["url"].rstrip("/") == cle:
                entree["vues"] += 1
                if titre:
                    entree["titre"] = titre
                self.historique.insert(0, self.historique.pop(i))
                break
        else:
            self.historique.insert(0, {"url": url, "titre": titre or url,
                                       "vues": 1})
        del self.historique[core.MAX_HISTORIQUE:]
        maintenant = time.time()
        if maintenant - self._historique_ecrit > 5.0:
            self._historique_ecrit = maintenant
            core.enregistrer_historique(self.historique)

    def calculer_suggestions(self, texte):
        """Favoris d'abord, puis historique, puis la recherche web.

        La comparaison se fait mot par mot et non sur la chaine entiere : on se
        souvient d'une page par deux bouts de son titre, rarement dans l'ordre
        exact ou ils y figurent. « wiki navigateur » doit donc trouver l'article
        « Web browser » de Wikipedia.
        """
        texte = (texte or "").strip().lower()
        if len(texte) < 1:
            return []
        mots = [m for m in texte.split() if m]

        def correspond(*champs):
            paille = " ".join((c or "").lower() for c in champs)
            return all(m in paille for m in mots)

        trouves, deja = [], set()
        for favori in self.favoris["elements"]:
            url = favori.get("url") or ""
            titre = favori.get("titre") or url
            if correspond(url, titre):
                trouves.append(("favori", url, titre))
                deja.add(url.rstrip("/"))
            if len(trouves) >= 3:
                break
        for entree in self.historique:
            if len(trouves) >= MAX_SUGGESTIONS - 1:
                break
            cle = entree["url"].rstrip("/")
            if cle in deja:
                continue
            if correspond(entree["url"], entree["titre"]):
                trouves.append(("historique", entree["url"],
                                entree["titre"] or entree["url"]))
                deja.add(cle)
        # Derniere ligne, toujours presente sauf si la saisie est deja une
        # adresse : elle rend previsible ce que fera Entree, et evite le
        # « pourquoi ca a cherche au lieu d'ouvrir ».
        if not core.RE_URL.match(texte):
            trouves = trouves[:MAX_SUGGESTIONS - 1]
            trouves.append(("recherche", core.url_recherche_web(texte),
                            "Rechercher « %s »" % texte))
        return trouves[:MAX_SUGGESTIONS]

    def enregistrer_session(self, force=False):
        """Ecrit la session, au plus une fois toutes les deux secondes.

        Sans ce frein, chaque changement d'adresse d'une page qui se recharge
        toute seule ferait une ecriture disque.
        """
        if self._restauration:
            return
        maintenant = time.time()
        if not force and maintenant - self._session_ecrite < 2.0:
            return
        self._session_ecrite = maintenant
        fenetres = []
        for fenetre in FENETRES:
            # Une fenetre privee ne laisse pas ses onglets dans la session :
            # ce serait la retrouver au prochain lancement, donc l'inverse de
            # ce qu'elle promet.
            if fenetre.privee:
                continue
            try:
                gardes = [o for o in fenetre.onglets if o.url]
                urls = [o.url for o in gardes]
                if not urls:
                    continue
                indice = 0
                if fenetre.actif in gardes:
                    indice = gardes.index(fenetre.actif)
                # Une fenetre agrandie enregistre la taille a laquelle elle
                # reviendrait, pas celle de l'ecran : sinon « restaurer »
                # n'aurait nulle part ou revenir au prochain lancement.
                if fenetre._maximise and fenetre._avant_agrandissement:
                    r = fenetre._avant_agrandissement
                else:
                    r = fenetre.Bounds
                fenetres.append({"onglets": urls, "actif": indice,
                                 "bornes": [r.X, r.Y, r.Width, r.Height],
                                 "agrandie": bool(fenetre._maximise)})
            except Exception:
                continue
        core.enregistrer_session({"fenetres": fenetres})

    def nouvel_onglet(self, url=None):
        url = url or ACCUEIL
        journal("onglet ouvert : %s" % str(url)[:90])
        if url == ACCUEIL:
            self.ecrire_accueil()
        onglet = Onglet(self, url)
        # Pas d'animation pendant la reprise de session : vingt onglets qui
        # s'ecartent l'un apres l'autre au lancement font une entree en scene,
        # pas une interface.
        if not self._restauration:
            onglet.echelle = 0.0
            onglet._ouverture = time.time()
            self.animer()
        self.onglets.append(onglet)
        # Un onglet neuf se pose toujours a droite : sa page arrive donc du
        # meme cote que si on l'avait choisi dans la barre. Pas pendant une
        # reprise de session, ou vingt pages defileraient au lancement.
        self.activer(onglet, glisser=not self._restauration)
        if url == ACCUEIL:
            # Comme dans les autres navigateurs : un onglet neuf attend une
            # adresse. La page locale ne prend pas le focus, mais WebView2 le
            # reclame en fin de chargement, d'ou le rappel dans `traiter`.
            onglet.rendre_focus = True
            self.champ.Focus()
        # Sans forcer, le frein de deux secondes pouvait avaler l'ecriture :
        # ouvrir un onglet est assez rare pour meriter un enregistrement sur.
        self.enregistrer_session(force=True)
        return onglet

    # ------------------------------------------------------------------
    # Apparition et effacement de la fenetre
    # ------------------------------------------------------------------
    def fondre(self, cible, duree, apres=None):
        """Amene l'opacite a `cible`, puis appelle `apres`.

        Une fenetre qui surgit et disparait d'un coup fait sursauter ; le meme
        geste en deux dixiemes de seconde se lit comme une intention. La duree
        reste courte : une animation qu'on attend est une animation de trop.
        """
        depart = float(self.Opacity)
        debut = time.time()
        self._arreter_fondu()
        minuteur = Timer()
        minuteur.Interval = PERIODE_ANIM

        def battre(envoyeur=None, args=None):
            part = (time.time() - debut) / max(0.01, duree)
            if part >= 1.0:
                self._arreter_fondu()
                try:
                    self.Opacity = cible
                except Exception:
                    pass
                if apres is not None:
                    apres()
                return
            # ralentissement a l'arrivee, comme pour les onglets
            adouci = 1.0 - (1.0 - part) ** 3
            try:
                self.Opacity = depart + (cible - depart) * adouci
            except Exception:
                self._arreter_fondu()

        minuteur.Tick += battre
        self._anim_fenetre = minuteur
        minuteur.Start()

    def _arreter_fondu(self):
        if self._anim_fenetre is None:
            return
        try:
            self._anim_fenetre.Stop()
            self._anim_fenetre.Dispose()
        except Exception:
            pass
        self._anim_fenetre = None

    # ------------------------------------------------------------------
    # Groupes de travail
    # ------------------------------------------------------------------
    def recharger_travail(self):
        """Relit le fichier : plusieurs fenetres se partagent les groupes."""
        self.travail = core.charger_groupes_travail()
        return self.travail

    def enregistrer_travail(self):
        core.enregistrer_groupes_travail(self.travail)
        # La page d'accueil montre les groupes : la reecrire tout de suite,
        # sinon un onglet neuf afficherait l'etat d'avant.
        self.ecrire_accueil()
        for fenetre in FENETRES:
            if fenetre is not self:
                fenetre.travail = core.charger_groupes_travail()
            # Une page d'accueil deja ouverte garde l'ancienne liste : la
            # recharger, sinon le groupe cree n'apparait qu'au prochain onglet.
            for onglet in fenetre.onglets:
                if onglet.url == ACCUEIL:
                    try:
                        onglet.vue.CoreWebView2.Reload()
                    except Exception:
                        pass

    def dans_groupe(self, groupe, url):
        cle = (url or "").rstrip("/")
        return any((o["url"] or "").rstrip("/") == cle
                   for o in groupe["onglets"])

    def ajouter_au_travail(self, onglet, nom):
        """Range une page dans un groupe de travail, ou l'en retire."""
        self.recharger_travail()
        groupe = core.groupe_travail(self.travail, nom)
        if groupe is None or not onglet.url or onglet.url == ACCUEIL:
            return
        if self.dans_groupe(groupe, onglet.url):
            cle = onglet.url.rstrip("/")
            groupe["onglets"] = [o for o in groupe["onglets"]
                                 if (o["url"] or "").rstrip("/") != cle]
            self.signaler(core.t("retire_de", nom), erreur=False)
        elif len(groupe["onglets"]) >= core.MAX_ONGLETS_TRAVAIL:
            self.signaler("« %s » contient deja %d onglets : c'est le maximum, "
                          "les rouvrir tous doit rester tenable."
                          % (nom, core.MAX_ONGLETS_TRAVAIL))
            return
        else:
            groupe["onglets"].append({"url": onglet.url,
                                      "titre": onglet.titre or onglet.url})
            self.signaler(core.t("ajoute_a", nom), erreur=False)
        self.enregistrer_travail()

    def creer_groupe_travail(self, onglet=None):
        """Demande un nom, cree le groupe, et y range l'onglet vise."""
        nom = self.demander_texte("Nouveau groupe de travail",
                                  "Son nom, par exemple : dev")
        nom = (nom or "").strip()[:28]
        if not nom:
            return
        self.recharger_travail()
        if core.groupe_travail(self.travail, nom) is not None:
            self.signaler(core.t("groupe_existe", nom))
            return
        self.travail.append({"nom": nom, "couleur": len(self.travail),
                             "couleurs": [len(self.travail)
                                          % core.NB_COULEURS_GROUPE],
                             "onglets": []})
        self.enregistrer_travail()
        if onglet is not None:
            self.ajouter_au_travail(onglet, nom)

    def supprimer_groupe_travail(self, nom):
        self.recharger_travail()
        self.travail = [gr for gr in self.travail if gr["nom"] != nom]
        self.enregistrer_travail()
        self.signaler("Groupe « %s » supprime. Les onglets ouverts restent "
                      "ouverts." % nom, erreur=False)

    def ouvrir_groupe_travail(self, nom):
        """Rouvre toutes les pages d'un groupe, sans doubler celles deja la."""
        self.recharger_travail()
        groupe = core.groupe_travail(self.travail, nom)
        if groupe is None or not groupe["onglets"]:
            self.signaler("Le groupe « %s » ne contient encore aucune page : "
                          "clic droit sur un onglet pour l'y ranger." % nom)
            return 0
        deja = set((o.url or "").rstrip("/") for o in self.onglets)
        ouverts = 0
        premier = None
        for entree in groupe["onglets"]:
            if entree["url"].rstrip("/") in deja:
                continue
            onglet = self.nouvel_onglet(entree["url"])
            premier = premier or onglet
            ouverts += 1
        if premier is not None:
            self.activer(premier)
        self.signaler("« %s » : %d onglet%s ouvert%s."
                      % (nom, ouverts, "s" if ouverts > 1 else "",
                         "s" if ouverts > 1 else ""), erreur=False)
        return ouverts

    def menu_onglet(self, onglet, ecran_x, ecran_y):
        """Menu du clic droit sur un onglet."""
        self.recharger_travail()
        items = []
        rangeable = bool(onglet.url) and onglet.url != ACCUEIL
        for groupe in self.travail:
            nom = groupe["nom"]
            dedans = rangeable and self.dans_groupe(groupe, onglet.url)
            items.append({
                "texte": core.t("menu_retirer_de" if dedans
                                else "menu_ajouter_a", nom),
                "coche": dedans,
                "actif": rangeable,
                "action": (lambda o=onglet, n=nom:
                           self.ajouter_au_travail(o, n)) if rangeable
                else None,
            })
        items.append({"texte": core.t("menu_nouveau_groupe"),
                      "action": lambda o=onglet: self.creer_groupe_travail(
                          o if rangeable else None)})
        items.append({"separateur": True, "texte": ""})
        items.append({"texte": core.t("menu_fermer"),
                      "action": lambda o=onglet: self.fermer(o)})
        items.append({"texte": core.t("menu_fermer_autres"),
                      "action": lambda o=onglet: self.fermer_les_autres(o)})
        self.ouvrir_menu(items, ecran_x, ecran_y)

    def fermer_les_autres(self, garde):
        for onglet in list(self.onglets):
            if onglet is not garde:
                self.fermer(onglet)

    def demander_texte(self, titre, invite):
        """Petite fenetre de saisie, dessinee comme le reste de Plume.

        WinForms n'offre rien de tel, et une boite de dialogue systeme jurerait
        au milieu d'une interface entierement dessinee.
        """
        boite = Form()
        boite.FormBorderStyle = getattr(FormBorderStyle, "None")
        boite.StartPosition = FormStartPosition.CenterParent
        boite.ShowInTaskbar = False
        boite.Size = Size(380, 132)
        boite.BackColor = ui.BORD_FENETRE
        boite.Padding = Padding(1)
        fond = Panel()
        fond.Dock = DockStyle.Fill
        fond.BackColor = ui.FOND_NAV
        boite.Controls.Add(fond)

        champ = TextBox()
        champ.BorderStyle = getattr(BorderStyle, "None")
        champ.BackColor = ui.CHAMP_FOND
        champ.ForeColor = ui.TEXTE
        champ.Font = self.police
        champ.Location = Point(20, 62)
        champ.Size = Size(338, 22)
        fond.Controls.Add(champ)

        def peindre(envoyeur, args):
            g = args.Graphics
            ui.preparer(g)
            ui.texte_tronque(g, titre, self.police_plus, ui.TEXTE, 20, 16,
                             330, 22)
            ui.texte_tronque(g, invite, self.police_petite, ui.TEXTE2, 20, 40,
                             330, 16)
            ui.remplir_arrondi(g, ui.CHAMP_FOND, 14, 56, 350, 34, 0, "pilule")
            ui.contour_arrondi(g, ui.ACCENT, 14, 56, 350, 34, 17, 1)

        fond.Paint += peindre
        ui.double_tampon(fond)

        reponse = [None]

        def au_clavier(envoyeur, args):
            if args.KeyCode == Keys.Enter:
                args.SuppressKeyPress = True
                reponse[0] = champ.Text
                boite.Close()
            elif args.KeyCode == Keys.Escape:
                args.SuppressKeyPress = True
                boite.Close()

        champ.KeyDown += au_clavier
        boite.Shown += lambda e, a: champ.Focus()
        # Le menu est encore a l'ecran : le fermer avant, sinon il flotterait
        # au-dessus de la saisie.
        self.fermer_menu()
        try:
            boite.ShowDialog(self)
        finally:
            boite.Dispose()
        return reponse[0]

    # ------------------------------------------------------------------
    # Menu contextuel, dessine comme le reste
    # ------------------------------------------------------------------
    def ouvrir_menu(self, items, ecran_x, ecran_y):
        """Montre un menu a l'ecran. Chaque item : {texte, action, coche}.

        Une fenetre a part, comme la liste de suggestions : un controle
        WinForms ne peut pas se dessiner au-dessus de WebView2.
        """
        self._items_menu = items
        self._survol_menu = -1
        if not items:
            return
        largeur = 0
        # pythonnet n'expose pas IDisposable en gestionnaire de contexte :
        # liberer le Graphics a la main, sinon on fuit une ressource GDI a
        # chaque ouverture de menu.
        mesure = None
        try:
            mesure = Graphics.FromHwnd(self.Handle)
            for item in items:
                if item.get("separateur"):
                    continue
                largeur = max(largeur,
                              int(mesure.MeasureString(item["texte"],
                                                       self.police).Width))
        except Exception:
            largeur = 200
        finally:
            if mesure is not None:
                try:
                    mesure.Dispose()
                except Exception:
                    pass
        largeur = min(320, max(190, largeur + 54))
        hauteur = 8 + sum(H_SEPARATEUR if i.get("separateur") else H_MENU
                          for i in items)
        if self._menu is None:
            self._menu = self._creer_menu()
            if self._menu is None:
                return
        # Le menu doit rester sur l'ecran, meme demande tout en bas a droite.
        zone = Screen.FromHandle(self.Handle).WorkingArea
        x = min(int(ecran_x), zone.Right - largeur - 4)
        y = min(int(ecran_y), zone.Bottom - hauteur - 4)
        self._menu.Size = Size(largeur, hauteur)
        user32.SetWindowPos(
            ctypes.c_void_p(self._menu.Handle.ToInt64()),
            ctypes.c_void_p(HWND_TOPMOST), x, y, largeur, hauteur,
            SWP_NOACTIVATE | SWP_SHOWWINDOW)
        self._menu.Invalidate()

    def _creer_menu(self):
        try:
            menu = Form()
            menu.FormBorderStyle = getattr(FormBorderStyle, "None")
            menu.StartPosition = FormStartPosition.Manual
            menu.ShowInTaskbar = False
            menu.BackColor = ui.FOND_NAV
            menu.Paint += self._peindre_menu
            menu.MouseMove += self._souris_menu
            menu.MouseClick += self._clic_menu
            menu.MouseLeave += self._sortie_menu
            ui.double_tampon(menu)
            poignee = menu.Handle.ToInt64()
            style = _lire_style(ctypes.c_void_p(poignee), GWL_EXSTYLE)
            _ecrire_style(ctypes.c_void_p(poignee), GWL_EXSTYLE,
                          int(style) | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
            return menu
        except Exception as e:
            journal("menu : %s" % e)
            return None

    def fermer_menu(self):
        self._items_menu = []
        self._survol_menu = -1
        if self._menu is None:
            return
        try:
            user32.ShowWindow(ctypes.c_void_p(self._menu.Handle.ToInt64()), 0)
        except Exception:
            pass

    def _lignes_menu(self):
        """Position verticale de chaque item : les separateurs sont plus bas."""
        y = 4
        for i, item in enumerate(self._items_menu):
            h = H_SEPARATEUR if item.get("separateur") else H_MENU
            yield i, item, y, h
            y += h

    def _peindre_menu(self, envoyeur, args):
        g = args.Graphics
        ui.preparer(g)
        largeur = envoyeur.Width
        ui.remplir_arrondi(g, ui.FOND_NAV, 0, 0, largeur, envoyeur.Height, 10)
        ui.contour_arrondi(g, ui.CHAMP_BORD, 0, 0, largeur - 1,
                           envoyeur.Height - 1, 10, 1)
        for i, item, y, h in self._lignes_menu():
            if item.get("separateur"):
                ui.remplir_arrondi(g, ui.CHAMP_BORD, 12, y + h // 2,
                                   largeur - 24, 1, 0)
                continue
            if i == self._survol_menu:
                ui.remplir_arrondi(g, ui.ONGLET_SURVOL, 4, y, largeur - 8,
                                   h, 7)
            couleur = ui.TEXTE if item.get("actif", True) else ui.TEXTE3
            if item.get("coche"):
                ui.etoile(g, ui.ACCENT_PALE, 20, y + h / 2.0, 6, True)
            ui.texte_tronque(g, item["texte"], self.police, couleur,
                             34, y + (h - 16) // 2, largeur - 44, 16)

    def _ligne_menu_sous(self, py):
        for i, item, y, h in self._lignes_menu():
            if y <= py < y + h and not item.get("separateur"):
                return i
        return -1

    def _souris_menu(self, envoyeur, args):
        i = self._ligne_menu_sous(args.Y)
        if i != self._survol_menu:
            self._survol_menu = i
            envoyeur.Invalidate()

    def _sortie_menu(self, envoyeur, args):
        if self._survol_menu != -1:
            self._survol_menu = -1
            envoyeur.Invalidate()

    def _clic_menu(self, envoyeur, args):
        i = self._ligne_menu_sous(args.Y)
        if i < 0 or i >= len(self._items_menu):
            return
        action = self._items_menu[i].get("action")
        self.fermer_menu()
        if action:
            try:
                action()
            except Exception as e:
                journal("menu : action refusee : %s" % e)

    def animer(self):
        """Reveille le minuteur d'animation, s'il dort."""
        if self.minuteur_anim is not None:
            return
        self.minuteur_anim = Timer()
        self.minuteur_anim.Interval = PERIODE_ANIM
        self.minuteur_anim.Tick += self._battement_anim
        self.minuteur_anim.Start()

    def _arreter_anim(self):
        if self.minuteur_anim is None:
            return
        self.minuteur_anim.Stop()
        self.minuteur_anim.Dispose()
        self.minuteur_anim = None

    def _battement_anim(self, envoyeur=None, args=None):
        # Une exception dans un Tick remonte dans WinForms et tue le processus.
        # Une animation ratee doit couter l'animation, pas la fenetre.
        try:
            self._battement()
        except Exception:
            plantage("animation")
            for solde in (self._finir_glisse_page, self._finir_chute):
                try:
                    solde()
                except Exception:
                    pass
            self._arreter_anim()

    def _battement(self):
        """Fait avancer les ouvertures et les fermetures, puis s'arrete.

        Le minuteur ne tourne que pendant l'animation : une boucle permanente
        a soixante images par seconde pour une barre qui ne bouge pas serait
        exactement le genre de depense que Plume refuse.
        """
        maintenant = time.time()
        encore = False
        for onglet in self.onglets:
            if onglet._ouverture is None:
                continue
            part = (maintenant - onglet._ouverture) / DUREE_OUVERTURE
            if part >= 1.0:
                onglet.echelle = 1.0
                onglet._ouverture = None
            else:
                # ralentissement a l'arrivee
                onglet.echelle = 1.0 - (1.0 - part) ** 3
                encore = True
        for fantome in list(self._fantomes):
            part = (maintenant - fantome["debut"]) / DUREE_FERMETURE
            if part >= 1.0:
                self._fantomes.remove(fantome)
            else:
                # acceleration au depart
                fantome["echelle"] = 1.0 - part * part
                encore = True
        if self._avancer_glisse_page(maintenant):
            encore = True
        if self._avancer_chute(maintenant):
            encore = True
        self.barre_onglets.Invalidate()
        if not encore:
            self._arreter_anim()

    def demarrer_veille(self):
        """Lance la surveillance des onglets d'arriere-plan."""
        if self.minuteur_veille is not None:
            return
        if not core.CONFIG.get("veille_onglets"):
            return
        self.minuteur_veille = Timer()
        self.minuteur_veille.Interval = PERIODE_VEILLE
        self.minuteur_veille.Tick += self.verifier_veille
        self.minuteur_veille.Start()

    def verifier_veille(self, envoyeur=None, args=None):
        """Endort ce qui dort deja de fait.

        Deux onglets sont epargnes : celui qu'on regarde, et celui qui joue une
        video. Le delai laisse un aller-retour rapide entre deux onglets sans
        aucun cout.
        """
        delai = core.CONFIG.get("veille_onglets") or 0
        if delai <= 0:
            return
        maintenant = time.time()
        for onglet in list(self.onglets):
            if onglet is self.actif or onglet.endormi:
                continue
            age = maintenant - onglet.derniere_activite
            if age < delai:
                continue
            try:
                if onglet.incrustation.en_cours():
                    continue
            except Exception:
                pass
            journal("veille : tentative sur %s (inactif depuis %.0f s)"
                    % (str(onglet.url)[:60], age))
            onglet.endormir()

    def activer(self, onglet, glisser=False):
        # `glisser` n'est vrai que pour un changement d'onglet DEMANDE : clic
        # ou raccourci. Une restauration de session, une fermeture ou un
        # deplacement d'onglet ne doivent rien animer, sans quoi le lancement
        # defilerait vingt fois de suite.
        self._finir_glisse_page()
        self._finir_chute()
        sortant = self.actif if (glisser and onglet is not self.actif) else None
        sens = 0
        if sortant is not None and sortant in self.onglets \
                and onglet in self.onglets:
            sens = 1 if (self.onglets.index(onglet)
                         > self.onglets.index(sortant)) else -1
        for o in self.onglets:
            # `sens` est un entier : sans `bool`, une propriete .NET
            # booleenne recevrait 0 ou 1 et refuserait la conversion.
            o.vue.Visible = bool(o is onglet
                                 or (sens != 0 and o is sortant))
            if o is not onglet:
                o.incrustation.cacher()     # de cote, mais toujours vivante
                # Le compteur repart d'ici : c'est maintenant que cet onglet
                # commence a ne plus etre regarde.
                o.derniere_activite = time.time()
        onglet.reveiller()
        # Une mesure prise sous une autre taille de fenetre ferait apparaitre
        # le lecteur au mauvais format le temps que la page se reforme. Mieux
        # vaut ne rien montrer pendant les 120 ms qu'elle met a se redire.
        if onglet.zone_page is not None:
            try:
                taille = self.contenu.ClientSize
                if onglet.taille_mesure != (taille.Width, taille.Height):
                    onglet.zone_page = None
                    onglet.incrustation.cacher()
            except Exception:
                pass
        self.actif = onglet
        # Le fil appartient a l'onglet : changer d'onglet doit montrer le sien,
        # pas laisser celui d'avant.
        self.rafraichir_navigation()
        onglet.incrustation.definir_parent(self.Handle.ToInt64())
        if sens:
            self.glisser_pages(sortant, onglet, sens)
        # Une page video restauree en arriere-plan n'a pas pu annoncer son
        # lecteur : on lui demande de recommencer maintenant qu'on la regarde.
        self.relancer_lecteur(onglet)
        self.afficher_url(onglet)
        try:
            onglet.vue.BringToFront()
        except Exception:
            pass
        self.barre_onglets.Invalidate()

    def onglet_voisin(self, sens):
        """Onglet suivant ou precedent."""
        if len(self.onglets) < 2:
            return
        i = self.onglets.index(self.actif) if self.actif in self.onglets else 0
        self.activer(self.onglets[(i + sens) % len(self.onglets)],
                     glisser=True)

    def glisser_pages(self, sortant, entrant, sens):
        """Fait entrer la nouvelle page par le cote d'ou elle vient.

        On deplace les deux vues WebView2 elles-memes plutot que des images :
        leur taille ne change pas, seulement leur position, ce qui n'oblige la
        page a aucune remise en page. Le panneau qui les contient les rogne aux
        bords, donc rien ne deborde.

        `sens` vaut 1 pour un onglet situe a droite, -1 pour la gauche : la
        page sortante part du cote oppose a celui d'ou arrive l'entrante.

        L'animation est confiee au minuteur, jamais a une boucle avec
        `Application.DoEvents` : celle-ci laissait re-entrer `activer` au
        milieu du glissement, qui finissait alors sur le mauvais onglet.
        """
        if not core.CONFIG.get("glissement_onglets", True):
            return
        if sortant is None or sortant is entrant:
            return
        largeur = self.contenu.ClientSize.Width
        hauteur = self.contenu.ClientSize.Height
        if largeur < 240 or hauteur < 120:
            return
        sans_ancrage = getattr(DockStyle, "None")
        try:
            # Le lecteur video est une fenetre a part : il ne peut pas glisser
            # avec la page. On l'efface, il revient de lui-meme au prochain
            # message de zone, dans les 120 ms.
            for onglet in (sortant, entrant):
                try:
                    onglet.incrustation.cacher()
                except Exception:
                    pass
            for vue in (sortant.vue, entrant.vue):
                vue.Dock = sans_ancrage
                vue.SetBounds(0, 0, largeur, hauteur)
            sortant.vue.Left = 0
            entrant.vue.Left = sens * largeur
            entrant.vue.BringToFront()
        except Exception as e:
            journal("glissement : %s" % e)
            return
        self._glisse_page = {"sortant": sortant, "entrant": entrant,
                             "sens": sens, "largeur": largeur,
                             "debut": time.time()}
        self.animer()

    def _avancer_glisse_page(self, maintenant):
        """Une image du glissement. Renvoie vrai tant qu'il reste a faire."""
        etat = self._glisse_page
        if etat is None:
            return False
        part = (maintenant - etat["debut"]) / DUREE_GLISSE_PAGE
        if part >= 1.0:
            self._finir_glisse_page()
            return False
        # Amorti aux deux bouts : la page prend son elan puis se pose,
        # au lieu de bondir des la premiere image.
        if part < 0.5:
            avance = 4.0 * part ** 3
        else:
            avance = 1.0 - (-2.0 * part + 2.0) ** 3 / 2.0
        # Arrondi, et non troncature : `int()` rogne vers zero, donc dans un
        # sens et pas dans l'autre. Le pas devenait irregulier d'une image a
        # l'autre, et l'oeil lit cette irregularite comme un saut.
        decalage = int(round(etat["sens"] * etat["largeur"] * avance))
        largeur = etat["sens"] * etat["largeur"]
        if not self._deplacer_ensemble(
                ((etat["sortant"].vue, -decalage),
                 (etat["entrant"].vue, largeur - decalage))):
            self._finir_glisse_page()
            return False
        return True

    def _deplacer_ensemble(self, couples):
        """Pose plusieurs vues a leur abscisse en une seule repeinture.

        Chaque vue est une fenetre a part entiere. Deux `SetWindowPos` separes,
        c'est deux repeintures : la premiere page bouge, la seconde suit une
        image plus tard, et le decalage se voit comme un saut de quelques
        pixels au bord commun. `DeferWindowPos` les groupe en une transaction
        que Windows applique d'un bloc.

        Renvoie faux si une vue n'est plus posable : au premier echec, mieux
        vaut solder le glissement que d'animer une fenetre disparue.
        """
        try:
            poignees = [(v.Handle.ToInt64(), int(x), v.Top, v.Width, v.Height)
                        for v, x in couples]
        except Exception:
            return False
        lot = user32.BeginDeferWindowPos(len(poignees))
        if not lot:
            # Repli : le resultat est le meme, au scintillement pres.
            try:
                for vue, x in couples:
                    vue.Left = int(x)
            except Exception:
                return False
            return True
        drapeaux = SWP_NOACTIVATE | SWP_NOZORDER
        try:
            for poignee, x, y, l, h in poignees:
                lot = user32.DeferWindowPos(ctypes.c_void_p(lot),
                                            ctypes.c_void_p(poignee), None,
                                            x, y, l, h, drapeaux)
                if not lot:
                    return False
            return bool(user32.EndDeferWindowPos(ctypes.c_void_p(lot)))
        except Exception:
            return False

    def _preparer_chute(self, onglet):
        """Detache la vue d'un onglet ferme pour qu'elle puisse tomber.

        L'onglet est deja sorti de `self.onglets` : plus rien ne le replacera,
        et `activer` ne touchera pas a sa vue. Renvoie l'etat a lancer une fois
        la nouvelle page en place, ou None si la chute n'est pas possible.
        """
        if not core.CONFIG.get("glissement_onglets", True):
            return None
        try:
            hauteur = self.contenu.ClientSize.Height
            largeur = self.contenu.ClientSize.Width
            if largeur < 240 or hauteur < 120:
                return None
            # Le lecteur est une fenetre de premier niveau : il ne tombe pas
            # avec la page, il flotterait au-dessus d'elle. Il part tout de
            # suite, l'onglet est de toute facon condamne.
            onglet.incrustation.cacher()
            sans_ancrage = getattr(DockStyle, "None")
            onglet.vue.Dock = sans_ancrage
            onglet.vue.SetBounds(0, 0, largeur, hauteur)
        except Exception as e:
            journal("chute : %s" % e)
            return None
        return {"onglet": onglet, "hauteur": hauteur, "debut": None}

    def _lancer_chute(self, etat):
        """Met la page condamnee au premier plan et la laisse tomber.

        Appele APRES l'activation de la page suivante : celle-ci se met elle
        aussi au premier plan en s'activant, et passerait sinon devant la page
        qui tombe.
        """
        try:
            etat["onglet"].vue.BringToFront()
        except Exception:
            return self._detruire(etat["onglet"])
        etat["debut"] = time.time()
        self._chute = etat
        self.animer()

    def _avancer_chute(self, maintenant):
        """Une image de la chute. Renvoie vrai tant qu'il reste a faire."""
        etat = self._chute
        if etat is None:
            return False
        part = (maintenant - etat["debut"]) / DUREE_CHUTE_PAGE
        if part >= 1.0:
            self._finir_chute()
            return False
        # Une chute accelere : le carre du temps, comme une vraie. Une courbe
        # lineaire donnerait un ascenseur, pas un objet qui tombe.
        try:
            etat["onglet"].vue.Top = int(round(etat["hauteur"] * part * part))
        except Exception:
            self._finir_chute()
            return False
        return True

    def _finir_chute(self):
        """Detruit pour de bon la page tombee. Sans effet s'il n'y a rien.

        Appele aussi au DEBUT de chaque activation : fermer deux onglets coup
        sur coup ne doit pas laisser une page en suspens.
        """
        etat, self._chute = self._chute, None
        if etat is not None:
            self._detruire(etat["onglet"])

    def _detruire(self, onglet):
        try:
            onglet.detruire()
        except Exception as e:
            journal("destruction de l'onglet : %s" % e)

    def _finir_glisse_page(self):
        """Remet les deux vues en place. Sans effet s'il n'y a rien en cours.

        Appele aussi au DEBUT de chaque activation : un changement d'onglet
        demande pendant un glissement doit d'abord solder le precedent, sinon
        c'est l'ancien qui deciderait quelle vue cacher.
        """
        etat, self._glisse_page = self._glisse_page, None
        if etat is None:
            return
        try:
            etat["sortant"].vue.Visible = (etat["sortant"] is self.actif)
            for vue in (etat["sortant"].vue, etat["entrant"].vue):
                vue.Left = 0
                vue.Dock = DockStyle.Fill
            if self.actif is not None:
                self.actif.vue.BringToFront()
        except Exception as e:
            journal("glissement : %s" % e)

    def afficher_url(self, onglet):
        """Montre l'adresse, sauf celle de la page d'accueil.

        Un onglet neuf doit presenter une barre vide et prete a la saisie, pas
        le chemin d'un fichier local sans interet pour l'utilisateur.
        """
        # Marquer que le changement vient de nous : sans cela, l'adresse
        # posee par une navigation relancait la liste de suggestions, qui se
        # rouvrait aussitot apres qu'on y ait choisi quelque chose.
        self._maj_programmee = True
        try:
            self.champ.Text = ("" if onglet.url == ACCUEIL
                               else (onglet.url or ""))
        finally:
            self._maj_programmee = False

    def fermer(self, onglet):
        if onglet not in self.onglets:
            return
        if onglet.url and onglet.url != ACCUEIL:
            self._fermes.append(onglet.url)
            del self._fermes[:-20]
        indice = self.onglets.index(onglet)
        etait_actif = (onglet is self.actif)
        # L'onglet disparait de la logique tout de suite, et ne reste qu'a
        # l'ecran, le temps de se retirer : rien d'autre n'a a connaitre cet
        # etat intermediaire.
        self._fantomes.append({"indice": indice, "echelle": 1.0,
                               "debut": time.time()})
        del self._fantomes[:-6]
        self.onglets.remove(onglet)
        # La page d'un onglet ferme tombe hors du cadre plutot que de
        # disparaitre d'un coup. Elle n'est donc detruite qu'a l'arrivee, et
        # seulement si c'est bien la page qu'on regardait : une page fermee en
        # arriere-plan n'a rien a montrer.
        chute = (self._preparer_chute(onglet)
                 if (etait_actif and self.onglets) else None)
        if chute is None:
            onglet.detruire()
        self.animer()
        if not self.onglets:
            # Fermer le dernier onglet ferme la fenetre. Rouvrir une page
            # d'accueil a la place laissait une fenetre vide dont on ne
            # comprenait pas pourquoi elle etait encore la.
            self.Close()
            return
        elif etait_actif:
            self.activer(self.onglets[min(indice, len(self.onglets) - 1)])
            # Le controle qui avait le focus vient d'etre detruit : sans le
            # rendre a la vue restante, plus aucun raccourci ne repondait tant
            # qu'on n'avait pas reclique dans la fenetre.
            try:
                self.actif.vue.Focus()
            except Exception:
                pass
            if chute is not None:
                self._lancer_chute(chute)
        else:
            self.barre_onglets.Invalidate()
        self.enregistrer_session(force=True)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def aller(self, texte):
        texte = (texte or "").strip()
        if not texte or not self.actif:
            return
        url = (core.normaliser_url(texte) if core.est_url(texte)
               else core.url_recherche_web(texte))
        try:
            # Navigate plutot que Source : affecter Source la meme valeur ne
            # declenche rien, si bien que choisir la suggestion de la page
            # deja ouverte laissait la barre d'adresse sur la saisie a moitie
            # tapee, sans que rien ne se passe.
            noyau = self.actif.vue.CoreWebView2
            if noyau is not None:
                noyau.Navigate(url)
            else:
                self.actif.vue.Source = Uri(url)
        except Exception as e:
            journal("navigation : %s" % e)
            try:
                self.actif.vue.Source = Uri(url)
            except Exception:
                pass

    def rouvrir_onglet(self):
        """Rouvre le dernier onglet ferme, comme dans les autres navigateurs."""
        while self._fermes:
            url = self._fermes.pop()
            if url:
                self.nouvel_onglet(url)
                return True
        return False

    def zoom_du_site(self, url):
        return self.zooms.get(core.hote(url or ""), 1.0)

    def changer_zoom(self, sens):
        """Monte, descend ou remet le zoom du site en cours.

        Retenu par site : on ne veut pas refaire le reglage a chaque visite,
        et un site lisible n'a pas les memes besoins qu'un autre.
        """
        if not self.actif or not self.actif.url:
            return
        hote = core.hote(self.actif.url)
        if not hote:
            return
        if sens == 0:
            facteur = 1.0
            self.zooms.pop(hote, None)
        else:
            facteur = core.palier_zoom(self.zoom_du_site(self.actif.url), sens)
            self.zooms[hote] = facteur
        core.enregistrer_zooms(self.zooms)
        self.appliquer_zoom(self.actif)
        self.signaler("Zoom %d %% sur %s" % (round(facteur * 100), hote),
                      erreur=False)

    def appliquer_zoom(self, onglet):
        try:
            onglet.vue.ZoomFactor = self.zoom_du_site(onglet.url)
        except Exception as e:
            journal("zoom : %s" % e)

    def aller_accueil(self):
        self.ecrire_accueil()
        self.aller(ACCUEIL)

    def reculer(self):
        try:
            if self.actif and self.actif.vue.CoreWebView2.CanGoBack:
                self.actif.vue.CoreWebView2.GoBack()
        except Exception:
            pass

    def avancer(self):
        try:
            if self.actif and self.actif.vue.CoreWebView2.CanGoForward:
                self.actif.vue.CoreWebView2.GoForward()
        except Exception:
            pass

    def recharger(self):
        try:
            if self.actif:
                self.actif.vue.CoreWebView2.Reload()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Clavier
    # ------------------------------------------------------------------
    def au_clavier_champ(self, envoyeur, args):
        if args.KeyCode == Keys.Down:
            args.SuppressKeyPress = True
            if not self._suggestions:
                self.montrer_suggestions()
            self.deplacer_choix(1)
        elif args.KeyCode == Keys.Up:
            args.SuppressKeyPress = True
            self.deplacer_choix(-1)
        elif args.KeyCode == Keys.Enter:
            args.SuppressKeyPress = True
            choisi = None
            if 0 <= self._choix_suggestion < len(self._suggestions):
                choisi = self._suggestions[self._choix_suggestion][1]
            self.cacher_suggestions()
            self.aller(choisi or self.champ.Text)
        elif args.KeyCode == Keys.Escape:
            args.SuppressKeyPress = True
            if self._suggestions:
                self.cacher_suggestions()
            elif self.actif:
                self.champ.Text = self.actif.url

    def au_clavier(self, envoyeur, args):
        # AltGr, sur un clavier francais, c'est Ctrl + Alt : Windows le
        # rapporte ainsi. Sans cette garde, AltGr+2 basculait sur le deuxieme
        # onglet au lieu d'ecrire son caractere, et de meme pour tous les
        # chiffres. Aucun raccourci de Plume n'emploie Ctrl+Alt : la touche
        # revient donc entierement a la page, sans etre absorbee.
        if args.Control and args.Alt:
            return
        if args.Control and args.KeyCode == Keys.L:
            args.SuppressKeyPress = True
            self.champ.Focus()
            self.champ.SelectAll()
        elif args.Control and args.KeyCode == Keys.D:
            args.SuppressKeyPress = True
            self.basculer_favori()
        elif args.Control and args.KeyCode == Keys.B:
            args.SuppressKeyPress = True
            self.basculer_barre_favoris()
        elif args.Control and args.Shift and args.KeyCode == Keys.N:
            args.SuppressKeyPress = True
            self.nouvelle_fenetre(privee=True)
        elif args.Control and args.KeyCode == Keys.N:
            args.SuppressKeyPress = True
            self.nouvelle_fenetre()
        elif args.Control and args.Shift and args.KeyCode == Keys.T:
            args.SuppressKeyPress = True
            self.rouvrir_onglet()
        elif args.Control and args.KeyCode == Keys.T:
            args.SuppressKeyPress = True
            self.nouvel_onglet(ACCUEIL)
        elif args.Control and args.KeyCode in (Keys.Oemplus, Keys.Add):
            args.SuppressKeyPress = True
            self.changer_zoom(1)
        elif args.Control and args.KeyCode in (Keys.OemMinus, Keys.Subtract):
            args.SuppressKeyPress = True
            self.changer_zoom(-1)
        elif args.Control and args.KeyCode in (Keys.D0, Keys.NumPad0):
            args.SuppressKeyPress = True
            self.changer_zoom(0)
        elif args.Control and args.KeyCode == Keys.W:
            args.SuppressKeyPress = True
            if self.actif:
                self.fermer(self.actif)
        elif args.Control and args.Shift and args.KeyCode == Keys.Tab:
            args.SuppressKeyPress = True
            self.onglet_voisin(-1)
        elif args.Control and args.KeyCode == Keys.Tab:
            args.SuppressKeyPress = True
            self.onglet_voisin(1)
        elif args.Control and Keys.D1 <= args.KeyCode <= Keys.D9:
            # Ctrl+1 a Ctrl+8 designent un onglet, Ctrl+9 le dernier, quel
            # qu'il soit : c'est la convention de tous les navigateurs.
            args.SuppressKeyPress = True
            montres = self.onglets
            rang = int(args.KeyCode) - int(Keys.D1)
            if not montres:
                pass
            elif rang == 8:
                self.activer(montres[-1], glisser=True)
            elif rang < len(montres):
                self.activer(montres[rang], glisser=True)
        elif args.Alt and args.KeyCode == Keys.Left:
            args.SuppressKeyPress = True
            self.reculer()
        elif args.Alt and args.KeyCode == Keys.Right:
            args.SuppressKeyPress = True
            self.avancer()
        elif args.KeyCode == Keys.F5:
            args.SuppressKeyPress = True
            self.recharger()

    # ------------------------------------------------------------------
    # Messages venus des pages
    # ------------------------------------------------------------------
    def traiter(self, onglet, message):
        genre = message.get("type")
        if genre == "travail":
            # Demande venue de la page d'accueil, qui est un fichier local a
            # nous : elle n'a pas d'autre moyen de parler a l'application.
            nom = str(message.get("nom") or "")
            journal("travail : %s %r" % (message.get("action"), nom))
            if message.get("action") == "couleurs":
                indices = message.get("indices")
                if isinstance(indices, list):
                    self.definir_couleurs_travail(nom, indices)
                return
            if message.get("action") == "supprimer":
                self.supprimer_groupe_travail(nom)
            else:
                self.ouvrir_groupe_travail(nom)
            return
        if genre == "maj":
            # Demande venue du bandeau que nous avons pose nous-memes. On ne
            # fait rien sans une mise a jour en attente : une page ne doit pas
            # pouvoir declencher un telechargement a elle seule.
            if not getattr(self, "_maj", None):
                return
            action = str(message.get("action") or "")
            if action == "installer" and not self._maj_en_cours:
                self._maj_en_cours = True
                threading.Thread(target=self.installer_maj,
                                 daemon=True).start()
            elif action == "annuler":
                self._maj_annulee = True
            return
        if genre == "reglage":
            # Demande venue de la page d'accueil, qui est un fichier local a
            # nous : elle n'a pas d'autre moyen de parler a l'application.
            cle = str(message.get("cle") or "")
            if cle == "langue":
                if core.definir_langue(str(message.get("valeur") or "")):
                    self.appliquer_langue()
            elif cle == "defaut":
                core.ouvrir_reglages_defaut()
            return
        if genre != "zone":
            journal("msg %s | actif=%s | %s"
                    % (genre, onglet is self.actif,
                       str(message.get("url"))[:60]))
        if genre == "url":
            # le fichier doit exister avant la premiere lecture : on l'ecrit
            # des qu'une page est chargee, sans attendre qu'une video s'ouvre
            if time.time() - self._cookies_exportes > 60:
                self._cookies_exportes = time.time()
                self.exporter_cookies()
            onglet.url = message.get("url") or onglet.url
            onglet.lecteur_site = False     # le script parle, donc il agit
            self.noter_historique(onglet.url, message.get("titre") or "")
            self.appliquer_zoom(onglet)
            self.enregistrer_session()
            if getattr(onglet, "rendre_focus", False) and onglet is self.actif:
                onglet.rendre_focus = False
                self.champ.Focus()
            if message.get("titre"):
                onglet.definir_titre(message["titre"])
            if onglet is self.actif:
                self.afficher_url(onglet)
                # Redessiner explicitement : l'etoile et le bouton du lecteur
                # dependent de l'adresse, et leurs rectangles ne sont calcules
                # qu'au rendu. Sans cela, l'etoile pouvait rester absente et
                # donc inutilisable, son rectangle vide empechant meme la
                # detection du survol qui aurait provoque un nouveau rendu.
                self.barre_nav.Invalidate()
        elif genre == "hors_video":
            onglet.incrustation.arreter()   # meme en arriere-plan : la page a change
        elif onglet is not self.actif:
            return                      # un onglet cache ne repositionne rien
        elif genre == "page_video":
            self.demarrer_video(onglet, message.get("url"), message.get("titre"))
        elif genre == "zone":
            self.placer_lecteur(onglet, message)

    def exporter_cookies(self):
        """Ecrit les cookies YouTube dans un fichier, pour yt-dlp.

        On ne peut pas lire la base du profil pendant que le navigateur tourne :
        il la verrouille. On passe donc par l'API de WebView2, qui donne les
        cookies dechiffres, et on les ecrit au format Netscape que yt-dlp lit
        avec --cookies.
        """
        if not self.actif or not self.actif.vue.CoreWebView2:
            return
        try:
            gestionnaire = self.actif.vue.CoreWebView2.CookieManager
            tache = gestionnaire.GetCookiesAsync("https://www.youtube.com")
        except Exception as e:
            journal("cookies : %s" % e)
            return

        def quand_pret(terminee):
            # Le resultat contient des objets COM de WebView2 : les lire depuis
            # le fil du pool leve « Unable to cast to ICoreWebView2Cookie ».
            # Tout se fait donc sur le fil d'interface.
            self.Invoke(Action(lambda: self._ecrire_cookies(terminee)))

        try:
            tache.ContinueWith(Action[Task](quand_pret))
        except Exception as e:
            journal("cookies : %s" % e)

    def _ecrire_cookies(self, terminee):
            try:
                lignes = ["# Netscape HTTP Cookie File",
                          "# genere par Plume, ne pas modifier a la main", ""]
                for c in terminee.Result:
                    domaine = c.Domain
                    universel = "TRUE" if domaine.startswith(".") else "FALSE"
                    # Expires est un DateTime .NET ; le format Netscape veut
                    # un horodatage Unix, et 0 pour un cookie de session.
                    expire = 0
                    try:
                        if not c.IsSession:
                            ecart = c.Expires.ToUniversalTime() - EPOCH
                            expire = max(0, int(ecart.TotalSeconds))
                    except Exception:
                        expire = 0
                    lignes.append("\t".join([
                        domaine, universel, c.Path,
                        "TRUE" if c.IsSecure else "FALSE",
                        str(expire), c.Name, c.Value]))
                core.FICHIER_COOKIES.write_text("\n".join(lignes) + "\n",
                                                encoding="utf-8")
                journal("cookies exportes : %d" % (len(lignes) - 3))
            except Exception as e:
                journal("cookies : %s" % e)

    def guetter_mise_a_jour(self):
        """Regarde, en fond, s'il existe une version plus recente.

        Sur un fil a part : une interrogation reseau au demarrage, meme
        courte, ne doit pas retarder l'apparition de la fenetre. Et sur la
        premiere fenetre seulement, comme le canal local : trois fenetres ne
        posent pas trois fois la meme question.

        Le resultat revient par `Invoke` : le bandeau appartient a l'interface,
        et l'interface n'appartient qu'a son propre fil.
        """
        try:
            manifeste = core.chercher_mise_a_jour(
                core.CONFIG.get("manifeste_maj", ""))
        except Exception as e:
            return journal("recherche de mise a jour : %s" % e)
        if not manifeste:
            return
        self._maj = manifeste
        texte = core.t("maj_disponible", manifeste["version"])
        # Une page ne sera prete que dans quelques secondes. On patiente
        # jusqu'a une minute, puis on renonce : passe ce delai, l'annonce
        # arriverait alors que la personne est deja partie faire autre chose,
        # et un bandeau surgi de nulle part vaut moins que pas de bandeau.
        for _ in range(60):
            porte = []
            try:
                self.Invoke(Action(
                    lambda: porte.append(self.annoncer_maj(texte))))
            except Exception as e:
                return journal("annonce de mise a jour : %s" % e)
            if porte and porte[0]:
                return
            time.sleep(1.0)
        journal("mise a jour %s : aucune page prete pour l'annoncer"
                % manifeste["version"])

    def installer_maj(self):
        """Telecharge, verifie, previent, puis installe. Sur un fil a part.

        Rien de ce qui touche a la page n'est fait ici : tout repasse par
        `Invoke`, le controle WebView2 ayant une affinite de fil qui ne se
        negocie pas.
        """
        manifeste = self._maj
        self._maj_annulee = False

        def dire(texte, bouton=None, action=None):
            try:
                self.Invoke(Action(
                    lambda: self.bandeau_maj(texte, bouton, action)))
            except Exception:
                pass

        dernier = [0]

        def avancement(recus, total):
            # Une fois par pour-cent, pas a chaque bloc : reecrire le bandeau
            # mille fois par seconde ne le rendrait pas plus lisible.
            part = int(recus * 100 / total) if total else 0
            if part != dernier[0]:
                dernier[0] = part
                dire(core.t("maj_telechargement", part))

        dire(core.t("maj_telechargement", 0))
        chemin = core.telecharger_mise_a_jour(manifeste, progression=avancement)
        if chemin is None:
            self._maj_en_cours = False
            return dire(core.t("maj_echec"))

        # Le compte a rebours : rien ne commence sans qu'on ait pu l'arreter.
        for reste in range(DUREE_AVANT_MAJ, 0, -1):
            if self._maj_annulee:
                self._maj_en_cours = False
                return dire(core.t("maj_annulee"))
            dire(core.t("maj_bientot", reste), core.t("maj_annuler"),
                 "annuler")
            time.sleep(1.0)
        if self._maj_annulee:
            self._maj_en_cours = False
            return dire(core.t("maj_annulee"))

        dire(core.t("maj_lancement"))
        try:
            # /SILENT plutot que /VERYSILENT : la barre de progression de
            # l'installeur reste visible, ce qui evite l'impression que rien
            # ne se passe pendant que Plume disparait.
            # /relance=1 lui demande de rouvrir Plume a la fin.
            subprocess.Popen(
                [str(chemin), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                 "/DIR=%s" % core.dossier_installe(), "/relance=1"],
                creationflags=core.CREATE_NO_WINDOW)
        except Exception as e:
            self._maj_en_cours = False
            journal("lancement de la mise a jour : %s" % e)
            return dire(core.t("maj_echec"))
        # On se retire : l'installeur ne peut pas remplacer des fichiers
        # qu'un processus tient ouverts.
        self.quitter_pour_maj()

    def quitter_pour_maj(self):
        """Ferme Plume pour laisser l'installeur travailler.

        Isole dans sa propre methode parce que `Application.Exit` est une
        methode statique de .NET : un test ne peut pas la remplacer, et il
        n'aurait aucune envie de la laisser s'executer.
        """
        try:
            self.Invoke(Action(lambda: Application.Exit()))
        except Exception:
            pass

    def bandeau_maj(self, texte, bouton=None, action=None):
        """Bandeau avec un bouton qui reparle a Plume. Faux si pas de page.

        A appeler SUR LE FIL DE LA FENETRE.
        """
        try:
            if not self.actif or self.actif.vue.CoreWebView2 is None:
                return False
        except Exception:
            return False
        style = ("position:fixed;z-index:2147483647;left:50%;top:24px;"
                 "transform:translateX(-50%);max-width:min(680px,86vw);"
                 "display:flex;align-items:center;gap:14px;"
                 "background:#1c1b22;color:#d6d6e0;border:1px solid #7c5cff;"
                 "border-radius:10px;padding:12px 16px;"
                 "font:13px/1.5 'Segoe UI',sans-serif;"
                 "box-shadow:0 12px 40px rgba(0,0,0,.55)")
        bouton_style = ("background:#7c5cff;color:#fff;border:0;"
                        "border-radius:7px;padding:7px 14px;cursor:pointer;"
                        "font:600 13px 'Segoe UI',sans-serif;flex:none")
        # Tout ce qui entre dans la page passe par json.dumps : un titre de
        # version venu du reseau ne doit pas pouvoir fermer une chaine et
        # ecrire du script.
        script = (
            "(function(){var d=document.getElementById('plume-mot');"
            "if(!d){d=document.createElement('div');d.id='plume-mot';"
            "document.body.appendChild(d);}"
            "if(d._t)clearTimeout(d._t);"
            "d.style.cssText=%s;d.textContent='';"
            "var s=document.createElement('span');s.textContent=%s;"
            "s.style.flex='1';d.appendChild(s);"
            "%s})();"
            % (json.dumps(style), json.dumps(texte),
               ("var b=document.createElement('button');b.textContent=%s;"
                "b.style.cssText=%s;b.onclick=function(){"
                "try{window.chrome.webview.postMessage(JSON.stringify("
                "{type:'maj',action:%s}));}catch(e){}};"
                "d.appendChild(b);"
                % (json.dumps(bouton), json.dumps(bouton_style),
                   json.dumps(action))) if bouton else ""))
        try:
            self.actif.vue.CoreWebView2.ExecuteScriptAsync(script)
            return True
        except Exception as e:
            journal("bandeau de mise a jour : %s" % e)
            return False

    def annoncer_maj(self, texte):
        """Pose le bandeau si une page peut le porter. Faux sinon.

        A appeler SUR LE FIL DE LA FENETRE : `CoreWebView2` ne se lit pas
        ailleurs.
        """
        return self.bandeau_maj(texte, core.t("maj_bouton"), "installer")

    def signaler(self, texte, erreur=True, garder=False):
        """Affiche un bandeau dans la page active.

        Sans cela, un echec de lecture ne se voit pas : la zone du lecteur reste
        simplement vide et rien n'explique pourquoi. `erreur=False` sert aux
        nouvelles ordinaires, un telechargement termine par exemple : les
        annoncer en rouge les ferait passer pour des pannes.
        """
        if erreur:
            couleurs = ("#2b1b1b", "#ffd9d9", "#7a3b3b")
        else:
            couleurs = ("#1c1b22", "#d6d6e0", "#7c5cff")
        # Le style est passe par json.dumps, comme le texte : ecrit a la main
        # dans une chaine entre apostrophes, le « \'Segoe UI\' » de la police
        # refermait cette chaine. Le script devenait invalide, et comme
        # ExecuteScriptAsync n'annonce pas les erreurs de la page, AUCUN
        # bandeau n'est jamais apparu, pas meme pour les echecs de lecture.
        style = ("position:fixed;z-index:2147483647;left:50%%;top:24px;"
                 "transform:translateX(-50%%);max-width:min(680px,86vw);"
                 "background:%s;color:%s;border:1px solid %s;"
                 "border-radius:10px;padding:12px 16px;"
                 "font:13px/1.5 'Segoe UI',sans-serif;"
                 "box-shadow:0 12px 40px rgba(0,0,0,.55)") % couleurs

        def afficher():
            try:
                if not self.actif or not self.actif.vue.CoreWebView2:
                    return
                # Un identifiant fixe : un bandeau qui se met a jour
                # remplace le precedent au lieu de s'empiler dessus.
                script = (
                    "(function(){var d=document.getElementById('plume-mot');"
                    "if(!d){d=document.createElement('div');"
                    "d.id='plume-mot';document.body.appendChild(d);}"
                    "d.textContent=%s;d.style.cssText=%s;"
                    "if(d._t)clearTimeout(d._t);"
                    "%s})();"
                    % (json.dumps(texte), json.dumps(style),
                       "" if garder
                       else "d._t=setTimeout(function(){d.remove();},12000);"))
                self.actif.vue.CoreWebView2.ExecuteScriptAsync(script)
            except Exception as e:
                journal("bandeau : %s" % e)
        try:
            if self.InvokeRequired:
                self.Invoke(Action(afficher))
            else:
                afficher()
        except Exception as e:
            journal("bandeau : appel impossible : %r" % (e,))

    def noter_position(self, onglet, position, duree):
        """Retient ou l'on en est dans la video de cet onglet."""
        cle = core.cle_video(onglet.url or "")
        if not cle:
            return
        if core.noter_position(positions(), cle, position, duree,
                               onglet.titre or ""):
            ecrire_positions()
            # Le volume aussi : il se regle souvent juste avant de fermer.
            core.ecrire_son()

    def relancer_lecteur(self, onglet):
        """Rallume le lecteur d'un onglet video sur lequel on revient.

        Ne fait rien si une lecture est deja en cours, ni si l'utilisateur a
        choisi le lecteur du site : dans les deux cas il n'y a rien a relancer.
        """
        if not onglet or not onglet.url or onglet.lecteur_site:
            return
        if not core.est_video(onglet.url):
            return
        try:
            if onglet.incrustation.en_cours():
                return
            noyau = onglet.vue.CoreWebView2
            if noyau is None:
                return
            noyau.ExecuteScriptAsync(SCRIPT_REANNONCE)
        except Exception as e:
            journal("relance du lecteur : %s" % e)

    def demarrer_video(self, onglet, url, titre):
        if not url:
            return
        # Comparer l'identite de la video, pas l'adresse : YouTube ajoute puis
        # retire `&themeRefresh=1` juste apres le chargement, ce qui faisait
        # relancer le lecteur trois fois de suite, chaque relance tuant la
        # precedente en plein chargement.
        if (core.cle_video(onglet.incrustation.url) == core.cle_video(url)
                and onglet.incrustation.en_cours()):
            return                      # deja en cours : ne pas tout relancer
        self.exporter_cookies()      # yt-dlp en a besoin pour YouTube
        journal("video : %s  (pubs bloquees jusqu'ici : %d)"
                % (url, self.pubs_bloquees))
        onglet.incrustation.definir_parent(self.Handle.ToInt64())
        # Nouvelle lecture : la fin a venir devra de nouveau faire avancer la
        # playlist, meme s'il s'agit de la video qu'on vient de terminer.
        onglet._fin_traitee = None
        depart = 0.0
        if not core.est_live(url):
            depart = core.position_reprise(positions(), core.cle_video(url))
        # La reprise ne s'annonce pas : le curseur est deja pose au bon
        # endroit, et un bandeau a chaque video devient vite une corvee.
        resultat = onglet.incrustation.demarrer(url, titre, depart=depart)
        journal("  demarrer -> %s" % resultat)

    def placer_lecteur(self, onglet, message):
        """Retient la zone du lecteur, telle que la page l'exprime.

        La zone est retenue pour TOUS les onglets, le lecteur n'est montre que
        pour celui qu'on regarde. Une page d'arriere-plan continue de tourner
        et de renvoyer sa zone toutes les 120 ms : sans ce partage, elle
        rouvrait son lecteur par-dessus la page active, et l'affichait a la
        taille de sa derniere mise en page, souvent celle d'un autre ecran.
        """
        l, h = int(message.get("l", 0)), int(message.get("h", 0))
        if not l or not h:
            onglet.zone_page = None
            return onglet.incrustation.cacher()
        onglet.zone_page = (int(message.get("x", 0)), int(message.get("y", 0)),
                            l, h)
        try:
            taille = self.contenu.ClientSize
            onglet.taille_mesure = (taille.Width, taille.Height)
        except Exception:
            onglet.taille_mesure = None
        self.replacer(onglet)

    def replacer(self, onglet=None):
        """Traduit la zone de la page en coordonnees ecran et deplace mpv.

        Appele aussi quand la fenetre bouge ou change de taille : sans cela, le
        lecteur n'etait repositionne qu'a la prochaine mesure de la page, soit
        jusqu'a 120 ms plus tard, et trainait visiblement derriere la fenetre.
        """
        onglet = onglet or self.actif
        if not onglet or not onglet.zone_page:
            return
        # Seul l'onglet regarde a droit a son lecteur. C'est une fenetre de
        # premier niveau : rien dans la pile des fenetres ne l'empecherait de
        # couvrir la page d'un autre onglet, ni meme d'une autre application.
        if onglet is not self.actif:
            return onglet.incrustation.cacher()
        # Tant que la fenetre n'est pas entierement opaque, le lecteur reste
        # cache. Sa fenetre est de premier niveau : elle ne suit pas le fondu
        # et arrivait donc franche par-dessus une page encore transparente,
        # video visible avant la page qui l'entoure. La page renvoie sa zone
        # toutes les 120 ms : le lecteur apparait des que le fondu est fini.
        try:
            if (self.Opacity < 0.99 or self._glisse_page is not None
                    or self._chute is not None):
                return onglet.incrustation.cacher()
        except Exception:
            pass
        try:
            origine = self.contenu.PointToScreen(Point(0, 0))
            taille = self.contenu.Size
        except Exception:
            return
        x, y, l, h = onglet.zone_page
        bornes = (origine.X, origine.Y,
                  origine.X + taille.Width, origine.Y + taille.Height)
        onglet.incrustation.placer(origine.X + x, origine.Y + y, l, h, bornes)

    # ------------------------------------------------------------------
    # Fenetre : accrochage, cadre, redimensionnement
    # ------------------------------------------------------------------
    def offrir_accrochage(self):
        """Rend la fenetre accrochable par Windows, sans lui rendre son cadre.

        Windows ne propose l'ancrage qu'aux fenetres qu'il tient pour
        redimensionnables. Mesure faite : une fenetre `FormBorderStyle.None`
        n'a ni WS_THICKFRAME, ni WS_SYSMENU, ni WS_MINIMIZEBOX. Win+fleche, le
        glissement vers un bord, les dispositions d'ancrage de Windows 11 et
        l'assistant qui propose de remplir l'autre moitie lui etaient donc tous
        refuses.

        On repose les styles, et le cadre qu'ils ramenent est efface par notre
        reponse a WM_NCCALCSIZE : la zone client couvre toute la fenetre, donc
        le systeme n'y dessine rien. C'est ce que font Chrome et le Terminal
        Windows, pour la meme raison.
        """
        try:
            self._installer_procedure()
            poignee = ctypes.c_void_p(self.Handle.ToInt64())
            style = _lire_style(poignee, GWL_STYLE)
            voulu = (int(style) | WS_THICKFRAME | WS_SYSMENU
                     | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
            if voulu != int(style):
                _ecrire_style(poignee, GWL_STYLE, voulu)
            # Sans SWP_FRAMECHANGED, Windows garde en cache son calcul de cadre
            # et le changement de style reste sans effet.
            user32.SetWindowPos(poignee, None, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER
                                | SWP_NOACTIVATE | SWP_FRAMECHANGED)
            # WS_THICKFRAME ramene le cadre de Windows 11 : bordure claire
            # et changeante, et une zone de titre qui apparait en bandeau clair
            # le temps de notre premier dessin. On habille les deux, plutot que
            # de les supprimer : sans arete franche, une fenetre sombre se
            # confond avec ce qu'il y a derriere.
            habiller_cadre(self.Handle.ToInt64(),
                           ui.BORD_PRIVE if self.privee else ui.BORD_FENETRE,
                           ui.FOND_ONGLETS)
        except Exception as e:
            journal("accrochage : %s" % e)

    def _installer_procedure(self):
        """Prend la main sur les messages de la fenetre, par la voie native.

        Redefinir `WndProc` ne servait a rien : pythonnet ne redirige pas vers
        Python les methodes virtuelles protegees d'une classe .NET derivee.
        Mesure : zero message recu, alors que la fenetre en traitait. Tout ce
        qui reposait sur cette redefinition etait donc mort, bords saisissables
        compris.

        La procedure est gardee sur l'instance : liberee par le ramasse-miettes
        alors que Windows la connait encore, elle ferait tomber le processus au
        message suivant.
        """
        if self._procedure is not None:
            return
        poignee = ctypes.c_void_p(self.Handle.ToInt64())
        self._procedure = TYPE_PROCEDURE(self._traiter_message)
        # `_ecrire_style` attend un entier en troisieme position : le pointeur
        # de fonction est donc converti, pas passe tel quel.
        adresse = ctypes.cast(self._procedure, ctypes.c_void_p).value
        self._ancienne_procedure = _ecrire_style(poignee, GWLP_WNDPROC,
                                                 adresse)

    def _chainer(self, hwnd, msg, wparam, lparam):
        return user32.CallWindowProcW(
            ctypes.c_void_p(self._ancienne_procedure), hwnd, msg,
            wparam, lparam)

    def _traiter_message(self, hwnd, msg, wparam, lparam):
        """Notre procedure de fenetre. Ne doit JAMAIS laisser filer d'erreur.

        Elle est appelee par Windows lui-meme : une exception qui remonte ici
        traverse du code natif, et ce qui arrive ensuite n'est pas defini.
        """
        try:
            if msg == WM_NCCALCSIZE and wparam:
                return 0            # la zone client couvre toute la fenetre
            if msg == WM_GETMINMAXINFO:
                if self._bornes_agrandissement(lparam):
                    return 0
            if msg == WM_NCHITTEST:
                defaut = self._chainer(hwnd, msg, wparam, lparam)
                if defaut == HTCLIENT:
                    zone = self._zone_saisie(lparam)
                    if zone:
                        return zone
                return defaut
        except Exception:
            plantage("procedure de fenetre")
        return self._chainer(hwnd, msg, wparam, lparam)

    def _bornes_agrandissement(self, lparam):
        """Repond a WM_GETMINMAXINFO : agrandir sur l'ecran courant.

        C'est la reponse au defaut qui avait fait ecrire un agrandissement
        maison : `MaximizedBounds` fige des coordonnees absolues, et une
        fenetre agrandie sur un second ecran repartait sur le premier. Ici on
        interroge l'ecran le plus proche de la fenetre au moment ou la question
        est posee, donc toujours le bon.

        Sans cette reponse, la zone client couvrant toute la fenetre, une
        fenetre agrandie deborderait de l'ecran de l'epaisseur du cadre.
        """
        ecran = user32.MonitorFromWindow(
            ctypes.c_void_p(self.Handle.ToInt64()), MONITOR_AU_PLUS_PRES)
        if not ecran:
            return False
        infos = INFOS_ECRAN()
        infos.taille = ctypes.sizeof(INFOS_ECRAN)
        if not user32.GetMonitorInfoW(ctypes.c_void_p(ecran),
                                      ctypes.byref(infos)):
            return False
        mm = ctypes.cast(ctypes.c_void_p(lparam),
                         ctypes.POINTER(INFOS_MINMAX)).contents
        travail, plein = infos.travail, infos.ecran
        # La position se compte depuis le coin de l'ECRAN, pas du bureau.
        mm.position_max.x = travail.gauche - plein.gauche
        mm.position_max.y = travail.haut - plein.haut
        mm.taille_max.x = travail.droite - travail.gauche
        mm.taille_max.y = travail.bas - travail.haut
        mm.maxi.x = mm.taille_max.x
        mm.maxi.y = mm.taille_max.y
        return True

    # marges de saisie pour redimensionner, en pixels
    MARGE = 6

    def _zone_saisie(self, lparam):
        """A quelle partie de la fenetre appartient le point vise.

        Windows demande, nous repondons : bord gauche, coin bas droit, barre de
        titre, bouton d'agrandir. Il se charge ensuite du redimensionnement, du
        deplacement et de l'ancrage, avec son comportement habituel plutot
        qu'une imitation.
        """
        brut = int(lparam) & 0xFFFFFFFF
        x, y = brut & 0xFFFF, (brut >> 16) & 0xFFFF
        if x >= 0x8000:
            x -= 0x10000
        if y >= 0x8000:
            y -= 0x10000
        p = self.PointToClient(Point(x, y))

        if not self._maximise:
            g = p.X <= self.MARGE
            d = p.X >= self.ClientSize.Width - self.MARGE
            h = p.Y <= self.MARGE
            b = p.Y >= self.ClientSize.Height - self.MARGE
            if h and g:
                return 13                     # HTTOPLEFT
            if h and d:
                return 14                     # HTTOPRIGHT
            if b and g:
                return 16                     # HTBOTTOMLEFT
            if b and d:
                return 17                     # HTBOTTOMRIGHT
            if g:
                return 10                     # HTLEFT
            if d:
                return 11                     # HTRIGHT
            if h:
                return 12                     # HTTOP
            if b:
                return 15                     # HTBOTTOM
        return self._zone_de_titre(p)

    def _zone_de_titre(self, p):
        """Traduit un point de la fenetre en partie « titre », pour Windows.

        Repondre HTCAPTION sur la partie libre de la barre d'onglets confie le
        deplacement a Windows, et avec lui tout ce qui en depend : le
        glissement vers un bord qui ancre, le secouement, le double-clic qui
        agrandit.

        Repondre HTMAXBUTTON sur le bouton d'agrandissement fait apparaitre au
        survol les dispositions d'ancrage de Windows 11. C'est la seule facon
        de les obtenir : le systeme ne les propose qu'a cette reponse.
        """
        try:
            haut = self.barre_onglets.Top
            if p.Y < haut or p.Y >= haut + self.barre_onglets.Height:
                return None
            dans_la_barre = Point(p.X - self.barre_onglets.Left, p.Y - haut)
            r = (self.rect_fenetre.get("agrandir")
                 or self.rect_fenetre.get("restaurer"))
            if r is not None and r.Contains(dans_la_barre):
                return HTMAXBUTTON
            if self.zone_libre(dans_la_barre):
                return HTCAPTION
        except Exception:
            pass
        return None

    def au_deplacement(self, envoyeur, args):
        self.cacher_suggestions()
        """La fenetre a bouge : le lecteur suit sans attendre."""
        self.replacer()

    def au_redimensionnement(self, envoyeur, args):
        """Taille changee : seul le lecteur est a replacer."""
        self.replacer()

    def au_demarrage(self, envoyeur, args):
        # Une taille de repli, sinon « restaurer » n'a nulle part ou revenir et
        # le bouton semble sans effet : la fenetre demarre agrandie, donc aucune
        # taille precedente n'a jamais ete memorisee.
        # Avant toute chose : rendre la fenetre accrochable. Les styles
        # doivent etre poses avant qu'on lui donne sa taille, sinon le premier
        # agrandissement se fait encore sans eux.
        self.offrir_accrochage()
        travail = Screen.FromHandle(self.Handle).WorkingArea
        largeur = min(1440, int(travail.Width * 0.8))
        hauteur = min(900, int(travail.Height * 0.85))
        self._avant_agrandissement = Rectangle(
            travail.X + (travail.Width - largeur) // 2,
            travail.Y + (travail.Height - hauteur) // 2, largeur, hauteur)
        voulu = self._bornes_voulues
        if voulu is not None and not self._encore_visible(voulu):
            voulu = None        # les ecrans ont change depuis : on renonce
        if voulu is not None:
            self._avant_agrandissement = voulu
            # La taille normale est posee dans tous les cas : c'est celle que
            # « restaurer » retrouvera, et Windows la retient de lui-meme.
            self.Bounds = voulu
            if self._agrandie_voulue:
                self.WindowState = FormWindowState.Maximized
        else:
            self.Bounds = self._avant_agrandissement
            self.WindowState = FormWindowState.Maximized
        self.placer_champ()
        self.marquer_pour_la_barre()
        if len(FENETRES) == 1:
            self.poser_les_taches()
        if len(FENETRES) == 1:      # une seule fenetre tient le canal local
            threading.Thread(target=self.ecouter, daemon=True).start()
            threading.Thread(target=self.guetter_mise_a_jour,
                             daemon=True).start()
        # Pendant l'ouverture, la fenetre reste invisible : elle apparaitra
        # quand l'ecran d'ouverture s'effacera, pas par-dessus lui.
        if not self._sans_fondu and _OUVERTURE[0] is None:
            self.fondre(1.0, DUREE_FENETRE_OUVRE)
        self._pose = True

    def _encore_visible(self, bornes):
        """Cette geometrie tombe-t-elle encore sur un ecran existant ?

        Un portable debranche de ses ecrans rouvrirait sinon ses fenetres dans
        le vide, hors de toute zone affichee.
        """
        try:
            for ecran in Screen.AllScreens:
                zone = ecran.WorkingArea
                if (bornes.Right > zone.Left + 40
                        and bornes.Left < zone.Right - 40
                        and bornes.Bottom > zone.Top + 40
                        and bornes.Top < zone.Bottom - 40):
                    return True
        except Exception:
            return False
        return False

    def marquer_pour_la_barre(self):
        """Dit a Windows quoi epingler quand on epingle cette fenetre.

        Plume.exe n'est qu'un lanceur : le processus reel est pythonw.exe, et
        c'est lui que Windows epinglait, avec son icone et son nom. Ces
        proprietes, posees sur la fenetre, lui donnent la bonne commande, le
        bon nom et la bonne icone.
        """
        try:
            barre_taches.marquer_fenetre(
                self.Handle.ToInt64(), APPID,
                '"%s"' % core.EXECUTABLE, "Plume",
                core.ressource_icone())
        except Exception as e:
            journal("barre des taches : %s" % e)

    def poser_les_taches(self):
        """Menu « Taches » du clic droit sur l'icone de la barre des taches."""
        try:
            icone = core.ressource_icone()
            barre_taches.definir_taches(APPID, [
                (core.t("tache_fenetre"), core.EXECUTABLE,
                 "--nouvelle-fenetre", icone),
                (core.t("tache_privee"), core.EXECUTABLE,
                 "--fenetre-privee", icone),
                (core.t("tache_onglet"), core.EXECUTABLE, "", icone),
            ])
        except Exception as e:
            journal("taches : %s" % e)

    def a_ete_activee(self, envoyeur, args):
        DERNIERE[0] = self
        self.fermer_menu()
        self.verifier_defaut()

    def verifier_defaut(self):
        """Reecrit la page d'accueil si Plume vient d'etre choisie, ou ne l'est
        plus.

        C'est au retour de focus que cela se joue : on revient des Parametres
        de Windows, et le bouton doit avoir disparu. Sans cela il faut ouvrir
        un onglet neuf pour que la page se refasse, ce que personne ne devine.
        """
        try:
            maintenant = core.est_navigateur_par_defaut()
        except Exception:
            return
        if maintenant == self._defaut_connu:
            return
        self._defaut_connu = maintenant
        journal("navigateur par defaut : %s" % maintenant)
        try:
            self.ecrire_accueil()
            for onglet in self.onglets:
                if onglet.url == ACCUEIL:
                    noyau = onglet.vue.CoreWebView2
                    if noyau is not None:
                        noyau.Reload()
        except Exception as e:
            journal("rafraichissement de l'accueil : %s" % e)

    def nouvelle_fenetre(self, url=None, bornes=None, privee=False,
                         vide=False):
        """Ouvre une seconde fenetre, sur le meme fil et le meme profil."""
        journal("fenetre ouverte : %s%s"
                % (str(url)[:90], " (privee)" if privee else ""))
        if len(FENETRES) >= MAX_FENETRES:
            self.signaler("Plume n'ouvre pas plus de %d fenetres : chaque "
                          "onglet coute environ 390 Mo." % MAX_FENETRES)
            return None
        autre = Navigateur(url, None, bornes, privee, vide)
        autre.Show()
        if privee:
            autre.signaler(
                "Fenetre privee : ni historique, ni cookies, ni session "
                "conservee a la fermeture. Vos telechargements, eux, restent "
                "sur le disque, et votre fournisseur d'acces voit toujours "
                "passer le trafic.", erreur=False)
        return autre

    def a_la_fermeture(self, envoyeur, args):
        # Premier passage : on s'efface, puis on rappelle Close pour de bon.
        # La session est ecrite tout de suite, avant l'animation : une
        # coupure de courant pendant le fondu ne doit rien couter.
        if not self._ferme_pour_de_bon:
            self.enregistrer_session(force=True)
            try:
                args.Cancel = True
            except Exception:
                return
            self.fermer_menu()
            self.cacher_suggestions()
            for onglet in self.onglets:
                onglet.incrustation.cacher()

            def pour_de_bon():
                self._ferme_pour_de_bon = True
                try:
                    self.Close()
                except Exception:
                    pass

            self.fondre(0.0, DUREE_FENETRE_FERME, pour_de_bon)
            return
        self._arreter_fondu()
        # avant de detruire quoi que ce soit : la session doit refleter ce qui
        # etait ouvert, pas une fenetre a moitie demontee
        self.enregistrer_session(force=True)
        ecrire_positions(force=True)
        if self in FENETRES:
            FENETRES.remove(self)
        self._fermer_apercu()
        self.cacher_suggestions()
        if self.minuteur_veille is not None:
            self.minuteur_veille.Stop()
            self.minuteur_veille.Dispose()
            self.minuteur_veille = None
        self._finir_glisse_page()
        self._finir_chute()
        self._arreter_anim()
        core.enregistrer_historique(self.historique)
        for onglet in list(self.onglets):
            onglet.incrustation.detruire()
        if DERNIERE[0] is self:
            DERNIERE[0] = FENETRES[0] if FENETRES else None
        if not FENETRES:
            # plus aucune fenetre : la boucle de messages n'a plus lieu d'etre
            Application.ExitThread()

    def ecouter(self):
        """Recoit les demandes d'ouverture venues de l'interface de recherche."""
        try:
            serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            serveur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            serveur.bind(("127.0.0.1", PORT))
            serveur.listen(4)
        except OSError as e:
            journal("canal indisponible : %s" % e)
            return
        journal("canal ouvert sur %d" % PORT)
        while True:
            try:
                lien, _ = serveur.accept()
                donnees = lien.recv(4096).decode("utf-8", "replace").strip()
                lien.sendall(b"ok")
                lien.close()
                cible = DERNIERE[0] or self
                journal("canal local : %r" % donnees[:90])
                if donnees == "fenetre:":
                    cible.Invoke(Action(cible.nouvelle_fenetre))
                elif donnees == "privee:":
                    cible.Invoke(Action(
                        lambda: cible.nouvelle_fenetre(privee=True)))
                elif donnees.startswith("nav:"):
                    # navigue l'onglet courant, au lieu d'en ouvrir un
                    adresse = donnees[4:]
                    cible.Invoke(Action(lambda u=adresse: cible.aller(u)))
                elif donnees.startswith("js:"):
                    script = donnees[3:]
                    cible.Invoke(Action(
                        lambda s=script: cible.actif.vue.CoreWebView2
                        .ExecuteScriptAsync(s)))
                elif donnees:
                    cible.Invoke(Action(
                        lambda u=donnees: cible.nouvel_onglet(u)))
            except Exception as e:
                journal("canal : %s" % e)
                time.sleep(0.5)


def envoyer_au_canal(message):
    """Transmet une demande a une fenetre Plume deja lancee."""
    try:
        lien = socket.create_connection(("127.0.0.1", PORT), timeout=1.0)
        lien.sendall(message.encode("utf-8"))
        lien.recv(16)
        lien.close()
        return True
    except OSError:
        return False


def deja_ouvert(url):
    """Envoie l'URL a une fenetre Plume deja lancee. Vrai si elle a repondu."""
    return envoyer_au_canal(url or ACCUEIL)


# Garde-fou : si le navigateur ne signalait jamais qu'il est pret, l'ouverture
# ne doit pas rester a l'ecran indefiniment.
# Secondes avant qu'une mise a jour acceptee ne se lance. Assez pour
# changer d'avis, trop peu pour donner l'impression d'attendre.
DUREE_AVANT_MAJ = 5
DUREE_MAX_INTRO = 12.0
DUREE_EFFACEMENT = 0.80    # le logotype s'efface, fenetre encore immobile
DUREE_ETALEMENT = 0.65     # l'ouverture rejoint les bords de la fenetre
DUREE_FONDU_CROISE = 0.28  # puis les deux se croisent, l'une sort, l'autre entre
# Vrai pendant l'ouverture : les fenetres construites derriere restent
# invisibles au lieu d'apparaitre en fondu par-dessus elle.
_OUVERTURE = [None]


class Ouverture(object):
    """Ecran d'ouverture, sur son PROPRE fil.

    C'est la le point : WinForms n'a qu'un fil, et construire une fenetre
    WebView2 le bloque une a deux secondes. Une animation jouee sur ce fil-la
    resterait figee pendant tout le chargement, ce qui est exactement le
    contraire de ce qu'on veut. Sur un fil a elle, avec sa propre file de
    messages, elle tourne pendant que le navigateur se monte derriere.

    Ce fil ne touche a rien d'autre que sa propre fenetre : il ne partage avec
    le reste de Plume que trois drapeaux. Une fenetre WinForms appartient au
    fil qui l'a creee, et cette regle ne se contourne pas.
    """

    def __init__(self, zone=None):
        self.debut = time.time()
        # Ecran ou l'ouverture doit jouer. Sur deux moniteurs, se centrer sur
        # l'ecran principal la faisait apparaitre a gauche pendant que le
        # navigateur rouvrait sa session a droite.
        self.zone = zone or Screen.PrimaryScreen.WorkingArea
        self.pret = threading.Event()      # le navigateur est monte
        self.saute = threading.Event()     # un clic a abrege
        self.etale = threading.Event()     # l'ecran a rejoint les bords
        self.termine = threading.Event()   # la fenetre est fermee
        self.cible = None                  # bornes de la fenetre a venir
        self.fil = Thread(ThreadStart(self._jouer))
        self.fil.SetApartmentState(ApartmentState.STA)
        self.fil.IsBackground = True
        self.fil.Start()

    # ------------------------------------------------------------------
    def _jouer(self):
        boite = None
        police = None
        try:
            boite = Form()
            boite.FormBorderStyle = getattr(FormBorderStyle, "None")
            boite.StartPosition = FormStartPosition.Manual
            boite.ShowInTaskbar = False
            boite.Text = ""          # sans titre : rien ne la prend pour une
            boite.BackColor = ui.FOND_PAGE   # fenetre de navigation
            ui.double_tampon(boite)
            travail = self.zone
            largeur, hauteur = 560, 220
            boite.Bounds = Rectangle(
                travail.X + (travail.Width - largeur) // 2,
                travail.Y + (travail.Height - hauteur) // 2, largeur, hauteur)
            try:
                boite.Region = Region(
                    ui.chemin_arrondi(0, 0, largeur, hauteur, 18))
            except Exception:
                pass

            police = Font("Segoe UI", 54.0)

            # Mises a jour par l'etalement : la fenetre grandit, donc la
            # surface a peindre aussi.
            vue = {"l": largeur, "h": hauteur, "etalement": 0.0,
                   "ancre": None, "effacement": 0.0}

            def peindre(envoyeur, args):
                try:
                    ui.peindre_intro(args.Graphics, vue["l"], vue["h"],
                                     time.time() - self.debut, police,
                                     vue["etalement"], vue["ancre"],
                                     vue["effacement"])
                except Exception as e:
                    journal("intro : %s" % e)
                    self.saute.set()

            boite.Paint += peindre
            boite.MouseDown += lambda e, a: self.saute.set()
            boite.Show()
            user32.SetWindowPos(
                ctypes.c_void_p(boite.Handle.ToInt64()),
                ctypes.c_void_p(HWND_TOPMOST), 0, 0, 0, 0,
                SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE)

            # Elle reste tant que les deux conditions ne sont pas reunies :
            # l'animation est allee au bout, ET le navigateur est pret. Ce
            # dernier point est tout l'interet : le chargement se cache
            # derriere, au lieu de se montrer.
            while not self.saute.is_set():
                t = time.time() - self.debut
                if t >= DUREE_MAX_INTRO:
                    break
                if t >= ui.DUREE_INTRO and self.pret.is_set():
                    break
                boite.Invalidate()
                Application.DoEvents()
                time.sleep(0.016)

            # Le logotype s'efface d'abord, la fenetre encore immobile.
            # Bouger un repere pendant qu'on y dessine laisse toujours passer
            # quelque chose ; effacer puis bouger ne laisse rien a voir.
            self._effacer(boite, vue)
            self._etaler(boite, vue)
            self.etale.set()

            # Fondu croise : l'ouverture sort pendant que la fenetre entre, aux
            # memes dimensions. Le raccord ne se voit pas.
            depart = time.time()
            while True:
                avance = (time.time() - depart) / DUREE_FONDU_CROISE
                if avance >= 1.0:
                    break
                try:
                    boite.Opacity = max(0.0, 1.0 - avance)
                except Exception:
                    break
                boite.Invalidate()
                Application.DoEvents()
                time.sleep(0.016)
        except Exception as e:
            journal("intro : %s" % e)
        finally:
            try:
                if boite is not None:
                    boite.Close()
                    boite.Dispose()
            except Exception:
                pass
            try:
                if police is not None:
                    police.Dispose()
            except Exception:
                pass
            self.termine.set()

    # ------------------------------------------------------------------
    def _effacer(self, boite, vue):
        """Fait disparaitre le logotype avant que la fenetre ne bouge."""
        if self.saute.is_set():
            vue["effacement"] = 1.0
            return
        depart = time.time()
        while True:
            p = (time.time() - depart) / DUREE_EFFACEMENT
            if p >= 1.0:
                break
            vue["effacement"] = 1.0 - (1.0 - p) ** 2   # part doucement
            boite.Invalidate()
            Application.DoEvents()
            time.sleep(0.016)
        vue["effacement"] = 1.0
        boite.Invalidate()
        Application.DoEvents()

    # ------------------------------------------------------------------
    def _etaler(self, boite, vue):
        """Etire la fenetre d'ouverture jusqu'aux bords de celle qui arrive.

        Les coins partent rejoindre les quatre coins de la fenetre : l'ecran
        d'ouverture ne disparait pas, il devient la fenetre. C'est le meme
        geste qu'une toile qu'on tend.
        """
        cible = self.cible
        if not cible or self.saute.is_set():
            return
        try:
            x0, y0, l0, h0 = (boite.Left, boite.Top, boite.Width, boite.Height)
            x1, y1, l1, h1 = cible
            journal("intro : etalement %dx%d -> %dx%d en %.2f s"
                    % (l0, h0, l1, h1, DUREE_ETALEMENT))
            # Les coins arrondis disparaissent des le depart : suivre la
            # region a chaque image couterait un objet GDI par image, pour un
            # detail que l'oeil ne saisit pas pendant un mouvement aussi vif.
            boite.Region = None
            depart = time.time()
            while True:
                p = (time.time() - depart) / DUREE_ETALEMENT
                if p >= 1.0:
                    break
                e = 1.0 - (1.0 - p) ** 3        # part vite, arrive en douceur
                gauche = int(x0 + (x1 - x0) * e)
                haut = int(y0 + (y1 - y0) * e)
                vue["etalement"] = e
                vue["l"] = int(l0 + (l1 - l0) * e)
                vue["h"] = int(h0 + (h1 - h0) * e)
                # Le logotype reste ou il etait a l'ecran : on le compose dans
                # les dimensions de la carte et on le decale de ce que la
                # fenetre a bouge.
                vue["ancre"] = (x0 - gauche, y0 - haut, l0, h0)
                boite.Bounds = Rectangle(gauche, haut, vue["l"], vue["h"])
                boite.Invalidate()
                Application.DoEvents()
                time.sleep(0.016)
            vue["etalement"] = 1.0
            vue["l"], vue["h"] = int(l1), int(h1)
            vue["ancre"] = (x0 - int(x1), y0 - int(y1), l0, h0)
            boite.Bounds = Rectangle(int(x1), int(y1), int(l1), int(h1))
            boite.Invalidate()
            Application.DoEvents()
        except Exception as e:
            journal("intro : etalement : %s" % e)

    # ------------------------------------------------------------------
    def ceder(self, cible=None):
        """Annonce que le navigateur est pret, et attend que l'ecran s'efface.

        L'attente se fait en pompant nos propres messages : les fenetres du
        navigateur, deja construites, doivent pouvoir se dessiner pendant que
        l'ouverture finit son fondu.
        """
        self.cible = cible
        self.pret.set()
        # On attend que l'ecran ait rejoint les bords : c'est a cet instant,
        # et pas avant, que la fenetre doit commencer a apparaitre.
        fin = time.time() + DUREE_MAX_INTRO + 4.0
        while (not self.etale.is_set() and not self.termine.is_set()
               and time.time() < fin):
            Application.DoEvents()
            time.sleep(0.016)

    def attendre_fin(self):
        """Laisse l'ouverture finir son fondu, en pompant nos messages."""
        fin = time.time() + 4.0
        while not self.termine.is_set() and time.time() < fin:
            Application.DoEvents()
            time.sleep(0.016)


def zone_de_depart(fenetres):
    """Zone de travail de l'ecran ou la premiere fenetre va s'ouvrir.

    La session retient les bornes de chaque fenetre : si elles tombent encore
    sur un ecran branche, c'est la que le navigateur reviendra, et c'est donc
    la que l'ouverture doit jouer. Sinon, l'ecran principal, ou la fenetre
    atterrira faute de mieux.
    """
    try:
        bornes = (fenetres[0] or {}).get("bornes") if fenetres else None
        if bornes and len(bornes) == 4:
            r = Rectangle(*[int(v) for v in bornes])
            # Une fenetre peut chevaucher deux ecrans : on retient celui
            # qu'elle occupe le plus, pas le premier venu.
            meilleur, surface = None, 0
            for ecran in Screen.AllScreens:
                z = ecran.WorkingArea
                large = min(r.Right, z.Right) - max(r.Left, z.Left)
                haut = min(r.Bottom, z.Bottom) - max(r.Top, z.Top)
                if large <= 40 or haut <= 40:
                    continue
                if large * haut > surface:
                    meilleur, surface = z, large * haut
            if meilleur is not None:
                return meilleur
    except Exception:
        pass
    return Screen.PrimaryScreen.WorkingArea


def demarrer_ouverture(zone=None):
    """Lance l'ecran d'ouverture, ou rien si le reglage le refuse."""
    if not core.CONFIG.get("intro", True):
        return None
    try:
        _OUVERTURE[0] = Ouverture(zone)
        return _OUVERTURE[0]
    except Exception as e:
        journal("intro : %s" % e)
        _OUVERTURE[0] = None
        return None


def attendre_pose(fenetre, limite=3.0):
    """Laisse la fenetre prendre sa geometrie definitive.

    `Shown` arrive APRES le retour de `Show()`, et c'est lui qui pose la
    taille et l'agrandissement. Lire `Bounds` avant, c'est lire la taille du
    constructeur : l'etalement visait alors un rectangle qui n'existait deja
    plus une fraction de seconde apres. Le meme piege que celui qui faisait
    naitre les fenetres detachees en plein ecran.
    """
    fin = time.time() + limite
    while not getattr(fenetre, "_pose", False) and time.time() < fin:
        Application.DoEvents()
        time.sleep(0.01)


def cible_etalement(ouverture, fenetre):
    """Bornes a rejoindre, ou rien si la fenetre a atterri ailleurs.

    L'etalement n'a de sens que d'un point a l'autre du meme ecran. Si la
    fenetre s'est ouverte sur un autre moniteur, la carte traverserait le
    bureau en diagonale : mieux vaut alors un simple fondu.
    """
    try:
        r = fenetre.Bounds
        centre_x = r.X + r.Width // 2
        centre_y = r.Y + r.Height // 2
        if not ouverture.zone.Contains(centre_x, centre_y):
            journal("intro : la fenetre est sur un autre ecran, pas "
                    "d'etalement")
            return None
        return (r.X, r.Y, r.Width, r.Height)
    except Exception:
        return None


def reveler_fenetres(duree=None):
    """Fait apparaitre les fenetres restees invisibles derriere l'ouverture."""
    _OUVERTURE[0] = None
    for fenetre in list(FENETRES):
        try:
            if fenetre.Opacity < 1.0:
                fenetre.fondre(1.0, duree or DUREE_FENETRE_OUVRE)
        except Exception:
            pass


def boucle(depart, privee=False):
    Application.EnableVisualStyles()
    # Sans ce mode, une exception dans un rappel WinForms termine le processus
    # sans rien dire. Avec lui, elle passe par ThreadException, donc par nous.
    try:
        Application.SetUnhandledExceptionMode(
            UnhandledExceptionMode.CatchException)
        Application.ThreadException += (
            lambda envoyeur, args: plantage("interface", args.Exception))
        AppDomain.CurrentDomain.UnhandledException += (
            lambda envoyeur, args: plantage("processus",
                                            args.ExceptionObject))
    except Exception:
        pass
    # La session se lit AVANT de lancer l'ouverture : c'est elle qui dit sur
    # quel ecran la fenetre va revenir, donc ou l'ouverture doit jouer.
    fenetres = [] if privee else (core.charger_session().get("fenetres") or [])
    ouverture = demarrer_ouverture(zone_de_depart(fenetres))
    try:
        # Un contexte sans fenetre principale : sans cela, fermer la premiere
        # fenetre arreterait la boucle de messages et tuerait les autres.
        contexte = ApplicationContext()
        if privee:
            # Lancement direct en prive : aucune session rouverte, ce serait
            # ramener a l'ecran ce que la fenetre est censee ne pas garder.
            premiere = Navigateur(depart, None, None, True)
            premiere.Show()
            attendre_pose(premiere)
            if ouverture is not None:
                ouverture.ceder(cible_etalement(ouverture, premiere))
            reveler_fenetres(DUREE_FONDU_CROISE)
            if ouverture is not None:
                ouverture.attendre_fin()
            premiere.mettre_en_avant()
            Application.Run(contexte)
            return
        premiere = Navigateur(depart, fenetres[0] if fenetres else None)
        premiere.Show()
        for f in fenetres[1:MAX_FENETRES]:
            Navigateur(None, f).Show()
        # Laisser les fenetres prendre leur geometrie avant de viser : sans
        # cela l'etalement s'etire vers un rectangle provisoire.
        attendre_pose(premiere)
        # Tout est monte : l'ouverture peut s'effacer, et les fenetres
        # apparaitre a sa place.
        if ouverture is not None:
            ouverture.ceder(cible_etalement(ouverture, premiere))
        reveler_fenetres(DUREE_FONDU_CROISE)
        if ouverture is not None:
            ouverture.attendre_fin()
        premiere.mettre_en_avant()
        Application.Run(contexte)
    except Exception as e:
        journal("ERREUR : %s" % e)
        plantage("demarrage", e)
        raise


def main():
    arguments = sys.argv[1:]
    veut_fenetre = "--nouvelle-fenetre" in arguments
    veut_privee = "--fenetre-privee" in arguments
    adresses = [a for a in arguments if not a.startswith("--")]
    depart = adresses[0] if adresses else ACCUEIL
    if depart and not depart.startswith(("http://", "https://", "file://")):
        depart = core.normaliser_url(depart)

    # Demande venue du menu de la barre des taches : une fenetre de plus dans
    # l'instance en cours, plutot qu'un onglet.
    if veut_privee:
        if envoyer_au_canal("privee:"):
            return
    elif veut_fenetre:
        if envoyer_au_canal("fenetre:"):
            return
    elif deja_ouvert(depart):   # une fenetre existe deja : elle prend l'onglet
        return

    fil = Thread(ThreadStart(lambda: boucle(depart, privee=veut_privee)))
    fil.SetApartmentState(ApartmentState.STA)   # obligatoire pour WebView2
    fil.Start()

    # Surtout pas fil.Join() : il retient le verrou global de Python pendant
    # toute l'attente. Or le dessin des barres, les clics et le clavier sont des
    # rappels Python, qui ne peuvent alors plus s'executer : la fenetre cesse de
    # repondre et Windows la tue avec un « Application Hang ».
    # time.sleep, lui, relache le verrou a chaque tour.
    while fil.IsAlive:
        time.sleep(0.15)


if __name__ == "__main__":
    main()
