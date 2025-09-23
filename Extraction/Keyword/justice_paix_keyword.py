import re

# Remarques : trois pattern détecte absence d'adresse + va falloir harmoniser
# interpretation des keywords
# A vérifier : tous utiles ?
APOST = r"[’']"  # apostrophe droite ou typographique
# =====================================================================================
#                                        COMPIL REGEX
# =====================================================================================
# ----------------------------
# SANS ADRESSE
# ----------------------------
radie_office_re = re.compile(
    r"\bradi[ée]s?\s+d['’]office\b",
    re.IGNORECASE
)

sans_adresse_domicile_connu_re = re.compile(
    r"""
    \b(
        sans\s+(adresse|domicile)\s+connue?                # ex: sans adresse connue / sans domicile connu
        |
        (adresse|domicile)\s+(inconnue?|ignor[ée]e?)       # ex: adresse inconnue / domicile ignorée
        |
        ne\s+(dispose|poss[èe]de)\s+pas\s+d['’]?(une|aucune)?\s+(adresse|domicile)\s+(connue|fixe)
        |
        dont\s+(le\s+)?(domicile|adresse)\s+est\s+(inconnue?|ignor[ée]e?)
        |
        sans\s+(adresse|domicile)\s+fixe                   # ex: sans domicile fixe / sans adresse fixe
        |
        (sans\s+domicile)                              
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)
# ----------------------------
# Avec adresse résidence
# ----------------------------
residence_re = re.compile(
    r"\b(ayant\s+sa\s+résidence\s+à|résidant(?:\s+à)?)\b",
    re.IGNORECASE
)
# ----------------------------
# Présomption d'absence
# ----------------------------
absence = re.compile(rf"""
    (?:
        # "est présumé absent", "présumée d’absence"
        (?P<presum>\bprésum[ée]?\b.{0,15}?(?:absent(?:e|es|s)?|d{APOST}?absence)\b)

      | # "présomption d'absence"
        (?P<presomp>\bprésomption\s+d{APOST}?absence\b)

    )
""", re.IGNORECASE | re.VERBOSE)

# ----------------------------
# Type décision
# ----------------------------
# ++++++
# CODE JUDICIAIRE
# ++++++
article_492_4_re = re.compile(
    r"\b(?:article|art\.)\s*492/4\b(?:\s+de\s+l[’']?ancien\s+code\s+civil)?",
    re.IGNORECASE
)
article_492_1_re = re.compile(
    r"\b(?:article|art\.)\s*492/1\b(?:\s+de\s+l[’']?ancien\s+code\s+civil)?",
    re.IGNORECASE
)
# ++++++
# pattern récurrents
# ++++++
# Formes verbales : "désigne / désigner / a été désigné(e)(s)" + (en qualité de|comme) + personne(s) de confiance [supplémentaire]
personne_confiance_verbe_re = re.compile(r"""
    \b
    désign(?:e|er|é(?:e|s)?|ent)                 # désigne / désigner / désigné(e)(s) / désignent
    (?:\s+(?:en\s+qualité\s+de|comme))?          # optionnel : "en qualité de" ou "comme"
    \s+(?:une?\s+|la\s+|des\s+)?                 # optionnel : article
    personne(?:s)?\s+de\s+confiance              # personne(s) de confiance
    (?:\s+supplémentaire|s)?                     # optionnel : "supplémentaire" ou pluriel
    \b
""", re.IGNORECASE | re.VERBOSE)

# Formes nominales : "désignation (d'/de la/des) personne(s) de confiance"
personne_confiance_nom_re = re.compile(r"""
    \b
    désignation(?:s)?\s+
    (?:d['’]|de\s+(?:la|l[’'])|des\s+)?          # d'/de la/des (optionnel)
    personne(?:s)?\s+de\s+confiance
    (?:\s+supplémentaire|s)?                      # optionnel
    \b
