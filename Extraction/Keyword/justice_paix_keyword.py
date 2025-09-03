import re

# =====================================================================================
#                                        COMPIL REGEX
# =====================================================================================
regime_representation_re = re.compile(
    r"\bplac[ée]e?\s+sous\s+(un\s+)?r[ée]gime\s+de\s+repr[ée]sentation\b.*?\bjuge\s+de\s+paix\b",
    re.IGNORECASE | re.DOTALL
)

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
designation_re = re.compile(r"\bdésignation\b", re.IGNORECASE)
nomination_re = re.compile(r"\bnomm(e|é|ée)\b", re.IGNORECASE)
remplacement_re = re.compile(r"\bremplacement\b", re.IGNORECASE)
mainlevee_re = re.compile(r"\bmainlevée\b", re.IGNORECASE)
fin_mesures_re = re.compile(r"\bfin\s+aux\s+mesures\b", re.IGNORECASE)
fin_mission_re = re.compile(r"\bfin\s+[aà]\s+la\s+mission\b", re.IGNORECASE)

curateur_re = re.compile(r"curateur(?:\s+aux\s+meubles)?", re.IGNORECASE)
declaration_absence_re = re.compile(
    r"\b(?:sollicit(?:e|ent)|demand(?:e|ent)|requiert|requi[èe]rent|conclu(?:t|ent)(?:\s+à)?)\s+(?:la\s+)?d[ée]claration\s+d['’]?\s*absence\b",
    re.IGNORECASE
)
administrateur_personne_biens_re = re.compile(
    r"\ba\s+été\s+désign[ée]?\s+en\s+qualité\s+d['’]administrateur\s+de\s+(la\s+)?personne(?:\s+et\s+des?\s+biens)?",
    re.IGNORECASE
)
decharge_mission_administrateur_re = re.compile(
    r"\ba\s+été\s+d[ée]charg[ée]?\s+de\s+sa\s+mission(?:\s+(?:d['’]administrateur|parmi\s+les\s+administrateurs?)\s+(?:des?\s+biens|de\s+la\s+personne|des?\s+biens\s+et\s+de\s+la\s+personne|de\s+la\s+personne\s+et\s+des?\s+biens))?",
    re.IGNORECASE
)




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
