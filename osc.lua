-- Barre de commandes de Plume, dessinee par mpv lui-meme.
--
-- Pourquoi un script Lua plutot qu'une barre en HTML dans la page : la fenetre
-- de mpv est posee PAR-DESSUS la vue web, donc tout element HTML passerait
-- dessous. Et plutot qu'une troisieme fenetre a maintenir au bon endroit et au
-- bon plan, on dessine dans la video elle-meme : l'ordre d'affichage est
-- toujours correct, le plein ecran fonctionne sans rien synchroniser, et rien
-- ne vole le focus a la page.
--
-- Les icones sont des traces vectoriels et non des caracteres d'une police
-- d'icones. Meme raison qu'en GDI+ dans interface.py : une police absente ne
-- previent pas, elle dessine des rectangles vides.

local mp = require "mp"
local assdraw = require "mp.assdraw"
local msg = require "mp.msg"
local opts = require "mp.options"

-- --------------------------------------------------------------------------
-- Reglages recus de Plume
-- --------------------------------------------------------------------------
local reglages = {
    live = false,        -- un live passe par un tube : pas de choix de qualite
    fps = 60,
    qualite = 1080,
    toujours = false,    -- ne jamais masquer la barre : mise au point du rendu
    langue = "fr",       -- celle de Plume, transmise au lancement
}
opts.read_options(reglages, "plume")

-- --------------------------------------------------------------------------
-- Les phrases du lecteur, dans les deux langues
-- --------------------------------------------------------------------------
-- Cinq phrases : un dictionnaire ici coute moins cher que de les faire
-- traverser le tube depuis Plume a chaque ouverture. Une cle absente renvoie
-- la cle elle-meme, pour qu'un oubli se voie a l'ecran plutot que de faire
-- tomber la barre au milieu d'une video.
local PHRASES = {
    fr = {
        auto = "Automatique",
        normale = "Normale",
        piste = "piste ",
        aucune_piste = "Aucune piste disponible",
        passage = "Passage en ",
    },
    en = {
        auto = "Automatic",
        normale = "Normal",
        piste = "track ",
        aucune_piste = "No track available",
        passage = "Switching to ",
    },
}

local function dit(cle)
    local table_langue = PHRASES[reglages.langue] or PHRASES.en
    return table_langue[cle] or PHRASES.en[cle] or cle
end

-- --------------------------------------------------------------------------
-- Palette, reprise de interface.py. En ASS une couleur s'ecrit a l'envers,
-- bleu-vert-rouge, d'ou les valeurs qui semblent permutees.
-- --------------------------------------------------------------------------
local C = {
    texte    = "&HFEFBFB&",   -- 251,251,254
    -- Plus clair que le TEXTE2 de interface.py (177,177,189) : sur une image
    -- claire, mesure au bas d'une video, ce gris tombait a 2,8 pour 1 de
    -- contraste, en dessous du seuil lisible. Ici 214,214,224.
    faible   = "&HE0D6D6&",
    accent   = "&HFF5C7C&",   -- 124,92,255
    accent2  = "&HFA8BA7&",   -- 167,139,250
    fond     = "&H221B1C&",   -- 28,27,34
    surface  = "&H332A2B&",   -- 43,42,51
    survol   = "&H4D4142&",   -- 66,65,77
    blanc    = "&HFFFFFF&",
    noir     = "&H000000&",
}

-- --------------------------------------------------------------------------
-- Etat
-- --------------------------------------------------------------------------
local etat = {
    pause = false,
    position = 0,
    duree = 0,
    volume = 100,
    muet = false,
    plein_ecran = false,
    vitesse = 1,
    tampon = 0,            -- fin du tampon, en secondes
    pistes = {},
    chargement = nil,      -- texte affiche pendant un rechargement
}

local vue = {
    l = 0, h = 0,          -- taille de l'OSD
    ech = 1,               -- echelle
    souris_x = -1, souris_y = -1,
    visible = false,
    derniere_activite = 0,
    zones = {},            -- rectangles cliquables du rendu courant
    menu = nil,            -- menu ouvert : {nom, items, x, bas}
    glisse = nil,          -- "temps" ou "volume" pendant un cliquer-glisser
}

local calque = mp.create_osd_overlay("ass-events")
local minuterie = nil
local dernier_rendu = nil      -- evite de renvoyer un dessin identique
local premier_pause = true     -- la 1re notification n'est pas une action
local reprise = nil            -- position a retrouver apres un rechargement

local DELAI_MASQUAGE = 2.6     -- secondes d'inactivite avant de s'effacer
local DUREE_ANIM = 0.5         -- duree du retour visuel au clic sur l'image

-- --------------------------------------------------------------------------
-- Petits utilitaires
-- --------------------------------------------------------------------------
local function borner(v, mini, maxi)
    if v < mini then return mini end
    if v > maxi then return maxi end
    return v
end

local function duree_texte(s)
    if not s or s ~= s or s < 0 then return "--:--" end
    s = math.floor(s)
    local h = math.floor(s / 3600)
    local m = math.floor((s % 3600) / 60)
    local r = s % 60
    if h > 0 then
        return string.format("%d:%02d:%02d", h, m, r)
    end
    return string.format("%d:%02d", m, r)
end

local function dans(x, y, r)
    return r and x >= r.x and x <= r.x + r.l and y >= r.y and y <= r.y + r.h
end

