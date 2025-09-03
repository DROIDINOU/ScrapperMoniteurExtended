import re
import logging
from typing import List, Tuple

loggeridentifiant_terrorisme = logging.getLogger("nomsterrorisme_logger")
logged_identifiant_terrorisme = set()  # mémorise (doc_id, nrn)

# 1) Avec numéro : "1. NOM PRÉNOM (NRN 06.03.04-221.29)"
RX_NUM = re.compile(r"""
    \b(\d+)\s*[,\.]\s*
    ([A-ZÀ-ÖØ-Ý'’\-\s]+?)\s*\(
    \s*NRN\s*:?\s*(\d{2}\.\d{2}\.\d{2}-\d{3}\.\d{2})\s*\)
""", re.IGNORECASE | re.VERBOSE)

# 2) Sans numéro : "NOM PRÉNOM (NRN 06.03.04-221.29)"
RX_NONUM = re.compile(r"""
    ([A-ZÀ-ÖØ-Ý'’\-\s]+?)\s*\(
    \s*NRN\s*:?\s*(\d{2}\.\d{2}\.\d{2}-\d{3}\.\d{2})\s*\)
""", re.IGNORECASE | re.VERBOSE)

def _norm_nom(n: str) -> str:
    return re.sub(r"\s+", " ", n or "").strip()

def extraire_personnes_terrorisme(texte: str, doc_id: str) -> List[Tuple[str, str, str]]:
    """
    Retourne [(num, nom, nrn)] SANS DOUBLONS sur (nom, nrn).
    """
    out: List[Tuple[str, str, str]] = []
    seen_pairs = set()  # (NOM_UPPER, NRN)

    # 1) Avec numéro
    for num, nom, nrn in RX_NUM.findall(texte):
        nom_norm = _norm_nom(nom)
        key = (nom_norm.upper(), nrn.strip())
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        out.append((num.strip(), nom_norm, nrn.strip()))

    # 2) Sans numéro → on poursuit la numérotation
    next_num = (max((int(n) for n, _, _ in out), default=0) + 1)
    for nom, nrn in RX_NONUM.findall(texte):
        nom_norm = _norm_nom(nom)
        key = (nom_norm.upper(), nrn.strip())
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        out.append((str(next_num), nom_norm, nrn.strip()))
        next_num += 1

    # Logging idempotent par (doc_id, nrn)
    print(f"bon c est quoi out ? :{out}")
    for (num, nom, nrn) in out:
        log_key = (doc_id)
        if log_key in logged_identifiant_terrorisme:
            continue
        logged_identifiant_terrorisme.add(log_key)
        loggeridentifiant_terrorisme.warning(
            f"DOC ID: '{doc_id}'\n"
            f"Personne listée (terrorisme): '{out}'\n"
            f"Texte : '{texte} "
        )

    return out
