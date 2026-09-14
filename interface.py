# -*- coding: utf-8 -*-
"""
Plume / interface : les elements dessines du navigateur.

WinForms ne sait pas faire d'onglets arrondis ni de champ en pilule : ces
formes sont tracees a la main en GDI+, dans les evenements Paint. On y gagne
une barre d'onglets et une barre d'adresse qui ressemblent a celles d'un vrai
navigateur, plutot qu'a des rectangles gris.

Ce module ne contient que de l'apparence : aucune logique de navigation.
"""
import math

import clr

clr.AddReference("System.Drawing")

from System.Drawing import (Color, Pen, PointF, Rectangle, RectangleF,
                            SolidBrush, StringAlignment, StringFormat,
                            StringFormatFlags, StringTrimming)
from System.Drawing.Drawing2D import GraphicsPath, SmoothingMode
from System.Drawing.Text import TextRenderingHint

# ---- palette, dans l'esprit sombre de Firefox, avec notre violet ----------
FOND_ONGLETS = Color.FromArgb(28, 27, 34)
FOND_NAV = Color.FromArgb(43, 42, 51)
FOND_PAGE = Color.FromArgb(18, 19, 26)
ONGLET_ACTIF = Color.FromArgb(66, 65, 77)
# L'onglet actif tire vers le violet de Plume : la teinte le designe avant
# meme qu'on lise le contour, et sur un fond sombre un pastel clair ecraserait
# le texte blanc.
ONGLET_ACTIF_TEINTE = Color.FromArgb(64, 57, 92)
ONGLET_SURVOL = Color.FromArgb(53, 52, 63)
CHAMP_FOND = Color.FromArgb(28, 27, 34)
CHAMP_BORD = Color.FromArgb(58, 57, 68)
TEXTE = Color.FromArgb(251, 251, 254)
# Coeur des lueurs : un halo qui ne blanchit pas en son centre ne brille
# pas, il grisaille.
BLANC = Color.FromArgb(255, 255, 255)
TEXTE2 = Color.FromArgb(177, 177, 189)
# Onglet endormi : lisible, mais visiblement en retrait.
TEXTE3 = Color.FromArgb(122, 121, 136)
ACCENT = Color.FromArgb(124, 92, 255)
ACCENT_PALE = Color.FromArgb(167, 139, 250)
CROIX_SURVOL = Color.FromArgb(82, 81, 95)
# Le contour de la fenetre. Sans bordure systeme, une fenetre sombre se
# confond avec un fond sombre : on ne voit plus ou elle s'arrete.
BORD_FENETRE = Color.FromArgb(88, 86, 102)
# Fenetre privee : le bord change de couleur, pour qu'on ne se trompe
# jamais de fenetre en croyant etre a l'abri.
BORD_PRIVE = Color.FromArgb(124, 92, 255)

# Couleurs des groupes de taches. Claires, parce que le nom du groupe s'ecrit
# par dessus en sombre : c'est le seul sens de lecture qui reste lisible sur
# une pastille de vingt pixels de haut.
COULEURS_GROUPE = (
    Color.FromArgb(167, 199, 255),   # bleu
    Color.FromArgb(167, 232, 190),   # vert
    Color.FromArgb(247, 205, 150),   # ambre
    Color.FromArgb(240, 180, 205),   # rose
    Color.FromArgb(205, 186, 250),   # violet
    Color.FromArgb(163, 224, 230),   # turquoise
)


def couleur_groupe(indice):
    return COULEURS_GROUPE[int(indice) % len(COULEURS_GROUPE)]


def fond_groupe(indice):
    """La meme couleur, tres attenuee : un fond, pas une tache."""
    c = couleur_groupe(indice)
    return Color.FromArgb(64, c.R, c.G, c.B)


def chemin_arrondi(x, y, largeur, hauteur, rayon, coins="tous"):
    """Trace un rectangle aux coins arrondis.

    `coins` vaut "tous", "haut" (bas laisse droit, pour les onglets), ou
    "pilule" (rayon egal a la moitie de la hauteur).
    """
    if coins == "pilule":
        rayon = hauteur / 2.0
    rayon = max(1.0, min(rayon, min(largeur, hauteur) / 2.0))
    d = rayon * 2.0
    p = GraphicsPath()
    p.AddArc(float(x), float(y), d, d, 180, 90)
    p.AddArc(float(x + largeur) - d, float(y), d, d, 270, 90)
    if coins == "haut":
        p.AddLine(float(x + largeur), float(y + hauteur),
                  float(x), float(y + hauteur))
    else:
        p.AddArc(float(x + largeur) - d, float(y + hauteur) - d, d, d, 0, 90)
        p.AddArc(float(x), float(y + hauteur) - d, d, d, 90, 90)
    p.CloseFigure()
    return p


