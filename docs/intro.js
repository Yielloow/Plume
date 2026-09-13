// L'intro de Plume, celle du lancement du navigateur, rejouee dans la page.
//
// Portage direct de interface.py (peindre_intro) : memes couleurs, memes
// proportions, meme minutage. Ce qui change est le support — un canvas plutot
// que GDI+ — et deux details que le navigateur rend gratuits : le melange
// additif existe ici, mais on garde l'empilement de couches pour que le halo
// ait exactement le meme rendu que dans l'application.
//
// Tout est dessine, rien n'est charge : une video de deux secondes et demie
// peserait plus lourd que le reste du site.

(function (global) {
  "use strict";

  var FOND_PAGE = [18, 19, 26];
  var TEXTE = [251, 251, 254];
  var ACCENT = [124, 92, 255];
  var ACCENT_PALE = [167, 139, 250];
  var BLANC = [255, 255, 255];

  var DUREE_INTRO = 2.5;        // comme interface.DUREE_INTRO
  var DUREE_EFFACEMENT = 0.80;  // le voile qui precede l'etirement
  var DUREE_ETALEMENT = 0.65;   // les quatre coins qui partent aux angles

  function rgba(c, a) {
    return "rgba(" + c[0] + "," + c[1] + "," + c[2] + "," +
      Math.max(0, Math.min(1, a)) + ")";
  }

  // Avancement de 0 a 1 d'une etape qui commence a `debut`.
  function part(t, debut, duree) {
    if (duree <= 0) { return 1; }
    return Math.max(0, Math.min(1, (t - debut) / duree));
  }

  // Ralentit a l'arrivee. La meme courbe que l'ouverture d'un onglet.
  function adouci(p) { return 1 - Math.pow(1 - p, 3); }

  // Elargissements et transparences d'un halo, du plus large au plus serre.
  // Quatre couches laissaient voir des anneaux concentriques : sept suffisent
  // a ce que l'oeil n'y lise plus de marches.
  function couchesHalo(couches) {
    var sortie = [];
    for (var i = couches; i > 0; i--) {
      var f = i / couches;
      sortie.push([1 + 2.2 * f * f, (8 + 62 * Math.pow(1 - f, 1.5)) / 255]);
    }
    return sortie;
  }
  var COUCHES = couchesHalo(7);

  // L'etoile a quatre branches de Plume, celle de l'icone. Cotes concaves :
  // c'est ce galbe qui distingue la marque d'une etoile ordinaire.
  function etincelle(c, cx, cy, rayon, creux) {
    if (rayon <= 0.3) { return; }
    creux = creux === undefined ? 0.16 : creux;
    var pointes = [];
    for (var i = 0; i < 4; i++) {
      var a = -Math.PI / 2 + i * Math.PI / 2;
      pointes.push([cx + rayon * Math.cos(a), cy + rayon * Math.sin(a)]);
    }
    c.beginPath();
    c.moveTo(pointes[0][0], pointes[0][1]);
    for (var j = 0; j < 4; j++) {
      var suivant = pointes[(j + 1) % 4];
      var milieu = -Math.PI / 2 + (j + 0.5) * Math.PI / 2;
      c.quadraticCurveTo(cx + rayon * creux * Math.cos(milieu),
                         cy + rayon * creux * Math.sin(milieu),
                         suivant[0], suivant[1]);
    }
    c.closePath();
    c.fill();
  }

  function haloEtincelle(c, couleur, cx, cy, rayon, force) {
    for (var i = 0; i < COUCHES.length; i++) {
      c.fillStyle = rgba(couleur, COUCHES[i][1] * force);
      etincelle(c, cx, cy, rayon * COUCHES[i][0], 0.16);
    }
  }

  function haloDisque(c, couleur, cx, cy, rayon, force) {
    for (var i = 0; i < COUCHES.length; i++) {
      c.fillStyle = rgba(couleur, COUCHES[i][1] * force);
      c.beginPath();
      c.arc(cx, cy, rayon * COUCHES[i][0], 0, Math.PI * 2);
      c.fill();
    }
  }

  function souligner(c, couleur, x, y, largeur, hauteur) {
    if (largeur <= 0) { return; }
    var r = Math.min(hauteur / 2, largeur / 2);
    c.fillStyle = couleur;
    c.beginPath();
    if (c.roundRect) {
      c.roundRect(x, y, largeur, hauteur, r);
    } else {
      c.rect(x, y, largeur, hauteur);
    }
    c.fill();
  }

  // Une equerre de coin, pour l'etalement final : les quatre angles partent
  // rejoindre ceux de la page, comme une toile qui s'ecarte.
  function equerre(c, couleur, x, y, sx, sy, longueur, epaisseur) {
    c.fillStyle = couleur;
    c.fillRect(Math.min(x, x + sx * longueur), y - epaisseur / 2,
               longueur, epaisseur);
    c.fillRect(x - epaisseur / 2, Math.min(y, y + sy * longueur),
               epaisseur, longueur);
  }

  /**
   * Dessine une image de l'intro.
   *
   * @param {CanvasRenderingContext2D} c
   * @param {number} largeur  en pixels CSS
   * @param {number} hauteur  en pixels CSS
   * @param {number} t        secondes depuis le debut
   * @param {number} etalement  0 a 1, les coins qui s'ecartent
   * @param {number} effacement 0 a 1, le voile qui precede
   */
  function peindre(c, largeur, hauteur, t, etalement, effacement) {
    etalement = etalement || 0;
    effacement = effacement || 0;
    c.clearRect(0, 0, largeur, hauteur);
    c.fillStyle = rgba(FOND_PAGE, 1);
    c.fillRect(0, 0, largeur, hauteur);

    // Un seul voile pour deux usages : l'effacement qui precede l'etirement,
    // et celui qui l'accompagne. Le plus opaque gagne.
    var voile = Math.max(effacement, Math.min(1, etalement * 1.7));
    if (voile >= 0.999) {
      peindreVoileEtCoins(c, largeur, hauteur, 1, etalement);
      return;
    }

    // La taille de police suit la fenetre, bornee : sur un telephone le
    // logotype doit tenir, sur un grand ecran il ne doit pas devenir une
    // enseigne.
    var S = Math.max(34, Math.min(92, Math.min(largeur * 0.12, hauteur * 0.2)));
    c.font = "600 " + S + "px 'Segoe UI', -apple-system, system-ui, sans-serif";
    c.textBaseline = "top";

    var mot = "Plume";
    var lMot = c.measureText(mot).width;
    var rayonEtincelle = S * 0.40;
    var ecart = S * 0.46;
    var rayonPoint = S * 0.125;
    var total = rayonEtincelle * 2 + ecart + lMot + ecart * 0.5 + rayonPoint * 2;
    var x = (largeur - total) / 2;
    var milieu = hauteur / 2;
    var x0Etincelle = x + rayonEtincelle;
    var hautTexte = milieu - S * 0.74;
    // Sous les jambages, pas dessus : le point et le trait partagent la meme
    // ligne, c'est ce qui relie les deux bouts du logotype.
    var yTrait = milieu + S * 0.92;
    var xPoint = x + rayonEtincelle * 2 + ecart + lMot + ecart * 0.5;

    c.save();
    c.globalAlpha = 1 - voile;

    // 1. L'etincelle eclot, avec un leger depassement : elle arrive, elle ne
    //    se contente pas d'apparaitre.
    var p = part(t, 0, 0.55);
    if (p > 0) {
      var avance = adouci(p);
      var rayon = rayonEtincelle * avance * (1 + 0.22 * Math.sin(Math.PI * p));
      haloEtincelle(c, ACCENT_PALE, x0Etincelle, milieu, rayon, avance);
      c.fillStyle = rgba(BLANC, avance);
      etincelle(c, x0Etincelle, milieu, rayon * 0.66);
      c.fillStyle = rgba(ACCENT_PALE, 0.92 * avance);
      etincelle(c, x0Etincelle, milieu, rayon);
    }
    x += rayonEtincelle * 2 + ecart;

    // 2. Le mot s'ecrit, une lettre apres l'autre, chacune montant a sa place.
    var curseur = x;
    for (var i = 0; i < mot.length; i++) {
      var pl = part(t, 0.34 + i * 0.13, 0.38);
      if (pl > 0) {
        var al = adouci(pl);
        c.fillStyle = rgba(TEXTE, al);
        c.fillText(mot[i], curseur, hautTexte + 16 * (1 - al));
      }
      curseur = x + c.measureText(mot.slice(0, i + 1)).width;
    }

    // 3. Le trait file sous le mot jusqu'au point, puis reste, plus discret.
    p = part(t, 0.82, 0.95);
    if (p > 0) {
      var av = adouci(p);
      var bout = (lMot + ecart * 0.5 + rayonPoint) * av;
      var eclat = 1 - 0.62 * part(t, 1.55, 0.45);   // vif, puis pose
      // Deux lueurs sous le trait : une large et tres pale, une serree et plus
      // vive. Une seule couche donne une bande, pas une lumiere.
      souligner(c, rgba(ACCENT, 42 / 255 * eclat), x - 5, yTrait - 5,
                bout + 10, 13);
      souligner(c, rgba(ACCENT, 95 / 255 * eclat), x - 2, yTrait - 2,
                bout + 4, 7);
      souligner(c, rgba(ACCENT_PALE, 245 / 255 * eclat), x, yTrait, bout, 3);
    }

    // 4. Le point d'accent, pose sur la ligne du trait, qui depasse un peu.
    p = part(t, 1.32, 0.26);
    if (p > 0) {
      var ap = adouci(p);
      var rp = rayonPoint * ap * (1 + 0.35 * Math.sin(Math.PI * p));
      haloDisque(c, ACCENT_PALE, xPoint, yTrait + 1, rp, ap);
      c.fillStyle = rgba(ACCENT_PALE, ap);
      c.beginPath();
      c.arc(xPoint, yTrait + 1, rp, 0, Math.PI * 2);
      c.fill();
    }

    // 5. Une fois le nom pose, l'etincelle respire. Un ecran fige pendant deux
    //    secondes donne l'impression que ca a plante ; ce battement lent dit
    //    que ca travaille.
    if (t > 1.7) {
      var battement = 0.5 + 0.5 * Math.sin((t - 1.7) * 2.4);
      haloEtincelle(c, ACCENT_PALE, x0Etincelle, milieu,
                    rayonEtincelle * (1 + 0.12 * battement),
                    0.55 + 0.85 * battement);
      c.fillStyle = rgba(BLANC, (60 + 120 * battement) / 255);
      etincelle(c, x0Etincelle, milieu, rayonEtincelle * 0.5);
    }

    c.restore();
    peindreVoileEtCoins(c, largeur, hauteur, voile, etalement);
  }

  // 6. Le voile, puis l'etalement : les quatre coins partent rejoindre ceux de
  //    la page. Comme une toile qui s'en va.
  function peindreVoileEtCoins(c, largeur, hauteur, voile, etalement) {
    if (voile > 0.002) {
      c.fillStyle = rgba(FOND_PAGE, voile);
      c.fillRect(0, 0, largeur, hauteur);
    }
    if (etalement <= 0.001) { return; }
    var e = adouci(Math.min(1, etalement));
    // Les equerres partent d'un rectangle central et filent vers les angles.
    var mx = largeur / 2, my = hauteur / 2;
    var demiL = (largeur * 0.18) + (mx - largeur * 0.18) * e;
    var demiH = (hauteur * 0.22) + (my - hauteur * 0.22) * e;
    var longueur = Math.max(14, Math.min(largeur, hauteur) * 0.07);
    // Vive au depart, elle s'eteint en arrivant aux angles : la toile se
    // dissout au lieu de s'arreter net.
    var force = Math.sin(Math.PI * Math.min(1, etalement));
    var coul = rgba(ACCENT_PALE, 0.85 * force);
    equerre(c, coul, mx - demiL, my - demiH, 1, 1, longueur, 2);
    equerre(c, coul, mx + demiL, my - demiH, -1, 1, longueur, 2);
    equerre(c, coul, mx - demiL, my + demiH, 1, -1, longueur, 2);
    equerre(c, coul, mx + demiL, my + demiH, -1, -1, longueur, 2);
  }

  /**
   * Joue l'intro sur un canvas plein ecran, puis appelle `fini`.
   *
   * Un clic passe la sequence, comme dans le navigateur. Et si la personne a
   * demande moins d'animations dans son systeme, on ne joue rien du tout :
   * une intro est un agrement, pas un peage.
   */
  function jouer(canvas, fini) {
    var reduit = global.matchMedia &&
      global.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduit) { fini(); return; }

    var c = canvas.getContext("2d");
    var debut = null, saute = false;

    function taille() {
      var d = global.devicePixelRatio || 1;
      canvas.width = Math.round(canvas.clientWidth * d);
      canvas.height = Math.round(canvas.clientHeight * d);
      c.setTransform(d, 0, 0, d, 0, 0);
    }
    taille();
    global.addEventListener("resize", taille);

    function passer() { saute = true; }
    canvas.addEventListener("click", passer);
    global.addEventListener("keydown", passer);

    function image(horodatage) {
      if (debut === null) { debut = horodatage; }
      var t = (horodatage - debut) / 1000;
      if (saute) { t = Math.max(t, DUREE_INTRO); }

      var effacement = 0, etalement = 0;
      if (t > DUREE_INTRO) {
        // Le logotype s'efface AVANT que la page arrive : sans cela on le
        // voyait partir vers un coin puis revenir.
        effacement = Math.min(1, (t - DUREE_INTRO) / DUREE_EFFACEMENT);
        etalement = Math.max(0, (t - DUREE_INTRO - DUREE_EFFACEMENT * 0.55) /
                             DUREE_ETALEMENT);
      }
      peindre(c, canvas.clientWidth, canvas.clientHeight, t,
              Math.min(1, etalement), effacement);

      if (etalement >= 1) {
        global.removeEventListener("resize", taille);
        global.removeEventListener("keydown", passer);
        fini();
        return;
      }
      global.requestAnimationFrame(image);
    }
    global.requestAnimationFrame(image);
  }

  global.IntroPlume = { jouer: jouer, peindre: peindre,
                        DUREE_INTRO: DUREE_INTRO };
})(window);
