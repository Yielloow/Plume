# Plume

Navigateur / lecteur de bureau à empreinte mémoire minimale.

## Pourquoi

Un onglet YouTube dans un navigateur coûte 0,6 à 2 Go de RAM : moteur JS, DOM,
compositeur, extensions, un process par onglet. Pour *regarder une vidéo*,
tout cela est du gaspillage.

Plume sépare les deux métiers :

| Tâche | Qui la fait | Coût |
|---|---|---|
| Interface, recherche, résultats | tkinter (stdlib Python), **aucun moteur web** | ~35 Mo |
| Lecture vidéo / stream | mpv, décodage GPU, sans DOM ni JS | ~200 Mo |
| Parcourir un site (YouTube, Twitch…) | navigateur à onglets, **processus séparé et fermable** | ~390 Mo par onglet |

Plume s'ouvre en plein écran. `F11` bascule en plein écran sans bordure.

## Le navigateur : une fenêtre, des onglets

Google est la page de départ. La fenêtre a une barre d'onglets et une barre
d'adresse, et **tout y reste** : une demande venue de Plume devient un onglet,
un lien qui voudrait ouvrir une fenêtre devient un onglet.

Chaque onglet possède son **propre contrôle WebView2**. Basculer ne recharge
donc rien : les pages restent vivantes, les vidéos continuent, le défilement et
les formulaires sont conservés. C'est ce qui distingue de vrais onglets d'une
simple liste d'adresses.

### Sur une page vidéo

1. le lecteur du site est **muselé avant même de démarrer** : le script est
   injecté par `AddScriptToExecuteOnDocumentCreated`, donc il s'exécute avant le
   code de la page, et `play()` est neutralisé d'entrée ;
2. **mpv vient se placer exactement à l'emplacement du lecteur**, et suit la
   zone quand on fait défiler ou qu'on redimensionne ;
3. tout le reste de la page est intact : titre, description, commentaires,
   **recommandations**, chat Twitch.

C'est là que se trouve l'essentiel du gain. Afficher le fil de YouTube coûte
cher, mais c'est le *lecteur vidéo* de la page (décodage logiciel, buffers,
compositeur) qui est le vrai gouffre. Il ne démarre jamais.

La fenêtre de mpv étant de premier niveau, rien ne la rogne aux bords de la
page : elle est **découpée** (`SetWindowRgn`) sur la portion visible, et masquée
dès que le lecteur sort de l'écran. Comme les barres d'onglets et d'adresse
occupent le haut, la zone reçue de la page est traduite en coordonnées écran à
partir du panneau de contenu, pas de la fenêtre.

Pages reconnues comme pages vidéo :

- YouTube : `/watch?v=`, `/shorts/`, `/live/`, `youtu.be/`
- Twitch : les pages de chaîne. Les pages du site (`/directory`, `/settings`,
  `/following`…) sont explicitement exclues pour éviter les faux positifs
- Vimeo, Dailymotion, Kick

### Lives : streamlink plutôt que yt-dlp

Twitch et Kick passent par **streamlink**, qui alimente mpv par un tube
(`--stdout` côté streamlink, `-` côté mpv). On lance mpv soi-même plutôt que de
laisser streamlink s'en charger avec `--player` : il faut connaître le processus
de mpv pour retrouver sa fenêtre et l'incruster.

Le gain est net : un live démarre en **6 secondes au lieu d'environ 40** avec le
greffon yt-dlp, et streamlink ne coûte que 4 Mo.

### Plein écran

`f` ou double-clic sur la vidéo. Ça paraît trivial, ça ne l'est pas : la boucle
qui colle mpv sur la zone du lecteur tourne toutes les 120 ms et **écrasait le
plein écran aussitôt**. mpv est donc lancé avec `--input-ipc-server`, et un fil
écoute sa propriété `fullscreen` pour suspendre le suivi.

### Session persistante

