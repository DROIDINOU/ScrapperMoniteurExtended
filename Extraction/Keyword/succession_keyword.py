import re



def detect_succession_keywords(texte_brut: str, extra_keywords):

    if re.search(r"\bdéshérence", texte_brut, flags=re.IGNORECASE):
        extra_keywords.append("déshérence")
    elif re.search(r"\bacceptation\s+sous\s+bénéfice\s+d['’]inventaire", texte_brut, flags=re.IGNORECASE):
        extra_keywords.append("acceptation_sous_benefice_inventaire")
