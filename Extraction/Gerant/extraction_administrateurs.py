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


# -----------------------------------------------------------------
#                       NETTOYAGE CHAMP ADMINISTRATEUR
# -----------------------------------------------------------------
def clean_admin_list(admins):
    stopwords = {
        "LE", "LA", "DE", "DES", "DU", "S-", "C-", "L'", "D'",
        "AITRE", "T-", "E-", "M-", "T- S- E-", "T-S-M", "E- T- E-"
    }
    adresse_keywords = {
        "RUE", "AVENUE", "CHAUSSÉE", "CHAUSSEE", "BOULEVARD",
        "PLACE", "CHEMIN", "QUAI", "IMPASSE", "SQUARE"
    }

    bruit_keywords = {"DROIT", "plein droit", "juridiction", "tribunal", "justice", "instance"}


    cleaned = []
    for a in admins:
        if not a:
            continue
        val = a.strip()
        upper_val = val.upper()

        # Stopword exact
        if upper_val in stopwords:
            continue
        # Trop court
        if len(val) < 3:
            continue

        # ⚡ rejeter si c'est un seul mot
        if len(val.split()) == 1:
            continue

        # Contient un mot d'adresse (début OU intérieur)
        if any(k in upper_val.split() for k in adresse_keywords):
            continue

        if any(k in upper_val.split() for k in bruit_keywords):
            continue


        cleaned.append(val)

    # Supprimer doublons exacts en conservant l'ordre
    cleaned_unique = list(dict.fromkeys(cleaned))

    # Supprimer les entrées qui sont strictement contenues dans une autre
    final_list = []
    for val in cleaned_unique:
        if not any(
            val != other and val.lower() in other.lower()
            for other in cleaned_unique
        ):
            final_list.append(val)

    return final_list