Les cookies et sessions sont conservés dans `profil/`, à côté du projet (pas sur
`C:`, dont l'espace est compté). **On reste connecté à YouTube, Twitch et au
reste d'un lancement à l'autre.**

Pour repartir d'une session vierge, supprimer le dossier `profil/`.

### Pourquoi WinForms et pythonnet plutôt que pywebview

pywebview ne connaît qu'une page par fenêtre : impossible d'y bâtir des onglets
sans recharger à chaque bascule. Le navigateur pilote donc WebView2 directement,
via les assemblages déjà fournis avec pywebview et pythonnet.

Deux pièges à connaître :

- WinForms et WebView2 exigent un fil COM en **STA**, que Python n'a pas par
  défaut. La boucle tourne dans un fil .NET dont on fixe l'appartement, sinon
  WebView2 lève `RPC_E_CHANGED_MODE` ;
- en héritant d'une classe .NET, il faut appeler `super().__init__()`, faute de
  quoi .NET lève une `NullReferenceException` au premier accès.

### Fenêtre sans barre de titre

La barre de titre de Windows est supprimée (`FormBorderStyle = None`) et les
boutons réduire / agrandir / fermer sont dessinés à droite de la barre
d'onglets, comme dans les navigateurs. Ce qu'il a fallu réimplémenter, puisque
la barre système le fournissait :

- **déplacer la fenêtre** : géré par nous, voir la section suivante ;
- **redimensionner** : `WM_NCHITTEST` déclare les 6 px de bordure comme
  poignées, Windows fait le reste ;
- **agrandir sans recouvrir la barre des tâches** : voir plus bas, la fenêtre
  reste à l'état `Normal` et se dimensionne elle-même sur la zone de travail ;
- double-clic sur la barre pour agrandir ou restaurer.

### Déplacer la fenêtre, et l'accrocher aux bords

Le déplacement était délégué à Windows par `WM_NCLBUTTONDOWN`. Cela ne pouvait
pas marcher ici : **Windows ignore que la fenêtre est agrandie**, puisque nous
posons nous-mêmes ses dimensions et que son état reste `Normal`. Il ne la
restaurait donc pas quand on la tirait vers le bas, et son propre accrochage
aurait remis `WindowState.Maximized`, dont les coordonnées figées font
disparaître la fenêtre sur un second écran.

Le déplacement est donc à nous, dans `appui_onglets`, `_glisser` et
`relache_onglets` :

- au-delà de 8 px de mouvement, une fenêtre agrandie ou collée **retrouve sa
  taille normale**, positionnée pour que le curseur reste au même endroit
  relatif sur la barre. Sans ce calcul, elle rétrécirait par son coin haut
  gauche et filerait sous le curseur ;
- pendant le déplacement, on regarde où est le **curseur**, pas la fenêtre :
  c'est l'écran sous le curseur qui décide, ce qui rend le passage d'un écran
  à l'autre naturel ;
- au relâchement, à moins de 8 px du bord haut la fenêtre se recolle en plein
  écran ; à gauche ou à droite, elle prend la moitié de l'écran.

Mesuré dans une vraie fenêtre : agrandie en 2560x1392, tirée vers le bas elle
revient à 1440x900 avec le curseur toujours dessus, puis remontée au bord haut
et relâchée elle reprend exactement 2560x1392.

### Barre des taches : epingler Plume, pas Python

`Plume.exe` n'est qu'un lanceur, le processus reel est `pythonw.exe`. Appeler
`SetCurrentProcessExplicitAppUserModelID` suffit pour l'icone de la **fenetre**,
mais pas pour l'**epinglage** : Windows creait un raccourci vers Python, avec son
icone et son nom.

La correction tient dans trois proprietes posees sur la fenetre elle-meme, dans
`barre_taches.py` : relancer par cette commande, sous ce nom, avec cette icone.
Windows s'en sert au moment de fabriquer le raccourci epingle.

Le meme fichier pose le menu « Taches » du clic droit sur l'icone, avec
« Nouvelle fenetre » et « Nouvel onglet ». La premiere passe l'argument
`--nouvelle-fenetre`, transmis par le canal local a l'instance en cours.

Tout est ecrit en COM par ctypes : ni pywin32 ni comtypes ne sont installes, et
les embarquer pour quelques appels serait disproportionne. Deux pieges rencontres
en chemin :

- **`InitPropVariantFromString` n'est pas exportee** par `propsys.dll`, c'est une
  fonction en ligne de l'en-tete. Il faut construire le PROPVARIANT soi-meme :
  type `VT_LPWSTR`, et une chaine allouee par `CoTaskMemAlloc` pour que
  `PropVariantClear` puisse la liberer ;
- **`PropVariantClear` vit dans `ole32`**, pas dans `propsys`.

> Un raccourci deja epingle garde l'ancienne icone : il faut le detacher puis le
> reepingler une fois.

### L'ouverture : un chargement deguise

Au lancement, une page a elle : l'etincelle a quatre branches eclot, le nom
s'ecrit lettre a lettre, un trait d'accent file **sous les jambages** jusqu'au
point violet, qui arrive en dernier en depassant legerement sa taille et reste
pose sur la ligne. Le trait ne disparait pas : il s'attenue et relie les deux
extremites du logotype. Puis l'etincelle **respire
lentement** tant que le navigateur n'est pas monte. Un ecran fige pendant deux
secondes donne l'impression que le programme a plante ; ce battement dit que ca
travaille.

**Elle ne s'efface pas : elle devient la fenetre.** Quand le navigateur est
pret, le logotype passe sous un voile et les quatre coins de la carte partent
rejoindre les quatre coins de la fenetre a venir, en 0,55 s. Des equerres
lumineuses conduisent le regard vers les bords, le cadre se referme derriere
elles, puis elles s'effacent : il ne reste qu'un rectangle borde d'un liseré,
c'est-a-dire exactement ce qu'est la fenetre de Plume. Les deux se croisent
alors en fondu, aux memes dimensions, et le raccord ne se voit pas.

**Sur plusieurs ecrans, elle joue sur le bon.** La session retient les bornes
de chaque fenetre : elles disent sur quel moniteur le navigateur va revenir, et
c'est la que l'ouverture se centre. Sans cela elle s'affichait sur l'ecran
principal pendant que la fenetre rouvrait ailleurs, puis traversait le bureau en
diagonale. La session est donc lue **avant** de lancer l'ouverture. Une fenetre
a cheval sur deux ecrans est rattachee a celui qu'elle occupe le plus, et si les
bornes enregistrees ne tombent plus sur aucun ecran branche, l'ecran principal
sert de repli, la ou la fenetre atterrira de toute facon.

Dernier garde-fou : si la fenetre s'ouvre malgre tout sur un autre moniteur que
l'ouverture, l'etalement est abandonne au profit d'un simple fondu. Une carte
qui traverse le bureau en diagonale serait pire que pas d'effet du tout.

C'est possible parce que l'ouverture vit sur son propre fil : elle anime sa
propre geometrie pendant que le navigateur, deja monte, attend derriere. Le fil
principal lui passe simplement les bornes de la fenetre a rejoindre.

**Le meme piege que les fenetres detachees, une deuxieme fois.** L'etalement ne
se voyait pas : il s'etirait de 560x220 vers 1440x900 a une position par defaut,
puis la fenetre sautait a sa taille reelle. En cause, `Shown`, qui arrive APRES
le retour de `Show()` et qui est ce qui pose la geometrie definitive : lire
`Bounds` juste apres `Show()`, c'est lire la taille du constructeur. Mesure
faite sur une fenetre invisible : 1440x900 juste apres `Show()`, 2560x1392 apres
avoir pompe les messages. Le lancement attend donc que la fenetre ait pose sa
geometrie avant de donner la cible.

Le journal consigne desormais ce que l'etalement a vise
(`intro : etalement 560x220 -> 2560x1392 en 0.75 s`) : une animation qu'on ne
voit pas ne dit pas d'elle-meme si elle n'a pas eu lieu ou si elle a vise a
cote.

**Le logotype tressaillait pendant l'etirement.** Il etait recentre dans une
fenetre qui grandit, et les arrondis de la position et de la largeur ne tombent
pas ensemble : la position a l'ecran sautait d'un pixel d'une image a l'autre.
Mesure sur les 45 images de l'animation : **26 bougeaient**, d'un pixel au
maximum, ce qui suffit largement a se voir a soixante images par seconde.
Pendant l'etirement, le logotype est donc compose dans les dimensions de la
carte de depart puis decale de ce que la fenetre a bouge : il garde sa place a
l'ecran, et c'est la fenetre qui grandit autour de lui. Apres correction, zero
image ne bouge.

**Le logotype s'efface AVANT que la fenetre ne bouge**, pendant 0,8 s, la
fenetre encore immobile. C'est la seule facon sure : une animation de position,
si soignee soit-elle, laisse passer quelque chose des que le repere de dessin
change en meme temps que la fenetre. Une seule image composee dans le repere de
la carte alors que la fenetre est deja grande, et le nom apparait en haut a
gauche avant de revenir. Effacer d'abord, bouger ensuite : il n'y a plus rien a
voir bouger. L'etirement part donc d'une carte deja vide, et le logotype n'est
meme plus dessine une fois le voile complet.

**Deux ruptures a la premiere image de l'etirement**, qui se lisaient comme un
sursaut. La respiration de l'etincelle n'etait dessinee qu'en dehors de
l'etirement : elle s'eteignait d'un coup, alors qu'elle est justement proche de
son maximum a cet instant. Et les quatre equerres apparaissaient a pleine
intensite, deja formees, sur une carte encore petite. La respiration continue
donc pendant l'etirement, c'est le voile qui l'eteint progressivement ; les
equerres, elles, entrent en fondu et partent de zero.

Un raccord ne se juge pas a l'oeil : on compare les images. Entre la derniere
image d'attente et la premiere de l'etirement, l'ecart moyen est de **0,03 sur
255**, puis il croit doucement. Un sursaut se serait vu comme un pic.

Un detail de mise en oeuvre : les coins arrondis de la carte disparaissent des
le debut de l'etalement. Suivre la region a chaque image couterait un objet GDI
par image, pour un detail que l'oeil ne saisit pas pendant un mouvement aussi
vif.

Elle ne s'efface qu'a **deux conditions reunies** : l'animation est allee au
bout de ses 2,5 secondes, **et** le navigateur est pret. C'est tout l'interet :
le chargement se cache derriere au lieu de se montrer. Les fenetres construites
pendant ce temps restent invisibles et n'apparaissent qu'ensuite, en fondu, a la
place de l'ouverture.

**Elle tourne sur son PROPRE fil, et c'est la seule facon.** WinForms n'a qu'un
fil, et construire une fenetre WebView2 le bloque une a deux secondes : une
animation jouee sur ce fil-la resterait figee pendant tout le chargement, soit
exactement le contraire du but. Sur un fil a elle, avec sa propre file de
messages, elle tourne pendant que le navigateur se monte derriere. Ce fil ne
touche a rien d'autre que sa propre fenetre : il ne partage avec le reste de
Plume que trois drapeaux. Une fenetre WinForms appartient au fil qui l'a creee,
et cette regle ne se contourne pas.

**Les lueurs se fabriquent a la main.** GDI+ ne sait pas melanger en mode
additif : un halo s'obtient en empilant la meme forme, plus large et plus
transparente a chaque couche, avec un coeur blanc par-dessus, faute de quoi la
lumiere grisaille au lieu de briller. **Quatre couches laissaient voir des
anneaux concentriques** : il en faut sept, avec une decroissance douce, pour que
l'oeil n'y lise plus de marches. Sept remplissages de quelques pixels ne coutent
rien a soixante images par seconde.

**Dessinee, pas filmee.** Une video de 2,5 s pese plusieurs megaoctets dans un
paquet qu'on tient a garder mince, et il faudrait demarrer un lecteur avant
meme d'avoir une fenetre. Ici il n'y a rien a charger : du GDI+, comme le reste
de l'interface, reprenant les formes deja en place (l'etincelle des onglets, le
trait d'accent, la meme courbe de ralentissement).

Trois precautions. La fenetre n'a **pas de titre**, sans quoi les tests la
prendraient pour une fenetre de navigation. Elle ne prend jamais le focus
(`SWP_NOACTIVATE`). Et un garde-fou de douze secondes la ferme meme si le
navigateur ne signalait jamais qu'il est pret : une ouverture ratee ne doit
jamais empecher Plume de demarrer.

La sequence complete dure donc 2,5 s d'attente au minimum, puis 0,8 s
d'effacement, 0,65 s d'etirement et 0,28 s de fondu croise. Les quatre durees
sont des constantes voisines en tete de fichier, faciles a regler.

Un clic abrege, et `intro: false` dans `config.json` supprime la sequence.

**Le lecteur ne devance plus la page.** Au lancement sur une page video, on
voyait arriver le lecteur avant la page qui l'entoure. La fenetre de mpv est de
premier niveau : elle ne suit ni le fondu d'apparition de la fenetre, ni son
invisibilite pendant l'ouverture. Le lecteur reste donc cache tant que sa
fenetre n'est pas entierement opaque. La page renvoie sa zone toutes les
120 ms : il reapparait des la fin du fondu, dans le bon ordre, la page d'abord.

### Plus de flash blanc

WebView2 peint en **blanc** tant que la page n'a rien rendu. Sur une interface
sombre, chaque onglet neuf lancait donc un eclair blanc en plein ecran, sur
toute la surface de la page. `DefaultBackgroundColor` pose la couleur de fond de
Plume a la place : l'eclair disparait, et les pages posent la leur par dessus
sans rien changer.

### Un onglet s'ouvre et se ferme en bougeant

Une barre d'onglets ou tout apparait et disparait d'un coup ne dit pas ce qui
vient de se passer. Un onglet neuf s'ecarte donc depuis une largeur nulle, et un
onglet ferme se retire en laissant les autres reprendre sa place.

Deux courbes differentes, comme pour l'animation du lecteur : l'ouverture
ralentit en arrivant (170 ms), la fermeture accelere en partant (140 ms). Avec
une seule courbe pour les deux, le mouvement parait mou, ce qu'on avait deja
mesure sur le disque de lecture et pause.

Un onglet ferme quitte la logique **tout de suite** et ne reste qu'a l'ecran,
sous forme de fantome : rien d'autre dans le code n'a a connaitre cet etat
intermediaire. Le fantome compte encore dans le calcul de la largeur des
onglets, sans quoi les voisins sauteraient d'un coup a leur nouvelle taille.

Le minuteur ne tourne que pendant l'animation et s'arrete de lui-meme : une
boucle permanente a soixante images par seconde pour une barre immobile serait
exactement la depense que Plume refuse. Et rien ne s'anime a la reprise de
session : vingt onglets qui s'ecartent l'un apres l'autre au lancement font une
entree en scene, pas une interface.

**La marque de Plume dans le mouvement.** Une largeur qui varie, n'importe quel
navigateur le fait. Pendant l'ouverture, l'etincelle a quatre branches de
l'icone eclot a la place du favicon, grandit puis s'efface, un trait d'accent
balaye le haut de l'onglet, et le titre entre en fondu derriere. A la
fermeture, la meme etincelle se retracte au centre de la place qui se referme.
La place de l'icone est reservee pendant l'ouverture : sans cette reserve,
l'etincelle se dessinait sur le titre.

L'etincelle est tracee en courbes, cotes concaves compris, exactement comme
l'icone du programme : c'est ce galbe qui la distingue d'une etoile ordinaire,
et les polices d'icones de Windows ne sont de toute facon pas rendues par GDI+.

### La fenetre apparait et s'efface

Une fenetre qui surgit et disparait d'un coup fait sursauter. Plume nait a
opacite nulle et monte en 220 ms ; a la fermeture, elle descend en 150 ms avant
de se fermer pour de bon.

Deux details. L'opacite est posee **des la construction**, sinon un cadre opaque
serait deja a l'ecran quand l'animation demarre. Et la fermeture se joue en deux
temps : le premier passage dans `FormClosing` annule la fermeture, ecrit la
session, lance le fondu, puis rappelle `Close` ; le second fait le vrai travail.
La session est ecrite **avant** l'animation, pour qu'une coupure pendant le
fondu ne coute rien.

Verifie plutot que suppose : WinForms rend la fenetre « layered » tant que
l'opacite est inferieure a 1, et WebView2 dessine dans sa propre fenetre enfant.
La composition aurait pu mal se passer. Mesure : la fenetre passe bien par un
etat transparent, redevient opaque ensuite, et la barre garde sa couleur
normale.

### Fermer le dernier onglet ferme la fenetre

Plume rouvrait une page d'accueil a la place. On se retrouvait devant une
fenetre vide sans comprendre pourquoi elle etait encore la, et il fallait un
second geste pour s'en debarrasser. C'est le comportement de tous les
navigateurs, et il n'y avait aucune raison d'en differer.

### Le fil de progression

Rien ne disait si une page chargeait ou si le clic s'etait perdu. Un fil de
deux pixels court desormais au bas de la barre de navigation, pose par etapes
au fil des evenements de WebView2 : `NavigationStarting` 8 %, `ContentLoading`
45 %, `DOMContentLoaded` 80 %, `NavigationCompleted` efface.

Pas de minuteur, donc pas d'animation : une boucle a trente images par seconde
pour un trait de deux pixels couterait plus que ce qu'elle apporte, et Plume se
juge au processeur qu'il ne consomme pas. Le fil appartient a l'onglet, pas a
la fenetre : changer d'onglet montre le sien.

### AltGr n'est pas un raccourci

Sur un clavier francais, `AltGr` se presente a Windows comme `Ctrl` + `Alt`.
Les raccourcis `Ctrl` + chiffre repondaient donc a chaque `AltGr` + chiffre :
taper `@` basculait sur le deuxieme onglet, taper `|` sur le premier, et le
caractere n'arrivait jamais.

Le correctif tient en une garde au debut du gestionnaire de clavier : aucun
raccourci de Plume n'emploie `Ctrl` + `Alt`, donc toute frappe qui porte les
deux est rendue entierement a la page, sans etre absorbee. C'est la regle
generale : un raccourci sur `Ctrl` + X ne doit jamais repondre a
`Ctrl` + `Alt` + X.

Mesure : `AltGr` + `2` ecrit bien `@` dans la barre d'adresse, et l'onglet
actif ne bouge pas.

### Le lecteur se rallume en revenant sur l'onglet

Apres un redemarrage, une page video restauree n'activait pas son lecteur : il
fallait rafraichir a la main. Deux mecanismes se combinaient pour produire ce
silence, et aucun des deux n'etait fautif seul.

Le script de page n'annonce sa video qu'au **changement d'adresse** : une seule
fois, au chargement. Or Plume **jette** les annonces venant d'un onglet qui
n'est pas actif, a juste titre, un onglet cache n'ayant rien a repositionner.
Et WebView2 gele de toute facon les onglets invisibles. Au retour sur l'onglet,
la page croyait donc avoir deja tout dit, et plus rien ne se declenchait.

Le correctif tient en une ligne de JavaScript : en activant un onglet video sans
lecteur, Plume remet a zero l'adresse memorisee par le script de page. Le
battement suivant, dans les 120 ms, refait l'annonce complete, museler compris.
Rien n'est fait si une lecture tourne deja, ni si l'utilisateur a choisi le
lecteur du site.

Ce correctif repose sur un **nom de propriete partage entre deux fichiers**,
`window.__plume.url`, ecrit d'un cote et compare de l'autre. Un renommage d'un
seul cote casserait tout en silence : un test de coherence le verifie, sans
ouvrir de fenetre.

### Reprendre une video la ou on l'a laissee

Fermer Plume au milieu d'une video et la rouvrir la reprend a la seconde pres,
sans rien annoncer. Un bandeau « Reprise a 5:18 » a existe un temps : il disait
ce que le curseur montrait deja, et une video sur deux le declenchait. Les
positions vivent dans
`profil/positions.json`, rangees **par identite de video** et non par adresse :
YouTube ajoute et retire des parametres, et la meme video doit se retrouver quoi
qu'il arrive. C'est la meme cle que celle qui empeche le lecteur de redemarrer
trois fois, `core.cle_video`.

Trois regles, qui font la difference entre une commodite et une gene :

- **en dessous de trente secondes, rien n'est retenu.** On vient de commencer,
  proposer une reprise serait plus penible qu'utile ;
- **a moins de quarante-cinq secondes de la fin, la video est consideree comme
  vue** : la position est effacee, et la rouvrir la reprend au debut plutot
  qu'au generique. Une video allee jusqu'au bout est oubliee de la meme facon ;
- **au dela de deux mois, on oublie.** La position d'une video vue en avril ne
  veut plus rien dire. Trois cents videos au maximum : c'est une commodite, pas
  une archive.

**Qui mesure quoi.** mpv connait la position, Plume connait la video : le script
Lua publie `position/duree` sur le meme canal `user-data` que le mode theatre,
**toutes les cinq secondes** et non a chaque image, `time-pos` changeant soixante
fois par seconde. Une pause la publie immediatement, parce qu'une pause veut
souvent dire « je m'arrete la ». La reprise se fait par `--start=` au lancement
d'un nouveau processus mpv, et non par la propriete `start` posee dans un mpv
deja en marche, qui resterait active pour les lectures suivantes.

L'ecriture du fichier est freinee a une fois toutes les vingt secondes, et
forcee a la fermeture de la fenetre.

### Les playlists s'enchainent

Le lecteur du site est muselé : la page ne sait donc pas que la video est finie,
et n'enchaine jamais d'elle-meme. Une playlist s'arretait au premier titre, ce
qui n'avait l'air d'un bug de personne, chacun faisant exactement son travail.

Il fallait relier les deux. mpv tourne avec `--keep-open=yes` : a la fin il ne
se ferme pas, il reste sur la derniere image, ce qui laisse le temps de
prevenir proprement. Le script Lua observe `eof-reached` et passe l'information
a Plume par le meme canal `user-data` que le mode theatre. Guetter la mort du
processus aurait ete une course perdue d'avance.

Plume, lui, ne decide de rien : il execute un script dans la page, parce qu'elle
seule connait l'ordre de la liste. Trois voies, dans cet ordre : le panneau de
playlist quand il est rendu, sinon les donnees de la page (`ytInitialData`, ou
YouTube decrit la liste entiere et sait dire « c'etait la derniere »), sinon
l'adresse du bouton « suivant » du lecteur du site. Le chargement de la page
suivante declenche le lecteur comme n'importe quelle autre video.

**Ce que la mesure sur une vraie playlist a appris, et qu'aucun raisonnement
n'aurait donne.** La premiere version enchainait correctement... une fois. Elle
cliquait le bouton « suivant » du site, et l'adresse d'arrivee **perdait le
`&list=`** : la deuxieme video n'etait plus dans une playlist, donc plus rien
n'enchainait. Le bug avait l'air corrige et ne l'etait pas. D'ou deux
changements : on lit l'**adresse** du bouton au lieu de le cliquer, et toute
navigation repose la liste si elle manque. Pour le verifier, un test ne suffit
pas a une bascule : il en faut **deux d'affilee**, sans quoi on ne voit rien.

Le journal dit desormais quelle voie a ete prise (`action fini -> "panneau"`,
`"donnees"`, `"bouton-adresse"`...). Sans cette trace, une playlist qui
n'enchaine pas ne laisse rien a lire.

**Aucun repli sur « index + 1 »** : YouTube ramene un index hors bornes au debut
de la liste, ce qui ferait tourner la playlist en boucle sans fin. Mieux vaut
s'arreter que de ne plus savoir s'arreter. Hors playlist, le script ne touche a
rien : l'enchainement automatique des recommandations n'a pas ete demande, et
ne serait pas souhaitable.

Un garde-fou : une meme video n'enchaine qu'une fois, `eof-reached` repassant a
vrai si la lecture est relancee sur place. Il se rearme a chaque nouvelle
lecture.

### La fenetre qui recoit l'onglet passe devant

Sortir un onglet dans une fenetre a lui, ou le deposer dans une autre fenetre,
laissait la fenetre d'arrivee DERRIERE. Le coupable etait dans Plume, et pas ou
on l'aurait cherche : `fermer()` rend le focus a la vue restante de la fenetre
de depart, et cet appel arrive **apres** la creation de la nouvelle fenetre. La
fenetre d'origine reprenait donc le premier plan qu'on venait de donner a
l'autre.

Corrige des deux cotes du meme geste : `mettre_en_avant()` est appelee **apres**
la fermeture, jamais avant, et ne se contente pas d'`Activate()` (insuffisant
quand une autre fenetre du meme programme vient de reclamer le focus) mais
appelle explicitement le premier plan.

Le lecteur suit : quand le premier plan appartenait a Plume, il est rendu a la
fenetre qui porte le lecteur **maintenant**, pas a celle qui l'avait avant.
Sortir un onglet en pleine lecture deplace le lecteur, et rendre le focus a
l'ancienne fenetre remettait la nouvelle derriere.

### Le lecteur ne vole plus le premier plan

**mpv s'empare du premier plan en creant sa fenetre**, et Plume relance un
lecteur a chaque video. Sur une playlist, la fenetre du navigateur passait donc
derriere a chaque changement de titre : on croyait le navigateur parti en
arriere-plan tout seul.

Plume n'y etait pour rien : il n'active jamais la fenetre du lecteur
(`SWP_NOACTIVATE`, `SW_SHOWNOACTIVATE`). **Et `--focus-on=never` ne suffit
pas** : mesure faite en isolant mpv de Plume, il vole le premier plan avec
comme sans l'option. L'option reste, elle ne coute rien et sert sur les
versions ou elle fonctionne, mais la vraie correction est ailleurs : une fois
la fenetre adoptee, Plume **rend le premier plan** a celle qui l'avait juste
avant.

Trois precautions, sans lesquelles le remede serait pire que le mal : on ne
reprend la main que si c'est bien mpv qui l'a prise ; on la rend a la fenetre
qui l'avait, pas forcement a la notre ; et si quelqu'un est passe sur une autre
application pendant le chargement, c'est a elle qu'elle revient, pas a la
fenetre notee au depart. Autrement dit, Plume ne rappelle jamais le focus a lui
depuis une autre application.

### La molette ne saute plus dans la video

Une molette au-dessus de l'image avancait ou reculait de cinq secondes. Trop
facile a declencher sans le vouloir : on perdait sa place pour un coup de doigt,
et retrouver l'endroit exact demandait plusieurs essais. Elle fait desormais
defiler la page, comme sur le site. Au-dessus du curseur de volume, elle regle
toujours le volume ; dans un menu ouvert, elle le fait toujours defiler.

### Mode theatre

Un bouton en forme de cadre large, a gauche du plein ecran, absent quand on est
deja en plein ecran ou il n'aurait aucun sens.

Le mode theatre appartient a la **page**, pas au lecteur : c'est le site qui
elargit sa mise en page. mpv ne fait donc que transmettre la demande, et Plume
appuie sur le bouton du site quand il existe, sinon lui envoie la touche `t`
qu'il attend. mpv suit tout seul ensuite : le script de page renvoie la nouvelle
zone du lecteur a chaque changement de mise en page, et le lecteur s'y recolle.

**Comment mpv parle a Plume.** Il n'y en avait pas besoin jusqu'ici : Plume
lisait l'etat de mpv, mpv ne demandait rien. Le canal passe par une propriete
`user-data/plume/action`, que le script Lua ecrit et que le cote Python observe
sur le tube IPC deja ouvert pour le plein ecran. La valeur porte un compteur en
tete, sans quoi demander deux fois la meme chose ne produirait qu'une seule
notification. Un piege de Lua au passage : une fonction locale declaree apres
son appelant n'est pas visible, et le clic sur le bouton aurait appele une
valeur nulle.

### La fenetre privee

`Ctrl` + `Maj` + `N`, ou le clic droit sur l'icone de la barre des taches.
La fenetre s'ouvre avec un bord violet et un insigne dans la barre d'onglets :
une fenetre privee qui ressemble aux autres est un piege, on finit par taper au
mauvais endroit.

Techniquement, chaque vue de cette fenetre est creee avec
`CoreWebView2CreationProperties.IsInPrivateModeEnabled`. Meme dossier de
profil, mais session separee : cookies, cache et stockage local vivent en
memoire et disparaissent a la fermeture. Cote Plume, la fenetre n'ecrit ni
historique ni session, et n'est donc pas rouverte au lancement suivant.

Deux details de mise en oeuvre. Les proprietes de creation doivent etre posees
**avant** `EnsureCoreWebView2Async`, apres quoi la vue ne les accepte plus. Et
la boucle principale lancee avec `--fenetre-privee` saute la restauration de
session : rouvrir les onglets d'hier dans une fenetre privee serait exactement
l'inverse de ce qu'elle promet.

Le bandeau d'ouverture dit aussi ce que la fenetre ne fait pas : les
telechargements restent sur le disque, et le fournisseur d'acces voit toujours
passer le trafic. Une promesse de confidentialite qu'on laisse croire plus large
qu'elle n'est vaut moins que pas de promesse du tout.

### Groupes de travail

Une premiere version groupait les onglets automatiquement, par la chaine qui
les avait ouverts. Ce n'etait pas la bonne idee : elle rangeait la seance en
cours, alors que ce qu'on veut retrouver, ce sont les **memes pages, d'un jour
a l'autre**. Un groupe de travail est une habitude, pas une session.

Clic droit sur un onglet, « Ajouter a ... » ou « Nouveau groupe de travail ».
La page est rangee dans le groupe, avec son titre. Sur la page d'accueil, chaque
groupe est une carte : un clic l'ouvre en entier, la croix le supprime. Un
groupe « dev » rouvre ainsi ses cinq pages habituelles d'un seul geste, et le
meme clic droit retire une page devenue inutile.

Trois decisions qui comptent :

- **une page deja ouverte n'est pas rouverte.** Sans cela, cliquer deux fois sur
  un groupe doublerait tous ses onglets, et l'usage naturel (« je reprends le
  travail ») deviendrait un piege a memoire ;
