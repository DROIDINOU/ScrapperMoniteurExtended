import re


def fallback_nom(text):
    # 🔹 Nom/prénom APRÈS "liquidateur"/"curateur"
    pattern_avant = (
        r"(curateur|liquidateur(?:\(s\))?)\s*(?:désigné\(s\))?\s*:?\s*"
        r"((?:[A-ZÉÈÀÂÊÎÔÛÇ][a-zéèêàîôûç\-']+\s+){0,3}"
        r"[A-ZÉÈÀÂÊÎÔÛÇ][a-zéèêàîôûç\-']+)"
    )
    match = re.search(pattern_avant, text, flags=re.IGNORECASE)
    if match:
        raw = match.group(2).strip()
        mots = re.findall(r"[A-ZÉÈÀÂÊÎÔÛÇ][a-zéèêàîôûç\-']+", raw)
        if 1 <= len(mots) <= 4:
            return " ".join(mots)

    # 🔹 Nom/prénom AVANT "liquidateur"/"curateur"
    pattern_apres = (
        r"((?:[A-ZÉÈÀÂÊÎÔÛÇ][a-zéèêàîôûç\-']+\s+){0,3}"
        r"[A-ZÉÈÀÂÊÎÔÛÇ][a-zéèêàîôûç\-']+)"
        r"\s*,?\s*(curateur|liquidateur(?:\(s\))?)\s*(?:désigné\(s\))?"
    )
    match2 = re.search(pattern_apres, text, flags=re.IGNORECASE)
    if match2:
        raw = match2.group(1).strip()
        mots = re.findall(r"[A-ZÉÈÀÂÊÎÔÛÇ][a-zéèêàîôûç\-']+", raw)
        if 1 <= len(mots) <= 4:
            return " ".join(mots)

    return None




def extract_administrateur(text):
    """
    Extrait le nom du curateur ou liquidateur (ex : BERNARD POPYN, S. HUART)
    à partir de phrases contenant 'Curateur' ou 'Liquidateur'
    """

    # 1. Curateur avec 2 à 3 blocs en majuscules
    pattern1 = r"curateur\s*:?\s*([A-ZÉÈÀÂÊÎÔÛÇ]+(?:\s+[A-ZÉÈÀÂÊÎÔÛÇ]+){1,3})"

    # 2. Liquidateur avec Prénom + NOM
    pattern2 = (
        r"liquidateur(?:\(s\))?\s*(?:désigné\(s\))?\s*:?\s*"
        r"(\d+\.\s*)?"  # ex : "1. "
        r"(?:Me|Maître|M(?:onsieur)?|Mme|Madame|Mr|M\.)?\.?\s*"
        r"([A-Z][a-zéèêàîç\-']+)\s+([A-ZÉÈÀÂÊÎÔÛÇ\-]{2,})"
    )

    # 3. Liquidateur avec 1 à 3 blocs majuscules
    pattern3 = (
        r"liquidateur(?:\(s\))?\s*(?:désigné\(s\))?\s*:?\s*"
        r"(?:Me|M(?:onsieur)?|Mme|Madame|Mr|M\.|Maître)?\.?\s*"
        r"((?:[A-ZÉÈÀÂÊÎÔÛÇ\-]{2,}(?:\s+|$)){1,4})"
    )

    # 4. Format initiale + NOM (ex : S. HUART)
    pattern4 = r"""
        liquidateur(?:\(s\))?
        \s*:?\s*
        \d*\.?\s*
        (?:me|maître|mr|mme|madame|m\.)?\s*
        (?P<nom>[A-Z](?:\.\-?[A-Z])?\.\s*[A-ZÉÈÀÂÊÎÔÛÇ\-]{2,})
    """

    match = re.search(pattern1, text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()

    match2 = re.search(pattern2, text, flags=re.IGNORECASE)
    if match2:
        prenom = match2.group(2)
        nom = match2.group(3)
        return f"{prenom} {nom}"

    match3 = re.search(pattern3, text, flags=re.IGNORECASE)
    if match3:
        nom_brut = match3.group(1).strip()
        mots = re.findall(r"[A-ZÉÈÀÂÊÎÔÛÇ\-]{2,}", nom_brut)
        if 1 <= len(mots) <= 4:
            return " ".join(mots)

    match4 = re.search(pattern4, text, flags=re.IGNORECASE | re.VERBOSE)
    if match4:
        return match4.group("nom").strip()

    return fallback_nom(text)

