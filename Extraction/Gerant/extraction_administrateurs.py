import re

# -----------------------------------------------------------------
# Fallback : nom après ou avant "liquidateur"/"curateur"
# -----------------------------------------------------------------
def fallback_nom(text):
    pattern_avant = (
        r"(curateur|liquidateur(?:\(s\))?)\s*(?:désigné\(s\))?\s*:?\s*"
        r"((?:[A-ZÉÈÀÂÊÎÔÛÇ][a-zéèêàîôûç\-']+\s+){0,3}"
        r"[A-ZÉÈÀÂÊÎÔÛÇ][a-zéèêàîôûç\-']+)"
    )
    match = re.search(pattern_avant, text, flags=re.IGNORECASE)
    if match:
        role = match.group(1).lower()
        raw = match.group(0).strip()
        mots = re.findall(r"[A-ZÉÈÀÂÊÎÔÛÇ][a-zéèêàîôûç\-']+", match.group(2).strip())
        if 1 <= len(mots) <= 4:
            return {"role": role, "entity": " ".join(mots), "raw": raw}

    pattern_apres = (
        r"((?:[A-ZÉÈÀÂÊÎÔÛÇ][a-zéèêàîôûç\-']+\s+){0,3}"
        r"[A-ZÉÈÀÂÊÎÔÛÇ][a-zéèêàîôûç\-']+)"
        r"\s*,?\s*(curateur|liquidateur(?:\(s\))?)\s*(?:désigné\(s\))?"
    )
    match2 = re.search(pattern_apres, text, flags=re.IGNORECASE)
    if match2:
        role = match2.group(2).lower()
        raw = match2.group(0).strip()
        mots = re.findall(r"[A-ZÉÈÀÂÊÎÔÛÇ][a-zéèêàîôûç\-']+", match2.group(1).strip())
        if 1 <= len(mots) <= 4:
            return {"role": role, "entity": " ".join(mots), "raw": raw}
    return None


# -----------------------------------------------------------------
# Nettoyage liste administrateurs
# -----------------------------------------------------------------
def clean_admin_list(admins):
    stopwords = {"LE", "LA", "DE", "DES", "DU", "S-", "C-", "L'", "D'"}
    adresse_keywords = {"RUE", "AVENUE", "CHAUSSÉE", "BOULEVARD", "PLACE", "CHEMIN", "QUAI", "IMPASSE", "SQUARE"}
    bruit_keywords = {"DROIT", "PLEIN DROIT", "JURIDICTION", "TRIBUNAL", "JUSTICE", "INSTANCE"}

    cleaned = []
    for a in admins:
        if not isinstance(a, dict):
            continue
        entity = a.get("entity", "").strip().upper()
        if not entity or len(entity) < 3:
            continue
        if len(entity.split()) == 1:
            continue
        if any(k in entity for k in adresse_keywords | bruit_keywords | stopwords):
            continue
        cleaned.append(a)

    # Dédupliquer par entity
    seen = set()
    final = []
    for adm in cleaned:
        ent = adm["entity"].lower()
        if ent not in seen:
            seen.add(ent)
            final.append(adm)
    return final


