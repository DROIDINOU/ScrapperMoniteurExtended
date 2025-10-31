KEYWORD_GROUPS = {

    # 🔹 Procédures collectives (faillite, liquidation, réorganisation, effacement)
    "procedures_collectives": [
        "rapporte_faillite",
        "rapporte_faillite_tribunal_de_l_entreprise",
        "rapporte_dissolution_tribunal_de_l_entreprise",
        "dissolution_judiciaire",
        "dissolution_judiciaire_tribunal_de_l_entreprise",
        "cloture_liquidation",
        "cloture_liquidation_tribunal_de_l_entreprise",
        "cloture_faillite_tribunal_de_l_entreprise",
        "cloture_reorganisation_judiciaire",
        "ouverture_liquidation_judiciaire_tribunal_de_l_entreprise",
        "ouverture_faillite_tribunal_de_l_entreprise",
        "liquidation_tribunal_de_l_entreprise",
        "effacement_dette",
        "effacement_partiel_tribunal_de_l_entreprise",
        "effacement_tribunal_de_l_entreprise",
        "sans_effacement_tribunal_de_l_entreprise",
        "refus_effacement_dette",
        "delai_modere_tribunal_de_l_entreprise",
        "non_excusable",   # ✅ ajouté ici (faillite non excusable)
    ],

    # 🔹 Administration et mandataires judiciaires
    "administration_mandataires": [
        "designation_liquidateur_remplacement_tribunal_de_l_entreprise",
        "designation_liquidateur_tribunal_de_l_entreprise",
        "remplacement_juge_commissaire_tribunal_de_l_entreprise",
        "remplacement_administrateur_tribunal_de_l_entreprise",
        "designation_mandataire_tribunal_de_l_entreprise",
        "prolongation_administrateur_tribunal_de_l_entreprise",
        "designation_administrateur_provisoire_tribunal_de_l_entreprise",
        "designation_administrateur_provisoire_droit_commun_tribunal_de_l_entreprise",
        "decharge_administrateur_provisoire_tribunal_de_l_entreprise",
        "report_cessation_paiement_tribunal_de_l_entreprise",
        "fin_de_mission",
        "désignation",
    ],

    # 🔹 Décisions judiciaires et jugements
    "decisions_judiciaires": [
        "reforme_mise_a_neant",
        "reforme_ordonnance",
        "reforme_jugement",
        "reforme_decision_jp",
        "mise_a_neant",
        "mise_neant_jugement",
        "homologation_plan_apres_reforme",
        "retractation_dissolution",
        "annulation_decision_AG",
        "annulation_decision_ag_tribunal_de_l_entreprise",
        "levee_mesure",
        "levee_mesure_observation",
        "fin_mesure",
        "sursis",
        "rejet_demande",
        "condamnation",      # ✅ conservé
        "non_excusable",     # ✅ aussi présent ici (pertinent pour décisions)
    ],

    # 🔹 Radiations / BCE / UBO / Adresses / Corrections
    "radiations_bce_ubo": [
        "retrait_radiation_non_depot_comptes",
        "retrait_ou_annulation_radiation_office",
        "annulation_ou_retrait_radiation_ubo",
        "radiation_office_ubo",
        "radiation_adresse_siege",
        "liste_radiations_adresse_siege",
        "annulation_ou_arret_radiation_adresse_siege",
        "annulation_ou_arret_radiation_succursale_siege",
        "annulation_doublon",
        "annulation_remplacement_numero_doublon",
        "remplacement_numero_bce",
        "correction_date_radiation_adresse_siege_ou_succursale",
        "ouverture_transfert_autorite_judiciaire_tribunal_de_l_entreprise",
        "transfert_autorite_judiciaire_tribunal_de_l_entreprise",
    ],
}

