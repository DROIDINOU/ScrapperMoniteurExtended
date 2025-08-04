import logging
from logger_config import setup_logger, setup_fallback3_logger  # adapte le chemin selon ton projet
logger = setup_logger("extraction", level=logging.DEBUG)  # 👈 nom unique et explicite
logger.debug("✅ Logger initialisé dans le script principal.")
loggerfallback3 = setup_fallback3_logger("fallback3", level=logging.DEBUG)  # 👈 nom unique et explicite
loggerfallback3.debug("✅ Logger initialisé dans le script principal.")
print(">>> CODE À JOUR")
from extraction_noms import extract_name_before_birth
from extract_adresses_entreprises import extract_add_entreprises
from extraction_adresses_moniteur import extract_address
from extraction_nom_entreprises import extract_noms_entreprises
from extraction_administrateurs import extract_administrateur
import concurrent.futures
import re
import time
from datetime import date, datetime
from bs4 import BeautifulSoup, NavigableString, Tag
import requests
import locale
from tqdm import tqdm
import meilisearch
import sys
import psycopg2
from psycopg2.extras import Json
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, urljoin
import hashlib
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import tempfile
import os
from collections import defaultdict
import unicodedata
import json







assert len(sys.argv) == 2, "Usage: python testMoniteurB.py \"mot+clef\""
keyword = sys.argv[1]

# a JOUR 1/8/2025
from_date = date.fromisoformat("2025-07-01")
to_date ="2025-07-09"  #date.today()
BASE_URL = "https://www.ejustice.just.fgov.be/cgi/"

locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

VILLE_TRIBUNAUX = [
    "Bruxelles", "Charleroi", "Mons", "Namur", "Liège", "Huy",
    "Tournai", "Neufchâteau", "Marche-en-Famenne", "Arlon", "Dinant", "Eupen", "Nivelles", "Verviers"
]

escaped_villes = [re.escape(v) for v in VILLE_TRIBUNAUX]

# Joindre avec |
villes = "|".join(escaped_villes)

def generate_doc_id_from_metadata(url, date_doc):
    base = f"{url.strip()}|{date_doc.strip()}"
    return hashlib.md5(base.encode()).hexdigest()

def extract_date_after_rendu_par(texte_brut):
    jour_map = {
        'premier': 1, 'un': 1, 'deux': 2, 'trois': 3, 'quatre': 4, 'cinq': 5, 'six': 6,
        'sept': 7, 'huit': 8, 'neuf': 9, 'dix': 10, 'onze': 11, 'douze': 12, 'treize': 13,
        'quatorze': 14, 'quinze': 15, 'seize': 16, 'dix-sept': 17, 'dix-huit': 18,
        'dix-neuf': 19, 'vingt': 20, 'vingt-et-un': 21, 'vingt-deux': 22, 'vingt-trois': 23,
        'vingt-quatre': 24, 'vingt-cinq': 25, 'vingt-six': 26, 'vingt-sept': 27,
        'vingt-huit': 28, 'vingt-neuf': 29, 'trente': 30, 'trente-et-un': 31
    }

    mois_map = {
        'janvier': '01', 'février': '02', 'mars': '03', 'avril': '04',
        'mai': '05', 'juin': '06', 'juillet': '07', 'août': '08',
        'septembre': '09', 'octobre': '10', 'novembre': '11', 'décembre': '12'
    }

    annee_map = {
        'deux mille vingt': '2020',
        'deux mille vingt et un': '2021',
        'deux mille vingt deux': '2022',
        'deux mille vingt trois': '2023',
        'deux mille vingt quatre': '2024',
        'deux mille vingt cinq': '2025',
        'deux mille vingt six': '2026'
    }

    # 1️⃣ Format écrit en lettres
    match_lettres = re.search(
        r"le\s+(" + "|".join(jour_map.keys()) + r")\s+(" + "|".join(
            mois_map.keys()) + r")\s+((?:deux\s+mille(?:[\s\-]\w+){0,2}))",
        texte_brut,
        flags=re.IGNORECASE
    )
    if match_lettres:
        jour_txt = match_lettres.group(1).lower()
        mois_txt = match_lettres.group(2).lower()
        annee_txt = match_lettres.group(3).lower().replace("-", " ").strip()

        jour = jour_map.get(jour_txt)
        mois = mois_map.get(mois_txt)
        annee = annee_map.get(annee_txt)

        if jour and mois and annee:
            return f"{annee}-{mois}-{int(jour):02d}"

    # 2️⃣ Format numérique classique : 18/12/2024, 18-12-2024, 18.12.2024
    match_numeric = re.search(r"\b(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})\b", texte_brut)
    if match_numeric:
        jour, mois, annee = match_numeric.groups()
        if len(annee) == 2:
            annee = f"20{annee}"  # suppose 21e siècle
        return f"{annee}-{int(mois):02d}-{int(jour):02d}"

    # 3️⃣ Format ISO : 2024-12-18, 2024/12/18, etc.
    match_iso = re.search(r"\b(\d{4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,2})\b", texte_brut)
    if match_iso:
        annee, mois, jour = match_iso.groups()
        return f"{annee}-{int(mois):02d}-{int(jour):02d}"

    return None

def get_month_name(month_num):
    mois = [
        "", "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"
    ]
    return mois[month_num] if 1 <= month_num <= 12 else ""

def detect_erratum(texte_html):
    """
    Retourne True si 'erratum', 'errata' ou 'ordonnance rectificative' est détecté
    dans les 400 premiers caractères du texte HTML. Sinon False.
    """
    soup = BeautifulSoup(texte_html, 'html.parser')
    full_text = soup.get_text(separator=" ").strip().lower()
    snippet = full_text[:400]

    if re.search(r"\berrat(?:um|a)\b", snippet):
        return True

    if re.search(r"\bordonnance\s+rectificative\b", snippet):
        return True

    return False


def extract_uppercase_sequences(text: str) -> list[str]:
    """
    Extrait des séquences de mots en majuscules (avec ou sans chiffres),
    en s'arrêtant sur les débuts d'adresse (Rue, Avenue, etc.).
    """

    def is_address_start(word: str) -> bool:
        address_words = {
            "rue", "avenue", "impasse", "chemin", "place", "boulevard", "square",
            "allee", "cour", "chaussée", "drève", "clos", "sentier", "ry", "drève"
        }
        return word.lower() in address_words

    text = strip_html_tags(text)
    text = re.sub(r'\s+', ' ', text)

    words = text.split()
    result = []
    current_sequence = []

    for word in words:
        clean_word = re.sub(r"[^\w’'-]", "", word)

        if is_address_start(clean_word):
            break

        # Cas 1 : mot strictement en majuscules sans chiffres (regex standard)
        if re.fullmatch(r"[A-ZÉÈÊÀÂÙÛÎÏÔÇ]{2,}", clean_word):
            current_sequence.append(clean_word)

        # Cas 2 : mot en majuscules + chiffres + tirets/apostrophes
        elif re.fullmatch(r"[A-Z0-9ÉÈÊÀÂÙÛÎÏÔÇ’'-]{2,}", clean_word):
            result.append(clean_word)

        elif current_sequence:
            result.append(" ".join(current_sequence))
            current_sequence = []

    if current_sequence:
        result.append(" ".join(current_sequence))

    # Supprimer doublons tout en gardant l’ordre
    seen = set()
    return [s for s in result if not (s in seen or seen.add(s))]


def extract_justice_de_paix_jugement_date(text):
    """
    Extrait la date du jugement pour un document mentionnant 'Justice de Paix'.
    Exemple attendu : "Par ordonnance du 9 juillet 2025 du juge de paix du..."
    """
    # Normalisation des caractères potentiellement mal encodés
    text = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")

    match_date = re.search(r"[Pp]ar\s+ordonnance\s+du\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})", text)
    if match_date:
        print(match_date.group(1).strip())
        return match_date.group(1).strip()

    return None


def extract_numero_tva(text: str, format_output: bool = False) -> list[str]:
    """
    Extrait les numéros de TVA belges valides (10 chiffres), avec ou sans séparateurs.
    Exemples détectés : 1008.529.190, 0108 529 190, 0423456789, 05427-15196, etc.

    Args:
        text (str): Texte brut contenant des numéros
        format_output (bool): Si True → format 'XXXX.XXX.XXX', sinon 'XXXXXXXXXX'

    Returns:
        list[str]: Liste de TVA détectées
    """
    import re

    text = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")

    # Liste des résultats
    tvas = []

    # 🔹 1. Format standard 4+3+3 (avec espace, point, tiret ou rien)
    pattern_4_3_3 = r"\b(\d{4})[\s.\-]?(\d{3})[\s.\-]?(\d{3})\b"
    matches = re.findall(pattern_4_3_3, text)
    for a, b, c in matches:
        raw = f"{a}{b}{c}"
        if len(raw) == 10 and raw.isdigit():
            tvas.append(f"{raw[:4]}.{raw[4:7]}.{raw[7:]}" if format_output else raw)

    # 🔹 2. Format alternatif : 5 + 5 chiffres (souvent avec tiret)
    pattern_5_5 = r"\b(\d{5})[\s.\-]?(\d{5})\b"
    matches_alt = re.findall(pattern_5_5, text)
    for a, b in matches_alt:
        raw = f"{a}{b}"
        if len(raw) == 10 and raw.isdigit():
            tvas.append(f"{raw[:4]}.{raw[4:7]}.{raw[7:]}" if format_output else raw)

    # 🔁 Supprime les doublons tout en conservant l’ordre
    seen = set()
    return [x for x in tvas if not (x in seen or seen.add(x))]


r"""def extract_numero_tva(text: str, format_output: bool = False) -> list[str]:
    Extrait les numéros de TVA belges valides (10 chiffres), avec ou sans séparateurs.
    Exemples détectés : 1008.529.190, 0108 529 190, 0423456789, etc.

    Args:
        text (str): Texte brut contenant des numéros
        format_output (bool): Si True → format 'XXXX.XXX.XXX', sinon 'XXXXXXXXXX'

    Returns:
        list[str]: Liste de TVA détectées
    text = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")

    # Matche exactement 10 chiffres, divisés en 4 + 3 + 3
    pattern = r"\b(\d{4})[\s.\-]?(\d{3})[\s.\-]?(\d{3})\b"
    matches = re.findall(pattern, text)

    tvas = []
    for a, b, c in matches:
        raw = f"{a}{b}{c}"
        if len(raw) == 10 and raw.isdigit():
            tvas.append(f"{raw[:4]}.{raw[4:7]}.{raw[7:]}" if format_output else raw)

    return tvas"""

