import re
import unicodedata


import unicodedata
import re

# Avant la boucle add_admin, on prépare la regex une fois
ADDR_SPLIT = re.compile(
        r"\b(?:RUE|AVENUE|CHAUSS[ÉE]E|VIA|BOULEVARD|PLACE|CHEMIN|QUAI|IMPASSE|SQUARE)\b",
        re.IGNORECASE
    )

def refine_admin_names(admins):
    """
    Re-nettoie les entités ('entity') à partir de leur 'raw' pour corriger
    les erreurs comme 'AITRE MICHELLE' ou 'regex-fallback MICHELLE',
    puis supprime les entrées incomplètes ou dupliquées.
    """
    refined = []
    for a in admins:
        raw = a.get("raw", "")
        entity = a.get("entity", "").strip()
        role = a.get("role", "").lower()

        # 1️⃣ On ne garde que ce qui vient après le dernier ':' ou tiret
        raw_part = re.split(r"[:\-]", raw)[-1]

        # 1️⃣bis Couper tout ce qui ressemble à une adresse
        raw_part = ADDR_SPLIT.split(raw_part, 1)[0]

        # 2️⃣ Supprime les mots techniques avant le vrai nom
        raw_part = re.sub(
            r"(?i)\b(regex-fallback|liquidateur(?:\(s\))?|curateur(?:\(s\))?|désigné(?:\(s\))?|ma[îi]tre|me|mr|mme|madame|monsieur)\b",
            " ",
            raw_part,
        )

        # 3️⃣ Capture du nom (tolère minuscules)
        m = re.search(
            r"([A-Za-zÉÈÀÂÊÎÔÛÇà-öø-ÿ'\-]+(?:\s+[A-Za-zÉÈÀÂÊÎÔÛÇà-öø-ÿ'\-]+){0,3})",
            raw_part.strip(),
        )
        if m:
            clean = m.group(1).strip()
            clean = " ".join(w.capitalize() for w in clean.split())

            # 🔥 Recoupe encore si jamais un bout d’adresse a glissé
            clean = ADDR_SPLIT.split(clean, 1)[0].strip()

            a["entity"] = clean

        a["entity"] = re.sub(r"\s{2,}", " ", a["entity"]).strip(" .-")
        refined.append(a)

    # 🧹 4️⃣ Filtrage : supprimer entités < 2 mots et dédoublonner (sans accents / casse)
    def canon(s):
        s = s.strip().lower()
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        s = re.sub(r"\s+", " ", s)
        return s

    seen = set()
    final = []
    for a in refined:
        ent = a.get("entity", "")
        # doit contenir au moins 2 mots
        if len(ent.split()) < 2:
            continue
        key = canon(ent)
        if key in seen:
            continue
        seen.add(key)
        final.append(a)

    return final

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
    """
    Nettoie et déduplique la liste d'administrateurs.
    - Supprime les entrées incomplètes ou bruitées.
    - Ignore les doublons (même nom avec accents/casse différents).
    - Conserve le rôle le plus spécifique si plusieurs existent.
    """

    # --- 1️⃣ Précompile les regex pour détection d'adresses/bruit ---
    addr_pat  = re.compile(r"\b(RUE|AVENUE|CHAUSS[ÉE]E|BOULEVARD|PLACE|CHEMIN|QUAI|IMPASSE|SQUARE)\b", re.IGNORECASE)
    bruit_pat = re.compile(r"\b(DROIT|PLEIN DROIT|JURIDICTION|TRIBUNAL|JUSTICE|INSTANCE)\b", re.IGNORECASE)
    stop_pat  = re.compile(r"\b(LE|LA|DE|DES|DU)\b|(?<!\w)(L'|D')", re.IGNORECASE)

    # --- 2️⃣ Nettoyage de base ---
    cleaned = []
    for a in admins:
        if not isinstance(a, dict):
            continue

        entity = (a.get("entity") or "").strip()
        if len(entity) < 3:
            continue
        if len(entity.split()) == 1:
            continue

        U = entity.upper()
        if addr_pat.search(U) or bruit_pat.search(U) or stop_pat.search(U):
            continue

        cleaned.append(a)

    # --- 3️⃣ Canonicalisation pour déduplication ---
    def canon(s):
        """Retourne une version canonique (sans accents, minuscule, espaces normalisés)."""
        s = s.strip().lower()
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        s = re.sub(r"\s+", " ", s)
        return s

    # --- 4️⃣ Déduplication avec priorité de rôle ---
    role_priority = {"liquidateur": 3, "curateur": 2, "inconnu": 1}

    merged = {}
    for adm in cleaned:
        key = canon(adm["entity"])
        current = merged.get(key)
        if not current or role_priority.get(adm["role"], 0) > role_priority.get(current["role"], 0):
            merged[key] = adm

    # --- 5️⃣ Retour final ---
    return list(merged.values())

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
            # ✅ Supprime l’adresse correctement (insensible à la casse)
            entity = ADDR_SPLIT.split(entity, 1)[0].strip()

            # 🧽 Nettoyage final
            entity = re.sub(r"\s{2,}", " ", entity)
            entity = entity.strip(" .-")

            administrateurs.append({
                "role": role.lower(),
                "entity": entity,
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
    # --- 6bis. Liquidateur ou curateur : NOM PRENOM avant une adresse
    m = re.search(
        r"(?:liquidateur(?:\(s\))?|curateur(?:\(s\))?)\s*(?:désigné\(s\))?\s*:?\s*"
        r"\b([A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zéèêàîôûç'\-]+\s+[A-ZÉÈÀÂÊÎÔÛÇ][A-Za-zéèêàîôûç'\-]+)"
        r"(?=[^A-ZÉÈÀÂÊÎÔÛÇ]{0,100}\b(?:RUE|AVENUE|CHAUSS[ÉE]E|VIA|BOULEVARD|PLACE|CHEMIN|QUAI|IMPASSE|SQUARE)\b)",
        text,
        flags=re.IGNORECASE
    )

    # 🔁 Si le premier échoue, on tente la version plus permissive (pour VIA FREGONA, etc.)
    if not m:
        m = re.search(
            r"(?:liquidateur(?:\(s\))?|curateur(?:\(s\))?)\s*(?:désigné\(s\))?\s*:?\s*"
            # le nom
            r"([A-ZÉÈÀÂÊÎÔÛÇ][A-ZÉÈÀÂÊÎÔÛÇa-zéèêàîôûç'\-]+\s+[A-ZÉÈÀÂÊÎÔÛÇ][A-ZÉÈÀÂÊÎÔÛÇa-zéèêàîôûç'\-]+)"
            # ✅ lookahead limité à 100 caractères max
            r"(?=\s{0,5}.{0,100}?\b(?:RUE|AVENUE|CHAUSS[ÉE]E|VIA|BOULEVARD|PLACE|CHEMIN|QUAI|IMPASSE|SQUARE)\b)",
            text,
            flags=re.IGNORECASE
        )

    if m:
        print(f"reussi : !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!{m}")
        add_admin(
            "liquidateur" if "liquidateur" in m.group(0).lower() else "curateur",
            m.group(1),
            m.group(0)
        )

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

    admins = refine_admin_names(administrateurs)
    return clean_admin_list(admins)