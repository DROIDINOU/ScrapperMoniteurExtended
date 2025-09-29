import logging
import os
import re

def setup_logger(name="extraction", log_file="logs/extraction.log", level=logging.INFO):
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    handler = logging.FileHandler(log_file, encoding='utf-8')
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        logger.addHandler(handler)

    return logger


def setup_dynamic_logger(name="dynamic_logger", keyword="default", level=logging.DEBUG):
    safe_keyword = re.sub(r'[^\w\-_.]', '_', keyword)  # Nettoyage basique
    log_file_path = f"logs/{name}_{safe_keyword}.log"
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    handler = logging.FileHandler(log_file_path, encoding='utf-8')
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Évite d'ajouter plusieurs fois le même handler (même fichier)
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename == handler.baseFilename for h in logger.handlers):
        logger.addHandler(handler)

    return logger


# ======================
#   Classe utilitaire
# ======================
PRIORITY_REGEXES = {
    "RX_PROTECTION_INTERESSE_NE",
    "RX_PROTECTION_INTERESSE_NOM_SEUL",
    "RX_INTERDIT_A",
    "RX_LE_NOMME_NP",
    "RX_NR_NP",
    "RX_SV_ANY",
    "RX_SV_PN",
    "RX_SV_NP",
    "RX_SV_ANY",
    "RX_SV_PN",
    "RX_ADMIN_SV_SPEC",
    "RX_SV_NP",
    "RX_CURATEUR_SV_PN",
    "RX_SV_NE_LE",
    "RX_SRV_M_RN",
    "RX_SV_PART_VAC",
    "RX_SV_NE_LE",
    "RX_SV_FEU_VARIANTES",
    "RX_ADMIN_SV_VAC_ALT",
    "RX_SV_DESHERENCE_SIMPLE",
    "RX_CURATEUR_SV_NP",
    "RX_CURATEUR_SV_NP_NN",
    "match12_personne_protegee",
    "match16_regime_representation",
    "match_incapable_nom",
    "match_observation_protectrice",
    "regex_ne_a",
    "regex_ne_le",
    "RX_ADMIN_PROV_SUCC_DE",
    "RX_CONDAMNE_LE_NOMME_NP",
    "RX_CONDAMNE_LE_NOMME_PN",
    "RX_EN_CAUSE_NP",
    "RX_EN_CAUSE_PN",
    "RX_SV_PN_NN",
    "RX_QUALITE_CURATEUR_SV_PN_NN",
    "RX_QUALITE_CURATEUR_SV_PN",
    "RX_EN_CAUSE_DE_NOM",
    "RX_EN_CAUSE_ITEM_NP",
    "RX_EN_CAUSE_ITEM_NP",
    "match_condamne",
    "RX_SRV_NOMPRENOM",
    "RX_DECL_CIVILITE_NP_RRN",
    "match_succession_simple"
}


class LoggedList(list):
    _logged_docs = set()  # évite de logger deux fois le même doc_id

    def __init__(self, full_text, doc_id, logger=None):
        super().__init__()
        self.full_text = full_text
        self.doc_id = doc_id
        self._first_regex = None
        self._buffer = []  # tuples (tag, item, regex_name, contexte, start, order)
        self._order_counter = 0
        self.logger = logger
        if self.logger:
            self.logger.propagate = False

    def append(self, item, regex_name="GENERIC", m=None):
        if self._first_regex is None:
            self._first_regex = regex_name

        tag = "PRIORITAIRE" if regex_name in PRIORITY_REGEXES else "SECONDAIRE"

        contexte, start = "", None
        if m is not None:
            try:
                # m doit être un match (finditer), pas la liste renvoyée par findall
                start, end = m.start(), m.end()
                contexte = self.full_text[max(0, start-50): end+50]
            except Exception:
                pass

        self._buffer.append((tag, item, regex_name, contexte, start, self._order_counter))
        self._order_counter += 1

        super().append(item)

    def first_is_priority(self):
        return self._first_regex in PRIORITY_REGEXES

    def flush(self):
        if not self.logger:
            self._buffer.clear()
            return

        # Déjà loggé pour ce doc ?
        if self.doc_id in LoggedList._logged_docs:
            self._buffer.clear()
            return

        # S'il y a un prioritaire quelque part, on ne log rien (comme voulu)
        if any(tag == "PRIORITAIRE" for tag, *_ in self._buffer):
            self._buffer.clear()
            return

        # Candidats secondaires uniquement
        secondaires = [t for t in self._buffer if t[0] == "SECONDAIRE"]
        if not secondaires:
            self._buffer.clear()
            return

        # Choisir le "meilleur" secondaire :
        # 1) regex spécifique d'abord (regex_name != "GENERIC")
        # 2) item le plus long (souvent plus informatif)
        # 3) premier dans l'ordre d’apparition
        def key(t):
            tag, item, regex_name, contexte, start, order = t
            return (regex_name == "GENERIC", -len(item), order)

        best = sorted(secondaires, key=key)[0]
        _, item, regex_name, contexte, _, _ = best

        # Logger une seule ligne pour ce doc_id
        self.logger.info(
            f"[{self.doc_id}] SECONDAIRE: {item} (regex={regex_name}) | …{contexte}…"
        )
        LoggedList._logged_docs.add(self.doc_id)

        self._buffer.clear()