r"""
def extract_name_before_birth(texte_html):
    soup = BeautifulSoup(texte_html, 'html.parser')
    nom_list = []
    # Cherche toutes les balises <br>
    for br in soup.find_all('br'):
        text = br.previous_element.strip() if isinstance(br.previous_element, str) else ''

        if text:
            match = re.search(r"(.*?)\s*(né|née|,né|,née|né\(e\))\s*à", text, re.IGNORECASE)
            if match:
                nom_list.append(match.group(1).strip())
            match_bis = re.search(r"([A-Za-z\s]+),\s*(né\(e\)?|née)\s*le\s*(\d{4}-\d{2}-\d{2})\s*à\s*([A-Za-z\s]+)", text, re.IGNORECASE)
            if match_bis:
                nom_list.append(match_bis.group(1).strip())
            match_ter = re.search(r"([A-Za-z\s]+),\s*(né\(e\)?|née)\s*le\s*(\d{4}-\d{2}-\d{2})\s*à\s*([A-Za-z\s]+)", text, re.IGNORECASE)
            if match_ter:
                nom_list.append(match_ter.group(1).strip())

    return nom_list
    """
def remove_footer_metadata(text):
    """
    Supprime les liens bas de page du Moniteur belge (PDF, copier le lien, haut de page…).
    """
    return re.sub(
        r"Liens\s*:\s*https://www\.ejustice\.just\.fgov\.be/cgi/article\.pl\?.*?(Haut de la page|Copier le lien|Image du Moniteur belge.*?)$",
        "",
        text,
        flags=re.DOTALL
    )

def convert_french_text_date_to_numeric(text_date):
    """
    Convertit une date en lettres (ex : 'trente mai deux mil vingt-trois')
    en format '30 mai 2023'
    """
    jour_map = {
        'premier': 1, 'un': 1, 'deux': 2, 'trois': 3, 'quatre': 4, 'cinq': 5, 'six': 6,
        'sept': 7, 'huit': 8, 'neuf': 9, 'dix': 10, 'onze': 11, 'douze': 12,
        'treize': 13, 'quatorze': 14, 'quinze': 15, 'seize': 16, 'dix-sept': 17,
        'dix-huit': 18, 'dix-neuf': 19, 'vingt': 20, 'vingt-et-un': 21, 'vingt-deux': 22,
        'vingt-trois': 23, 'vingt-quatre': 24, 'vingt-cinq': 25, 'vingt-six': 26,
        'vingt-sept': 27, 'vingt-huit': 28, 'vingt-neuf': 29, 'trente': 30, 'trente-et-un': 31
    }

    mois_map = {
        'janvier': 'janvier', 'février': 'février', 'mars': 'mars', 'avril': 'avril',
        'mai': 'mai', 'juin': 'juin', 'juillet': 'juillet', 'août': 'août',
        'septembre': 'septembre', 'octobre': 'octobre', 'novembre': 'novembre', 'décembre': 'décembre'
    }

    annee_map = {
        'deux mil vingt-trois': '2023', 'deux mille vingt-trois': '2023',
        'deux mil vingt-quatre': '2024', 'deux mille vingt-quatre': '2024',
        'deux mil vingt-cinq': '2025', 'deux mille vingt-cinq': '2025'
        # Ajouter plus de combinaisons si besoin
    }

    words = text_date.lower().strip().split()

    # Créer une date si les 3 parties sont reconnaissables
    jour = next((v for k, v in jour_map.items() if k in text_date), None)
    mois = next((v for k, v in mois_map.items() if k in text_date), None)
    annee = next((v for k, v in annee_map.items() if k in text_date), None)

    if jour and mois and annee:
        return f"{jour} {mois} {annee}"

    return None

