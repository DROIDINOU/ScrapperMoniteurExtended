from datetime import datetime
import re

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

def convertir_date(date_input):

    # ✅ Si on reçoit un dict { value, source, confidence }
    if isinstance(date_input, dict):
        date_str = date_input.get("date") or date_input.get("value")
    else:
        date_str = date_input

    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip().lower()

    # ✅ si déjà ISO -> NE PAS RECONVERTIR
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str

    # ✅ Extraction avant conversion
    m = re.search(
        r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b"
        r"|\b\d{1,2}\s+(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s+\d{4}\b",
        date_str
    )
    if m:
        date_str = m.group(0)

    # ➤ Formats numériques
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

    # ➤ Format texte ("20 octobre 2025")
    parties = date_str.replace(",", "").split()
    if len(parties) == 3:
        jour, mois_txt, annee = parties
        mois_txt = mois_txt.replace("é", "e")  # simplification accents
        if mois_txt in MOIS:
            return f"{int(annee):04d}-{MOIS[mois_txt]:02d}-{int(jour):02d}"

    return None