def preparer(graphiques):
    graphiques.SmoothingMode = SmoothingMode.AntiAlias
    graphiques.TextRenderingHint = TextRenderingHint.ClearTypeGridFit


def remplir_arrondi(graphiques, couleur, x, y, largeur, hauteur, rayon,
                    coins="tous"):
    chemin = chemin_arrondi(x, y, largeur, hauteur, rayon, coins)
    pinceau = SolidBrush(couleur)
    try:
        graphiques.FillPath(pinceau, chemin)
    finally:
        pinceau.Dispose()
        chemin.Dispose()


def contour_arrondi(graphiques, couleur, x, y, largeur, hauteur, rayon,
                    epaisseur=2.0, coins="tous"):
    """Trace le pourtour d'un rectangle arrondi, sans le remplir."""
    chemin = chemin_arrondi(x, y, largeur, hauteur, rayon, coins)
    stylo = Pen(couleur, float(epaisseur))
    try:
        graphiques.DrawPath(stylo, chemin)
    finally:
        stylo.Dispose()
        chemin.Dispose()


def texte_tronque(graphiques, texte, police, couleur, x, y, largeur, hauteur,
                  milieu=False):
    """Ecrit un texte coupe par des points de suspension s'il deborde.

    `milieu` centre le texte verticalement dans son rectangle. Sans cela il se
    pose en haut, ce qui le desaligne de toute icone posee a cote, elle centree.
    """
    format_ = StringFormat()
    format_.Trimming = StringTrimming.EllipsisCharacter
    # pythonnet 3 refuse la conversion implicite d'un entier en enumeration
    format_.FormatFlags = StringFormatFlags.NoWrap
    if milieu:
        format_.LineAlignment = StringAlignment.Center
    pinceau = SolidBrush(couleur)
    try:
        graphiques.DrawString(texte, police, pinceau,
                              RectangleF(float(x), float(y),
                                         float(largeur), float(hauteur)),
                              format_)
    finally:
        pinceau.Dispose()
        format_.Dispose()


def souligner(graphiques, couleur, x, y, largeur, epaisseur=2):
    """Petit trait d'accent, sous l'onglet actif."""
    remplir_arrondi(graphiques, couleur, x, y, largeur, epaisseur,
                    epaisseur / 2.0)


def cercle(graphiques, couleur, cx, cy, rayon, epaisseur=1.0):
    """Cercle vide, centre sur un point."""
    stylo = Pen(couleur, float(epaisseur))
    graphiques.DrawEllipse(stylo, float(cx - rayon), float(cy - rayon),
                           float(rayon * 2), float(rayon * 2))
    stylo.Dispose()


def trait(graphiques, couleur, x1, y1, x2, y2, epaisseur=1.0):
    stylo = Pen(couleur, float(epaisseur))
    graphiques.DrawLine(stylo, float(x1), float(y1), float(x2), float(y2))
    stylo.Dispose()


def centrer(graphiques, texte, police, couleur, rect):
    """Ecrit un texte centre dans un rectangle : glyphes de boutons, croix."""
    format_ = StringFormat()
    format_.Alignment = StringAlignment.Center
    format_.LineAlignment = StringAlignment.Center
    pinceau = SolidBrush(couleur)
    try:
        graphiques.DrawString(texte, police, pinceau,
                              RectangleF(float(rect.X), float(rect.Y),
                                         float(rect.Width), float(rect.Height)),
                              format_)
    finally:
        pinceau.Dispose()
        format_.Dispose()


