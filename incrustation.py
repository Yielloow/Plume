# -*- coding: utf-8 -*-
"""
Plume / incrustation : place la fenetre mpv a l'interieur de la page web,
exactement sur la zone ou le site afficherait son propre lecteur.

Methode : mpv ouvre sa propre fenetre, sans bordure. On l'adopte ensuite en
donnant la vue de navigation comme proprietaire, puis on la deplace sur la zone
du lecteur que le script de la page nous transmet.

Pourquoi ne pas creer nous-memes la fenetre et la passer a mpv via --wid : une
fenetre appartient au fil qui la cree et n'existe vraiment que s'il fait tourner
une boucle de messages. Les appels venus de la page s'executent dans un fil de
travail de pywebview, qui n'en a pas : la fenetre n'apparaissait jamais. mpv,
lui, gere sa propre fenetre et sa propre boucle.

Les lives (Twitch, Kick) passent par streamlink, qui alimente mpv par un tube :
il gere la latence et les reconnexions bien mieux que le greffon yt-dlp.

Une liaison IPC avec mpv nous dit quand il passe en plein ecran, pour cesser de
le repositionner : sans cela, la boucle de suivi ecrase le plein ecran aussitot.
"""
import ctypes
import itertools
import json
import os
import subprocess
import threading
import time
from ctypes import wintypes

import core

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

# Journal des apparitions et disparitions du lecteur. Un clignotement se voit
# mais ne se raconte pas : sans cette trace, il faut le reproduire pour savoir
# combien de fois la fenetre a ete montree puis cachee, et quand.
_JOURNAL = os.environ.get("PLUME_DEBUG")


def _trace(message):
    if not _JOURNAL:
        return
    try:
        with open(_JOURNAL, "a", encoding="utf-8") as f:
            f.write("%.1f  lecteur : %s\n" % (time.time() % 10000, message))
    except Exception:
        pass

user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
user32.GetParent.restype = wintypes.HWND
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                            ctypes.POINTER(wintypes.DWORD)]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
gdi32.CreateRectRgn.restype = wintypes.HRGN
gdi32.CreateRectRgn.argtypes = [ctypes.c_int] * 4
user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]

if ctypes.sizeof(ctypes.c_void_p) == 8:
    _set_long = user32.SetWindowLongPtrW
    _set_long.restype = ctypes.c_longlong
    _set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_longlong]
    _get_long = user32.GetWindowLongPtrW
    _get_long.restype = ctypes.c_longlong
    _get_long.argtypes = [wintypes.HWND, ctypes.c_int]
else:                                     # Windows 32 bits
    _set_long = user32.SetWindowLongW
    _set_long.restype = ctypes.c_long
    _set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    _get_long = user32.GetWindowLongW
    _get_long.restype = ctypes.c_long
    _get_long.argtypes = [wintypes.HWND, ctypes.c_int]

GWLP_HWNDPARENT = -8
GWL_EXSTYLE = -20
# Une fenetre qui porte ce style n'est pas activee quand elle est montree, ni
# quand on clique dedans. Elle recoit toujours la souris, ce qui suffit a la
# barre de lecture.
#
# Ce qu'il NE fait PAS, mesure a l'appui : il n'empeche pas un
# `SetForegroundWindow` explicite. Il ferme donc le chemin le plus probable,
# celui de la fenetre qui s'active en apparaissant, mais pas tous. C'est pour
# cela que `_rendre_le_focus` reste en place derriere.
WS_EX_NOACTIVATE = 0x08000000
GA_ROOT = 2
SWP_NOACTIVATE = 0x0010
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
HWND_TOP = 0

TITRE_INCRUSTE = "PlumeLecteurIncruste"
_compteur = itertools.count(1)


def _fenetres_du_processus(pid, visibles_seulement=True):
    """Fenetres de premier niveau appartenant a un processus."""
    trouvees = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def rappel(hwnd, _):
        proprio = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proprio))
        if proprio.value != pid:
            return True
        if visibles_seulement and not user32.IsWindowVisible(hwnd):
            return True
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        trouvees.append((hwnd, cls.value,
                         (r.right - r.left) * (r.bottom - r.top)))
        return True

    user32.EnumWindows(rappel, 0)
    return trouvees


