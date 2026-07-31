"""Carte des touches : familles, disposition AZERTY et mapping de départ.

Module de **données pures** (aucune I/O, aucune dépendance au web ni au terminal),
sur le même modèle que `TamrielicCalendar` : les gabarits et les routes consomment
ces constantes sans jamais coder en dur une couleur, une légende ou un scan code.

Un bind est identifié par son **scan code DirectInput** (entier), tel que le
comprennent Skyrim et ses mods (SKSE, MCM, fichiers .ini/.json). Les codes de
souris suivent la convention Skyrim (256 + numéro de bouton).

Pour ajouter une famille : une entrée dans `CATEGORIES`, rien d'autre. Les
couleurs remontent jusqu'au keycap via des variables CSS inline (voir
`_keyboard.html`), la feuille de style n'en connaît aucune.
"""

# --- Familles ------------------------------------------------------------------

# {clé: {label, ink (texte), edge (contour + bordure basse), face (fond)}}
# L'ordre d'insertion est celui du bandeau de légende.
CATEGORIES = {
    "deplacement": {"label": "Déplacement", "ink": "#8FA6BC", "edge": "#4E6D8C", "face": "#20303F"},
    "vanilla":     {"label": "Vanilla",     "ink": "#B9C6D2", "edge": "#6E7F90", "face": "#242E38"},
    "combat":      {"label": "Combat",      "ink": "#F0A878", "edge": "#C8622A", "face": "#3A2419"},
    "iequip":      {"label": "iEquip",      "ink": "#7FD4C8", "edge": "#2E9B8C", "face": "#16302E"},
    "survie":      {"label": "Survie",      "ink": "#A9CE86", "edge": "#5D8F3C", "face": "#1F2C18"},
    "interface":   {"label": "Interface",   "ink": "#C0A2E0", "edge": "#7B5AA6", "face": "#281F36"},
}

# Touche libre (non assignée) : éteinte.
FREE_KEY = {"label": "Libre", "ink": "#5A6874", "edge": "#2A333D", "face": "#1B222B"}


def palette(cat):
    """Retourne le triplet de couleurs d'une famille, ou celui d'une touche libre.

    Tolérant à une famille inconnue (bind écrit en base puis famille retirée de
    `CATEGORIES`) : on retombe sur l'aspect éteint plutôt que de casser le rendu.
    """
    return CATEGORIES.get(cat) or FREE_KEY


# --- Disposition AZERTY --------------------------------------------------------

# Format d'une touche : (scan code, légende physique, largeur, hauteur) en unités
# de keycap. Largeur et hauteur sont omises quand elles valent 1 (voir `_expand`).
# La hauteur ne sert qu'au pavé numérique — voir `_NUMPAD_RAW`.
#
# ATTENTION : les scan codes sont **positionnels** — ils décrivent l'emplacement
# physique de la touche sur un clavier US, pas le caractère imprimé dessus en
# AZERTY. C'est la source de confusion que ce module neutralise une fois pour
# toutes : la touche A française porte le code 16 (le « Q » américain), la touche
# Z porte 17 (le « W »), etc. Les mods lisent le code, jamais la lettre.
_ROWS_RAW = [
    # Rangée fonctions
    [(1, "Échap", 1.2), (59, "F1"), (60, "F2"), (61, "F3"), (62, "F4"),
     (63, "F5"), (64, "F6"), (65, "F7"), (66, "F8"), (67, "F9"),
     (68, "F10"), (87, "F11"), (88, "F12")],
    # Rangée chiffres
    [(41, "²"), (2, "&"), (3, "é"), (4, '"'), (5, "'"), (6, "("), (7, "-"),
     (8, "è"), (9, "_"), (10, "ç"), (11, "à"), (12, ")"), (13, "="),
     (14, "Retour", 1.9)],
    # Rangée A
    [(15, "Tab", 1.5), (16, "A"), (17, "Z"), (18, "E"), (19, "R"), (20, "T"),
     (21, "Y"), (22, "U"), (23, "I"), (24, "O"), (25, "P"), (26, "^"),
     (27, "$"), (28, "Entrée", 1.4)],
    # Rangée Q
    # « Verr Maj » et non « Verr » : le pavé numérique a désormais son propre
    # verrou (69). Deux touches homonymes dans `LEGENDS`, c'est exactement
    # l'ambiguïté que ce module existe pour supprimer.
    [(58, "Verr Maj", 1.8), (30, "Q"), (31, "S"), (32, "D"), (33, "F"), (34, "G"),
     (35, "H"), (36, "J"), (37, "K"), (38, "L"), (39, "M"), (40, "ù"),
     (43, "*", 1.6)],
    # Rangée W
    [(42, "Maj", 1.4), (86, "<"), (44, "W"), (45, "X"), (46, "C"), (47, "V"),
     (48, "B"), (49, "N"), (50, ","), (51, ";"), (52, ":"), (53, "!"),
     (54, "Maj D", 2.1)],
    # Rangée basse
    [(29, "Ctrl", 1.5), (56, "Alt", 1.3), (57, "Espace", 7),
     (184, "AltGr", 1.3), (157, "Ctrl D", 1.5)],
]

