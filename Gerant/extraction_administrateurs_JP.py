import unicodedata
import csv
import re
import os


def normaliser_nom(nom: str) -> str:
    """Supprime accents, met en minuscule, retire espaces en double, etc."""
    # Supprimer les accents
    nfkd_form = unicodedata.normalize('NFKD', nom)
    sans_accents = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Retirer apostrophes, points, majuscules, etc.
    nettoyé = sans_accents.replace("'", "").replace(".", "").lower()
    # Supprimer les espaces multiples
    return " ".join(nettoyé.split())

def variantes_nom(nom: str) -> set:
    """Génère les variantes typiques d’un nom : inversé, simplifié, etc."""
    variantes = set()
    nom_norm = normaliser_nom(nom)

    variantes.add(nom_norm)

    # Si prénom NOM, générer NOM prénom
    parts = nom_norm.split()
    if len(parts) == 2:
        inversé = f"{parts[1]} {parts[0]}"
        variantes.add(inversé)
    if len(parts) > 2:
        inversé = f"{' '.join(parts[1:])} {parts[0]}"
        variantes.add(inversé)

    # Supprimer particules (de, van, etc.)
    particules = {"de", "du", "la", "le", "van", "von", "der"}
    sans_part = " ".join([p for p in parts if p not in particules])
    variantes.add(sans_part)

    return variantes

def trouver_curateur_dans_texte(texte: str, chemin_csv: str) -> list:
    """Cherche si un curateur est mentionné dans une fenêtre ±80 autour du mot 'curateur'."""
    if not os.path.exists(chemin_csv):
        print("❌ Fichier CSV introuvable.")
        return []

    with open(chemin_csv, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        noms = [row["nom"].strip() for row in reader]

    texte_norm = normaliser_nom(texte)
    matches = [m.start() for m in re.finditer(r"curateur", texte_norm)]

    trouvés = set()

    for pos in matches:
        fenêtre = texte_norm[max(0, pos - 80): pos + 80]
        for nom in noms:
            for variante in variantes_nom(nom):
                if variante in fenêtre:
                    trouvés.add(nom)
                    break  # Si une variante matche, inutile de tester les autres

    return sorted(trouvés)