def fenetre_du_processus(pid=None):
    """Handle de la fenetre principale du processus : la plus grande visible."""
    candidates = []
    for hwnd, _cls, surface in _fenetres_du_processus(pid or os.getpid()):
        if user32.GetParent(hwnd):
            continue
        if user32.GetWindowTextLengthW(hwnd) <= 0:
            continue
        if surface > 40000:
            candidates.append((surface, hwnd))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _interdire_activation(fenetre, interdite=True):
    """Empeche, ou reautorise, l'activation de cette fenetre.

    mpv ne doit jamais prendre le premier plan : il est incruste dans une page,
    pilote par le tube, et sa fenetre est POSSEDEE par celle de Plume. Or
    activer une fenetre possedee fait remonter tous ses proprietaires : c'est
    par la que Plume passait devant Discord a chaque titre d'une playlist.

    La garantie est partielle, et il vaut mieux le savoir : le style empeche
    l'activation a l'affichage et au clic, pas un `SetForegroundWindow`
    explicite. Mesure faite sur une vraie fenetre.

    Renvoie vrai si le style a ete pose ou retire comme demande.
    """
    if not fenetre:
        return False
    try:
        actuel = int(_get_long(fenetre, GWL_EXSTYLE))
        voulu = (actuel | WS_EX_NOACTIVATE) if interdite \
            else (actuel & ~WS_EX_NOACTIVATE)
        if voulu != actuel:
            _set_long(fenetre, GWL_EXSTYLE, voulu)
        return bool(int(_get_long(fenetre, GWL_EXSTYLE))
                    & WS_EX_NOACTIVATE) == bool(interdite)
    except Exception:
        return False


