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
    "RX_SV_NOM_COMPLET_VIRG",
    "RX_SRV_SIMPLE",
    "RX_SRV_NP",
    "RX_SV_PN",
    "RX_ADMIN_SV_SPEC"
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
    "RX_SV_NOM_VIRG_PRENOMS",
    "match12_personne_protegee",
    "match16_regime_representation",
    "match_incapable_nom",
    "match_observation_protectrice",
    "regex_ne_a",
    "regex_ne_le",
}


class LoggedList(list):
    def __init__(self, full_text, doc_id, logger=None):
        super().__init__()
        self.full_text = full_text
        self.doc_id = doc_id
        self._first_regex = None
        self._events = []
        self._buffer = []
        self.logger = logger  # None par défaut => aucun log

        # Si un logger est fourni, on évite toute remontée vers le root
        if self.logger:
            self.logger.propagate = False

    def append(self, item, regex_name="GENERIC", m=None):
        if self._first_regex is None:
            self._first_regex = regex_name

        tag = "PRIORITAIRE" if regex_name in PRIORITY_REGEXES else "SECONDAIRE"
        contexte = ""
        start = end = None
        if m:
            try:
                start, end = m.start(), m.end()
                contexte = self.full_text[max(0, start-50): end+50]
            except Exception:
                pass

        # ⚠️ On ne log pas ici : on bufferise seulement
        self._buffer.append((tag, item, regex_name, contexte))
        self._events.append((regex_name, item, start, end))

        # La liste reste une simple liste de chaînes
        super().append(item)

    def first_is_priority(self):
        return self._first_regex in PRIORITY_REGEXES

    def flush(self):
        """Écrit les logs uniquement si:
           - un logger a été fourni
           - le 1er match n'est PAS prioritaire
        """
        if not self.logger or self.first_is_priority():
            self._buffer.clear()
            return

        for tag, item, regex_name, contexte in self._buffer:
            self.logger.info(
                f"[{self.doc_id}] {tag}: {item} (regex={regex_name}) | …{contexte}…"
            )
        self._buffer.clear()
