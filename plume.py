# -*- coding: utf-8 -*-
"""
Plume, navigateur et lecteur de bureau a empreinte memoire minimale.

L'interface est en tkinter (stdlib) : aucun moteur web n'est charge pour
l'afficher. Les videos et les streams partent vers mpv, qui decode en GPU.
Parcourir un site ouvre une vue separee et fermable.

Empreinte : ~35 Mo au repos, ~250 Mo en lecture.
"""
import ctypes
import io
import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import font as tkfont
from urllib.request import Request, urlopen

import core

# ---- palette ----
FOND = "#12131a"
FOND2 = "#191b25"
FOND3 = "#21242f"
SURVOL = "#262a38"
CHOISI = "#2b2350"
BORD = "#2c3040"
TEXTE = "#e6e8ef"
TEXTE2 = "#9aa0b4"
ACCENT = "#7c5cff"
ACCENT2 = "#2ee6a8"
DANGER = "#ff6b6b"

VIGNETTE = (168, 94)


try:
    # sinon la barre des taches affiche l'icone de Python
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Plume.Recherche")
except Exception:
    pass


class Plume(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Plume")
        self.geometry("1020x700")
        self.minsize(760, 480)
        self.configure(bg=FOND)
        self.state("zoomed")          # ouvre en plein ecran
        self._plein_ecran = False
        try:
            if core.ICONE.exists():
                self.iconbitmap(default=str(core.ICONE))
        except Exception:
            pass                      # une icone manquante ne doit rien bloquer

        self._images = []            # garde une reference : sinon tkinter les libere
        self._lignes = []            # (cadre, sous-widgets, video)
        self._selection = -1
        self._file = queue.Queue()
        self._occupe = False
        self._historique = []
        self._pos_historique = 0

        self._polices()
        self._construire_entete()
        self._construire_liste()
        self._construire_pied()
        self._raccourcis()

        self.after(80, self._vider_file)
        self.after(1200, self._maj_memoire)
        self.champ.focus_set()
        self._accueil()

    # ------------------------------------------------------------------
    def _polices(self):
        self.f_base = tkfont.Font(family="Segoe UI", size=10)
        self.f_titre = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        self.f_marque = tkfont.Font(family="Segoe UI", size=13, weight="bold")
        self.f_petit = tkfont.Font(family="Segoe UI", size=9)
        self.f_champ = tkfont.Font(family="Segoe UI", size=12)

    # ------------------------------------------------------------------
    def _construire_entete(self):
        tete = tk.Frame(self, bg=FOND2)
        tete.pack(fill="x", side="top")

        ligne1 = tk.Frame(tete, bg=FOND2)
        ligne1.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(ligne1, text="✦", bg=FOND2, fg=ACCENT,
                 font=tkfont.Font(family="Segoe UI", size=14)).pack(side="left")
        tk.Label(ligne1, text="Plume", bg=FOND2, fg=TEXTE,
                 font=self.f_marque).pack(side="left", padx=(8, 0))

        # acces direct aux sites, a droite
        for nom, url in (("Twitch", "https://www.twitch.tv/directory"),
                         ("YouTube", "https://www.youtube.com")):
            self._puce_site(ligne1, nom, url).pack(side="right", padx=(7, 0))
        tk.Label(ligne1, text="Parcourir", bg=FOND2, fg=TEXTE2,
                 font=self.f_petit).pack(side="right", padx=(0, 4))

        ligne2 = tk.Frame(tete, bg=FOND2)
        ligne2.pack(fill="x", padx=20, pady=(13, 0))

        self._cadre_champ = tk.Frame(ligne2, bg=BORD, padx=1, pady=1)
        self._cadre_champ.pack(side="left", fill="x", expand=True)
        self.champ = tk.Entry(self._cadre_champ, bg=FOND3, fg=TEXTE,
                              insertbackground=ACCENT, relief="flat",
                              font=self.f_champ, width=10)
        self.champ.pack(fill="x", ipady=9, ipadx=10)

        self._bouton(ligne2, "Chercher", self.chercher, principal=True).pack(
            side="left", padx=(9, 0))
        self._bouton(ligne2, "Google", self.vers_google).pack(side="left", padx=(6, 0))

        self.ligne_aide = tk.Frame(tete, bg=FOND2)
        self.ligne_aide.pack(fill="x", padx=20, pady=(9, 14))
        self.aide = tk.Label(self.ligne_aide, bg=FOND2, fg=TEXTE2, font=self.f_petit,
                             anchor="w")
        self.aide.pack(side="left")
        self._maj_aide()

    def _bouton(self, parent, texte, commande, principal=False):
        fond = ACCENT if principal else FOND3
        survol = "#6a4ce8" if principal else SURVOL
        b = tk.Label(parent, text=texte, bg=fond, fg=TEXTE, font=self.f_base,
                     padx=17, pady=10, cursor="hand2")
        b.bind("<Button-1>", lambda e: commande())
        b.bind("<Enter>", lambda e: b.configure(bg=survol))
        b.bind("<Leave>", lambda e: b.configure(bg=fond))
        return b

    def _puce_site(self, parent, nom, url):
        e = tk.Label(parent, text=nom, bg=FOND3, fg=ACCENT2, font=self.f_petit,
                     padx=11, pady=4, cursor="hand2")
        e.bind("<Button-1>", lambda ev: self.ouvrir_navigation(url))
        e.bind("<Enter>", lambda ev: e.configure(bg=SURVOL))
        e.bind("<Leave>", lambda ev: e.configure(bg=FOND3))
        return e

    def _maj_aide(self, texte=None):
        self.aide.configure(
            text=texte or "Entrée : chercher des vidéos   ·   ↑ ↓ : parcourir   ·   "
                          "Entrée sur un résultat : ouvrir la page   ·   Échap : effacer")

    # ------------------------------------------------------------------
    def _construire_liste(self):
        conteneur = tk.Frame(self, bg=FOND)
        conteneur.pack(fill="both", expand=True)

        self.toile = tk.Canvas(conteneur, bg=FOND, highlightthickness=0, bd=0)
        self.toile.pack(side="left", fill="both", expand=True)

        self.barre = tk.Scrollbar(conteneur, orient="vertical", command=self.toile.yview,
                                  bg=FOND2, troughcolor=FOND, bd=0, relief="flat",
                                  activebackground=ACCENT, width=11)
        self.barre.pack(side="right", fill="y")
        self.toile.configure(yscrollcommand=self.barre.set)

        self.interieur = tk.Frame(self.toile, bg=FOND)
        self._fen = self.toile.create_window((0, 0), window=self.interieur, anchor="nw")
        self.interieur.bind("<Configure>",
                            lambda e: self.toile.configure(scrollregion=self.toile.bbox("all")))
        self.toile.bind("<Configure>",
                        lambda e: self.toile.itemconfigure(self._fen, width=e.width))
        self.bind_all("<MouseWheel>",
                      lambda e: self.toile.yview_scroll(int(-e.delta / 120), "units"))

    # ------------------------------------------------------------------
    def _construire_pied(self):
        pied = tk.Frame(self, bg=FOND2)
        pied.pack(fill="x", side="bottom")

        outils = core.etat_outils()
        ok = outils["mpv_ok"]
        tk.Label(pied, text="●", bg=FOND2, fg=ACCENT2 if ok else DANGER,
                 font=self.f_petit).pack(side="left", padx=(20, 5), pady=7)
        self.lbl_etat = tk.Label(
            pied, bg=FOND2, fg=TEXTE2, font=self.f_petit,
            text="Prêt" if ok else "mpv introuvable, la lecture ne marchera pas")
        self.lbl_etat.pack(side="left")

        self.lbl_ram = tk.Label(pied, text="", bg=FOND2, fg=ACCENT2, font=self.f_petit)
        self.lbl_ram.pack(side="right", padx=20)

    # ------------------------------------------------------------------
    def _raccourcis(self):
        self.champ.bind("<Return>", lambda e: self._entree())
        self.champ.bind("<Down>", lambda e: self._deplacer(1) or "break")
        self.champ.bind("<Up>", lambda e: self._deplacer(-1) or "break")
        self.champ.bind("<KeyRelease>", self._frappe)
        self.champ.bind("<FocusIn>", lambda e: self._cadre_champ.configure(bg=ACCENT))
        self.champ.bind("<FocusOut>", lambda e: self._cadre_champ.configure(bg=BORD))

        self.bind("<Escape>", lambda e: self._echap())
        self.bind("<Control-l>", lambda e: self._focus_champ() or "break")
        self.bind("<Control-q>", lambda e: self.destroy())
        self.bind("<Control-Up>", lambda e: self._rappeler(-1) or "break")
        self.bind("<Control-Down>", lambda e: self._rappeler(1) or "break")
        self.bind("<F5>", lambda e: self._relancer())
        self.bind("<F11>", lambda e: self._basculer_plein_ecran())

    def _basculer_plein_ecran(self):
        self._plein_ecran = not self._plein_ecran
        self.attributes("-fullscreen", self._plein_ecran)
        if not self._plein_ecran:
            self.state("zoomed")

    def _focus_champ(self):
        self.champ.focus_set()
        self.champ.select_range(0, "end")

    def _echap(self):
        if self._selection >= 0:
            self._choisir(-1)
            self._focus_champ()
        else:
            self.champ.delete(0, "end")
            self._accueil()

    def _frappe(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape"):
            return
        if self._selection >= 0:
            self._choisir(-1)

    def _rappeler(self, sens):
        """Ctrl + flèches : rappelle les recherches précédentes."""
        if not self._historique:
            return
        self._pos_historique = max(0, min(len(self._historique),
                                          self._pos_historique + sens))
        self.champ.delete(0, "end")
        if self._pos_historique < len(self._historique):
            self.champ.insert(0, self._historique[self._pos_historique])

    def _relancer(self):
        if self._historique:
            self.chercher(self._historique[-1])

    # ------------------------------------------------------------------
    # Actions principales
    # ------------------------------------------------------------------
    def _entree(self):
        """Entrée : lit le résultat sélectionné, sinon lance la recherche."""
        if self._selection >= 0:
            return self._lire(self._lignes[self._selection][2])
        self.chercher()

    def chercher(self, texte=None):
        """Action par défaut : chercher des vidéos, sans préfixe à retenir."""
        texte = (texte if texte is not None else self.champ.get()).strip()
        if not texte or self._occupe:
            return

        # une URL vidéo collée part directement dans mpv
        if core.est_url(texte):
            url = core.normaliser_url(texte)
            if core.est_video(url):
                return self._lire({"url": url, "titre": None})
            return self.ouvrir_navigation(url)

        self._occupe = True
        if texte not in self._historique:
            self._historique.append(texte)
        self._pos_historique = len(self._historique)
        self._info("Recherche de « %s »" % texte, "Interrogation de YouTube")
        threading.Thread(
            target=lambda: self._file.put(("resultats", core.chercher_youtube(texte))),
            daemon=True).start()

    def vers_google(self):
        texte = self.champ.get().strip()
        if not texte:
            return self.ouvrir_navigation("https://www.google.com")
        if core.est_url(texte):
            return self.ouvrir_navigation(core.normaliser_url(texte))
        self.ouvrir_navigation(core.url_recherche_web(texte))

    def ouvrir_navigation(self, url):
        r = core.ouvrir_navigation(url)
        if not r["ok"]:
            return self._info("Ouverture impossible", r["erreur"], erreur=True)
        if r.get("onglet"):
            self._flash("Ouvert dans un nouvel onglet")
        else:
            self._info(
                "Navigateur ouvert",
                "Une seule fenêtre, à onglets. Les vidéos y sont jouées par mpv,\n"
                "à la place du lecteur du site. La fermer rend toute sa mémoire ;\n"
                "Plume reste à 35 Mo.")

    def _lire(self, video):
        """Ouvre la page du site : on garde titre, description et recommandations,
        et mpv vient s'incruster a la place du lecteur."""
        url = video.get("url")
        if url:
            self.ouvrir_navigation(url)

    def _lire_seul(self, video):
        """Lecture dans une fenetre mpv nue : le mode le plus econome."""
        url = video.get("url")
        if not url:
            return
        r = core.lire(url, video.get("titre"))
        if r["ok"]:
            self._flash("Lecture lancée dans mpv")
        else:
            self._info("Lecture impossible", r["erreur"], erreur=True)

    def _flash(self, texte):
        self.lbl_etat.configure(text=texte, fg=ACCENT2)
        self.after(2600, lambda: self.lbl_etat.configure(text="Prêt", fg=TEXTE2))

    # ------------------------------------------------------------------
    # Affichage
    # ------------------------------------------------------------------
    def _nettoyer(self):
        for w in self.interieur.winfo_children():
            w.destroy()
        self._images.clear()
        self._lignes.clear()
        self._selection = -1
        self.toile.yview_moveto(0)

    def _info(self, titre, detail="", erreur=False):
        self._nettoyer()
        boite = tk.Frame(self.interieur, bg=FOND)
        boite.pack(pady=64)
        tk.Label(boite, text=titre, bg=FOND, fg=DANGER if erreur else TEXTE,
                 font=self.f_titre, wraplength=640, justify="center").pack()
        if detail:
            tk.Label(boite, text=detail, bg=FOND, fg=TEXTE2, font=self.f_petit,
                     wraplength=640, justify="center").pack(pady=(9, 0))

    def _accueil(self):
        self._nettoyer()
        boite = tk.Frame(self.interieur, bg=FOND)
        boite.pack(pady=56)
        tk.Label(boite, text="✦", bg=FOND, fg=ACCENT,
                 font=tkfont.Font(family="Segoe UI", size=30)).pack()
        tk.Label(boite, text="Tape ce que tu veux regarder", bg=FOND, fg=TEXTE,
                 font=self.f_titre).pack(pady=(14, 0))
        tk.Label(boite, bg=FOND, fg=TEXTE2, font=self.f_petit, justify="center",
                 text="Les vidéos s'ouvrent dans mpv, qui décode en GPU.\n"
                      "Environ dix fois moins de mémoire qu'un onglet de navigateur.").pack(
            pady=(8, 0))

        exemples = tk.Frame(boite, bg=FOND)
        exemples.pack(pady=(22, 0))
        for libelle, action in (
                ("Parcourir YouTube", lambda: self.ouvrir_navigation("https://www.youtube.com")),
                ("Parcourir Twitch", lambda: self.ouvrir_navigation("https://www.twitch.tv/directory")),
        ):
            b = tk.Label(exemples, text=libelle, bg=FOND3, fg=TEXTE, font=self.f_petit,
                         padx=14, pady=7, cursor="hand2")
            b.bind("<Button-1>", lambda e, a=action: a())
            b.bind("<Enter>", lambda e, w=b: w.configure(bg=SURVOL))
            b.bind("<Leave>", lambda e, w=b: w.configure(bg=FOND3))
            b.pack(side="left", padx=5)

    def _afficher(self, r):
        self._occupe = False
        if not r["ok"]:
            return self._info("Recherche impossible", r["erreur"], erreur=True)
        if not r["resultats"]:
            return self._info("Aucun résultat", "Essaie d'autres mots.")

        self._nettoyer()
        tk.Frame(self.interieur, bg=FOND, height=8).pack()
        for v in r["resultats"]:
            lbl = self._ligne(v)
            if core.CONFIG.get("miniatures", True) and v["miniature"]:
                self._miniature(v["miniature"], lbl)
        tk.Frame(self.interieur, bg=FOND, height=16).pack()
        self._maj_aide("%d résultats   ·   ↑ ↓ pour parcourir   ·   Entrée pour ouvrir "
                       "la page   ·   clic droit pour les autres options"
                       % len(r["resultats"]))

    def _ligne(self, video):
        i = len(self._lignes)
        cadre = tk.Frame(self.interieur, bg=FOND2, cursor="hand2",
                         highlightbackground=BORD, highlightthickness=1)
        cadre.pack(fill="x", padx=20, pady=4)

        vign = tk.Frame(cadre, bg="#0d0e14", width=VIGNETTE[0], height=VIGNETTE[1])
        vign.pack(side="left", padx=11, pady=11)
        vign.pack_propagate(False)
        img = tk.Label(vign, bg="#0d0e14", text="▶", fg=BORD,
                       font=tkfont.Font(family="Segoe UI", size=17))
        img.pack(expand=True)

        infos = tk.Frame(cadre, bg=FOND2)
        infos.pack(side="left", fill="both", expand=True, pady=11, padx=(3, 14))
        t = tk.Label(infos, text=video["titre"], bg=FOND2, fg=TEXTE, font=self.f_titre,
                     anchor="w", justify="left", wraplength=580)
        t.pack(fill="x")
        meta = "   ·   ".join([m for m in (video["chaine"], video["duree"],
                                           video["vues"]) if m])
        m = tk.Label(infos, text=meta, bg=FOND2, fg=TEXTE2, font=self.f_petit, anchor="w")
        m.pack(fill="x", pady=(6, 0))

        widgets = (cadre, infos, t, m)
        for w in widgets + (vign, img):
            w.bind("<Button-1>", lambda e, k=i: self._clic(k))
            w.bind("<Button-3>", lambda e, k=i: self._menu(e, k))
            w.bind("<Enter>", lambda e, k=i: self._survol(k, True))
            w.bind("<Leave>", lambda e, k=i: self._survol(k, False))

        self._lignes.append((cadre, widgets, video))
        return img

    def _peindre(self, i, couleur, bordure):
        cadre, widgets, _ = self._lignes[i]
        cadre.configure(bg=couleur, highlightbackground=bordure)
        for w in widgets[1:]:
            w.configure(bg=couleur)

    def _survol(self, i, entre):
        if i == self._selection:
            return
        self._peindre(i, SURVOL if entre else FOND2, ACCENT if entre else BORD)

    def _choisir(self, i):
        if 0 <= self._selection < len(self._lignes):
            self._peindre(self._selection, FOND2, BORD)
        self._selection = i
        if 0 <= i < len(self._lignes):
            self._peindre(i, CHOISI, ACCENT)
            self._montrer(i)

    def _montrer(self, i):
        """Fait défiler pour que la ligne choisie reste visible."""
        cadre = self._lignes[i][0]
        self.update_idletasks()
        haut = cadre.winfo_y()
        bas = haut + cadre.winfo_height()
        total = max(self.interieur.winfo_height(), 1)
        vue_haut = self.toile.canvasy(0)
        vue_bas = vue_haut + self.toile.winfo_height()
        if haut < vue_haut:
            self.toile.yview_moveto(max(0.0, (haut - 10) / total))
        elif bas > vue_bas:
            self.toile.yview_moveto(max(0.0, (bas - self.toile.winfo_height() + 10) / total))

    def _deplacer(self, pas):
        if not self._lignes:
            return
        self._choisir(max(0, min(len(self._lignes) - 1, self._selection + pas)))

    def _clic(self, i):
        self._choisir(i)
        self._lire(self._lignes[i][2])

    def _menu(self, event, i):
        video = self._lignes[i][2]
        menu = tk.Menu(self, tearoff=0, bg=FOND3, fg=TEXTE, font=self.f_petit,
                       activebackground=ACCENT, activeforeground=TEXTE, bd=0)
        menu.add_command(label="Ouvrir la page (avec recommandations)",
                         command=lambda: self._lire(video))
        menu.add_command(label="Lire dans mpv seul (le plus léger)",
                         command=lambda: self._lire_seul(video))
        menu.add_separator()
        menu.add_command(label="Copier le lien",
                         command=lambda: self._copier(video["url"]))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copier(self, texte):
        self.clipboard_clear()
        self.clipboard_append(texte)
        self._flash("Lien copié")

    # ------------------------------------------------------------------
    # Threads vers interface
    # ------------------------------------------------------------------
    def _vider_file(self):
        try:
            while True:
                genre, charge = self._file.get_nowait()
                if genre == "resultats":
                    self._afficher(charge)
                elif genre == "miniature":
                    self._poser(*charge)
        except queue.Empty:
            pass
        self.after(80, self._vider_file)

    def _miniature(self, url, lbl):
        def travail():
            try:
                req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urlopen(req, timeout=10) as rep:
                    self._file.put(("miniature", (rep.read(), lbl)))
            except Exception:
                pass
        threading.Thread(target=travail, daemon=True).start()

    def _poser(self, donnees, lbl):
        if not lbl.winfo_exists():
            return
        try:
            from PIL import Image, ImageTk
            im = Image.open(io.BytesIO(donnees))
            im.thumbnail(VIGNETTE, Image.LANCZOS)
            photo = ImageTk.PhotoImage(im)
            self._images.append(photo)   # sinon le ramasse-miettes l'efface
            lbl.configure(image=photo, text="")
        except Exception:
            pass

    def _maj_memoire(self):
        mo = core.memoire_mo()
        if mo:
            self.lbl_ram.configure(text="%d Mo" % mo)
        self.after(5000, self._maj_memoire)


if __name__ == "__main__":
    Plume().mainloop()