class Incrustation:
    """Pilote un mpv sans bordure, colle sur la zone du lecteur de la page."""

    def __init__(self, parent=None, au_probleme=None, au_action=None):
        self.parent = parent
        self.au_probleme = au_probleme     # rappel(texte) en cas d'echec
        # rappel(nom, valeur) pour ce que la barre du lecteur demande a la
        # page : defilement, mode theatre. Appele depuis le fil d'ecoute.
        self.au_action = au_action
        self.mpv = None
        self.amont = None            # streamlink, pour les lives
        self.fenetre = None          # fenetre de mpv, une fois adoptee
        self.url = None
        self.plein_ecran = False
        self.tuyau = None            # chemin du tube IPC
        self._visible = False
        self._zone = None
        self._decoupe = None
        self._avec_cookies = False   # premiere tentative : sans la session
        self._titre = None
        self._depart = 0.0           # reprise : ou commencer la lecture
        self._devant_avant = None    # fenetre au premier plan avant la lecture
        self._verrou = threading.Lock()

    def definir_parent(self, hwnd):
        """Change de fenetre hote sans interrompre la lecture.

        La fenetre de mpv est de premier niveau : elle a un proprietaire, pas
        un parent. Changer ce proprietaire suffit a la faire suivre l'onglet
        dans une autre fenetre, et la video ne s'en apercoit pas. Avant, on
        arretait puis relancait la lecture, ce qui la faisait repartir du
        debut a chaque glissement d'onglet.
        """
        if not hwnd or hwnd == self.parent:
            return
        self.parent = hwnd
        with self._verrou:
            fenetre = self.fenetre
        if fenetre and self.en_cours():
            try:
                _set_long(fenetre, GWLP_HWNDPARENT, self.parent)
                _interdire_activation(fenetre, not self.plein_ecran)
            except Exception:
                # Le reparentage a echoue : plutot qu'une fenetre orpheline
                # posee au travers de l'ecran, on relance proprement.
                reprendre = self.url
                self.arreter()
                if reprendre:
                    self.demarrer(reprendre)
                return
            self._attendre_la_page()
            return
        # Rien ne joue : il n'y a qu'a retenir le nouvel hote.
        self._attendre_la_page()

    def _attendre_la_page(self):
        """Efface le lecteur jusqu'a ce que la page redise ou il va.

        `_zone` retient la position ET les bornes de l'ANCIENNE fenetre. S'en
        servir pendant que la nouvelle se pose faisait apparaitre le lecteur au
        mauvais endroit, disparaitre parce que la zone tombait hors des bornes,
        reapparaitre au calcul suivant : un clignotement a chaque onglet sorti
        d'une fenetre pendant une lecture.

        La page renvoie sa zone toutes les 120 ms. Une seule disparition
        breve, puis le lecteur revient une fois, au bon endroit.
        """
        self.cacher()
        self._zone = None

    # ------------------------------------------------------------------
    def _args_mpv(self, titre=None, live=False):
        args = [a for a in core.construire_args_mpv(titre,
                                                    self._avec_cookies)
                if not a.startswith(("--force-window", "--keep-open",
                                     "--force-media-title"))]
        args += [
            # Le volume retenu de la derniere fois. Pose au lancement et non
            # apres, sinon on entendrait le debut trop fort avant la
            # correction.
            "--volume=%d" % core.volume_retenu()[0],
            "--mute=" + ("yes" if core.volume_retenu()[1] else "no"),
            "--no-border",                 # pas de decoration : elle s'incruste
            # Demande a mpv de ne pas prendre le premier plan en s'ouvrant.
            # **Mesure faite : sur cette version, l'option ne suffit pas**, il
            # le vole quand meme. C'est `_rendre_le_focus` qui corrige
            # reellement le probleme ; l'option reste pour les versions ou elle
            # fonctionne, elle ne coute rien.
            "--focus-on=never",
            "--force-window=immediate",
            "--keep-open=yes",
            "--ontop=no",
            "--title=" + TITRE_INCRUSTE,
            # Barre de commandes maison, a la place de celle de mpv : voir
            # osc.lua. Celle de mpv, sur une fenetre sans bordure, ajoutait en
            # prime sa propre barre de titre et ses boutons de fenetre, qui
            # n'ont aucun sens une fois le lecteur incruste dans la page.
            "--osc=no",
            "--osd-bar=no",     # notre barre affiche deja la position
            "--script=" + str(core.APP_DIR / "osc.lua"),
            # -append pour ne pas ecraser le --script-opts qui pointe yt-dlp.
            # Une option par argument : --script-opts-append ne prend QU'UNE
            # paire cle=valeur, une liste separee par des virgules part
            # entierement dans la valeur de la premiere cle.
            # Un live arrive par un tube : sa qualite se regle du cote de
            # streamlink, pas de mpv, donc le menu correspondant est masque.
            "--script-opts-append=plume-live=" + ("yes" if live else "no"),
            # mpv est un autre processus : il ne lit pas notre configuration,
            # la langue doit donc voyager par la ligne de commande.
            "--script-opts-append=plume-langue=" + core.langue(),
            "--script-opts-append=plume-qualite=%d"
            % int(core.CONFIG.get("qualite_max", 1080)),
            "--script-opts-append=plume-fps=%d"
            % int(core.CONFIG.get("fps_max", 60)),
            # Sans cela, glisser la video deplace la fenetre de mpv, qui se
            # decolle de la page : le lecteur part tout seul sur le cote.
            "--input-builtin-dragging=no",
            "--window-dragging=no",
            "--input-default-bindings=yes",
            "--input-vo-keyboard=yes",
            "--input-ipc-server=" + self.tuyau,
            # Journal de mpv, ecrase a chaque lecture. Il coute peu et c'est
            # la seule facon de savoir pourquoi une lecture s'arrete : la
            # sortie d'erreur du processus, elle, n'etait pas capturee.
            "--log-file=" + str(core.JOURNAL_MPV),
            "--geometry=1x1+0+0",          # minuscule au depart : evite le flash
        ]
        return args

    def demarrer(self, url, titre=None, avec_cookies=False, depart=0.0):
        if not core.MPV:
            return {"ok": False, "erreur": "mpv introuvable"}
        if not self.parent:
            self.parent = fenetre_du_processus()
        if not self.parent:
            return {"ok": False, "erreur": "fenetre hote introuvable"}

        # Qui avait le premier plan juste avant ? mpv va le lui prendre, et
        # il faudra le lui rendre.
        try:
            self._devant_avant = user32.GetForegroundWindow()
        except Exception:
            self._devant_avant = None
        self.arreter()
        self._avec_cookies = avec_cookies
        self._titre = titre
        self._depart = max(0.0, float(depart or 0.0))
        self.tuyau = r"\\.\pipe\plume-mpv-%d-%d" % (os.getpid(),
                                                    next(_compteur))
        try:
            if core.est_live(url):
                self._lancer_live(url, titre)
            else:
                self._lancer_video(url, titre)
        except Exception as e:
            return {"ok": False, "erreur": str(e)}

        self.url = url
        self._visible = False
        self.plein_ecran = False
        self.fenetre = None
        threading.Thread(target=self._adopter, daemon=True).start()
        threading.Thread(target=self._suivre_plein_ecran, daemon=True).start()
        threading.Thread(target=self._surveiller_echec, daemon=True).start()
        return {"ok": True}

    def _surveiller_echec(self):
        """Un mpv qui meurt tout de suite n'a pas pu lire le flux.

        Le cas le plus frequent n'est pas une panne de l'application mais un
        refus de YouTube (« Sign in to confirm you're not a bot »). Sans ce
        signal, la page reste muette et l'utilisateur ne voit qu'une absence.
        """
        processus = self.mpv
        if processus is None:
            return
        debut = time.time()
        while True:
            time.sleep(0.4)
            if processus is not self.mpv:
                return                     # une autre lecture a pris la main
            code = processus.poll()
            if code is None:
                continue
            duree = time.time() - debut
            self._noter_arret(code, duree)
            if duree > 12:
                return          # arret tardif : deja note, pas de bandeau
            # Un echec rapide sans cookies vient souvent d'une video qui exige
            # la session : restriction d'age, ou controle anti-robot. On
            # rejoue une fois avec, plutot que d'abandonner.
            if (code != 0 and not self._avec_cookies
                    and core.CONFIG.get("cookies_navigateur")
                    and core.FICHIER_COOKIES.exists()
                    and core.FICHIER_COOKIES.stat().st_size > 2000):
                self.demarrer(self.url, self._titre, avec_cookies=True,
                              depart=self._depart)
                return
            if code != 0 and self.au_probleme:
                try:
                    connecte = (core.FICHIER_COOKIES.exists() and
                                core.FICHIER_COOKIES.stat().st_size > 2000)
                    if connecte:
                        message = (
                            "La lecture a echoue, avec et sans votre session. "
                            "YouTube a refuse le flux. Reessayer dans un "
                            "moment, ou verifier youtube_client dans "
                            "config.json.")
                    else:
                        message = (
                            "La lecture a echoue : YouTube exige d'etre "
                            "connecte. Connectez-vous a YouTube dans Plume "
                            "(bouton « Se connecter », en haut a droite de la "
                            "page), puis relancez la video. Une seule fois "
                            "suffit, la session est conservee.")
                    self.au_probleme(message)
                except Exception:
                    pass
            return

    def _noter_arret(self, code, duree):
        """Consigne l'arret du lecteur, avec ce que mpv en a dit.

        Un arret apres douze secondes ne declenche aucun bandeau et passait
        donc totalement inapercu : la video s'interrompait sans explication.
        """
        try:
            lignes = ["", "=" * 70,
                      time.strftime("%Y-%m-%d %H:%M:%S"),
                      "url        : %s" % self.url,
                      "code       : %s" % code,
                      "duree      : %.1f s" % duree]
            try:
                journal = core.JOURNAL_MPV.read_text(encoding="utf-8",
                                                     errors="replace")
                brutes = journal.splitlines()
                fautes = [l for l in brutes if "[e]" in l or "[w]" in l]
                if fautes:
                    lignes.append("erreurs de mpv :")
                    lignes += ["   " + l[:200] for l in fautes[-12:]]
                lignes.append("dernieres lignes du journal de mpv :")
                lignes += ["   " + l[:200] for l in brutes[-15:]]
            except Exception as e:
                lignes.append("journal de mpv illisible : %s" % e)
            core.JOURNAL_LECTEUR.parent.mkdir(parents=True, exist_ok=True)
            with open(core.JOURNAL_LECTEUR, "a", encoding="utf-8") as f:
                f.write("\n".join(lignes) + "\n")
        except Exception:
            pass

    @staticmethod
    def _sans_activation():
        """Demande a Windows que la premiere fenetre du fils s'ouvre en fond.

        Un processus herite du `wShowWindow` de son lanceur pour la premiere
        fenetre qu'il montre avec SW_SHOWDEFAULT. SW_SHOWNOACTIVATE la montre
        donc sans lui donner le premier plan. C'est le mecanisme du systeme :
        il ne depend pas du bon vouloir de mpv, contrairement a
        `--focus-on=never`, mesuree sans effet sur cette version.

        Ce n'est pas une garantie : un programme qui appelle lui-meme
        `SetForegroundWindow` passe outre. D'ou la reprise, qui reste.
        """
        infos = subprocess.STARTUPINFO()
        infos.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        infos.wShowWindow = 4          # SW_SHOWNOACTIVATE
        return infos

    def _lancer_video(self, url, titre):
        args = self._args_mpv(titre, False)
        if self._depart > 0:
            # `--start` au lancement d'un nouveau processus : sans effet sur
            # les lectures suivantes, contrairement a la propriete `start`
            # posee dans un mpv deja en marche.
            args.append("--start=%.1f" % self._depart)
        self.mpv = subprocess.Popen([core.MPV] + args + [url],
                                    startupinfo=self._sans_activation(),
                                    creationflags=core.CREATE_NO_WINDOW)

    def _lancer_live(self, url, titre):
        """Twitch et Kick : streamlink alimente mpv par un tube.

        On lance mpv nous-memes plutot que de laisser streamlink s'en charger
        (--player) : il faut connaitre le processus de mpv pour retrouver sa
        fenetre et l'incruster.
        """
        amont = subprocess.Popen(
            core.STREAMLINK_CMD + [
                "--stdout",
                "--twitch-low-latency",
                "--twitch-disable-ads",       # saute les segments publicitaires
                "--hls-live-edge", "2",
                "--stream-segment-threads", "2",
                "--retry-streams", "3",
                "--retry-max", "5",
                url, "best",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=core.CREATE_NO_WINDOW)
        args = [a for a in self._args_mpv(titre, True)
                if not a.startswith("--ytdl-format")]
        self.mpv = subprocess.Popen([core.MPV] + args + ["-"],
                                    stdin=amont.stdout,
                                    startupinfo=self._sans_activation(),
                                    creationflags=core.CREATE_NO_WINDOW)
        # le tube appartient desormais a mpv : le refermer ici pour que
        # streamlink recoive bien la fin de lecture quand mpv s'arrete
        amont.stdout.close()
        self.amont = amont

    # ------------------------------------------------------------------
    def _adopter(self):
        """Attend la fenetre de mpv, puis la rattache a la vue de navigation."""
        pid = self.mpv.pid if self.mpv else None
        if not pid:
            return
        for _ in range(160):                     # au plus 40 secondes
            if not self.en_cours():
                return
            candidates = [(s, h) for h, cls, s in _fenetres_du_processus(pid)
                          if cls.lower().startswith("mpv")
                          and not cls.lower().endswith("smtc")]
            if candidates:
                candidates.sort(reverse=True)
                hwnd = candidates[0][1]
                with self._verrou:
                    if not self.en_cours():
                        return
                    # la vue devient proprietaire : mpv flotte au-dessus d'elle,
                    # se minimise et se ferme avec elle
                    _set_long(hwnd, GWLP_HWNDPARENT, self.parent)
                    # Avant meme de la placer : chaque instant ou elle est
                    # activable est un instant ou elle peut voler le premier
                    # plan.
                    _interdire_activation(hwnd, not self.plein_ecran)
                    self.fenetre = hwnd
                if self._zone:
                    self.placer(*self._zone)
                self._rendre_le_focus()
                return
            time.sleep(0.25)

    def _rendre_le_focus(self):
        """Rend le premier plan a qui l'avait avant que mpv s'ouvre.

        mpv s'en empare en creant sa fenetre. **`--focus-on=never` n'y change
        rien sur cette version** : mesure faite, il le vole dans les deux cas.
        Plume, lui, ne l'active jamais (SWP_NOACTIVATE, SW_SHOWNOACTIVATE), il
        n'y avait donc rien a corriger de ce cote.

        Sans cela, une playlist qui relance un lecteur a chaque titre faisait
        passer la fenetre du navigateur derriere a chaque changement de video.

        Deux precautions : on ne reprend le premier plan que si c'est bien mpv
        qui l'a pris, et on le rend a la fenetre qui l'avait, pas a la notre.
        Si l'utilisateur est parti sur une autre application entre-temps, on ne
        la derange pas non plus.
        """
        precedent = self._devant_avant
        if not precedent:
            return
        # Si le premier plan appartenait a Plume, le rendre a la fenetre qui
        # porte le lecteur MAINTENANT, pas a celle qui l'avait avant : sortir
        # un onglet dans une nouvelle fenetre deplace le lecteur, et rendre le
        # focus a l'ancienne fenetre faisait passer la nouvelle derriere.
        try:
            proprietaire = wintypes.DWORD()
            user32.GetWindowThreadProcessId(precedent,
                                            ctypes.byref(proprietaire))
            if proprietaire.value == os.getpid() and self.parent:
                racine = user32.GetAncestor(self.parent, GA_ROOT)
                if racine:
                    precedent = racine
        except Exception:
            pass
        try:
            if not user32.IsWindow(precedent):
                return
        except Exception:
            return
        # On surveille pendant toute la duree du demarrage, au lieu de
        # rendre la main a la premiere correction. mpv prend le premier plan
        # en creant sa fenetre, puis parfois une seconde fois en chargeant le
        # fichier : la seconde fois n'etait jamais rattrapee, et la fenetre de
        # Plume restait devant. C'est ce qu'on voyait a chaque titre d'une
        # playlist.
        for _ in range(20):
            time.sleep(0.15)
            processus = self.mpv
            if processus is None or processus.poll() is not None:
                return
            try:
                devant = user32.GetForegroundWindow()
                if not devant:
                    continue
                proprio = wintypes.DWORD()
                user32.GetWindowThreadProcessId(devant,
                                                ctypes.byref(proprio))
                if proprio.value != processus.pid:
                    # Quelqu'un d'autre a la main : on n'y touche pas, et on
                    # retient qui c'est. Si mpv la lui prend juste apres, c'est
                    # a LUI qu'il faudra la rendre, pas a la fenetre notee au
                    # depart : sinon on arrache le focus a l'application ou
                    # l'utilisateur vient de passer.
                    precedent = devant
                    continue
                if not user32.IsWindow(precedent):
                    return
                if not user32.SetForegroundWindow(precedent):
                    # Refuse : nous ne tenons pas le premier plan et nous
                    # n'avons pas recu la derniere entree. Windows se contente
                    # alors de faire clignoter le bouton de la barre des
                    # taches. On remet au moins l'ordre d'affichage, ce qui ne
                    # demande aucun droit particulier : l'utilisateur retrouve
                    # sa fenetre devant, meme si le clavier reste ou il est.
                    user32.SetWindowPos(precedent, HWND_TOP, 0, 0, 0, 0,
                                        SWP_NOMOVE | SWP_NOSIZE
                                        | SWP_NOACTIVATE)
                    _trace("premier plan refuse, rang remis pour %s"
                           % precedent)
                else:
                    _trace("premier plan rendu a %s" % precedent)
            except Exception:
                pass

    # ------------------------------------------------------------------
    def _suivre_plein_ecran(self):
        """Ecoute mpv pour savoir quand il bascule en plein ecran.

        Sans cela, la boucle de suivi remettrait aussitot la fenetre sur la zone
        du lecteur et le plein ecran serait impossible a garder.
        """
        tube = None
        for _ in range(120):                     # le tube met un moment a exister
            if not self.en_cours():
                return
            try:
                tube = open(self.tuyau, "r+b", buffering=0)
                break
            except OSError:
                time.sleep(0.25)
        if not tube:
            return
        try:
            tube.write(b'{"command":["observe_property",1,"fullscreen"]}\n')
            tube.write(b'{"command":["observe_property",2,'
                       b'"user-data/plume/action"]}\n')
            while self.en_cours():
                ligne = tube.readline()
                if not ligne:
                    break
                try:
                    message = json.loads(ligne.decode("utf-8", "replace"))
                except ValueError:
                    continue
                if message.get("event") != "property-change":
                    continue
                if message.get("name") == "fullscreen":
                    self._basculer_plein_ecran(bool(message.get("data")))
                elif message.get("name") == "user-data/plume/action":
                    self._transmettre(message.get("data"))
        except OSError:
            pass
        finally:
            try:
                tube.close()
            except Exception:
                pass

    def _transmettre(self, brut):
        """Passe a Plume ce que la barre du lecteur demande a la page.

        Format : « numero:nom:valeur ». Le numero ne sert qu'a rendre la
        valeur differente a chaque fois, sans quoi demander deux fois la meme
        chose ne declencherait qu'une notification.
        """
        if not brut or not self.au_action:
            return
        morceaux = str(brut).split(":", 2)
        if len(morceaux) < 2:
            return
        try:
            self.au_action(morceaux[1], morceaux[2] if len(morceaux) > 2
                           else "")
        except Exception:
            pass

    def _basculer_plein_ecran(self, actif):
        self.plein_ecran = actif
        if not self.fenetre:
            return
        # En plein ecran, mpv doit recevoir Echap et f : c'est le seul moment
        # ou son activation est legitime.
        _interdire_activation(self.fenetre, not actif)
        if actif:
            # plus de decoupe ni de suivi : mpv occupe l'ecran comme il l'entend
            user32.SetWindowRgn(self.fenetre, None, True)
            self._decoupe = None
        elif self._zone:
            self.placer(*self._zone)

    # ------------------------------------------------------------------
    def placer(self, x, y, largeur, hauteur, bornes=None):
        """Positionne le lecteur, en coordonnees ECRAN.

        `bornes` delimite la surface ou le lecteur a le droit de s'afficher,
        elle aussi en coordonnees ecran : (gauche, haut, droite, bas). C'est la
        zone occupee par la page, barres d'onglets et d'adresse exclues, sans
        quoi une video recouvrirait l'interface du navigateur en defilant.
        """
        self._zone = (x, y, largeur, hauteur, bornes)
        if not self.fenetre or self.plein_ecran:
            return
        x, y, largeur, hauteur = int(x), int(y), int(largeur), int(hauteur)
        if largeur < 40 or hauteur < 30:
            return self.cacher()

        if bornes is None:
            if not self.parent:
                return self.cacher()
            vue = wintypes.RECT()
            user32.GetClientRect(self.parent, ctypes.byref(vue))
            coin = wintypes.POINT(0, 0)
            user32.ClientToScreen(self.parent, ctypes.byref(coin))
            bornes = (coin.x, coin.y, coin.x + vue.right, coin.y + vue.bottom)

        # La fenetre de mpv est de premier niveau : rien ne la rogne aux bords
        # de la page. On calcule donc la portion reellement visible et on y
        # decoupe la fenetre. Decouper plutot que redimensionner : mpv garde sa
        # taille, donc l'image n'est pas deformee, juste tronquee.
        bg, bh, bd, bb = bornes
        gauche = max(0, bg - x)
        haut = max(0, bh - y)
        droite = min(largeur, bd - x)
        bas = min(hauteur, bb - y)
        if droite <= gauche or bas <= haut:
            return self.cacher()

        user32.SetWindowPos(self.fenetre, HWND_TOP,
                            x, y, largeur, hauteur,
                            SWP_NOACTIVATE)

        decoupe = (gauche, haut, droite, bas)
        if decoupe != self._decoupe:
            self._decoupe = decoupe
            # SetWindowRgn s'approprie la region : ne pas la detruire ensuite
            region = gdi32.CreateRectRgn(gauche, haut, droite, bas)
            user32.SetWindowRgn(self.fenetre, region, True)

        if not self._visible:
            user32.ShowWindow(self.fenetre, SW_SHOWNOACTIVATE)
            self._visible = True
            _trace("montre en %d,%d (%dx%d)" % (x, y, largeur, hauteur))

    def cacher(self):
        if self.fenetre and self._visible and not self.plein_ecran:
            _trace("cache")
            user32.ShowWindow(self.fenetre, SW_HIDE)
            self._visible = False

    # ------------------------------------------------------------------
    def arreter(self):
        with self._verrou:
            for processus in (self.mpv, self.amont):
                if processus and processus.poll() is None:
                    try:
                        processus.terminate()
                    except Exception:
                        pass
            self.mpv = None
            self.amont = None
            self.fenetre = None
            self.url = None
            self.plein_ecran = False
            self._visible = False
            self._decoupe = None

    def en_cours(self):
        return bool(self.mpv and self.mpv.poll() is None)

    def detruire(self):
        self.arreter()
