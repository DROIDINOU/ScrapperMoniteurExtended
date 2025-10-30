import re
import traceback

def detect_radiations_keywords(texte_brut: str, extra_keywords):
    try:
        # 🔹 Nettoyage basique des caractères nuls ou invisibles
        if not texte_brut:
            return extra_keywords
        texte_brut = texte_brut.replace('\x00', '').strip()

        # 🚀 Tronquer si texte trop long (moins de 1500 caractères pour éviter backtracking)
        if len(texte_brut) > 1500:
            texte_brut = texte_brut[:1500]

        # On ne regarde que les 500 premiers caractères pour les headers
        head_text = texte_brut[:450]

        # --------------------------------------------------------------------------------------------------------------
        # --- PATTERNS critiques : détection directe (on quitte si trouvé)
        # --------------------------------------------------------------------------------------------------------------
        # ***** RETRAITS
        retrait_non_depot_pattern = re.compile(
            r"liste\s+des\s+entit[ée]s?\s+enregistr[ée]es?.{0,200}?"
            r"retrait\s+de\s+la\s+radiation\s+d['’]?\s*office.{0,200}?"
            r"pour\s+(le\s+)?non[-\s]?d[ée]p[oô]t.{0,80}?comptes\s+annuels",
            flags=re.IGNORECASE | re.DOTALL
        )
        if retrait_non_depot_pattern.search(texte_brut):
            extra_keywords.append("retrait_radiation_non_depot_comptes")
            return extra_keywords

        arret_radiation_pattern = re.compile(
            r"liste\s+des\s+entit[ée]s?\s+enregistr[ée]es?.{0,120}?"
            r"(arr[êe]t|arret|annulation|retrait)\s+de\s+la\s+radiation\s+d['’]?\s*office\s+"
            r"(de|de\s+l['’]?)?\s*(adresse|si[èe]ge|succursale)",
            flags=re.IGNORECASE
        )
        if arret_radiation_pattern.search(head_text):
            extra_keywords.append("arret_ou_annulation_radiation_adresse_siege")
            return extra_keywords

        pattern_annulation_radiation_ubo = re.compile(
            r"liste\s+des\s+entit[ée]s?\s+enregistr[ée]es?.{0,500}?"
            r"(?:à\s+l['’]\s*|au\s+)?"
            r"(annulation|arr[êe]t|retrait)\s+(?:de\s+la\s+)?radiation.{0,300}?"
            r"(?:d['’]?\s*)?office.{0,200}?"
            r"(ubo|formalit[ée]s?\s+ubo)",
            flags=re.IGNORECASE | re.DOTALL
        )
        if pattern_annulation_radiation_ubo.search(texte_brut):
            extra_keywords.append("annulation_ou_retrait_radiation_ubo")
            return extra_keywords

        retrait_radiation_pattern = re.compile(
            r"liste\s+des\s+entit[ée]s?\s+enregistr[ée]es?.{0,300}?"
            r"(?:au\s+)?(annulation|arr[êe]t|retrait)\s+(?:de\s+la\s+)?radiation.{0,200}?"
            r"(?:d['’]?\s*)?office",
            flags=re.IGNORECASE
        )
        if retrait_radiation_pattern.search(texte_brut):
            extra_keywords.append("retrait_ou_annulation_radiation_office")
            return extra_keywords

        radiation_header_pattern = re.compile(
            r"liste\s+des\s+entit[ée]s?\s+enregistr[ée]es?.{0,100}?"
            r"(adresse\s+du\s+(si[èe]ge|siege|siège)|succursale).{0,80}?radi[ée]e?",
            flags=re.IGNORECASE
        )
        if radiation_header_pattern.search(head_text):
            extra_keywords.append("liste_radiations_adresse_siege")
            return extra_keywords

        ubo_radiation_pattern = re.compile(
            r"liste\s+des\s+entit[ée]s?\s+enregistr[ée]es?.{0,150}?"
            r"((ayant\s+fait\s+l['’]?objet|faisant\s+l['’]?objet)"
            r"|pour\s+lesquelles\s+il\s+a\s+été\s+proc[ée]d[ée])"
            r".{0,120}?radiation\s+d['’]?office.{0,100}?"
            r"(ubo|formalit[ée]s?\s+ubo)",
            flags=re.IGNORECASE | re.DOTALL
        )
        if ubo_radiation_pattern.search(head_text):
            extra_keywords.append("radiation_office_ubo")
            return extra_keywords

        # --------------------------------------------------------------------------------------------------------------
        # --- PATTERNS en série (moins critiques)
        # --------------------------------------------------------------------------------------------------------------
        if re.search(
            r"pour\s+cause\s+de\s+dou+blons?.{0,100}?a\s+été\s+an+ul+ée",
            texte_brut, flags=re.IGNORECASE
        ):
            extra_keywords.append("annulation_doublon")

        if re.search(
            r"liste\s+des\s+entit[ée]s\s+enregistr[ée]es.{0,100}?"
            r"remplacement\s+du\s+num[ée]ro\s+d['’]entreprise.{0,80}?"
            r"pour\s+cause\s+de\s+dou+blons?.{0,80}?a\s+été\s+an+ul+é",
            texte_brut, flags=re.IGNORECASE
        ):
            extra_keywords.append("annulation_remplacement_numero_doublon")

        if re.search(
            r"remplac[ée]?\s+.{0,60}?num(é|e)ro\s+d['’]entreprise",
            texte_brut, flags=re.IGNORECASE
        ):
            extra_keywords.append("remplacement_numero_bce")

        if re.search(
            r"la\s+radiation\s+d['’]?office\s+des\s+entit[ée]s?\s+suivantes.{0,80}?a\s+été\s+effectu[ée]e",
            texte_brut, flags=re.IGNORECASE
        ):
            extra_keywords.append("radiation_office_effectuee")

        if re.search(
            r"entit[ée]s?\s+enregistr[ée]es?.{0,100}?adresse\s+du\s+si[èe]ge.{0,60}?a\s+été\s+radi[ée]e",
            texte_brut, flags=re.IGNORECASE
        ):
            extra_keywords.append("radiation_adresse_siege")

        if re.search(
            r"liste\s+des\s+entit[ée]s\s+enregistr[ée]es.{0,120}?"
            r"(annulation|arr[êe]t)\s+de\s+la\s+radiation\s+d['’]office.{0,60}?l['’]adresse\s+du\s+si[eè]ge",
            texte_brut, flags=re.IGNORECASE
        ):
            extra_keywords.append("annulation_ou_arret_radiation_adresse_siege")

        if re.search(
            r"liste\s+des\s+entit[ée]s\s+enregistr[ée]es.{0,120}?"
            r"(annulation|arr[êe]t|retrait)\s+de\s+la\s+radiation\s+d['’]office.{0,60}?"
            r"l['’]adresse\s+de\s+la\s+succursale",
            texte_brut, flags=re.IGNORECASE
        ):
            extra_keywords.append("annulation_ou_arret_radiation_succursale_siege")

        if re.search(
            r"(annulation|arr[êe]t|retrait)\s+de\s+la\s+radiation.{0,80}?office.{0,80}?non[- ]?respect.{0,80}?"
            r"formalit[ée]s?.{0,80}?ubo",
            texte_brut, flags=re.IGNORECASE
        ):
            extra_keywords.append("retrait_radiation_ubo")

        if re.search(
            r"(annulation|arr[êe]t|retrait)\s+de\s+la\s+radiation.{0,80}?office.{0,80}?pour.{0,40}?non[-\s]?"
            r"d[ée]p[oô]t.{0,80}?comptes\s+annuels",
            texte_brut, flags=re.IGNORECASE
        ):
            extra_keywords.append("retrait_radiation_non_depot_comptes")

        if re.search(
            r"liste\s+des\s+entit[ée]s\s+enregistr[ée]es.{0,120}?"
            r"correction\s+de\s+la\s+date.{0,80}?prise\s+d['’]?effet.{0,80}?r?adiation.{0,80}?office.{0,80}?"
            r"adresse\s+(du\s+si[eè]ge|de\s+la\s+succursale)",
            texte_brut, flags=re.IGNORECASE
        ):
            extra_keywords.append("correction_date_radiation_adresse_siege_ou_succursale")

    except Exception as e:
        print("[ERREUR detect_radiations_keywords] →", e)
        traceback.print_exc()

    # ✅ Toujours retourner explicitement la liste (évite les blocages en fin de scraping)
    return extra_keywords
