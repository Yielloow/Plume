# -*- coding: utf-8 -*-
"""Les textes de Plume, en francais et en anglais.

Un dictionnaire plat plutot qu'un systeme de traduction : deux langues, moins
de cinquante phrases, et aucune dependance a installer. `gettext` obligerait a
compiler des catalogues binaires et a les embarquer dans le paquet, pour un
resultat identique.

Les cles decrivent ce que la phrase FAIT, pas ce qu'elle dit : `groupe_plein`
reste juste meme si le jour ou on reformule la phrase.

Les phrases a trous gardent leurs marques dans le meme ordre dans les deux
langues. Quand l'ordre doit changer, on nomme les trous (`%(nom)s`) plutot que
de compter sur leur position.
"""

TEXTES = {
    "fr": {
        # --- bandeaux
        "telecharge": "Téléchargé : %s  (dans %s)",
        "telechargement_interrompu": "Téléchargement interrompu : %s",
        "aucun_favori": "Aucun favori pour l'instant : cliquez l'étoile "
                        "de la barre d'adresse pour en ajouter un.",
        "retire_de": "Retiré de « %s ».",
        "groupe_plein": "« %s » contient déjà %d onglets : c'est le maximum, "
                        "pour que les rouvrir reste tenable.",
        "ajoute_a": "Ajouté à « %s ».",
        "groupe_existe": "Un groupe « %s » existe déjà.",
        "groupe_supprime": "Groupe « %s » supprimé. Les onglets ouverts "
                           "restent ouverts.",
        "groupe_vide": "Le groupe « %s » ne contient encore aucune page : "
                       "faites un clic droit sur un onglet pour l'y ranger.",
        "groupe_ouvert": "« %s » : %d onglet%s ouvert%s.",
        "zoom": "Zoom %d %% sur %s",
        "trop_fenetres": "Plume n'ouvre pas plus de %d fenêtres : chaque "
                         "fenêtre coûte de la mémoire.",
        # --- menu du clic droit sur un onglet
        "menu_retirer_de": "Retirer de « %s »",
        "menu_ajouter_a": "Ajouter à « %s »",
        "menu_nouveau_groupe": "Nouveau groupe de travail...",
        "groupe_nouveau_titre": "Nouveau groupe de travail",
        "groupe_nouveau_aide": "Son nom, par exemple : dev",
        "titre_fenetre_privee": "Plume, fenêtre privée",
        "menu_fermer": "Fermer l'onglet",
        "menu_fermer_autres": "Fermer les autres onglets",
        # --- page d'accueil
        "accueil_recherche": "Rechercher, ou saisir une adresse",
        "accueil_groupes": "Groupes de travail",
        "accueil_supprimer_groupe": "Supprimer ce groupe",
        "accueil_changer_teinte": "Changer les couleurs du groupe",
        "accueil_teinte": "Choisir cette couleur",
        "accueil_valider_teintes": "Valider",
        "accueil_pubs": "%d requête%s publicitaire%s refusée%s depuis le "
                        "lancement",
        "accueil_defaut": "Faire de Plume le navigateur par défaut",
        "accueil_defaut_aide": "Windows ne laisse aucun programme se désigner "
                               "lui-même : le bouton ouvre la page des "
                               "Paramètres où vous pouvez le choisir.",
        "accueil_langue": "Langue",
        "accueil_aucun_favori": "Aucun favori pour l'instant : l'étoile, à "
                                "droite de la barre d'adresse, en ajoute un.",
        "accueil_aucun_groupe": "Aucun groupe de travail. Clic droit sur un "
                                "onglet pour en créer un : il rouvrira toutes "
                                "ses pages d'un seul geste.",
        "tache_fenetre": "Nouvelle fenêtre",
        "tache_privee": "Nouvelle fenêtre privée",
        "tache_onglet": "Nouvel onglet",
        "accueil_defaut_fait": "Plume est votre navigateur par défaut",
        "accueil_vie_privee": "Plume n'a pas de serveur : rien ne remonte "
                              "vers son auteur, il n'y a pas de compte ni de "
                              "synchronisation. Vos favoris, vos cookies et "
                              "cette page vivent dans un dossier de votre "
                              "disque.",
        # --- lecteur video
        "lecteur_auto": "Automatique",
        "lecteur_normale": "Normale",
        "lecteur_piste": "piste ",
        "lecteur_aucune_piste": "Aucune piste disponible",
        "lecteur_passage": "Passage en ",
        # --- infobulles de la barre d'adresse
        "bulle_reculer": "Reculer",
        "bulle_avancer": "Avancer",
        "bulle_recharger": "Recharger (F5)",
        "bulle_accueil": "Page d'accueil",
        "bulle_favori_ajouter": "Ajouter aux favoris",
        "bulle_favori_retirer": "Retirer des favoris",
        "bulle_lecteur_site": "Lire avec le lecteur du site",
        "bulle_lecteur_plume": "Lire avec le lecteur de Plume",
        "bulle_reglages": "Paramètres",
        # --- panneau des parametres
        "reglages_titre": "Paramètres",
        "reglages_moteur": "Moteur de recherche",
        "reglages_qualite": "Qualité des lives Twitch",
        "reglages_intro": "Animation d'ouverture",
        "reglages_glissement": "Glissement des onglets",
        "reglages_veille": "Veille des onglets",
        "reglages_jamais": "Jamais",
        "reglages_secondes": "%d s",
        "reglages_minutes": "%d min",
        # --- echecs de lecture
        "lecture_echec_flux": "La lecture a échoué, avec et sans votre "
                              "session : YouTube a refusé le flux.",
        "lecture_echec_connexion": "La lecture a échoué : YouTube exige "
                                   "d'être connecté. Connectez-vous à YouTube "
                                   "dans Plume (bouton « Se connecter », en "
                                   "haut à droite de la page), puis relancez "
                                   "la vidéo. Une seule fois suffit, la "
                                   "session est conservée.",
        "lecture_essayer_site": "Lire avec le lecteur du site",
        "lecture_echec_live": "La lecture du live a échoué dans le lecteur "
                              "de Plume.",
        # --- mises a jour
        "maj_disponible": "Plume %s est disponible.",
        "reglages_maj": "Vérifier les mises à jour",
        "maj_a_jour": "Plume est à jour (version %s).",
        "maj_verification_echouee": "La vérification des mises à jour a "
                                    "échoué. Vérifiez la connexion, puis "
                                    "réessayez (version actuelle : %s).",
        "maj_bouton": "Mettre à jour",
        "maj_telechargement": "Téléchargement de la mise à jour... %d %%",
        "maj_bientot": "Mise à jour dans %d secondes.",
        "maj_annuler": "Annuler",
        "maj_annulee": "Mise à jour annulée.",
        "maj_lancement": "Installation en cours, Plume va se rouvrir.",
        "maj_echec_reseau": "La mise à jour n'a pas pu être téléchargée. "
                            "Elle n'est peut-être pas encore en ligne : "
                            "réessayez plus tard.",
        "maj_echec_empreinte": "Le fichier reçu ne correspond pas à celui qui "
                               "a été publié. Rien n'a été installé, et il a "
                               "été effacé.",
        "maj_echec_manifeste": "L'annonce de mise à jour est illisible. Rien "
                               "n'a été installé.",
    },
    "en": {
        "telecharge": "Downloaded: %s  (in %s)",
        "telechargement_interrompu": "Download interrupted: %s",
        "aucun_favori": "No bookmarks yet: click the star in the address bar "
                        "to add one.",
        "retire_de": "Removed from “%s”.",
        "groupe_plein": "“%s” already holds %d tabs, which is the "
                        "maximum, so that reopening them stays manageable.",
        "ajoute_a": "Added to “%s”.",
        "groupe_existe": "A group named “%s” already exists.",
        "groupe_supprime": "Group “%s” deleted. Open tabs stay open.",
        "groupe_vide": "Group “%s” holds no page yet: right-click a "
                       "tab to file it there.",
        "groupe_ouvert": "“%s”: %d tab%s opened.",
        "zoom": "Zoom %d %% on %s",
        "trop_fenetres": "Plume opens at most %d windows: every window costs "
                         "memory.",
        "menu_retirer_de": "Remove from “%s”",
        "menu_ajouter_a": "Add to “%s”",
        "menu_nouveau_groupe": "New work group...",
        "groupe_nouveau_titre": "New work group",
        "groupe_nouveau_aide": "Its name, for example: dev",
        "titre_fenetre_privee": "Plume, private window",
        "menu_fermer": "Close tab",
        "menu_fermer_autres": "Close other tabs",
        "accueil_recherche": "Search, or type an address",
        "accueil_groupes": "Work groups",
        "accueil_supprimer_groupe": "Delete this group",
        "accueil_changer_teinte": "Change the group colours",
        "accueil_teinte": "Pick this colour",
        "accueil_valider_teintes": "Apply",
        "accueil_pubs": "%d advertising request%s refused since launch",
        "accueil_defaut": "Make Plume the default browser",
        "accueil_defaut_aide": "Windows lets no program appoint itself: this "
                               "button opens the Settings page where you can "
                               "choose it.",
        "accueil_langue": "Language",
        "accueil_aucun_favori": "No bookmarks yet: the star, on the right of "
                                "the address bar, adds one.",
        "accueil_aucun_groupe": "No work group yet. Right-click a tab to "
                                "create one: it will reopen all its pages in "
                                "one go.",
        "tache_fenetre": "New window",
        "tache_privee": "New private window",
        "tache_onglet": "New tab",
        "accueil_defaut_fait": "Plume is your default browser",
        "accueil_vie_privee": "Plume has no server: nothing goes back to its "
                              "author, there is no account and no sync. Your "
                              "bookmarks, your cookies and this page live in "
                              "a folder on your own disk.",
        "lecteur_auto": "Automatic",
        "lecteur_normale": "Normal",
        "lecteur_piste": "track ",
        "lecteur_aucune_piste": "No track available",
        "lecteur_passage": "Switching to ",
        "bulle_reculer": "Back",
        "bulle_avancer": "Forward",
        "bulle_recharger": "Reload (F5)",
        "bulle_accueil": "Home page",
        "bulle_favori_ajouter": "Add to bookmarks",
        "bulle_favori_retirer": "Remove from bookmarks",
        "bulle_lecteur_site": "Play with the site's player",
        "bulle_lecteur_plume": "Play with Plume's player",
        "bulle_reglages": "Settings",
        "reglages_titre": "Settings",
        "reglages_moteur": "Search engine",
        "reglages_qualite": "Twitch live quality",
        "reglages_intro": "Opening animation",
        "reglages_glissement": "Tab sliding",
        "reglages_veille": "Tab sleep",
        "reglages_jamais": "Never",
        "reglages_secondes": "%d s",
        "reglages_minutes": "%d min",
        "lecture_echec_flux": "Playback failed, with and without your "
                              "session: YouTube refused the stream.",
        "lecture_echec_connexion": "Playback failed: YouTube requires you to "
                                   "be signed in. Sign in to YouTube inside "
                                   "Plume (the Sign in button, top right of "
                                   "the page), then start the video again. "
                                   "Once is enough, the session is kept.",
        "lecture_essayer_site": "Play with the site's player",
        "lecture_echec_live": "The live stream failed in Plume's player.",
        "maj_disponible": "Plume %s is available.",
        "reglages_maj": "Check for updates",
        "maj_a_jour": "Plume is up to date (version %s).",
        "maj_verification_echouee": "The update check failed. Check the "
                                    "connection, then try again (current "
                                    "version: %s).",
        "maj_bouton": "Update",
        "maj_telechargement": "Downloading the update... %d %%",
        "maj_bientot": "Updating in %d seconds.",
        "maj_annuler": "Cancel",
        "maj_annulee": "Update cancelled.",
        "maj_lancement": "Installing, Plume will reopen.",
        "maj_echec_reseau": "The update could not be downloaded. It may not "
                            "be online yet: please try again later.",
        "maj_echec_empreinte": "The file received does not match the one that "
                               "was published. Nothing was installed, and it "
                               "has been deleted.",
        "maj_echec_manifeste": "The update announcement is unreadable. "
                               "Nothing was installed.",
    },
}

# Les marques de pluriel ne se posent pas au meme endroit d'une langue a
# l'autre : en francais elles suivent le nom ET l'adjectif, en anglais le nom
# seul. Chaque langue dit donc combien de marques elle attend et ou.
PLURIELS = {
    "accueil_pubs": {"fr": 3, "en": 1},
    "groupe_ouvert": {"fr": 2, "en": 1},
}


def cles_manquantes():
    """Cles presentes dans une langue et absentes de l'autre.

    Sert au test : une cle oubliee ne se voit pas a l'oeil, elle se voit le
    jour ou quelqu'un lit l'interface dans l'autre langue.
    """
    fr, en = set(TEXTES["fr"]), set(TEXTES["en"])
    return sorted(fr ^ en)
