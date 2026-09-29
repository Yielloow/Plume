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
        "bulle_lecteur_site": "Revenir au lecteur du site : moins de charge graphique, avec ses pubs",
        "bulle_lecteur_plume": "Lecteur de Plume : sans pub, mais plus de charge graphique",
        "lecteur_bulle_titre": "Des pubs ?",
        "lecteur_bulle_texte": "Avec le lecteur de Plume, vous n'en aurez pas. En contrepartie, la carte graphique travaille davantage.",
        "lecteur_bulle_bouton": "Essayer",
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
        "param_ouvrir": "Tous les paramètres",
        "param_titre": "Paramètres",
        "param_general": "Général",
        "param_apparence": "Apparence",
        "param_modules": "Modules",
        "param_apropos": "À propos",
        "param_nouveautes": "Nouveautés",
        "nouveautes_bandeau": "Plume %s est installée. Voir ce qui a changé ?",
        "nouveautes_bouton": "Les nouveautés",
        "param_nouveautes_aide": "Ce que les dernières versions ont changé. Plume se met à jour toute seule, autant savoir ce qui a bougé.",
        "nouveautes_absentes": "Le journal des versions est introuvable.",
        "param_intro_aide": "L'ouverture dessinée au lancement, et le repli de la fenêtre à la fermeture.",
        "param_note_maj": "Plume regarde une fois par jour si une version plus récente existe. Rien d'autre ne sort de votre machine.",
        "param_maj_aide": "Demande tout de suite, sans attendre la vérification du jour.",
        "param_maj_bouton": "Vérifier",
        "param_oubli": "Oublier la vérification du jour",
        "param_oubli_aide": "La prochaine ouverture cherchera de nouveau, comme si rien n'avait été vérifié aujourd'hui.",
        "param_oubli_bouton": "Oublier",
        "param_oubli_fait": "La vérification du jour est oubliée.",
        "param_theme": "Couleur de l'interface",
        "param_theme_aide": "Toute la palette se déduit de cette couleur : les barres, les onglets et le fond des pages de Plume en prennent une pointe.",
        "param_theme_libre": "Votre couleur",
        "param_teinte_violet": "Violet",
        "param_teinte_ocean": "Océan",
        "param_teinte_foret": "Forêt",
        "param_teinte_braise": "Braise",
        "param_teinte_ardoise": "Ardoise",
        "param_apercu_onglet": "Un onglet",
        "param_apercu_autre": "Un autre",
        "param_modules_aide": "Les modules sont livrés actifs : ce sont eux qui font Plume. Les couper ne désinstalle rien, et les rallumer suffit à les retrouver.",
        "param_ext_pub": "YouTube sans publicité",
        "param_ext_pub_aide": "Les publicités sont retirées de la page avant même que le lecteur ne les voie, et les requêtes publicitaires connues sont refusées.",
        "param_ext_twitch": "Lecteur Twitch de Plume",
        "param_ext_twitch_aide": "Les lives peuvent passer par mpv, sans coupure publicitaire, mais la carte graphique travaille davantage. Coupé, Twitch garde son lecteur.",
        "param_ext_veille": "Onglets en veille",
        "param_ext_veille_aide": "Les onglets que vous ne regardez pas rendent leur mémoire. Y revenir les retrouve intacts.",
        "param_qualite": "Qualité maximale des lives",
        "param_delai": "Délai avant la veille",
        "param_actif": "Actif",
        "param_inactif": "Inactif",
        "param_defaut": "Faire de Plume le navigateur par défaut",
        "param_defaut_aide": "Windows ouvre sa propre fenêtre de choix : Plume ne peut pas décider à votre place.",
        "param_defaut_bouton": "Ouvrir le réglage de Windows",
        "param_profil": "Dossier du profil",
        "param_mdp": "Enregistrer les mots de passe",
        "param_mdp_aide": "Plume propose de retenir un mot de passe et le remplit ensuite. Tout reste dans le dossier de profil, chiffré par Windows pour votre compte : rien ne part ailleurs, et il n'y a ni coffre ni synchronisation.",
        "param_formulaires": "Remplir les formulaires",
        "param_formulaires_aide": "Nom, adresse, courriel, proposés d'après ce que vous avez déjà saisi.",
        "param_mdp_oubli": "Oublier ce qui est enregistré",
        "param_comptes": "Mots de passe enregistrés",
        "param_comptes_aide": "Ce que le moteur a retenu. Plume ne lit ni n'affiche jamais le mot de passe lui-même, seulement où il sert.",
        "param_comptes_aucun": "Aucun mot de passe enregistré.",
        "param_compte_sans_nom": "sans identifiant",
        "param_compte_retirer": "Oublier cet identifiant",
        "param_compte_oublie": "Identifiant oublié.",
        "param_compte_differe": "Identifiant retiré au prochain démarrage de Plume : le moteur tient sa base ouverte.",
        "param_mdp_oubli_aide": "Efface les mots de passe retenus et les entrées de formulaire, sans retour possible.",
        "param_mdp_fait": "Mots de passe et formulaires oubliés.",
        "param_mdp_echec": "Impossible d'effacer ces données.",
        "param_bug": "Signaler un problème",
        "param_bug_aide": "Ouvre la page des signalements du dépôt. Dites ce que vous faisiez et ce qui s'est passé.",
        "param_bug_bouton": "Ouvrir",
        "param_infos": "Copier les informations",
        "param_infos_aide": "Version, système, moteur et modules, à coller dans votre signalement.",
        "param_infos_bouton": "Copier",
        "param_infos_fait": "Copié",
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
        "bulle_lecteur_site": "Back to the site's player: lighter on the graphics card, with its ads",
        "bulle_lecteur_plume": "Plume's player: no ads, but more load on the graphics card",
        "lecteur_bulle_titre": "Ads?",
        "lecteur_bulle_texte": "With Plume's player, you won't get any. In return, the graphics card works harder.",
        "lecteur_bulle_bouton": "Try it",
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
        "param_ouvrir": "All settings",
        "param_titre": "Settings",
        "param_general": "General",
        "param_apparence": "Appearance",
        "param_modules": "Modules",
        "param_apropos": "About",
        "param_nouveautes": "What's new",
        "nouveautes_bandeau": "Plume %s is installed. See what changed?",
        "nouveautes_bouton": "What's new",
        "param_nouveautes_aide": "What the last few versions changed. Plume updates itself, so you may as well know what moved.",
        "nouveautes_absentes": "The changelog could not be found.",
        "param_intro_aide": "The drawn opening at launch, and the window folding back when it closes.",
        "param_note_maj": "Plume checks once a day whether a newer version exists. Nothing else leaves your machine.",
        "param_maj_aide": "Ask right now, without waiting for today's check.",
        "param_maj_bouton": "Check",
        "param_oubli": "Forget today's check",
        "param_oubli_aide": "The next launch will look again, as if nothing had been checked today.",
        "param_oubli_bouton": "Forget",
        "param_oubli_fait": "Today's check has been forgotten.",
        "param_theme": "Interface colour",
        "param_theme_aide": "The whole palette follows from this colour: the bars, the tabs and the background of Plume's own pages all take a hint of it.",
        "param_theme_libre": "Your colour",
        "param_teinte_violet": "Violet",
        "param_teinte_ocean": "Ocean",
        "param_teinte_foret": "Forest",
        "param_teinte_braise": "Ember",
        "param_teinte_ardoise": "Slate",
        "param_apercu_onglet": "A tab",
        "param_apercu_autre": "Another",
        "param_modules_aide": "Modules ship switched on: they are what makes Plume. Switching one off uninstalls nothing, and switching it back on is all it takes.",
        "param_ext_pub": "YouTube without ads",
        "param_ext_pub_aide": "Ads are removed from the page before the player even sees them, and known ad requests are refused.",
        "param_ext_twitch": "Plume's Twitch player",
        "param_ext_twitch_aide": "Lives can go through mpv, with no ad breaks, but the graphics card works harder. Switched off, Twitch keeps its own player.",
        "param_ext_veille": "Sleeping tabs",
        "param_ext_veille_aide": "Tabs you are not looking at give their memory back. Coming back finds them intact.",
        "param_qualite": "Maximum live quality",
        "param_delai": "Delay before sleeping",
        "param_actif": "On",
        "param_inactif": "Off",
        "param_defaut": "Make Plume the default browser",
        "param_defaut_aide": "Windows opens its own chooser: Plume cannot decide for you.",
        "param_defaut_bouton": "Open the Windows setting",
        "param_profil": "Profile folder",
        "param_mdp": "Save passwords",
        "param_mdp_aide": "Plume offers to remember a password and fills it in later. Everything stays in the profile folder, encrypted by Windows for your account: nothing leaves, and there is no vault and no sync.",
        "param_formulaires": "Fill in forms",
        "param_formulaires_aide": "Name, address, email, suggested from what you have already typed.",
        "param_mdp_oubli": "Forget what is saved",
        "param_comptes": "Saved passwords",
        "param_comptes_aide": "What the engine has kept. Plume never reads or shows the password itself, only where it is used.",
        "param_comptes_aucun": "No saved passwords.",
        "param_compte_sans_nom": "no username",
        "param_compte_retirer": "Forget this login",
        "param_compte_oublie": "Login forgotten.",
        "param_compte_differe": "Login will be removed next time Plume starts: the engine is holding its database open.",
        "param_mdp_oubli_aide": "Erases saved passwords and form entries, with no way back.",
        "param_mdp_fait": "Passwords and form entries forgotten.",
        "param_mdp_echec": "Could not erase that data.",
        "param_bug": "Report a problem",
        "param_bug_aide": "Opens the repository's issues page. Say what you were doing and what happened.",
        "param_bug_bouton": "Open",
        "param_infos": "Copy the details",
        "param_infos_aide": "Version, system, engine and modules, to paste into your report.",
        "param_infos_bouton": "Copy",
        "param_infos_fait": "Copied",
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
