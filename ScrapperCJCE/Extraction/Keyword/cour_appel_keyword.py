import re
from Utilitaire.outils.MesOutils import normalize_mois, normalize_annees

DATE_RX = r"(?:\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{2,4})"
DATE_OPT = rf"(?:\s+du\s+{DATE_RX})?"   # ← rend la date optionnelle
RG_TOKEN = r"\(RG"


APOST = r"[’']"  # apostrophe droite ou typographique
# --- Interdiction : "interdit à … pour une durée de X ans" (ou "pendant X ans")
NB_MOTS = r"(?:\d{1,2}|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|quinze|vingt)"
# Thèmes “contenu” (sans dates)
RX_SUCC = re.compile(r"""
    \bsuccession[s]?
    (?:
        [^.\n]{0,40}?
        (?:
            (?P<vac>
                (?:réputée[s]?(?:[^.\n]{0,10})?vacante[s]?)  # cas 1 : "réputée vacante"
              | vacante[s]?                                  # ✅ cas 2 : "succession vacante"
            )
          | (?P<desh>en\s+désh[ée]rence)
        )
    )?
""", re.IGNORECASE | re.VERBOSE)


# A rapporté / rapporte la faillite (présent ou passé), date et blabla optionnels avant
RX_RAPPORTE_FAILLITE = re.compile(
    rf"(?:par\s+arr[êe]t\s+du\s+{DATE_RX}\s*,\s*)?.{{0,160}}?\b(?:a\s+)?rapport[ée]?\s+la\s+faillite\b",
    re.IGNORECASE | re.DOTALL
)

# Variante si tu veux aussi choper le nom après "de" (facultatif)
RX_RAPPORTE_FAILLITE_DE = re.compile(
    r"\brapport[ée]?\s+la\s+faillite\s+de\s+(?P<cible>[^.;:\n]{2,160})",
    re.IGNORECASE | re.DOTALL
)