# ATTENTION A RETRAVAILLER PAS COMPLET
def extract_jugement_date(text):
    """
    Extrait une date de jugement depuis un texte.
    Priorité :
    1. "passe en force de chose jugée le ..."
    2. Date 100 caractères avant "le greffier"
    3. Date après "division [ville]"
    4. Autres formulations classiques
    """

    text = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    # Sécurité en cas de texte mal nettoyé
    text = re.sub(r'\s+', ' ', text.replace('\xa0', ' ').replace('\n', ' ').replace('\r', ' ')).strip()
    text = re.sub(r"\b1er\s+er\b", "1er", text)
    # 🔹 2. Date dans les 100 caractères avant "le greffier"
    match_greffier = re.search(r"(.{0,100})\ble\s+greffier", text, flags=re.IGNORECASE | re.DOTALL)
    if match_greffier:
        zone = match_greffier.group(1)
        date_patterns = [
            r"(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
            r"(\d{2})[/-](\d{2})[/-](\d{4})",
            r"(\d{4})[/-](\d{2})[/-](\d{2})"
        ]
        for pat in date_patterns:
            match_date = re.search(pat, zone)
            if match_date:
                groups = match_date.groups()
                if len(groups) == 3:
                    if pat.startswith(r"(\d{4})[/-]"):
                        yyyy, mm, dd = groups
                    else:
                        dd, mm, yyyy = groups
                    return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"
                else:
                    return match_date.group(1).strip()


    # 🔹 3. Date après "division [Ville]" suivie de "le ..."
    match_division = re.search(
        r"division(?:\s+de)?\s+[A-ZÉÈÊËÀÂÇÎÏÔÙÛÜA-Za-zà-ÿ'\-]+.{0,60}?\b(?:le|du)\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        text, flags=re.IGNORECASE
    )
    if match_division:
        raw = match_division.group(1).strip()
        raw = match_division.group(1).strip().strip(",.;")

        if re.search(r"\d{1,2}(?:er)?\s+\w+\s+\d{4}", raw):
            return raw
        match_slash = re.search(r"(\d{2})/(\d{2})/(\d{4})", raw)
        if match_slash:
            dd, mm, yyyy = match_slash.groups()
            return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"
        match_dash_ddmm = re.search(r"(\d{2})-(\d{2})-(\d{4})", raw)
        if match_dash_ddmm:
            dd, mm, yyyy = match_dash_ddmm.groups()
            return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"
        match_dash = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
        if match_dash:
            yyyy, mm, dd = match_dash.groups()
            return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"
        try:
            return convert_french_text_date_to_numeric(raw)
        except:
            pass

    # 🔹 Nouveau : "Date du jugement : 15 juillet 2025"
    match_date_jugement_label = re.search(
        r"date\s+du\s+jugement\s*[:\-–]?\s*(.{0,30})",
        text,
        flags=re.IGNORECASE
    )
    if match_date_jugement_label:
        raw = match_date_jugement_label.group(1).strip()

        # Formats à tester
        if re.search(r"\d{1,2}(?:er)?\s+\w+\s+\d{4}", raw):
            return raw
        match_slash = re.search(r"(\d{2})/(\d{2})/(\d{4})", raw)
        if match_slash:
            dd, mm, yyyy = match_slash.groups()
            return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"
        match_dash = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
        if match_dash:
            yyyy, mm, dd = match_dash.groups()
            return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"
        try:
            converted = convert_french_text_date_to_numeric(raw)
            if converted:
                return converted
        except:
            pass

    match_intro = re.search(
        r"par\s+ordonnance\s+prononc[ée]e?.{0,200}?en\s+date\s+du\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        text[:500],
        flags=re.IGNORECASE
    )
    if match_intro:
        return match_intro.group(1).strip()

    # 🔹 0. "Par jugement du <date>" dans les 400 premiers caractères
    match_jugement_intro = re.search(
        r"par\s+jugement\s+du\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})",
        text[:400],
        flags=re.IGNORECASE
    )
    if match_jugement_intro:

        return match_jugement_intro.group(1).strip()

    match_ville_date_fin = re.search(
        rf"\.{{0,5}}\s*(?:{villes})\b[^a-zA-Z0-9]{{1,5}}le\s+(\d{{1,2}}(?:er)?\s+\w+\s+\d{{4}})\.",
        text[-300:],
        flags=re.IGNORECASE
    )
    if match_ville_date_fin:
         return match_ville_date_fin.group(1).strip()

         # Cas spécial : date juste après "par jugement du", avec contexte "tribunal de première instance"
    match = re.search(
        r"par\s+jugement\s+du\s+(\d{1,2}[./-]\d{1,2}[./-]\d{4}|\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        text,
        flags=re.IGNORECASE
    )
    if match:
        start_pos = match.start()
        context = text[max(0, start_pos - 100):start_pos].lower()
        if "tribunal de première instance" in context:
            return match.group(1).strip()
    # Cas spécifique : date précédée dans les 150 caractères par "tribunal de première instance", dans les 300 premiers caractères
    debut = text[:300].lower()
    match_date = re.search(r"\b(le\s+\d{1,2}(?:er)?\s+\w+\s+\d{4})", debut)
    if match_date:
        position = match_date.start()
        contexte_large = debut[max(0, position - 150):position]
        contexte_court = debut[max(0, position - 30):position]

        if "tribunal de première instance" in contexte_large:
            # ⛔ Exclure si le contexte court contient une naissance
            if re.search(r"\bn[ée]e?\b", contexte_court):
                pass  # Date ignorée
            else:
                return match_date.group(1).strip()

    # 🔹 4. Formulations classiques
    patterns = [
        r"[Pp]ar\s+d[ée]cision\s+prononc[ée]e?\s+le\s+(\d{2}[-/]\d{2}[-/]\d{4})",
        r"par\s+jugement\s+contradictoire\s+rendu\s+le\s+(\d{2}/\d{2}/\d{4})",
        r"ordonnance\s+d[ée]livr[ée]e?\s+par\s+la\s+\d{1,2}(?:e|er)?\s+chambre.*?\ble\s+(\d{2}/\d{2}/\d{4})",
        r"par\s+ordonnance\s+d[ée]livr[ée]e?.{0,200}?\b(\d{2}/\d{2}/\d{4})",
    ]

    patterns += [
        r"[Pp]ar\s+d[ée]cision\s+prononc[ée]e?\s+le\s+(\d{1,2}(?:er)?[\s/-]\w+[\s/-]\d{4}|\d{2}[-/]\d{2}[-/]\d{4}|\d{4}-\d{2}-\d{2})",
        r"[Dd]ate\s+du\s+jugement\s*[:\-]?\s*(\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})",
        r"[Pp]ar\s+ordonnance\s+(?:rendue|prononcée)\s+le\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{2}/\d{2}/\d{4})",
        r"[Pp]ar\s+jugement\s+(?:rendu\s+)?(?:le|du)\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{2}/\d{2}/\d{4})",
        r"[Pp]ar\s+d[ée]cision\s+prononc[ée]e?\s+le\s+(\d{1,2}\s+\w+\s+\d{4}|\d{2}/\d{2}/\d{4})",
        r"d[ée]cision\s+prononc[ée]e?\s+le\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{2}[-/]\d{2}[-/]\d{4})",
    ]

    patterns += [
        r"[Pp]ar\s+(?:son\s+)?ordonnance\s+du\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
        r"[Pp]ar\s+ordonnance\s+(?:rendue|prononcée)\s+en\s+date\s+du\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"[Pp]ar\s+ordonnance\s+prononcée,\s+en\s+date\s+du\s+(\d{2}/\d{2}/\d{4})",
        r"[Pp]ar\s+d[ée]cision\s+du\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"jugement\s+rendu\s+le\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"[Pp]ar\s+(?:sa|son)?\s*(?:ordonnance|décision|jugement)\s+de.*?\b(?:le|du)\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"d[ée]cision\s+de\s+la\s+\d{1,2}(?:[eE])?\s+chambre.*?le\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"[Pp]ar\s+ordonnance\s+du\s+(\d{1,2}[./-]\d{1,2}[./-]\d{4})"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            raw = match.group(1).strip()

            # Nettoyage final si besoin
            raw = raw.strip(",.;")

            # Si déjà au bon format texte
            if re.search(r"\d{1,2}(?:er)?\s+\w+\s+\d{4}", raw):
                return raw
            match_dash_ddmm = re.search(r"(\d{2})-(\d{2})-(\d{4})", raw)
            if match_dash_ddmm:
                dd, mm, yyyy = match_dash_ddmm.groups()
                return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"
            # dd/mm/yyyy
            match_slash = re.search(r"(\d{2})/(\d{2})/(\d{4})", raw)
            if match_slash:
                dd, mm, yyyy = match_slash.groups()
                return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"

            # dd.mm.yyyy
            match_point = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", raw)
            if match_point:
                dd, mm, yyyy = match_point.groups()
                return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"

            # yyyy-mm-dd
            match_dash = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
            if match_dash:
                yyyy, mm, dd = match_dash.groups()
                return f"{int(dd)} {get_month_name(int(mm))} {yyyy}"

            # En dernier recours : conversion texte → date
            try:
                converted = convert_french_text_date_to_numeric(raw)
                if converted:
                    return converted
            except:
                pass

    return None


r"""
def extract_date_after_birthday(texte_html):
    soup = BeautifulSoup(texte_html, 'html.parser')
    date_list = []

    # Cherche toutes les balises <br>
    for br in soup.find_all('br'):
        text = br.previous_element.strip() if isinstance(br.previous_element, str) else ''

        # Si on a du texte avant le <br>
        if text:
            match = re.search(r"(né|née)\(e\)?\s*le\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
            if match:
                date_list.append(match.group(2).strip())
                return date_list
            # Regex pour capturer la première date après "né à" ou "née à"
            match = re.search(r"(né|née)\s*à\s*[\w\s]+(?:\s*le\s*(\d{1,2}\s\w+\s\d{4}))[\s,]*", text, re.IGNORECASE)
            if match:
                # Si une correspondance est trouvée, on ajoute la date à la liste
                date_list.append(match.group(2).strip())
                return date_list
            match1 = re.search(r"(né|née)\s*à\s*[\w\s]+(?:\s*le\s*(\d{1,2}\s\w+\s\d{4}))[\s,]*", text, re.IGNORECASE)
            if match1 : 
                date_list.append(match1.group(4).strip())
                # Si une autre correspondance est trouvée, on peut faire quelque chose d'autre
            match2 = re.search(r"([A-Za-z\s]+),\s*(né\(e\)?|née)\s*le\s*(\d{4}-\d{2}-\d{2})\s*à\s*([A-Za-z\s]+)", text, re.IGNORECASE)

            if match2 : 
                date_list.append(match2.group(3).strip())
                # Si une autre correspondance est trouvée, on peut faire quelque chose d'autre

    return date_list
"""


def extract_dates_after_decede(html):
    soup = BeautifulSoup(html, 'html.parser')
    date_list = []

    # Regex pour formats de date
    date_pattern = re.compile(
        r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{4}"                # ex: 01.09.2024 ou 01/09/2024
        r"|\d{4}-\d{2}-\d{2}"                              # ex: 2024-09-01
        r"|\d{1,2}(?:er)?\s+[a-zéûîà]+\s+\d{4})",          # ex: 1er septembre 2024
        re.IGNORECASE
    )

    total_detected = 0
    total_with_dates = 0

    for text in soup.stripped_strings:
        match_decede = re.search(r"décéd[ée](?:\(e\))?", text, re.IGNORECASE)
        if not match_decede:
            continue

        total_detected += 1
        start_pos = match_decede.end()
        following_text = text[start_pos:start_pos + 60]

        matches = date_pattern.findall(following_text)
        cleaned_matches = [date.strip() for date in matches]

        if cleaned_matches:
            total_with_dates += 1
            date_list.extend(cleaned_matches)


    return date_list





def extract_date_after_birthday(texte_html):
    from bs4 import BeautifulSoup
    import re, unicodedata

    soup = BeautifulSoup(texte_html, 'html.parser')
    date_list = []

    raw_text = soup.get_text(separator=" ")
    full_text = unicodedata.normalize("NFC", unicodedata.normalize("NFKC", raw_text)).replace('\u00a0', ' ')
    full_text = full_text.replace('\u202f', ' ').replace('\u200b', '').replace('\ufeff', '')
    full_text = re.sub(r"\s+", " ", full_text)
    publications = [full_text]

    patterns = [
        r"succession\s+vacante\s+de\s+(?:M(?:onsieur)?|Madame)?\.?\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s*,\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s*,\s+né\s+à\s+[^\d\n]{1,50}?\s+le\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"né\s+le\s+1\s+(?:er\s+)?(?:er\s+)?(\w+\s+\d{4})",
        r"\bn[ée](?:\(e\))?\s+le\s+(\d{2}[\./-]\d{2}[\./-]\d{4})",
        r"(?:né|née)\s*à\s*[\w\s\-']+\s*le\s*(\d{1,2}[\s\-\.]\w+[\s\-\.]\d{4})",
        r"\bn[ée](?:\(e\))?\s+le\s+(\d{4}[-/\.]\d{2}[-/\.]\d{2})",
        r"\bn[ée](?:\(e\))?\s+le\s+(\d{1,2}\s+\w+\s+\d{4})\s+\(NN",
        r"(?:né|née)\s+à\s+[^\d\n]{1,50}?\s+le\s+(\d{1,2}\s+\w+\s+\d{4})(?=\s+\(NN|\s)",
        r"\(NN\s*(\d{2})[.\-/](\d{2})[.\-/](\d{2})[-.\s]",
        r"(?:né|née)\s+le\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"RN\s+(\d{2})[.\-/](\d{2})[.\-/](\d{2})[-.\s]",
        r"(?:né|née)\(e\)?\s+à\s+[^\d\n]{1,50}?\s+le\s+(\d{2}[\./-]\d{2}[\./-]\d{4})",
        r"(?:né|née)\s+(\d{2}[\./-]\d{2}[\./-]\d{4})",
        r"(?:né|née)\s+à\s+.+?\s+le\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"\bn[ée]\s+à\s+[^\n\d]{1,100}?\s+le\s+(\d{2}[\./-]\d{2}[\./-]\d{4})",
        r"\bsuccession vacante de\s+[^,]+,\s+n[ée]\s+à\s+.+?\s+le\s+(\d{2}[\./-]\d{2}[\./-]\d{4})",
        r"née à .+? le (\d{2}/\d{2}/\d{4})",
        r"Registre national\s*:\s*(\d{2})[.\-/](\d{2})[.\-/](\d{2})",
        r"Lieu et date de naissance\s*:\s*[^,]+,\s*le\s*(\d{1,2}\s+\w+\s+\d{4})",
        r"né\s+le\s+1(?:\s*er)?\s+(\w+\s+\d{4})",
        r"(?:né|née)\s+à\s+[^\d\n]{1,50}?\s+le\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"(?:né|née)\s+à\s+[^\d\n]{1,50}?,?\s+le\s+(\d{1,2}\s+\w+\s+\d{4})",
        r"succession\s+vacante\s+de\s+(?:M(?:onsieur)?|Madame)?\.?\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+,\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+,\s+né\s+à\s+[^\n\d]{1,50}?\s+le\s+(\d{1,2}\s+\w+\s+\d{4})(?=\s*[\(\.,;])"
    ]

    for pub in publications:
        pub = pub.strip()
        if not pub:
            continue
        found = False

        for pat in patterns:
            match = re.search(pat, pub, re.IGNORECASE)
            if match:
                if len(match.groups()) == 3:
                    yy, mm, dd = match.groups()
                    yyyy = f"19{yy}" if int(yy) > 30 else f"20{yy}"
                    date = f"{int(dd):02d}/{int(mm):02d}/{yyyy}"
                else:
                    date = match.group(1).strip()
                date_list.append(date)
                found = True
                break

        if found:
            continue

        # fallback ligne à ligne
        for line in pub.split("\n"):
            text = line.strip()
            if not text:
                continue
            for pat in patterns:
                match = re.search(pat, text, re.IGNORECASE)
                if match:
                    if len(match.groups()) == 3:
                        yy, mm, dd = match.groups()
                        yyyy = f"19{yy}" if int(yy) > 30 else f"20{yy}"
                        date = f"{int(dd):02d}/{int(mm):02d}/{yyyy}"
                    else:
                        date = match.group(1).strip()
                    date_list.append(date)
                    found = True
                    break
            if found:
                break

    return date_list

def extract_name_from_text(text):
    return extract_name_before_birth(text)

excluded_sources = {
    "Agence Fédérale pour la Sécurité de la Chaîne Alimentaire",
    "Agence Fédérale des Médicaments et des Produits de Santé",
    "Assemblée de la Commission Communautaire Française de la Région ...",
    "Autorité Flamande",
    "Banque Nationale de Belgique",
    "Chambre",
    "Collège de la Commission Communautaire Française",
    "Commission Bancaire et Financière",
    "Commission Communautaire Commune de Bruxelles-Capitale",
    "Commission Communautaire Française de la Région de Bruxelles-Capitale",
    "Commission de la Protection de la vie privee",
    "Communauté Française",
    "Conseil d'Etat",
    "Conseil Supérieur de la Justice",
    "Corps Interfédéral de l'Inspection des Finances",
    "Cour d'Arbitrage",
    "Cour des Comptes",
    "Cour Constitutionnelle",
    "Institut National d'Assurance Maladie-Invalidite",
    "Ministère de l'Emploi et du Travail",
    "Ministère de l'Intérieur",
    "Ministère de la Communauté Flamande",
    "Ministère de la Communauté Française",
    "Ministère de la Communauté Germanophone",
    "Ministère de la Défense Nationale",
    "Ministère de la Défense",
    "Ministère de la Fonction Publique",
    "Ministère de la Justice",
    "Ministère de la Région de Bruxelles-Capitale",
    "Ministere de la Region de Bruxelles-Capitale",
    "Ministere de la Region de Bruxelles-capitale",
    "Ministere de La Region de Bruxelles-Capitale",
    "Ministère de la Région Wallonne",
    "Ministère des Affaires Economiques",
    "Ministère des Affaires Etrangères",
    "Ministère des Affaires Sociales",
    "Ministère des Classes Moyennes et de l'Agriculture",
    "Ministère des Communications et de l'Infrastructure",
    "Ministère des Finances",
    "Ministère Wallon de l'Equipement et des Transports",
    "Pouvoir Judiciaire",
    "Selor - Bureau de Selection de l'Administration Fédérale",
    "Sénat",
    "Service Public de Wallonie",
    "Service Public Fédéral Affaires Etrangères, ...",
    "Service Public Fédéral Budget et controle de la gestion",
    "Service Public Fédéral Chancellerie du Premier Ministre",
    "Service Public Fédéral Chancellerie et Services Généraux",
    "Service Public Fédéral de Programmation Développement Durable",
    "Service Public Fédéral de Programmation Gestion des Actifs",
    "Service Public Fédéral de Programmation Intégration sociale",
    "Service Public Fédéral de Programmation Politique Scientifique",
    "Service Public Fédéral de Programmation Protection des Consommateurs",
    "Service Public Fédéral de Programmation Telecommunications",
    "Service Public Fédéral Economie, P.M.E., Classes Moyennes et Enérgie",
    "Service Public Fédéral Emploi, Travail et Concertation Sociale",
    "Service Public Fédéral Finances",
    "Service Public Fédéral Interieur",
    "Service Public Fédéral Justice",
    "Service Public Fédéral Mobilite et Transports",
    "Service Public Fédéral Personnel et Organisation",
    "Service Public Fédéral Sante Publique, Sécurité de la chaîne ...",
    "Service Public Fédéral Securite Sociale",
    "Service Public Fédéral Stratégie et Appui",
    "Service Public Fédéral Technologie de l'Information et de la Communication",
    "Services du Premier Ministre",
    "Services Fédéraux des Affaires Scientifiques, Techniques et Culturelles"
}


def detect_cour_constitutionnelle_title(title: str) -> bool:
    """
    Détecte les titres faisant référence à la Cour constitutionnelle via l'article 74 de la loi spéciale.
    """
    title_clean = re.sub(r"[^\w\s]", " ", title.lower())
    return "article 74 de la loi spéciale du 6 janvier 1989" in title_clean

def detect_autre_juridiction_title(title: str) -> str | None:
    """
    Détecte si le titre mentionne explicitement une juridiction importante
    et retourne un mot-clé correspondant à réassigner si trouvé.
    """
    title_clean = re.sub(r"[^\w\s]", " ", title.lower())

    if "cour d'appel" in title_clean:
        return "cour_d_appel"
    elif "tribunal de première instance" in title_clean:
        return "tribunal_premiere_instance"

    return None

def detect_societe_title(title: str) -> bool:
    societes_abrev = {"SA", "SRL", "SE", "SPRL", "SIIC", "SC", "SNC", "SCS", "COMMV", "SCRL", "SAS", "ASBL", "SCA"}
    societes_formelles = [
        "société anonyme", "société à responsabilité limitée", "société coopérative",
        "société européenne", "société en commandite", "société civile"
    ]

    # Retire ponctuations internes inutiles
    title_clean = re.sub(r"[^\w\s]", " ", title).strip()

    # 1. Vérifie si le titre commence par une séquence MAJUSCULES suivie d'une abréviation
    for abrev in societes_abrev:
        pattern = r'^([A-Z][A-Z\s\-&]{2,})\s+' + abrev + r'\b'
        if re.match(pattern, title_clean):
            return True

    # 2. Vérifie si le titre commence par une séquence MAJUSCULES suivie d'un nom complet de société
    for full in societes_formelles:
        pattern = r'^([A-Z][A-Z\s\-&]{2,})\s+' + re.escape(full) + r'\b'
        if re.match(pattern, title_clean, flags=re.IGNORECASE):
            return True

    return False

def extract_clean_text(soup):
    """
    Extrait un texte propre à partir d’un objet BeautifulSoup,
    en supprimant les balises non utiles et les caractères invisibles.
    Gère les balises <br>, <sup>, etc., et normalise le texte.
    """
    output = []
    last_was_tag = None

    for elem in soup.descendants:
        if isinstance(elem, NavigableString):
            txt = elem.strip()
            if txt:
                # Ajouter un espace si nécessaire
                if last_was_tag in ("font", "sup", "text"):
                    output.append(" ")
                output.append(txt)
                last_was_tag = "text"

        elif isinstance(elem, Tag):
            tag_name = elem.name.lower()
            if tag_name == "br":
                output.append(" ")
                last_was_tag = "br"
            # Remplace par ça :
            elif tag_name == "sup":
                sup_text = elem.get_text(strip=True)
                if output and output[-1].isdigit():
                    # Fusionne le chiffre avec "er", "e", etc.
                    output[-1] = output[-1] + sup_text
                else:
                    output.append(sup_text)
                last_was_tag = "sup"
            else:
                last_was_tag = tag_name

    # Assembler le texte extrait
    text = "".join(output)

    # 🔧 Nettoyage des caractères invisibles et espaces anormaux
    text = text.replace('\u00a0', ' ')  # espace insécable
    text = text.replace('\u200b', '')  # zero-width space
    text = text.replace('\ufeff', '')  # BOM UTF-8
    text = re.sub(r'\s+', ' ', text)   # remplace tous les blancs par un seul espace

    return text.strip()

def generate_doc_hash_from_html(html, date_doc):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(["script", "style", "font", "span", "mark"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"Liens\s*:.*?(Haut de la page|Copier le lien).*?$", "", text, flags=re.DOTALL)
    text = re.sub(r"https://www\.ejustice\.just\.fgov\.be[^\s]+", "", text)
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # 💡 Inclure la date dans le hash
    full_string = f"{date_doc}::{text}"
    return hashlib.sha256(full_string.encode("utf-8")).hexdigest()

def clean_url(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    # Supprimer 'exp' de la query string s'il existe
    query.pop("exp", None)

    # Reconstruire l'URL sans 'exp'
    cleaned_query = urlencode(query, doseq=True)
    cleaned_url = urlunparse(parsed._replace(query=cleaned_query))
    return cleaned_url


def retry(url, session, params=None):
    try:
        response = session.get(url, params=params)
        response.encoding = "Windows-1252"
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException:
        print(f"[!] Retry needed for {url}")
        time.sleep(10)
        return retry(url, session, params)

def find_linklist_in_items(item, keyword, link_list):
    link_tag = item.find("div", class_="list-item--button").find("a")
    numac = re.search(r'numac_search=(\d+)', link_tag["href"]).group(1)
    datepub = re.search(r'pd_search=(\d{4}-\d{2}-\d{2})', link_tag["href"]).group(1)
    lang = "FR"
    full_url = BASE_URL + link_tag["href"]

    title_element = item.find("a", class_="list-item--title")
    title = title_element.get_text(strip=True) if title_element else ""

    subtitle_element = item.find("p", class_="list-item--subtitle")
    subtitle = subtitle_element.get_text(strip=True) if subtitle_element else ""

    link_list.append((full_url, numac, datepub, lang, keyword, title, subtitle))

def get_page_amount(session, start_date, end_date, keyword):
    encoded = keyword.replace(" ", "+")
    today = date.today()
    url = f'{BASE_URL}list.pl?language=fr&sum_date={today}&page=&pdd={start_date}&pdf={end_date}&choix1=et&choix2=et&exp={encoded}&fr=f&trier=promulgation'
    response = retry(url, session)
    soup = BeautifulSoup(response.text, 'html.parser')
    last_link = soup.select_one("div.pagination-container a:last-child")
    if not last_link:
        return 1
    match = re.search(r'page=(\d+)', last_link["href"])
    return int(match.group(1)) if match else 1

def ask_belgian_monitor(session, start_date, end_date, keyword):
    page_amount = get_page_amount(session, start_date, end_date, keyword)
    print(f"[INFO] Pages à scraper pour '{keyword}': {page_amount}")
    link_list = []

    def process_page(page):
        encoded = keyword.replace(" ", "+")
        today = date.today()
        url = f'{BASE_URL}list.pl?language=fr&sum_date={today}&page={page}&pdd={start_date}&pdf={end_date}&choix1=et&choix2=et&exp={encoded}&fr=f&trier=promulgation'
        response = retry(url, session)
        soup = BeautifulSoup(response.text, 'html.parser')
        class_list = soup.find("div", class_="list")
        if not class_list:
            return
        for item in class_list.find_all(class_="list-item"):
            subtitle = item.find("p", class_="list-item--subtitle")
            subtitle_text = subtitle.get_text(strip=True) if subtitle else ""
            title_elem = item.find("a", class_="list-item--title")
            title = title_elem.get_text(strip=True) if title_elem else ""
            if keyword == "Liste+des+entites+enregistrees" and subtitle_text == "Service public fédéral Economie, P.M.E., Classes moyennes et Énergie":
                find_linklist_in_items(item, keyword, link_list)
            elif keyword == "Conseil+d+'+Etat" and subtitle_text == "Conseil d'État" and title.lower().startswith("avis prescrit"):
                find_linklist_in_items(item, keyword, link_list)
            elif keyword == "Cour+constitutionnelle" and subtitle_text == "Cour constitutionnelle":
                find_linklist_in_items(item, keyword, link_list)
            elif keyword == "terrorisme":
                cleaned_title = title.strip().lower()
                print("voici le titre:",cleaned_title)
                if "entités visée aux articles 3 et 5 de l'arrêté royal du 28 décembre 2006" in cleaned_title:
                     print(f"[🪦] Document succession détecté : {title}")
                     find_linklist_in_items(item, keyword, link_list)
                else:
                    print(f"[❌] Ignoré (terrorisme mais pas SPF Finances) : {title}")

            elif keyword in ("succession", "successions"):
                
                cleaned_title = title.strip().lower()
                
                # Vérifie si le titre correspond exactement à ce que tu recherches
                if cleaned_title == "administration générale de la documentation patrimoniale" or cleaned_title.startswith("les créanciers et les légataires sont invités à "):
                     print(f"[🪦] Document succession détecté : {title}")
                     find_linklist_in_items(item, keyword, link_list)
                       # faut le faire pour chacun ici!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            elif keyword in ("tribunal+de+premiere+instance"):
                if (
                        title.lower().startswith("tribunal de première instance")

                ):
                    #print(title)
                    find_linklist_in_items(item, keyword, link_list)
                else:
                    print(f"[❌] Ignoré (source ou titre non pertinent pour tribunal de première instance) : {title} | Source : {subtitle_text}")
            elif keyword in ("tribunal+de+l"):
                if (
                        title.lower().startswith("tribunal de l")

                ):
                    #print(title)
                    find_linklist_in_items(item, keyword, link_list)
                else:
                    print(f"[❌] Ignoré (source ou titre non pertinent pour trib entreprise) : {title} | Source : {subtitle_text}")

            elif keyword in ("justice+de+paix"):
                    if (
                            title.lower().startswith("justice de paix")


                    ):
                        #print(title)
                        find_linklist_in_items(item, keyword, link_list)
                    
                    else:
                        print(f"[❌] Ignoré (source ou titre non pertinent pourjustice de paix) : {title} | Source : {subtitle_text}")
            elif keyword in ("cour+de+d"):
                if (
                        title.lower().startswith("cour d'appel")

                ):
                    #print(title)
                    find_linklist_in_items(item, keyword, link_list)
                else:
                    print(
                        f"[❌] Ignoré (source ou titre non pertinent pour cour d appel) : {title} | Source : {subtitle_text}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        list(tqdm(executor.map(process_page, range(1, page_amount + 1)), total=page_amount, desc="Pages"))

    return link_list

def strip_html_tags(text):
    return re.sub('<.*?>', '', text)



def extract_terrorism_data(html):
        """Fonction spécifique pour le traitement du terrorisme"""
        texte = extract_clean_text(html)
        nom = extract_name_from_text(texte)
        match_nn_all = re.findall(r'(\d{2})[\s.\-]?(\d{2})[\s.\-]?(\d{2})[\s.\-]?(\d{3})[\s.\-]?(\d{2})', texte)
        numero_national = ''.join(match_nn_all[0]) if match_nn_all else None
        return [nom, numero_national]

def extract_page_index_from_url(pdf_url):
    match = re.search(r'#page=(\d+)', pdf_url)
    if match:
        page_number = int(match.group(1))
        print("numéro de la page pdf", page_number)
        return page_number - 1  # PyMuPDF indexe à partir de 0
    return None 

def extract_names_and_nns(text):
    results = []

    # 🔹 Pattern classique NOM, Prénom, NRN
    pattern = (
        r"(?:le nommé\s*:|NOM(?:\s+et)?\s+PRÉNOM\s*:)?\s*"
        r"(\d+\s*[A-Z]\s*\d{4})?\s*"  # ex: 1492 C 2025
        r"([A-ZÉÈÀÛÎÇ\-']{2,}(?:\s+[A-ZÉÈÀÛÎÇ\-']{2,})*),?\s+"
        r"([A-Z][a-zéèàêîç\-']{1,}(?:\s+[A-Z][a-zéèàêîç\-']{1,})*)\s*,?\s+"
        r"(?:NRN|Registre national)\s*:?\s*(\d{2}[.\-/]\d{2}[.\-/]\d{2}[-\s.]\d{3}[.\-/]\d{2})"
    )
    matches = re.findall(pattern, text, re.IGNORECASE)
    for _, _, _, nn in matches:
        results.append(nn.strip())

    # 🔹 Pattern spécial "le nommé : 1492 C 2025 NOM, Prénom, NRN ..."
    pattern_alt = (
        r"le nommé\s*:\s*(?:\d+\s*[A-Z]\s*\d{4})\s+"
        r"([A-ZÉÈÀÛÎÇ\-']{2,}(?:\s+[A-ZÉÈÀÛÎÇ\-']{2,})*),\s+"
        r"([A-Z][a-zéèàêîç\-']{1,}(?:\s+[A-Z][a-zéèàêîç\-']{1,})*),?\s+"
        r"NRN\s+(\d{2}[.\-/]\d{2}[.\-/]\d{2}-\d{3}[.\-/]\d{2})"
    )
    matches_alt = re.findall(pattern_alt, text, re.IGNORECASE)
    for _, _, nn in matches_alt:
        results.append(nn.strip())

    # 🔹 NRN isolé
    pattern_nrn_alone = r'\b(\d{2})[.\-/ ](\d{2})[.\-/ ](\d{2})[.\-/ ](\d{3})[.\-/ ](\d{2})\b'
    matches_nrn_only = re.findall(pattern_nrn_alone, text)
    for yy, mm, dd, bloc, suffix in matches_nrn_only:
        nn = f"{yy}.{mm}.{dd}-{bloc}.{suffix}"
        results.append(nn)

    return list(dict.fromkeys(results))

def convert_pdf_pages_to_text_range(pdf_url, start_page_index, page_count=6):
    """
    Télécharge un PDF depuis une URL, applique l’OCR sur plusieurs pages à partir de start_page_index.
    Corrige les problèmes de permission, fichiers verrouillés, noms en conflit et profils ICC.
    """
    try:
        response = requests.get(pdf_url)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement du PDF : {e}")
        return ""

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(response.content)
        tmp_path = tmp_file.name
        print(f"[📄] PDF temporaire sauvegardé : {tmp_path}")

    full_text = ""
    pdf = None

    try:
        pdf = fitz.open(tmp_path)
        total_pages = len(pdf)

        # 🔒 start_page_index par défaut
        if start_page_index is None:
            print(f"[⚠️] start_page_index est None — on démarre à la page 0")
            start_page_index = 0

        end_page_index = min(start_page_index + page_count, total_pages)

        for i in range(start_page_index, end_page_index):
            try:
                page = pdf.load_page(i)
                # ✅ Matrice haute résolution + couleurs RGB pour éviter les erreurs ICC
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csRGB)

                # ✅ Nom de fichier unique
                timestamp = int(time.time() * 1000)
                img_path = f"ocr_page_{i + 1}_{os.getpid()}_{timestamp}.png"
                pix.save(img_path)

                if not os.path.exists(img_path):
                    print(f"[❌] Image non créée pour la page {i + 1} : {img_path}")
                    continue

                try:
                    img = Image.open(img_path)
                    text = pytesseract.image_to_string(img)
                    img.close()
                except Exception as e_ocr:
                    print(f"[⚠️] Erreur OCR sur la page {i + 1} : {e_ocr}")
                    text = ""

                full_text += f"\n--- Page {i + 1} ---\n{text}"

                try:
                    os.remove(img_path)
                except Exception as e_rm:
                    print(f"[⚠️] Impossible de supprimer '{img_path}' : {e_rm}")

            except Exception as e_page:
                print(f"⚠️ Erreur OCR sur la page {i + 1} : {e_page}")
                continue

    except Exception as e_open:
        print(f"❌ Erreur d’ouverture ou d’OCR : {e_open}")
        return ""

    finally:
        if pdf:
            pdf.close()
        try:
            os.remove(tmp_path)
        except Exception as e_rm:
            print(f"[⚠️] Erreur suppression fichier temporaire : {e_rm}")

    return full_text.strip()


def scrap_informations_from_url(session, url, numac, date_doc, langue, keyword, title, subtitle):
    response = retry(url, session)
    soup = BeautifulSoup(response.text, 'html.parser')
    extra_keywords = []
    extra_links = []

    main = soup.find("main", class_="page__inner page__inner--content article-text")
    if not main:
        return (numac, date_doc, langue, "", url, keyword, None, title, subtitle, None, None,None,None, None, None,None,None,None, None)

    texte_brut = extract_clean_text(main)
    #if re.search(r"statuant", texte_brut, flags=re.IGNORECASE):
        #print("✅ 'statuant' trouvé dans texte_brut")
    #if re.search(r"statuant\s+en\s+degr[ée]?\s+d[’'`´]appel", texte_brut, flags=re.IGNORECASE):
        #print("✅ Match complet trouvé")
    date_jugement = None
    administrateur = None
    nom_trib_entreprise = None
    date_deces = None
    doc_id = generate_doc_hash_from_html(texte_brut, date_doc)
    if detect_erratum(texte_brut):
        extra_keywords.append("erratum")

    # Cas spécial : TERRORISME
    if re.search(r"terrorisme", keyword, flags=re.IGNORECASE):
        print("🔍 Détection d’un document lié au terrorisme.")

        # 🔎 Extraction directe depuis le texte HTML (dans certains cas ça suffit)
        pattern = r"(\d+)[,\.]\s*([A-Za-z\s]+)\s*\(NRN:\s*(\d{2}\.\d{2}\.\d{2}-\d{3}\.\d{2})\)"
        matches = re.findall(pattern, texte_brut)

        noms_paires = [(name.strip(), nn.strip()) for _, name, nn in matches]

        # Si trouvé dans le HTML → pas besoin d'OCR
        if noms_paires:
            return (
                numac, date_doc, langue, texte_brut, url, keyword,
                None, title, subtitle, noms_paires, None, None, None, None,None,None,None, None
            )

        # Sinon, OCR fallback
        main_pdf_links = soup.find_all("a", class_="links-link")
        if len(main_pdf_links) >= 2:
            pdf_href = main_pdf_links[-2]['href']
            full_pdf_url = urljoin("https://www.ejustice.just.fgov.be", pdf_href)
            print(f"📄 Téléchargement du PDF : {full_pdf_url}")
            page_index = extract_page_index_from_url(full_pdf_url)
            if page_index is None:
                print(f"[⚠️] Pas de numéro de page dans l’URL : {full_pdf_url} — on commence à la page 0")
                page_index = 0

            ocr_text = convert_pdf_pages_to_text_range(full_pdf_url, page_index, page_count=6)

            if ocr_text:
                ocr_matches = re.findall(pattern, ocr_text)
                noms_ocr = [(name.strip(), nn.strip()) for _, name, nn in ocr_matches]
                return (
                    numac, date_doc, langue, texte_brut, url, keyword,
                    None, title, subtitle, noms_ocr, None, None, None, None,None, nom_trib_entreprise, None, None, None
                )
            else:
                print("⚠️ Texte OCR vide.")
                return None
        else:
            print("⚠️ Aucun lien PDF trouvé pour l’OCR.")
            return None

    # Cas normal
    nom = extract_name_from_text(str(main))
    date_naissance = extract_date_after_birthday(str(main))
    adresse = extract_address(str(main))
    if not date_jugement:
        date_jugement = extract_jugement_date(str(texte_brut))

    if re.search(r"succession[s]?", keyword, flags=re.IGNORECASE):
        date_deces = extract_dates_after_decede(str(texte_brut))
        date_deces = ", ".join(date_deces) if date_deces else None
        adresse = extract_address(str(main))
        if re.search(r"\bdéshérence", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("déshérence")
        elif re.search(r"\bacceptation\s+sous\s+bénéfice\s+d['’]inventaire", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("acceptation_sous_benefice_inventaire")

    if re.search(r"tribunal[\s+_]+de[\s+_]+premiere[\s+_]+instance", keyword, flags=re.IGNORECASE | re.DOTALL):
        print(keyword)
        if re.search(r"\bsuccession[s]?", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("succession")
            print(texte_brut)
            date_deces = extract_dates_after_decede(str(texte_brut))
            date_deces = ", ".join(date_deces) if date_deces else None
        if re.search(r"\bsuccession[s]?.{0,30}?(réputée[s]?.{0,10}?vacante[s]?|en\s+déshérence)", texte_brut, flags=re.IGNORECASE| re.DOTALL):
            extra_keywords.append("succession_vacante_desherence")
        if re.search(r"\bdésign[ée]?\b", texte_brut, flags=re.IGNORECASE):
            print("designation")
            extra_keywords.append("désignation")
            # ✅ Ajout pour "présumé(e) absent(e)"
        if re.search(r"\bprésum[ée]?\b.{0,10}?(absent[ée]?|d[’']?absence)", texte_brut,
                     flags=re.IGNORECASE | re.DOTALL):
            extra_keywords.append("presume_absent")
        elif re.search(r"\bprésomption\s+d[’']?absence\b", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("presomption_absence")
        elif re.search(r"\bdissolution\s+judiciaire\b", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("dissolution_judiciaire")
        if re.search(r"(?:statuant|siégeant)\s+en\s+degr[ée]?\s+d[’']?appel|(?:requête\s+d[’']?appel)", texte_brut,
                     flags=re.IGNORECASE):
            extra_keywords.append("appel")
        if re.search(r"\b(condamn[ée]?[es]?|emprisonnement|réclusion|peine\s+privative\s+de\s+liberté)\b", texte_brut,
                     flags=re.IGNORECASE):
            extra_keywords.append("condamnation")
            # ✅ Ajout du cas "actuellement sans résidence ni domicile connu"
        if re.search(r"sans\s+résidence\s+ni\s+domicile", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("sans_domicile_connu")

        # ✅ Nouveau cas : réforme de l'ordonnance
        if re.search(r"\br[ée]forme\s+l[’']?ordonnance", texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("reforme_ordonnance")
        if re.search(r"\bsuccession[s]?\s+vacante[s]?\b", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("succession_vacante")
        if re.search(r"\bsuccession[s]?\s+en\s+déshérence\b", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("succession_deshérence")
        if re.search(r"\bl[èe]ve\s+la\s+mesure\s+d[’']?observation", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("levee_mesure_observation")
        if re.search(r"(?:jugement|ordonnance)[^.,:\n]{0,100}du\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})[^.\n]{0,50}\(RG", texte_brut, flags=re.IGNORECASE):
            match_rg_date = re.search(
                r"(?:jugement|ordonnance)[^.,:\n]{0,100}du\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})[^.\n]{0,50}\(RG",
                texte_brut,
                flags=re.IGNORECASE
            )
            if match_rg_date:
                print("🎯 Date capturée!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! :", match_rg_date.group(1))
                extra_links.append(f"levee_{match_rg_date.group(1)}")
            else:
                print("❌ Aucun match pour RG date")
        # 🔍 Bloc 1 : levée de la mesure du [date]
        match_levee = re.search(
            r"levée\s+de\s+la\s+mesure(?:\s+de\s+protection)?[^.,:\n]{0,50}du\s+"
            r"(\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})[^.\n]{0,50}\(RG",
            texte_brut,
            flags=re.IGNORECASE
        )
        if match_levee:
            date_str = match_levee.group(1)
            print("✅ Date levée trouvée :", date_str)
            extra_links.append(f"levee_{date_str}")
        else:
            print("❌ Aucune date pour 'levée de la mesure'")

        # 🔍 Bloc 2 : réforme et mise à néant du [date]
        match_rl_date = re.search(
            r"réforme\s+et\s+met\s+à\s+néant\s+la\s+décision\s+du\s+"
            r"(\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{4}),\s+du\s+juge\s+de\s+paix",
            texte_brut,
            flags=re.IGNORECASE
        )
        if match_rl_date:
            date_str = match_rl_date.group(1)
            print("✅ Date levée trouvée :", date_str)
            extra_links.append(f"levee_{date_str}")
        else:
            print("❌ Aucune date pour 'réforme et mise à néant'")
        if re.search(r"ordonnance\s+du\s+juge\s+de\s+paix.{0,300}?"
              r"(\d{1,2}(?:er)?\s+\w+\s+\d{4})",  # on ne va matcher ici que 23 février 2023 pour plus de contrôle
              texte_brut,
              flags=re.IGNORECASE | re.DOTALL):
              match_rh_date = re.search(
                 r"ordonnance\s+du\s+juge\s+de\s+paix.{0,300}?"
                 r"(\d{1,2}(?:er)?\s+\w+\s+\d{4})",  # on ne va matcher ici que 23 février 2023 pour plus de contrôle
                 texte_brut,
                 flags=re.IGNORECASE | re.DOTALL
                 )
              if match_rh_date:
                     print("✅ Date trouvée :", match_rh_date.group(1))
                     extra_links.append(f"levee_{match_rh_date.group(1)}")
              else:
                     print("❌ Aucune date trouvée")

        match_neant_date = re.search(
            r"met\s+à\s+néant\s+la\s+décision\s+du.{0,30}?"
            r"(\d{1,2}(?:er)?\s+\w+\s+\d{4}"  # ex : 10 janvier 2024
            r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"  # ex : 10/01/2024
            r"|\d{4}-\d{2}-\d{2}"  # ISO
            r"|\d{1,2}\.\d{1,2}\.\d{2,4})",  # 10.01.2024
            texte_brut,
            flags=re.IGNORECASE | re.DOTALL
        )

        if match_neant_date:
            extra_links.append(f"levee_{match_neant_date.group(1)}")
            print("✅ Date trouvée :", match_neant_date.group(1))
        else:
            print("❌ Aucune date trouvée")
        match_reforme_date = re.search(
            r"réforme\s+l[’']?ordonnance\s+du.{0,30}?"
            r"(\d{1,2}(?:er)?\s+\w+\s+\d{4}"  # ex : 10 janvier 2024
            r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"  # ex : 10/01/2024
            r"|\d{4}-\d{2}-\d{2}"  # ex : 2024-01-10
            r"|\d{1,2}\.\d{1,2}\.\d{2,4})",  # ex : 10.01.2024
            texte_brut,
            flags=re.IGNORECASE | re.DOTALL
        )

        if match_reforme_date:
            extra_links.append(f"levee_{match_reforme_date.group(1)}")
            print("✅ Date trouvée :", match_reforme_date.group(1))
        else:
            print("❌ Aucune date trouvée")

        match_rep_date = re.search(
            r"sous\s+un\s+régime\s+de\s+représentation\s+par\s+ordonnance\s+du\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})",
            texte_brut,
            flags=re.IGNORECASE
        )
        if match_rep_date:
            print("✅ Date de régime de représentation :", match_rep_date.group(1))
            extra_links.append(f"regime_repr_{match_rep_date.group(1)}")
        else:
            print("❌ Aucune date de régime de représentation trouvée")

        match_rendu = re.search(r"rendu[e]?(?:\s+(?:par|le|à))?", texte_brut, flags=re.IGNORECASE)
        if match_rendu:
            print("matcreeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeendu")
            zone = texte_brut[match_rendu.start():match_rendu.end() + 300]
            date_convertie = extract_date_after_rendu_par(zone)
            print("date convertieeeeeeeeeeeeeeeeeeeeeee", date_convertie)
            if date_convertie:
                extra_links.append(f"levee_{date_convertie}")
                print("✅ Date extraite et convertie :", date_convertie)
            else:
                print("❌ Date présente mais non reconnue dans la zone")
        else:
            print("❌ 'rendu par' non trouvé")

    if re.search(r"justice\s+de\s+paix", keyword.replace("+", " "), flags=re.IGNORECASE):
        if re.search(r"\b[dD]ésignation\b", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("designation_justice_de_paix")
        elif re.search(r"\b[nN]omm(e|é|ée)\b", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("nomination_justice_de_paix")
        elif re.search(r"\b[rR]emplacement\b", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("remplacement_justice_de_paix")
        elif re.search(r"\b[Mm]ainlevée\b", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("mainlevée_justice_de_paix")
        elif re.search(r"\b[fF]in\s+aux\s+mesures\b", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("fin_aux_mesures_justice_de_paix")
        if re.search(r"curateur(?:\s+aux\s+meubles)?", texte_brut, flags=re.IGNORECASE):
            extra_keywords.append("curateur_aux_meubles_justice_de_paix")

    if re.search(r"tribunal\s+de\s+l", keyword.replace("+", " "), flags=re.IGNORECASE):
        nom = None  # à vérifier si nécessaire
        nom_trib_entreprise = extract_noms_entreprises(texte_brut, doc_id=doc_id)
        administrateur = extract_administrateur(texte_brut)
        adresse = extract_add_entreprises(str(main), doc_id=doc_id)
        pattern_cloture = r"\b[cC](l[oô]|olo)ture\b"
        pattern_liquidation = r"\bliquidations?\b"
        pattern_liquidation_bis = r"\bliquidation(?:s)?\s*de\b"
        pattern_ouverture = r"\bouverture\s+de\s+la\s+faillite\b"
        pattern_faillite = r"\bfaillite\b"
        pattern_designation_mandataire = r"(application\s+de\s+l['’]?art\.?\s*XX\.?(2[0-9]|3[0-9])\s*CDE)"
        pattern_delai_modere = r"(?i)(délais?\s+modérés?.{0,80}article\s+5[.\s\-]?201)"

        pattern_ouverture_reorg = r"\bouverture\s+de\s+la\s+réorganisation\s+judiciaire\b"
        pattern_prorogation_reorg = r"\bprorogation\s+du\s+sursis\s+de\s+la\s+réorganisation\s+judiciaire\b"
        pattern_nouveau_plan_reorg = r"\bautorisation\s+de\s+d[ée]p[oô]t\s+d['’]un\s+nouveau\s+plan\s+de\s+la\s+réorganisation\s+judiciaire\b"
        pattern_homologation_plan = r"\bhomologation\s+du\s+plan\s+de\b"
        pattern_reorg_generique = r"\bréorganisation\s+judiciaire\s+de\b"
        pattern_homologation_accord = r"\bhomologation\s+de\s+l[’']accord\s+amiable\s+de\b"
        pattern_revocation_plan_reorganisation_judiciaire = r"révocation\s+du\s+plan\s+de\s+réorganisation\s+judiciaire"

        pattern_administrateur_provisoire = r"administrateur\s+provisoire\s+d[ée]sign[ée]?"
        pattern_rapporte = r"\brapporte\s+(la\s+)?faillite(s)?(\s+\w+)?"
        pattern_rapporte_bis = r"\best\s+rapportée(s)?(\s+.*)?"
        pattern_effacement_partiel = r"(?:\b[lL]['’]?\s*)?[eé]ffacement\s+partiel\b"
        pattern_excusabilite = r"\ble\s+failli\s+est\s+déclaré\s+excusable\b[\.]?\s*"
        pattern_effacement = r"\beffacement\s+de\s+la\s+faillite\s+de\b[.:]?\s*"
        pattern_effacement_ter = r"(l['’]?\s*)?effacement\s+(est\s+)?accordé"
        pattern_sans_effacement = r"\bsans\s+effacement\s+de\s+la\s+faillite\s+de\b[.:]?\s*"
        pattern_effacement_bis = r"\boctroie\s+l['’]effacement\s+à\b[.:]?\s*"
        pattern_accord_collectif = r"réorganisation\s+judiciaire\s+par\s+accord\s+collectif"
        # 🔒 Interdiction d'exploiter / gérer une entreprise
        # 🛑 Interdiction d'exploiter / exercer / diriger une entreprise
        pattern_interdiction = (
            r"\b(interdit[ée]?|interdiction).{0,150}?"
            r"\b(exploiter|exercer|diriger|gérer|administrer).{0,100}?"
            r"\b(entreprise|fonction|personne\s+morale|société)\b"
        )
        pattern_remplacement_administrateur = (
            r"(curateur|liquidateur|administrateur).*?remplac[ée]?(?:\s+à\s+sa\s+demande)?\s+par"
        )
        pattern_remplacement_juge_commissaire = r"est\s+remplac[ée]?\s+par\s+le\s+juge\s+commissaire"
        pattern_remplacement_juge_commissaire_bis = (
            r"est\s+remplac[ée]?\s+par\s+(le|les)\s+juges?\s+commissaires?"
        )

        pattern_report_cessation_paiement = r"report[\s\w,.'’():\-]{0,80}?cessation\s+des\s+paiements"
        # Combinaison des deux
        pattern = fr"({pattern_cloture})|({pattern_liquidation})"

        if re.search(pattern_rapporte, texte_brut, flags=re.IGNORECASE) or re.search(pattern_rapporte_bis, texte_brut,
                                                                                     flags=re.IGNORECASE):
            extra_keywords.append("rapporte_faillite_tribunal_de_l_entreprise")
        else:
            if re.search(r"\b[dD]ésignation\b", texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("designation_tribunal_de_l_entreprise")

            if re.search(pattern_cloture, texte_brut, flags=re.IGNORECASE):
                if re.search(r"\binsuffisance\s+d[’'\s]?actif\b", texte_brut, flags=re.IGNORECASE):
                    extra_keywords.append("cloture_insuffisance_actif_tribunal_de_l_entreprise")
                if re.search(r"\bdissolution\b", texte_brut, flags=re.IGNORECASE):
                    extra_keywords.append("cloture_dissolution_tribunal_de_l_entreprise")
                if re.search(pattern_faillite, texte_brut, flags=re.IGNORECASE):
                    extra_keywords.append("cloture_faillite_tribunal_de_l_entreprise")
                elif re.search(pattern_liquidation, texte_brut, flags=re.IGNORECASE):
                    extra_keywords.append("cloture_liquidation_tribunal_de_l_entreprise")
            #rajouter else ici? 1b8a3b9f6d69a6ed271a5b1fabceaff959aeaff8150df0ce8a53fd11bd2e581d
            if re.search(r"\bdissolution\s+judiciaire\b", texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("dissolution_judiciaire_tribunal_de_l_entreprise")
            if re.search(pattern_designation_mandataire, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("designation_mandataire_tribunal_de_l_entreprise")
            if re.search(pattern_liquidation_bis, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("ouverture_faillite_tribunal_de_l_entreprise")
            if re.search(pattern_delai_modere, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("delai_modere_tribunal_de_l_entreprise")

            if re.search(pattern_ouverture, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("ouverture_faillite_tribunal_de_l_entreprise")

            if re.search(pattern_interdiction, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("interdiction_gestion_tribunal_de_l_entreprise")

            # Effacement : priorité au refus, ensuite partiel, ensuite complet
            if re.search(r"\b(?:\(?[eE]\)?[\s:\.-]*)?effacement\b", texte_brut, flags=re.IGNORECASE) and re.search(
                    r"\brefus[ée]?\b", texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("effacement_refusé_tribunal_de_l_entreprise")
            elif re.search(pattern_sans_effacement, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("sans_effacement_tribunal_de_l_entreprise")
            elif re.search(pattern_effacement_partiel, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("effacement_partiel_tribunal_de_l_entreprise")
            elif re.search(pattern_effacement, texte_brut, flags=re.IGNORECASE) or re.search(pattern_effacement_bis, texte_brut, flags=re.IGNORECASE) or re.search(pattern_effacement_ter, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("effacement_tribunal_de_l_entreprise")

            if re.search(pattern_remplacement_juge_commissaire, texte_brut, flags=re.IGNORECASE) or re.search(pattern_remplacement_juge_commissaire_bis, texte_brut, flags=re.IGNORECASE) :
                extra_keywords.append("remplacement_juge_commissaire_tribunal_de_l_entreprise")
            # Fallback intelligent, en tout dernier recours
            elif re.search(pattern_remplacement_administrateur, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("remplacement_administrateur_tribunal_de_l_entreprise")

            # pas vraiment utile?
            elif not any(k.startswith("cloture") or k.startswith("ouverture") for k in extra_keywords):
                if re.search(
                        r"(faillite\s+de\s*:?.{0,80}?(déclar[ée]e?|prononc[ée]e?))"
                        r"|\bfaillite\b.{0,80}?(déclar[ée]e?|prononc[ée]e?)",
                        texte_brut,
                        flags=re.IGNORECASE
                ):
                    extra_keywords.append("ouverture_faillite_tribunal_de_l_entreprise")
            if re.search(pattern_report_cessation_paiement, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("report_cessation_paiement_tribunal_de_l_entreprise")
            # Réorganisations
            reorg_tags = 0
            if re.search(pattern_ouverture_reorg, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("ouverture_reorganisation_tribunal_de_l_entreprise")
                reorg_tags += 1
            if re.search(pattern_prorogation_reorg, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("prorogation_reorganisation_tribunal_de_l_entreprise")
                reorg_tags += 1
            if re.search(pattern_nouveau_plan_reorg, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("nouveau_plan_reorganisation_tribunal_de_l_entreprise")
                reorg_tags += 1
            if re.search(pattern_homologation_plan, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("homologation_plan_tribunal_de_l_entreprise")
                reorg_tags += 1
            elif re.search(pattern_homologation_accord, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("homologation_accord_amiable_tribunal_de_l_entreprise")
                reorg_tags += 1
            elif re.search(pattern_revocation_plan_reorganisation_judiciaire, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("revocation_plan_reorganisation_judicaire_tribunal_de_l_entreprise")
                reorg_tags += 1

            if re.search(pattern_reorg_generique, texte_brut, flags=re.IGNORECASE) and reorg_tags == 0:
                extra_keywords.append("reorganisation_tribunal_de_l_entreprise")
            if re.search(pattern_accord_collectif, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("reorganisation_judiciaire_par_accord_collectif_tribunal_de_l_entreprise")
            # Autres
            if re.search(pattern_administrateur_provisoire, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("administrateur_provisoire_tribunal_de_l_entreprise")
            if re.search(pattern_excusabilite, texte_brut, flags=re.IGNORECASE):
                extra_keywords.append("excusable_tribunal_de_l_entreprise")

    tvas = extract_numero_tva(texte_brut)
    match_nn_all = re.findall(r'(\d{2})[\s.\-]?(\d{2})[\s.\-]?(\d{2})[\s.\-]?(\d{3})[\s.\-]?(\d{2})', texte_brut)
    match_nn_all = extract_names_and_nns(texte_brut)
    nns = [''.join(groups) for groups in match_nn_all] if match_nn_all else []
    doc_id = generate_doc_hash_from_html(texte_brut, date_doc)
    return (
        numac, date_doc, langue, texte_brut, url, keyword,
        tvas, title, subtitle, nns, extra_keywords, nom, date_naissance, adresse, date_jugement, nom_trib_entreprise, date_deces, extra_links, administrateur, doc_id
    )


def get_publication_pdfs_for_tva(session, tva, max_pages=7):
    base_url = "https://www.ejustice.just.fgov.be/cgi_tsv/article.pl"
    tva_clean = tva.lstrip("0")
    publications = []
    for page in range(1, max_pages + 1):
        url = f"{base_url}?language=fr&btw_search={tva_clean}&page={page}&la_search=f"
        response = retry(url, session)
        soup = BeautifulSoup(response.text, "html.parser")
        pdf_links = soup.find_all("a", href=re.compile(r"/tsv_pdf/"))
        if not pdf_links:
            break
        for link in pdf_links:
            publications.append("https://www.ejustice.just.fgov.be" + link["href"])
    return publications

# MAIN
final = []
with requests.Session() as session:
    raw_link_list = ask_belgian_monitor(session, from_date, to_date, keyword)

    link_list = raw_link_list  # on garde le nom pour compatibilité

    #print(f"[INFO] Liens collectés : {len(link_list)}")
    scrapped_data = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [
            executor.submit(
                scrap_informations_from_url,
                session, url, numac, date_doc, langue, keyword, title, subtitle
            )
            for (url, numac, date_doc, langue, keyword, title, subtitle) in link_list
        ]
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc=f"Scraping {keyword}"):
            result = future.result()
            if result is not None and isinstance(result, tuple) and len(result) >= 5:
                scrapped_data.append(result)
            else:
                print("[⚠️] Résultat invalide ignoré.")

# ✅ Supprime les None avant de les envoyer à Meilisearch
final.extend(scrapped_data)  # ou final = [r for r in scrapped_data if r is not None]


print("[INFO] Connexion à Meilisearch…")
client = meilisearch.Client("http://127.0.0.1:7700", 'TBVEHV1dBQBT7mVQpHXw2RXeICzQvONQ5p9CqI84gF4')
index_name = "moniteur_documents"

# ✅ Si l'index existe, on le supprime proprement
try:
    index = client.get_index(index_name)
    print("✅ Clé primaire de l'index :", index.primary_key)
    delete_task = index.delete()
    client.wait_for_task(delete_task.task_uid)
    print(f"[🗑️] Index '{index_name}' supprimé avec succès.")
except meilisearch.errors.MeilisearchApiError:
    print(f"[ℹ️] Aucun index existant à supprimer.")

# 🔄 Ensuite on recrée un nouvel index propre avec clé primaire
create_task = client.create_index(index_name, {"primaryKey": "id"})
client.wait_for_task(create_task.task_uid)
index = client.get_index(index_name)
print("✅ Index recréé avec clé primaire :", index.primary_key)

# ✅ Ajoute ces lignes ici (et non dans le try)
index.update_filterable_attributes(["keyword"])
index.update_searchable_attributes([
    "id","title", "keyword", "extra_keyword", "nom", "date_jugement", "TVA",
    "extra_keyword", "num_nat", "date_naissance", "adresse", "nom_trib_entreprise",
    "date_deces", "extra_links","administrateur"
])
index.update_displayed_attributes([
    "id","doc_hash", "title", "keyword", "extra_keyword", "nom", "date_jugement", "TVA",
    "num_nat", "date_naissance", "adresse", "nom_trib_entreprise", "date_deces",
    "extra_links", "administrateur", "text", "url"
])
last_task = index.get_tasks().results[-1]
client.wait_for_task(last_task.uid)


documents = []
with requests.Session() as session:

    for record in tqdm(final, desc="Préparation Meilisearch"):
        cleaned_url = clean_url(record[4])
        texte = record[3].strip()
        texte = texte.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        doc_hash = generate_doc_hash_from_html(record[3], record[1])  # ✅ Hash du texte brut + date
        doc = {
            "id": doc_hash,  # ✅ L’ID est celui généré dans scrap_informations_from_url
            "doc_hash": doc_hash,  # ✅ Tu peux aussi réutiliser cet ID comme hash si c’est ce que tu veux
            "date_document": record[1],
            "lang": record[2],
            "text": record[3],
            "url": cleaned_url,
            "keyword": record[5],
            "TVA": record[6],
            "title": record[7],
            "subtitle": record[8],
            "num_nat": record[9],
            "extra_keyword": record[10],  # <= AJOUTÉ
            "nom": record[11],  # Ajout du champ nom extrait ici
            "date_naissance": record[12],  # Ajout du champ nom extrait ici
            "adresse": record[13],  # Ajout du champ nom extrait ici
            "date_jugement": record[14],
            "nom_trib_entreprise": record[15],
            "date_deces": record[16],
            "extra_links": record[17],
            "administrateur": record[18],

        }
        #rien a faire dans meili mettre dans postgre
        #if record[6]:
            #doc["publications_pdfs"] = get_publication_pdfs_for_tva(session, record[6][0])
        documents.append(doc)

        if keyword == "terrorisme":
            if isinstance(record[9], list):
                doc["nom_terrorisme"] = [pair[0] for pair in record[9] if len(pair) == 2]
                doc["num_nat_terrorisme"] = [pair[1] for pair in record[9] if len(pair) == 2]


# 🔪 Fonction pour tronquer tout texte après le début du récit
def tronque_texte_apres_adresse(chaine):
    marqueurs = [
        " est décédé", " est décédée", " est morte",
        " sans laisser", " Avant de statuer", " le Tribunal",
        " article 4.33", " Tribunal de Première Instance"
    ]
    for m in marqueurs:
        if m in chaine:
            return chaine.split(m)[0].strip()
    return chaine.strip()

# 🧼 Nettoyage des champs adresse : suppression des doublons dans la liste
for doc in documents:
    adresse = doc.get("adresse")

    # Si c’est une chaîne → transforme en liste
    if isinstance(adresse, str):
        adresse = [adresse]

    if isinstance(adresse, list):
        seen = set()
        adresse_cleaned = []

        for a in adresse:
            if not a:
                continue

            # 🔄 Remplacer les virgules par des espaces et normaliser
            cleaned = a.replace(",", " ").strip()
            cleaned = re.sub(r'\s+', ' ', cleaned)

            # ✂️ Tronquer le texte si du récit est présent
            cleaned = tronque_texte_apres_adresse(cleaned)

            # ✅ Ajouter si unique
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                adresse_cleaned.append(cleaned)

        doc["adresse"] = adresse_cleaned if adresse_cleaned else None

if not documents:
    print("❌ Aucun document à indexer.")
    sys.exit(1)
# 🔁 Supprimer les doublons par ID (donc par URL nettoyée)
print("👉 DOC POUR MEILI", doc["url"], "| date_deces =", doc.get("date_deces"))
unique_docs = {}
for doc in documents:
    if doc["doc_hash"] not in unique_docs:
        unique_docs[doc["doc_hash"]] = doc
print(f"[📋] Total de documents avant déduplication : {len(documents)}")
seen_hashes = set()
deduped_docs = []

for doc in documents:
    if doc["doc_hash"] not in seen_hashes:
        seen_hashes.add(doc["doc_hash"])
        deduped_docs.append(doc)

documents = deduped_docs

# 🔍 Log des doublons avant déduplication
hash_to_docs = defaultdict(list)
for doc in documents:
    hash_to_docs[doc["doc_hash"]].append(doc)

print("\n=== Doublons internes détectés ===")
for h, docs in hash_to_docs.items():
    if len(docs) > 1:
        print(f"\n[🔁] doc_hash = {h} (×{len(docs)})")
        for d in docs:
            print(f" - URL: {d['url']} | Date: {d['date_document']}")

# 🔁 Ensuite, suppression des doublons par doc_hash (garde le + récent)
unique_docs = {}
for doc in sorted(documents, key=lambda d: d["date_document"], reverse=True):
    unique_docs[doc["doc_hash"]] = doc
documents = list(unique_docs.values())
print(f"[✅] Total après suppression des doublons : {len(documents)}")
print(f"[📉] Nombre de doublons supprimés : {len(final)} → {len(documents)}")
print(f"[🔍] Documents uniques pour Meilisearch (par doc_hash): {len(documents)}")

# Supprime explicitement tous les documents avec ces doc_hash
doc_ids = [doc["id"] for doc in documents]
#if doc_ids:
    #print(f"[🧹] Suppression des documents existants par ID ({len(doc_ids)} items)...")
    #task = index.delete_documents(doc_ids)
    #client.wait_for_task(task.task_uid)

batch_size = 1000
task_ids = []

for i in tqdm(range(0, len(documents), batch_size), desc="Envoi vers Meilisearch"):
    batch = documents[i:i + batch_size]

    # 🔍 Vérifie si un document n'a pas d'ID
    for doc in batch:
        if not doc.get("id"):
            print("❌ Document sans ID :", json.dumps(doc, indent=2))

    print("\n[🧾] Exemple de document envoyé à Meilisearch :")
    print(json.dumps(batch[0], indent=2))

    task = index.add_documents(batch)
    task_ids.append(task.task_uid)


# ✅ Attendre que toutes les tasks soient terminées à la fin
for uid in task_ids:
    index.wait_for_task(uid, timeout_in_ms=150_000)



# 🧪 TEST : Vérifie que le document a bien été indexé avec l'ID attendu
import json
test_id = documents[0]["id"]
print(f"\n🔍 Test récupération document avec ID = {test_id}")
try:
    found_doc = index.get_document(test_id)
    print("✅ Document trouvé dans Meilisearch :")
    print(json.dumps(dict(found_doc), indent=2))
except meilisearch.errors.MeilisearchApiError:
    print("❌ Document non trouvé par ID dans Meilisearch.")

print("[📥] Connexion à PostgreSQL…")

conn = psycopg2.connect(
    dbname="monsite_db",
    user="postgres",
    password="Jamesbond007colibri+",
    host="localhost",
    port="5432"
)
cur = conn.cursor()
cur.execute("SET search_path TO public;")
cur.execute("SELECT version();")
print(">> PostgreSQL connecté :", cur.fetchone()[0])

# 👇 Affiche le nom de la base de données connectée
cur.execute("SELECT current_database();")
print(">> Base utilisée :", cur.fetchone()[0])

# ➕ Active l'extension pgvector
# Nous supprimons cette ligne car il n'y a plus d'index de type `vector`
# cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

print("🛠️ Recréation de la table PostgreSQL moniteur_documents...")
cur.execute("""
    CREATE TABLE IF NOT EXISTS moniteur_documents (
    id          SERIAL PRIMARY KEY,
    date_document    DATE,
    lang        TEXT,
    text        TEXT,
    url         TEXT,
    doc_hash    TEXT UNIQUE,
    keyword     TEXT,
    tva         TEXT[],
    titre       TEXT,
    sous_titre  TEXT,
    num_nat     TEXT[],
    extra_keyword TEXT,
    nom         TEXT,
    date_naissance        TEXT,
    adresse        TEXT,
    date_jugement TEXT,
    nom_trib_entreprise TEXT,
    date_deces TEXT,
    extra_links TEXT,
    administrateur TEXT  
);
""")

conn.commit()
print("✅ Table recréée sans index GIN")

# Nous supprimons également la vérification des embeddings dans la table PostgreSQL
# cur.execute("""
#     SELECT t.typname
#     FROM pg_type t
#     JOIN pg_attribute a ON a.atttypid = t.oid
#     JOIN pg_class c ON a.attrelid = c.oid
#     WHERE c.relname = 'moniteur_documents' AND a.attname = 'embedding';
# """)
# print("[🧬] Type réel de 'embedding' dans PostgreSQL :", cur.fetchone())

print("[📦] Insertion dans PostgreSQL (sans vecteurs)…")

# Insertion des documents sans embeddings
for doc in tqdm(documents, desc="PostgreSQL Insert"):
    text = doc.get("text", "").strip()

    # Suppression de l'encodage des embeddings avec SentenceTransformer
    # embedding = model.encode(text).tolist() if text else None

    # Insertion des données dans la base PostgreSQL sans embeddings
    cur.execute("""
    INSERT INTO moniteur_documents (
    date_document, lang, text, url, doc_hash, keyword, tva, titre, subtitle, num_nat, extra_keyword,nom, date_naissance, adresse, date_jugement, nom_trib_entreprise, date_deces, extra_links, administrateur
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s,%s,%s, %s,%s,%s, %s)
ON CONFLICT (doc_hash) DO NOTHING
""", (
    doc["date_document"],
    doc["lang"],
    text,
    doc["url"],
    doc["doc_hash"],
    doc["keyword"],
    doc["TVA"],
    doc["title"],
    doc["subtitle"],
    doc["num_nat"],
    doc.get("extra_keyword"),
    doc["nom"],
    doc["date_naissance"],
    doc["adresse"],
    doc["date_jugement"],
    doc["nom_trib_entreprise"],
    doc["date_deces"],
    doc.get("extra_links"),
    doc["administrateur"]
))

conn.commit()
cur.close()
conn.close()
print("[✅] Insertion PostgreSQL terminée.")