# Pavé numérique complet, grille 4 colonnes × 5 rangées.
#
# Il n'y avait que le carré 3×3 des chiffres 1-9 : Verr Num, « / », « * », « - »,
# « + », « 0 », « . » et l'Entrée du pavé n'étaient pas déclarées, donc invisibles
# et impossibles à assigner — alors que ce sont des candidates de choix, presque
# toutes libres sur un mapping Skyrim.
#
# Les codes ne se suivent pas et ne sont pas devinables : « / » est 181 (0xB5) et
# non 74, l'Entrée du pavé est 156 (0x9C) et non 28 — c'est une touche distincte de
# l'Entrée principale, un mod peut les lire séparément.
#
# Quatrième champ = hauteur en unités. « + » et « Entrée » couvrent deux rangées,
# comme sur le pavé physique ; les rangées qu'elles traversent n'ont donc que trois
# touches, et la grille CSS place le reste par elle-même.
_NUMPAD_RAW = [
    # « Num » et non « Verr Num » : la touche fait 1 unité, et « Verr Num » y était
    # rogné en « Verr … ». Aucune ambiguïté pour autant — l'autre verrou porte
    # « Verr Maj », et celui-ci est dans le bloc du pavé.
    [(69, "Num"), (181, "/"), (55, "*"), (74, "-")],
    [(71, "7"), (72, "8"), (73, "9"), (78, "+", 1, 2)],
    [(75, "4"), (76, "5"), (77, "6")],
    [(79, "1"), (80, "2"), (81, "3"), (156, "Entrée", 1, 2)],
    [(82, "0", 2), (83, ".")],
]

# Bloc de navigation : Inser / Suppr / Début / Fin / pages, et les flèches.
#
# Dix touches qui manquaient entièrement — donc invisibles et non assignables — alors
# qu'elles sont presque toutes libres sur un mapping Skyrim, ce qui en fait les
# meilleures candidates pour un nouveau bind.
#
# ATTENTION, et c'est le piège que ce module existe pour désamorcer : ce sont des
# touches « étendues ». Leur code vaut celui de la touche du pavé numérique située
# à la même position physique, **plus 128** :
#
#     Début  199 = 71 + 128   (le « 7 » du pavé)
#     ↑      200 = 72 + 128   (le « 8 »)
#     Pg↑    201 = 73 + 128   (le « 9 »)
#     Inser  210 = 82 + 128   (le « 0 »)
#
# Écrire 71 en croyant viser Début, c'est assigner le pavé numérique — une erreur
# silencieuse, le mod répond simplement à la mauvaise touche.
#
# La rangée de la flèche haute n'a qu'une touche : le CSS la centre, ce qui la place
# dans la colonne du milieu sans qu'aucune position n'ait à être écrite ici.
_NAVIGATION_RAW = [
    [(210, "Inser"), (199, "Début"), (201, "Pg↑")],
    [(211, "Suppr"), (207, "Fin"), (209, "Pg↓")],
    [(200, "↑")],
    [(203, "←"), (208, "↓"), (205, "→")],
]

# Souris. Les deux boutons latéraux sont nommés par leur **position physique**
# (haut / bas) et non « M4 / M5 » : c'est la confusion principale à éliminer,
# les libellés constructeur ne disent rien de la touche qu'on a sous le pouce.
_MOUSE_BUTTONS_RAW = [(256, "Clic gauche"), (258, "Molette"), (257, "Clic droit")]
_MOUSE_SIDE_RAW = [(261, "Latéral haut", 2), (260, "Latéral bas", 2)]