def cadenas(graphiques, couleur, x, y, hauteur=11):
    """Trace un cadenas.

    Les polices d'icones de Windows (Segoe Fluent Icons, Segoe MDL2 Assets) ne
    sont pas rendues par GDI+ : elles donnent des rectangles vides. Le dessiner
    evite d'en dependre.
    """
    from System.Drawing import Pen, Rectangle as R
    largeur = int(hauteur * 0.82)
    corps = int(hauteur * 0.58)
    haut_corps = y + hauteur - corps
    pinceau = SolidBrush(couleur)
    plume = Pen(couleur, 1.4)
    try:
        graphiques.FillRectangle(pinceau, R(int(x), int(haut_corps),
                                            largeur, corps))
        # l'anse : un demi-cercle pose sur le corps
        anse = int(largeur * 0.62)
        graphiques.DrawArc(plume, float(x + (largeur - anse) / 2.0),
                           float(y + 1), float(anse), float(anse * 1.15),
                           180, 180)
    finally:
        pinceau.Dispose()
        plume.Dispose()


ROUGE_FERMER = Color.FromArgb(232, 17, 35)


# --------------------------------------------------------------------------
# Ouverture : le nom qui s'ecrit
# --------------------------------------------------------------------------
DUREE_INTRO = 2.5          # secondes avant de pouvoir ceder la place


def _part(t, debut, duree):
    """Avancement de 0 a 1 d'une etape qui commence a `debut`."""
    if duree <= 0:
        return 1.0
    return max(0.0, min(1.0, (t - debut) / float(duree)))


def _adouci(p):
    """Ralentit a l'arrivee. La meme courbe que l'ouverture d'un onglet."""
    return 1.0 - (1.0 - p) ** 3


def _couches_halo(couches=7):
    """Elargissements et transparences d'un halo, du plus large au plus serre.

    Quatre couches laissaient voir des anneaux concentriques : une lueur se
    fabrique par une decroissance douce, pas par des paliers. Sept couches
    suffisent a ce que l'oeil n'y lise plus de marches, et sept remplissages
    de quelques pixels ne coutent rien a soixante images par seconde.
    """
    for i in range(couches, 0, -1):
        f = i / float(couches)
        yield 1.0 + 2.2 * f * f, 8.0 + 62.0 * (1.0 - f) ** 1.5


def _halo_etincelle(graphiques, couleur, cx, cy, rayon, force=1.0):
    """Aureole autour de l'etincelle.

    GDI+ ne sait pas melanger en mode additif : le halo s'obtient en empilant
    la meme forme, plus large et plus transparente a chaque couche.
    """
    for elargissement, alpha in _couches_halo():
        etincelle(graphiques, avec_alpha(couleur, alpha * force),
                  cx, cy, rayon * elargissement)


def _halo_disque(graphiques, couleur, cx, cy, rayon, force=1.0):
    """Le meme halo, autour d'un disque, un peu plus etale."""
    for elargissement, alpha in _couches_halo():
        r = rayon * (1.0 + (elargissement - 1.0) * 1.35)
        pinceau = SolidBrush(avec_alpha(couleur, alpha * force))
        graphiques.FillEllipse(pinceau, float(cx - r), float(cy - r),
                               float(r * 2), float(r * 2))
        pinceau.Dispose()


def _equerre(graphiques, couleur, x, y, sx, sy, longueur, epaisseur):
    """Un coin en equerre : deux traits partant du meme angle."""
    remplir_arrondi(graphiques, couleur,
                    min(x, x + sx * longueur), min(y, y + sy * epaisseur),
                    longueur, epaisseur, epaisseur / 2.0)
    remplir_arrondi(graphiques, couleur,
                    min(x, x + sx * epaisseur), min(y, y + sy * longueur),
                    epaisseur, longueur, epaisseur / 2.0)