- **douze pages par groupe au maximum.** Les rouvrir toutes doit rester tenable :
  au dela, on ferait exploser la memoire d'un clic ;
- la page d'accueil n'y est pas rangeable. Un onglet neuf n'est pas une page de
  travail, et la ligne du menu reste grisee pour le dire.

Les groupes vivent dans `profil/groupes-travail.json`, un fichier lisible, et
sont partages par toutes les fenetres. En ecrire un reecrit la page d'accueil et
recharge celles qui sont deja ouvertes, sinon le groupe cree n'apparaitrait
qu'au prochain onglet.

**Le menu du clic droit est dessine par Plume**, comme la liste de suggestions :
une fenetre a part, sans bordure, en `WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE`, et
montree par `SetWindowPos`. Un menu Windows standard, gris clair, jurerait au
milieu d'une interface entierement dessinee. Meme chose pour la saisie du nom :
WinForms n'offre pas de boite de saisie, et celle de Windows aurait le meme
defaut.

#### Le piege : un guillemet qui refermait l'attribut

Les cartes portent `onclick="ouvrirTravail(...)"`, et le nom du groupe y est
insere. `json.dumps` rend bien la chaine sure **pour JavaScript**, mais ses
guillemets doubles refermaient l'attribut HTML qui la contient : le
gestionnaire se retrouvait coupe en deux, et le clic ne faisait simplement
rien, sans la moindre erreur. Il faut les deux echappements, JavaScript puis
HTML. C'est la meme famille de bug que le bandeau qui n'avait jamais
fonctionne, et la meme regle : ne jamais composer de JavaScript a la main.

### Les onglets qui dorment

Un onglet coute environ 390 Mo, et c'est le poste de depense principal de
Plume. Or un onglet ouvert depuis dix minutes sans etre regarde consomme
exactement autant qu'un onglet actif : ses minuteurs tournent, ses scripts
s'executent, ses connexions restent ouvertes.

WebView2 sait geler un onglet, et cette possibilite n'etait pas branchee.
`CoreWebView2.TrySuspendAsync()` arrete tout ce qui tourne dans la page, et
`MemoryUsageTargetLevel = Low` demande en plus au moteur de rendre ce qu'il
peut. Un minuteur passe toutes les quinze secondes et endort les onglets
inactifs depuis plus de `veille_onglets` secondes, 90 par defaut, 0 pour
desactiver.

**Suspendre n'est pas decharger**, et c'est toute la difference avec le
« tab discarding » de Chrome. Le DOM reste en place, la position de
defilement aussi, un formulaire a moitie rempli n'est pas perdu. Revenir sur
l'onglet appelle `Resume()` : la page est deja la, il n'y a rien a
recharger, donc rien a redemander au reseau. L'utilisateur ne voit pas la
difference, sinon que sa machine respire.

Deux onglets sont epargnes : celui qu'on regarde, et celui qui joue une
video, mpv suivant la position du lecteur dans la page. Le delai laisse aussi
un aller-retour rapide entre deux onglets sans aucun cout.

**Mesure, trois onglets ouverts dont deux endormis :**

| Etat | Moteurs web |
|---|---|
| trois onglets eveilles | **559 Mo** |
| deux endormis | **447 Mo** |

112 Mo rendus, soit 20 % du total, sur un cas ou l'un des trois onglets etait
une page presque vide. Le gain croit avec le poids des pages laissees de cote,
c'est-a-dire exactement dans le cas qui fait mal.

Un trou corrige apres coup : si le noyau se trouvait deja suspendu sans que
Plume l'ait note, l'onglet restait « eveille » dans ses comptes et ne pouvait
plus jamais etre endormi, la fonction ressortant en silence. L'etat local
rattrape desormais le vrai. La veille consigne aussi chaque tentative dans le
journal, avec le temps d'inactivite : un onglet qui refuse de dormir dit
maintenant pourquoi.