def _expand(row):
    """Normalise une rangée en dicts {code, legend, width, height}, 1 par défaut."""
    return [
        {
            "code": k[0],
            "legend": k[1],
            "width": k[2] if len(k) > 2 else 1,
            "height": k[3] if len(k) > 3 else 1,
        }
        for k in row
    ]


ROWS = [_expand(r) for r in _ROWS_RAW]
NUMPAD = [_expand(r) for r in _NUMPAD_RAW]
NAVIGATION = [_expand(r) for r in _NAVIGATION_RAW]
MOUSE_BUTTONS = _expand(_MOUSE_BUTTONS_RAW)
MOUSE_SIDE = _expand(_MOUSE_SIDE_RAW)


def all_keys():
    """Itère sur toutes les touches déclarées (clavier, navigation, pavé, souris)."""
    for row in ROWS + NAVIGATION + NUMPAD:
        yield from row
    yield from MOUSE_BUTTONS
    yield from MOUSE_SIDE


# Index code -> légende, pour afficher une touche hors de sa rangée (panneau
# d'édition, export, infobulle).
LEGENDS = {k["code"]: k["legend"] for k in all_keys()}


def legend_of(code):
    """Légende physique d'un scan code, ou le code lui-même s'il est inconnu."""
    return LEGENDS.get(code, str(code))


# --- Mapping de départ ---------------------------------------------------------

# Semis initial de la base : le mapping Skyrim / Nolvus réel.
# Format : {scan code: (action, famille, mémo)}.
# Le mémo répond à « où se modifie cette touche ? » — c'est l'information qu'on
# ne retrouve plus six mois après, bien plus que l'action elle-même.
DEFAULT_BINDS = {
    # --- Déplacement ---
    17:  ("Avancer", "deplacement", ""),
    30:  ("Gauche", "deplacement", ""),
    31:  ("Reculer", "deplacement", ""),
    32:  ("Droite", "deplacement", ""),
    57:  ("Saut", "deplacement", ""),
    56:  ("Sprint", "deplacement", ""),
    29:  ("Furtivité", "deplacement", ""),
    42:  ("Prone", "deplacement",
          "Sneak Behavior Extensions — JSON, combinaisons 42,17 / 42,30 / 42,32. "
          "Ne jamais remapper le déplacement dans les options du jeu, le mod "
          "écoute les codes en dur."),

    # --- Vanilla ---
    18:  ("Activer", "vanilla", ""),
    19:  ("Rengainer", "vanilla", ""),
    33:  ("Changement de vue", "vanilla",
          "Sert aussi à marquer un favori dans l'inventaire."),
    44:  ("Cri", "vanilla", ""),
    39:  ("Carte", "vanilla", "Déplacée depuis la virgule."),
    49:  ("Attendre", "vanilla", "Déplacée depuis T."),
    38:  ("Favoris", "vanilla", "Déplacés depuis A."),

    # --- Combat ---
    47:  ("Attaque puissante", "combat",
          "One Click Power Attack — ini, ForceRightKey=47, force la main droite : "
          "jamais de cast involontaire en hybride."),
    16:  ("Attaque spéciale", "combat",
          "Additional Attack By Loop — MCM, équiper et déclencher le pouvoir une "
          "fois pour activer la seconde."),
    59:  ("Stance agressive", "combat", ""),
    60:  ("Stance défensive", "combat", ""),
    260: ("Esquive", "combat", "TK Dodge RE — ini."),
    261: ("Blocage et parade", "combat",
          "À déclarer avec la MÊME touche dans Valhalla Combat "
          "(Compatibility → Alternate Blocking Key) ET dans Dual Wield Parrying. "
          "Un seul des deux = parade sans effets Valhalla, ni stagger ni contre."),

    # --- iEquip (tout se règle dans le MCM du mod) ---
    45:  ("Main droite : armes", "iequip", "MCM iEquip."),
    46:  ("Main gauche : sorts et wards", "iequip", "MCM iEquip."),
    34:  ("Cris et pouvoirs", "iequip", "MCM iEquip."),
    48:  ("Consommables et poisons", "iequip", "MCM iEquip."),
    20:  ("Utility", "iequip",
          "MCM iEquip. Ouvre le menu utilitaire, la gestion des files et l'Edit "
          "Mode ; sert aussi de combo pour cycler en sens inverse."),

    # --- Survie ---
    37:  ("Menu radial Campfire", "survie", ""),
}
