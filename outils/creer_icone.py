# -*- coding: utf-8 -*-
"""
Genere l'icone de Plume : l'etoile a quatre branches, celle utilisee partout
dans l'interface.

La forme est dessinee, pas rasterisee depuis une police : on garde ainsi la
maitrise de l'epaisseur des branches, qui doit rester lisible jusqu'en 16 px.

Chaque cote joint deux pointes par une courbe de Bezier quadratique dont le
point de controle est tout pres du centre : c'est cette concavite qui donne
l'etoile en etincelle plutot qu'un losange.

Produit icone/plume.ico (multi-tailles) et icone/plume.png (512 px).
"""
import math
import os

from PIL import Image, ImageDraw

DOSSIER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "icone")

COTE = 1024                 # on dessine en grand, on reduit ensuite (anticrenelage)
FOND_HAUT = (30, 32, 46)
FOND_BAS = (18, 19, 26)
VIOLET_HAUT = (167, 139, 250)
VIOLET_BAS = (109, 76, 232)

TAILLES = [256, 128, 64, 48, 32, 24, 16]


def bezier(p0, p1, p2, pas=48):
    """Points d'une courbe de Bezier quadratique."""
    points = []
    for i in range(pas + 1):
        t = i / float(pas)
        u = 1.0 - t
        points.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                       u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return points


def etoile(centre, rayon, creux=0.16, branches=4, rotation=-math.pi / 2):
    """Contour de l'etoile. `creux` rapproche les cotes du centre."""
    cx, cy = centre
    pointes = []
    for i in range(branches):
        a = rotation + i * 2 * math.pi / branches
        pointes.append((cx + rayon * math.cos(a), cy + rayon * math.sin(a)))

    contour = []
    for i in range(branches):
        depart = pointes[i]
        arrivee = pointes[(i + 1) % branches]
        milieu = rotation + (i + 0.5) * 2 * math.pi / branches
        controle = (cx + rayon * creux * math.cos(milieu),
                    cy + rayon * creux * math.sin(milieu))
        contour.extend(bezier(depart, controle, arrivee))
    return contour


def degrade(taille, haut, bas):
    """Bande verticale allant d'une couleur a l'autre."""
    img = Image.new("RGB", (1, taille))
    for y in range(taille):
        t = y / float(max(taille - 1, 1))
        img.putpixel((0, y), tuple(int(haut[c] + (bas[c] - haut[c]) * t)
                                   for c in range(3)))
    return img.resize((taille, taille))


def dessiner():
    # --- fond : carre aux coins arrondis, en degrade ----------------------
    fond = degrade(COTE, FOND_HAUT, FOND_BAS).convert("RGBA")
    masque_fond = Image.new("L", (COTE, COTE), 0)
    ImageDraw.Draw(masque_fond).rounded_rectangle(
        [0, 0, COTE - 1, COTE - 1], radius=int(COTE * 0.22), fill=255)
    plaque = Image.new("RGBA", (COTE, COTE), (0, 0, 0, 0))
    plaque.paste(fond, (0, 0), masque_fond)

    # --- etoile ------------------------------------------------------------
    centre = (COTE / 2.0, COTE / 2.0)
    rayon = COTE * 0.40

    # halo diffus, pour que l'etoile ne flotte pas sur le fond sombre
    halo = Image.new("L", (COTE, COTE), 0)
    ImageDraw.Draw(halo).polygon(etoile(centre, rayon * 1.06, creux=0.22), fill=70)
    try:
        from PIL import ImageFilter
        halo = halo.filter(ImageFilter.GaussianBlur(COTE * 0.045))
    except Exception:
        pass
    plaque.paste(Image.new("RGBA", (COTE, COTE), VIOLET_HAUT + (255,)),
                 (0, 0), halo)

    masque = Image.new("L", (COTE, COTE), 0)
    ImageDraw.Draw(masque).polygon(etoile(centre, rayon, creux=0.16), fill=255)
    encre = degrade(COTE, VIOLET_HAUT, VIOLET_BAS).convert("RGBA")
    plaque.paste(encre, (0, 0), masque)

    # --- petite etoile secondaire, pour l'equilibre ------------------------
    petite = (COTE * 0.735, COTE * 0.30)
    m2 = Image.new("L", (COTE, COTE), 0)
    ImageDraw.Draw(m2).polygon(etoile(petite, COTE * 0.085, creux=0.16), fill=235)
    plaque.paste(Image.new("RGBA", (COTE, COTE), (214, 202, 255, 255)), (0, 0), m2)

    return plaque


def main():
    os.makedirs(DOSSIER, exist_ok=True)
    grande = dessiner()

    png = os.path.join(DOSSIER, "plume.png")
    grande.resize((512, 512), Image.LANCZOS).save(png)

    ico = os.path.join(DOSSIER, "plume.ico")
    grande.resize((256, 256), Image.LANCZOS).save(
        ico, format="ICO", sizes=[(t, t) for t in TAILLES])

    # variante sans plaque, utile sur fond clair
    seule = Image.new("RGBA", (COTE, COTE), (0, 0, 0, 0))
    centre = (COTE / 2.0, COTE / 2.0)
    m = Image.new("L", (COTE, COTE), 0)
    ImageDraw.Draw(m).polygon(etoile(centre, COTE * 0.46, creux=0.16), fill=255)
    seule.paste(degrade(COTE, VIOLET_HAUT, VIOLET_BAS).convert("RGBA"), (0, 0), m)
    seule.resize((512, 512), Image.LANCZOS).save(
        os.path.join(DOSSIER, "plume_etoile.png"))

    for chemin in (png, ico, os.path.join(DOSSIER, "plume_etoile.png")):
        print("%-46s %6d octets" % (chemin, os.path.getsize(chemin)))


if __name__ == "__main__":
    main()
