import re

def detect_tribunal_entreprise_keywords(texte_brut, extra_keywords):
    # --- DESIGNATION / REMPLACEMENT DE LIQUIDATEUR ---
    pattern_designation_liquidateur = (
        r"\ba\s+(?:été\s+)?d[ée]sign[ée]?(?:\s*,?\s*en\s+remplacement\s+de\s+\w+)?"
        r".{0,80}?\ben\s+qualit[ée]\s+de\s+liquidateur\b"
    )

    # Variante simple pour capter "nommé liquidateur"
    pattern_nomination_liquidateur = (
        r"\b(?:nomm[ée]?|désign[ée]?)\b.{0,50}?\bliquidateur\b"
    )

    # 🆕 Spécifique à ton exemple :
    # "a été désignée, en remplacement de Me X, en qualité de liquidateur"
    pattern_designation_liquidateur_remplacement = (
        r"a\s+été\s+d[ée]sign[ée]?\s*,?\s*en\s+remplacement\s+de\s+[^,]+,\s*en\s+qualit[ée]\s+de\s+liquidateur"
    )

    # --- annulation ag
    pattern_annulation_ag = r"(?:prononc[ée]e?|d[ée]cid[ée]e?)\s+l[’']?annulation\s+de\s+la\s+d[ée]cision\s+de\s+l[’']?assembl[ée]e\s+g[ée]n[ée]rale"
    # --- FAILLITE ---
    pattern_ouverture = r"\bouverture\s+de\s+la\s+faillite\b"

    pattern_faillite = r"faillite"
    pattern_rapporte = r"\brapporte\s+(la\s+)?faillite(s)?(\s+\w+)?"
    pattern_ordonne_rapporter_faillite = r"\bordonne\s+de\s+rapporter\s+la\s+faillite(s)?\b"

    pattern_effacement = r"\beffacement\s+de\s+la\s+faillite\s+de\b[.:]?\s*"

    # --- LIQUIDATION ---
    pattern_liquidation = r"\bliquidations?\b"
    pattern_liquidation_bis = r"\bliquidation(?:s)?\s*de\b"
    pattern_ouverture_liquidation_judiciaire = (
        r"\bouverture\s+de\s+la\s+procédure\s+de\s+liquidation\s+judiciaire(?:\s+immédiate)?\b"
    )

    # --- DISSOLUTION ---
    pattern_cloture_dissolution_judiciaire = (r"\bcl[oô]ture\s+de\s+la\s+dissolution\s+judiciaire\b")
    pattern_ouverture_dissolution_judiciaire = (r"\bouverture\s+de\s+la\s+dissolution\s+judiciaire\b")
    pattern_dissolution_judiciaire_generique = (r"\bdissolution\s+judiciaire\b")
    pattern_dissolution_judiciaire_ultra_generique = (r"\bdissolution\b")
    # --- REORGANISATION JUDICIAIRE ---
    pattern_revocation_plan_reorganisation_judiciaire = r"révocation\s+du\s+plan\s+de\s+réorganisation\s+judiciaire"
    # Pattern combiné pour "refus homologation plan" + "clôture procédure RJ"
    pattern_refus_homologation_cloture_reorg = (
        r"(?:refus[ée]?\s+(?:d['’]homologation|l['’]homologation)\s+du\s+plan)"  # refus homologation du plan
        r".{0,200}?"  # jusqu’à 120 caractères max
        r"(?:cl[oô]tur[ée]?\s+(?:la\s+)?proc[ée]dure\s+de\s+r[ée]organisation\s+judiciaire)"  # clôture procédure RJ
    )

    pattern_reorg_generique = r"\bréorganisation\s+judiciaire\s+de\b"
    pattern_ouverture_reorg = r"\bouverture\s+de\s+la\s+réorganisation\s+judiciaire\b"
    pattern_prorogation_reorg = r"\bprorogation\s+du\s+sursis\s+de\s+la\s+réorganisation\s+judiciaire\b"
    pattern_nouveau_plan_reorg = r"\bautorisation\s+de\s+d[ée]p[oô]t\s+d['’]un\s+nouveau\s+plan\s+de\s+la\s+réorganisation\s+judiciaire\b"
    pattern_accord_collectif = r"réorganisation\s+judiciaire\s+par\s+accord\s+collectif"

    # --- TRANSFERT SOUS AUTORITE DE JUSTICE ---
    pattern_transfert_autorite_judiciaire_generique = (
        r"\bproc[ée]dure\s+de\s+transfert\s+sous\s+l?['’]?\s*autorit[ée]\s+(?:judiciaire|de\s+justice)\b"
    )
    pattern_transfert_autorite_judiciaire_generique_bis = (
        r"\btransfert\s+sous\s+l?['’]?\s*autorit[ée]\s+(?:judiciaire|de\s+justice)\b"
    )

    pattern_ouverture_transfert = (
        r"\bouverture\s+du\s+transfert\s+sous\s+autorit[ée]\s+judiciaire(?:\s+\w+)?"
    )
    pattern_ouverture_transfert_bis = (
        r"ouverture\s+du\s+transfert\s+sous\s+autorit(?:é|e)\s+judiciaire"
    )
    pattern_decision_ouverture_transfert = (
        r"\ba\s+d[ée]cid[ée]?\s+de\s+d[ée]clarer\s+ouverte\s+la\s+proc[ée]dure\s+de\s+transfert\s+sous\s+l?['’]?\s*autorit[ée]\s+(?:judiciaire|de\s+justice)\b"
    )
    # 🆕 nouveau
    pattern_declarer_ouverte_transfert = (
        r"d[ée]clar[ée]?\s+ouverte\s+la\s+proc[ée]dure\s+de\s+transfert\s+sous\s+l?['’]?\s*autorit[ée]\s+(?:judiciaire|de\s+justice)"
    )

    # --- information sur l'état de la procédure       ---
    pattern_suspend_effets_publication_pv_ag = r"\b(?:ordonne\s+de\s+)?suspend(?:re)?\s+les\s+effets?\s+à\s+l?['’]?égard\s+des\s+tiers\s+de\s+la\s+publication(?:\s+aux?\s+annexes?\s+du\s+moniteur\s+belge)?[\s\S]*?proc[èe]s[-\s]?verbaux\s+des?\s+assembl[ée]es?\s+g[ée]n[ée]rales?"
    pattern_administrateur_provisoire = r"administrateur\s+provisoire\s+d[ée]sign[ée]?"
    pattern_administrateur_provisoire_droit_commun = (
        r"\b(?:a\s+)?d[ée]sign[ée]?\s+en\s+qualit[ée]\s+d['’]?"
        r"administrateur(?:s)?\s+provisoire(?:s)?\s+de\s+droit\s+commun\b"
    )

    pattern_cloture = r"\b[cC](l[oô]|olo)ture\b"
    pattern_cloture_insuffisance_actif = r"\binsuffisance\s+d[’'\s]?actif\b"
    pattern_prolongation_administrateur_provisoire = (
        r"\bprolong\w*\s+le\s+mandat\b.{0,120}?\badministrateur\s+provisoire\b"
    )

    pattern_designation_mandataire = (
        r"en\s+application\s+de\s+l['’]?\s*(?:article|art\.?)\s*XX[\.\s]?(2\d{1,2}|3\d{1,2})"
        r"(?:\s*(?:du\s*(?:CDE|code\s+de\s+droit\s+[ée]conomique))?)"
    )
    pattern_delai_modere = r"(?i)(délais?\s+modérés?.{0,80}article\s+5[.\s\-]?201)"
    pattern_homologation_plan = r"\bhomologation\s+du\s+plan\s+de\b"
    pattern_homologation_accord = r"\bhomologation\s+de\s+l[’']accord\s+amiable\s+de\b"
    pattern_rapporte_bis = r"\best\s+rapportée(s)?(\s+.*)?"
    pattern_rapporte_dissolution = (
        r"\brapport[ée]?\s+la\s+dissolution\b"
    )
    pattern_effacement_partiel = r"(?:\b[lL]['’]?\s*)?[eé]ffacement\s+partiel\b"
    pattern_excusabilite = r"\ble\s+failli\s+est\s+déclaré\s+excusable\b[\.]?\s*"
    pattern_effacement_ter = r"(l['’]?\s*)?effacement\s+(est\s+)?accordé"
    pattern_sans_effacement = r"\bsans\s+effacement\s+de\s+la\s+faillite\s+de\b[.:]?\s*"
    pattern_effacement_bis = r"\boctroie\s+l['’]effacement\s+à\b[.:]?\s*"
    pattern_interdiction = (
        r"\b(interdit[ée]?|interdiction).{0,150}?"
        r"\b(exploiter|exercer|diriger|gérer|administrer).{0,100}?"
        r"\b(entreprise|fonction|personne\s+morale|société)\b"
    )
    pattern_remplacement_administrateur = (
        r"(curateur|liquidateur|administrateur).*?remplac[ée]?(?:\s+à\s+sa\s+demande)?\s+par"
    )
    pattern_interdiction_bis = (
        r"(?:fait\s+)?interdiction\s+(?:à\s+(?:Monsieur|Madame|Mr|Mme)?\s*)?"
        r"([A-Z][a-zéèêàâïüë\-']+(?:\s+[A-Z][A-ZÉÈÊÀÂ\-']+)+)"
    )
    pattern_remplacement_juge_commissaire = r"est\s+remplac[ée]?\s+par\s+le\s+juge\s+commissaire"
    pattern_remplacement_juge_commissaire_bis = (
        r"est\s+remplac[ée]?\s+par\s+(le|les)\s+juges?\s+commissaires?"
    )

    pattern_report_cessation_paiement = r"report[\s\w,.'’():\-]{0,80}?cessation\s+des\s+paiements"
    if re.search(pattern_annulation_ag, texte_brut, flags=re.IGNORECASE):
        extra_keywords.append("annulation_decision_ag_tribunal_de_l_entreprise")
    if re.search(pattern_designation_liquidateur_remplacement, texte_brut, flags=re.IGNORECASE):
        extra_keywords.append("designation_liquidateur_remplacement_tribunal_de_l_entreprise")
    elif re.search(pattern_designation_liquidateur, texte_brut, flags=re.IGNORECASE):
        extra_keywords.append("designation_liquidateur_tribunal_de_l_entreprise")
    elif re.search(pattern_nomination_liquidateur, texte_brut, flags=re.IGNORECASE):
        extra_keywords.append("designation_liquidateur_tribunal_de_l_entreprise")

    if re.search(pattern_rapporte, texte_brut, flags=re.IGNORECASE) \
            or re.search(pattern_rapporte_bis, texte_brut) \
            or re.search(pattern_ordonne_rapporter_faillite, texte_brut, flags=re.IGNORECASE):
        extra_keywords.append("rapporte_faillite_tribunal_de_l_entreprise")
    if re.search(pattern_rapporte_dissolution, texte_brut, flags=re.IGNORECASE):
        extra_keywords.append("rapporte_dissolution_tribunal_de_l_entreprise")

    else:
        if re.search(r"\b[dD]ésignation\b", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("designation_tribunal_de_l_entreprise")

        if re.search(pattern_cloture, texte_brut, flags=re.IGNORECASE):
            if re.search(pattern_cloture_insuffisance_actif, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("cloture_insuffisance_actif_tribunal_de_l_entreprise")
            if re.search(pattern_cloture_dissolution_judiciaire, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("cloture_dissolution_tribunal_de_l_entreprise")
            if re.search(pattern_dissolution_judiciaire_ultra_generique, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("cloture_dissolution_tribunal_de_l_entreprise")
            if re.search(pattern_faillite, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("cloture_faillite_tribunal_de_l_entreprise")
            elif re.search(pattern_liquidation, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("cloture_liquidation_tribunal_de_l_entreprise")
        # rajouter else ici? 1b8a3b9f6d69a6ed271a5b1fabceaff959aeaff8150df0ce8a53fd11bd2e581d
        if re.search(pattern_dissolution_judiciaire_generique, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("dissolution_judiciaire_tribunal_de_l_entreprise")
        if re.search(pattern_ouverture_dissolution_judiciaire, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("ouverture_dissolution_judiciaire_tribunal_de_l_entreprise")
        if re.search(pattern_ouverture_liquidation_judiciaire, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("ouverture_liquidation_judiciaire_tribunal_de_l_entreprise")
        if re.search(pattern_designation_mandataire, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("designation_mandataire_tribunal_de_l_entreprise")
        if re.search(pattern_liquidation_bis, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("liquidation_tribunal_de_l_entreprise")
        if re.search(pattern_delai_modere, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("delai_modere_tribunal_de_l_entreprise")

        if re.search(pattern_ouverture, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("ouverture_faillite_tribunal_de_l_entreprise")
        elif re.search(pattern_ouverture_transfert, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("ouverture_transfert_autorite_judiciaire_tribunal_de_l_entreprise")
        elif re.search(pattern_ouverture_transfert_bis, texte_brut.replace("\xa0", " "), flags=re.IGNORECASE):
            extra_keywords.append("ouverture_transfert_autorite_judiciaire_tribunal_de_l_entreprise")
        elif re.search(pattern_decision_ouverture_transfert, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("ouverture_transfert_autorite_judiciaire_tribunal_de_l_entreprise")
        elif re.search(pattern_declarer_ouverte_transfert, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("ouverture_transfert_autorite_judiciaire_tribunal_de_l_entreprise")
        # 🆕 Cas générique sans "ouverture"
        elif re.search(pattern_transfert_autorite_judiciaire_generique, texte_brut, flags=re.IGNORECASE) \
                or re.search(pattern_transfert_autorite_judiciaire_generique_bis, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("transfert_autorite_judiciaire_tribunal_de_l_entreprise")
        if re.search(pattern_interdiction, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("interdiction_gestion_tribunal_de_l_entreprise")
        elif re.search(pattern_interdiction_bis, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("interdiction_gestion_tribunal_de_l_entreprise")

        # Effacement : priorité au refus, ensuite partiel, ensuite complet
        if re.search(r"\b(?:\(?[eE]\)?[\s:\.-]*)?effacement\b", texte_brut, flags=re.IGNORECASE) and re.search(
                r"\brefus[ée]?\b", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("effacement_refusé_tribunal_de_l_entreprise")
        elif re.search(pattern_sans_effacement, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("sans_effacement_tribunal_de_l_entreprise")
        elif re.search(pattern_effacement_partiel, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("effacement_partiel_tribunal_de_l_entreprise")
        elif re.search(pattern_effacement, texte_brut, flags=re.IGNORECASE) or re.search(pattern_effacement_bis,
                                                                                         texte_brut,
                                                                                         flags=re.IGNORECASE) or re.search(
            pattern_effacement_ter, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("effacement_tribunal_de_l_entreprise")

        if re.search(pattern_remplacement_juge_commissaire, texte_brut, flags=re.IGNORECASE) or re.search(
                pattern_remplacement_juge_commissaire_bis, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("remplacement_juge_commissaire_tribunal_de_l_entreprise")
        # Fallback intelligent, en tout dernier recours
        elif re.search(pattern_remplacement_administrateur, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("remplacement_administrateur_tribunal_de_l_entreprise")

        if re.search(pattern_prolongation_administrateur_provisoire, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("prolongation_administrateur_tribunal_de_l_entreprise")

        # pas vraiment utile?
        elif not any(k.startswith("cloture") or k.startswith("ouverture") for k in extra_keywords):
            if re.search(
                    r"(faillite|faillite\s+de\s*:?.{0,80}?(déclar[ée]e?|prononc[ée]e?))"
                    r"|\bfaillite\b.{0,80}?(déclar[ée]e?|prononc[ée]e?)",
                    texte_brut,
                    flags=re.IGNORECASE
            ):
                extra_keywords.append("ouverture_faillite_tribunal_de_l_entreprise")
        if re.search(pattern_report_cessation_paiement, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("report_cessation_paiement_tribunal_de_l_entreprise")
        # Réorganisations
        reorg_tags = 0
        if re.search(pattern_ouverture_reorg, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("ouverture_reorganisation_tribunal_de_l_entreprise")
            reorg_tags += 1
        if re.search(pattern_prorogation_reorg, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("prorogation_reorganisation_tribunal_de_l_entreprise")
            reorg_tags += 1
        if re.search(pattern_nouveau_plan_reorg, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("nouveau_plan_reorganisation_tribunal_de_l_entreprise")
            reorg_tags += 1
        if re.search(pattern_homologation_plan, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("homologation_plan_tribunal_de_l_entreprise")
            reorg_tags += 1
        elif re.search(pattern_homologation_accord, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("homologation_accord_amiable_tribunal_de_l_entreprise")
            reorg_tags += 1
        elif re.search(pattern_revocation_plan_reorganisation_judiciaire, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("revocation_plan_reorganisation_judicaire_tribunal_de_l_entreprise")
            reorg_tags += 1
        if re.search(pattern_refus_homologation_cloture_reorg,texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("refus_hologation_revocation_plan_reorganisation_judicaire_tribunal_de_l_entreprise")
        if re.search(pattern_reorg_generique, texte_brut, flags=re.IGNORECASE) and reorg_tags == 0:
            extra_keywords.append("reorganisation_tribunal_de_l_entreprise")
        if re.search(pattern_accord_collectif, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("reorganisation_judiciaire_par_accord_collectif_tribunal_de_l_entreprise")
        # Autres
        if re.search(pattern_administrateur_provisoire, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("designation_administrateur_provisoire_tribunal_de_l_entreprise")
        if re.search(pattern_administrateur_provisoire_droit_commun, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("designation_administrateur_provisoire_droit_commun_tribunal_de_l_entreprise")
        if re.search(pattern_suspend_effets_publication_pv_ag , texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("suspension_effets_ag")
        if re.search(pattern_excusabilite, texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("excusable_tribunal_de_l_entreprise")

        extra_keywords = list(dict.fromkeys(extra_keywords))
