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
        "telecharge": "Telecharge : %s  (dans %s)",
        "telechargement_interrompu": "Telechargement interrompu : %s",
        "aucun_favori": "Aucun favori pour l'instant : cliquez l'etoile "
                        "de la barre d'adresse pour en ajouter un.",
        "retire_de": "Retire de « %s ».",
        "groupe_plein": "« %s » contient deja %d onglets : c'est le maximum, "
                        "pour que les rouvrir reste tenable.",
        "ajoute_a": "Ajoute a « %s ».",
        "groupe_existe": "Un groupe « %s » existe deja.",
        "groupe_supprime": "Groupe « %s » supprime. Les onglets ouverts "
                           "restent ouverts.",
        "groupe_vide": "Le groupe « %s » ne contient encore aucune page : "
                       "faites un clic droit sur un onglet pour l'y ranger.",
        "groupe_ouvert": "« %s » : %d onglet%s ouvert%s.",
        "zoom": "Zoom %d %% sur %s",
        "trop_fenetres": "Plume n'ouvre pas plus de %d fenetres : chaque "
                         "fenetre coute de la memoire.",
        # --- menu du clic droit sur un onglet
        "menu_retirer_de": "Retirer de « %s »",
        "menu_ajouter_a": "Ajouter a « %s »",
        "menu_nouveau_groupe": "Nouveau groupe de travail...",
        "menu_fermer": "Fermer l'onglet",
        "menu_fermer_autres": "Fermer les autres onglets",
        # --- page d'accueil
        "accueil_recherche": "Rechercher, ou saisir une adresse",
        "accueil_groupes": "Groupes de travail",
        "accueil_supprimer_groupe": "Supprimer ce groupe",
        "accueil_changer_teinte": "Changer les couleurs du groupe",
        "accueil_teinte": "Choisir cette couleur",
        "accueil_valider_teintes": "Valider",
        "accueil_pubs": "%d requete%s publicitaire%s refusee%s depuis le "
                        "lancement",
        "accueil_defaut": "Faire de Plume le navigateur par defaut",
        "accueil_defaut_aide": "Windows ne laisse aucun programme se designer "
                               "lui-meme : le bouton ouvre la page des "
                               "Parametres ou vous pouvez le choisir.",
        "accueil_langue": "Langue",
        "tache_fenetre": "Nouvelle fenetre",
        "tache_privee": "Nouvelle fenetre privee",
        "tache_onglet": "Nouvel onglet",
        "accueil_defaut_fait": "Plume est votre navigateur par defaut",
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
        # --- mises a jour
        "maj_disponible": "Plume %s est disponible.",
        "maj_bouton": "Mettre a jour",
        "maj_telechargement": "Telechargement de la mise a jour... %d %%",
        "maj_bientot": "Mise a jour dans %d secondes.",
        "maj_annuler": "Annuler",
        "maj_annulee": "Mise a jour annulee.",
        "maj_lancement": "Installation en cours, Plume va se rouvrir.",
        "maj_echec": "La mise a jour n'a pas pu etre verifiee. Rien n'a ete "
                     "installe : passez par le site.",
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
        "groupe_ouvert": "“%s”: %d tab%s opened%s.",
        "zoom": "Zoom %d %% on %s",
        "trop_fenetres": "Plume opens at most %d windows: every window costs "
                         "memory.",
        "menu_retirer_de": "Remove from “%s”",
        "menu_ajouter_a": "Add to “%s”",
        "menu_nouveau_groupe": "New work group...",
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
        "maj_disponible": "Plume %s is available.",
        "maj_bouton": "Update",
        "maj_telechargement": "Downloading the update... %d %%",
        "maj_bientot": "Updating in %d seconds.",
        "maj_annuler": "Cancel",
        "maj_annulee": "Update cancelled.",
        "maj_lancement": "Installing, Plume will reopen.",
        "maj_echec": "The update could not be verified. Nothing was "
                     "installed: please use the website.",
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