def extract_administrateur(text):
    """
    Extrait le ou les noms du curateur ou liquidateur (personnes physiques ou sociétés),
    y compris les cas avec plusieurs liquidateurs listés.
    Retourne toujours une liste de noms.
    """

    administrateurs = []

    # --- A. "a déchargé Me X Y de sa mission de curateur/curatrice"
    pattern_decharge = (
        r"(?:a\s+)?d[ée]charg[ée]?\s+"  
        r"(?:Me|Ma(?:ître)?|M(?:\.|onsieur)?|Mme|Madame)?\s*"
        r"([A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÀ-ÖØ-öø-ÿ\-']+(?:\s+[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÀ-ÖØ-öø-ÿ\-']+){0,4})"
        r"\s+de\s+sa\s+mission\s+de\s+curateur(?:rice)?\b"
    )
    m_decharge = re.search(pattern_decharge, text, flags=re.IGNORECASE)
    if m_decharge:
        administrateurs.append(m_decharge.group(1).strip())

    # --- B. "X Y, curateur/curatrice"
    pattern_suffix = (
        r"(?:Me|Ma(?:ître)?|M(?:\.|onsieur)?|Mme|Madame|Mr)?\s*"
        r"([A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÀ-ÖØ-öø-ÿ\-']+(?:\s+[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÀ-ÖØ-öø-ÿ\-']+){0,4})"
        r"\s*,\s*curateur(?:rice)?\b"
    )
    for nom in re.findall(pattern_suffix, text, flags=re.IGNORECASE):
        administrateurs.append(nom.strip())

    # --- 0. Multi-liquidateurs (liste numérotée avec tiret avant adresse)
    pattern_multi = (
        r"(?:liquidateur(?:s)?(?:\s+désigné\(s\))?\s*:?\s*)"
        r"((?:\d+\.\s*(?:monsieur|madame|me|ma[iî]tre)?\s*[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÉÈÀÂÊÎÔÛÇ\-\s']+?\s*-\s*)+)"
    )
    match_multi = re.search(pattern_multi, text, flags=re.IGNORECASE)
    if match_multi:
        bloc = match_multi.group(1)
        noms_trouves = re.findall(
            r"(?:monsieur|madame|me|ma[iî]tre)?\s*([A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÉÈÀÂÊÎÔÛÇ\-\s']+?)\s*(?=-)",
            bloc,
            flags=re.IGNORECASE
        )
        administrateurs.extend([n.strip() for n in noms_trouves if n.strip()])

    # --- 1. Société (SRL, SA...) avant l'adresse → priorité
    pattern_societe = (
        r"(?:liquidateur|curateur)(?:\(s\))?\s*(?:désigné\(s\))?\s*:?\s*"
        r"((?:[A-ZÉÈÀÂÊÎÔÛÇ]{2,5}\s+)?[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zÉÈÀÂÊÎÔÛÇ\-\&\.\s']+?)"
        r"(?=\s+(RUE|AVENUE|CHAUSS[ÉE]E|BOULEVARD|PLACE|CHEMIN|QUAI|IMPASSE|SQUARE)\b)"
    )
    match_societe = re.search(pattern_societe, text, flags=re.IGNORECASE)
    if match_societe:
        administrateurs.append(match_societe.group(1).strip())

    # --- 2. Curateur avec 2 à 4 blocs en majuscules
    pattern1 = r"curateur\s*:?\s*([A-ZÉÈÀÂÊÎÔÛÇ]+(?:\s+[A-ZÉÈÀÂÊÎÔÛÇ]+){1,4})"
    match = re.search(pattern1, text, flags=re.IGNORECASE)
    if match:
        administrateurs.append(match.group(1).strip())

    # --- 3. Liquidateur avec Prénom + NOM
    pattern2 = (
        r"liquidateur(?:\(s\))?\s*(?:désigné\(s\))?\s*:?\s*"
        r"(\d+\.\s*)?"
        r"(?:Me|Maître|M(?:onsieur)?|Mme|Madame|Mr|M\.)?\.?\s*"
        r"([A-Z][a-zéèêàîç\-']+(?:\s+[A-Z][a-zéèêàîç\-']+){0,2})\s+"
        r"([A-ZÉÈÀÂÊÎÔÛÇ\-]{2,}(?:\s+[A-ZÉÈÀÂÊÎÔÛÇ\-]{2,}){0,1})"
    )
    match2 = re.search(pattern2, text, flags=re.IGNORECASE)
    if match2:
        administrateurs.append(f"{match2.group(2)} {match2.group(3)}")

    # --- 4. Liquidateur avec 1 à 5 blocs majuscules
    pattern3 = (
        r"liquidateur(?:\(s\))?\s*(?:désigné\(s\))?\s*:?\s*"
        r"(?:Me|M(?:onsieur)?|Mme|Madame|Mr|M\.|Maître)?\.?\s*"
        r"((?:[A-ZÉÈÀÂÊÎÔÛÇ\-]{2,}(?:\s+|$)){1,5})"
    )
    match3 = re.search(pattern3, text, flags=re.IGNORECASE)
    if match3:
        mots = re.findall(r"[A-ZÉÈÀÂÊÎÔÛÇ\-]{2,}", match3.group(1).strip())
        if 1 <= len(mots) <= 5:
            administrateurs.append(" ".join(mots))

    # --- 5. Format initiale + NOM
    pattern4 = r"""
        liquidateur(?:\(s\))?
        \s*:?\s*
        \d*\.?\s*
        (?:me|maître|mr|mme|madame|m\.)?\s*
        (?P<nom>[A-Z](?:\.\-?[A-Z])?\.\s*[A-ZÉÈÀÂÊÎÔÛÇ\-]{2,})
    """
    match4 = re.search(pattern4, text, flags=re.IGNORECASE | re.VERBOSE)
    if match4:
        administrateurs.append(match4.group("nom").strip())

    # --- 6. Cas "est considéré/désigné comme liquidateur (de plein droit)"
    pattern5_6 = (
            r"(?:Monsieur|Madame|Me|Maître|M\.|Mr|Mme)\s+"  # civilité obligatoire
            r"([A-Z][a-zéèêàîç\-']+(?:\s+[A-Z][a-zéèêàîç\-']+)*)"  # prénom(s)
            r"\s+([A-ZÉÈÀÂÊÎÔÛÇ][a-zA-Zéèêàîôûç\-']+)"  # nom (MAJ ou minuscule)
            r"\s*,\s*né"  # suivi de ", né"
            r".{0,200}?est\s+(?:considéré|désigné)\s+comme\s+liquidateur"  # jusqu'à "est ... liquidateur"
            r"(?:\s+de\s+plein\s+droit)?"  # optionnel "de plein droit"
        )

    match5_6 = re.search(pattern5_6, text, flags=re.IGNORECASE | re.DOTALL)
    if match5_6:
            administrateurs.append(f"{match5_6.group(1)} {match5_6.group(2)}")

    # --- 7. Cas "article 2:79" avec Monsieur/Madame ... , né le ...
    # On ne déclenche QUE si "article 2:79" est dans le texte
    if re.search(r"article\s*2\s*:?\s*79", text, flags=re.IGNORECASE):
        pattern_279 = (
            r"(?:Monsieur|Messieurs|Madame|M\.|Mme|Mr)\s+"   # civilité obligatoire
            r"([A-Z][a-zéèêàîôûç\-']+(?:\s+[A-Z][a-zéèêàîôûç\-']+)*)"  # prénom(s)
            r"\s+([A-ZÉÈÀÂÊÎÔÛÇ\-]{2,})"                     # NOM en majuscules
            r"\s*,?\s*né\s+le\s+\d{1,2}\s+\w+\s+\d{4}"       # date de naissance obligatoire
        )
        matches_279 = re.findall(pattern_279, text, flags=re.IGNORECASE)
        for prenom, nom in matches_279:
            administrateurs.append(f"{prenom} {nom}")
    # --- 7bis. Cas "article 2:79" avec plusieurs personnes (séparées par "et")
    if re.search(r"article\s*2\s*:?\s*79", text, flags=re.IGNORECASE):
        bloc_pattern = (
            r"(Messieurs?|Mesdames?|Monsieur|Madame|M\.|Mme|Mr)\s+"
            r"(.+?)"  # capture tout ce bloc de noms + "né le ...", jusqu'à "sont considérés"
            r"\s+sont\s+considérés?\s+comme\s+liquidateurs?"
        )
        bloc_match = re.search(bloc_pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if bloc_match:
            bloc_noms = bloc_match.group(2)

            # Découpe en segments "X NOM, né le JJ mois AAAA"
            personne_pattern = (
                r"(?:Monsieur|Madame|M\.|Mme|Mr|Messieurs?)?\s*"
                r"([A-Z][a-zéèêàîôûç\-']+(?:\s+[A-Z][a-zéèêàîôûç\-']+)*)"  # prénom(s)
                r"\s+([A-ZÉÈÀÂÊÎÔÛÇ\-]{2,})"  # NOM
                r"(?=\s*,?\s*né\s+le\s+\d{1,2}\s+\w+\s+\d{4})"  # lookahead: s’arrête avant "né le"
            )

            matches = re.findall(personne_pattern, bloc_noms, flags=re.IGNORECASE)
            for prenom, nom in matches:
                administrateurs.append(f"{prenom} {nom}")

    # --- Fallback
    fallback = fallback_nom(text)
    if fallback:
        administrateurs.append(fallback)

    # ✅ Nettoyage et retour
    return clean_admin_list(administrateurs)