def peindre_etalement(graphiques, largeur, hauteur, avance):
    """Les quatre coins qui filent vers les bords de la fenetre a venir.

    Le fond est deja couvert par le voile qui efface le logotype : ne restent
    que les equerres et le cadre, qui grandissent avec la fenetre et viennent
    epouser ses bords. L'effet se lit comme une toile qui se tend.
    """
    if avance <= 0:
        return
    douceur = 1.0 - (1.0 - avance) ** 2
    # La longueur part de zero, elle aussi : des equerres deja formees au
    # premier instant se verraient comme un decoupage pose sur la carte.
    longueur = (10.0 + (min(largeur, hauteur) * 0.26 - 10.0) * douceur)
    epaisseur = 3.0
    marge = 1.0
    # Les equerres entrent en fondu et repartent de meme : apparaitre d'un
    # coup a pleine intensite sur la petite carte faisait un sursaut net a la
    # premiere image de l'etirement.
    vif = _part(avance, 0.0, 0.16) * (1.0 - _part(avance, 0.72, 0.28))
    for x, y, sx, sy in ((marge, marge, 1, 1),
                         (largeur - marge, marge, -1, 1),
                         (marge, hauteur - marge, 1, -1),
                         (largeur - marge, hauteur - marge, -1, -1)):
        # la lueur d'abord, plus large et plus pale : sans elle les equerres
        # ressortent comme des baguettes posees sur le fond
        _equerre(graphiques, avec_alpha(ACCENT, 70 * vif), x, y, sx, sy,
                 longueur * 1.06, epaisseur * 3.0)
        _equerre(graphiques, avec_alpha(BLANC, 210 * vif), x, y, sx, sy,
                 longueur, epaisseur)

    # Le cadre se ferme sur la fin : les quatre coins se rejoignent.
    liaison = _part(avance, 0.45, 0.55)
    if liaison > 0:
        # Le cadre finit sur la couleur du bord de fenetre : le raccord avec
        # la vraie fenetre, qui porte le meme liseré, ne se voit pas.
        contour_arrondi(graphiques,
                        avec_alpha(ACCENT_PALE, 150 * liaison * vif),
                        0, 0, largeur - 1, hauteur - 1, 0, 2)
        contour_arrondi(graphiques,
                        avec_alpha(BORD_FENETRE, 255 * liaison),
                        0, 0, largeur - 1, hauteur - 1, 0, 1)


def _peindre_voile_et_coins(graphiques, largeur, hauteur, voile, etalement):
    """Le voile qui efface le logotype, puis les equerres de l'etirement."""
    if voile > 0:
        pinceau = SolidBrush(avec_alpha(FOND_PAGE, 255 * voile))
        graphiques.FillRectangle(pinceau, 0, 0, int(largeur), int(hauteur))
        pinceau.Dispose()
    if etalement > 0:
        peindre_etalement(graphiques, largeur, hauteur, etalement)


