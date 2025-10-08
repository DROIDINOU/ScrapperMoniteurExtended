# --- Imports standards ---
import os
import pickle
import hashlib
import csv
import re
import unicodedata
import requests


# --- Bibliothèques tierces ---
from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from typing import List, Any, Optional, Tuple

# --- Modules internes au projet ---
from Constante.mesconstantes import JOURMAPBIS, MOISMAPBIS, ANNEEMAPBIS, TVA_INSTITUTIONS


# TODO:
#  Rajouter dans nettoyer_adresses_par_keyword des patterns a nettoyer au fur et a mesure de l evolution du \
#  scrapping -> faut un log pour quasi tout ....
# note:
#   contrairement à set(out), l’ordre d’apparition est conservé (car depuis Python 3.7+,
#   les dicts gardent l’ordre d’insertion).
#   dict.fromkeys(seq) crée un dictionnaire dont les clés sont les éléments de la liste.


# ----------------------------------------------------------------------------------------------------------------------
#                                         FONCTIONS ACCES DE FICHIERS
# ----------------------------------------------------------------------------------------------------------------------


# Exemple :
# Entrée → "data/users.csv"
# Sortie → ".cache/users.denoms.pkl"
def _cache_path_for(csv_path: str) -> str:
    base = os.path.splitext(os.path.basename(csv_path))[0]
    os.makedirs(".cache", exist_ok=True)
    return os.path.join(".cache", f"{base}.denoms.pkl")


# Cette fonction est souvent utilisée dans un mécanisme de cache :
# on compare la date de modification du CSV avec celle d’un fichier de cache
# (par exemple .cache/clients.denoms.pkl) pour savoir si le cache est encore valide ou s’il faut le régénérer.
def _csv_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


# depend du repertoire courant
def chemin_csv(nom_fichier: str) -> str:
    return os.path.abspath(os.path.join("Datas", nom_fichier))