# mapping interne → lisible
KEYWORD_LABELS = {

    # -------------------------
    # PROCÉDURES COLLECTIVES
    # -------------------------
    "rapporte_faillite": "Rapport de faillite",
    "rapporte_faillite_tribunal_de_l_entreprise": "Rapport de faillite (Tribunal de l’entreprise)",
    "rapporte_dissolution_tribunal_de_l_entreprise": "Rapport de dissolution (Tribunal de l’entreprise)",
    "dissolution_judiciaire": "Dissolution judiciaire",
    "dissolution_judiciaire_tribunal_de_l_entreprise": "Dissolution judiciaire (Tribunal de l’entreprise)",
    "cloture_liquidation": "Clôture de liquidation",
    "cloture_liquidation_tribunal_de_l_entreprise": "Clôture de liquidation (Tribunal de l’entreprise)",
    "cloture_faillite_tribunal_de_l_entreprise": "Clôture de faillite (Tribunal de l’entreprise)",
    "cloture_reorganisation_judiciaire": "Clôture de réorganisation judiciaire",
    "ouverture_liquidation_judiciaire_tribunal_de_l_entreprise": "Ouverture de liquidation judiciaire (Tribunal de l’entreprise)",
    "ouverture_faillite_tribunal_de_l_entreprise": "Ouverture de faillite (Tribunal de l’entreprise)",
    "liquidation_tribunal_de_l_entreprise": "Liquidation (Tribunal de l’entreprise)",
    "effacement_dette": "Effacement des dettes",
    "effacement_partiel_tribunal_de_l_entreprise": "Effacement partiel (Tribunal de l’entreprise)",
    "effacement_tribunal_de_l_entreprise": "Effacement (Tribunal de l’entreprise)",
    "sans_effacement_tribunal_de_l_entreprise": "Faillite sans effacement (Tribunal de l’entreprise)",
    "refus_effacement_dette": "Refus d’effacement des dettes",
    "delai_modere_tribunal_de_l_entreprise": "Délai modéré (Tribunal de l’entreprise)",
    "non_excusable": "Faillite non excusable",

    # -------------------------
    # ADMINISTRATION / MANDATAIRES
    # -------------------------
    "designation_liquidateur_remplacement_tribunal_de_l_entreprise": "Désignation / Remplacement du liquidateur",
    "designation_liquidateur_tribunal_de_l_entreprise": "Désignation d’un liquidateur",
    "remplacement_juge_commissaire_tribunal_de_l_entreprise": "Remplacement du juge commissaire",
    "remplacement_administrateur_tribunal_de_l_entreprise": "Remplacement de l’administrateur",
    "designation_mandataire_tribunal_de_l_entreprise": "Désignation d’un mandataire",
    "prolongation_administrateur_tribunal_de_l_entreprise": "Prolongation de l’administrateur",
    "designation_administrateur_provisoire_tribunal_de_l_entreprise": "Désignation d’un administrateur provisoire",
    "designation_administrateur_provisoire_droit_commun_tribunal_de_l_entreprise": "Désignation d’un administrateur provisoire (droit commun)",
    "decharge_administrateur_provisoire_tribunal_de_l_entreprise": "Décharge de l’administrateur provisoire",
    "report_cessation_paiement_tribunal_de_l_entreprise": "Report de cessation de paiement",
    "fin_de_mission": "Fin de mission",
    "désignation": "Désignation",

    # -------------------------
    # DÉCISIONS JUDICIAIRES
    # -------------------------
    "reforme_mise_a_neant": "Réforme / Mise à néant",
    "reforme_ordonnance": "Réforme de l’ordonnance",
    "reforme_jugement": "Réforme du jugement",
    "reforme_decision_jp": "Réforme de la décision",
    "mise_a_neant": "Mise à néant",
    "mise_neant_jugement": "Mise à néant du jugement",
    "homologation_plan_apres_reforme": "Homologation du plan après réforme",
    "retractation_dissolution": "Rétractation d’une dissolution",
    "annulation_decision_AG": "Annulation de décision d’assemblée générale",
    "annulation_decision_ag_tribunal_de_l_entreprise": "Annulation de décision d’assemblée générale (Tribunal de l’entreprise)",
    "levee_mesure": "Levée de mesure",
    "levee_mesure_observation": "Levée de mesure (période d’observation)",
    "fin_mesure": "Fin de mesure",
    "sursis": "Sursis",
    "rejet_demande": "Rejet de la demande",
    "condamnation": "Condamnation",

    # -------------------------
    # RADIATIONS / BCE / UBO / ADRESSES
    # -------------------------
    "retrait_radiation_non_depot_comptes": "Retrait de radiation — non dépôt des comptes",
    "retrait_ou_annulation_radiation_office": "Retrait / Annulation de radiation (office)",
    "annulation_ou_retrait_radiation_ubo": "Annulation / retrait radiation UBO",
    "radiation_office_ubo": "Radiation UBO (office)",
    "radiation_adresse_siege": "Radiation adresse du siège",
    "liste_radiations_adresse_siege": "Liste des radiations (adresse du siège)",
    "annulation_ou_arret_radiation_adresse_siege": "Arrêt / Annulation de radiation d’adresse de siège",
    "annulation_ou_arret_radiation_succursale_siege": "Arrêt / Annulation de radiation de succursale",
    "annulation_doublon": "Annulation (doublon)",
    "annulation_remplacement_numero_doublon": "Remplacement numéro BCE (doublon)",
    "remplacement_numero_bce": "Remplacement du numéro BCE",
    "correction_date_radiation_adresse_siege_ou_succursale": "Correction de date de radiation (siège ou succursale)",
    "ouverture_transfert_autorite_judiciaire_tribunal_de_l_entreprise": "Ouverture de transfert (Autorité judiciaire)",
    "transfert_autorite_judiciaire_tribunal_de_l_entreprise": "Transfert (Autorité judiciaire)",
}

