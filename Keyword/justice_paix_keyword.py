import re

def detect_justice_paix_keywords(texte_brut, extra_keywords):
    if re.search(r"\b[dD]ésignation\b", texte_brut, flags=re.IGNORECASE):
        extra_keywords.append("designation_justice_de_paix")
    elif re.search(r"\b[nN]omm(e|é|ée)\b", texte_brut, flags=re.IGNORECASE):
        extra_keywords.append("nomination_justice_de_paix")
    elif re.search(r"\b[rR]emplacement\b", texte_brut, flags=re.IGNORECASE):
        extra_keywords.append("remplacement_justice_de_paix")
    elif re.search(r"\b[Mm]ainlevée\b", texte_brut, flags=re.IGNORECASE):
        extra_keywords.append("mainlevée_justice_de_paix")
    elif re.search(r"\b[fF]in\s+aux\s+mesures\b", texte_brut, flags=re.IGNORECASE):
        extra_keywords.append("fin_aux_mesures_justice_de_paix")
    if re.search(r"curateur(?:\s+aux\s+meubles)?", texte_brut, flags=re.IGNORECASE):
        extra_keywords.append("curateur_aux_meubles_justice_de_paix")