import logging
import os

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


def setup_fallback3_logger(name="fallback3", log_file="logs/fallback3.log", level=logging.DEBUG):
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
    log_file_path = f"logs/{keyword}.log"
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