""", re.IGNORECASE | re.VERBOSE)

regime_representation_re = re.compile(
    r"\bplac[ée]e?\s+sous\s+(un\s+)?r[ée]gime\s+de\s+repr[ée]sentation\b.*?\bjuge\s+de\s+paix\b",
    re.IGNORECASE | re.DOTALL
)
designation_re = re.compile(r"\bdésignation\b", re.IGNORECASE)
nomination_re = re.compile(r"\bnomm(e|é|ée)\b", re.IGNORECASE)
remplacement_re = re.compile(r"\bremplacement\b", re.IGNORECASE)
mainlevee_re = re.compile(r"\bmainlevée\b", re.IGNORECASE)
fin_mesures_re = re.compile(r"\bfin\s+aux\s+mesures\b", re.IGNORECASE)
fin_mission_re = re.compile(r"\bfin\s+[aà]\s+la\s+mission\b", re.IGNORECASE)
curateur_re = re.compile(r"curateur(?:\s+aux\s+meubles)?", re.IGNORECASE)
declaration_absence_re = re.compile(
    r"\b(?:sollicit(?:e|ent)|demand(?:e|ent)|requiert|requi[èe]rent|conclu(?:t|ent)(?:\s+à)?)\s+"
    r"(?:la\s+)?d[ée]claration\s+d['’]?\s*absence\b",
    re.IGNORECASE
)

administrateur_personne_biens_re = re.compile(
    r"\ba\s+été\s+désign[ée]?\s+en\s+qualité\s+d['’]administrateur\s+de\s+(la\s+)?personne(?:\s+et\s+des?\s+biens)?",
    re.IGNORECASE
)
decharge_mission_administrateur_re = re.compile(
    r"\ba\s+été\s+d[ée]charg[ée]?\s+de\s+sa\s+mission(?:\s+"
    r"(?:d['’]administrateur|parmi\s+les\s+administrateurs?)\s+"
    r"(?:des?\s+biens|de\s+la\s+personne|des?\s+biens\s+et\s+de\s+la\s+personne|de\s+la\s+personne\s+et\s+des?\s+biens))?",
    re.IGNORECASE
)


# =====================================================================================
#                          FONCTION D EXTRACTION PRINCIPALE
# =====================================================================================
def detect_justice_paix_keywords(texte_brut, extra_keywords):
    if designation_re.search(texte_brut):
        extra_keywords.append("designation_justice_de_paix")
    if regime_representation_re.search(texte_brut):
        extra_keywords.append("mise_sous_regime_representation_justice_de_paix")
    if nomination_re.search(texte_brut):
        extra_keywords.append("nomination_justice_de_paix")
    if remplacement_re.search(texte_brut):
        extra_keywords.append("remplacement_justice_de_paix")
    if mainlevee_re.search(texte_brut):
        extra_keywords.append("mainlevée_justice_de_paix")
    if fin_mesures_re.search(texte_brut):
        extra_keywords.append("fin_aux_mesures_justice_de_paix")

    if curateur_re.search(texte_brut):
        extra_keywords.append("curateur_aux_meubles_justice_de_paix")

    if declaration_absence_re.search(texte_brut):
        extra_keywords.append("declaration_absence_justice_de_paix")
    if administrateur_personne_biens_re.search(texte_brut):
        extra_keywords.append("designation_administrateur_personne_et_biens_justice_de_paix")
    if article_492_1_re.search(texte_brut):
        extra_keywords.append("ordonnance_mesure_protection_judicaire_justice_de_paix")
    if article_492_4_re.search(texte_brut):
        extra_keywords.append("modification_mesure_protection_judicaire_justice_de_paix")
    if decharge_mission_administrateur_re.search(texte_brut):
        extra_keywords.append("decharge_administrateur_mission_justice_de_paix")
    if fin_mission_re.search(texte_brut):
        extra_keywords.append("fin_mission_justice_de_paix")
    if radie_office_re.search(texte_brut):
        extra_keywords.append("radie_d_office_justice_de_paix")
    elif sans_adresse_domicile_connu_re.search(texte_brut):
        extra_keywords.append("sans_adresse_connue_justice_de_paix")
    if residence_re.search(texte_brut):
        extra_keywords.append("residence_detectee_justice_de_paix")
    if personne_confiance_verbe_re.search(texte_brut) or personne_confiance_nom_re.search(texte_brut):
        extra_keywords.append("designation_personne_de_confiance_justice_de_paix")
    if absence.search(texte_brut):
        extra_keywords.append("absence_justice_de_paix")


