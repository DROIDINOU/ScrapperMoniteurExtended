import re


# attention on sera tranquille que quand tous les points de l'article 42 seront couverts dans regex
# ajouter espace insecable nettoyage (je l ai deja normalement)
# article  40 et 42 en fall back??
def detect_radiations_keywords(texte_brut: str, extra_keywords):
    if not texte_brut:
        return
    # ------------------------------------------------------------------------------------------------------------------
    # --- DOUBLONS ---
    # annulation_doublon : ce qui veut dire que le num tva présent dans article n est plus le bon!!!
    # annulation_remplacement_numero_doublon : ce qui veut dire que ça a été fait on a l'ancien et le nouveau num ici
    # ------------------------------------------------------------------------------------------------------------------
    # --- Détection "pour cause de doublons a été annulée" ---
    if re.search(
        r"pour\s+cause\s+de\s+dou+blons?.*a\s+été\s+an+ul+ée",
        texte_brut,
        flags=re.IGNORECASE | re.DOTALL
    ):
        extra_keywords.append("annulation_doublon")

    #  --- Détection "Liste des entités enregistrées dont le remplacement du numéro d'entreprise
    #  pour cause de doublons a été annulé" ---
    if re.search(
                r"liste\s+des\s+entit[ée]s\s+enregistr[ée]es.*?"
                r"remplacement\s+du\s+num[ée]ro\s+d['’]entreprise\s+pour\s+cause\s+de\s+dou+blons?.*a\s+été\s+an+ul+é",
                texte_brut,
                flags=re.IGNORECASE | re.DOTALL,
        ):
        extra_keywords.append("annulation_remplacement_numero_doublon")
    # ------------------------------------------------------------------------------------------------------------------
    # --- Détection remplacement de numéro BCE ---
    # ------------------------------------------------------------------------------------------------------------------
    if re.search(
        r"remplac[ée]?\s+.*num(é|e)ro\s+d['’]entreprise",
        texte_brut,
        flags=re.IGNORECASE
    ):
        extra_keywords.append("remplacement_numero_bce")
    # ------------------------------------------------------------------------------------------------------------------
    #  Article 40 à 42 du Code de droit économique :
    #  Article 40 : procédure — absence ou données erronées
    #  Article 42 : exception — radiation d’office (procédure simplifiée sans frais)
    #    1° décès du fondateur (personne physique) depuis au moins 6 mois
    #    2° clôture de liquidation prononcée depuis au moins 3 mois
    #    3° clôture de faillite prononcée depuis au moins 3 mois
    #    3°/1 fusion ou scission datant d’au moins 3 mois
    #    4° non-dépôt des comptes annuels pendant au moins 3 exercices consécutifs
    #        -> retrait automatique de la radiation après dépôt des comptes
    #    5° sociétés sans activité ni modification depuis 7 ans :
    #        a) aucune activité, qualité ou unité d’établissement active depuis ≥ 3 ans
    #        b) statut actif à la BCE
    #        c) aucune demande d’autorisation ou de qualité en cours
    #        d) aucune modification des données BCE depuis 7 ans
    #        e) aucune publication (hors comptes annuels) au Moniteur belge depuis 7 ans
    #    6° non-respect des obligations UBO (registre des bénéficiaires effectifs) :
    #        a) non-transmission des infos UBO malgré amende depuis ≥ 60 jours
    #        b) absence de mise à jour annuelle UBO depuis ≥ 1 an
    #        c) non-transmission UBO + aucune publication au Moniteur belge depuis 7 ans
    #    7° sociétés étrangères radiées (depuis ≥ 3 mois) sur base d’infos reçues via le
    #        système européen d’interconnexion des registres (article III.15, alinéa 6)
    #
    #  Notes :
    # #   - Le service de gestion procède au retrait de la radiation si un critère n’est plus rempli.
    # #   - Les radiations et retraits des §1er, 4° à 6° sont publiés gratuitement au Moniteur belge.
    # #   - Ces radiations peuvent être élargies ou modifiées par arrêté royal.
    #  -----------------------------------------------------------------------------------------------------------------
    # --- Détection article III.40 du Code de droit économique ---
    if re.search(
                r"l['’]?\s*article\s*I{1,3}\s*[\.\-]?\s*40\b[\s,;:–-]*([^\.]{0,300})?\s*du\s+"
                r"code\s+de\s+droit\s+[ée]conomique",
                texte_brut,
                flags=re.IGNORECASE,):
        extra_keywords.append("article_iii_42")

    # --- Détection article III.42 du Code de droit économique ---
    if re.search(
            r"l['’]?\s*article\s*I{1,3}\s*[\.\-]?\s*42\b[\s,;:–-]*([^\.]{0,300})?\s*du\s+"
            r"code\s+de\s+droit\s+[ée]conomique",
            texte_brut,
            flags=re.IGNORECASE):
        extra_keywords.append("article_iii_42")

    # ------------------------------------------------------------------------------------------------------------------
    # RADIATION :  entite - adresses
    # ------------------------------------------------------------------------------------------------------------------
    # --- Détection "la radiation d'office des entités suivantes a été effectuée" ---
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
    # RETRAIT/ANNULATION : radiation d'office siege social - succursale - ubo
    #  NON RESPECT UBO
    # ------------------------------------------------------------------------------------------------------------------
    # --- Détection "annulation / arrêt de la radiation d'office de l'adresse du siège" ---
    if re.search(
            r"liste\s+des\s+entit[ée]s\s+enregistr[ée]es.*?"
            r"(annulation|arr[êe]t)\s+de\s+la\s+radiation\s+d['’]office\s+de\s+l['’]adresse\s+du\s+si[eè]ge\b.*",
            texte_brut,
            flags=re.IGNORECASE | re.DOTALL,):
        extra_keywords.append("annulation_ou_arret_radiation_adresse_siege")
    # --- Détection "annulation / arrêt de la radiation d'office de l'adresse de la succursale" ---
    if re.search(
            r"liste\s+des\s+entit[ée]s\s+enregistr[ée]es.*?"
            r"(annulation|arr[êe]t|retrait)\s+de\s+la\s+radiation\s+d['’]office\s+de\s+"
            r"l['’]adresse\s+de\s+la\ssuccursale\b.*",
            texte_brut,
            flags=re.IGNORECASE | re.DOTALL,
    ):
        extra_keywords.append("annulation_ou_arret_radiation_succursale_siege")

    # --- Détection "retrait de la radiation d’office suite au non-respect des formalités UBO" ---
    if re.search(
        r"(annulation|arr[êe]t|retrait)\s+de\s+la\s+radiation\s+"
        r"d['’]office.*non[- ]?respect.*formalit[ée]s?.*ubo",
        texte_brut,
        flags=re.IGNORECASE | re.DOTALL
    ):
        extra_keywords.append("retrait_radiation_ubo")
    # --- Détection "retrait de la radiation d’office pour non dépôt des comptes annuels" ---
    if re.search(
            (
                    r"(annulation|arr[êe]t|retrait)\s+de\s+la\s+radiation\s+"
                    r"d['’]?office\s+pour\s+non[-\s]?d[ée]p[oô]t\s+"
                    r"des\s+comptes\s+annuels"
            ),
            texte_brut,
            flags=re.IGNORECASE | re.DOTALL,
    ):
        extra_keywords.append("retrait_radiation_non_depot_comptes")

    # ------------------------------------------------------------------------------------------------------------------
    # CORRECTION : date radiation d'office -
    # ------------------------------------------------------------------------------------------------------------------
    # --- Détection "correction de la date de prise d'effet de la radiation d'office de
    # l'adresse du siège ou de la succursale" ---
    if re.search(
            r"liste\s+des\s+entit[ée]s\s+enregistr[ée]es.*?"
            r"correction\s+de\s+la\s+date\s+de\s+prise\s+d['’]?effet\s+de\s+la\s+radiation\s+"
            r"d['’]?office\s+de\s+l['’]?adresse\s+"
            r"(du\s+si[eè]ge|de\s+la\s+succursale)\b",
            texte_brut,
            flags=re.IGNORECASE | re.DOTALL,):
        extra_keywords.append("correction_date_radiation_adresse_siege_ou_succursale")