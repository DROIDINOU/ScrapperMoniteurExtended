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

