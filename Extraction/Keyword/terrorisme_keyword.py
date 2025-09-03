import re

PATTERN_PERSONNES_A_SUPPR = r"\bpersonnes?\s+(?:a|à)\s+supprimer\b\s*:?"


def add_tag_personnes_a_supprimer(texte_brut: str, extra_keywords):
    """
    Regarde si 'personnes à supprimer' apparaît dans texte_brut.
    Si oui, ajoute 'personnes à supprimer' à extra_keywords.
    Retourne la liste (ou None si rien).
    """

    if re.search(PATTERN_PERSONNES_A_SUPPR, texte_brut, flags=re.IGNORECASE):
        extra_keywords.append("personnes à supprimer")
    else:
        extra_keywords.append("personnes a ajouter")

