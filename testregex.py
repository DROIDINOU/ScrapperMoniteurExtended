import re

import re

text = "Tribunal de l 'entreprise francophone de Bruxelles. Dissolution judiciaire de : SRL INST-BOUW-BOULEVARD DU MIDI 25-2, 1000 BRUXELLES Numéro d'entreprise : 0746.993.832Liquidateur : 1. ME S. HUART (SOPHIE.HUART@SYBARIUS.NET) - CHAUSSEE DE WATERLOO 880, 1000 BRUXELLES"
def extract_liquidateur_nom_et_email(text):
    """
    Extrait le nom du liquidateur (ex. 'S. HUART') et l'email entre parenthèses s'il existe.
    """
    pattern = r"""
        liquidateur(?:\(s\))?         # "Liquidateur" ou "Liquidateur(s)"
        \s*:?\s*                      # Deux-points optionnels
        \d*\.?\s*                     # Numérotation type "1." (optionnelle)
        (?:me|maître|mr|mme|madame|m\.)?\s*  # Titre (optionnel)
        (?P<nom>[A-Z]\.\s*[A-ZÉÈÀÂÊÎÔÛÇ]+)   # Nom de forme "S. HUART"
        (?:\s*\((?P<email>[^\)]+)\))?        # Email éventuel entre parenthèses
    """

    match = re.search(pattern, text, flags=re.IGNORECASE | re.VERBOSE)
    if match:
        return {
            "nom": match.group("nom").strip(),
            "email": match.group("email").strip() if match.group("email") else None
        }
    return None


print(extract_liquidateur_nom_et_email(text))