def peindre_intro(graphiques, largeur, hauteur, t, police, etalement=0.0,
                  ancre=None, effacement=0.0):
    """Le nom de Plume, lettre a lettre, a l'instant `t` du demarrage.

    Dessine plutot que filme : une video de quelques secondes pese plusieurs
    megaoctets dans un paquet qu'on tient a garder mince, et il faudrait
    demarrer un lecteur avant meme d'avoir une fenetre. Ici, rien a charger.

    `ancre` vaut (dx, dy, largeur, hauteur) pendant l'etirement : le logotype
    est alors compose dans les dimensions de la carte de depart, puis decale
    pour retomber au meme endroit A L'ECRAN. Le recentrer dans une fenetre qui
    grandit le faisait tressaillir d'un pixel a chaque image, les arrondis de
    la position et de la largeur ne tombant pas ensemble.
    """
    preparer(graphiques)
    graphiques.Clear(FOND_PAGE)

    # Dimensions reelles de la fenetre : le voile et les equerres s'y
    # rapportent, meme quand le logotype est compose ailleurs.
    vraie_largeur, vraie_hauteur = largeur, hauteur

    # Un seul voile pour deux usages : l'effacement qui precede l'etirement,
    # et celui qui accompagne l'etirement lui-meme. Le plus opaque gagne.
    voile = max(effacement, min(1.0, etalement * 1.7))
    if voile >= 0.999:
        # Plus rien a montrer du logotype : ne pas le dessiner du tout, plutot
        # que de le couvrir. Une image dessinee au mauvais endroit sous un
        # voile opaque ne se verrait pas, mais elle n'aurait rien a faire la.
        _peindre_voile_et_coins(graphiques, vraie_largeur, vraie_hauteur,
                                1.0, etalement)
        return

    etat = None
    if ancre is not None:
        dx, dy, largeur, hauteur = ancre
        etat = graphiques.Save()
        graphiques.TranslateTransform(float(dx), float(dy))

    mot = "Plume"
    fmt = StringFormat(StringFormat.GenericTypographic)

    def large(texte):
        if not texte:
            return 0.0
        return float(graphiques.MeasureString(texte, police, PointF(0, 0),
                                              fmt).Width)

    l_mot = large(mot)
    rayon_etincelle = police.Size * 0.40
    ecart = police.Size * 0.46
    rayon_point = police.Size * 0.125
    total = rayon_etincelle * 2 + ecart + l_mot + ecart * 0.5 + rayon_point * 2
    x = (largeur - total) / 2.0
    milieu = hauteur / 2.0
    x0_etincelle = x + rayon_etincelle
    haut_texte = milieu - police.Size * 0.74
    # Sous les jambages, pas dessus : a 0.66 le trait mordait sur le bas des
    # lettres. Le point et le trait partagent desormais la meme ligne.
    y_trait = milieu + police.Size * 0.92
    x_point = x + rayon_etincelle * 2 + ecart + l_mot + ecart * 0.5

    # 1. L'etincelle eclot, avec un leger depassement : elle arrive, elle ne
    #    se contente pas d'apparaitre.
    p = _part(t, 0.0, 0.55)
    if p > 0:
        avance = _adouci(p)
        rayon = rayon_etincelle * avance * (1.0 + 0.22 * math.sin(math.pi * p))
        _halo_etincelle(graphiques, ACCENT_PALE, x0_etincelle, milieu, rayon,
                        avance)
        etincelle(graphiques, avec_alpha(BLANC, 255 * avance),
                  x0_etincelle, milieu, rayon * 0.66)
        etincelle(graphiques, avec_alpha(ACCENT_PALE, 235 * avance),
                  x0_etincelle, milieu, rayon)
    x += rayon_etincelle * 2 + ecart

    # 2. Le mot s'ecrit, une lettre apres l'autre, chacune montant a sa place.
    curseur = x
    for i, lettre in enumerate(mot):
        p = _part(t, 0.34 + i * 0.13, 0.38)
        if p > 0:
            avance = _adouci(p)
            pinceau = SolidBrush(avec_alpha(TEXTE, 255 * avance))
            graphiques.DrawString(
                lettre, police, pinceau,
                PointF(float(curseur),
                       float(haut_texte + 16.0 * (1.0 - avance))), fmt)
            pinceau.Dispose()
        curseur = x + large(mot[:i + 1])

    # 3. Le trait file sous le mot jusqu'au point, puis reste, plus discret.
    #    Il relie les deux extremites du logotype au lieu de disparaitre.
    p = _part(t, 0.82, 0.95)
    if p > 0:
        avance = _adouci(p)
        bout = (l_mot + ecart * 0.5 + rayon_point) * avance
        eclat = 1.0 - 0.62 * _part(t, 1.55, 0.45)     # vif, puis pose
        # deux lueurs sous le trait : une large et tres pale, une serree et
        # plus vive. Une seule couche donne une bande, pas une lumiere.
        souligner(graphiques, avec_alpha(ACCENT, 42 * eclat),
                  x - 5, y_trait - 5, bout + 10, 13)
        souligner(graphiques, avec_alpha(ACCENT, 95 * eclat),
                  x - 2, y_trait - 2, bout + 4, 7)
        souligner(graphiques, avec_alpha(ACCENT_PALE, 245 * eclat),
                  x, y_trait, bout, 3)

    # 4. Le point d'accent, pose sur la ligne du trait, qui depasse un peu.
    p = _part(t, 1.32, 0.26)
    if p > 0:
        avance = _adouci(p)
        rayon = rayon_point * avance * (1.0 + 0.35 * math.sin(math.pi * p))
        _halo_disque(graphiques, ACCENT_PALE, x_point, y_trait + 1, rayon,
                     avance)
        pinceau = SolidBrush(avec_alpha(ACCENT_PALE, 255 * avance))
        graphiques.FillEllipse(pinceau, float(x_point - rayon),
                               float(y_trait + 1 - rayon),
                               float(rayon * 2), float(rayon * 2))
        pinceau.Dispose()

    # 5. Une fois le nom pose, l'etincelle respire. Un ecran fige pendant deux
    #    secondes donne l'impression que le programme a plante ; ce battement
    #    lent dit que ca travaille.
    #
    #    Elle continue de respirer PENDANT l'etirement : la couper a la
    #    premiere image le faisait sursauter, le battement etant alors proche
    #    de son maximum. C'est le voile qui l'eteint, progressivement.
    if t > 1.7:
        battement = 0.5 + 0.5 * math.sin((t - 1.7) * 2.4)
        _halo_etincelle(graphiques, ACCENT_PALE, x0_etincelle, milieu,
                        rayon_etincelle * (1.0 + 0.12 * battement),
                        0.55 + 0.85 * battement)
        etincelle(graphiques,
                  avec_alpha(BLANC, 60 + 120 * battement),
                  x0_etincelle, milieu, rayon_etincelle * 0.5)

    if etat is not None:
        # Fin du repere de la carte : le voile et les equerres, eux, se
        # placent dans la fenetre telle qu'elle est maintenant.
        graphiques.Restore(etat)

    # 6. Le voile, puis l'etalement : les quatre coins partent rejoindre ceux
    #    de la fenetre.
    _peindre_voile_et_coins(graphiques, vraie_largeur, vraie_hauteur,
                            voile, etalement)


