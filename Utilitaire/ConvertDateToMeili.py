from datetime import datetime

MOIS = {
    "janvier": 1, "jan": 1, "january": 1,
    "février": 2, "fev": 2, "fév": 2, "february": 2, "feb": 2,
    "mars": 3, "mar": 3, "march": 3,
    "avril": 4, "avr": 4, "apr": 4, "april": 4,
    "mai": 5, "may": 5,
    "juin": 6, "jun": 6, "june": 6,
    "juillet": 7, "jul": 7, "july": 7,
    "août": 8, "aout": 8, "aug": 8, "august": 8,
    "septembre": 9, "sep": 9, "september": 9,
    "octobre": 10, "oct": 10, "october": 10,
    "novembre": 11, "nov": 11, "november": 11,
    "décembre": 12, "dec": 12, "déc": 12, "december": 12
}

def convertir_date(date_str):
    """
    Convertit une date (numérique ou textuelle) en format 'YYYY-MM-DD'.
    Retourne None si la date est vide ou invalide.
    """
    # --- AJOUT : prise en charge des listes/tuples ---
    if isinstance(date_str, (list, tuple)):
        out, seen = [], set()
        for s in date_str:
            if not isinstance(s, str):
                continue
            iso = convertir_date(s)  # réutilise la logique existante
            if iso and iso not in seen:
                seen.add(iso)
                out.append(iso)
        return out or None
    # -------------------------------------------------

    if not date_str or not isinstance(date_str, str):
        return None  # On ne plante pas, on retourne None

    date_str = date_str.strip().lower()

    # Essai avec formats numériques classiques
    formats_possibles = [
        "%d/%m/%Y", "%Y/%m/%d",
        "%d-%m-%Y", "%Y-%m-%d",
        "%d.%m.%Y", "%d/%m/%y",
        "%y-%m-%d"
    ]
    for fmt in formats_possibles:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Essai avec noms de mois
    parties = date_str.replace(",", "").split()
    if len(parties) == 3:
        jour, mois_txt, annee = parties
        if mois_txt in MOIS:
            mois_num = MOIS[mois_txt]
            return f"{int(annee):04d}-{mois_num:02d}-{int(jour):02d}"

    return None  # Si aucun format ne correspond