# A) "interdit à <cible> ... pour une durée de X ans" (ou "pendant X ans")
RX_INTERDIT_A_DUREE = re.compile(
    rf"""
    \b(?:il\s+est\s+)?interdit\s+à\s+
    (?P<cible>[^,;:\n]{{2,200}})
    \s*,?\s*
    .{{0,300}}?
    (?:
        pour\s+une?\s+durée\s+de\s+|pendant\s+
    )
    (?P<annees>{NB_MOTS})\s+(?:ans?|années?)
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL
)

# B) "prononce l'interdiction ... à l'égard de <cible> ... pour une durée de X ans"
RX_INTERDICTION_DECISION = re.compile(rf"""
    \b(?:prononce|confirme|maintient|r[ée]forme\s+et\s+prononce)\s+
    l[’']?interdiction.*?                      # texte libre non-gourmand
    (?:
        (?:\bà\s+l[’']?égard\s+de\b|\bde\b|\bà\b)\s+
    )?
    (?P<cible>[^,;:\n]{{2,200}})
    \s*,?\s*
    .{{0,300}}?
    (?:
        pour\s+une\s+durée\s+de\s+|pendant\s+
    )
    (?P<annees>{NB_MOTS})\s+ans?
""", re.IGNORECASE | re.VERBOSE | re.DOTALL)

RX_INTERDISANT_A_DUREE = re.compile(
    rf"""
    \binterdisant\s+à\s+
    (?P<cible>[^,;:\n]{{2,200}})
    \s*,?\s*
    .{{0,300}}?
    (?:
        pour\s+une?\s+durée\s+de\s+|pendant\s+
    )
    (?P<annees>{NB_MOTS})\s+(?:ans?|années?)
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL
)

# C) Spécifique "diriger/engager personne morale" (tag complémentaire)
PAT_INTERDICTION_DIRIGER = re.compile(
    r"d[’']exercer\s+une\s+fonction\s+conf[ée]rant\s+le\s+pouvoir\s+d[’']engager\s+une\s+personne\s+morale",
    re.IGNORECASE,
)


RX_ABSENCE = re.compile(rf"""
    (?:
        # "est présumé absent", "présumée d’absence"
        (?P<presum>\bprésum[ée]?\b.{0,15}?(?:absent(?:e|es|s)?|d{APOST}?absence)\b)

      | # "présomption d'absence"
        (?P<presomp>\bprésomption\s+d{APOST}?absence\b)

    )
""", re.IGNORECASE | re.VERBOSE)

# Cas strict : "l'absence de Monsieur X" ou "l'absence de Dupont"
RX_ABSENCE_DE = re.compile(rf"""
    (?P<absence_de>
        \b
        (?:d[ée]clar(?:e|er|é(?:e|s)?|ait|aient|era(?:ient)?|ent)\s+(?:[^.\n]{{0,60}})?)?
        (?:l|d){APOST}?\s*absence\s+de\s+
        (?:
            (?:Monsieur|Madame|M\.|Mme)\b
            |[A-ZÉÈÀÂÎÔÙ][a-zà-öø-ÿ'\-]+
        )
        (?:\s+[A-ZÉÈÀÂÎÔÙ][a-zà-öø-ÿ'\-]+){{0,3}}
    )
""", re.VERBOSE)  # ⚠️ pas de IGNORECASE ici

RX_CAPABLE_BIENS_STMT = re.compile(
    r"\b(?:dit\s+pour\s+droit\s+que\s+)?(?:le\s+tribunal\s+)?(?:statuant\s+)?(?:monsieur|madame)\b[^.\n]{0,100}?\best\s+capable\b(?:[^.\n]{0,60}?(?:gestion\s+de\s+ses\s+biens|g[ée]rer\s+ses\s+biens))?",
    re.IGNORECASE
)
RX_CONDAMN       = re.compile(r"\b(?:condamn[ée]?(?:es)?|emprisonnement|réclusion|peine\s+privative\s+de\s+liberté)\b", re.IGNORECASE)
RX_SANS_DOM      = re.compile(r"\bsans\s+(?:résidence|domicile)\s+ni\s+(?:résidence|domicile)(?:\s+connu[e]?s?)?", re.IGNORECASE)
RX_DESIGN = re.compile(
    r"[,:\s]*\bdésign(?:é|ée|ation)\b(.*?)(?:en\s+qualité\s+de\s+)?\b(?:administrateur|administratrice|curateur|liquidateur)\b",
    re.IGNORECASE | re.DOTALL
)
RX_DISSOLUTION   = re.compile(r"\bdissolution\s+judiciaire\b", re.IGNORECASE)
RX_REFORME_ORD   = re.compile(r"r[ée]forme\s+l[’']?ordonnance", re.IGNORECASE)
RX_LEVEE_OBS     = re.compile(r"\bl[èe]ve\s+la\s+mesure\s+d[’']?observation\b", re.IGNORECASE)
RX_CLOTURE_LIQ = re.compile(r"\bcl[ôo]ture\s+de\s+(?:la\s+)?liquidation(?:\s+judiciaire)?\b", re.IGNORECASE)
RX_CLOTURE_REORGANISATION = re.compile(
    r"(met\s+fin\s+à\s+la\s+procédure\s+de\s+r[ée]organisation\s+judiciaire"
    r"|cl[ôo]ture\s+la\s+procédure\s+de\s+r[ée]organisation\s+judiciaire)",
    re.IGNORECASE
)
RX_OPP_APPEL_NON_AVENUE_ET_PUB_MB = re.compile(
    r"^(?=.*\bdit\s+l[’']?(?:opposition|appel)\b[\s\S]{0,200}?\bnon[-\s]+avenue?\b)"
    r"(?=.*\bordonne\s+la\s+publication\b[\s\S]{0,200}?(?:aux?\s+annexes\s+du\s+)?moniteur\s+belge\b)",
    flags=re.IGNORECASE | re.DOTALL
)

RX_SURSIS_MOIS_ACCORDE_A = re.compile(
    r"""
    # (préfixe facultatif) "par arrêt de la Cour d'appel de ..."
    (?:par\s+arr[êe]t\s+de\s+la\s+cour\s+d\s*[’']\s*appel\s+[^,]*,\s*)?
    # noyau : "un/le sursis de X mois est accordé à ..."
    \b(?:un|le)?\s*sursis\s+de\s+
    (?P<duree>\d{1,2}|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze)
    \s+mois
    \s+est\s+accord[ée]?\s+à\s+
    (?P<beneficiaire>[^.;:\n]{3,160})            # capture jusqu’à ., ;, : ou fin de ligne
    """,
    flags=re.IGNORECASE | re.DOTALL | re.VERBOSE
)

RX_CONVENTION_TRANSFERT = re.compile(
    r"""
    \bconclusion\s+de\s+la\s+convention\s+de\s+transfert\b
    """,
    flags=re.IGNORECASE | re.VERBOSE
)


RX_DISSOLUTION_RETRACTEE = re.compile(
    r"la\s+dissolution(?:\s+judiciaire)?\s+de[\s\S]*?a\s+été\s+r[ée]tract[ée]e?\b",
    re.IGNORECASE
)

RX_EFFACEMENT = re.compile(
    r"\boctroie\b.*?\ble\s+b[ée]n[ée]fice\s+de\s+l[’']?effacement",
    re.IGNORECASE | re.DOTALL
)

RX_REFUS_EFFACEMENT = re.compile(
    r"(?:n['’]?\s*y\s+a\s+pas\s+lieu\s+d['’]accorder\s+le\s+b[ée]n[ée]fice\s+de\s+l[’']?effacement"
    r"|refuse\s+d['’]accorder\s+le\s+b[ée]n[ée]fice\s+de\s+l[’']?effacement)",
    re.IGNORECASE | re.DOTALL
)


RX_MISE_A_NEANT = re.compile(
    r"la\s+cour\s+d\s*[’']?\s*appel\s+(?:de\s+\w+)?\s+a\s+mis\s+à\s+n[ée]ant\s+le\s+jugement",
    re.IGNORECASE
)



RX_INTERDIT_EXPLOITATION = re.compile(
    r"interdisant\s+à\s+(.{1,300}?)\s+d[’']?exploiter\s+une\s+entreprise",
    re.IGNORECASE | re.DOTALL
)

# Excusabilité (faillite)
RX_NON_EXCUSABLE = re.compile(
    r"(?:d[ée]clare\b[\s\S]{0,600}?\b(?:non[-\s]?excusable|inexcusable)\b|\best\s+(?:non[-\s]?excusable|inexcusable)\b)",
    re.IGNORECASE
)

RX_EXCUSABLE = re.compile(
    r"(?:d[ée]clare\b[\s\S]{0,600}?\bexcusable\b|\best\s+excusable\b)",
    re.IGNORECASE
)

RX_RAPPORT_REVO_PLAN_PRJ = re.compile(
    r"""
    \brapporte\s+la\s+r[ée]vocation\s+du\s+plan\s+de\s+r[ée]organisation
    (?:\s+judiciaire)?  # facultatif
    """,
    flags=re.IGNORECASE | re.VERBOSE
)

RX_PROROGE_SURSIS_JUSQUA = re.compile(
    rf"""
    \b
    (?:proroge|prolonge)\s+
    le\s+sursis\s+
    jusqu[’']?au\s+
    {DATE_RX}
    """,
    re.IGNORECASE | re.VERBOSE
)





# Réforme/réformant le jugement/ordonnance/décision … puis homologue le plan de réorganisation (PRJ)
RX_REFORME_JUGEMENT_HOMOLOGUE_PRJ = re.compile(r"""
    \b
    r[ée]form(?:ant|e)\s+le\s+(?:jugement|ordonnance|d[ée]cision)\b
    .{0,400}?                              # tolère du texte entre les deux blocs
    \b(?:et\s+)?homologu(?:e|ant|é|ée)\s+  # homologue / homologuant / homologué(e)
    (?:l[’']?)?le\s+plan\s+de\s+r[ée]organisation
    (?:\s+judiciaire)?                     # "judiciaire" optionnel
    (?:\s*\(PRJ\))?                        # "(PRJ)" optionnel
""", re.IGNORECASE | re.VERBOSE | re.DOTALL)
# Motifs “acte + (quelque part une) date” → on NE récupère PAS la date,
# on tag juste la présence du motif
# Levée simple
PAT_LEVEE_SIMPLE = re.compile(
    r"lev[ée]e\s+de\s+la\s+mesure(?:\s+de\s+protection)?",
    re.IGNORECASE
)
PAT_LEVEE         = re.compile(rf"lev[ée]e\s+de\s+la\s+mesure(?:\s+de\s+protection)?[^.,:\n]{{0,80}}{DATE_OPT}[^.\n]{{0,50}}\(RG", re.IGNORECASE)
PAT_REFORME_NEANT = re.compile(rf"réforme\s+et\s+met\s+à\s+néant\s+la\s+d[ée]cision{DATE_OPT}(?:,\s+du\s+juge\s+de\s+paix)?", re.IGNORECASE)
PAT_MET_NEANT     = re.compile(rf"\bmet\s+à\s+néant\s+la\s+d[ée]cision{DATE_OPT}", re.IGNORECASE)
PAT_REFORME_ORD   = re.compile(rf"réforme\s+l[’']?ordonnance{DATE_OPT}", re.IGNORECASE)
PAT_REGIME_REP    = re.compile(rf"sous\s+un\s+régime\s+de\s+représentation\s+par\s+ordonnance{DATE_OPT}", re.IGNORECASE)
PAT_DECHARGE_MISSION = re.compile(
    r"\bd[ée]charg(?:é(?:e|es|s)?|er)?\s+(?:[^.\n]{0,120})?\bde\s+(?:sa|la)\s+mission\s+(?:d['’]|de\s+)(?P<fonction>curateur|liquidateur|administrateur(?:\s+[a-zà-öø-ÿ'’\-]{1,20}){0,6})",
    flags=re.IGNORECASE
)
PAT_ARTICLE_CC = re.compile(
    r"art(?:\.|icl[ée])?s?\s+\d{1,4}(?:/\d{1,3})?(?:-\d+)?\s*(?:d['’]?(?:u|la)?)?\s+(?:code\s+civil|c\.\s*civ(?:il)?)",
    re.IGNORECASE
)




def detect_courappel_keywords(texte_brut, extra_keywords):
    """Ajoute des tags normalisés en fonction des motifs détectés (aucune extraction de date)."""

    def add(tag: str):
        if tag not in extra_keywords:
            extra_keywords.append(tag)

    # ── Thèmes principaux
    for m in RX_SUCC.finditer(texte_brut):
        add("succession")
        if m.group("vac"):
            add("succession_vacante")
        if m.group("desh"):
            add("succession_deshérence")


    for m in RX_ABSENCE.finditer(texte_brut):
        if m.group("presum"):
            add("presume_absent")
        if m.group("presomp"):
            add("presomption_absence")

    if PAT_REFORME_NEANT.search(texte_brut): add("reforme_mise_a_neant")
    if RX_RAPPORTE_FAILLITE.search(texte_brut): extra_keywords.append("rapporte_faillite")
    if RX_RAPPORTE_FAILLITE_DE.search(texte_brut): extra_keywords.append("rapporte_faillite")
    if RX_REFORME_ORD.search(texte_brut): add("reforme_ordonnance")
    if PAT_LEVEE_SIMPLE.search(texte_brut) : add("levee_mesure")
    if PAT_MET_NEANT.search(texte_brut):     add("mise_a_neant")
    if PAT_REFORME_ORD.search(texte_brut):   add("reforme_ordonnance")   # déjà couvert ci-dessus; garde pour sûreté
    if PAT_DECHARGE_MISSION.search(texte_brut):        add("fin de mission")
    if PAT_ARTICLE_CC.search(texte_brut): add("fin_mesure")
    if RX_LEVEE_OBS.search(texte_brut):   add("levee_mesure_observation")
    if RX_CLOTURE_LIQ.search(texte_brut):        add("cloture_liquidation")
    if RX_EFFACEMENT.search(texte_brut): add("effacement_dette")
    if RX_REFUS_EFFACEMENT.search(texte_brut): add("refus_effacement_dette")
    if RX_CLOTURE_REORGANISATION.search(texte_brut): add("cloture_reorganisation_judiciaire")
    if RX_OPP_APPEL_NON_AVENUE_ET_PUB_MB.search(texte_brut) : add("opposition_appel_non_avenue")
    if PAT_LEVEE.search(texte_brut):         add("levee_mesure")
    if RX_CAPABLE_BIENS_STMT.search(texte_brut): add ("est capable")
    if RX_CONDAMN.search(texte_brut):     add("condamnation")
    if RX_SANS_DOM.search(texte_brut):    add("sans_domicile_connu")
    if RX_DESIGN.search(texte_brut):      add("désignation")
    if RX_DISSOLUTION.search(texte_brut): add("dissolution_judiciaire")
    if PAT_REGIME_REP.search(texte_brut):    add("regime_representation")
    if RX_ABSENCE_DE.search(texte_brut) : add ("absent")
    if RX_DISSOLUTION_RETRACTEE.search(texte_brut) : add("rétractation dissolution")
    if RX_REFORME_JUGEMENT_HOMOLOGUE_PRJ.search(texte_brut) : add ("homologation_plan_apres_reforme")
    if RX_INTERDIT_EXPLOITATION.search(texte_brut) : add ("interdiction_exploiter")
    if RX_MISE_A_NEANT.search(texte_brut) : add ("mise_neant_jugement")
    if RX_RAPPORT_REVO_PLAN_PRJ.search(texte_brut) : add("rapporte_revocation_plan_reorganisation")
    if RX_SURSIS_MOIS_ACCORDE_A.search(texte_brut) : add("sursis")
    if RX_NON_EXCUSABLE.search(texte_brut):
        add("non_excusable")
    if RX_EXCUSABLE.search(texte_brut) and not re.search(r"\b(?:non[\s-]?|in)excusable\b", texte_brut, re.IGNORECASE):
        add("excusable")
    if RX_CONVENTION_TRANSFERT.search(texte_brut):
        add("convention_transfert")

    match_sursis = RX_SURSIS_MOIS_ACCORDE_A.search(texte_brut)
    if match_sursis:
        mois = normalize_mois(match_sursis.group('duree'))
        add(f"sursis_accordé_{mois}_mois")
    # --- Interdictions : "interdit à … pour une durée de X ans" ---
    m_int = RX_INTERDIT_A_DUREE.search(texte_brut) or RX_INTERDICTION_DECISION.search(texte_brut)
    if m_int:
        add("interdiction")
        yrs = normalize_annees(m_int.group("annees"))
        if yrs:
            add(f"interdiction_{yrs}_ans")

        # Tag spécifique "diriger/engager une personne morale"
        if PAT_INTERDICTION_DIRIGER.search(texte_brut):
            add("interdiction_diriger_personne_morale")
    m_int = (
            RX_INTERDIT_A_DUREE.search(texte_brut)
            or RX_INTERDICTION_DECISION.search(texte_brut)
            or RX_INTERDISANT_A_DUREE.search(texte_brut)  # ← nouveau
    )
    if m_int:
        add("interdiction")
        yrs = normalize_annees(m_int.group("annees"))
        if yrs:
            add(f"interdiction_{yrs}_ans")

        if PAT_INTERDICTION_DIRIGER.search(texte_brut):
            add("interdiction_diriger_personne_morale")

    if RX_PROROGE_SURSIS_JUSQUA.search(texte_brut):
        add("prolongation_sursis")




