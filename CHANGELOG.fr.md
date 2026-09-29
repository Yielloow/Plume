# Journal des versions

English: [CHANGELOG.md](CHANGELOG.md)

Les versions publiées se trouvent dans les
[Releases](https://github.com/Yielloow/Plume/releases). Le détail de chaque
changement, avec ses raisons, est dans les messages de commit.

## 1.0.22 (2026-09-29)

- Une section « Nouveautés » dans les paramètres, tirée du journal des
  versions, et un bandeau au premier lancement d'une nouvelle version.
- Les mots de passe enregistrés se listent et s'oublient un par un. Plume ne
  lit ni n'affiche jamais le mot de passe lui-même, seulement le site,
  l'identifiant et la date.
- Enregistrement des mots de passe et remplissage des formulaires, allumés :
  le moteur demande avant de retenir quoi que ce soit, et tout peut être
  effacé d'un coup.
- De quoi signaler un problème, et copier les informations utiles au
  signalement.
- Une page YouTube qui s'affiche vide se recharge d'elle-même.

## 1.0.21 (2026-09-28)

- Les pages de Plume se rafraîchissent : la page des paramètres restait dans
  l'ancienne langue, et l'accueil comme les paramètres gardaient l'ancienne
  palette après un changement de couleur.
- En sortant du plein écran d'une vidéo, la fenêtre revient sur l'écran où
  elle jouait, au lieu de sauter sur l'écran principal.

## 1.0.20 (2026-09-28)

- Une page vidéo laissée de côté longtemps repart toute seule : le lecteur est
  examiné au retour, et la page rechargée s'il ne répond plus.
- Le son des pages sort désormais du processus de WebView2, fils direct de
  Plume, pour qu'un partage d'application le capte.
- La version s'affiche en petit dans le coin de la page d'accueil et mène aux
  paramètres.

## 1.0.19 (2026-09-27)

- Le lecteur mpv prend la couleur du thème, au lancement et en cours de
  lecture.
- La couleur gagne la ligne de temps, le volume et les boutons survolés.

## 1.0.18 (2026-09-27)

- Une page de paramètres complète, en onglet : général, apparence, modules, à
  propos. Ctrl+virgule l'ouvre.
- Toute la palette se déduit d'une seule couleur : cinq thèmes, ou la vôtre.
  Les barres, l'ouverture dessinée, l'icône de la fenêtre et les pages de
  Plume suivent.
- Trois modules activables : YouTube sans publicité, lecteur Twitch de Plume,
  onglets en veille.
- Le fond de l'onglet actif glisse d'un onglet à l'autre.

## 1.0.17 (2026-09-27)

- L'onglet actif prend la couleur de la barre d'adresse et descend jusqu'à
  elle : les deux barres ne font plus qu'une surface. L'étincelle de Plume
  marque l'onglet regardé.

## 1.0.16 (2026-09-25)

- Le logotype de l'ouverture est centré sur son étincelle.
- La fermeture de la dernière fenêtre rejoue l'ouverture à l'envers.

## 1.0.15 (2026-09-25)

- Un lien ouvert depuis une autre application ramène Plume au premier plan.
- Le clic de la molette et Ctrl+clic ouvrent l'onglet derrière.
- La veille n'endort plus un onglet qui joue du son.
- Le glissement entre onglets est plus régulier.

## 1.0.14 (2026-09-22)

- Sur Twitch, le lecteur du site passe par défaut ; celui de Plume, sans
  publicité mais plus coûteux pour la carte graphique, reste à un clic.
- Les notifications apparaissent et disparaissent en douceur.
- Nouveau site.

## 1.0.13 (2026-09-22)

- Le plein écran d'une page couvre vraiment l'écran, bords de Windows
  compris.

## 1.0.12 (2026-09-21)

- Correction du démarrage : la 1.0.11 ne se lançait pas sur certaines
  machines.
- Un bouton « Vérifier les mises à jour » dans les paramètres.

## 1.0.11 (2026-09-21)

- YouTube garde son lecteur, et ses publicités sont retirées de la page.
- mpv est réservé aux lives Twitch, dont il saute les coupures.
- Revue complète de l'interface et des réglages.

## 1.0.10 (2026-09-20)

- Le lecteur ne se pose plus par-dessus l'onglet d'à côté quand on change vite
  d'onglet.

## 1.0.9 (2026-09-14)

- La bande claire en haut de la fenêtre, traitée à sa source.

## 1.0.8 (2026-09-14)

- Le trait blanc au bord de la fenêtre, et le lecteur qui débordait de sa
  zone.

## 1.0.7 (2026-09-13)

- Les groupes de travail portent leurs couleurs.

## 1.0.6 (2026-09-13)

- La mise à jour en un bouton, avec compte à rebours annulable.

## 1.0.5 (2026-09-13)

- C'est le shell de Windows qui dit quel navigateur ouvre les liens.

## 1.0.4 (2026-09-13)

- Le navigateur par défaut, constaté au bon endroit du registre.

## 1.0.3 (2026-09-13)

- L'annonce d'une mise à jour arrive après la page, pas avant.
- La configuration survit à une mise à jour.

## 1.0.2 (2026-09-13)

- Le volume est retenu d'une vidéo à l'autre.
- Icône dans la barre des tâches, documentation.

## 1.0.1 (2026-09-13)

- Deux langues, français et anglais.
- Plume peut devenir le navigateur par défaut.

## 1.0.0 (2026-09-13)

- Première version : onglets, favoris, groupes de travail, veille des
  onglets, lecteur vidéo incrusté, page d'accueil locale.
