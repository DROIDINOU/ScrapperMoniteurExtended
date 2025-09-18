# --- Imports standards ---
import re

# --- Modules internes au projet ---
from Utilitaire.outils.MesOutils import get_month_name, convert_french_text_date_to_numeric
from Constante.mesconstantes import VILLES, JOURMAP, MOISMAP, ANNEMAP


# ATTENTION A RETRAVAILLER PAS COMPLET
def extract_jugement_date(text):
    """
    Extrait une date de jugement depuis un texte.
    Priorité :
    1. "passe en force de chose jugée le ..."
    2. Date 100 caractères avant "le greffier"
    3. Date après "division [ville]"
    4. Autres formulations classiques
    """

    text = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    # Sécurité en cas de texte mal nettoyé
    text = re.sub(r'\s+', ' ', text.replace('\xa0', ' ').replace('\n', ' ').replace('\r', ' ')).strip()
    text = re.sub(r"\b1er\s+er\b", "1er", text)
    # 🔹 2. Date dans les 100 caractères avant "le greffier"
    match_greffier = re.search(r"(.{0,100})\ble\s+greffier", text, flags=re.IGNORECASE | re.DOTALL)
    if match_greffier:
        zone = match_greffier.group(1)
        date_patterns = [
            r"(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
            r"(\d{2})[/-](\d{2})[/-](\d{4})",
            r"(\d{4})[/-](\d{2})[/-](\d{2})"
        ]
        for pat in date_patterns:
            match_date = re.search(pat, zone)
            if match_date:
                groups = match_date.groups()
                if len(groups) == 3:
                    if pat.startswith(r"(\d{4})[/-]"):
                        yyyy, mm, dd = groups
                    else:
                        dd, mm, yyyy = groups
                    return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"
                else:
                    return match_date.group(1).strip()
    # 🔹 3. Date après "division [Ville]" suivie de "le ..."
    match_division = re.search(
        r"division(?:\s+de)?\s+[A-ZÉÈÊËÀÂÇÎÏÔÙÛÜA-Za-zà-ÿ'\-]+.{0,60}?\b(?:le|du)\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        text, flags=re.IGNORECASE
    )
    if match_division:
        raw = match_division.group(1).strip()
        raw = match_division.group(1).strip().strip(",.;")

        if re.search(r"\d{1,2}(?:er)?\s+\w+\s+\d{4}", raw):
            return raw
        match_slash = re.search(r"(\d{2})/(\d{2})/(\d{4})", raw)
        if match_slash:
            dd, mm, yyyy = match_slash.groups()
            return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"
        match_dash_ddmm = re.search(r"(\d{2})-(\d{2})-(\d{4})", raw)
        if match_dash_ddmm:
            dd, mm, yyyy = match_dash_ddmm.groups()
            return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"
        match_dash = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
        if match_dash:
            yyyy, mm, dd = match_dash.groups()
            return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"
        try:
            return convert_french_text_date_to_numeric(raw)
        except:
            pass

    # 🔹 Nouveau : "Date du jugement : 15 juillet 2025"
    match_date_jugement_label = re.search(
        r"date\s+du\s+jugement\s*[:\-–]?\s*(.{0,30})",
        text,
        flags=re.IGNORECASE
    )
    if match_date_jugement_label:
        raw = match_date_jugement_label.group(1).strip()

        # Formats à tester
        if re.search(r"\d{1,2}(?:er)?\s+\w+\s+\d{4}", raw):
            return raw
        match_slash = re.search(r"(\d{2})/(\d{2})/(\d{4})", raw)
        if match_slash:
            dd, mm, yyyy = match_slash.groups()
            return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"
        match_dash = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
        if match_dash:
            yyyy, mm, dd = match_dash.groups()
            return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"
        try:
            converted = convert_french_text_date_to_numeric(raw)
            if converted:
                return converted
        except:
            pass

    match_intro = re.search(
        r"par\s+ordonnance\s+prononc[ée]e?.{0,200}?en\s+date\s+du\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        text[:500],
        flags=re.IGNORECASE
    )
    if match_intro:
        return match_intro.group(1).strip()

    # 🔹 0. "Par jugement du <date>" dans les 400 premiers caractères
    match_jugement_intro = re.search(
        r"par\s+jugement\s+du\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})",
        text[:400],
        flags=re.IGNORECASE
    )
    if match_jugement_intro:
        return match_jugement_intro.group(1).strip()

    match_ville_date_fin = re.search(
        rf"\.{{0,5}}\s*(?:{VILLES})\b[^a-zA-Z0-9]{{1,5}}le\s+(\d{{1,2}}(?:er)?\s+\w+\s+\d{{4}})\.",
        text[-300:],
        flags=re.IGNORECASE
    )
    if match_ville_date_fin:
        return match_ville_date_fin.group(1).strip()
    # Cas spécial : date juste après "par jugement du", avec contexte "tribunal de première instance"
    match = re.search(
        r"par\s+jugement\s+du\s+(\d{1,2}[./-]\d{1,2}[./-]\d{4}|\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        text,
        flags=re.IGNORECASE
    )
    if match:
        start_pos = match.start()
        context = text[max(0, start_pos - 100):start_pos].lower()
        if "tribunal de première instance" in context:
            return match.group(1).strip()
    # Cas spécifique : date précédée dans les 150 caractères par "tribunal de première instance",
    # dans les 300 premiers caractères
    debut = text[:300].lower()
    match_date = re.search(r"\b(le\s+\d{1,2}(?:er)?\s+\w+\s+\d{4})", debut)
    if match_date:
        position = match_date.start()
        contexte_large = debut[max(0, position - 150):position]
        contexte_court = debut[max(0, position - 30):position]

        if "tribunal de première instance" in contexte_large:
            # ⛔ Exclure si le contexte court contient une naissance
            if re.search(r"\bn[ée]e?\b", contexte_court):
                pass  # Date ignorée
            else:
                return match_date.group(1).strip()

    # 🔹 4. Formulations classiques
    patterns = [
        r"[Pp]ar\s+d[ée]cision\s+prononc[ée]e?\s+le\s+(\d{2}[-/]\d{2}[-/]\d{4})",
        r"par\s+jugement\s+contradictoire\s+rendu\s+le\s+(\d{2}/\d{2}/\d{4})",
        r"ordonnance\s+d[ée]livr[ée]e?\s+par\s+la\s+\d{1,2}(?:e|er)?\s+chambre.*?\ble\s+(\d{2}/\d{2}/\d{4})",
        r"par\s+ordonnance\s+d[ée]livr[ée]e?.{0,200}?\b(\d{2}/\d{2}/\d{4})",
    ]

    patterns += [
        r"[Pp]ar\s+d[ée]cision\s+prononc[ée]e?\s+le\s+(\d{1,2}(?:er)?[\s/-]\w+[\s/-]\d{4}|\d{2}[-/]\d{2}[-/]\d{4}|\d{4}-\d{2}-\d{2})",
        r"[Dd]ate\s+du\s+jugement\s*[:\-]?\s*(\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})",
        r"[Pp]ar\s+ordonnance\s+(?:rendue|prononcée)\s+le\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{2}/\d{2}/\d{4})",
        r"[Pp]ar\s+jugement\s+(?:rendu\s+)?(?:le|du)\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{2}/\d{2}/\d{4})",
        r"[Pp]ar\s+d[ée]cision\s+prononc[ée]e?\s+le\s+(\d{1,2}\s+\w+\s+\d{4}|\d{2}/\d{2}/\d{4})",
        r"d[ée]cision\s+prononc[ée]e?\s+le\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{2}[-/]\d{2}[-/]\d{4})",
    ]

    patterns += [
        r"[Pp]ar\s+(?:son\s+)?ordonnance\s+du\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        r"[Pp]ar\s+ordonnance\s+(?:rendue|prononcée)\s+en\s+date\s+du\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"[Pp]ar\s+ordonnance\s+prononcée,\s+en\s+date\s+du\s+(\d{2}/\d{2}/\d{4})",
        r"[Pp]ar\s+d[ée]cision\s+du\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"jugement\s+rendu\s+le\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"[Pp]ar\s+(?:sa|son)?\s*(?:ordonnance|décision|jugement)\s+de.*?\b(?:le|du)\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"d[ée]cision\s+de\s+la\s+\d{1,2}(?:[eE])?\s+chambre.*?le\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"[Pp]ar\s+ordonnance\s+du\s+(\d{1,2}[./-]\d{1,2}[./-]\d{4})"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            raw = match.group(1).strip()

            # Nettoyage final si besoin
            raw = raw.strip(",.;")

            # Si déjà au bon format texte
            if re.search(r"\d{1,2}(?:er)?\s+\w+\s+\d{4}", raw):
                return raw
            match_dash_ddmm = re.search(r"(\d{2})-(\d{2})-(\d{4})", raw)
            if match_dash_ddmm:
                dd, mm, yyyy = match_dash_ddmm.groups()
                return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"
            # dd/mm/yyyy
            match_slash = re.search(r"(\d{2})/(\d{2})/(\d{4})", raw)
            if match_slash:
                dd, mm, yyyy = match_slash.groups()
                return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"

            # dd.mm.yyyy
            match_point = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", raw)
            if match_point:
                dd, mm, yyyy = match_point.groups()
                return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"

            # yyyy-mm-dd
            match_dash = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
            if match_dash:
                yyyy, mm, dd = match_dash.groups()
                return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"

            # En dernier recours : conversion texte → date
            try:
                converted = convert_french_text_date_to_numeric(raw)
                if converted:
                    return converted
            except:
                pass

    return None