Dans la barre, un onglet endormi porte un point discret et son titre passe en
gris : il faut que ce soit lisible sans donner l'impression d'une panne. Le
detail qui compte a l'ecriture : `MemoryUsageTargetLevel` doit etre pose
**avant** la suspension, puisque apres, plus rien dans cet onglet ne repond.

### Historique local, et completion de la barre d'adresse

`profil/historique.json` retient les 3000 dernieres adresses visitees, avec leur
titre, leur date et leur nombre de visites. Rien ne sort de la machine : c'est un
fichier, dans le dossier de Plume, et il suffit de le supprimer pour tout
oublier.

La barre d'adresse s'en sert pour proposer jusqu'a huit lignes des la deuxieme
lettre tapee : les favoris d'abord, l'historique ensuite, classe par nombre de
visites puis par date. `Bas` et `Haut` parcourent la liste, `Entree` ouvre la
ligne choisie, `Echap` la referme sans rien changer, et un clic marche aussi.

La comparaison se fait **mot par mot**, pas sur la chaine entiere : on se
souvient d'une page par deux bouts de son titre, rarement dans l'ordre exact ou
ils y figurent. « wiki navigateur » retrouve donc l'article de Wikipedia, ce
qu'une recherche par sous-chaine ratait.

La derniere ligne est toujours « Rechercher "..." », sauf si la saisie est deja
une adresse. Elle rend previsible ce que fera `Entree` : sans elle, taper deux
mots et valider donnait une recherche web sans que rien ne l'ait annonce.

La liste est **une fenetre a part**, pas un panneau : WebView2 occupe toute la
zone de la page et aucun controle WinForms ne peut se dessiner par dessus. Cette
fenetre est creee sans bordure, avec `WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE`, et
montree par `SetWindowPos` avec `SWP_NOACTIVATE`. Le detail qui compte :
`TopMost = True` de WinForms **active** la fenetre, donc volait le focus au champ
de saisie et coupait la frappe au bout d'une lettre. Il a fallu s'en passer
entierement.

Deux autres pieges ont ete traverses. Choisir la suggestion de la page deja
ouverte ne faisait rien, parce qu'affecter a `Source` la valeur qu'elle a deja
ne declenche aucune navigation : il faut appeler `CoreWebView2.Navigate(url)`.
Et la liste se rouvrait juste apres la navigation, le champ etant reecrit par
Plume lui-meme, ce que resout un drapeau pose autour de la mise a jour
programmee.

### Le zoom est retenu par site

`Ctrl` + `+` et `Ctrl` + `-` montent et descendent dans les paliers usuels, de
50 % a 200 %. Le facteur est range par hote dans `profil/zooms.json`, si bien
qu'un site trop petit reste lisible a la visite suivante sans qu'on y repense.
`Ctrl` + `0` revient a 100 % et **retire** l'entree du fichier : le reglage par
defaut ne merite pas d'etre stocke. Le zoom est applique a chaque fin de
navigation, l'onglet pouvant changer de site.

### Rouvrir un onglet ferme

`Ctrl` + `Maj` + `T` rouvre le dernier onglet ferme, jusqu'a vingt en arriere.
La page d'accueil n'est pas retenue, sans quoi le raccourci passerait son temps a
rouvrir des onglets vides.

Cela a mis au jour un defaut plus ancien : apres `Ctrl` + `W`, plus aucun
raccourci ne repondait. Fermer l'onglet detruisait le controle qui avait le
focus, et le focus ne revenait a personne. La fermeture redonne desormais la main
a la vue de l'onglet actif.

### Un contour visible

Sans bordure systeme, une fenetre sombre se confond avec un fond sombre : on ne
voit plus ou elle s'arrete. Le formulaire porte donc `Padding(1)` et sa couleur
de fond sert de contour, les panneaux ancres se placant a l'interieur de cette
marge. Verifie au pixel : la premiere ligne et la premiere colonne valent
exactement la couleur du bord, la suivante celle de la barre d'onglets.

### Deplacer un onglet, dedans ou dehors

Tirer un onglet et le relacher :

- **sur la barre d'onglets d'une autre fenetre Plume** : il y passe ;
- **plus de 26 px sous sa propre barre** : il sort dans une fenetre a lui,
  posee sous le curseur ;
- ailleurs : rien.

**Le sort de l'onglet se decide au relachement, pas pendant le mouvement.** La
premiere version detachait des le franchissement du seuil, ce qui rendait le
depot dans une autre fenetre impossible : l'onglet etait deja parti.

**La fenetre creee par un detachement recevait la taille de l'ecran entier.**
Elle naissait donc en plein ecran, quelle que soit la taille demandee ensuite.
En cause, un ordre contre-intuitif : l'evenement `Shown`, qui agrandit une
fenetre neuve, arrive **apres** le retour de `Show()`, et ecrasait la taille
posee juste apres. La taille voulue est desormais passee au constructeur, et
`au_demarrage` la respecte au lieu de maximiser.

Pendant le deplacement, trois choses le montrent : une **vignette** portant le
titre et l'icone suit le curseur, la place de l'onglet reste marquee **en creux**
dans sa barre d'origine, et la barre **visee** s'entoure d'un liseré d'accent
avec un trait d'insertion la ou l'onglet se posera.

Deux details rendent cette vignette possible :

- elle est affichee par `SetWindowPos` et non par `Show()`. Afficher normalement
  une fenetre lui donne le focus, ce qui romprait la capture de la souris et
  donc le glissement en cours ;
- elle porte `WS_EX_TRANSPARENT`. Sans cela `WindowFromPoint`, posee sous le
  curseur, se designait **elle-meme** comme cible : la fenetre visee ne
  s'allumait jamais. Au relachement le transfert fonctionnait quand meme, la
  vignette etant fermee juste avant la recherche de la cible, ce qui rendait le
  symptome purement visuel et d'autant plus deroutant.

La fenetre visee est celle que **Windows** declare sous le curseur
(`WindowFromPoint` puis `GetAncestor`), et non la premiere de notre liste : deux
fenetres peuvent se recouvrir, et seule celle du dessus doit recevoir l'onglet.

Si l'onglet deplace etait le dernier de sa fenetre, celle-ci se ferme.

**L'onglet est DEPLACE, plus rouvert (2026-09-12).** La premiere version
rouvrait l'adresse de l'autre cote, par prudence : un rechargement complet a
chaque glissement, et une video qui repartait du debut. Le controle WebView2
passe desormais d'une fenetre a l'autre tel quel. Les deux fenetres vivent sur
le meme fil, WinForms se contente donc d'un `SetParent` ; et comme la poignee de
la vue elle-meme ne change pas, le `ParentWindow` du controleur WebView2 reste
valide. La page continue ou elle en etait : defilement, formulaires, lecture
video, et l'historique de l'onglet n'est plus perdu.

Le lecteur suit sans s'arreter. La fenetre de mpv est de premier niveau : elle a
un **proprietaire**, pas un parent. Lui donner le nouveau proprietaire suffit, et
la video ne s'en apercoit pas. `definir_parent` arretait puis relancait la
lecture, ce qui la faisait repartir de zero a chaque glissement.

**Le clignotement du passage.** Sortir un onglet pendant une lecture donnait
une suite d'apparitions et de disparitions de l'image. Deux causes, traitees
toutes les deux plutot que de chercher laquelle dominait :

- `_zone` retient la position **et les bornes de l'ancienne fenetre**. S'en
  servir pendant que la nouvelle se pose faisait apparaitre le lecteur au
  mauvais endroit, disparaitre parce que la zone tombait hors des bornes, et
  reapparaitre au calcul suivant. Le lecteur s'efface donc le temps que la page
  redise ou il va, ce qu'elle fait toutes les 120 ms : une disparition breve au
  lieu d'un clignotement ;
- une fenetre nee d'un onglet tire n'a **pas de fondu**. Faire apparaitre en
  fondu une fenetre qui porte deja une video visible ajoutait sa propre
  scintillation, et le geste fait deja la transition.

Chaque apparition et chaque disparition du lecteur sont consignees dans le
journal (`PLUME_DEBUG`). Un clignotement se voit mais ne se raconte pas : sans
cette trace il faut le reproduire pour savoir combien de cycles ont eu lieu.

**Deux garde-fous, parce que deplacer est plus risque que rouvrir.** Si le
moteur de la page ne survivait pas au changement de parent, on aurait une page
blanche, pire qu'un rechargement : Plume verifie donc que `CoreWebView2` est
toujours la apres coup, et remet l'onglet ou il etait sinon. Et tout echec du
deplacement retombe sur l'ancienne methode, qui rouvre l'adresse. Mieux vaut une
page rechargee qu'un onglet perdu entre deux fenetres.

Le clic qui suit un deplacement est ignore, sans quoi il activerait ou fermerait
un onglet au passage.

### Telechargements

Le fichier arrivait bien dans le dossier Telechargements, mais **rien ne le
disait** : ni progression, ni chemin, ni echec. WebView2 sait afficher sa propre
fenetre de telechargements, elle ne s'ouvre simplement pas toute seule.

Plume s'abonne donc a `DownloadStarting`, ouvre cette fenetre, et suit l'etat de
l'operation : un bandeau annonce la fin avec le nom du fichier et son dossier,
ou l'interruption avec sa raison. La fenetre de WebView2 se referme d'elle-meme
au bout de quelques secondes, le bandeau reste douze secondes.

### Le bandeau n'avait jamais fonctionne

**Pas une seule fois, pas meme pour annoncer un echec de lecture**, alors que
c'est sa raison d'etre. La regle CSS injectee contenait
`font:13px/1.5 'Segoe UI',sans-serif` a l'interieur d'une chaine JavaScript
elle-meme delimitee par des apostrophes : la chaine se refermait sur
`'Segoe`, le script devenait invalide, et `ExecuteScriptAsync` n'annonce pas les
erreurs de la page.

Le texte et le style passent desormais tous les deux par `json.dumps`, ce qui
supprime la classe entiere de ces bugs de guillemets. Un second parametre
distingue les mauvaises nouvelles, en rouge, des ordinaires : annoncer un
telechargement reussi en rouge le faisait passer pour une panne.

### Recherche dans la page : ce qui marche, et ce qui ne marche pas

**Elle fonctionne deja**, sans une ligne de code de notre part : `Ctrl` + `F`
ouvre la barre de WebView2 quand la **page** a le focus. Je l'avais declaree
absente sur la seule foi d'un `grep`, a tort.

Le seul angle mort est le focus dans la barre d'adresse. Trois tentatives, toutes
infructueuses :

- simuler la frappe (`SendKeys`) : le contenu web vit dans un autre processus et
  ne recoit pas les touches envoyees a notre fenetre ;
- `CoreWebView2FindOptions()` : pas constructible directement, il faut
  `environnement.CreateFindOptions()` ;
- `Find.StartAsync` avec `SuppressDefaultFindDialog = False` : la tache se
  termine sans erreur (`RanToCompletion`) et **surligne bien toutes les
  correspondances**, mais la barre visuelle ne s'ouvre pas.

Le raccourci a donc ete retire plutot que de laisser une touche sans effet. Ce
que cela apprend : le moteur de recherche est pilotable (`MatchCount`,
`ActiveMatchIndex`, `FindNext`, `FindPrevious`), seule son interface ne l'est
pas. Une barre de recherche dessinee par Plume est donc possible, au prix de
desactiver `AreBrowserAcceleratorKeysEnabled` pour n'en avoir qu'une seule, ce
qui coute F12 et Ctrl+P.

### Les onglets survivent a la fermeture

La liste des onglets ouverts est ecrite dans `profil/session.json` et rouverte
au lancement suivant. L'enregistrement est freine a une ecriture toutes les deux
secondes au plus : sans ce frein, une page qui se recharge toute seule ferait
une ecriture disque a chaque fois. La fermeture, elle, force l'ecriture avant de
demonter quoi que ce soit.

Le fichier retient **une liste de fenetres**, pas une simple liste d'onglets, ce
qui evite de tout reecrire maintenant que Plume en ouvre plusieurs. Deux
plafonds : 20 onglets restaures par fenetre, 4 fenetres, parce qu'un onglet
coute environ 390 Mo.

Chaque fenetre y range aussi **sa position, sa taille et son etat agrandi**.
Rouvrir Plume redonne donc l'ecran tel qu'il etait, y compris quand une fenetre
avait ete posee sur un second moniteur. Une precaution : les bornes enregistrees
sont verifiees contre les ecrans presents au lancement, faute de quoi une fenetre
laissee sur un moniteur debranche reviendrait hors du champ visible, vivante mais
introuvable. Si elle ne croise plus aucun ecran, elle reprend la taille par
defaut au centre.

### Plusieurs fenetres

`Ctrl` + `N` ouvre une fenetre de plus, sur le meme fil et le meme profil.