-- --------------------------------------------------------------------------
-- Traces ASS
--
-- Un rectangle arrondi et un disque n'existent pas en primitives ASS : il faut
-- les composer a la courbe de Bezier. Le facteur 0.5523 est celui qui approche
-- le mieux un quart de cercle.
-- --------------------------------------------------------------------------
local K = 0.5523

local function trace_rect(d, x, y, l, h, r)
    r = math.min(r or 0, math.min(l, h) / 2)
    if r <= 0 then
        d:move_to(x, y)
        d:line_to(x + l, y)
        d:line_to(x + l, y + h)
        d:line_to(x, y + h)
        return
    end
    local k = r * K
    d:move_to(x + r, y)
    d:line_to(x + l - r, y)
    d:bezier_curve(x + l - r + k, y, x + l, y + r - k, x + l, y + r)
    d:line_to(x + l, y + h - r)
    d:bezier_curve(x + l, y + h - r + k, x + l - r + k, y + h, x + l - r, y + h)
    d:line_to(x + r, y + h)
    d:bezier_curve(x + r - k, y + h, x, y + h - r + k, x, y + h - r)
    d:line_to(x, y + r)
    d:bezier_curve(x, y + r - k, x + r - k, y, x + r, y)
end

local function trace_disque(d, cx, cy, r)
    local k = r * K
    d:move_to(cx - r, cy)
    d:bezier_curve(cx - r, cy - k, cx - k, cy - r, cx, cy - r)
    d:bezier_curve(cx + k, cy - r, cx + r, cy - k, cx + r, cy)
    d:bezier_curve(cx + r, cy + k, cx + k, cy + r, cx, cy + r)
    d:bezier_curve(cx - k, cy + r, cx - r, cy + k, cx - r, cy)
end

-- Chaque element est une ligne d'evenement ASS a part.
local lignes = {}

local function forme(couleur, alpha, tracer)
    -- mp.assdraw multiplie les coordonnees par 2^(scale-1) pour gagner en
    -- precision sous-pixel : la balise doit reprendre le meme facteur, sinon
    -- le trace sort du cadre sans rien signaler.
    local d = assdraw.ass_new()
    tracer(d)
    lignes[#lignes + 1] = string.format(
        "{\\an7\\pos(0,0)\\bord0\\shad0\\1c%s\\1a&H%02X&\\p%d}%s{\\p0}",
        couleur, alpha or 0, d.scale, d.text)
end

local function texte(x, y, contenu, couleur, taille, ancre, alpha)
    lignes[#lignes + 1] = string.format(
        "{\\an%d\\pos(%.1f,%.1f)\\bord0\\shad0\\fnSegoe UI\\fs%.1f"
        .. "\\1c%s\\1a&H%02X&}%s",
        ancre or 4, x, y, taille, couleur, alpha or 0, contenu)
end

-- --------------------------------------------------------------------------
-- Icones, dessinees dans un carre de 100x100 puis ramenees a l'echelle voulue
-- --------------------------------------------------------------------------
local function icone(nom, cx, cy, taille, couleur, alpha)
    local s = taille / 100
    local function p(x, y) return cx + (x - 50) * s, cy + (y - 50) * s end
    forme(couleur, alpha, function(d)
        if nom == "lecture" then
            local x1, y1 = p(30, 20); local x2, y2 = p(80, 50)
            local x3, y3 = p(30, 80)
            d:move_to(x1, y1); d:line_to(x2, y2); d:line_to(x3, y3)
        elseif nom == "pause" then
            local a, b = p(28, 20); local c, e = p(44, 80)
            trace_rect(d, a, b, c - a, e - b, 2 * s)
            local f, g = p(56, 20); local h, i = p(72, 80)
            trace_rect(d, f, g, h - f, i - g, 2 * s)
        elseif nom == "son" then
            local a, b = p(18, 38); local c, e = p(34, 62)
            trace_rect(d, a, b, c - a, e - b, 1 * s)
            local x1, y1 = p(34, 40); local x2, y2 = p(56, 18)
            local x3, y3 = p(56, 82); local x4, y4 = p(34, 60)
            d:move_to(x1, y1); d:line_to(x2, y2)
            d:line_to(x3, y3); d:line_to(x4, y4)
        elseif nom == "barre_son" then
            -- la croix seule : le haut-parleur est trace juste avant, par un
            -- appel distinct, pour ne pas imbriquer deux traces.
            local x1, y1 = p(62, 34); local x2, y2 = p(88, 60)
            local x3, y3 = p(84, 66); local x4, y4 = p(58, 40)
            d:move_to(x1, y1); d:line_to(x2, y2)
            d:line_to(x3, y3); d:line_to(x4, y4)
            local a1, b1 = p(88, 40); local a2, b2 = p(62, 66)
            local a3, b3 = p(58, 60); local a4, b4 = p(84, 34)
            d:move_to(a1, b1); d:line_to(a2, b2)
            d:line_to(a3, b3); d:line_to(a4, b4)
        elseif nom == "coche" then
            local pts = {{16, 50}, {38, 72}, {84, 24}, {92, 32},
                         {38, 88}, {8, 58}}
            for i, c in ipairs(pts) do
                local px, py = p(c[1], c[2])
                if i == 1 then d:move_to(px, py) else d:line_to(px, py) end
            end
        elseif nom == "theatre" then
            -- Un cadre large, trace en quatre barres : un rectangle evide
            -- dependrait de la regle de remplissage de libass, quatre barres
            -- donnent le meme dessin sans rien supposer.
            local ep = 9
            local x0, y0 = 12, 26
            local x1, y1 = 88, 74
            local a, b = p(x0, y0); local c, e = p(x1, y0 + ep)
            trace_rect(d, a, b, c - a, e - b, 1 * s)
            local f, g2 = p(x0, y1 - ep); local h, i = p(x1, y1)
            trace_rect(d, f, g2, h - f, i - g2, 1 * s)
            local j, k = p(x0, y0); local l2, m = p(x0 + ep, y1)
            trace_rect(d, j, k, l2 - j, m - k, 1 * s)
            local n, o = p(x1 - ep, y0); local q, r = p(x1, y1)
            trace_rect(d, n, o, q - n, r - o, 1 * s)
        elseif nom == "plein" or nom == "reduire" then
            local dedans = (nom == "reduire")
            local coins = {{18, 18, 1, 1}, {82, 18, -1, 1},
                           {18, 82, 1, -1}, {82, 82, -1, -1}}
            for _, c in ipairs(coins) do
                local ox, oy, sx, sy = c[1], c[2], c[3], c[4]
                if dedans then ox = ox + sx * 12; oy = oy + sy * 12 end
                local ax, ay = p(ox, oy)
                local bx, by = p(ox + sx * 26, oy)
                local cx2, cy2 = p(ox + sx * 26, oy + sy * 7)
                local dx, dy = p(ox + sx * 7, oy + sy * 7)
                local ex, ey = p(ox + sx * 7, oy + sy * 26)
                local fx, fy = p(ox, oy + sy * 26)
                d:move_to(ax, ay); d:line_to(bx, by); d:line_to(cx2, cy2)
                d:line_to(dx, dy); d:line_to(ex, ey); d:line_to(fx, fy)
            end
        end
    end)