def avec_alpha(couleur, alpha):
    """La meme couleur, plus ou moins transparente."""
    a = max(0, min(255, int(alpha)))
    return Color.FromArgb(a, couleur.R, couleur.G, couleur.B)


def etincelle(graphiques, couleur, cx, cy, rayon, creux=0.16):
    """L'etoile a quatre branches de Plume, celle de l'icone.

    Cotes concaves, traces en courbes quadratiques converties en cubiques :
    c'est ce galbe qui distingue la marque d'une etoile ordinaire.
    """
    if rayon <= 0.3:
        return
    pointes = []
    for i in range(4):
        a = -math.pi / 2 + i * math.pi / 2
        pointes.append((cx + rayon * math.cos(a), cy + rayon * math.sin(a)))
    chemin = GraphicsPath()
    for i in range(4):
        x0, y0 = pointes[i]
        x2, y2 = pointes[(i + 1) % 4]
        milieu = -math.pi / 2 + (i + 0.5) * math.pi / 2
        cxq = cx + rayon * creux * math.cos(milieu)
        cyq = cy + rayon * creux * math.sin(milieu)
        # quadratique -> cubique : les deux points de controle sont au tiers
        chemin.AddBezier(
            float(x0), float(y0),
            float(x0 + 2.0 / 3 * (cxq - x0)), float(y0 + 2.0 / 3 * (cyq - y0)),
            float(x2 + 2.0 / 3 * (cxq - x2)), float(y2 + 2.0 / 3 * (cyq - y2)),
            float(x2), float(y2))
    chemin.CloseFigure()
    pinceau = SolidBrush(couleur)
    graphiques.FillPath(pinceau, chemin)
    pinceau.Dispose()
    chemin.Dispose()


def etoile(graphiques, couleur, cx, cy, rayon, pleine=True,
           epaisseur=1.6):
    """Etoile a cinq branches, tracee segment par segment.

    Meme raison que pour le cadenas : les polices d'icones de Windows ne sont
    pas rendues par GDI+, elles ne donnent que des rectangles vides.
    """
    points = []
    for i in range(10):
        r = rayon if i % 2 == 0 else rayon * 0.42
        a = math.radians(-90 + i * 36)
        points.append((float(cx + r * math.cos(a)),
                       float(cy + r * math.sin(a))))
    p = GraphicsPath()
    for i in range(10):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % 10]
        p.AddLine(x1, y1, x2, y2)
    p.CloseFigure()
    if pleine:
        pinceau = SolidBrush(couleur)
        graphiques.FillPath(pinceau, p)
        pinceau.Dispose()
    else:
        stylo = Pen(couleur, float(epaisseur))
        graphiques.DrawPath(stylo, p)
        stylo.Dispose()
    p.Dispose()