Deux details ont demande attention. `Application.Run(formulaire)` arrete la
boucle de messages quand **ce** formulaire se ferme, ce qui tuait les autres
fenetres : il faut un `ApplicationContext` sans fenetre principale, et sortir
soi-meme quand la derniere se ferme. Et le canal local du port 47821 n'est
ouvert que par la premiere fenetre ; une adresse recue est dirigee vers la
derniere fenetre activee.

### La page d'accueil est un fichier local

`profil/accueil.html`, reecrit a chaque ouverture pour refleter les favoris et
le compteur de publicites bloquees. Rien n'y est distant : ni police, ni feuille
de style, ni image. Les icones des favoris y sont incluses en base64, une page
`file://` n'ayant pas toujours le droit de lire d'autres fichiers locaux.

C'est aussi ce qui permet a un onglet neuf de **garder le focus dans la barre
d'adresse**, tout selectionne : une page web le lui prend des qu'elle a fini de
charger. WebView2 le reclame quand meme en fin de chargement, d'ou un second
appel au focus quand la page se signale.

La barre d'adresse reste **vide** sur cette page, et l'etoile des favoris y est
masquee : mettre en favori un fichier local propre a chaque installation n'aurait
aucun sens.

> Une adresse `file://` est desormais reconnue comme une adresse par
> `core.est_url`. Sans cela, le bouton Accueil lancait une recherche Google sur
> le chemin du fichier.

### Choisir entre les deux lecteurs

Sur un site video, un bouton apparait dans la barre d'adresse, a gauche de
l'etoile : il fait passer du lecteur de Plume a celui du site, et inversement.
Utile quand l'incrustation se passe mal, ou quand une video refuse de partir.

Le choix est ecrit dans le **stockage local du site**, pas dans un fichier de
Plume. Une seule source de verite, et la preference suit naturellement le
domaine. Le script injecte le relit avant que la page ne s'execute, seul moment
ou l'on peut encore decider de museler le lecteur d'origine ; il sort alors sans
rien faire, et aucun lecteur mpv ne demarre.

### Favoris

L'étoile à droite de la barre d'adresse ajoute ou retire la page courante. Les
favoris s'affichent alors dans une barre sous la barre d'adresse : clic pour
ouvrir, clic milieu pour ouvrir dans un onglet, croix au survol pour retirer.

Ils vivent dans `profil/favoris.json`, donc **hors du paquet distribué** : ce
que quelqu'un met en favori le regarde.

Chaque favori porte **l'icône de son site**, rangée sous le nom d'hôte dans
`profil/favicons/`. Elle n'est conservée que pour les sites mis en favori :
garder celle de tout ce qui est visité ferait grossir le dossier sans fin et
reviendrait à tenir la liste des sites fréquentés. À défaut d'icône, une étoile
est tracée en GDI+, comme le cadenas, pour la raison habituelle : les polices
d'icônes de Windows ne sont pas rendues par GDI+.

> **Les favicons n'avaient jamais fonctionné, nulle part, pas même dans les
> onglets.** Le flux rendu par `GetFaviconAsync` n'est pas repositionnable, or
> `Image.FromStream` l'exige : il levait `NotImplementedException`, avalée par
> le `try` qui entoure l'appel. Correction : recopier le flux dans un
> `MemoryStream`, puis en tirer un `Bitmap` autonome.

`texte_tronque` écrit par défaut **en haut** de son rectangle, ce qui le
désalignait de toute icône posée à côté, elle centrée. D'où le paramètre
`milieu`.
La largeur d'un favori est **mesurée** (`MeasureString`) et non estimée au
nombre de lettres, sans quoi des titres qui tenaient largement ressortaient
coupés ; la place de la croix est réservée en permanence pour que le titre ne
se raccourcisse pas au passage de la souris.

### Le clavier ne traverse pas WebView2

**Piège majeur, et il était là depuis le début.** `KeyPreview` du formulaire ne
voit **rien** dès que la page a le focus : WebView2 traite les frappes dans son
propre processus, elles ne passent jamais par la boucle de messages de WinForms.
Tous les raccourcis du navigateur (`Ctrl+L`, `Ctrl+T`, `Ctrl+W`, `Ctrl+Tab`,
`F5`) étaient donc muets dès qu'on avait cliqué dans la page, c'est-à-dire
presque toujours.

Le symptôme trompe : les raccourcis marchent parfaitement au démarrage et après
un clic sur une barre, ce qui donne l'impression d'un problème intermittent.

Correction en une ligne, dans `Onglet.__init__` : le contrôle WinForms de
WebView2 réexpose les touches d'accélérateur par son propre événement `KeyDown`,
auquel on branche le gestionnaire du navigateur.

### L'onglet actif se signale sur tout son pourtour

Il portait un simple trait d'accent en haut, insere de dix pixels de chaque
cote : coupe, il donnait l'impression d'un surlignage rate plutot que d'une
selection. Il a desormais un fond teinte du violet de Plume et un contour
complet, haut et cotes. Sur un fond sombre, un pastel clair ecraserait le texte
blanc : c'est donc une teinte sombre violette, pas un aplat clair.

Le contour est trace trois pixels plus bas que la barre, de sorte que son trait
du bas tombe hors du panneau et n'est jamais rendu : l'onglet reste ouvert vers
la page, comme un onglet doit l'etre. Verifie au pixel : accent sur le bord haut
et les bords lateraux, teinte seule sur la derniere ligne.

### Changer d'onglet fait glisser la page

Cliquer sur un onglet ne remplace plus la page d'un coup : la sortante part d'un
cote, l'entrante arrive de l'autre, en trois dixiemes de seconde. L'onglet de
gauche fait glisser vers la gauche, celui de droite vers la droite ; deux
onglets plus loin, c'est le meme geste, sans surenchere. Le reglage
`glissement_onglets` le coupe.

Ce sont **les vues WebView2 elles-memes** qui bougent, pas des images d'elles :
leur taille ne change jamais, seulement leur position, donc la page n'est jamais
remise en page et une video ne saute pas. Le panneau qui les contient les rogne
aux bords.

Trois choses sont allees de travers avant que ce soit regardable, et chacune
apprend quelque chose.

**`Application.DoEvents()` n'anime rien.** La premiere version faisait tourner
une boucle avec `DoEvents` entre deux images. Mais `DoEvents` distribue les
messages en attente, donc laisse **re-entrer un second changement d'onglet au
milieu du premier** : le glissement en cours finissait alors son travail sur un
onglet qui n'etait plus le bon et cachait la vue devenue active. Ctrl+1 et
Ctrl+9 restaient sans effet. L'animation est confiee au minuteur deja present,
qui rend la main entre chaque image.

**Deux etats ne peuvent pas porter le meme nom.** `self._glisse` designait depuis
toujours le deplacement de la fenetre. En le reutilisant pour le glissement de
page, le relachement de la souris — qui remet `_glisse` a None a la fin du clic,
*dans le meme clic* que l'activation — effacait le glissement avant son premier
battement. Les vues restaient ou le montage venait de les poser, l'entrante hors
cadre : le changement d'onglet paraissait sans aucun effet. C'est desormais
`_glisse` pour la fenetre et `_glisse_page` pour la page.

**Deux fenetres se deplacent ensemble ou pas du tout.** Chaque vue est une
fenetre a part entiere. Deux `SetWindowPos` separes, c'est deux repeintures : la
premiere page bougeait, la seconde suivait une image plus tard, et ce decalage
se lit exactement comme un saut de pixels au bord commun. Elles passent par une
transaction `DeferWindowPos`, que Windows applique d'un bloc. Et l'abscisse est
**arrondie**, non tronquee : `int()` rogne vers zero, donc dans un sens et pas
dans l'autre, ce qui rendait le pas irregulier d'une image a l'autre.

Reste une source de saccade qui n'est pas corrigee : le minuteur WinForms tourne
sur l'horloge Windows a 15,6 ms, sans verrouillage de phase. Les battements
n'arrivent pas a intervalle regulier, et comme l'animation se cale sur le temps
ecoule, un battement en retard fait un pas plus grand. Monter la resolution
d'horloge du processus le corrigerait, au prix de la consommation.

### Un onglet neuf arrive, un onglet ferme tombe

Le meme mouvement sert aux trois gestes. Un onglet neuf se pose toujours a
droite : sa page arrive donc du meme cote que si on l'avait choisi dans la
barre. Pas pendant une reprise de session, ou vingt pages defileraient au
lancement.

La page d'un onglet ferme, elle, **tombe** hors du cadre, en accelerant comme
une vraie chute : le carre du temps, et non une progression lineaire, qui
donnerait un ascenseur. Elle n'est donc detruite qu'a l'arrivee, ce qui impose
un ordre precis dans `fermer()` : la vue est detachee du panneau **avant**
l'activation de la page suivante, et remise au premier plan **apres**. La
nouvelle page se met elle aussi au premier plan en s'activant : lancee trop
tot, la page condamnee tomberait derriere elle, invisible.

La page qui prend la place ne bouge pas. Une arrivee laterale pendant que
l'autre descend laisserait la zone liberee par la chute vide le temps de la
traversee, un trou au milieu de l'ecran : mieux vaut qu'elle soit deja la et que
la chute la decouvre.

Dans la barre, rien a ajouter : l'onglet ferme retrecit et les suivants se
decalent pour combler, ce que `_fantomes` et `_plan_onglets` faisaient deja.

Fermer un onglet d'arriere-plan n'anime rien : il n'y a rien a montrer.

### L'incrustation couvre le lecteur du site, elle ne le frise pas

Une barre de progression rouge apparaissait sous l'incrustation, sur quelques
pixels au bord gauche. La page mesurait son lecteur puis arrondissait
**separement la position et la largeur** : `round(gauche) + round(largeur)`
n'est pas `round(gauche + largeur)`, et le rectangle se retrouvait un pixel trop
court, d'un cote ou de l'autre selon les decimales.

La regle est maintenant plancher au bord proche, plafond au bord lointain, plus
deux pixels de debord. La marge du lecteur etant noire, un surplus ne se voit
pas ; un manque, si.

Mesure sur 20 000 rectangles fractionnaires a sept facteurs d'echelle d'ecran :
la nouvelle regle ne decouvre **jamais** le lecteur, l'ancienne le decouvrait
dans **87 %** des cas. Ce n'etait pas la malchance d'une configuration, c'etait
le cas courant.

### Le lecteur d'un onglet de fond reste cache

Une page d'arriere-plan continue de tourner et renvoie la zone de sa video
toutes les 120 ms. Ces mesures etaient transmises sans regarder quel onglet
etait actif : comme mpv est une fenetre de premier niveau, rien dans la pile des
fenetres ne l'empechait de se poser **par-dessus la page qu'on regardait**.
Changer d'onglet le cachait bien, mais le message suivant le rouvrait 120 ms
plus tard. On voyait deux lecteurs a la fois.

`replacer()` est le seul point de passage : la zone est retenue pour tous les
onglets, le lecteur n'est montre que pour celui qu'on regarde.

Le meme defaut expliquait un lecteur affiche a la taille d'un autre ecran. Une
vue WebView2 cachee **ne refait pas sa mise en page** : l'onglet de fond gardait
la mesure prise a la taille de fenetre precedente, et c'est elle qu'il
rediffusait. Chaque mesure retient donc maintenant la taille de page qui l'a
produite ; a l'activation, si la fenetre n'a plus cette taille, la mesure est
jetee et le lecteur attend les 120 ms que la page met a se redire, plutot que
d'apparaitre au mauvais format.

### Un plantage laisse une trace

Une exception dans un rappel WinForms — minuteur, dessin, clic — remontait dans
le vide : la fenetre disparaissait sans un mot. Le journal ne servait a rien,
puisqu'il fallait avoir pose `PLUME_DEBUG` **avant**. `Application.ThreadException`
et `AppDomain.UnhandledException` sont maintenant interceptes, et la pile
complete part dans `profil/plantages.txt`, sans condition et sans reglage. Le
battement d'animation a son propre filet : une animation ratee doit couter
l'animation, pas la fenetre.

C'est la seule trace qui restera d'un plantage survenu chez quelqu'un d'autre.

### L'apparence est dessinée

WinForms ne sait pas faire d'onglets arrondis ni de champ en pilule : ces formes
sont tracées à la main en GDI+ dans `interface.py`, sur les événements `Paint`.
On obtient une barre d'onglets et une barre d'adresse dans l'esprit de Firefox,
avec le favicon de chaque site, plutôt que des rectangles gris.

Trois pièges rencontrés, tous silencieux :

