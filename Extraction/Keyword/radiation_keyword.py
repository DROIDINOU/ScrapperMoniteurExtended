import re

def detect_radiations_keywords(texte_brut: str, extra_keywords):
    if not texte_brut:
        return

    # 🚀 Tronquer si texte trop long
    if len(texte_brut) > 3000:
        texte_brut = texte_brut[:3000]
    # ------------------------------------------------------------------------------------------------------------------
    # --- PATTERN permettant de quitter directement
    # ------------------------------------------------------------------------------------------------------------------

    # On ne regarde que les 3–4 premières lignes pour éviter du bruit ailleurs
    head_text = texte_brut[:500]
    print(f"head!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!{head_text}")
    radiation_header_pattern = re.compile(
        r"liste\s+des\s+entit[ée]s?\s+enregistr[ée]es?.{0,100}?"
        r"(adresse\s+du\s+(si[èe]ge|siege|siège)|succursale).*radi[ée]e?",
        flags=re.IGNORECASE | re.DOTALL
    )

    if radiation_header_pattern.search(head_text):
        print("okkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk")
        extra_keywords.append("liste_radiations_adresse_siege")
        return

    # ------------------------------------------------------------------------------------------------------------------
    # --- DOUBLONS ---
    if re.search(
        r"pour\s+cause\s+de\s+dou+blons?.*a\s+été\s+an+ul+ée",
        texte_brut,
        flags=re.IGNORECASE | re.DOTALL
    ):
        extra_keywords.append("annulation_doublon")

    if re.search(
        r"liste\s+des\s+entit[ée]s\s+enregistr[ée]es.*?"
        r"remplacement\s+du\s+num[ée]ro\s+d['’]entreprise\s+pour\s+cause\s+de\s+dou+blons?.*a\s+été\s+an+ul+é",
        texte_brut,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        extra_keywords.append("annulation_remplacement_numero_doublon")

    # ------------------------------------------------------------------------------------------------------------------
    # --- REMPLACEMENT NUMÉRO BCE ---
    if re.search(
        r"remplac[ée]?\s+.*num(é|e)ro\s+d['’]entreprise",
        texte_brut,
        flags=re.IGNORECASE
    ):
        extra_keywords.append("remplacement_numero_bce")

    # ------------------------------------------------------------------------------------------------------------------
    # --- RADIATION : entités / adresses ---
    if re.search(
        r"la\s+radiation\s+d['’]?office\s+des\s+entit[ée]s?\s+suivantes\s+a\s+été\s+effectu[ée]e",
        texte_brut,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        extra_keywords.append("radiation_office_effectuee")

    if re.search(
        r"entit[ée]s?\s+enregistr[ée]es?.*adresse\s+du\s+si[èe]ge\s+a\s+été\s+radi[ée]e",
        texte_brut,
        flags=re.IGNORECASE | re.DOTALL
    ):
        extra_keywords.append("radiation_adresse_siege")

    # ------------------------------------------------------------------------------------------------------------------
    # --- RETRAIT / ANNULATION ---
    if re.search(
        r"liste\s+des\s+entit[ée]s\s+enregistr[ée]es.*?"
        r"(annulation|arr[êe]t)\s+de\s+la\s+radiation\s+d['’]office\s+de\s+l['’]adresse\s+du\s+si[eè]ge\b.*",
        texte_brut,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        extra_keywords.append("annulation_ou_arret_radiation_adresse_siege")

    if re.search(
        r"liste\s+des\s+entit[ée]s\s+enregistr[ée]es.*?"
        r"(annulation|arr[êe]t|retrait)\s+de\s+la\s+radiation\s+d['’]office\s+de\s+"
        r"l['’]adresse\s+de\s+la\ssuccursale\b.*",
        texte_brut,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        extra_keywords.append("annulation_ou_arret_radiation_succursale_siege")

    if re.search(
        r"(annulation|arr[êe]t|retrait)\s+de\s+la\s+radiation\s+"
        r"d['’]office.*non[- ]?respect.*formalit[ée]s?.*ubo",
        texte_brut,
        flags=re.IGNORECASE | re.DOTALL
    ):
        extra_keywords.append("retrait_radiation_ubo")

    if re.search(
        r"(annulation|arr[êe]t|retrait)\s+de\s+la\s+radiation\s+"
        r"d['’]?office\s+pour\s+non[-\s]?d[ée]p[oô]t\s+des\s+comptes\s+annuels",
        texte_brut,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        extra_keywords.append("retrait_radiation_non_depot_comptes")

    # ------------------------------------------------------------------------------------------------------------------
    # --- CORRECTIONS ---
    if re.search(
        r"liste\s+des\s+entit[ée]s\s+enregistr[ée]es.*?"
        r"correction\s+de\s+la\s+date\s+de\s+prise\s+d['’]?effet\s+de\s+la\s+radiation\s+"
        r"d['’]?office\s+de\s+l['’]?adresse\s+(du\s+si[eè]ge|de\s+la\s+succursale)\b",
        texte_brut,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        extra_keywords.append("correction_date_radiation_adresse_siege_ou_succursale")

    # ------------------------------------------------------------------------------------------------------------------
    # --- FALLBACK : ARTICLES 40 & 42 DU CODE DE DROIT ÉCONOMIQUE ---
    # S'exécute TOUJOURS, peu importe ce qui a été trouvé avant
    # ------------------------------------------------------------------------------------------------------------------
    if re.search(
        r"l['’]?\s*article\s*I{1,3}\s*[\.\-]?\s*40\b[\s,;:–-]*([^\.]{0,300})?\s*du\s+code\s+de\s+droit\s+[ée]conomique",
        texte_brut,
        flags=re.IGNORECASE
    ):
        if "article_iii_40" not in extra_keywords:
            extra_keywords.append("article_iii_40")

    if re.search(
        r"l['’]?\s*article\s*I{1,3}\s*[\.\-]?\s*42\b[\s,;:–-]*([^\.]{0,300})?\s*du\s+code\s+de\s+droit\s+[ée]conomique",
        texte_brut,
        flags=re.IGNORECASE
    ):
        if "article_iii_42" not in extra_keywords:
            extra_keywords.append("article_iii_42")