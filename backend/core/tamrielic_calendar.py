"""Calendrier tamrielien (univers The Elder Scrolls / Skyrim).

Fournit les constantes du calendrier de jeu et des fonctions pures de
formatage / parsing d'une date de session, afin que les interfaces (web et CLI)
manipulent des composants structurés (ère, année, mois, jour) plutôt qu'une
chaîne de texte libre saisie à la main.

La date **stockée** reste écrite en anglais (« Evening Star, 15th, 4E 201 »),
format compatible avec les dates déjà présentes dans les XML TakeNotes et avec
l'affichage in-game de Skyrim.

Réf. : https://lagbt.wiwiland.net/index.php?title=Calendrier_tamrielien
"""

import re

# Les 12 mois du calendrier, dans l'ordre : (nom anglais, nom français, nb de jours).
# Le nom anglais est celui utilisé dans la date stockée ; le nom français sert
# uniquement à reconnaître d'éventuelles anciennes dates saisies en français.
MONTHS = [
    ("Morning Star", "Primétoile", 31),   # Janvier
    ("Sun's Dawn", "Clairciel", 28),       # Février
    ("First Seed", "Semailles", 31),       # Mars
    ("Rain's Hand", "Ondepluie", 30),      # Avril
    ("Second Seed", "Plantaisons", 31),    # Mai
    ("Midyear", "Mi-l'an", 30),            # Juin
    ("Sun's Height", "Hautzénith", 31),    # Juillet
    ("Last Seed", "Vifazur", 31),          # Août
    ("Hearthfire", "Âtrefeu", 30),         # Septembre
    ("Frostfall", "Soufflegivre", 31),     # Octobre
    ("Sun's Dusk", "Sombreciel", 30),      # Novembre
    ("Evening Star", "Soirétoile", 31),    # Décembre
]

# Les 7 jours de la semaine tamrielienne (fournis à titre de référence).
WEEKDAYS = ["Morndas", "Tirdas", "Middas", "Turdas", "Fredas", "Loredas", "Sundas"]

# Les ères connues (1re à 4e). Skyrim se déroule en 4E.
ERAS = [1, 2, 3, 4]

# Nombre maximum de jours dans un mois (bornes du menu déroulant « jour »).
MAX_DAYS = max(days for _, _, days in MONTHS)

# Valeurs par défaut si aucune date connue : début de Skyrim (4E 201).
DEFAULT = {"era": 4, "year": 201, "month_index": 11, "day": 15}


def month_names_en():
    """Liste des noms de mois en anglais, dans l'ordre du calendrier."""
    return [en for en, _fr, _days in MONTHS]


def days_in_month(month_index):
    """Nombre de jours du mois d'index donné (0 = Morning Star)."""
    return MONTHS[month_index][2]


def clamp_day(month_index, day):
    """Ramène `day` dans [1, nombre de jours du mois]."""
    return max(1, min(int(day), MONTHS[month_index][2]))


def ordinal(day):
    """Suffixe ordinal anglais : 1 -> '1st', 2 -> '2nd', 15 -> '15th'…"""
    day = int(day)
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def format_date(era, year, month_index, day):
    """Assemble une date à partir de ses composants -> « Evening Star, 15th, 4E 201 »."""
    month_index = int(month_index)
    month_name = MONTHS[month_index][0]
    return f"{month_name}, {ordinal(day)}, {int(era)}E {int(year)}"


def parse_date(text):
    """Décompose une date écrite en composants, ou renvoie None si non reconnue.

    Tolérant : accepte « Evening Star, 15th, 4E 201 », les variations d'espaces,
    l'absence de suffixe ordinal et les noms de mois en français (anciennes dates).
    """
    if not text:
        return None
    m = re.match(
        r"^\s*(.+?)\s*,\s*(\d+)(?:st|nd|rd|th)?\s*,\s*(\d+)\s*E\s+(\d+)\s*$",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    month_name = m.group(1).strip().lower()
    day, era, year = int(m.group(2)), int(m.group(3)), int(m.group(4))
    month_index = None
    for i, (en, fr, _days) in enumerate(MONTHS):
        if month_name in (en.lower(), fr.lower()):
            month_index = i
            break
    if month_index is None:
        return None
    return {
        "era": era,
        "year": year,
        "month_index": month_index,
        "day": clamp_day(month_index, day),
    }


def components_or_default(text):
    """Décompose une date connue en composants, ou retombe sur DEFAULT si illisible.

    Sert à pré-remplir les menus déroulants du formulaire à partir de la dernière
    date connue de la catégorie (qui peut être vide ou dans un format inattendu).
    """
    parsed = parse_date(text)
    return parsed if parsed is not None else dict(DEFAULT)
