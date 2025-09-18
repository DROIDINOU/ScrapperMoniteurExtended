import re


# Fonction de nettoyage à appliquer aux noms trouvés
def nettoyer_nom(nom):
    parasites = [
        "d'exploiter", "d’exploiter", "exploiter",
        "d'exercer", "d’exercer", "exercer",
        "diriger", "gérer", "administrer", "constituer",
        "créer", "entreprendre", "reprendre"
    ]
    nom_lower = nom.lower()
    for parasite in parasites:
        if parasite in nom_lower:
            index = nom_lower.index(parasite)
            nom = nom[:index].strip()
            break
    return nom.strip()

# Ta fonction principale conservée
def extraire_personnes_interdites(texte):
    """
    Extrait les noms de personnes physiques visées par une interdiction,
    via :
    - "interdiction à Monsieur NOM pour une durée de N ans"
    - "interdit à NOM pour une durée de N ans"
    Retourne une liste de noms (sans doublons, sans durée)
    """

    personnes_trouvees = []

    # Pattern 1 : interdiction à Monsieur NOM...
    pattern_1 = (
        r"(?:fait\s+)?interdiction\s+à\s+(?:Monsieur|Madame|Mr|Mme)?\s*"
        r"([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+){1,4})"
        r"\s+pour\s+une\s+durée\s+de\s+(?:10|[1-9])\s+ans?"
    )

    for match in re.findall(pattern_1, texte, flags=re.IGNORECASE):
        nom = nettoyer_nom(match.strip())
        personnes_trouvees.append(nom)

    # Pattern 2 : interdit à NOM avec 3 mots
    pattern_3mots = (
        r"interdit\s+à\s+([A-ZÉÈÊÀÂ\-']+\s+[A-ZÉÈÊÀÂ\-']+\s+[A-ZÉÈÊÀÂ\-']+)"
        r"\s+.*?\s+pour\s+une\s+durée\s+de\s+(?:10|[1-9])\s+ans?"
    )
    for match in re.findall(pattern_3mots, texte, flags=re.IGNORECASE):
        nom = nettoyer_nom(match.strip())
        personnes_trouvees.append(nom)

    # Pattern 3 : interdit à NOM avec 4 mots
    pattern_4mots = (
        r"interdit\s+à\s+([A-ZÉÈÊÀÂ\-']+\s+[A-ZÉÈÊÀÂ\-']+\s+[A-ZÉÈÊÀÂ\-']+\s+[A-ZÉÈÊÀÂ\-']+)"
        r"\s+.*?\s+pour\s+une\s+durée\s+de\s+(?:10|[1-9])\s+ans?"
    )
    for match in re.findall(pattern_4mots, texte, flags=re.IGNORECASE):
        nom = nettoyer_nom(match.strip())
        personnes_trouvees.append(nom)

    # Suppression des doublons
    personnes_uniques = list(set(personnes_trouvees))

    for nom in personnes_uniques:
        print(f"✅ {nom}")

    return personnes_uniques