# -----------------------------------------------------------------
# Extraction principale
# -----------------------------------------------------------------
def extract_administrateur(text):
    """
    Extrait les mandataires (liquidateurs, curateurs…)
    Retourne une liste de dictionnaires {role, entity, raw}
    """
    text = re.sub(r"[\u00A0\u202F\u2009\u2002\u2003]+", " ", text)  # tous les espaces spéciaux
    text = re.sub(r"[‐-‒–—―]", "-", text)
    text = re.sub(r"\s+", " ", text)  # normalise tous les espaces multiples
    administrateurs = []

    def add_admin(role, entity, raw):
        if entity:
            administrateurs.append({
                "role": role.lower(),
                "entity": entity.strip(),
                "raw": raw.strip()
            })


    # --- A. "a déchargé Me X Y de sa mission de curateur"
    m = re.search(
        r"(?:a\s+)?d[ée]charg[ée]?\s+(?:Me|Ma(?:ître)?|M(?:\.|onsieur)?|Mme|Madame)?\s*"
        r"([A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÀ-ÖØ-öø-ÿ\-']+(?:\s+[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÀ-ÖØ-öø-ÿ\-']+){0,4})"
        r"\s+de\s+sa\s+mission\s+de\s+curateur(?:rice)?\b",
        text, flags=re.IGNORECASE)
    if m:
        add_admin("curateur", m.group(1), m.group(0))

    # --- B. "X Y, curateur"
    for nom in re.findall(
        r"(?:Me|Ma(?:ître)?|M(?:\.|onsieur)?|Mme|Madame|Mr)?\s*"
        r"([A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÀ-ÖØ-öø-ÿ\-']+(?:\s+[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÀ-ÖØ-öø-ÿ\-']+){0,4})"
        r"\s*,\s*curateur(?:rice)?\b", text, flags=re.IGNORECASE):
        add_admin("curateur", nom, f"{nom}, curateur")

    # --- 0. Multi-liquidateurs (ancien comportement conservé)
    pattern_multi = (
        r"(?:^|[\s,.;0-9])liquidateur(?:s)?(?:\s+désigné\(s\))?\s*:?\s*"
        r"((?:\d+\.\s*(?:monsieur|madame|me|ma[iî]tre)?\s*[A-ZÉÈÀÂÊÎÔÛÇ]"
        r"[A-Za-zÉÈÀÂÊÎÔÛÇ\-\s']+?\s*-\s*)+|"
        r"(?:\d+\.\s*(?:monsieur|madame|me|ma[iî]tre)?\s*[A-ZÉÈÀÂÊÎÔÛÇ]"
        r"[A-Za-zÉÈÀÂÊÎÔÛÇ\-\s']+))"
    )
    m = re.search(pattern_multi, text, flags=re.IGNORECASE)

    # ➜ Nouveau : si pas de match, accepter un seul bloc "1. NOM - ..."
    if not m:
        pattern_single = (
            r"(?:liquidateur(?:s)?(?:\s+désigné\(s\))?\s*:?\s*)"
            r"(\d+\.\s*(?:monsieur|madame|me|ma[iî]tre)?\s*[A-ZÉÈÀÂÊÎÔÛÇ]"
            r"[A-Za-zÉÈÀÂÊÎÔÛÇ\-\s']+)"
        )
        m = re.search(pattern_single, text, flags=re.IGNORECASE)

    if m:
        bloc = m.group(1)
        # Ancien : (?=-)  ➜ Nouveau : (?:-|$) pour capter aussi la fin de ligne
        noms = re.findall(
            r"(?:monsieur|madame|me|ma[iî]tre)?\s*"
            r"([A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÉÈÀÂÊÎÔÛÇ\-\s']+?)\s*(?:-|$)",
            bloc,
            flags=re.IGNORECASE
        )
        for n in noms:
            add_admin("liquidateur", n, n)

    # --- 1. Société avant adresse
    m = re.search(
        r"(?:liquidateur|curateur)(?:\(s\))?\s*(?:désigné\(s\))?\s*:?\s*"
        r"((?:[A-ZÉÈÀÂÊÎÔÛÇ]{2,5}\s+)?[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÉÈÀÂÊÎÔÛÇ\-\&\.\s']+?)"
        r"(?=\s+(RUE|AVENUE|CHAUSS[ÉE]E|BOULEVARD|PLACE|CHEMIN|QUAI|IMPASSE|SQUARE)\b)",
        text, flags=re.IGNORECASE)
    if m:
        add_admin("liquidateur", m.group(1), m.group(0))

    # --- 2. Curateur majuscules
    m = re.search(r"curateur\s*:?\s*([A-ZÉÈÀÂÊÎÔÛÇ]+(?:\s+[A-ZÉÈÀÂÊÎÔÛÇ]+){1,4})", text)
    if m:
        add_admin("curateur", m.group(1), m.group(0))

    # --- 3. Liquidateur prénom + NOM
    m = re.search(
        r"liquidateur(?:\(s\))?\s*(?:désigné\(s\))?\s*:?\s*"
        r"(\d+\.\s*)?"
        r"(?:Me|Maître|M(?:onsieur)?|Mme|Madame|Mr|M\.)?\.?\s*"
        r"([A-Z][a-zéèêàîç\-']+(?:\s+[A-Z][a-zéèêàîç\-']+){0,2})\s+"
        r"([A-ZÉÈÀÂÊÎÔÛÇ\-]{2,}(?:\s+[A-ZÉÈÀÂÊÎÔÛÇ\-]{2,}){0,1})",
        text, flags=re.IGNORECASE)
    if m:
        add_admin("liquidateur", f"{m.group(2)} {m.group(3)}", m.group(0))

    # --- 4. Liquidateur majuscules
    m = re.search(
        r"liquidateur(?:\(s\))?\s*(?:désigné\(s\))?\s*:?\s*"
        r"(?:Me|M(?:onsieur)?|Mme|Madame|Mr|M\.|Maître)?\.?\s*"
        r"((?:[A-ZÉÈÀÂÊÎÔÛÇ\-]{2,}(?:\s+|$)){1,5})",
        text, flags=re.IGNORECASE)
    if m:
        entity = " ".join(re.findall(r"[A-ZÉÈÀÂÊÎÔÛÇ\-]{2,}", m.group(1).strip()))
        add_admin("liquidateur", entity, m.group(0))

    # --- 5. Initiale + NOM
    m = re.search(
        r"liquidateur(?:\(s\))?\s*:?\s*\d*\.?\s*(?:me|maître|mr|mme|madame|m\.)?\s*(?P<nom>[A-Z](?:\.\-?[A-Z])?\.\s*[A-ZÉÈÀÂÊÎÔÛÇ\-]{2,})",
        text, flags=re.IGNORECASE | re.VERBOSE)
    if m:
        add_admin("liquidateur", m.group("nom"), m.group(0))

    # --- 6. "est désigné comme liquidateur"
    m = re.search(
        r"(?:Monsieur|Madame|Me|Maître|M\.|Mr|Mme)\s+"
        r"([A-Z][a-zéèêàîç\-']+(?:\s+[A-Z][a-zéèêàîç\-']+)*)\s+"
        r"([A-ZÉÈÀÂÊÎÔÛÇ][a-zA-Zéèêàîôûç\-']+)"
        r"\s*,\s*né.{0,200}?est\s+(?:considéré|désigné)\s+comme\s+liquidateur",
        text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        add_admin("liquidateur", f"{m.group(1)} {m.group(2)}", m.group(0))

    # --- 7. Article 2:79 (simplifié)
    if re.search(r"article\s*2\s*:?\s*79", text, flags=re.IGNORECASE):
        matches = re.findall(
            r"(?:Monsieur|Madame|M\.|Mme|Mr)\s+([A-Z][a-zéèêàîôûç\-']+(?:\s+[A-Z][a-zéèêàîôûç\-']+)*)\s+([A-ZÉÈÀÂÊÎÔÛÇ\-]{2,})",
            text, flags=re.IGNORECASE)
        for prenom, nom in matches:
            add_admin("liquidateur", f"{prenom} {nom}", f"{prenom} {nom}")

    # --- Fallback
    fb = fallback_nom(text)
    if fb:
        administrateurs.append(fb)

    return clean_admin_list(administrateurs)