- **les polices d'icônes de Windows** (`Segoe Fluent Icons`, `Segoe MDL2
  Assets`) ne sont pas rendues par GDI+ : elles n'affichent que des rectangles
  vides. Les flèches viennent donc de `Segoe UI Symbol`, et le cadenas de la
  barre d'adresse est **dessiné** plutôt que tapé ;
- **pythonnet 3 refuse la conversion implicite d'un entier en énumération**
  (`StringFormatFlags.NoWrap` et non `0x4000`) ;
- une exception levée dans un `Paint` **est avalée par WinForms** : la barre
  reste simplement vide, sans message. D'où l'utilité de faire tourner le code
  de rendu hors fenêtre, sur un `Bitmap`, pour que les erreurs remontent.

Le double tampon des panneaux est activé par réflexion (la propriété est
protégée dans WinForms), sans quoi les barres scintillent au survol.

### WebView2 a une affinité de thread, et elle ne se négocie pas

Le favicon a d'abord été récupéré ainsi : un thread annexe appelant
`GetFaviconAsync(...).Result`. L'application se figeait au démarrage, et Windows
la fermait avec un « Application Hang ». Pas une exception, pas de message :
juste une fenêtre qui cesse de répondre.

**Toute méthode de WebView2 doit être appelée depuis le thread qui possède la
fenêtre**, et il ne faut jamais attendre une de ses tâches en bloquant. La
version correcte lance la tâche depuis l'événement `FaviconChanged`, qui est
déjà sur le bon thread, et traite le résultat dans un `ContinueWith`.

Le diagnostic est venu de deux choses, pas de la lecture du code : le journal
d'événements Windows (`Application Hang`, et non une erreur applicative), puis
l'isolement, en désactivant le favicon pour voir si le blocage disparaissait.
Une fois la correction faite, quatre lancements de suite sans blocage, en
vérifiant `Responding` et non la seule présence du processus.

### Raccourcis du navigateur

| Touche | Effet |
|---|---|
| `Ctrl` + `T` | nouvel onglet, adresse prete a la saisie |
| `Ctrl` + `Maj` + `T` | rouvrir le dernier onglet ferme |
| `Ctrl` + `N` | nouvelle fenetre |
| `Ctrl` + `Maj` + `N` | nouvelle fenetre privee |
| `Ctrl` + `W` | fermer l'onglet |
| `Ctrl` + `Tab` | onglet suivant |
| `Ctrl` + `Maj` + `Tab` | onglet precedent |
| `Ctrl` + `1` a `8` | aller a cet onglet, `Ctrl` + `9` au dernier |
| `Alt` + `Gauche` `Droite` | reculer, avancer |
| clic du milieu sur un onglet | le fermer |
| clic droit sur un onglet | menu : groupes de travail, fermeture |
| `Ctrl` + `L` | barre d'adresse, tout sélectionné |
| `Ctrl` + `D` | ajouter ou retirer la page des favoris |
| `Ctrl` + `B` | afficher ou masquer la barre des favoris |
| `Ctrl` + `+` `-` | zoom du site, retenu pour la prochaine visite |
| `Ctrl` + `0` | zoom a 100 %, et le site est oublie |
| `F5` | recharger |
| `Entrée` dans la barre | une adresse y navigue, tout autre texte part sur Google |

Un clic dans la barre d'adresse en sélectionne tout le contenu, comme dans les
autres navigateurs, pour qu'une nouvelle adresse remplace l'ancienne d'un coup.
Il faut pour cela reposer la sélection au relâchement du bouton : le clic qui
donne le focus repositionne le curseur juste après et l'annulerait.

**Mesuré sur cette machine :**

| Situation | RAM |
|---|---|
| Plume au repos | **35 Mo** |
| Plume + 14 résultats et leurs miniatures | **49 Mo** |
| Plume + une vidéo dans mpv seul | **~250 Mo** |
| Navigateur, 1 onglet + vidéo incrustée | ~1080 Mo |
| Navigateur, 3 onglets ouverts | ~1470 Mo |
| *(pour comparaison)* un onglet YouTube dans Brave | 600 – 1500 Mo |

**Un onglet coûte environ 390 Mo, et c'est le prix assumé des vrais onglets** :
garder une page vivante pour ne pas la recharger, c'est garder son moteur web en
mémoire. Fermer l'onglet rend cette mémoire, et depuis la veille des onglets, ne
plus le regarder en rend déjà une partie sans rien fermer (voir
« Les onglets qui dorment »).

Le navigateur coûte donc ce que coûte un navigateur. Ce que Plume économise
vraiment est ailleurs :

- le *lecteur vidéo* de la page ne démarre jamais, or c'est lui qui pèse le plus
  et fait chauffer le CPU ; mpv décode en GPU à sa place ;
- l'interface, elle, reste à 35 Mo et sert de point de départ permanent ;
- pour regarder sans naviguer, « lire dans mpv seul » coûte ~250 Mo, sans aucun
  moteur web.

Une première version utilisait WebView2 pour l'interface : elle coûtait
**417 Mo** (6 process Chromium pour afficher 10 Ko de HTML). D'où tkinter.

## Utilisation

Double-clic sur **`Plume.exe`** : le navigateur s'ouvre sur **Google**.

Aucune fenêtre de console n'apparaît, à aucun moment : le lanceur passe par
`pythonw.exe`, tous les processus lancés ensuite (mpv, yt-dlp, streamlink) le
sont avec le drapeau `CREATE_NO_WINDOW`, et la mesure mémoire interroge
directement l'API Windows au lieu d'appeler `tasklist`.

`Plume.vbs` fait la même chose et reste disponible en secours.

### Barre des tâches

Chaque interface déclare son identité à Windows
(`SetCurrentProcessExplicitAppUserModelID`) avant de créer sa fenêtre. Sans
cela, Windows regroupe la fenêtre sous Python et affiche l'icône de Python dans
la barre des tâches, puisque le processus hôte est `pythonw.exe`.

### L'interface de recherche vidéo

`Plume-Recherche.vbs` ouvre l'interface légère en tkinter (~35 Mo) : elle
cherche des vidéos sans charger le moindre moteur web, et envoie ce qu'on
choisit au navigateur, qui en fait un onglet.

C'est le mode le plus économe pour simplement regarder quelque chose.

| Saisie | Effet |
|---|---|
| n'importe quel texte | cherche des vidéos, résultats listés **dans Plume** |
| une URL, vidéo ou non | ouvre un onglet dessus dans le navigateur |
| bouton *Google* | envoie la saisie sur Google, dans un onglet |

Un clic sur un résultat ouvre **la page du site**, pour garder les
recommandations, avec mpv incrusté à la place du lecteur. Le clic droit propose
« Lire dans mpv seul », sans moteur web du tout.

### Raccourcis clavier

| Touche | Effet |
|---|---|
| `Entrée` | lance la recherche, ou ouvre le résultat sélectionné |
| `↑` `↓` | parcourt les résultats, depuis la barre de saisie directement |
| `Échap` | annule la sélection, puis efface la barre |
| `Ctrl` + `L` | revient à la barre et sélectionne son contenu |
| `Ctrl` + `↑` `↓` | rappelle les recherches précédentes |
| `F5` | relance la dernière recherche |
| `Ctrl` + `Q` | quitte |
| `F11` | plein écran sans bordure |
| clic droit sur un résultat | ouvrir la page, lire dans mpv seul, copier le lien |

L'indicateur en bas à droite affiche la RAM réellement consommée
(Plume + les mpv en cours).

## Donner Plume à quelqu'un

```
python outils\construire.py
```

Produit `..\Plume-paquet\Plume.zip` : environ 147 Mo compressés. Il contient Python, les bibliothèques, mpv, Deno et un yt-dlp
autonome. Sur la machine d'arrivée, rien à installer hormis le runtime WebView2,
présent d'origine sur Windows 11.

Trois points ont demandé un traitement particulier :

- **le `yt-dlp.exe` installé par pip ne fait que 0,1 Mo** : c'est un amorceur qui
  a besoin du Python de la machine. Comme mpv l'appelle par son chemin, le
  script en compile un autonome, **en dossier et non en fichier unique** (voir
  plus bas) ;
- **il n'y a plus d'interpréteur séparé** dans le paquet : pour lancer
  streamlink en sous-processus, l'exécutable se relance lui-même avec un rôle
  (`Plume.exe --streamlink …`) ;
- **`webview` n'y est pas installé**, seules ses DLL sont copiées : la recherche
  des assemblages passe par `sys._MEIPASS` avant `find_spec`.

> **Le dossier `profil/` n'entre jamais dans le paquet.** Il contient les
> cookies de session Google en clair : le distribuer donnerait accès au compte.
> La construction le vérifie avant de compresser et refuse d'aboutir s'il en
> trouve la moindre trace.

Celui qui reçoit le paquet devra **se connecter à YouTube dans Plume** : sans
session, YouTube refuse de livrer le flux. Le bandeau d'erreur le dit
explicitement dans ce cas, et `LISEZ-MOI.txt` accompagne le paquet.

### Ne jamais compiler en fichier unique ce qui sera distribué

Les premiers destinataires du paquet ont vu Windows le bloquer en le qualifiant
de **cheval de Troie**. Ce n'était pas une infection, mais la conséquence directe
d'un choix de compilation.

`yt-dlp.exe` était produit par PyInstaller en mode `--onefile`. Un exécutable de
cette forme se décompresse dans `%TEMP%\_MEIxxxx` à chaque lancement, puis
exécute ce qu'il vient d'y écrire. Vu d'un antivirus, écrire un exécutable dans
un dossier temporaire et le lancer est la définition même d'un dropper, d'où la
détection comportementale `Trojan:Win32/Wacatac.B!ml`.

La construction utilise désormais `--onedir`. Mesure avant et après, sur une
extraction YouTube réelle réussie dans les deux cas :

| Forme | Dossiers `_MEI*` créés dans `%TEMP%` |
| --- | --- |
| `--onefile` | 1 |
| `--onedir` | 0 |

`core.py` cherche `outils-externes/yt-dlp/yt-dlp.exe` avant l'ancien chemin à
plat, donc les deux dispositions fonctionnent.

**Piège de diagnostic :** une analyse statique ne reproduit rien. `MpCmdRun
-Scan` sur les binaires ne trouve aucune menace, y compris après leur avoir posé
la marque « vient d'Internet » (flux `Zone.Identifier`, `ZoneId=3`) qui déclenche
l'analyse cloud renforcée. La détection est comportementale : elle n'existe qu'à
l'exécution. Un scan statique propre ne prouve donc rien.

### Avertissements Windows au premier lancement

Le paquet n'est pas signé. Sur les quatre exécutables livrés, seul `deno.exe`
porte une signature valide (Deno Land Inc.). Un certificat coûterait 200 à 400 €
par an, ce qui n'a pas été retenu pour une poignée de destinataires.

Deux messages différents peuvent donc apparaître, et il ne faut pas les
confondre :

- **fenêtre bleue, « Windows a protégé votre ordinateur »** : SmartScreen, un
  simple avertissement de réputation. « Informations complémentaires », puis
  « Exécuter quand même » ;
- **alerte rouge de l'antivirus** : un vrai blocage, traité à la section
  précédente.

Le paquet contient `EMPREINTES.txt`, généré à la construction, qui liste le
SHA-256 de chaque exécutable livré. Le destinataire peut ainsi vérifier lui-même
que le fichier reçu est bien celui qui a été construit avant de passer outre une
alerte. **Ne pas conseiller d'exclusion antivirus permanente** : la manœuvre
fonctionne, mais elle installe l'habitude de désactiver une protection pour faire
tourner un programme.

Conseil utile à transmettre : faire clic droit sur le zip, Propriétés, cocher
« Débloquer » **avant** de décompresser. Sinon la marque « vient d'Internet » se
propage à chacun des fichiers extraits.

## Configuration (`config.json`)

```json
{
  "moteur_recherche": "https://www.google.com/search?q={q}",
  "qualite_max": 1080,
  "fps_max": 60,
  "nb_resultats": 14,
  "miniatures": true,
  "cookies_navigateur": false,
  "mpv_extra": [],
  "veille_onglets": 90,
  "intro": true,
  "glissement_onglets": true
}
```

- `qualite_max` / `fps_max` : plafond de résolution demandé à yt-dlp.
  Baisser à `720` réduit encore la RAM et la bande passante.
- `miniatures` : passer à `false` pour une liste purement textuelle (~35 Mo constants).
- `mpv_extra` : arguments mpv supplémentaires, ex. `["--volume=70"]`.
- `moteur_recherche` : remplacer par DuckDuckGo, Brave Search, etc.
- `veille_onglets` : secondes avant qu'un onglet de fond soit mis en sommeil.
  `0` desactive la veille.
- `intro` : l'ouverture dessinee au lancement. `false` pour demarrer sec.
- `glissement_onglets` : le glissement de la page en changeant d'onglet. C'est
  le geste le plus frequent d'un navigateur ; si l'animation gene, ce reglage
  la coupe sans rien changer d'autre.
- `youtube_client` : client que yt-dlp déclare à YouTube. **Vide par
  défaut**, et c'est la bonne valeur au 5 septembre 2026 ; ce réglage
  s'inverse au gré des changements de YouTube, voir plus bas.

### Faire accepter la lecture par YouTube

YouTube exige **deux choses à la fois**, et l'une sans l'autre ne suffit pas.
Mesuré : cookies seuls, échec ; solveur seul, échec ; les deux, lecture
correcte.

**1. Une session authentifiée, mais seulement en repli.** Sans elle :
*« Sign in to confirm you're not a bot »*. Les cookies ne peuvent pas être lus dans la base du profil, que le
navigateur verrouille tant qu'il tourne (`Permission denied`). Plume les exporte
donc lui-même, via l'API de WebView2, dans `profil/cookies.txt` au format
Netscape. L'export a lieu au premier chargement de page et avant chaque lecture.

#### La session fait echouer certaines lectures

**Envoyer la session authentifiée fait refuser le flux par YouTube sur une
partie des vidéos**, avec une erreur **HTTP 403** au téléchargement, alors que
l'extraction, elle, a parfaitement réussi. Mesuré le 5 septembre 2026 :

| Configuration | Lectures réussies |
|---|---|
| avec la session | **2 sur 4** |
| sans la session | **4 sur 4**, en 1080p |

Sur un échantillon plus large : **6 sur 10 avec la session, 10 sur 10 sans**.

Plume lit donc **sans cookies par défaut**, et n'y recourt qu'en repli : si mpv
s'arrête dans les douze secondes, la lecture est relancée une fois avec la
session, ce qui couvre les vidéos à restriction d'âge et le contrôle
anti-robot. Une seule reprise, jamais deux.

L'âge de la vidéo n'y est pour rien, contrairement à ce qu'on pourrait croire :
huit vidéos publiées entre 1,3 h et 13,9 h avant le test se lisent toutes, en
1080p, et démarrent en moins de 4,5 s.

> **`profil/cookies.txt` contient tes cookies de session YouTube en clair.**
> Quiconque obtient ce fichier peut se faire passer pour toi sur ton compte
> Google. Ne le partage pas, ne le mets pas dans une sauvegarde publique. Pour
> désactiver l'export, passer `cookies_navigateur` à `false` dans `config.json`,
> au prix de la lecture YouTube.

**2. La résolution d'un défi JavaScript.** Sans elle : *« The page needs to be
reloaded »*. yt-dlp la délègue à **Deno** (`winget install DenoLand.Deno`) et à
un script solveur qu'il télécharge depuis son dépôt GitHub, ce qu'active
`--remote-components ejs:github`. C'est donc du code tiers récupéré à l'exécution
par yt-dlp ; pour le refuser, passer `solveur_distant` à `false`.

Les lives Twitch ne sont concernés par rien de tout cela : ils passent par
streamlink.

### Le lecteur qui ne démarre jamais vraiment

Symptôme : la vidéo essaie de charger, puis rien. Le lecteur repart de zéro sans
jamais aboutir.

Cause : **YouTube ajoute `&themeRefresh=1` à l'adresse juste après le
chargement, puis le retire.** La garde qui évite de relancer une lecture déjà en
cours comparait l'adresse brute. Elle voyait donc trois vidéos différentes en
trois secondes et relançait mpv à chaque fois, chaque relance tuant la
précédente en plein chargement. Relevé dans le journal :

```
2390.2  msg page_video | https://www.youtube.com/watch?v=aqz-KE-bpKQ
2391.3  msg page_video | https://www.youtube.com/watch?v=aqz-KE-bpKQ&themeRefresh=1
2392.2  msg page_video | https://www.youtube.com/watch?v=aqz-KE-bpKQ
```

Correction : `core.cle_video()` compare l'**identité** de la vidéo et non
l'adresse. Pour YouTube c'est l'identifiant `v` ; ailleurs, l'adresse débarrassée
des paramètres de suivi (préfixes `utm_`, `tt_`, plus une liste nommée).
**Ne jamais comparer deux adresses brutes pour décider s'il s'agit de la même
vidéo.**

#### Diagnostiquer un lecteur qui s'arrête

Trois traces, dans cet ordre d'utilité :

- `profil/lecteur.log` : chaque arrêt du lecteur, avec l'adresse, le code de
  sortie, la durée et les dernières lignes de mpv. Cumulatif. Auparavant, la
  sortie d'erreur de mpv n'était même pas capturée et un arrêt au-delà de douze
  secondes ne laissait absolument rien ;
- `profil/mpv.log` : le journal de mpv lui-même, écrasé à chaque lecture ;
- `PLUME_DEBUG=<fichier>` : le journal de Plume, dont les lignes
  `msg page_video` avec l'adresse exacte. C'est lui qui a montré les trois
  adresses ci-dessus.

### Les onglets qui s'ouvraient tout seuls

Un lien voulant une fenetre devient un onglet, pour que rien ne sorte de
l'application. Mais l'evenement `NewWindowRequested` ne distingue pas, en
lui-meme, un clic d'un `window.open` appele par un script : **toute page pouvait
donc ouvrir des onglets d'elle-meme**, publicites passees entre les mailles
comprises.

Le filtre tient dans `args.IsUserInitiated`. Mesure sur une page d'essai : deux
`window.open` differes sont refuses et consignes, un vrai clic sur un lien
`target="_blank"` ouvre bien son onglet.

Les ouvertures sont desormais tracees dans le journal (`PLUME_DEBUG`) : onglet
ouvert, fenetre ouverte, demande recue sur le canal local, popup refusee. Si des
ouvertures inexpliquees reapparaissent, le journal dira laquelle des quatre
voies en est responsable.

### Publicités

Trois niveaux, aucun ne dépend d'une extension :

- **le lecteur n'en voit jamais** : yt-dlp extrait le flux de la vidéo, les
  publicités n'en font pas partie. mpv joue déjà un contenu sans coupure ;
- **les requêtes sont refusées avant d'être émises** : WebView2 filtre une liste
  de motifs (`doubleclick`, `googlesyndication`, `pagead`, `ptracking`…) et
  répond 403. Un filtre par motif plutôt qu'un filtre général, pour ne pas
  ralentir le reste du trafic ;
- **les habillages sont masqués** : bandeaux, superpositions et emplacements
  publicitaires de la page, par une feuille de style injectée.

Sur Twitch, les publicités sont dans le flux lui-même : c'est streamlink qui les
saute, avec `--twitch-disable-ads`.

### Temps de démarrage d'une vidéo

Environ 3 s. Le coût vient du contournement : yt-dlp doit déchiffrer les URLs de
flux, ce que YouTube protège par un défi JavaScript.

#### `youtube_client` s'inverse, il faut le remesurer

**Ne jamais fixer ce réglage de mémoire.** YouTube change de côté régulièrement,
et la bonne valeur d'un jour casse la lecture le lendemain.

- **2026-09-04** : `web_safari` était obligatoire. Le client par défaut extrayait
  plus vite mais donnait des URLs refusées au téléchargement (**HTTP 403**),
  2 lectures sur 5 contre 5 sur 5.
- **2026-09-05** : exactement l'inverse, la valeur est désormais **vide**.

Relevé du 5 septembre, sur deux vidéos :

| Client | Formats obtenus | Lecture de bout en bout |
|---|---|---|
| **vide, laissé à yt-dlp** | 1080p60 | **4 sur 4**, démarrage 3,0 s |
| `web_safari` | aucun, storyboards seuls | **0 sur 4** |
| `web` | aucun, storyboards seuls | non testable |
| `tv` | « The page needs to be reloaded » | non testable |
| `mweb`, `android_vr`, `tv_simply` | format 18 seulement, 360p | non retenu |

Deux symptômes trompeurs, selon le sens de la panne. Soit l'extraction réussit et
c'est le flux qui est refusé (403), donc « la vidéo ne démarre pas » sans erreur
visible. Soit yt-dlp annonce **« Requested format is not available »**, ce qui
fait chercher du côté de `--ytdl-format` alors que le fautif est le client.

Diagnostic sûr : lancer `yt-dlp -F` sur la vidéo. S'il ne sort que des lignes
`sb0` à `sb3`, aucun format vidéo n'a été extrait et c'est le client qu'il faut
changer.

`demuxer-readahead-secs` est en revanche passé de 20 s à 3 s sans contrepartie :
autant de tampon en moins à remplir avant la première image.

Les lives Twitch démarrent en 6 s via streamlink, sans être concernés par ce
déchiffrement.

### A largeur egale, la barre est identique

L'echelle de la barre du lecteur se calculait sur la **seule hauteur**
(`vue.h / 720`). Une video au format cinema, ou le mode theatre, donne un
lecteur large et court : il recevait une barre rabougrie alors qu'il occupe
autant de largeur qu'un 16:9. Une deuxieme version, fondee sur la surface,
attenuait le probleme sans le regler : 1920x1080 et 1920x500 donnaient encore
1,50 et 1,02.

**C'est la largeur qui decide, et elle seule.** Une video en 1920x1080 et la
meme en 1920x500 ont desormais exactement les memes boutons, le meme texte et
le meme curseur. C'est la largeur qu'on a sous les yeux, c'est elle qui doit
commander.

| Lecteur | Hauteur seule | Surface | Largeur |
|---|---|---|---|
| 1280x720, la reference | 1,00 | 1,00 | 1,00 |
| 1920x1080 | 1,50 | 1,50 | 1,50 |
| 1920x500 | 0,75 | 1,02 | **1,50** |
| 1345x590 | 0,82 | 0,93 | 1,05 |
| 640x360 | 0,75 | 0,80 | 0,80 |

Un garde-fou borne la barre au tiers de la hauteur du lecteur, pour le cas
extreme d'une fenetre tres plate. Sur des proportions normales il ne joue
jamais.

**Verifie en comparant les zones cliquables, pas des pixels.** Le fond video
differe d'un format a l'autre et fausserait toute comparaison d'image : on lit
donc la geometrie que le script publie lui-meme. Entre 1920x1080 et 1920x500,
les dix zones sont identiques au pixel, abscisse et taille comprises.

### La barre de commandes est dessinée par mpv

L'OSC de mpv est désactivé (`--osc=no`) au profit de `osc.lua`, écrit pour
Plume : lecture/pause, ligne de temps avec infobulle de position, volume, plein
écran, et quatre menus (qualité, vitesse, sous-titres, pistes audio).

**Une barre en HTML dans la page était impossible.** La fenêtre mpv est posée
par-dessus la vue web : tout élément HTML passerait dessous. Une barre en
fenêtre séparée, dessinée en GDI+ comme le reste de Plume, aurait fait une
troisième fenêtre à maintenir au bon endroit et au bon plan, avec un cas plein
écran à traiter à part. Dessiner dans la vidéo évite les deux problèmes.

Quatre pièges, tous silencieux :

- **`mp.assdraw` multiplie les coordonnées par 8** (2^(scale-1)) pour gagner en
  précision sous-pixel. La balise doit reprendre le même facteur, `\p4` et non
  `\p1`, sinon le tracé sort du cadre sans la moindre erreur. Une passe de rendu
  complète y est passée : le texte s'affichait, aucune forme.
- **l'ASS ne connaît pas le dégradé** : il s'approche par bandes. Sept laissaient
  des marches franches, il en faut une trentaine avec une progression courbe.
- **pas de police d'icônes**, même raison qu'en GDI+ : tout est tracé en
  vectoriel, y compris la coche des menus.
- **`--script-opts-append` ne prend qu'une paire clé=valeur.** Une liste séparée
  par des virgules part entièrement dans la valeur de la première clé, et mpv
  répond `Can't convert ... to boolean!`. Une option par argument.