def roue_dentee(graphiques, couleur, cx, cy, rayon, dents=7):
    """Roue dentee, tracee plutot que tiree d'une police.

    Meme raison que l'etoile et le cadenas : GDI+ ne rend pas les polices
    d'icones de Windows. Mesure faite en dessinant U+2699 hors ecran, le
    resultat ne se distinguait pas du rectangle de repli d'un glyphe absent.

    Le trou du centre est une seconde figure du meme trace : en remplissage
    alterne, ce qui tombe a l'interieur d'un nombre pair de contours reste
    vide. Une rondelle percee plutot qu'un disque avec un rond par-dessus,
    qui obligerait a connaitre la couleur du fond.
    """
    creux = rayon * 0.74
    periode = 2 * math.pi / dents
    # Une dent occupe un peu moins d'un tiers du pas : au-dela elles se
    # touchent et la roue redevient un disque.
    sommet = periode * 0.30
    fond = periode * 0.34
    flanc = (periode - sommet - fond) / 2.0

    p = GraphicsPath()
    points = []
    for i in range(dents):
        a = -math.pi / 2 + i * periode
        for angle, r in ((a, rayon),
                         (a + sommet, rayon),
                         (a + sommet + flanc, creux),
                         (a + sommet + flanc + fond, creux)):
            points.append((float(cx + r * math.cos(angle)),
                           float(cy + r * math.sin(angle))))
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        p.AddLine(x1, y1, x2, y2)
    p.CloseFigure()

    trou = rayon * 0.36
    p.AddEllipse(float(cx - trou), float(cy - trou),
                 float(trou * 2), float(trou * 2))

    pinceau = SolidBrush(couleur)
    graphiques.FillPath(pinceau, p)
    pinceau.Dispose()
    p.Dispose()


def ecran_lecteur(graphiques, couleur, x, y, largeur, hauteur, plein=True):
    """Petit ecran avec un triangle de lecture, trace et non tire d'une police."""
    chemin = chemin_arrondi(x, y, largeur, hauteur, 3)
    if plein:
        pinceau = SolidBrush(couleur)
        graphiques.FillPath(pinceau, chemin)
        pinceau.Dispose()
    else:
        stylo = Pen(couleur, 1.4)
        graphiques.DrawPath(stylo, chemin)
        stylo.Dispose()
    chemin.Dispose()

    cx = x + largeur / 2.0
    cy = y + hauteur / 2.0
    d = min(largeur, hauteur) * 0.30
    triangle = GraphicsPath()
    triangle.AddLine(float(cx - d * 0.7), float(cy - d),
                     float(cx + d * 0.9), float(cy))
    triangle.AddLine(float(cx + d * 0.9), float(cy),
                     float(cx - d * 0.7), float(cy + d))
    triangle.CloseFigure()
    pinceau = SolidBrush(FOND_NAV if plein else couleur)
    graphiques.FillPath(pinceau, triangle)
    pinceau.Dispose()
    triangle.Dispose()


def bouton_fenetre(graphiques, genre, rect, couleur, survole=False):
    """Trace un bouton reduire / agrandir / fermer, facon barre de titre.

    Les traits sont dessines plutot que tapes : aucune police d'icone de
    Windows n'est rendue par GDI+.
    """
    from System.Drawing import Pen
    if survole:
        fond = ROUGE_FERMER if genre == "fermer" else ONGLET_SURVOL
        remplir_arrondi(graphiques, fond, rect.X, rect.Y,
                        rect.Width, rect.Height, 6)
        if genre == "fermer":
            couleur = Color.FromArgb(255, 255, 255)

    cx = rect.X + rect.Width / 2.0
    cy = rect.Y + rect.Height / 2.0
    d = 4.5
    plume = Pen(couleur, 1.2)
    try:
        if genre == "reduire":
            graphiques.DrawLine(plume, cx - d, cy, cx + d, cy)
        elif genre == "agrandir":
            graphiques.DrawRectangle(plume, cx - d, cy - d, d * 2, d * 2)
        elif genre == "restaurer":
            graphiques.DrawRectangle(plume, cx - d, cy - d + 2, d * 2 - 2, d * 2 - 2)
            graphiques.DrawLine(plume, cx - d + 2, cy - d, cx + d, cy - d)
            graphiques.DrawLine(plume, cx + d, cy - d, cx + d, cy + d - 2)
        elif genre == "fermer":
            graphiques.DrawLine(plume, cx - d, cy - d, cx + d, cy + d)
            graphiques.DrawLine(plume, cx + d, cy - d, cx - d, cy + d)
    finally:
        plume.Dispose()


def double_tampon(controle):
    """Active le double tampon d'un Panel.

    La propriete est protegee dans WinForms : sans elle, les barres dessinees
    scintillent au redimensionnement et au survol. On passe donc par la
    reflexion, seul moyen d'y acceder depuis l'exterieur de la classe.
    """
    try:
        import System
        propriete = controle.GetType().GetProperty(
            "DoubleBuffered",
            System.Reflection.BindingFlags.Instance
            | System.Reflection.BindingFlags.NonPublic)
        if propriete is not None:
            propriete.SetValue(controle, True, None)
    except Exception:
        pass
