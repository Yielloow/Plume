# Journal des versions / Changelog

Les versions publiées se trouvent dans les
[Releases](https://github.com/Yielloow/Plume/releases). Le détail de chaque
changement, avec ses raisons, est dans les messages de commit.

Released versions live in the
[Releases](https://github.com/Yielloow/Plume/releases). The reasoning behind
each change is in the commit messages.

## 1.0.20 (2026-09-28)

- Une page vidéo laissée de côté longtemps repart toute seule : le lecteur est
  examiné au retour, et la page rechargée s'il ne répond plus.
- Le son des pages sort désormais du processus de WebView2, fils direct de
  Plume, pour qu'un partage d'application le capte.
- La version s'affiche en petit dans le coin de la page d'accueil et mène aux
  paramètres.

*Forgotten video pages recover on their own; page audio now comes from
WebView2's own process so screen sharing picks it up; the version shows in the
corner of the home page.*

## 1.0.19 (2026-09-27)

- Le lecteur mpv prend la couleur du thème, au lancement et en cours de
  lecture.
- La couleur gagne la ligne de temps, le volume et les boutons survolés.

*The mpv player follows the chosen colour, at launch and while playing.*

## 1.0.18 (2026-09-27)

- Une page de paramètres complète, en onglet : général, apparence, modules, à
  propos. Ctrl+virgule l'ouvre.
- Toute la palette se déduit d'une seule couleur : cinq thèmes, ou la vôtre.
  Les barres, l'ouverture dessinée, l'icône de la fenêtre et les pages de
  Plume suivent.
- Trois modules activables : YouTube sans publicité, lecteur Twitch de Plume,
  onglets en veille.
- Le fond de l'onglet actif glisse d'un onglet à l'autre.

*A full settings page, a palette derived from a single colour, three
switchable modules, and a sliding active-tab background.*

## 1.0.17 (2026-09-27)

- L'onglet actif prend la couleur de la barre d'adresse et descend jusqu'à
  elle : les deux barres ne font plus qu'une surface. L'étincelle de Plume
  marque l'onglet regardé.

*The active tab now merges into the address bar, marked by Plume's spark.*

## 1.0.16 (2026-09-25)

- Le logotype de l'ouverture est centré sur son étincelle.
- La fermeture de la dernière fenêtre rejoue l'ouverture à l'envers.

*Centred logotype, and a closing animation that mirrors the opening.*

## 1.0.15 (2026-09-25)

- Un lien ouvert depuis une autre application ramène Plume au premier plan.
- Le clic de la molette et Ctrl+clic ouvrent l'onglet derrière.
- La veille n'endort plus un onglet qui joue du son.
- Le glissement entre onglets est plus régulier.

*Links raise Plume to the front, middle-click opens tabs in the background,
sleeping never cuts audio, and tab sliding is smoother.*

## 1.0.14 (2026-09-22)

- Sur Twitch, le lecteur du site passe par défaut ; celui de Plume, sans
  publicité mais plus coûteux pour la carte graphique, reste à un clic.
- Les notifications apparaissent et disparaissent en douceur.
- Nouveau site.

*Twitch keeps its own player by default, Plume's remains one click away.*

## 1.0.13 (2026-09-22)

- Le plein écran d'une page couvre vraiment l'écran, bords de Windows
  compris.

*Page fullscreen now covers the whole screen.*

## 1.0.12 (2026-09-21)

- Correction du démarrage : la 1.0.11 ne se lançait pas sur certaines
  machines.
- Un bouton « Vérifier les mises à jour » dans les paramètres.

*Startup fix, and a manual update check.*

## 1.0.11 (2026-09-21)

- YouTube garde son lecteur, et ses publicités sont retirées de la page.
- mpv est réservé aux lives Twitch, dont il saute les coupures.
- Revue complète de l'interface et des réglages.

*YouTube keeps its player, ad-free; mpv is reserved for Twitch lives.*

## 1.0.10 (2026-09-20)

- Le lecteur ne se pose plus par-dessus l'onglet d'à côté quand on change vite
  d'onglet.

*The player no longer lands on the neighbouring tab.*

## 1.0.9 (2026-09-14)

- La bande claire en haut de la fenêtre, traitée à sa source.

*The pale band at the top of the window, fixed at its source.*

## 1.0.8 (2026-09-14)

- Le trait blanc au bord de la fenêtre, et le lecteur qui débordait de sa
  zone.

*The white edge line, and the player spilling out of its area.*

## 1.0.7 (2026-09-13)

- Les groupes de travail portent leurs couleurs.

*Work groups carry their colours.*

## 1.0.6 (2026-09-13)

- La mise à jour en un bouton, avec compte à rebours annulable.

*One-click updates, with a countdown you can cancel.*

## 1.0.5 (2026-09-13)

- C'est le shell de Windows qui dit quel navigateur ouvre les liens.

*Windows itself says which browser opens links.*

## 1.0.4 (2026-09-13)

- Le navigateur par défaut, constaté au bon endroit du registre.

*Default browser state read from the right place.*

## 1.0.3 (2026-09-13)

- L'annonce d'une mise à jour arrive après la page, pas avant.
- La configuration survit à une mise à jour.

*Update notices arrive after the page, and settings survive an update.*

## 1.0.2 (2026-09-13)

- Le volume est retenu d'une vidéo à l'autre.
- Icône dans la barre des tâches, documentation.

*Volume is remembered, taskbar icon, documentation.*

## 1.0.1 (2026-09-13)

- Deux langues, français et anglais.
- Plume peut devenir le navigateur par défaut.

*Two languages, and Plume can become the default browser.*

## 1.0.0 (2026-09-13)

- Première version : onglets, favoris, groupes de travail, veille des
  onglets, lecteur vidéo incrusté, page d'accueil locale.

*First release.*