end

-- --------------------------------------------------------------------------
-- Menus
-- --------------------------------------------------------------------------
local function liste_qualites()
    local items = {{titre = dit("auto"), valeur = 0}}
    for _, h in ipairs({2160, 1440, 1080, 720, 480, 360}) do
        items[#items + 1] = {titre = h .. "p", valeur = h}
    end
    for _, it in ipairs(items) do
        it.actif = (it.valeur == reglages.qualite)
    end
    return items
end

local function liste_vitesses()
    local items = {}
    for _, v in ipairs({0.5, 0.75, 1, 1.25, 1.5, 1.75, 2}) do
        items[#items + 1] = {
            titre = (v == 1) and dit("normale")
                    or (tostring(v):gsub("%.", ",") .. "x"),
            valeur = v,
            actif = math.abs(etat.vitesse - v) < 0.01,
        }
    end
    return items
end

local function liste_pistes(genre)
    local items = {}
    if genre == "sub" then
        items[#items + 1] = {titre = "Aucun", valeur = "no",
                             actif = mp.get_property("sid") == "no"}
    end
    local courant = mp.get_property(genre == "sub" and "sid" or "aid")
    for _, p in ipairs(etat.pistes) do
        if p.type == genre then
            local nom = p.lang or p.title or (dit("piste") .. tostring(p.id))
            if p.title and p.lang then nom = p.lang .. " - " .. p.title end
            items[#items + 1] = {
                titre = nom,
                valeur = tostring(p.id),
                actif = (courant == tostring(p.id)),
            }
        end
    end
    if #items == 0 or (genre == "sub" and #items == 1) then
        items[#items + 1] = {titre = dit("aucune_piste"), inerte = true}
    end
    return items
end

-- --------------------------------------------------------------------------
-- Actions
-- --------------------------------------------------------------------------
local function appliquer_qualite(hauteur)
    if reglages.live then return end
    local chemin = mp.get_property("path")
    if not chemin or chemin == "" or chemin == "-" then return end

    local format
    if hauteur == 0 then
        format = "bestvideo+bestaudio/best"
    else
        format = string.format(
            "bestvideo[height<=?%d][fps<=?%d]+bestaudio/best",
            hauteur, reglages.fps)
    end
    reglages.qualite = hauteur

    local pos = mp.get_property_number("time-pos") or 0
    local en_pause = mp.get_property_bool("pause")
    etat.chargement = (hauteur == 0) and "Qualite automatique..."
                      or (dit("passage") .. hauteur .. "p...")

    mp.set_property("options/ytdl-format", format)
    -- La position est reprise dans le gestionnaire `file-loaded` plutot que par
    -- l'option `start` : celle-ci resterait active pour les lectures suivantes.
    reprise = {position = pos, pause = en_pause}
    mp.commandv("loadfile", chemin, "replace")
end

local function basculer_menu(nom, items, ancre_x, bas)
    if vue.menu and vue.menu.nom == nom then
        vue.menu = nil
        return
    end
    vue.menu = {nom = nom, items = items, x = ancre_x, bas = bas,
                survol = nil}
end

local function choisir(nom, item)
    if item.inerte then return end
    if nom == "qualite" then
        appliquer_qualite(item.valeur)
    elseif nom == "vitesse" then
        mp.set_property_number("speed", item.valeur)
    elseif nom == "sous-titres" then
        mp.set_property("sid", item.valeur)
    elseif nom == "audio" then
        mp.set_property("aid", item.valeur)
    end
    vue.menu = nil
end

-- --------------------------------------------------------------------------
-- Rendu
-- --------------------------------------------------------------------------
-- Retour visuel au centre de l'image, comme sur les sites video : un disque
-- qui grandit en s'effacant, avec le symbole de l'etat obtenu. La progression
-- ralentit en fin de course, ce qui parait plus naturel qu'une vitesse
-- constante.
local function rendre_anim()
    local a = vue.anim
    if not a then return end
    local t = (mp.get_time() - a.debut) / DUREE_ANIM
    if t >= 1 then
        vue.anim = nil
        return
    end
    -- Deux progressions distinctes, et c'est ce qui fait tout : le disque
    -- grandit vite puis ralentit, tandis que l'effacement, lui, demarre
    -- doucement. Avec une seule courbe pour les deux, l'animation avait
    -- pratiquement disparu au bout de 160 ms.
    local croissance = 1 - (1 - t) * (1 - t)
    local disparition = t * t
    local ech = borner(vue.h / 720, 0.75, 1.9)
    local cx, cy = vue.l / 2, vue.h / 2
    forme(C.noir, math.floor(55 + 200 * disparition), function(d)
        trace_disque(d, cx, cy, (46 + 26 * croissance) * ech)
    end)
    icone(a.genre, cx, cy, (32 + 6 * croissance) * ech, C.blanc,
          math.floor(255 * disparition))
end

local function geometrie()
    -- Echelle de la barre, calculee sur la LARGEUR seule. Une video en
    -- 1920x1080 et la meme en 1920x500 doivent donner exactement les memes
    -- boutons, le meme texte et le meme curseur : c'est la largeur qu'on a
    -- sous les yeux, et c'est elle qui doit decider. Deux versions
    -- precedentes se fondaient sur la hauteur, puis sur la surface : dans les
    -- deux cas une video au format cinema recevait une barre rabougrie.
    --
    -- Le second terme n'est qu'un garde-fou pour les lecteurs extremement
    -- plats : il empeche la barre d'occuper plus du tiers de la hauteur. Sur
    -- tout lecteur de proportions normales, il ne joue jamais.
    local e = borner(math.min(vue.l / 1280, vue.h / 200), 0.8, 1.9)
    vue.ech = e
    local g = {}
    g.e = e
    g.marge = 18 * e
    g.barre_h = 70 * e
    g.barre_y = vue.h - g.barre_h
    g.piste_y = g.barre_y + 15 * e
    g.piste_x = g.marge
    g.piste_l = vue.l - 2 * g.marge
    g.piste_h = 5 * e
    g.boutons_y = g.barre_y + 44 * e
    g.icone = 20 * e
    g.police = 15 * e
    return g
end

local function rendre_piste(g)
    local survol_piste = vue.visible and
        (vue.souris_y >= g.piste_y - 9 * g.e and
         vue.souris_y <= g.piste_y + g.piste_h + 9 * g.e)
    local h = (survol_piste or vue.glisse == "temps") and g.piste_h * 1.8
              or g.piste_h
    local y = g.piste_y + (g.piste_h - h) / 2
    local r = h / 2

    forme(C.blanc, 165, function(d)
        trace_rect(d, g.piste_x, y, g.piste_l, h, r)
    end)

    if etat.duree > 0 then
        local tampon = borner(etat.tampon / etat.duree, 0, 1)
        if tampon > 0 then
            forme(C.blanc, 105, function(d)
                trace_rect(d, g.piste_x, y, g.piste_l * tampon, h, r)
            end)
        end
        -- accent2 plutot que accent : le violet sombre passait mal sur une
        -- image claire, verifie sur mire.
        local avance = borner(etat.position / etat.duree, 0, 1)
        forme(C.accent2, 0, function(d)
            trace_rect(d, g.piste_x, y, g.piste_l * avance, h, r)
        end)
        if survol_piste or vue.glisse == "temps" then
            local cx = g.piste_x + g.piste_l * avance
            forme(C.accent2, 0, function(d)
                trace_disque(d, cx, g.piste_y + g.piste_h / 2, 7.5 * g.e)
            end)
        end
    end

    -- Position survolee, affichee au-dessus de la piste
    if survol_piste and etat.duree > 0 and not vue.menu then
        local t = borner((vue.souris_x - g.piste_x) / g.piste_l, 0, 1)
        local bx = borner(vue.souris_x, g.piste_x + 26 * g.e,
                          g.piste_x + g.piste_l - 26 * g.e)
        local by = g.piste_y - 12 * g.e
        forme(C.fond, 40, function(d)
            trace_rect(d, bx - 26 * g.e, by - 20 * g.e, 52 * g.e, 22 * g.e,
                       5 * g.e)
        end)
        texte(bx, by - 9 * g.e, duree_texte(t * etat.duree), C.texte,
              13 * g.e, 5)
    end

    vue.zones[#vue.zones + 1] = {
        role = "temps",
        x = g.piste_x - 4 * g.e, y = g.piste_y - 9 * g.e,
        l = g.piste_l + 8 * g.e, h = g.piste_h + 18 * g.e,
    }
end

local function bouton(g, role, x, dessiner, largeur)
    local l = largeur or (g.icone + 18 * g.e)
    local z = {role = role, x = x, y = g.boutons_y - g.icone,
               l = l, h = g.icone * 2}
    local actif = dans(vue.souris_x, vue.souris_y, z) and vue.visible
    dessiner(x + l / 2, actif and C.texte or C.faible)
    vue.zones[#vue.zones + 1] = z
    return x + l
end

local function rendre_boutons(g)
    local x = g.marge

    x = bouton(g, "pause", x, function(cx, coul)
        icone(etat.pause and "lecture" or "pause", cx, g.boutons_y,
              g.icone, coul)
    end)

    x = x + 6 * g.e
    x = bouton(g, "muet", x, function(cx, coul)
        icone("son", cx, g.boutons_y, g.icone, coul)
        if etat.muet or etat.volume < 1 then
            icone("barre_son", cx, g.boutons_y, g.icone, coul)
        end
    end)

    -- Curseur de volume
    local vx, vl = x + 2 * g.e, 68 * g.e
    local vy, vh = g.boutons_y, 4 * g.e
    forme(C.blanc, 190, function(d)
        trace_rect(d, vx, vy - vh / 2, vl, vh, vh / 2)
    end)
    local part = etat.muet and 0 or borner(etat.volume / 100, 0, 1)
    forme(C.texte, 0, function(d)
        trace_rect(d, vx, vy - vh / 2, vl * part, vh, vh / 2)
    end)
    forme(C.texte, 0, function(d)
        trace_disque(d, vx + vl * part, vy, 5.5 * g.e)
    end)
    vue.zones[#vue.zones + 1] = {role = "volume", x = vx - 6 * g.e,
                                 y = vy - 12 * g.e, l = vl + 12 * g.e,
                                 h = 24 * g.e, x0 = vx, l0 = vl}
    x = vx + vl + 16 * g.e

    local t = duree_texte(etat.position) .. "  /  " .. duree_texte(etat.duree)
    if reglages.live then t = "EN DIRECT" end
    texte(x, g.boutons_y, t, C.texte, g.police, 4)

    if etat.chargement then
        texte(x + 180 * g.e, g.boutons_y, etat.chargement, C.accent2,
              g.police, 4)
    end

    -- Cote droit, de droite a gauche
    local xd = vue.l - g.marge
    local function droite(role, dessiner, largeur)
        local l = largeur or (g.icone + 18 * g.e)
        xd = xd - l
        bouton(g, role, xd, dessiner, l)
        xd = xd - 4 * g.e
    end

    droite("plein", function(cx, coul)
        icone(etat.plein_ecran and "reduire" or "plein", cx, g.boutons_y,
              g.icone, coul)
    end)

    -- Le mode theatre appartient a la PAGE, pas au lecteur : mpv ne fait que
    -- transmettre la demande a Plume, qui l'applique au site. En plein ecran
    -- il n'a aucun sens, la page n'etant plus visible.
    if not etat.plein_ecran then
        droite("theatre", function(cx, coul)
            icone("theatre", cx, g.boutons_y, g.icone, coul)
        end)
    end

    if not reglages.live then
        local q = (reglages.qualite == 0) and "Auto" or (reglages.qualite .. "p")
        droite("qualite", function(cx, coul)
            texte(cx, g.boutons_y, q,
                  vue.menu and vue.menu.nom == "qualite" and C.accent2 or coul,
                  g.police, 5)
        end, 58 * g.e)
    end

    droite("sous-titres", function(cx, coul)
        local actif = mp.get_property("sid") ~= "no"
        texte(cx, g.boutons_y, "ST",
              vue.menu and vue.menu.nom == "sous-titres" and C.accent2
              or (actif and C.texte or coul), g.police, 5)
    end, 38 * g.e)

    droite("audio", function(cx, coul)
        texte(cx, g.boutons_y, "Audio",
              vue.menu and vue.menu.nom == "audio" and C.accent2 or coul,
              g.police, 5)
    end, 56 * g.e)

    local v = (math.abs(etat.vitesse - 1) < 0.01) and "1x"
              or (string.format("%.2f", etat.vitesse):gsub("0+$", "")
                  :gsub("%.$", "") .. "x")
    droite("vitesse", function(cx, coul)
        texte(cx, g.boutons_y, (v:gsub("%.", ",")),
              vue.menu and vue.menu.nom == "vitesse" and C.accent2 or coul,
              g.police, 5)
    end, 52 * g.e)
end

local function rendre_menu(g)
    local m = vue.menu
    if not m then return end
    local lh = 30 * g.e
    local larg = 200 * g.e
    local n = #m.items

    -- Une video peut proposer vingt-sept langues de sous-titres : sans
    -- plafond, le menu sort par le haut de l'ecran et les premieres entrees
    -- deviennent inatteignables. Mesure faite sur une conference TED.
    local vis = math.min(n, math.max(3, math.floor((vue.h * 0.62) / lh)))
    if m.decalage == nil then
        local actif = 1
        for i, it in ipairs(m.items) do
            if it.actif then actif = i end
        end
        m.decalage = borner(actif - math.floor(vis / 2), 0, n - vis)
    end
    m.decalage = borner(m.decalage, 0, math.max(0, n - vis))

    local haut = lh * vis + 12 * g.e
    local x = borner(m.x - larg / 2, g.marge, vue.l - g.marge - larg)
    local y = m.bas - haut - 10 * g.e
    m.cadre = {x = x, y = y, l = larg, h = haut}

    forme(C.fond, 25, function(d)
        trace_rect(d, x, y, larg, haut, 10 * g.e)
    end)

    m.affiches = {}
    for k = 1, vis do
        local i = m.decalage + k
        local it = m.items[i]
        if it then
            local iy = y + 6 * g.e + (k - 1) * lh
            local r = {x = x, y = iy, l = larg, h = lh}
            m.affiches[#m.affiches + 1] = {index = i, rect = r}
            if dans(vue.souris_x, vue.souris_y, r) and not it.inerte then
                forme(C.survol, 60, function(d)
                    trace_rect(d, x + 5 * g.e, iy, larg - 10 * g.e, lh,
                               6 * g.e)
                end)
            end
            local coul = it.inerte and C.faible
                         or (it.actif and C.accent2 or C.texte)
            texte(x + 16 * g.e, iy + lh / 2, it.titre, coul, g.police, 4)
            if it.actif then
                icone("coche", x + larg - 20 * g.e, iy + lh / 2, 13 * g.e,
                      C.accent2)
            end
        end
    end

    -- Reglette de defilement, seulement quand elle a lieu d'etre
    if n > vis then
        local piste_h = haut - 12 * g.e
        local pouce = math.max(20 * g.e, piste_h * vis / n)
        local py = y + 6 * g.e
                   + (piste_h - pouce) * (m.decalage / (n - vis))
        forme(C.blanc, 200, function(d)
            trace_rect(d, x + larg - 6 * g.e, y + 6 * g.e, 3 * g.e, piste_h,
                       1.5 * g.e)
        end)
        forme(C.accent2, 40, function(d)
            trace_rect(d, x + larg - 6 * g.e, py, 3 * g.e, pouce, 1.5 * g.e)
        end)
    end
end

local function rendre()
    local l, h = mp.get_osd_size()
    if not l or l < 10 then return end
    vue.l, vue.h = l, h
    vue.zones = {}
    lignes = {}

    rendre_anim()      -- visible meme quand la barre est effacee

    if not vue.visible then
        calque.res_x, calque.res_y = vue.l, vue.h
        local vide = table.concat(lignes, "\n")
        if vide ~= dernier_rendu then
            calque.data = vide
            calque:update()
            dernier_rendu = vide
        end
        return
    end

    local g = geometrie()

    -- Fond degrade. L'ASS ne connait pas le degrade : il faut l'approcher par
    -- bandes. Avec sept bandes les marches se voyaient franchement ; il en
    -- faut beaucoup, et une progression courbe plutot que lineaire, sinon le
    -- haut du degrade reste visible comme une arete.
    local haut = g.barre_h + 52 * g.e
    local bandes = 34
    local hb = haut / bandes
    for i = 1, bandes do
        local part = (i - 1) / (bandes - 1)
        local y = vue.h - haut + (i - 1) * hb
        -- Assez opaque en bas pour que les libelles restent lisibles sur une
        -- image claire : mesure sur une video au fond blanc, la luminance du
        -- fond sous les libelles passe de 100 a une quarantaine.
        local a = math.floor(255 - 238 * (part ^ 1.35))
        forme(C.noir, a, function(d)
            trace_rect(d, 0, y, vue.l, hb + 1, 0)
        end)
    end

    rendre_piste(g)
    rendre_boutons(g)
    rendre_menu(g)

    calque.res_x, calque.res_y = vue.l, vue.h
    local donnees = table.concat(lignes, "\n")
    if donnees ~= dernier_rendu then
        calque.data = donnees
        calque:update()
        dernier_rendu = donnees
    end
end

-- --------------------------------------------------------------------------
-- Visibilite
-- --------------------------------------------------------------------------
local function doit_rester()
    return reglages.toujours or etat.pause or vue.menu ~= nil
           or vue.glisse ~= nil or etat.chargement ~= nil
end

-- Les sous-titres se posent au bas de l'image, donc juste sur la barre. On les
-- remonte tant qu'elle est affichee, et on les redescend ensuite.
local SOUS_TITRES_HAUT, SOUS_TITRES_BAS = 90, 100

local function placer_sous_titres(degage)
    local voulu = degage and SOUS_TITRES_HAUT or SOUS_TITRES_BAS
    if mp.get_property_number("sub-pos") ~= voulu then
        mp.set_property_number("sub-pos", voulu)
    end
end

local function montrer()
    vue.derniere_activite = mp.get_time()
    if not vue.visible then
        vue.visible = true
        placer_sous_titres(true)
        rendre()
    end
end

local function battement()
    if vue.visible and not doit_rester()
       and mp.get_time() - vue.derniere_activite > DELAI_MASQUAGE then
        vue.visible = false
        vue.menu = nil
        placer_sous_titres(false)
    end
    rendre()
end

-- --------------------------------------------------------------------------
-- Souris
-- --------------------------------------------------------------------------
local function position_souris()
    -- Le crochet de test pose une position fictive : sans cela, chaque
    -- fonction relit le vrai curseur au premier geste et le test ne pilote
    -- plus rien.
    if vue.souris_forcee then
        vue.souris_x, vue.souris_y = vue.souris_forcee[1], vue.souris_forcee[2]
        return vue.souris_x, vue.souris_y
    end
    local x, y = mp.get_mouse_pos()
    vue.souris_x, vue.souris_y = x, y
    return x, y
end

local function zone_sous_souris()
    for i = #vue.zones, 1, -1 do
        if dans(vue.souris_x, vue.souris_y, vue.zones[i]) then
            return vue.zones[i]
        end
    end
    return nil
end

local function appliquer_glisse()
    if vue.glisse == "temps" then
        local z
        for _, r in ipairs(vue.zones) do
            if r.role == "temps" then z = r end
        end
        if z and etat.duree > 0 then
            local t = borner((vue.souris_x - z.x - 4 * vue.ech)
                             / (z.l - 8 * vue.ech), 0, 1)
            mp.commandv("seek", t * etat.duree, "absolute+exact")
        end
    elseif vue.glisse == "volume" then
        local z
        for _, r in ipairs(vue.zones) do
            if r.role == "volume" then z = r end
        end
        if z then
            local t = borner((vue.souris_x - z.x0) / z.l0, 0, 1)
            mp.set_property_number("volume", math.floor(t * 100 + 0.5))
            if t > 0 then mp.set_property_bool("mute", false) end
        end
    end
end

local function sur_mouvement()
    position_souris()
    montrer()
    if vue.glisse then appliquer_glisse() end
    rendre()
end

-- Canal vers Plume : une propriete `user-data` que le cote Python observe
-- par le tube IPC. Le compteur en tete garantit un changement de valeur, donc
-- une notification, meme si la meme action est demandee deux fois de suite.
local compteur_action = 0
local function vers_plume(nom, valeur)
    compteur_action = compteur_action + 1
    mp.set_property("user-data/plume/action",
                    compteur_action .. ":" .. nom .. ":" .. (valeur or ""))
end

local agir_sur_zone
local function sur_clic(evt)
    if evt.event == "up" then
        vue.glisse = nil
        return
    end
    if evt.event ~= "down" then return end
    position_souris()
    montrer()

    -- Un menu ouvert capte le clic en priorite
    if vue.menu and vue.menu.affiches then
        for _, a in ipairs(vue.menu.affiches) do
            if dans(vue.souris_x, vue.souris_y, a.rect) then
                choisir(vue.menu.nom, vue.menu.items[a.index])
                rendre()
                return
            end
        end
        vue.menu = nil
        rendre()
        return
    end

    local z = zone_sous_souris()
    local g = geometrie()
    if not z then
        -- Clic dans l'image : lecture/pause. On ecarte le fond de la barre,
        -- qui n'est pas l'image et ne doit rien declencher.
        if vue.visible and vue.souris_y >= g.barre_y - 10 * g.e then
            return
        end
        -- mpv envoie MBTN_LEFT pour les DEUX appuis d'un double-clic, en plus
        -- de MBTN_LEFT_DBL. Sans ignorer le second, un double-clic basculait
        -- la pause deux fois puis une troisieme a la compensation.
        local maintenant = mp.get_time()
        if maintenant - (vue.clic_image or 0) < 0.32 then
            vue.clic_image = maintenant
            return
        end
        vue.clic_image = maintenant
        mp.commandv("cycle", "pause")
        rendre()
        return
    end

    agir_sur_zone(z, g)
    rendre()
end

function agir_sur_zone(z, g)
    if z.role == "temps" then
        vue.glisse = "temps"
        appliquer_glisse()
    elseif z.role == "volume" then
        vue.glisse = "volume"
        appliquer_glisse()
    elseif z.role == "pause" then
        mp.commandv("cycle", "pause")
    elseif z.role == "muet" then
        mp.commandv("cycle", "mute")
    elseif z.role == "plein" then
        mp.commandv("cycle", "fullscreen")
    elseif z.role == "theatre" then
        vers_plume("theatre")
    elseif z.role == "qualite" then
        basculer_menu("qualite", liste_qualites(), z.x + z.l / 2, g.barre_y)
    elseif z.role == "vitesse" then
        basculer_menu("vitesse", liste_vitesses(), z.x + z.l / 2, g.barre_y)
    elseif z.role == "sous-titres" then
        basculer_menu("sous-titres", liste_pistes("sub"), z.x + z.l / 2,
                      g.barre_y)
    elseif z.role == "audio" then
        basculer_menu("audio", liste_pistes("audio"), z.x + z.l / 2, g.barre_y)
    end
end

local function molette(sens)
    position_souris()
    montrer()
    -- Dans un menu, la molette le fait defiler plutot que la video
    if vue.menu and vue.menu.cadre
       and dans(vue.souris_x, vue.souris_y, vue.menu.cadre) then
        vue.menu.decalage = (vue.menu.decalage or 0) - sens * 3
        rendre()
        return
    end
    local z = zone_sous_souris()
    if z and (z.role == "volume" or z.role == "muet") then
        local v = borner((mp.get_property_number("volume") or 100) + sens * 5,
                         0, 100)
        mp.set_property_number("volume", v)
    else
        -- La molette ne saute plus dans la video : trop facile a declencher
        -- sans le vouloir, et on perdait sa place pour un coup de doigt. Elle
        -- fait defiler la page, comme sur le site.
        vers_plume("defiler", tostring(-sens * 120))
    end
    rendre()
end

-- --------------------------------------------------------------------------
-- Branchements
-- --------------------------------------------------------------------------
mp.observe_property("pause", "bool", function(_, v)
    etat.pause = v or false
    if premier_pause then
        premier_pause = false      -- etat initial, pas une action de l'usager
    else
        vue.anim = {debut = mp.get_time(),
                    genre = etat.pause and "pause" or "lecture"}
    end
    montrer()
end)
mp.observe_property("time-pos", "number", function(_, v)
    etat.position = v or 0
end)
mp.observe_property("duration", "number", function(_, v)
    etat.duree = v or 0
end)
mp.observe_property("volume", "number", function(_, v)
    etat.volume = v or 100
end)
mp.observe_property("mute", "bool", function(_, v) etat.muet = v or false end)
mp.observe_property("fullscreen", "bool", function(_, v)
    etat.plein_ecran = v or false
end)
mp.observe_property("speed", "number", function(_, v) etat.vitesse = v or 1 end)
mp.observe_property("demuxer-cache-time", "number", function(_, v)
    etat.tampon = v or 0
end)
-- Fin de la video. Avec --keep-open, mpv ne se ferme pas : il reste sur la
-- derniere image, ce qui laisse le temps de prevenir Plume proprement. Guetter
-- la mort du processus serait une course perdue d'avance.
mp.observe_property("eof-reached", "bool", function(_, v)
    if v then vers_plume("fini") end
end)

-- Position de lecture, publiee de temps en temps pour que Plume s'en
-- souvienne. Toutes les cinq secondes, pas a chaque image : `time-pos` change
-- soixante fois par seconde, et le tube n'a pas a porter cela.
local derniere_publiee = -999
local function publier_position(force)
    if reglages.live then return end
    local pos, duree = etat.position or 0, etat.duree or 0
    if duree <= 0 then return end
    if not force and math.abs(pos - derniere_publiee) < 5 then return end
    derniere_publiee = pos
    vers_plume("position", string.format("%.1f/%.1f", pos, duree))
end

mp.add_periodic_timer(5, function() publier_position(false) end)

-- Le volume est un reglage de personne, pas de video : Plume le retient d'une
-- lecture a l'autre. On ne publie qu'apres un silence, sinon tirer le curseur
-- enverrait cinquante messages pour un seul geste.
local son_en_attente = nil
local function publier_son()
    if not son_en_attente then return end
    vers_plume("son", son_en_attente)
    son_en_attente = nil
end

local function noter_son()
    son_en_attente = string.format("%d/%d", math.floor((etat.volume or 100) + 0.5),
                                   etat.muet and 1 or 0)
end

mp.observe_property("volume", "number", function(_, v)
    if v then noter_son() end
end)
mp.observe_property("mute", "bool", function(_, v)
    noter_son()
end)
mp.add_periodic_timer(2, publier_son)
-- Une pause, c'est souvent « je m'arrete la » : on note tout de suite.
mp.observe_property("pause", "bool", function(_, v)
    if v then publier_position(true) end
end)
mp.observe_property("track-list", "native", function(_, v)
    etat.pistes = v or {}
end)

-- Reprise de la position apres un changement de qualite : le flux est relance
-- depuis le debut, il faut y revenir soi-meme.
mp.register_event("file-loaded", function()
    etat.chargement = nil
    if reprise then
        local r = reprise
        reprise = nil
        if r.position and r.position > 1 then
            mp.commandv("seek", r.position, "absolute+exact")
        end
        if r.pause then mp.set_property_bool("pause", true) end
    end
    montrer()
end)

mp.add_forced_key_binding("mouse_move", "plume_mouvement", sur_mouvement)
mp.add_forced_key_binding("mbtn_left", "plume_clic", sur_clic, {complex = true})
-- Sur un double-clic, mpv n'envoie MBTN_LEFT que pour le premier appui : sans
-- cela, demander le plein ecran mettrait la video en pause au passage.
mp.add_forced_key_binding("mbtn_left_dbl", "plume_double", function()
    -- Le premier appui a deja bascule la pause : on la remet comme elle etait,
    -- demander le plein ecran ne doit pas arreter la video au passage.
    if mp.get_time() - (vue.clic_image or 0) < 0.6 then
        mp.commandv("cycle", "pause")
        vue.anim = nil
        vue.clic_image = mp.get_time()
    end
    mp.commandv("cycle", "fullscreen")
    rendre()
end)

mp.add_forced_key_binding("wheel_up", "plume_molette_h",
                          function() molette(1) end)
mp.add_forced_key_binding("wheel_down", "plume_molette_b",
                          function() molette(-1) end)

-- Crochet de mise au point. La barre se verifie ainsi sans souris, par IPC,
-- et mpv se capture lui-meme avec `screenshot window`, OSD compris. C'est le
-- seul moyen fiable de juger le rendu : une capture d'ecran compose mal les
-- surfaces de mpv et de WebView2, on s'y est deja laisse prendre deux fois.
-- Voir outils/apercu_barre.py.
mp.register_script_message("plume-test", function(action, a, b, c)
    if action == "souris" then
        vue.souris_x = tonumber(a) or -1
        vue.souris_y = tonumber(b) or -1
        vue.souris_forcee = {vue.souris_x, vue.souris_y}
    elseif action == "menu" then
        local listes = {
            qualite = liste_qualites,
            vitesse = liste_vitesses,
            ["sous-titres"] = function() return liste_pistes("sub") end,
            audio = function() return liste_pistes("audio") end,
        }
        local f = listes[a]
        if f then
            vue.menu = nil
            basculer_menu(a, f(), tonumber(b) or vue.l / 2, geometrie().barre_y)
        end
    elseif action == "zones" then
        -- Publie les zones cliquables : un test peut ainsi viser un bouton
        -- par son role, sans coder ses coordonnees en dur.
        local morceaux = {}
        for _, z in ipairs(vue.zones) do
            morceaux[#morceaux + 1] = string.format(
                "%s=%d,%d,%d,%d", z.role, z.x, z.y, z.l, z.h)
        end
        mp.set_property("user-data/plume/zones",
                        table.concat(morceaux, ";"))
    elseif action == "clic" then
        vue.souris_forcee = {tonumber(a) or -1, tonumber(b) or -1}
        position_souris()
        local z = zone_sous_souris()
        if z then agir_sur_zone(z, geometrie()) end
    elseif action == "molette" then
        vue.souris_forcee = {tonumber(b) or -1, tonumber(c) or -1}
        molette(tonumber(a) or 1)
    elseif action == "choisir" then
        if vue.menu then
            local it = vue.menu.items[tonumber(a) or 1]
            if it then choisir(vue.menu.nom, it) end
        end
    end
    montrer()
    rendre()
end)

minuterie = mp.add_periodic_timer(1 / 30, battement)
montrer()
msg.info("barre de commandes Plume chargee")