Le contraste a été mesuré, pas estimé à l'œil : sur une vidéo au fond blanc, le
gris de `interface.py` tombait à 2,8 pour 1, sous le seuil lisible. Dégradé
renforcé et gris éclairci, on est à **6,9 pour 1**.

Le changement de qualité relance le flux (`loadfile ... replace`) et reprend la
position dans `file-loaded` : mesuré à 2 s. Ne pas passer par l'option `start`,
elle resterait active pour les lectures suivantes. Le menu qualité est masqué
pour les lives, qui arrivent par un tube depuis streamlink et dont la qualité se
règle du côté de celui-ci. Les sous-titres remontent (`sub-pos` 90) tant que la
barre est affichée, sinon ils se posent dessus. Un menu se plafonne et défile :
une conférence TED propose 27 langues de sous-titres.

#### Cliquer l'image met en pause

Un clic dans l'image bascule lecture/pause, avec un retour visuel au centre :
un disque qui grandit en s'effaçant, portant le symbole de l'état obtenu.

Deux points méritent d'être retenus :

- **deux progressions distinctes, et c'est ce qui fait tout.** Le disque grandit
  vite puis ralentit, tandis que l'effacement démarre doucement. Avec une seule
  courbe pour les deux, l'animation avait pratiquement disparu au bout de
  160 ms, mesuré en capture ;
