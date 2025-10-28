# --- Imports standards ---
import re
from datetime import datetime

# --- Modules internes au projet ---
from Utilitaire.outils.MesOutils import get_month_name, convert_french_text_date_to_numeric
from Constante.mesconstantes import VILLES


# ==========================================================
# 🔹 Fonctions utilitaires communes
# ==========================================================
def extraire_date_propre(texte):
    """Renvoie uniquement la date 'JJ mois AAAA' du texte brut."""
    if not texte:
        return None
    m = re.search(
        r"(\d{1,2}(?:er)?\s+(?:janvier|février|fevrier|mars|avril|mai|juin|"
        r"juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s+\d{4})",
        texte,
        flags=re.IGNORECASE
    )
    return m.group(1).strip() if m else texte.strip()


def normaliser_date_iso(texte):
    """Convertit une date française '13 décembre 2023' en ISO '2023-12-13'."""
    if not texte:
        return None

    texte = texte.strip().lower().replace("1er", "1")
    texte = (
        texte.replace("février", "fevrier")
        .replace("août", "aout")
        .replace("décembre", "decembre")
    )

    mois_fr = {
        "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
        "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12
    }

    match = re.match(r"(\d{1,2})\s+([a-zéèêàûîôäöüç]+)\s+(\d{4})", texte)
    if not match:
        return None

    jour, mois_txt, annee = match.groups()
    mois_num = mois_fr.get(mois_txt)
    if not mois_num:
        return None

    try:
        return datetime(int(annee), mois_num, int(jour)).strftime("%Y-%m-%d")
    except Exception:
        return None


def nettoyer_sortie(texte):
    """Nettoie et normalise la date avant de la renvoyer."""
    if not texte:
        return None
    texte = extraire_date_propre(str(texte))
    iso = normaliser_date_iso(texte)
    return iso or texte