# ne depend pas du repertoire courant (-> plus robuste)
def chemin_csv_abs(nom_fichier: str) -> str:
    """Retourne le chemin absolu vers un fichier CSV situé dans le dossier 'Datas' (au même niveau que 'Scripts')."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))  # <- remonte 2 niveaux
    return os.path.join(base_dir, 'Datas', nom_fichier)


def chemin_log(nom_fichier: str = "succession.log") -> str:
    """
    Retourne le chemin absolu du fichier de log, situé dans le dossier 'logs',
    depuis la racine du projet (où est situé le dossier Utilitaire).
    """
    # Dossier du projet = 2 niveaux au-dessus de ce fichier
    projet_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(projet_dir, "logs", nom_fichier)


# ----------------------------------------------------------------------------------------------------------------------
#                                         FONCTIONS DE NETTOYAGE D'URL
# ----------------------------------------------------------------------------------------------------------------------
def clean_url(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    # Supprimer 'exp' de la query string s'il existe
    query.pop("exp", None)

    # Reconstruire l'URL sans 'exp'
    cleaned_query = urlencode(query, doseq=True)
    cleaned_url = urlunparse(parsed._replace(query=cleaned_query))
    return cleaned_url
# ----------------------------------------------------------------------------------------------------------------------
#                                         FONCTIONS ET VARIABLE DE NORMALISATION
# ----------------------------------------------------------------------------------------------------------------------
# ____________________________________________________________
    # Extrait un texte propre à partir d’un objet BeautifulSoup.
    # Par défaut, supprime la section 'Liens :' et ses liens.
    # Passez remove_links=False pour ne pas la supprimer.
# ____________________________________________________________


# --------------------------------------------------------------------------------------
# UNICODE_SPACES_MAP : Créer un dictionnaire de correspondance Unicode
# pour remplacer certains espaces spéciaux invisibles par un espace standard (" ").
# _norm_spaces :
# --------------------------------------------------------------------------------------
UNICODE_SPACES_MAP = dict.fromkeys(map(ord, "\u00A0\u202F\u2007\u2009\u200A\u200B"), " ")


def extract_clean_text(soup, remove_links: bool = True):
    # ⬇️ Comportement inchangé par défaut
    if remove_links:
        for el in soup.select(
                'h2.links-title, a.links-link, #link-text, .links, button#link-button, button.button'
        ):
            el.decompose()

    output = []
    last_was_tag = None

    for elem in soup.descendants:
        if isinstance(elem, NavigableString):
            txt = elem.strip()
            if txt:
                if last_was_tag in ("font", "sup", "text"):
                    output.append(" ")
                output.append(txt)
                last_was_tag = "text"
        elif isinstance(elem, Tag):
            tag_name = elem.name.lower()
            if tag_name == "br":
                output.append(" ")
                last_was_tag = "br"
            elif tag_name == "sup":
                sup_text = elem.get_text(strip=True)
                if output and output[-1].isdigit():
                    output[-1] = output[-1] + sup_text
                else:
                    output.append(sup_text)
                last_was_tag = "sup"
            else:
                last_was_tag = tag_name

    text = "".join(output)
    text = text.replace('\u00a0', ' ').replace('\u200b', '').replace('\ufeff', '')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# normalisation des espaces
def norm_spaces(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\xa0", " ").replace("\u202f", " ").replace("\u2009", " ").replace("\u200a", " ")
    return re.sub(r"\s+", " ", s).strip()


# Supprime les accents/diacritiques d'une chaîne Unicode.
# Paramètres:
# - s: chaîne d'entrée.
# - compatibility: si True, utilise NFKD (décomposition de compatibilité),
# sinon NFD (décomposition canonique).
# - lower: si True, convertit la chaîne résultante en minuscules.
# Retour:
# - nouvelle chaîne avec les marques non-spacing (Mn) retirées.
def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


# ----------------------------------------------------------------------------------------------------------------------
#                                 FONCTIONS DE NETTOYAGE D'ERREURS RECURENTES
#   1 : normaliser_espaces_invisibles : Nettoie une chaîne de texte en remplaçant les espaces "invisibles"
#       (espaces insécables, espaces fines, etc.) par des espaces normaux,
#       et en supprimant les espaces zéro largeur.
#   2 : strip_html_tags : supprime les balises html du texte
#   3 : fonctions suppression erreurs d'ocr (doublons)
#       - remove_duplicate_paragraphs - remove_av_parentheses - dedupe_phrases_ocr
#   4 : norm_er : supprimer double er pour les dates
# ----------------------------------------------------------------------------------------------------------------------
# 1 : Nettoie une chaîne de texte en remplaçant les espaces "invisibles"
def normaliser_espaces_invisibles(s: str) -> str:
    if not s:
        return ""
    # Remplace les espaces invisibles par un vrai espace
    return s.replace('\u00A0', ' ') \
            .replace('\u202F', ' ') \
            .replace('\u2009', ' ') \
            .replace('\u200A', ' ') \
            .replace('\u200B', '')  \
            .strip()\
            .lower()\


# 2 : strip_html_tags : supprime les balises html du texte
#     Supprime toutes les balises HTML d'une chaîne de texte.
#     Utilise une expression régulière pour matcher toute séquence de type <...>
#     (non-gourmande, pour ne pas avaler trop de contenu), puis la remplace par une chaîne vide.
def strip_html_tags(text):
    return re.sub('<.*?>', '', text)


# --------------------------
# 3 Suppressions erreurs OCR
# --------------------------
# Supprime paragraphes dedoublés
def remove_duplicate_paragraphs(text: str) -> str:
    # Découpe à chaque "Déclaration d'acceptation"
    blocks = re.split(r'(?=Déclaration d\'acceptation)', text)

    seen = set()
    uniques = []
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        if b not in seen:
            seen.add(b)
            uniques.append(b)

    # On recolle les blocs avec un espace (ou double saut de ligne si tu préfères)
    return " ".join(uniques)


# supprime tutes les parenthèses qui commencent par Av / Av.
def remove_av_parentheses(texte: str) -> str:
    return re.sub(r"\(Av\.?.*?\)", "", texte, flags=re.IGNORECASE)


# Supprime des doublons OCR fréquents comme 'Succession en déshérence Succession en déshérence'
def dedupe_phrases_ocr(texte: str) -> str:
    # Cas 1 : duplication directe mot pour mot
    texte = re.sub(r"(Succession en déshérence)\s+\1", r"\1", texte, flags=re.IGNORECASE)
    # Cas 2 : tu peux prévoir d’autres séquences récurrentes
    # (ex. "Administration générale ... Administration générale ...")
    # texte = re.sub(r"(Administration générale de la documentation patrimoniale),?\s+\1",
    # r"\1", texte, flags=re.IGNORECASE)
    return texte


# 4 Supprimer double er pour les dates
def norm_er(x):
    if isinstance(x, str):
            x = re.sub(r"\b(\d{1,2})\s*er\s*er\b", r"\1er", x)
            x = re.sub(r"\b(\d{1,2})\s*er\b", r"\1", x)
            return x
    return x


# ----------------------------------------------------------------------------------------------------------------------
#                                         FONCTIONS UTILISEES POUR OU SUR LES DATES
# ----------------------------------------------------------------------------------------------------------------------
def _clean_dates_and_grands_nombres(s: str) -> str:
    """Supprime les motifs de type dates + grands nombres (>6 chiffres, avec ou sans séparateur)."""
    months = r"(janvier|février|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|décembre)"

    # Dates classiques
    s = re.sub(rf"\b\d{{1,2}}\s+{months}\s+\d{{4}}\b", "", s, flags=re.IGNORECASE)
    s = re.sub(rf"\b{months}\s+\d{{4}}\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", "", s)
    s = re.sub(r"\b(19|20)\d{2}\b", "", s)

    # Suites de plus de 6 chiffres (avec ou sans séparateurs)
    s = re.sub(r"\b\d{7,}\b", "", s)                         # 1234567
    s = re.sub(r"\b(?:\d[\.\-]){6,}\d\b", "", s)             # 85.08.11-207.58 etc.

    return s


# Convertit une date en lettres (ex : 'trente mai deux mil vingt-trois')
# en format '30 mai 2023'
# utilise dans extraction_date_jugement.py
def convert_french_text_date_to_numeric(text_date):

    words = text_date.lower().strip().split()

    # Créer une date si les 3 parties sont reconnaissables
    jour = next((v for k, v in JOURMAPBIS.items() if k in text_date), None)
    mois = next((v for k, v in MOISMAPBIS.items() if k in text_date), None)
    annee = next((v for k, v in ANNEEMAPBIS.items() if k in text_date), None)

    if jour and mois and annee:
        return f"{jour} {mois} {annee}"

    return None


# transforme mois en lettre en mois en chiffre
# utilise dans extraction_date_jugement.py
def get_month_name(month_num):
    mois = [
        "", "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"
    ]
    return mois[month_num] if 1 <= month_num <= 12 else ""


# __________________________________________________
# Fonctions utilisees dans tribunal_premiere_instance_keyword
# --------------------------------------------------
def normalize_mois(val):
    mots = {
        "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
        "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
        "onze": 11, "douze": 12
    }
    if val.isdigit():
        return int(val)
    return mots.get(val.lower(), None)


# Petit normaliseur des nombres en mots → int (pour le tag "…_X_ans")
# on a pas besoin de tout la generalement c est tjs les mêmes nombres d'annees
_WORD2INT = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9,
    "dix": 10, "onze": 11, "douze": 12, "quinze": 15, "vingt": 20
}


def normalize_annees(val: str) -> int | None:
    v = (val or "").strip().lower()
    return int(v) if v.isdigit() else _WORD2INT.get(v)


def to_list_dates(x):
    """Normalise un champ date (None/str/list/tuple) en liste de chaînes non vides."""
    if x is None:
        return []
    if isinstance(x, str):
        return [x] if x.strip() else []
    if isinstance(x, (list, tuple)):
        return [s for s in x if isinstance(s, str) and s.strip()]
    return []


def clean_date_jugement(raw):
    """
    Extrait uniquement la date au format '16 juin 2025'
    et ignore ce qui suit (points, texte...).
    """
    mois = (
        "janvier|février|mars|avril|mai|juin|juillet|août|"
        "septembre|octobre|novembre|décembre"
    )
    pattern_date = rf"\b\d{{1,2}}\s+(?:{mois})\s+\d{{4}}\b"
    match = re.search(pattern_date, raw, flags=re.IGNORECASE)
    if match:
        return match.group(0).strip()
    return None


# ----------------------------------------------------------------------------------------------------------------------
#                                 FONCTIONS POUR NETTOYER DOC NOM
# ----------------------------------------------------------------------------------------------------------------------
def filtrer_doc(doc: dict) -> dict:
    """
    Nettoie les champs noms d'un document :
    - supprime les records invalides
    - filtre les canonicals
    - filtre les aliases_flat
    - recalcule doc["nom"] avec le premier canonical valide
    """
    def est_nom_valide(nom: str) -> bool:
        STOPWORDS = {"de", "la", "le", "et", "des", "du", "l’", "l'"}
        EXCLUSIONWORD = {
            "de l'intéressé", "et remplacée", "de la",
            "l'intéressé et", "l'intéressé", "suite au", "suite aux"
        }

        if not isinstance(nom, str):
            return False

        # Normalisation basique
        normalise = normaliser_espaces_invisibles(nom.strip().lower()).replace("’", "'")

        # Mot ou expression interdite
        if normalise in {w.replace("’", "'").lower() for w in EXCLUSIONWORD}:
            return False

        tokens = [t for t in nom.strip().split() if t]
        if len(tokens) < 2:  # doit avoir au moins prénom + nom
            return False
        if len("".join(tokens)) < 3:  # trop court
            return False

        # Tous les tokens sont des stopwords
        if all(t.lower() in STOPWORDS for t in tokens):
            return False

        return True

    # --- Filtrage des records
    if "records" in doc and isinstance(doc["records"], list):
        new_records = []
        for r in doc["records"]:
            if not isinstance(r, dict):
                continue
            nom = r.get("canonical", "")
            if isinstance(nom, str) and nom.strip() and est_nom_valide(nom):
                new_records.append(r)
        doc["records"] = new_records

    # --- Filtrage des canonicals
    if "canonicals" in doc and isinstance(doc["canonicals"], list):
        doc["canonicals"] = [
            c for c in doc["canonicals"]
            if isinstance(c, str) and c.strip() and est_nom_valide(c)
        ]

    # --- Filtrage des aliases_flat
    if "aliases_flat" in doc and isinstance(doc["aliases_flat"], list):
        doc["aliases_flat"] = [
            a for a in doc["aliases_flat"]
            if isinstance(a, str) and a.strip() and est_nom_valide(a)
        ]

    # --- Met à jour doc["nom"] avec le premier canonical valide
    if doc.get("canonicals"):
        doc["nom"] = doc["canonicals"][0]
    elif doc.get("records"):
        doc["nom"] = doc["records"][0].get("canonical")
    elif doc.get("aliases_flat"):
        doc["nom"] = doc["aliases_flat"][0]
    else:
        doc["nom"] = None

    return doc

# ----------------------------------------------------------------------------------------------------------------------
#                                 FONCTIONS UTILISEES POUR LES NUMEROS RN
# ----------------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------
# normalise les rn
def _norm_nrn(yy, mm, dd, bloc, suffix):
    yy = yy.zfill(2)
    mm = mm.zfill(2)
    dd = dd.zfill(2)
    bloc = bloc.zfill(3)
    suffix = suffix.zfill(2)
    return f"{yy}.{mm}.{dd}-{bloc}.{suffix}"
# Vérifie qu'un numéro national belge (NRN) est valide avec le contrôle modulo 97.
# Nrn est attendu au format 'YYMMDDXXXCD' (11 chiffres sans séparateurs).


def is_valid_nrn(nrn: str) -> bool:
    digits = re.sub(r"\D", "", nrn)  # enlève les séparateurs éventuels
    if len(digits) != 11:
        return False

    base = digits[:9]
    cd = int(digits[9:])
    # Cas avant 2000
    if 97 - (int(base) % 97) == cd:
        return True
    # Cas après 2000 (préfixe "2")
    if 97 - (int("2" + base) % 97) == cd:
        return True

    return False


#  Fonction principale d'extraction des numéros RN
def extract_nrn_variants(text: str):
    # Définit les séparateurs possibles dans un numéro de registre national (NRN)
    # Ex : "51.12.25-387.18" → séparateurs peuvent être ".", "-", "/", ou espace
    _NRSEP = r"[.\-/ ]"
    # Définit les libellés textuels qui peuvent précéder un NRN
    # Ex : "NRN: 51.12.25-387.18" ou "Registre national 51-12-25 387 18"
    LABEL = r"(?:NRN|R\.?\s*N\.?|REGISTRE\s+NATIONAL)"
    out = []

    # 1) NRN avec séparateurs
    rx_nrn = rf"\b(\d{{2}}){_NRSEP}(\d{{2}}){_NRSEP}(\d{{2}}){_NRSEP}(\d{{3}}){_NRSEP}(\d{{2}})\b"
    for yy, mm, dd, bloc, suffix in re.findall(rx_nrn, text):
        nrn = f"{yy}{mm}{dd}{bloc}{suffix}"
        if is_valid_nrn(nrn):
            out.append(_norm_nrn(yy, mm, dd, bloc, suffix))

    # 2) NRN collé (11 chiffres)
    rx_nrn_plain = r"\b(\d{2})(\d{2})(\d{2})(\d{3})(\d{2})\b"
    for yy, mm, dd, bloc, suffix in re.findall(rx_nrn_plain, text):
        nrn = f"{yy}{mm}{dd}{bloc}{suffix}"
        if is_valid_nrn(nrn):
            out.append(_norm_nrn(yy, mm, dd, bloc, suffix))

    # 3) NRN précédé d’un libellé
    rx_labeled = rf"(?:\b|[\(\[])\s*(?:{LABEL})\s*[:\-]?\s*(\d{{2}}){_NRSEP}(\d{{2}}){_NRSEP}(\d{{2}}){_NRSEP}(\d{{3}}){_NRSEP}(\d{{2}})"
    for yy, mm, dd, bloc, suffix in re.findall(rx_labeled, text, flags=re.IGNORECASE):
        nrn = f"{yy}{mm}{dd}{bloc}{suffix}"
        if is_valid_nrn(nrn):
            out.append(_norm_nrn(yy, mm, dd, bloc, suffix))
    # Déduplication
    return list(dict.fromkeys(out))


# transforme en format bce avec .
def format_bce(n: str | None) -> str | None:
    if not n:
        return None
    d = re.sub(r"\D", "", str(n))
    if len(d) == 9:
        d = "0" + d
    if len(d) != 10:
        return None
    return f"{d[:4]}.{d[4:7]}.{d[7:]}"


# ----------------------------------------------------------------------------------------------------------------------
#                                 FONCTIONS UTILISEES POUR LES NUMEROS DE TVA
# ----------------------------------------------------------------------------------------------------------------------
# transforme en format bce avec .
def format_bce(n: str | None) -> str | None:
    if not n:
        return None
    d = re.sub(r"\D", "", str(n))
    if len(d) == 9:
        d = "0" + d
    if len(d) != 10:
        return None
    return f"{d[:4]}.{d[4:7]}.{d[7:]}"


# Retourne que les chiffres de la chaine
# Utilise pour transformer les tva avec points (0514.194.192)
# en tva sans point (0514194192)
def digits_only(s: str) -> str:
    return re.sub(r"\D+", "", s or "")


# extraits les numéros de tva
# Exemples détectés : 1008.529.190, 0108 529 190, 0423456789, 05427-15196, etc.
def extract_numero_tva(text: str, format_output: bool = False) -> list[str]:

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
    tvas = [x for x in tvas if not (x in seen or seen.add(x))]

    # 🔹 3. Exclure ceux qui sont dans la liste TVA_ETAT
    if TVA_INSTITUTIONS:
        # on normalise sans points pour comparer
        tva_set = {x.replace(".", "") for x in TVA_INSTITUTIONS}
        tvas = [x for x in tvas if x.replace(".", "") not in tva_set]

    return tvas


# ----------------------------------------------------------------------------------------------------------------------
#                                         FONCTIONS AUTRES
# ----------------------------------------------------------------------------------------------------------------------
# ____________________________________________________________
    # Retourne True si 'erratum', 'errata' ou 'ordonnance rectificative' est détecté
    # dans les 400 premiers caractères du texte HTML. Sinon False.
# ____________________________________________________________
def detect_erratum(texte_html):

    soup = BeautifulSoup(texte_html, 'html.parser')
    full_text = soup.get_text(separator=" ").strip().lower()
    snippet = full_text[:400]

    if re.search(r"\berrat(?:um|a)\b", snippet):
        return True

    if re.search(r"\bordonnance\s+rectificative\b", snippet):
        return True

    return False



# -----------------------------------------------------------------------------
# 🧩 Fonction : generate_doc_hash_from_html(html, date_doc)
# -----------------------------------------------------------------------------
# Cette fonction génère une empreinte unique (hash SHA-256) à partir du contenu
# textuel nettoyé d’une page HTML et d’une date donnée.
#
# 🔹 Étapes :
#   1. Analyse du HTML avec BeautifulSoup.
#   2. Suppression des balises inutiles (script, style, font, span, mark).
#   3. Extraction du texte brut, en supprimant les liens et métadonnées propres
#      au site ejustice.just.fgov.be.
#   4. Mise en minuscules et normalisation du texte (suppression ponctuation,
#      espaces multiples, etc.).
#   5. Concaténation de la date du document avec le texte nettoyé.
#   6. Calcul d’un hash SHA-256 pour obtenir une signature unique et stable.
#
# 💡 Utilité :
#   Sert à identifier de manière unique un document juridique ou administratif
#   à partir de son contenu et de sa date, même si son format HTML change.
# -----------------------------------------------------------------------------
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


# ----------------------------------------------------------------------------------------------------------------------
#                                 FONCTIONS UTILISEES POUR LES NOMS
# ----------------------------------------------------------------------------------------------------------------------
def names_list_from_nom(nom):
    """
    Extrait la liste des noms 'canonicals' depuis le champ nom (voir structure fournie).
    Fallbacks si le format varie.
    """
    if not nom:
        return []
    if isinstance(nom, dict):
        if isinstance(nom.get("canonicals"), list) and nom["canonicals"]:
            return [s for s in nom["canonicals"] if isinstance(s, str) and s.strip()]
        if isinstance(nom.get("records"), list):
            out = []
            for r in nom["records"]:
                if isinstance(r, dict) and isinstance(r.get("canonical"), str) and r["canonical"].strip():
                    out.append(r["canonical"].strip())
            return out
        # fallback générique
        vals = []
        for k in ("aliases_flat", "aliases"):
            v = nom.get(k)
            if isinstance(v, list):
                vals.extend([s for s in v if isinstance(s, str) and s.strip()])
        return vals
    if isinstance(nom, list):
        return [s for s in nom if isinstance(s, str) and s.strip()]
    if isinstance(nom, str):
        return [nom] if nom.strip() else []
    return []


def is_entite_publique(entite_bce: str) -> bool:
    s = re.sub(r"\D", "", entite_bce or "")
    if len(s) == 9:
        s = "0" + s
    return s.startswith("0200")
# ----------------------------------------------------------------------------------------------------------------------
#                                        NETTOYAGE DES ADRESSES
# 1 Nettoyer en tronquant le texte (nettoyage final dans mainscrapper.py)
# 2 Nettoie une liste d'adresses selon un mot-clé thématique (keyword). (nettoyage final dans mainscrapper.py)
# 3 Nettoie une adresse en supprimant un artefact fréquent : un 'a' ou 'à' (avec ou sans accent) placé juste avant
#   (nettoyage dans extraction_adresses_moniteur.py)
# 4 couper_fin_adresse
# ----------------------------------------------------------------------------------------------------------------------


# 1 Fonction pour tronquer tout texte après le début du récit
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


# 2 Nettoie une liste d'adresses selon un mot-clé thématique (keyword)
def nettoyer_adresses_par_keyword(adresses, keyword):

    if not adresses:
        return []

    nettoyees = []

    for adr in adresses:
        original = adr  # sauvegarde avant nettoyage
        adr = normaliser_espaces_invisibles(adr)
        # Normalisation espaces
        cleaned = re.sub(r'\s+', ' ', adr).strip()

        if cleaned:
            nettoyees.append(cleaned)
        else:
            # fallback : garder version originale si nettoyage vide
            nettoyees.append(original.strip())

    return nettoyees


# 3 Nettoie une adresse en supprimant un artefact fréquent :
# un 'a' ou 'à' (avec ou sans accent) placé juste avant
# un code postal suivi d'une ville.
# Exemple :
# "à 4032 Liège" → "4032 Liège"
# "a 1000 Bruxelles" → "1000 Bruxelles"
def nettoyer_adresse(adresse: str) -> str:
    # Regex : cherche "à " ou "a " devant 4 chiffres + ville et supprime
    return re.sub(r"\b[àa]\s+(?=\d{4}\s+[A-ZÀ-Ÿ])", "", adresse, flags=re.IGNORECASE)


#  4 Coupe la fin d'une adresse dès qu'apparaissent certains mots-clés
# indiquant qu'on sort du champ adresse (éléments de procédure, infos perso, etc.).
# Mots-clés déclencheurs : "Signifié", "N°", "Casier", "Nationalité",
# "Né", "Date", "le <jour> <mois>".
# Exemple : "1000 Bruxelles, Rue de la Loi 12 Signifié le 03/01/2024"  → "1000 Bruxelles, Rue de la Loi 12"
def couper_fin_adresse(adresse: str) -> str:

    # Split l'adresse au premier mot-clé trouvé et garde uniquement la partie avant
    adresse = re.split(
        r"\b(Signifi[eé]|N°|Casier|Nationalit[eé]|Né[e]?\b|Date|le\s+\d{1,2}\s+\w+)",
        adresse
    )[0]
    return adresse.strip()


# ----------------------------------------------------------------------------------------------------------------------
#     Extrait l'index de page à partir de l'URL d'un PDF contenant '#page=X'.
#     Retourne un entier indexé à 0 (utilisable avec PyMuPDF).
#     Si aucun numéro de page n'est trouvé, retourne None.
# ----------------------------------------------------------------------------------------------------------------------
def extract_page_index_from_url(pdf_url):
    match = re.search(r'#page=(\d+)', pdf_url)
    if match:
        page_number = int(match.group(1))
        return page_number - 1  # PyMuPDF indexe à partir de 0
    return None


# va falloir étendre cela je pense
def _norm(s: str) -> str:
    s = s or ""
    s = s.lower()
    s = s.replace("’", "'")
    # unifier abréviations courantes
    s = re.sub(r"\bav\.?\b", "avenue", s)
    s = re.sub(r"\bbd\b", "boulevard", s)
    s = re.sub(r"\ball[ée]e\b", "allee", s)  # évite la variation é/ée
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# ---------------------------------------------------------------------------------------------------------------------
#                                    VERIFICATION LISTE ADRESSES A CODE POSTAL ET NUMERO
#                                    utilisé dans main pour verifier que la premiere adresse
#                                    qui est l'adresse de la personne concernée est correcte
# ----------------------------------------------------------------------------------------------------------------------
# extrait le code postal (pas de 0 en debut de chaine)
CP_RX = re.compile(r"\b([1-9]\d{3})\b")
# Même idée que dans l’extraction, mais plus tolérante pour la validation
DASH_CHARS = r"\-\u2010-\u2015"  # -, ‐, ‒, –, —, ―
# Avec ou sans libellé "num./n°/nr" juste avant
NUM_LABEL = r"(?:num(?:[ée]ro)?\.?|n[°ºo]?\.?|nr\.?)"
# Autorise espaces autour de / ou - (ex: "60 / 0-1")
NUM_TOKEN_LOOSE = rf"\d{{1,4}}(?:[A-Za-z](?!\s*\.))?(?:\s*[/[{DASH_CHARS}]]\s*[A-ZÀ-ÿ0-9\-]+)?"
ADDR_NUM_RX = re.compile(rf"(?:{NUM_LABEL}\s*)?({NUM_TOKEN_LOOSE})", re.IGNORECASE)
#     True s'il y a au moins 1 CP (4 chiffres) ET au moins 1 numéro d'adresse
#     au sens de l’extraction (NUM_TOKEN tolérant), distinct du/des CP.
#     Ex:
#       - '7000 Mons, Boulevard Sainctelette 60 / 0-1' -> True
#       - '4537 Verlaine, Grand-Route 245/0011'        -> True
#       - '4802 Verviers, avenue de Thiervaux 2 322'   -> True (deux nombres distincts)
#       - '5100 Namur'                                  -> False
def has_cp_plus_other_number_aligned(s: str) -> bool:

    s = norm_spaces(s)
    if not s:
        return False

    cps = set(CP_RX.findall(s))
    if not cps:
        return False

    # Tous les tokens "numéro d'adresse" style extraction
    addr_nums = [m.group(1) for m in ADDR_NUM_RX.finditer(s)]
    if not addr_nums:
        # Dernier recours : s'il y a deux nombres "simples" ≠ CP (ex: "2 322")
        # on les comptera ci-dessous via le scan générique
        pass

    # 1) s'il y a un token d'adresse dont la partie de tête (digits) ≠ CP → OK
    for tok in addr_nums:
        head = re.match(r"\d{1,4}", tok)
        if head and head.group(0) not in cps:
            return True

    # 2) fallback : compter tous les nombres 1–4 chiffres (avec lettre optionnelle) hors CP.
    #    Ça couvre le cas "2 322" sans slash ni tiret.
    simple_nums = [m.group(1) for m in re.finditer(r"\b(\d{1,4}[A-Za-z]?)\b", s)]
    # Enlève les CP exacts
    simple_nums = [n for n in simple_nums if n not in cps]
    # S'il reste au moins un nombre hors CP -> True
    return len(simple_nums) >= 1

# ---------------------------------------------------------------------------------------------------------------------
#                                         ORDONNANCEMENT DES ADRESSES EN FONCTION DU NOM
#                         (Permet de mettre l'adresse de la personne visee en 1 dans la liste d'adresses)
#                                 ATTENTION POUR SUCCESSION ON A DES LISTES DE NOM (A MODIFIER!)
# ----------------------------------------------------------------------------------------------------------------------

# ---------------------------
# Recherche positions dans le texte
# ---------------------------

# ------------------------------------------------------------------------------
# Renvoie la position (index) de la première occurrence de `pat` dans `T`,
# mais uniquement si elle apparaît APRÈS une position donnée `start`.
# Si `pat` est vide ou non trouvé → retourne None.
# Exemple :
#    T = "abc 123 def 456"
#    _first_after(T, "456", 5) → 12
#    _first_after(T, "123", 10) → None
# ------------------------------------------------------------------------------


def _first_after(text: str, pat: Optional[str], start: int) -> Optional[int]:
    if not pat:
        return None
    i = text.find(pat, start)
    return i if i >= 0 else None


# ------------------------------------------------------------------------------
# Renvoie la position (index) de la première occurrence de `pat` dans `T`,
# sans contrainte de position de départ.
# Si `pat` est vide ou non trouvé → retourne None.
# Exemple :
#    T = "abc 123 def 456"
#    _first_any(T, "123") → 4
#    _first_any(T, "zzz") → None
# ------------------------------------------------------------------------------
def _first_any(text: str, pat: Optional[str]) -> Optional[int]:
    if not pat:
        return None
    i = text.find(pat)
    return i if i >= 0 else None
# --------------------------------------------------------------------------------------------
# _NUM_RX : motif pour capturer un "numéro d'adresse" (souvent après le nom de la voie).
# Il correspond à :
# - 1 à 4 chiffres          → ex: 1, 23, 504, 9999
# - suivis optionnellement d'une lettre (sans point) → ex: 23A, 41b
# - éventuellement suivi d’un "/suffixe"             → ex: 28/001, 45/B, 56/123A
#
# Ne capture pas :
# - les "492/4" ou "499/7" (articles de loi), car on filtre les cas avec une lettre + point
# - des numéros avec un point après la lettre (ex: "1A.") grâce au lookahead négatif
#
# Exemple de matchs valides : "25", "3A", "102b", "245/0011", "50/A2"
# --------------------------------------------------------------------------------------------


_NUM_RX = r"\b\d{1,4}(?:[A-Za-z](?!\s*\.))?(?:/[A-ZÀ-ÿ0-9\-]+)?\b"


def _extract_cp(addr: Optional[str]) -> Optional[str]:
    """
    Extrait un code postal à 4 chiffres (commençant par 1-9) depuis une adresse.
    Retourne None si addr est None, vide ou ne contient pas de CP.
    """
    if not addr or not isinstance(addr, str):
        return None
    m = re.search(r"\b([1-9]\d{3})\b", addr)
    return m.group(1) if m else None


def verifier_si_premiere_adresse_est_bien_rapprochee_du_nom(nom: Any, texte: str, adresse: str, doc_hash: str, logger=None):
    """
    Vérifie si le 1er CP + numéro rencontrés après le nom correspondent à l’adresse donnée.
    Sinon, log un warning.
    """
    T = _norm(texte)
    name_end = _name_end_in_text(nom, texte)

    # Recherche du premier CP + numéro après le nom
    sub_T = T[name_end:]

    cp_match = re.search(r"\b\d{4}\b", sub_T)
    num_match = re.search(_NUM_RX, sub_T)

    first_cp = cp_match.group(0) if cp_match else None
    first_num = None
    if num_match:
        token = num_match.group(0)
        if not re.match(r"\b\d{1,4}/\d", token):  # ignorer "492/4" etc.
            first_num = token

    # Extraction CP + numéro depuis la 1ère adresse
    addr_cp = _extract_cp(adresse)
    addr_num = _extract_house_num(adresse)

    if not (first_cp and first_num):
        # Rien trouvé après le nom
        if logger:
            logger.warning(f"[❗️Aucun CP+num après nom] DOC={doc_hash} | adresse='{adresse}' | trouvé: CP={first_cp}, num={first_num}")
        else:
            print(f"[❗️Aucun CP+num après nom] DOC={doc_hash} | adresse='{adresse}' | trouvé: CP={first_cp}, num={first_num}")
        return

    # Comparaison stricte
    if first_cp != addr_cp or first_num != addr_num:
        msg = (f"[❗️1ère adresse différente du 1er CP+num après nom] DOC={doc_hash} | "
               f"adresse='{adresse}' | extrait: CP={addr_cp}, num={addr_num} | trouvé: CP={first_cp}, num={first_num}")
        if logger:
            logger.warning(msg)
        else:
            print(msg)

# Score “occurrences près du nom”
# ---------------------------


def _window_tokens_score(texte: str, start: int, addr: str, window: int = 220) -> Tuple[int, int]:
    """
    Compte le nb d'occurrences de tokens (>=3 lettres) de l'adresse
    dans la fenêtre [start, start+window] du texte normalisé.
    Renvoie (score_total, pos_min_token) pour tie-break.
    """
    T = _norm(texte)
    W = T[start:start+window]
    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{3,}", _norm(addr))
    if not tokens:
        return (0, 10**9)
    total = 0
    first_pos = 10**9
    for tok in set(tokens):
        j = W.find(tok)
        if j >= 0:
            total += W.count(tok)
            first_pos = min(first_pos, j)
    return (total, first_pos)


# ---------------------------
# Fonction principale
# ---------------------------
def prioriser_adresse_proche_nom_struct(
    nom: str,
    texte: str,
    adresses: List[str],
) -> List[str]:
    """
    Règle :
      1) CP le plus proche après le nom
      2) si même CP → numéro d'adresse le plus proche après le nom
      3) sinon ordre initial
    """
    if not adresses:
        return adresses

    T = _norm(texte)
    name_end = _name_end_in_text(nom, texte)

    scored = []
    for idx, a in enumerate(adresses):
        cp = _extract_cp(a)
        hn = _extract_house_num(a)

        cp_after = _first_after(T, cp, name_end) if cp else None
        hn_after = _first_after(T, _norm(hn) if hn else None, name_end) if hn else None

        # clé de tri simplifiée
        key = (
            0 if cp_after is not None else 1,
            (cp_after - name_end) if cp_after is not None else 10**9,
            0 if hn_after is not None else 1,
            (hn_after - name_end) if hn_after is not None else 10**9,
            idx  # fallback : ordre initial
        )
        scored.append((key, a))

    scored.sort(key=lambda x: x[0])
    return [a for _, a in scored]


# ---------------------------------------------------------------------------------------------------------------------
#                                                            Logs
#                            DETECTE SI PREMIERE ADRESSE CORRESPOND BIEN A L ADRESSE DU NOM
# ---------------------------------------------------------------------------------------------------------------------
# ---------------------------  Normalisation texte
# Normalise une chaîne de caractères :
#  - gère les cas None → chaîne vide
#  - unifie certains caractères spéciaux (apostrophes, guillemets)
#  - compresse les espaces multiples en un seul
#  - supprime les espaces en début et fin
# - met tout en minuscules


def _norm(s: str) -> str:
    s = (s or "")
    s = s.replace("’", "'").replace('"', " ")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


# ---------------------------  Localiser le nom dans le texte
def _name_end_in_text(nom: Any, texte: str) -> int:
    T = _norm(texte)
    candidates = []
    if isinstance(nom, dict):
        candidates += [c for c in (nom.get("canonicals") or []) if isinstance(c, str)]
        candidates += [a for a in (nom.get("aliases_flat") or []) if isinstance(a, str)]
        for r in nom.get("records") or []:
            if isinstance(r, dict) and isinstance(r.get("canonical"), str):
                candidates.append(r["canonical"])
    elif isinstance(nom, (list, tuple, set)):
        candidates += [s for s in nom if isinstance(s, str)]
    elif isinstance(nom, str):
        candidates.append(nom)

    for c in candidates:
        c_norm = _norm(c)
        if not c_norm:
            continue
        i = T.find(c_norm)
        if i >= 0:
            return i + len(c_norm)
    return 0


def _extract_house_num(addr: Optional[str]) -> Optional[str]:
    """
    Extrait le premier numéro de maison trouvé dans une adresse (1 à 4 chiffres, éventuellement avec suffixe).
    Retourne None si pas trouvé ou si addr est None.
    """
    if not addr or not isinstance(addr, str):
        return None
    for m in re.finditer(r"\b\d{1,4}(?:/[A-ZÀ-ÿ0-9\-]+)?\b", addr):
        return m.group(0)
    return None


# --------------------------------------------------------------------------------------
# Retourne le premier non-vide (après strip).
# --------------------------------------------------------------------------------------
def _pick(*vals: str) -> str:
    for v in vals:
        v = (v or "").strip()
        if v:
            return v
    return ""


def _format_address(row: dict, lang: str) -> str:
    """
    Construit une adresse lisible. Préférence pour la langue demandée,
    mais bascule sur l'autre si le champ est vide.
    """
    lang = (lang or "FR").upper()
    if lang not in {"FR", "NL"}:
        lang = "FR"

    # Suffixe principal et de repli
    suf_main = "FR" if lang == "FR" else "NL"
    suf_alt = "NL" if lang == "FR" else "FR"

    street = _pick(row.get(f"Street{suf_main}"), row.get(f"Street{suf_alt}"))
    muni = _pick(row.get(f"Municipality{suf_main}"), row.get(f"Municipality{suf_alt}"))
    country = _pick(row.get(f"Country{suf_main}"), row.get(f"Country{suf_alt}"))

    zipcode = (row.get("Zipcode") or "").strip()
    number = (row.get("HouseNumber") or "").strip()
    box = (row.get("Box") or "").strip()
    extra = (row.get("ExtraAddressInfo") or "").strip()

    # Libellé boîte selon langue (usage BE)
    box_lbl = "bte" if lang == "FR" else "bus"

    line1 = " ".join([s for s in [street, number] if s])
    if box:
        line1 = f"{line1} {box_lbl} {box}"

    line2 = " ".join([s for s in [zipcode, muni] if s])

    parts = [p for p in [line1, line2, country] if p]
    addr = ", ".join(parts)

    if extra:
        addr = f"{addr}, {extra}"

    return addr


def fetch_ejustice_article_names_by_tva(tva: str, language: str = "fr") -> list[dict]:
    """
    Extrait (nom, forme juridique) des sociétés listées dans la recherche eJustice
    Exemple : [{"nom": "AMD SERVICES", "forme": "SRL"}]
    """
    num = re.sub(r"\D", "", tva)
    if not num:
        return []

    searches = ([num[1:]] if len(num) > 1 else []) + [num]
    base = "https://www.ejustice.just.fgov.be/cgi_tsv/article.pl"

    for search in searches:
        url = f"{base}?{urlencode({'language': language, 'btw_search': search, 'page': 1, 'la_search': 'f', 'caller': 'list', 'view_numac': '', 'btw': num})}"
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"[article.pl] échec ({search}): {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        main = soup.select_one("main.page__inner.page__inner--content.article-text")
        if not main:
            continue

        out = []
        for p in main.find_all("p"):
            font_tag = p.find("font", {"color": "blue"})
            if font_tag:
                nom = font_tag.get_text(strip=True)

                # tout le texte du <p> après le <font>
                full_text = p.get_text(" ", strip=True)

                # supprime le nom déjà capturé
                reste = full_text.replace(nom, "").strip()

                # capture forme juridique (SA, SRL, ASBL, etc.)
                match_forme = re.search(r"\b(SA|SRL|SPRL|ASBL|SCRL|SNC|SCS|SC)\b", reste, flags=re.I)
                forme = match_forme.group(1).upper() if match_forme else None

                out.append({"nom": nom, "forme": forme})

        if out:
            return out

    return []


# ---------------------------------------------------------------------------------------------------------------------
#                              LECTURE DES FICHIERS CSV DE LA BCE
# ----------------------------------------------------------------------------------------------------------------------
def build_establishment_index(csv_path: str, skip_public: bool = True) -> dict[str, set[str]]:
    """
    Lit establishment.csv et renvoie :
      { "0403.449.823": {"2000000339", ...}, ... }
    """
    index: dict[str, set[str]] = {}

    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(csv_path, newline="", encoding=enc) as f:
                r = csv.DictReader(f)
                for row in r:
                    ent_raw = (row.get("EnterpriseNumber") or "").strip()
                    est_raw = (row.get("EstablishmentNumber") or "").strip()
                    if not ent_raw or not est_raw:
                        continue

                    # ⚙️ Normalisation des deux identifiants
                    ent = format_bce(ent_raw)
                    est = re.sub(r"\D", "", est_raw)  # 2.291.655.781 → 2291655781
                    if not ent or not est:
                        continue

                    if skip_public and is_entite_publique(ent):
                        continue

                    index.setdefault(ent, set()).add(est)
            break
        except UnicodeDecodeError:
            continue

    return index


def build_address_index(csv_path: str, *, lang: str = "FR", allowed_types: set[str] | None = None, skip_public: bool = True) -> dict[str, set[str]]:
    """
    Lit address.csv et renvoie :
      { "0731750083": {...}, "2291655781": {...} }
    """
    index: dict[str, set[str]] = {}

    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(csv_path, newline="", encoding=enc) as f:
                r = csv.DictReader(f)
                for row in r:
                    ent_raw = (row.get("EntityNumber") or "").strip()
                    if not ent_raw:
                        continue

                    # ⚙️ Un numéro commençant par 2. = établissement
                    if ent_raw.startswith("2."):
                        ent = re.sub(r"\D", "", ent_raw)  # 2.291.655.781 → 2291655781
                    else:
                        ent = format_bce(ent_raw) or ent_raw
                    if not ent:
                        continue

                    typ = (row.get("TypeOfAddress") or "").strip()
                    if allowed_types and typ not in allowed_types:
                        continue

                    addr = _format_address(row, lang)
                    if not addr:
                        continue

                    index.setdefault(ent, set()).add(addr)
            break
        except UnicodeDecodeError:
            continue

    return index

def build_denom_index(
    csv_path: str,
    *,
    allowed_types: set[str] | None = None,   # ex: {"001","002"}
    allowed_langs: set[str] | None = None,   # ex: {"1","2"}
    skip_public: bool = True,
) -> tuple[dict[str, set[str]], dict[str, str]]:
    """
    Lit le CSV une seule fois et renvoie :
      - index: { "xxxx.xxx.xxx": {"Denom1", "Denom2", ...}, ... }
      - type_entite_by_bce: { "xxxx.xxx.xxx": "physique" | "morale" }
    """
    index: dict[str, set[str]] = {}
    type_entite_by_bce: dict[str, str] = {}

    # petit cache disque
    pkl = _cache_path_for(csv_path)
    csv_mtime = _csv_mtime(csv_path)
    if os.path.exists(pkl):
        try:
            with open(pkl, "rb") as f:
                payload = pickle.load(f)
            if payload.get("mtime") == csv_mtime:
                return payload["index"], payload.get("types", {})
        except Exception:
            pass  # on reconstruit

    # Étape 1️⃣ : Charger enterprise.csv pour récupérer le type d'entité
    enterprise_csv = chemin_csv("enterprise.csv")
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(enterprise_csv, newline="", encoding=enc) as f:
                r = csv.DictReader(f)
                for row in r:
                    num = (row.get("EnterpriseNumber") or "").strip()
                    typ_ent = (row.get("TypeOfEnterprise") or "").strip()
                    ent = format_bce(num)
                    if not ent or not typ_ent:
                        continue

                    type_entite_by_bce[ent] = "physique" if typ_ent == "1" else "morale"
            break
        except UnicodeDecodeError:
            continue

    # Étape 2️⃣ : Lire denomination.csv
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(csv_path, newline="", encoding=enc) as f:
                r = csv.DictReader(f)
                for row in r:
                    raw_ent = (row.get("EntityNumber") or "").strip()
                    ent = format_bce(raw_ent)
                    if not ent:
                        continue

                    if skip_public and is_entite_publique(ent):
                        continue

                    typ = (row.get("TypeOfDenomination") or "").strip()
                    if allowed_types and typ not in allowed_types:
                        continue

                    lang = (row.get("Language") or "").strip()
                    if allowed_langs and lang not in allowed_langs:
                        continue

                    denom = (row.get("Denomination") or "").strip()
                    if not denom:
                        continue

                    # 🔹 Nettoie le code final du type (ex: "(015)")
                    denom = re.sub(r"\s*\(\d+\)\s*$", "", denom).strip()

                    index.setdefault(ent, set()).add(denom)
            break
        except UnicodeDecodeError:
            continue

    # Sauvegarde cache avec les deux structures
    try:
        with open(pkl, "wb") as f:
            pickle.dump(
                {"mtime": csv_mtime, "index": index, "types": type_entite_by_bce},
                f,
                protocol=pickle.HIGHEST_PROTOCOL
            )
    except Exception:
        pass

    return index, type_entite_by_bce


def build_enterprise_index(
    csv_path: str,
    skip_public: bool = True
) -> set[str]:
    """
    Lit enterprise.csv et renvoie un set de numéros BCE formatés
    ex: {"0200.065.765", "0778.045.116", ...}
    """

    index: set[str] = set()

    # petit cache disque
    pkl = _cache_path_for(csv_path)
    csv_mtime = _csv_mtime(csv_path)
    if os.path.exists(pkl):
        try:
            with open(pkl, "rb") as f:
                payload = pickle.load(f)
            if payload.get("mtime") == csv_mtime:
                return payload["index"]
        except Exception:
            pass

    # lecture streaming
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(csv_path, newline="", encoding=enc) as f:
                r = csv.DictReader(f)
                for row in r:
                    ent_raw = (row.get("EnterpriseNumber") or "").strip()
                    ent = format_bce(ent_raw)   # 👈 normalisation ici
                    if not ent:
                        continue
                    if skip_public and is_entite_publique(ent):
                        continue

                    index.add(ent)
            break
        except UnicodeDecodeError:
            continue

    # cache
    try:
        with open(pkl, "wb") as f:
            pickle.dump({"mtime": csv_mtime, "index": index}, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass

    return index

# ---------------------------------------------------------------------------------------------------------------------
#                          FONCTION DE CHARGEMENT "LAZY" DES INDEXS BCE (avec cache rapide pickle)
# ---------------------------------------------------------------------------------------------------------------------
def charger_indexes_bce():
    """
    Charge dynamiquement les index BCE :
    - dénominations (denomination.csv)
    - type d'entité (physique / morale)
    - adresses (address.csv)
    - entreprises (enterprise.csv)
    - établissements (establishment.csv)

    ✅ Utilise un cache pickle (cache_bce/bce_indexes.pkl)
    pour accélérer les exécutions suivantes.
    """
    import os
    import pickle
    from Utilitaire.outils.MesOutils import (
        chemin_csv,
        build_denom_index,
        build_address_index,
        build_enterprise_index,
        build_establishment_index,
    )

    CACHE_DIR = "cache_bce"
    CACHE_FILE = os.path.join(CACHE_DIR, "bce_indexes.pkl")

    # ⚡ 1️⃣ Si le cache existe, on recharge directement
    if os.path.exists(CACHE_FILE):
        print("[⚡] Chargement des index BCE depuis le cache pickle…")
        try:
            with open(CACHE_FILE, "rb") as f:
                payload = pickle.load(f)
                print("[✅] Cache BCE chargé avec succès.")
                return (
                    payload["denom_index"],
                    payload.get("type_entite_by_bce", {}),
                    payload["address_index"],
                    payload["enterprise_index"],
                    payload["establishment_index"],
                )
        except Exception as e:
            print(f"[⚠️] Erreur de lecture du cache ({e}), rechargement depuis les CSV…")

    # 🐢 2️⃣ Sinon : rechargement depuis les CSV
    print("[🐢] Chargement initial des fichiers CSV BCE…")
    os.makedirs(CACHE_DIR, exist_ok=True)

    # ⚙️ build_denom_index renvoie maintenant 2 objets
    denom_index, type_entite_by_bce = build_denom_index(
        chemin_csv("denomination.csv"),
        allowed_types=None,   # {"001","002"} si tu veux filtrer
        allowed_langs=None,   # {"2"} si tu veux uniquement FR
        skip_public=True
    )

    address_index = build_address_index(
        chemin_csv("address.csv"),
        lang="FR",
        allowed_types=None,
        skip_public=True
    )

    enterprise_index = build_enterprise_index(
        chemin_csv("enterprise.csv"),
        skip_public=True
    )

    establishment_index = build_establishment_index(
        chemin_csv("establishment.csv"),
        skip_public=True
    )

    print(f"[✅] Index BCE chargés : "
          f"{len(denom_index)} dénoms, "
          f"{len(address_index)} adresses, "
          f"{len(enterprise_index)} entreprises, "
          f"{len(establishment_index)} établissements, "
          f"{len(type_entite_by_bce)} types d'entité")

    # 💾 3️⃣ Sauvegarde du cache pour accélérer les prochains chargements
    try:
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(
                {
                    "denom_index": denom_index,
                    "type_entite_by_bce": type_entite_by_bce,
                    "address_index": address_index,
                    "enterprise_index": enterprise_index,
                    "establishment_index": establishment_index,
                },
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        print("[💾] Index BCE mis en cache pour les prochains runs.")
    except Exception as e:
        print(f"[⚠️] Impossible d’écrire le cache ({e})")

    return denom_index, type_entite_by_bce, address_index, enterprise_index, establishment_index

# --------------------------------------------------------------------------------------
# Retourne le premier non-vide (après strip).
# Filtre public num public dans fichier bce
# Utilise pcq les numeros publics ne seront jamais visés par decisions (attention ce ne
# sera pas le cas si on étend a decision FSMA dans l avenir
# --------------------------------------------------------------------------------------



def has_person_names(nom):
    if nom is None:
        return False
    if isinstance(nom, dict):
        return bool((nom.get("records") or []) or
                    (nom.get("canonicals") or []) or
                    (nom.get("aliases_flat") or []))
    if isinstance(nom, (list, str)):
        return bool(nom)
    return False


# ----------------------------------------------------------------------------------------------------------------------
#                                 FONCTIONS UTILISEES POUR NETTOYAGE DES NOMS D ENTREPRISES
# ----------------------------------------------------------------------------------------------------------------------
# Supprime de la liste les noms qui correspondent exactement à 'en cause de' (espaces ignorés, insensible à la casse).
def clean_nom_trib_entreprise(noms: list[str]) -> list[str]:

    return [
        nom for nom in noms
        if (nom.strip().lower() != "en cause de"
            and nom.strip().lower() != "qualité de curatrice sa"
            and nom.strip().lower() != "conformément e"
            and nom.strip().lower() != "conformément à"
            and nom.strip().lower() != "l'etat belge spf finances"
            and nom.strip().lower() != "1. l'etat belge spf finances"
            and nom.strip().lower() != "2. l etat belge spf finances"
            and nom.strip().lower() != "3. l etat belge spf finances"
            and nom.strip().lower() != "4. l etat belge spf finances"
            and nom.strip().lower() != "spf finances")
    ]


SOCIETESABRV = {"SA", "SRL", "SE", "SPRL", "SIIC", "SC", "SNC", "SCS",
                "COMMV", "SCRL", "SAS", "ASBL", "SCA"}

def _extraire_nom_majuscule(liste: list[str]) -> str | None:
    """
    Extrait un nom d'entreprise à partir d'une liste de chaînes.
    - Garde uniquement les tokens 100% en majuscules.
    - Supprime les abréviations de forme juridique (SA, SRL...).
    - Retourne le nom nettoyé ou None.
    """
    if not liste:
        return None
    for brut in liste:
        tokens = brut.strip().split()
        uppers = [t for t in tokens if t.isupper() and t not in SOCIETESABRV]
        if uppers:
            return " ".join(uppers)
    return None


# ----------------------------------------------------------------------------------------------------------------------
# Correction des TVA si denoms_by_bce est vide (via DENOM_INDEX déjà construit)
# ----------------------------------------------------------------------------------------------------------------------
def corriger_tva_par_nom(doc: dict, denom_index: dict[str, set[str]], logger=None):
    """
    Si denoms_by_bce est vide :
    - On prend le champ "nom"
    - Si rien, on tente le champ "nom_trib_entreprise" (extraction des tokens UPPER sans forme juridique)
    - On cherche dans DENOM_INDEX les EntityNumber où ce nom apparaît comme dénomination
    - Si trouvé, on compare le TVA correspondant avec les TVA extraites
    - Si différent → ajoute le bon numéro et met à jour denoms_by_bce
    """

    if doc.get("denoms_by_bce"):
        return doc  # rien à faire

    # 1️⃣ Essai avec champ "nom"
    noms = names_list_from_nom(doc.get("nom"))
    candidats = [n.strip() for n in noms if isinstance(n, str) and n.strip()]

    # 2️⃣ Fallback avec champ "nom_trib_entreprise"
    if not candidats and doc.get("nom_trib_entreprise"):
        fallback_nom = _extraire_nom_majuscule(doc["nom_trib_entreprise"])
        if fallback_nom:
            candidats = [fallback_nom]

    if not candidats:
        return doc

    nom_doc = candidats[0].strip().lower()

    # Recherche dans index des dénominations
    for ent, denoms in denom_index.items():
        if any((d or "").strip().lower() == nom_doc for d in denoms):
            tva_csv = format_bce(ent)
            if not tva_csv:
                continue

            tva_extraites = [format_bce(t) for t in (doc.get("TVA") or []) if format_bce(t)]

            if not tva_extraites or tva_csv not in tva_extraites:
                msg = (f"[⚠️ Correction TVA par NOM/ENTREPRISE] DOC={doc.get('doc_hash')} | "
                       f"Nom='{nom_doc}' | TVA extraite={tva_extraites} | TVA trouvé={tva_csv}")
                if logger:
                    logger.warning(msg)
                else:
                    print(msg)

                doc.setdefault("TVA", []).append(tva_csv)
                doc["denoms_by_bce"] = list(denoms)
            break

    return doc



