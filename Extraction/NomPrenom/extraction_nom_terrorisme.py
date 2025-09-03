import re
from typing import List, Tuple

def extraire_personnes_terrorisme(texte: str) -> List[Tuple[str, str]]:
    """
    Extrait les noms + NRN des listes liées au terrorisme.
    Utilise deux patterns :
      - ton motif original (plus permissif, avec 'NRN:')
      - un motif spécifique plus robuste
    Retourne une liste [(nom, nrn), ...]
    """
    results = []

    # 🔹 Ton motif original (tolère "NRN:" uniquement)
    pattern1 = re.compile(
        r"(\d+)[,\.]\s*([A-Za-z\s]+)\s*\(NRN:\s*(\d{2}\.\d{2}\.\d{2}-\d{3}\.\d{2})\)",
        flags=re.IGNORECASE
    )
    for _, name, nn in pattern1.findall(texte):
        results.append((name.strip(), nn.strip()))

    # 🔹 Motif amélioré (accepte 'NRN' avec ou sans ':', et borne mieux les noms)
    pattern2 = re.compile(
        r"""
        \b(\d+)              # numéro d'item (1, 2, 3…)
        [\.,]\s*             # séparateur
        (?P<nom>[A-ZÀ-ÖØ-Ý'\- ]+?)  # nom en majuscules
        \s*\(NRN\s*:?\s*     # NRN avec ':' optionnel
        (?P<nrn>\d{2}\.\d{2}\.\d{2}-\d{3}\.\d{2})
        \)                   # parenthèse fermante
        """,
        flags=re.VERBOSE
    )
    for _, nom, nrn in pattern2.findall(texte):
        results.append((nom.strip(), nrn.strip()))

    # 🔹 Dédoublonnage si nécessaire
    results = list(dict.fromkeys(results))

    return results