# ==========================================================
# 🔹 Fonction principale d’extraction
# ==========================================================
def extract_jugement_date(text):

    text = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    text = re.sub(r'\s+', ' ', text.replace('\xa0', ' ').replace('\n', ' ').replace('\r', ' ')).strip()
    text = re.sub(r"\b1er\s+er\b", "1er", text)

    # → ✅ Style 4 : "Cour d'appel de [Ville] Par arrêt du ..."
    match_arret_simple = re.search(
        r"(?i)\b cour \s+ d \s* ['’]? \s* appel"
        r"(?: \s+ de \s+ [A-ZÉÈÂÊÎÔÛÇÀ-ÿ'\-]+ )?"
        r"[^.\n]{0,100}? \b par \s+ arr[êe]t \s+ du \s+"
        r"(\d{1,2}(?:er)? \s+ \w+ \s+ \d{4})",
        text[:400], flags=re.IGNORECASE | re.VERBOSE
    )
    if match_arret_simple:
        return nettoyer_sortie(match_arret_simple.group(1))

    # → ✅ Style 5 : "Cour d'appel de [Ville] Arrêt du ..."
    match_arret_direct = re.search(
        r"(?i)\b cour \s+ d \s* ['’]? \s* appel"
        r"(?: \s+ de \s+ [A-ZÉÈÂÊÎÔÛÇÀ-ÿ'\-]+ )?"
        r"[^.\n]{0,100}? \b arr[êe]t \s+ du \s+"
        r"(\d{1,2}(?:er)? \s+ \w+ \s+ \d{4})",
        text, flags=re.IGNORECASE | re.VERBOSE
    )
    if match_arret_direct:
        return nettoyer_sortie(match_arret_direct.group(1))

    # ==========================================================
    # 🔹 1. Cas spécifique : Cour d’Appel
    # ==========================================================
    # → ✅ Style 3 : "Arrêt rendu à l’audience publique (extraordinaire)? du ..."
    match_arret_audience = re.search(
        r"(?i)\b cour \s+ d \s* ['’]? \s* appel"
        r"(?: \s+ de \s+ [A-ZÉÈÂÊÎÔÛÇÀ-ÿ'\-]+ )?"
        r"[^.\n]{0,120}? "
        r"arr[êe]t \s+ rendu \s+ à \s+ l \s* ['’] \s* audience \s+ publique"
        r"(?: \s+ extraordinaire )? \s+ du \s+"
        r"(\d{1,2}(?:er)? \s+ \w+ \s+ \d{4})",
        text[:400], flags=re.IGNORECASE | re.VERBOSE
    )
    if match_arret_audience:
        return nettoyer_sortie(match_arret_audience.group(1))

    # 🔸 Variante sans “Cour d’appel” (texte tronqué)
    match_arret_audience_simple = re.search(
        r"(?i)\b arr[êe]t \s+ rendu \s+ à \s+ l \s* ['’] \s* audience \s+ publique"
        r"(?: \s+ extraordinaire )? \s+ du \s+"
        r"(\d{1,2}(?:er)? \s+ \w+ \s+ \d{4})",
        text[400], flags=re.IGNORECASE | re.VERBOSE
    )
    if match_arret_audience_simple:
        return nettoyer_sortie(match_arret_audience_simple.group(1))
    # 🔹 Cas spécifique bis : "Cour d'Appel ... Extrait de l'arrêt du ..."
    match_arret_extrait = re.search(
        r"cour\s+d['’]appel\s+(?:de\s+[A-ZÉÈÊËÀÂÇÎÏÔÙÛÜA-Za-zà-ÿ'\-]+\s+)?"
        r"(?:.{0,50}?extrait\s+de\s+l['’]arr[êe]t\s+du\s+"
        r"(\d{1,2}(?:er)?\s+\w+\s+\d{4}))",
        text[:600],
        flags=re.IGNORECASE
    )
    if match_arret_extrait:
        return nettoyer_sortie(match_arret_extrait.group(1))

    # Variante sans "Cour d’Appel" (texte tronqué)
    match_arret_extrait_simple = re.search(
        r"extrait\s+de\s+l['’]arr[êe]t\s+du\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        text[:600],
        flags=re.IGNORECASE
    )
    if match_arret_extrait_simple:
        return nettoyer_sortie(match_arret_extrait_simple.group(1))

    # Variante sans "Cour d’Appel" (texte tronqué)
    match_arret_simple = re.search(
        r"de\s+l['’]arr[êe]t(?:\s+(?:contradictoire|par\s+d[ée]faut))?\s+rendu\s+le\s+"
        r"(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        text[:600],
        flags=re.IGNORECASE
    )
    if match_arret_simple:
        return nettoyer_sortie(match_arret_simple.group(1))
    # 🔹 3. Après "division [Ville]" suivie de "le ..."
    match_division = re.search(
        r"division(?:\s+de)?\s+[A-ZÉÈÊËÀÂÇÎÏÔÙÛÜA-Za-zà-ÿ'\-]+.{0,60}?\b(?:le|du)\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        text, flags=re.IGNORECASE
    )
    if match_division:
        return nettoyer_sortie(match_division.group(1))

    # 🔹 "Date du jugement : ..."
    match_date_jugement_label = re.search(
        r"date\s+du\s+jugement\s*[:\-–]?\s*(.{0,30})",
        text, flags=re.IGNORECASE
    )
    if match_date_jugement_label:
        return nettoyer_sortie(match_date_jugement_label.group(1))

    # 🔹 "par ordonnance prononcée en date du ..."
    match_intro = re.search(
        r"par\s+ordonnance\s+prononc[ée]e?.{0,200}?en\s+date\s+du\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        text[:500], flags=re.IGNORECASE
    )
    if match_intro:
        return nettoyer_sortie(match_intro.group(1))

    # 🔹 "Par jugement du ..."
    match_jugement_intro = re.search(
        r"par\s+jugement\s+du\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})",
        text[:400], flags=re.IGNORECASE
    )
    if match_jugement_intro:
        return nettoyer_sortie(match_jugement_intro.group(1))

    # 🔹 Ville à la fin
    match_ville_date_fin = re.search(
        rf"\.{{0,5}}\s*(?:{VILLES})\b[^a-zA-Z0-9]{{1,5}}le\s+(\d{{1,2}}(?:er)?\s+\w+\s+\d{{4}})\.",
        text[-300:], flags=re.IGNORECASE
    )
    if match_ville_date_fin:
        return nettoyer_sortie(match_ville_date_fin.group(1))

    # 🔹 Cas "tribunal de première instance"
    match = re.search(
        r"par\s+jugement\s+du\s+(\d{1,2}[./-]\d{1,2}[./-]\d{4}|\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        text, flags=re.IGNORECASE
    )
    if match:
        start_pos = match.start()
        context = text[max(0, start_pos - 100):start_pos].lower()
        if "tribunal de première instance" in context:
            return nettoyer_sortie(match.group(1))

    # 🔹 Cas avec contexte
    debut = text[:300].lower()
    match_date = re.search(r"\b(le\s+\d{1,2}(?:er)?\s+\w+\s+\d{4})", debut)
    if match_date:
        position = match_date.start()
        contexte_large = debut[max(0, position - 150):position]
        contexte_court = debut[max(0, position - 30):position]
        if "tribunal de première instance" in contexte_large and not re.search(r"\bn[ée]e?\b", contexte_court):
            return nettoyer_sortie(match_date.group(1))

    # 🔹 Cas : "Par jugement rendu contradictoirement / par défaut / en dernier ressort le ..."
    match_intro_jugement = re.search(
        r"par\s+jugement\s+rendu(?:\s+contradictoirement|\s+par\s+d[ée]faut|\s+en\s+dernier\s+ressort)?\s+le\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        text[:800],
        flags=re.IGNORECASE
    )
    if match_intro_jugement:
        return nettoyer_sortie(match_intro_jugement.group(1))

    # 🔹 4. Formulations classiques
    patterns = [
        r"[Pp]ar\s+d[ée]cision\s+prononc[ée]e?\s+le\s+(\d{1,2}(?:er)?[\s/-]\w+[\s/-]\d{4})",
        r"[Pp]ar\s+jugement\s+(?:rendu\s+)?(?:le|du)\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        r"[Pp]ar\s+ordonnance\s+(?:rendue|prononcée)\s+le\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        r"[Pp]ar\s+d[ée]cision\s+du\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"jugement\s+rendu\s+le\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"[Pp]ar\s+(?:son\s+)?ordonnance\s+du\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return nettoyer_sortie(match.group(1))
    print("on arrive ici au moins une fois !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    # 🔹 Fallback universel : première date trouvée dans les 500 premiers caractères
    zone_recherche = text[:500]  # ✅ on limite la recherche au début du texte

    match_final = re.finditer(
        r"\b(\d{1,2}(?:er)?\s+(?:janvier|février|fevrier|mars|avril|mai|juin|"
        r"juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s+\d{4})",
        zone_recherche,
        flags=re.IGNORECASE
    )

    # On récupère date + position pour vraiment prendre la première dans le texte
    dates_positionnees = [(m.group(1), m.start()) for m in match_final]

    # Filtrer les dates du type "née le"
    dates_filtrees = [
        d for d, pos in dates_positionnees
        if not re.search(r"n[ée]e?\s+le\s+" + re.escape(d), zone_recherche, re.IGNORECASE)
    ]

    if dates_filtrees:
        return nettoyer_sortie(dates_filtrees[0])  # ✅ première date dans le texte

    return None