- **mpv envoie `MBTN_LEFT` pour les DEUX appuis d'un double-clic**, en plus de
  `MBTN_LEFT_DBL`. Sans ignorer le second appui, demander le plein écran
  basculait la pause au passage. Le second appui est donc écarté s'il suit le
  premier de moins de 0,32 s, et le gestionnaire du double-clic remet la pause
  comme elle était.

Un clic sur le fond de la barre ne déclenche rien : ce n'est pas l'image.

La cadence de dessin est passée de 12 à 30 images par seconde pour l'animation,
sans coût : le dessin n'est renvoyé à mpv que s'il a changé.

### Vérifier le rendu, et le tester vraiment

`python outils\apercu_barre.py` rend la barre dans des images, sur une mire
générée par FFmpeg, sans réseau. Il s'appuie sur `screenshot-to-file ... window`
de mpv, qui se capture lui-même OSD compris : c'est la seule façon fiable de
juger le dessin, une capture d'écran composant mal les surfaces de mpv et de
WebView2.

Le crochet IPC `plume-test` permet de poser le curseur et d'ouvrir un menu sans
souris. **Il ne prouve rien pour le survol, la molette et le clic** : le script
relit la position réelle du curseur à chaque événement, donc la valeur simulée
est écrasée aussitôt. Ces trois-là se testent avec une vraie souris
(`SetCursorPos` puis `mouse_event`), en rendant le curseur à sa place ensuite.

### Plusieurs écrans, et le lecteur qui suit la fenêtre

Le lecteur mpv est une fenêtre à part, posée sur la page : rien ne le déplace
tout seul quand la fenêtre bouge. Il était repositionné à la mesure suivante de
la page, soit jusqu'à 120 ms plus tard, et traînait donc visiblement derrière.

Il est maintenant replacé sur les événements `Move` et `Resize` de la fenêtre,
à partir de la dernière zone connue. Mesuré en déplaçant la fenêtre par pas :
**dérive de 0 pixel**, contre un décalage net auparavant.

**L'agrandissement n'utilise pas `WindowState.Maximized`**, et il a fallu trois
essais pour en arriver là.

`MaximizedBounds` fige des **coordonnées absolues**. Agrandie sur un second
écran, la fenêtre repartait aux coordonnées de l'écran d'origine : elle quittait
purement et simplement l'écran où l'on travaillait. Et le recalculer depuis
`Resize` enclenche une boucle, puisque modifier cette propriété provoque
elle-même un redimensionnement.

`WM_GETMINMAXINFO`, pourtant la méthode habituelle pour une fenêtre sans
bordure, ne fonctionne pas ici : le message **n'atteint jamais** le `WndProc` de
la classe, WinForms le traitant en amont. Vérifié en journalisant sa réception,
qui n'a jamais eu lieu.

La fenêtre reste donc toujours à l'état `Normal`, et l'agrandissement pose
simplement `Bounds` sur la zone de travail de l'écran courant. La taille
précédente est mémorisée pour la restauration, avec une valeur de repli définie
au démarrage : sans elle, la fenêtre démarrant agrandie, « restaurer » n'avait
nulle part où revenir et le bouton semblait sans effet.

Vérifié sur les trois écrans (deux en 1920x1080, un en 2560x1440) : la fenêtre
occupe la zone de travail et **reste sur l'écran où elle se trouve**. Bascules
répétées : alternance propre entre deux tailles.

À noter, l'application **n'est pas déclarée sensible au DPI**. Cela ne se voit
pas ici, les trois écrans étant à 100 %. Si un écran passait à 125 ou 150 %,
Windows étirerait l'image et les coordonnées du lecteur se décaleraient : il
faudrait alors passer l'application en « par écran » et revoir les tailles
fixes des barres.

### Une vidéo par onglet

Chaque onglet possède **son propre lecteur mpv**. Changer d'onglet ne tue pas la
vidéo : elle est seulement masquée, et reprend où elle en était au retour, sans
recharger. Fermer l'onglet, en revanche, arrête bien son lecteur.

C'est ce qui distingue « mettre de côté » de « détruire » : sans cela, revenir
sur un onglet imposait de tout recharger, soit plusieurs secondes à chaque
aller-retour.

### Diagnostiquer un problème

`Diagnostic.vbs` lance Plume en consignant ce qu'il fait dans
`diagnostic.txt` : messages reçus des pages, lancement du lecteur, erreurs.
Reproduire le problème, fermer Plume, puis lire le fichier.

Une lecture qui démarre normalement y ressemble à ceci :

```
msg page_video | actif=True | https://www.youtube.com/watch?v=...
video : https://www.youtube.com/watch?v=...
  demarrer -> {'ok': True}
```

Si `page_video` n'apparaît pas, la page n'a pas été reconnue comme page vidéo.
Si `demarrer` renvoie une erreur, mpv n'a pas pu être lancé. Si tout est
présent mais que rien ne s'affiche, le lecteur tourne sans être visible : c'est
alors un problème de position ou de découpe, pas d'extraction.

### Si la lecture échoue quand même

YouTube bloque par moments l'extraction du flux, avec ce message :

```
Sign in to confirm you're not a bot
```

Le blocage vise l'adresse IP, pas l'application, et il est temporaire. Il se
déclenche facilement après des requêtes répétées. Deux leviers :

- `youtube_client` accepte une liste de clients séparés par des virgules
  (`tv`, `ios`, `android_vr`, `web_safari`…), essayés dans l'ordre. Quand
  le blocage est partiel, en désigner un autre suffit. Le vider rend la
  main à yt-dlp, ce qui est le bon réglage aujourd'hui ;
- quand tous sont refusés, il n'y a qu'à attendre. Les lives Twitch, eux, ne
  sont pas concernés : ils passent par streamlink.

**Un échec de lecture affiche désormais un bandeau dans la page.** Auparavant la
zone du lecteur restait simplement vide, sans rien expliquer : on ne pouvait pas
distinguer un refus de YouTube d'une panne de l'application.
- `cookies_navigateur` : exporte les cookies pour yt-dlp. **Nécessaire à la
  lecture YouTube**, voir plus bas.
- `solveur_distant` : autorise yt-dlp à télécharger le script qui résout le défi
  JavaScript de YouTube. Nécessaire aussi.

## Ce que serait un navigateur vraiment different

Ce chapitre n'est pas de la documentation, c'est une position. Elle vient de ce
qu'on a mesure en construisant Plume, pas d'une envie de faire moderne.

### Le point de depart : personne ne concurrence la coquille

Ecrire un moteur de rendu est hors de portee de tout le monde, Google et Apple
exceptes. Tous les navigateurs dits alternatifs sont donc la meme chose : une
coquille autour de Chromium. Et pourtant ils se ressemblent tous, parce qu'ils
copient la coquille de Chrome au lieu de la repenser. C'est precisement la que
la place est libre : **le moteur est verrouille, la coquille ne l'est pas**, et
c'est elle qui decide de ce que le navigateur fait pour vous ou contre vous.

Plume en est une preuve minuscule mais reelle : le moteur affiche la page de
YouTube telle quelle, et pourtant le lecteur qui pese le plus n'y demarre
jamais. Rien de tout cela n'a demande de toucher au moteur.

### 1. L'onglet est la mauvaise unite

Un onglet est un document. Ce qu'on fait, ce n'est jamais un document : c'est
une **tache**, qui traverse dix pages, s'interrompt trois jours, et reprend.
D'ou les quarante onglets ouverts de tout le monde : ce ne sont pas quarante
lectures en cours, c'est six taches dont personne n'ose fermer les morceaux.

Un navigateur different regrouperait les onglets **par la chaine qui les a
crees** : un lien ouvert appartient a la page qui l'a ouvert, et l'ensemble
forme un groupe qu'on nomme, qu'on range, qu'on rouvre entier. Fermer ne
serait plus une perte, donc on fermerait. La veille des onglets, deja
implementee ici, est le premier tiers du chemin : une tache mise de cote ne
devrait rien couter du tout, ni memoire, ni place a l'ecran.

### 2. La memoire doit etre visible et negociable

Tous les navigateurs cachent ce qu'ils consomment, et decident seuls quoi
decharger, generalement au pire moment. Plume affiche ses megaoctets et endort
ce qui dort. La suite logique : une ligne par onglet indiquant ce qu'il coute,
et le droit de dire « celui-la, garde-le vivant quoi qu'il arrive » ou
« celui-la, congele-le tout de suite ». **Le budget memoire appartient a celui
qui possede la machine**, pas au navigateur.

### 3. Le navigateur travaille pour le lecteur, pas pour le site

C'est le point qui compte le plus, et c'est celui que Plume prouve deja.

Une page moderne n'est pas un document, c'est un programme que le site fait
tourner chez vous, avec ses interets a lui : son lecteur video qui chauffe le
processeur, son defilement infini, sa banniere de consentement, son bandeau
d'inscription au bout de trois paragraphes. Le navigateur regarde tout cela
sans rien dire.

**La bonne question n'est pas « comment bloquer », c'est « comment
remplacer ».** Bloquer casse la page ; remplacer la rend meilleure. Plume
remplace le lecteur de YouTube par mpv et garde titre, description,
commentaires et recommandations. Le meme principe s'etend a tout composant
couteux et interchangeable : la galerie d'images, la carte, le lecteur audio,
le fil de commentaires charge en cinquante requetes. Un navigateur different
aurait un catalogue de ces substitutions, declaratif, lisible, modifiable par
n'importe qui, au lieu d'une liste de filtres qui ne savent dire que non.

### 4. La confidentialite se prouve, elle ne se promet pas

Tout le monde ecrit « nous respectons votre vie privee ». Personne ne montre
rien. Or un navigateur sait exactement a qui il parle : c'est lui qui ouvre les
connexions.

Un navigateur different en tiendrait le **journal lisible, local, et affiche
sur la page d'accueil** : voila les domaines contactes aujourd'hui, voila ceux
qui ont ete refuses, voila ce que Plume lui-meme a envoye, c'est-a-dire rien.
Une promesse verifiable en trois secondes vaut mieux qu'une charte. Et cela
retourne la charge de la preuve : ce n'est plus a l'utilisateur de croire, c'est
au navigateur de montrer.

### 5. Rien de ferme n'est perdu

La corbeille existe depuis 1985 dans les systemes de fichiers, et un navigateur
perd encore un onglet ferme par megarde. Session, onglets, fenetres, taille des
fenetres, dernier onglet ferme : tout doit revenir. Plume le fait maintenant.
La suite serait de traiter de la meme facon ce qui a ete tape et jamais envoye,
un formulaire a moitie rempli valant souvent plus que la page qui le contient.

### 6. La lenteur ressentie n'est pas la lenteur mesuree

Ce qui use n'est pas la seconde d'attente, c'est de ne pas savoir si quelque
chose se passe. D'ou le fil de progression, qui ne coute rien et change tout.
D'ou, aussi, le fait qu'un onglet endormi se reveille sans rechargement : deux
cents millisecondes de reprise valent mieux que trois secondes de rechargement,
meme quand le rechargement afficherait quelque chose plus tot.

### Ce qu'il ne faut pas faire

Ecrire un moteur : impossible. Coller un assistant automatique dans un panneau
lateral : c'est ce que tout le monde fait cette annee, et cela ne repond a
aucune des six questions ci-dessus. Multiplier les reglages : chaque option est
une decision qu'on n'a pas su prendre.

### Les trois prochaines etapes pour Plume

1. ~~**Groupes de taches**~~ : fait, mais autrement. Le groupement
   automatique a ete retire au profit des **groupes de travail**, enregistres
   et rouverts a la demande : c'est l'habitude qu'on veut retrouver, pas la
   seance en cours. Voir « Groupes de travail » plus haut.
2. **Journal des connexions sortantes**, affiche sur la page d'accueil a cote du
   compteur de publicites bloquees.
3. **Substitutions declaratives** : sortir la regle « remplacer le lecteur de
   YouTube par mpv » du code, en faire un fichier de regles auquel on ajoute un
   site sans toucher a Python.

Aucune de ces trois etapes ne demande un moteur. Toutes tiennent dans la
coquille. C'est bien la que la place etait libre.
