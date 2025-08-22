from bs4 import BeautifulSoup
import re


def extract_address(texte_html):
    soup = BeautifulSoup(texte_html, 'html.parser')
    texte = soup.get_text(separator=' ')
    texte = re.sub(r'\s+', ' ', texte).strip()
    adresse_list = []

    # Préfixes de voie
    ADRESSE_PREFIXES_FILTRE = (
        r"(?:rue|r\.|avenue|cours|cour|av\.|chee|chauss[ée]e|route|rte|place|pl\.?|"
        r"boulevard|bd|chemin|ch\.?|galerie|impasse|square|all[ée]e|clos|voie|ry|passage|"
        r"quai|parc|z\.i\.?|zone|site|promenade|faubourg|fbg|quartier|cite|hameau|"
        r"lotissement|residence)"
    )

    # Types de voies français + néerlandais
    VOIE_ALL = (
        rf"(?:{ADRESSE_PREFIXES_FILTRE}"
        r"|rue|route|grand[-\s]?route|grand[-\s]?place|avenue|chaussée|place|boulevard|impasse|"
        r"chemin|quai|straat|laan|steenweg|plein|weg|pad)"
    )
    NUM_TOKEN = r"\d{1,4}(?:[A-Za-z])?(?:/[A-ZÀ-ÿ0-9\-]+)?"
    MOT_NOM_VOIE = r"(?:[A-ZÀ-ÿa-z0-9'’()/\.-]+|de|du|des|la|le|l’|l'|d’|d')"
    MOTS_NOM_VOIE = rf"{MOT_NOM_VOIE}(?:\s+{MOT_NOM_VOIE}){{0,9}}"

    PROX = r"[^\.]{0,80}?"

    # Motifs "core" réutilisables (tes définitions)
    core_1 = rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{MOTS_NOM_VOIE}\s*{VOIE_ALL}\s*\d{{1,4}})"
    core_2 = rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{MOTS_NOM_VOIE}{VOIE_ALL}\s*\d{{1,4}})"
    core_3 = rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE})"
    core_4 = rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE})"
    core_5_any_before = (
        rf"(?:{MOTS_NOM_VOIE},\s*)?"
        rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+\d{{1,4}}(?:[A-Za-z])?"
        rf"(?:\s*(?:/|bte|bus|boite|boîte|b|bt)\s*[\w\-/.]+)?)"
    )
    # 👉 NOUVEAU : accepte “CP Ville, Hasoumont 71, boîte 16” sans mot-clé voie
    core_5b_no_voie = (
        rf"(?:{MOTS_NOM_VOIE},\s*)?"
        rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{MOTS_NOM_VOIE}\s+\d{{1,4}}(?:[A-Za-z])?"
        rf"(?:\s*(?:/|bte|bus|boite|boîte|b|bt)\s*[\w\-/.]+)?)"
    )
    core_6_nl = rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*(?:straat|laan|steenweg|plein|weg|pad)\s+{MOTS_NOM_VOIE})"
    core_7_fr = rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE})"
    core_8_rue_simple = (
        rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s+rue\s+{MOTS_NOM_VOIE}(?:\s+\d+)?)"
        r"(?=[\.,])"
    )
    core_9_autres_voies = (
        rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s+(?:avenue|chaussée|place)\s+{MOTS_NOM_VOIE}(?:\s+\d+)?)"
        r"(?=[\.,])"
    )
    core_10_fran_large = (
        rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s+{VOIE_ALL}\s+{MOTS_NOM_VOIE}(?:\s+\d+)?)"
        r"(?=[\.,])"
    )
    core_11_any_before_generic = (
        rf"(?:{MOTS_NOM_VOIE},\s*)?"
        rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{VOIE_ALL}\s*{MOTS_NOM_VOIE})"
    )
    core_12_wild = r"(.+?)(?=, [A-Z]{2}|, décédé|$)"
    # ex : "… est établi avenue Besme 107, 1190 Bruxelles"
    core_13_est_etabli = (
        rf"est\s+établi\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"  # avenue Besme 107
        rf"\s*,\s*\d{{4}}\s+{MOTS_NOM_VOIE}"  # , 1190 Bruxelles
        r")"
    )
    core_14_wild_end = r"(.{1,300}?)(?=\.|\bdécéd[ée]|$)"
    core_15_siege_social = (
        rf"(?:ayant\s+son\s+)?si[eè]ge\s+social\s*,\s*("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}\s*,\s*\d{{4}}\s+{MOTS_NOM_VOIE}"
        r")"
    )
    # ex: "… est établi, allée du Vieux Chêne 23, à 4480 Engis"
    core_14_est_etabli_cp_apres = (
        rf"est\s+établi[e]?\s*,?\s*("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"  # allée du Vieux Chêne 23
        rf"\s*,?\s*à\s*\d{{4}}\s+{MOTS_NOM_VOIE}"  # , à 4480 Engis
        r")"
    )
    # === TES PATTERNS (identiques) — deux lignes orphelines supprimées ===
    patterns_base = [
        r"domicili[ée](?:\(e\))?\s+à\s+" + core_1,
        r"domicili[ée]?\s+à\s+" + core_2,
        r"domicili[ée]?\s+à\s+" + core_3,
        r"domicili[ée]?\s+à\s+" + core_4,
        core_5_any_before,
        core_5b_no_voie,
        core_13_est_etabli,
        core_15_siege_social,
        core_14_est_etabli_cp_apres,

        r"domicili[ée]" + PROX + r"\bà\s+" + core_6_nl,
        r"domicili[ée]" + PROX + r"\bà\s+" + core_7_fr,
        r"domicili[ée]" + PROX + r"\bà\s+" + core_8_rue_simple,
        r"domicili[ée]" + PROX + r"\bà\s+" + core_9_autres_voies,
        r"domicili[ée]" + PROX + core_11_any_before_generic,

        r"domicili[ée](?:\(e\))?\s+à\s+" + core_12_wild,
        r"domiciliée\s+à\s+(.+?),?\s+est\s+décédée",
        r"domicili[ée](?:\(e\))?\s+à\s+" + core_14_wild_end,
        # ex: Domicile : rue de Jambes 319, à 5100 DAVE.
        rf"domicile\s*:\s*({VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}\s*,\s*à\s+\d{{4}}\s+{MOTS_NOM_VOIE})",

        # ex: Domicile : 5100 DAVE, rue de Jambes 319
        rf"domicile\s*:\s*(\d{{4}}\s+{MOTS_NOM_VOIE}\s*,\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN})",
        # Ex: "Domicile : Grand-Route(VER) 245/0011, à 4537 Verlaine"
        rf"domicile\s*:\s*("
        rf"{VOIE_ALL}(?:\s+|(?=\())"  # espace OU parenthèse après le type de voie
        rf"{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"  # nom de la voie + numéro (gère 245/0011, 12B, etc.)
        r"\s*(?:,\s*)?à\s*\d{4}\s+" + MOTS_NOM_VOIE +  # ", à 4537 Verlaine" (virgule optionnelle)
        r")",
        # ex: Domicile : rue de Jambes 319 - 5100 DAVE   (séparateur , ou tiret)
        rf"domicile\s*:\s*({VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}\s*(?:,|[-–])\s*\d{{4}}\s+{MOTS_NOM_VOIE})",

        # ex: Domicile : 5100 DAVE - rue de Jambes 319   (ordre inverse avec tiret)
        rf"domicile\s*:\s*(\d{{4}}\s+{MOTS_NOM_VOIE}\s*(?:,|[-–])\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN})",
        # Variantes "de son vivant"
        rf"domicili[ée](?:\(e\))?\s+de\s+son\s+vivant\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+\d{{1,4}}(?:[A-Za-z])?"
        r"(?:\s*(?:/|bte|bus|boite|boîte|b|bt)\s*[\w\-/.]+)?)"
        r"\s*,\s*à\s*\d{4}\s+" + MOTS_NOM_VOIE,

        rf"domicili[ée](?:\(e\))?\s+de\s+son\s+vivant\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+\d{{1,4}}(?:[A-Za-z])?"
        r"(?:\s*(?:/|bte|bus|boite|boîte|b|bt)\s*[\w\-/.]+)?)"
        r"\s*(?:,\s*)?à\s*\d{4}\s+" + MOTS_NOM_VOIE + r"(?=(?:\s*(?:,| et\b)|$))",

        # “de son vivant domiciliée …, à CP VILLE”
        rf"de\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+\d{{1,4}}(?:[A-Za-z])?"
        r"(?:\s*(?:/|bte|bus|boite|boîte|b|bt)\s*[\w\-/.]+)?"
        r")\s*,?\s*à\s*\d{4}\s+" + MOTS_NOM_VOIE,

        # “de son vivant domiciliée AVENUE … NUM” (sans "à CP Ville" immédiat)
        rf"de\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+\d{{1,4}}(?:[A-Za-z])?)",

        # Cas inversé : "domiciliée de son vivant à VILLE, rue XXX 12"
        rf"domicili[ée](?:\(e\))?\s+de\s+son\s+vivant\s+à\s+{MOTS_NOM_VOIE},?\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+\d{{1,4}}(?:[A-Za-z])?)",

        # Virgule après "vivant"
        rf"domicili[ée](?:\(e\))?\s+de\s+son\s+vivant\s*,\s*("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+\d{{1,4}}(?:[A-Za-z])?)"
        r"\s*,?\s*à\s*\d{4}\s+" + MOTS_NOM_VOIE,

        # Variantes "en son vivant"
        rf"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+\d{{1,4}}(?:[A-Za-z])?"
        r"(?:\s*(?:/|bte|bus|boite|boîte|b|bt)\s*[\w\-/.]+)?)"
        r"\s*(?:,\s*)?à\s*\d{4}\s+" + MOTS_NOM_VOIE,

        rf"(?:en|de)\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+\d{{1,4}}(?:[A-Za-z])?"
        r"(?:\s*(?:/|bte|bus|boite|boîte|b|bt)\s*[\w\-/.]+)?)"
        r"\s*,\s*\d{4}\s+" + MOTS_NOM_VOIE,

        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_1,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_2,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_3,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_4,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_6_nl,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_7_fr,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_10_fran_large,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_11_any_before_generic,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_12_wild,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_14_wild_end,

        r"en\s+son\s+vivant\s+à\s+" + core_6_nl,
        r"en\s+son\s+vivant\s+à\s+" + core_7_fr,
        r"en\s+son\s+vivant\s+à\s+" + core_8_rue_simple,
        r"en\s+son\s+vivant\s+à\s+" + core_9_autres_voies,
        r"en\s+son\s+vivant\s+à\s+" + core_10_fran_large,
        r"en\s+son\s+vivant\s+à\s+" + core_11_any_before_generic,

        rf"(?:en|de)\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+\d{{1,4}}(?:[A-Za-z])?"
        r"(?:\s*(?:/|bte|bus|boite|boîte|b|bt)\s*[\w\-/.]+)?)"
        r"\s*(?:,\s*)?à\s*\d{4}\s+" + MOTS_NOM_VOIE,

        rf"(?:en|de)\s+son\s+vivant\s+({VOIE_ALL}\s+{MOTS_NOM_VOIE})"
        r"\s*(?:,\s*)?à\s*\d{4}\s+" + MOTS_NOM_VOIE,
    ]

    # ─────────────────────────────────────────────────────────────
    # Génération AUTOMATIQUE de variantes pour TOUS tes patterns
    #   - ajout (avant) "((en|de) son vivant, )?"
    #   - ajout (après 'domicilié(e)') " (en|de) son vivant, ?"
    #   - "à" rendu optionnel: \s+à\s+  ->  \s*(?:à\s+)?
    # On part STRICTEMENT de tes patterns_base.
    # ─────────────────────────────────────────────────────────────
    def with_optional_a(p: str) -> str:
        return re.sub(r"\\s\+à\\s\+", r"\\s*(?:à\\s+)?", p)

    def vivant_before_domicilie(p: str) -> str:
        # insère "(en|de) son vivant, ?" juste avant la 1ère occurrence de "domicilié(e)"
        return re.sub(
            r"(?i)(?=\bdomicili\[ée\]\(\?:\\\(e\\\)\)\?\b|\bdomicili\[ée\]\b)",
            r"(?:en|de)\\s+son\\s+vivant\\s*,?\\s*",
            p,
            count=1
        )

    def vivant_after_domicilie(p: str) -> str:
        # ajoute "(en|de) son vivant, ?" juste APRÈS "domicilié(e)" + espaces
        return re.sub(
            r"(?i)(domicili\[ée\](?:\\\(e\\\))?\\s+)",
            r"\\1(?:en|de)\\s+son\\s+vivant\\s*,?\\s+",
            p,
            count=1
        )

    patterns_expanded = set()
    for p in patterns_base:
        patterns_expanded.add(p)
        p_opt_a = with_optional_a(p)
        patterns_expanded.add(p_opt_a)

        if "domicili" in p.lower():
            patterns_expanded.add(vivant_before_domicilie(p))
            patterns_expanded.add(vivant_after_domicilie(p))

            patterns_expanded.add(vivant_before_domicilie(p_opt_a))
            patterns_expanded.add(vivant_after_domicilie(p_opt_a))

    patterns = list(patterns_expanded)

    # Optimisation : on segmente le texte en phrases ciblées
    phrases = re.split(r'(?<=[\.\n])', texte)
    phrases = [p.strip() for p in phrases if any(kw in p.lower() for kw in ['domicili', 'domicile', 'vivant', ' à ', 'etabli', 'établi', 'etablie', 'établie', "établi,", "siège social", "siege social" ])]

    for phrase in phrases:
        for pattern in patterns:
            try:
                matches = re.findall(pattern, phrase, flags=re.IGNORECASE)
            except re.error:
                # si une variante générée est invalide (rare), on la saute
                continue
            for m in matches:
                # Chaque match peut être un str (un seul groupe) ou un tuple (plusieurs)
                if isinstance(m, tuple):
                    m = next((x for x in m if isinstance(x, str) and x.strip()), " ".join(m))
                m = re.sub(r"\s+(et(\s+décédé[e]?)?)$", "", str(m).strip(), flags=re.IGNORECASE)
                adresse_list.append(m)

    return list(set(adresse_list))
