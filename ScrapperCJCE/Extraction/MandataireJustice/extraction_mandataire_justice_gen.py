import unicodedata
import csv
import re
import os


def _norm_ws(t: str) -> str:
    """Aplatit juste les espaces (sans NFKC)."""
    return re.sub(r"\s+", " ", t).strip()


# ─────────────────────────────
# Fallback regex
# ─────────────────────────────
# verifier si on a pas casser qq chose
"""RE_AVOCAT = re.compile(
    r"(?i)"
    r"(?:ma[îi]tre|me)?\s*"
    r"(?P<nom>[A-ZÉÈÀÂÊÎÔÛÇ][a-zà-öø-ÿ'’-]+"
    r"(?:\s+[A-ZÉÈÀÂÊÎÔÛÇ][a-zà-öø-ÿ'’-]+"
    r"|\s+[A-ZÉÈÀÂÊÎÔÛÇ-]{2,}){1,3})"
    r"\s*,?\s*avocat(?:e)?\b\s*,?"
)"""

RE_AVOCAT = re.compile(
    r"""(?ix)               # i=ignorecase, x=verbose pour lisibilité
    (?:ma[îi]tre|me)?\s*
    (?P<nom>
        (?:[A-ZÉÈÀÂÊÎÔÛÇ][a-zà-öø-ÿ'’\-]+|[A-ZÉÈÀÂÊÎÔÛÇ\-]{2,})
        (?:\s+|,\s*)
        (?:[A-ZÉÈÀÂÊÎÔÛÇ][a-zà-öø-ÿ'’\-]+|[A-ZÉÈÀÂÊÎÔÛÇ\-]{2,})
        (?:
            (?:\s+|,\s*)
            (?:[A-ZÉÈÀÂÊÎÔÛÇ][a-zà-öø-ÿ'’\-]+|[A-ZÉÈÀÂÊÎÔÛÇ\-]{2,})
        ){0,2}
    )
    \s*,?\s*avocat(?:e)?\b
    """,
    re.VERBOSE
)



RE_CABINET = re.compile(
    r"(?i)"
    r"(?P<nom>[A-ZÉÈÀÂÊÎÔÛÇ][a-zà-öø-ÿ'’-]+"
    r"(?:\s+[A-ZÉÈÀÂÊÎÔÛÇ][a-zà-öø-ÿ'’-]+"
    r"|\s+[A-ZÉÈÀÂÊÎÔÛÇ-]{2,}){1,3})"
    r"\s*,?\s*dont\s+(?:le\s+cabinet|les\s+bureaux)\s+(?:est|sont)\s+(?:sis|établis?)"
)

# RE_ADMIN corrigé pour récupérer toutes les occurrences sans avaler trop loin
RE_ADMIN = re.compile(
    # 1) le NOM (⚠️ pas d'IGNORECASE ici)
    r"(?P<nom>[A-ZÉÈÀÂÊÎÔÛÇ][a-zà-öø-ÿ'’-]+"
    r"(?:\s+(?:[A-ZÉÈÀÂÊÎÔÛÇ][a-zà-öø-ÿ'’-]+|[A-ZÉÈÀÂÊÎÔÛÇ-]{2,})){1,3})"
    # 2) micro-fenêtre optionnelle : pas de majuscule (évite d'avaler un autre nom)
    r"(?:\s*,?[^A-ZÉÈÀÂÊÎÔÛÇ]{0,70}?)?"
    # 3) la formule "a été désigné ..." (en IGNORECASE uniquement ici)
    r"(?i:\ba\s+été\s+d[ée]sign[ée]\s+en\s+qualit[ée]\s+d['’]administrateur(?:trice)?)"
)


def _extract_with_regex(text: str, pattern: re.Pattern) -> list[str]:
    txt = _norm_ws(text)
    out, seen = [], set()
    for m in pattern.finditer(txt):
        nom = re.sub(r"\s+", " ", m.group("nom").strip(" ,.;:()[]{}—–-"))
        if nom and nom not in seen:
            seen.add(nom)
            out.append(nom)
    return out


def extract_names_avocat(text: str) -> list[str]:
    return _extract_with_regex(text, RE_AVOCAT)


def extract_names_cabinet(text: str) -> list[str]:
    return _extract_with_regex(text, RE_CABINET)


def extract_names_admin(text: str) -> list[str]:
    return _extract_with_regex(text, RE_ADMIN)


# ─────────────────────────────
# Normalisation noms & variantes CSV
# ─────────────────────────────
def normaliser_nom(nom: str) -> str:
    nfkd_form = unicodedata.normalize('NFKD', nom)
    sans_accents = "".join(c for c in nfkd_form if not unicodedata.combining(c))
    nettoye = sans_accents.replace("'", "").replace(".", "").lower()
    return " ".join(nettoye.split())


def variantes_nom(nom: str) -> set:
    variantes = set()
    nom_norm = normaliser_nom(nom)
    variantes.add(nom_norm)

    parts = nom_norm.split()
    if len(parts) == 2:
        variantes.add(f"{parts[1]} {parts[0]}")
    if len(parts) > 2:
        variantes.add(f"{' '.join(parts[1:])} {parts[0]}")
    particules = {"de", "du", "la", "le", "van", "von", "der"}
    variantes.add(" ".join(p for p in parts if p not in particules))
    return variantes


# ─────────────────────────────
# Nettoyage libellés (Maître / par Maître)
# ─────────────────────────────
def nettoyer_prefixes_maitre(nom: str) -> str:
    """Retire 'Maître' ou 'par Maître' au début, normalise espaces/ponctuation."""
    nom2 = re.sub(r"(?i)^(?:par\s+)?ma[îi]tre\s+", "", nom)
    nom2 = re.sub(r"\s+", " ", nom2).strip(" ,.;:()[]{}—–-")
    return nom2


# ─────────────────────────────
# Fonction principale — OPTION A élargie
# ─────────────────────────────
def trouver_personne_dans_texte(texte: str, chemin_csv: str, mots_clefs: list) -> list[str]:
    texte_norm = normaliser_nom(_norm_ws(texte))
    mots_norm = [normaliser_nom(m.replace("+", " ")) for m in mots_clefs]
    trouves = set()

    noms_csv = []
    if os.path.exists(chemin_csv):
        with open(chemin_csv, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            noms_csv = [row["nom"].strip() for row in reader]

        # 1) recherche sur mots-clés ±80 caractères
        for mot_clef_norm in mots_norm:
            for m in re.finditer(re.escape(mot_clef_norm), texte_norm):
                pos = m.start()
                fenetre = texte_norm[max(0, pos - 300): pos + 300]
                for nom in noms_csv:
                    for variante in variantes_nom(nom):
                        if variante and variante in fenetre:
                            trouves.add(nom)
                            break
    else:
        print(" Fichier CSV introuvable.")

    # Si trouvé via CSV → on renvoie (on NE nettoie PAS, on suppose le CSV propre)
    if trouves:
        return sorted(trouves)

    # 2) Fallback indépendant : avocat + cabinet + administrateur
    candidats = (
        extract_names_avocat(texte)
        + extract_names_cabinet(texte)
        + extract_names_admin(texte)
    )

    # 🔹 Nettoyage 'Maître' / 'par Maître' + normalisation
    propres = []
    seen = set()
    for c in candidats:
        c2 = nettoyer_prefixes_maitre(c)
        if c2 and c2 not in seen:
            seen.add(c2)
            propres.append(c2)

    # Retourne les regex fallback avec un "role" pour les différencier
    return [{"nom": n, "role": "regex-fallback", "raw": n} for n in sorted(propres)]
