# --- Imports standards ---
import concurrent.futures
import json
import locale
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import date
from typing import List

from urllib.parse import urlencode, urljoin

# --- Bibliothèques tierces ---
import meilisearch
import psycopg2
import pytesseract
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tqdm import tqdm

# --- Modules internes au projet ---
from logger_config import setup_logger, setup_dynamic_logger
from Constante.mesconstantes import BASE_URL, ADRESSES_INSTITUTIONS_SET, NETTOIE_ADRESSE_SET, POSTAL_RE, BCE_RE
from Extraction.NomPrenom.extraction_noms_personnes_physiques import extract_name_from_text
from Extraction.NomPrenom.extraction_nom_interdit import extraire_personnes_interdites
from Extraction.NomPrenom.extraction_nom_terrorisme_bis import extraire_personnes_terrorisme
from Extraction.Adresses.extract_adresses_entreprises import extract_add_entreprises
from Extraction.Adresses.extraction_adresses_moniteur import extract_address
from Extraction.Denomination.extraction_nom_entreprises import extract_noms_entreprises
from Extraction.Gerant.extraction_administrateurs import extract_administrateur
from Extraction.Keyword.tribunal_entreprise_keyword import detect_tribunal_entreprise_keywords
from Extraction.Keyword.justice_paix_keyword import detect_justice_paix_keywords
from Extraction.Keyword.tribunal_premiere_instance_keyword import detect_tribunal_premiere_instance_keywords
from Extraction.Keyword.cour_appel_keyword import detect_courappel_keywords
from Extraction.Keyword.terrorisme_keyword import add_tag_personnes_a_supprimer
from Extraction.Keyword.succession_keyword import detect_succession_keywords
from Extraction.MandataireJustice.extraction_mandataire_justice_gen import trouver_personne_dans_texte
from Extraction.Dates.extractionDateNaissanceDeces import extract_date_after_birthday, \
    extract_dates_after_decede
from Extraction.Dates.extraction_date_jugement import extract_jugement_date
from Utilitaire.ConvertDateToMeili import convertir_date
from Utilitaire.outils.MesOutils import detect_erratum, extract_numero_tva, \
    extract_clean_text, clean_url, generate_doc_hash_from_html, \
    clean_date_jugement, extract_nrn_variants, has_person_names, norm_er, \
    clean_nom_trib_entreprise, format_bce, chemin_csv, \
    norm_spaces, digits_only, prioriser_adresse_proche_nom_struct, \
    extract_page_index_from_url, has_cp_plus_other_number_aligned, nettoyer_adresses_par_keyword, \
    verifier_premiere_adresse_apres_nom, remove_av_parentheses, to_list_dates, names_list_from_nom, \
    remove_duplicate_paragraphs, dedupe_phrases_ocr, tronque_texte_apres_adresse, strip_accents, DENOM_INDEX, \
    ADDRESS_INDEX, normaliser_espaces_invisibles
from ParserMB.MonParser import find_linklist_in_items, retry, convert_pdf_pages_to_text_range

assert len(sys.argv) == 2, "Usage: python MainScrapper.py \"mot+clef\""
keyword = sys.argv[1]

# ---------------------------------------------------------------------------------------------------------------------
#                                    CONFIGURATION DES LOGGERS
# ----------------------------------------------------------------------------------------------------------------------
# **** LOGGER GENERAL
logger = setup_logger("extraction", level=logging.DEBUG)
logger.debug("✅ Logger initialisé dans le script principal.")

# *** LOGGERS SPECIFIQUES PAR MOTS CLEFS
# CHAMP ADRESSES : adresses
logger_adresses = setup_dynamic_logger(name="adresses_logger", keyword=keyword, level=logging.DEBUG)
logger_adresses.debug("🔍 Logger 'adresses_logger' initialisé pour les adresses.")

# CHAMP NOM : nom : log si le champ nom est null
logger_nomspersonnes = setup_dynamic_logger(name="nomspersonnes_logger", keyword=keyword, level=logging.DEBUG)
logger_nomspersonnes.debug("🔍 Logger 'nomspersonnes_logger' initialisé pour les noms.")
# CHAMP DATE NAISSANCE : date_naissance
logger_datenaissance = setup_dynamic_logger(name="datenaissance_logger", keyword=keyword, level=logging.DEBUG)
logger_datenaissance.debug("🔍 Logger 'datenaissance_logger' initialisé pour les noms.")

logger_nomsdouble = setup_dynamic_logger(name="nomsdouble_logger", keyword=keyword, level=logging.DEBUG)
logger_nomsdouble.debug("🔍 Logger 'nomsdouble_logger' initialisé pour les noms.")

# va falloir faire ca que pour cas de succession
logger_nomsvsdates = setup_dynamic_logger(name="nomsvsdates_logger", keyword=keyword, level=logging.DEBUG)
logger_nomsvsdates.debug("🔍 Logger 'nomsvsdates_logger' initialisé pour les noms et dates.")

# CHAMP NOM TERRORISME : identifiant_terrorisme
logger_nomsterrorisme = setup_dynamic_logger(name="nomsterrorisme_logger", keyword=keyword, level=logging.DEBUG)
logger_nomsterrorisme.debug("🔍 Logger 'nomsterrorisme_logger' initialisé pour les noms terrorisme.")

# CHAMP NOM ENTREPRISE : nom_entreprise
logger_nomsentreprises = setup_dynamic_logger(name="nomsentreprises_logger", keyword=keyword, level=logging.DEBUG)
logger_nomsentreprises.debug("🔍 Logger 'nomsentreprises_logger' initialisé pour les noms entreprises.")

logged_adresses: set[tuple[str, str]] = set()
print(">>> CODE À JOUR")

# ---------------------------------------------------------------------------------------------------------------------
#                                          VARIABLES D ENVIRONNEMENT
# ----------------------------------------------------------------------------------------------------------------------
load_dotenv()
MEILI_URL = os.getenv("MEILI_URL")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")


# ---------------------------------------------------------------------------------------------------------------------
#                                          FONCTIONS INTERNES
# ----------------------------------------------------------------------------------------------------------------------


def _log_len_mismatch(doc, date_naissance, date_deces, nom):
    births = to_list_dates(date_naissance)
    deaths = to_list_dates(date_deces)
    names = names_list_from_nom(nom)

    nb, nd, nn = len(births), len(deaths), len(names)
    doc_hash = doc.get("doc_hash")

    # 1) naissance vs décès
    if nb != nd:
        logger_nomsvsdates.warning(
            f"[LEN_MISMATCH naissance≠décès] DOC={doc_hash} | n_naiss={nb} n_deces={nd} | "
            f"naiss={births} | deces={deaths}"
        )

    # 2) dates vs nombre de noms (si on a au moins un nom)
    if nn > 0 and (nb != nn or nd != nn):
        logger_nomsvsdates.warning(
            f"[LEN_MISMATCH dates≠noms] DOC={doc_hash} | n_noms={nn} n_naiss={nb} n_deces={nd} | "
            f"noms={names} | naiss={births} | deces={deaths}"
        )


def _first_token_from_nom_field(nom_field: dict | str) -> str | None:
    """
    Récupère le 1er canonical (si dict) ou la chaîne (si str),
    puis retourne son 1er mot (ex: 'Carolina' pour 'Carolina Verboven').
    """
    base = None
    if isinstance(nom_field, dict):
        # priorité aux canonicals
        cans = nom_field.get("canonicals") or []
        if cans:
            base = cans[0]
        elif nom_field.get("records"):
            base = nom_field["records"][0].get("canonical")
        elif nom_field.get("aliases_flat"):
            base = nom_field["aliases_flat"][0]
    elif isinstance(nom_field, str):
        base = nom_field

    if not base:
        return None

    # 1er mot (lettres/accents/tirets/apostrophes)
    m = re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ'’-]+", base)
    if not m:
        return None
    token = m.group(0).strip()
    # Filtre mini longueur pour éviter 'de', 'le', etc. (tu peux ajuster)
    return token if len(token) >= 3 else None

def _log_nom_repetition_locale_first_token(doc, window=80):
    """
    Cherche la répétition locale du 1er mot du 1er canonical.
    Si ce mot apparaît >= 2 fois dans une fenêtre courte => warning.
    """
    nom_field = doc.get("nom")
    texte = doc.get("text", "") or ""
    if not nom_field or not texte:
        return

    token = _first_token_from_nom_field(nom_field)
    if not token:
        return

    # normalisation accent-insensible
    token_key = strip_accents(token).lower()
    if not token_key:
        return

    texte_norm = strip_accents(texte).lower()

    # mot entier
    pat = re.compile(rf"\b{re.escape(token_key)}\b", re.IGNORECASE)

    for m in pat.finditer(texte_norm):
        start, end = m.span()
        left = max(0, start - window)
        right = min(len(texte_norm), end + window)
        fen = texte_norm[left:right]

        # compte du token dans la fenêtre
        if len(pat.findall(fen)) >= 2:
            # utilise ton logger déjà défini (tu semblais utiliser `loggernomspersonnes`)
            try:
                logger_nomsdouble.warning(
                    f"[Nom (1er mot) dédoublé localement] DOC={doc.get('doc_hash')} | "
                    f"token='{token}' | fenêtre={window} | extrait=…{fen}…"
                )
            except NameError:
                # fallback print si le logger n'existe pas dans ce scope
                print(
                    f"[Nom (1er mot) dédoublé localement] DOC={doc.get('doc_hash')} | "
                    f"token='{token}' | fenêtre={window} | extrait=…{fen}…"
                )
            break  # un log par doc suffit


# ---------------------------------------------------------------------------------------------------------------------
#                               FONCTIONS PRINCIPALES D EXTRACTION
# ----------------------------------------------------------------------------------------------------------------------
def fetch_ejustice_article_addresses_by_tva(tva: str, language: str = "fr") -> list[str]:
    """
    Vue ARTICLE uniquement (page=1). Renvoie les lignes contenant un code postal.
    - essaie btw_search = TVA sans 1er chiffre, puis TVA complète
    - remplace <br> et <hr> par des retours à la ligne
    - ignore "IMAGE", BCE, dates, RUBRIQUE
    """
    num = digits_only(tva)
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
            logger.warning(f"[article.pl] échec ({search}): {e}")
            continue

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        main = soup.select_one("main.page__inner.page__inner--content.article-text") or soup.find("main")
        if not main:
            continue

        node = main.find("p") or main

        # 1) convertir <br> ET <hr> en sauts de ligne
        for tag in node.find_all(["br", "hr"]):
            tag.replace_with("\n")

        # 2) supprimer le texte "IMAGE" (liens PDF)
        for a in node.find_all("a"):
            if "image" in a.get_text(strip=True).lower():
                a.decompose()

        # 3) récupérer lignes + normaliser espaces/guillemets
        text = node.get_text("\n", strip=True).replace('"', " ").replace("’", "'")
        lines = [norm_spaces(ln) for ln in text.split("\n") if ln.strip()]

        # 4) filtrer le bruit puis garder les lignes avec CP
        out = []
        for ln in lines:
            if not ln or "rubrique" in ln.lower():
                continue
            if BCE_RE.search(ln):
                continue
            if re.search(r"\b(19|20)\d{2}-\d{2}-\d{2}\b", ln):
                continue
            if POSTAL_RE.search(ln):
                if ln not in out:
                    out.append(ln)

        if out:
            return out[:5]

    return []


from_date = date.fromisoformat("2025-07-26")
to_date = "2025-07-30"  # date.today()
# BASE_URL = "https://www.ejustice.just.fgov.be/cgi/"

locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def get_page_amount(session, start_date, end_date, keyword):
    encoded = keyword.replace(" ", "+")
    today = date.today()
    url = (
        f"{BASE_URL}list.pl?"
        f"language=fr&"
        f"sum_date={today}&"
        f"page=&"
        f"pdd={start_date}&"
        f"pdf={end_date}&"
        f"choix1=et&"
        f"choix2=et&"
        f"exp={encoded}&"
        f"fr=f&"
        f"trier=promulgation"
    )
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
        # NEW: crée une session locale dans ce thread (ne PAS réutiliser celle passée en argument)
        with requests.Session() as s:  # NEW
            response = retry(url, s)  # CHANGED (session -> s)
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
            elif keyword == "Conseil+d+'+Etat" and subtitle_text == "Conseil d'État" and title.lower().startswith(
                    "avis prescrit"):
                find_linklist_in_items(item, keyword, link_list)
            elif keyword == "Cour+constitutionnelle" and subtitle_text == "Cour constitutionnelle":
                find_linklist_in_items(item, keyword, link_list)
            elif keyword == "terrorisme":
                cleaned_title = title.strip().lower()
                if "entités visée aux articles 3 et 5 de l'arrêté royal du 28 décembre 2006" in cleaned_title:
                    print(f"[🪦] Document succession détecté: {title}")
                    find_linklist_in_items(item, keyword, link_list)
                else:
                    print(f"[❌] Ignoré (terrorisme mais pas SPF Finances): {title}")

            elif keyword in ("succession", "successions"):

                cleaned_title = title.strip().lower()

                # Vérifie si le titre correspond exactement à ce que tu recherches
                if cleaned_title == "administration générale de la documentation patrimoniale" or cleaned_title.startswith(
                        "les créanciers et les légataires sont invités à "):
                    print(f"[🪦] Document succession détecté: {title}")
                    find_linklist_in_items(item, keyword, link_list)
            elif keyword in ("tribunal+de+premiere+instance"):
                if title.lower().startswith("tribunal de première instance"):
                    find_linklist_in_items(item, keyword, link_list)
                else:
                    print(
                        f"[❌] Ignoré (source ou titre non pertinent pour tribunal de première instance): {title} | "
                        f"Source: {subtitle_text}")
            elif keyword in ("tribunal+de+l"):
                if (
                        title.lower().startswith("tribunal de l")

                ):
                    # print(title)
                    find_linklist_in_items(item, keyword, link_list)
                else:
                    print(
                        f"[❌] Ignoré (source ou titre non pertinent pour trib entreprise): {title} | Source : {subtitle_text}")

            elif keyword in ("justice+de+paix"):
                if title.lower().startswith("justice de paix"):
                    # print(title)
                    find_linklist_in_items(item, keyword, link_list)

                else:
                    print(
                        f"[❌] Ignoré (source ou titre non pertinent pourjustice de paix): {title} | Source: {subtitle_text}")
            elif keyword in ("cour+d"):
                if (
                        title.lower().startswith("cour d'appel")

                ):
                    find_linklist_in_items(item, keyword, link_list)
                else:
                    print(
                        f"[❌] Ignoré (source ou titre non pertinent pour cour d appel) : {title} | Source : {subtitle_text}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        list(tqdm(executor.map(process_page, range(1, page_amount + 1)), total=page_amount, desc="Pages"))

    return link_list


def scrap_informations_from_url(url, numac, date_doc, langue, keyword, title, subtitle):
    with requests.Session() as s:
        EVENT_RX = re.compile(
        r"\b(?:"
        r"dissolution\s+judiciaire"
        r"|faillites?"
        r"|liquidations?"
        r"|(?:proc[ée]dure\s+de\s+)?r[ée]organisation\s+judiciaire"
        r"|PRJ"
        r")\b",
        re.IGNORECASE
        )
        response = retry(url, session)
        soup = BeautifulSoup(response.text, 'html.parser')
        extra_keywords = []
        extra_links = []

        main = soup.find("main", class_="page__inner page__inner--content article-text")
        if not main:
           return (
               numac, date_doc, langue, "", url, keyword, None, title, subtitle, None, None, None, None, None, None, None,
               None, None, None, None, None, None, None, None)
        # si terrorisme on a besoin de garder les liens pour acceder aux pdf où certains noms devront etre recherchés
        if keyword != "terrorisme":
           texte_brut = extract_clean_text(main)
        else:
           texte_brut = extract_clean_text(main, remove_links=False)

        date_jugement = None
        administrateur = None
        nom = None
        nom_trib_entreprise = None
        date_deces = None
        nom_interdit = None
        identifiants_terrorisme = None
        doc_id = generate_doc_hash_from_html(texte_brut, date_doc)
        if detect_erratum(texte_brut):
            extra_keywords.append("erratum")

        # Cas spécial : TERRORISME
        if re.search(r"terrorisme", keyword, flags=re.IGNORECASE):
            add_tag_personnes_a_supprimer(texte_brut, extra_keywords)
            matches = extraire_personnes_terrorisme(texte_brut, doc_id=doc_id)  # [(num, nom, nrn), ...]
            seen = set()
            noms_paires: List[List[str]] = []

            for _, name, nn in matches:
                key = (name.upper(), nn)  # même logique de dédup que dans la fonction
                if key in seen:
                    continue
                seen.add(key)
                noms_paires.append([name, nn])

            # Si trouvé dans le HTML → pas besoin d'OCR
            if noms_paires:
                return (
                    numac, date_doc, langue, texte_brut, url, keyword,
                    None, title, subtitle, None, extra_keywords, None, None, None, None, None, None,
                    None, None, None, None, noms_paires, None, None
                )

            # Sinon, OCR fallback
            main_pdf_links = soup.find_all("a", class_="links-link")
            if len(main_pdf_links) >= 2:
                pdf_href = main_pdf_links[-2]['href']
                full_pdf_url = urljoin("https://www.ejustice.just.fgov.be", pdf_href)
                print(f"📄 Téléchargement du PDF: {full_pdf_url}")
                page_index = extract_page_index_from_url(full_pdf_url)
                if page_index is None:
                    print(f"[⚠️] Pas de numéro de page dans l’URL: {full_pdf_url} — on commence à la page 0")
                    page_index = 0

                ocr_text = convert_pdf_pages_to_text_range(full_pdf_url, page_index, page_count=6)
                pattern = r"(\d+)[,\.]\s*([A-Za-z\s]+)\s*\(NRN:\s*(\d{2}\.\d{2}\.\d{2}-\d{3}\.\d{2})\)"
                if ocr_text:
                    ocr_matches = re.findall(pattern, ocr_text)
                    noms_ocr = [(name.strip(), nn.strip()) for _, name, nn in ocr_matches]
                    return (
                        numac, date_doc, langue, texte_brut, url, keyword,
                        None, title, subtitle, None, extra_keywords, None, None, None, None, nom_trib_entreprise, None,
                        None,
                        None, None, None, noms_ocr, None, None
                    )
                else:
                    print("⚠️ Texte OCR vide.")
                    return None
            else:
                print("⚠️ Aucun lien PDF trouvé pour l’OCR.")
                return None

        # Cas normal
        # on va devoir deplacer nom

        texte_date_naissance = remove_av_parentheses(texte_brut)  # 🚨 on nettoie ici
        texte_date_naissance_sansdup = remove_duplicate_paragraphs(texte_date_naissance)
        texte_date_naissance_deces = dedupe_phrases_ocr(texte_date_naissance_sansdup)
        raw_naissance = extract_date_after_birthday(str(texte_date_naissance_deces))  # liste ou str

        if isinstance(raw_naissance, list):
            raw_naissance = [norm_er(s) for s in raw_naissance]
        elif isinstance(raw_naissance, str):
            raw_naissance = norm_er(raw_naissance)
        date_naissance = convertir_date(raw_naissance)  # liste ISO ou None

        adresse = extract_address(str(texte_brut), doc_id=doc_id)
        if not date_jugement:
            date_jugement = extract_jugement_date(str(texte_brut))

        if re.search(r"succession[s]?", keyword, flags=re.IGNORECASE):
            raw_deces = extract_dates_after_decede(str(texte_date_naissance_deces), first_only=False)  # liste ou str

            if isinstance(raw_deces, list):
                raw_deces = [norm_er(s) for s in raw_deces]
            elif isinstance(raw_deces, str):
                raw_deces = norm_er(raw_deces)
            # 🚨 Ajoute ce filtre ici
            # 🚨 Applique le filtre contre les dates parasites (Av, Avenue, parenthèses)
            date_deces = convertir_date(raw_deces)  # -> liste ISO ou None
            adresse = extract_address(str(texte_brut), doc_id=doc_id)
            detect_succession_keywords(texte_brut, extra_keywords)
            nom = extract_name_from_text(str(texte_date_naissance_deces), keyword, doc_id=doc_id)

        if re.search(r"tribunal[\s+_]+de[\s+_]+premiere[\s+_]+instance", keyword, flags=re.IGNORECASE | re.DOTALL):
            nom = extract_name_from_text(str(texte_date_naissance_deces), keyword, doc_id=doc_id)
            if re.search(r"\bsuccessions?\b", texte_brut, flags=re.IGNORECASE):
                raw_deces = extract_dates_after_decede(str(main))

                if isinstance(raw_deces, list):
                    raw_deces = [norm_er(s) for s in raw_deces]
                elif isinstance(raw_deces, str):
                    raw_deces = norm_er(raw_deces)

                date_deces = convertir_date(raw_deces)
            administrateur = trouver_personne_dans_texte(texte_brut, chemin_csv("curateurs.csv"),
                                                         ["avocate", "avocat", "Maître", "bureaux", "cabinet",
                                                          "curateur"])
            if not administrateur:
                administrateur = extract_administrateur(texte_brut)
                nom_trib_entreprise = extract_noms_entreprises(texte_brut)
            detect_tribunal_premiere_instance_keywords(texte_brut, extra_keywords)
            if all("delai de contact" not in element for element in extra_keywords):
                detect_tribunal_entreprise_keywords(texte_brut, extra_keywords)

            # Petit pré-nettoyage pour espaces insécables éventuels
            def _norm_txt(s: str) -> str:
                return re.sub(r"[\u00A0\u202F]+", " ", s)

            if not has_person_names(nom) and EVENT_RX.search(_norm_txt(texte_brut)):
                nom_trib_entreprise = extract_noms_entreprises(texte_brut, doc_id=doc_id)

        if re.search(r"justice\s+de\s+paix", keyword.replace("+", " "), flags=re.IGNORECASE):
            administrateur = trouver_personne_dans_texte(texte_brut, chemin_csv("curateurs.csv"),
                                                         ["avocate", "avocat", "Maître", "bureaux", "cabinet"])
            detect_justice_paix_keywords(texte_brut, extra_keywords)
            nom = extract_name_from_text(str(texte_date_naissance_deces), keyword, doc_id=doc_id)
        if re.search(r"tribunal\s+de\s+l", keyword.replace("+", " "), flags=re.IGNORECASE):
            # verifier à quoi sert id ici mais pense que peut etre utile
            nom_interdit = extraire_personnes_interdites(texte_brut)  # va falloir deplacer dans fonction ?
            nom_trib_entreprise = extract_noms_entreprises(texte_brut, doc_id=doc_id)
            administrateur = extract_administrateur(texte_brut)
            adresse = extract_add_entreprises(texte_brut, doc_id=doc_id)
            detect_tribunal_entreprise_keywords(texte_brut, extra_keywords)

        if re.search(r"cour\s+d", keyword.replace("+", " "), flags=re.IGNORECASE):

            nom_interdit = extraire_personnes_interdites(texte_brut)
            nom_trib_entreprise = extract_noms_entreprises(texte_brut, doc_id=doc_id)
            detect_tribunal_entreprise_keywords(texte_brut, extra_keywords)
            detect_courappel_keywords(texte_brut, extra_keywords)
            detect_tribunal_premiere_instance_keywords(texte_brut, extra_keywords)
            nom = extract_name_from_text(texte_brut, keyword, doc_id=doc_id)

            def clean(n):
                return re.sub(r"\s+", " ", n.strip().lower())

            # On nettoie tous les noms d'entreprise à exclure
            noms_entreprise_exclues = {clean(n) for n in nom_trib_entreprise}

            # 1. Nettoyer "records"
            filtered_records = [
                r for r in nom.get("records", [])
                if clean(r.get("canonical", "")) not in noms_entreprise_exclues
            ]

            # 2. Nettoyer "canonicals"
            filtered_canonicals = [
                c for c in nom.get("canonicals", [])
                if clean(c) not in noms_entreprise_exclues
            ]

            # 3. Nettoyer "aliases_flat"
            filtered_aliases_flat = [
                a for a in nom.get("aliases_flat", [])
                if clean(a) not in noms_entreprise_exclues
            ]

            # 4. Mettre à jour l'objet `nom`
            nom["records"] = filtered_records
            nom["canonicals"] = filtered_canonicals
            nom["aliases_flat"] = filtered_aliases_flat
            # administrateur me semble inutile pour cour d appel
            # administrateur = extract_administrateur(texte_brut)
            # refactoriser et faire qu en cas de succession?
            raw_deces = extract_dates_after_decede(str(main))  # liste ou str
            nom_trib_entreprise = clean_nom_trib_entreprise(nom_trib_entreprise)

            if isinstance(raw_deces, list):
                raw_deces = [norm_er(s) for s in raw_deces]
            elif isinstance(raw_deces, str):
                raw_deces = norm_er(raw_deces)

            date_deces = convertir_date(raw_deces)  # -> liste ISO ou None

        tvas = extract_numero_tva(texte_brut)
        tvas_valides = [t for t in tvas if format_bce(t)]
        denoms_by_bce = tvas_valides  # temporaire, juste le formaté
        adresses_by_bce = tvas_valides
        match_nn_all = extract_nrn_variants(texte_brut)
        nns = match_nn_all
        doc_id = generate_doc_hash_from_html(texte_brut, date_doc)
        return (
            numac, date_doc, langue, texte_brut, url, keyword,
            tvas, title, subtitle, nns, extra_keywords, nom, date_naissance, adresse, date_jugement,
            nom_trib_entreprise,
            date_deces, extra_links, administrateur, doc_id, nom_interdit, identifiants_terrorisme, denoms_by_bce,
            adresses_by_bce
        )


# MAIN
final = []
with requests.Session() as session:

    raw_link_list = ask_belgian_monitor(session, from_date, to_date, keyword)
    link_list = raw_link_list  # on garde le nom pour compatibilité
    scrapped_data = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [
            executor.submit(
                scrap_informations_from_url, url, numac, date_doc, langue, keyword, title, subtitle
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
client = meilisearch.Client(MEILI_URL, MEILI_KEY)

# ✅ Si l'index existe, on le supprime proprement
try:
    index = client.get_index(INDEX_NAME)
    print("✅ Clé primaire de l'index :", index.primary_key)
    delete_task = index.delete()
    client.wait_for_task(delete_task.task_uid)
    print(f"[🗑️] Index '{INDEX_NAME}' supprimé avec succès.")
except meilisearch.errors.MeilisearchApiError:
    print(f"[ℹ️] Aucun index existant à supprimer.")

# 🔄 Ensuite on recrée un nouvel index propre avec clé primaire
create_task = client.create_index(INDEX_NAME, {"primaryKey": "id"})
client.wait_for_task(create_task.task_uid)
index = client.get_index(INDEX_NAME)
print("✅ Index recréé avec clé primaire :", index.primary_key)

# ✅ Ajoute ces lignes ici (et non dans le try)
index.update_filterable_attributes(["keyword"])
index.update_searchable_attributes([
    "id", "date_doc", "title", "keyword", "nom", "date_jugement", "TVA",
    "extra_keyword", "num_nat", "date_naissance", "adresse", "nom_trib_entreprise",
    "date_deces", "extra_links", "administrateur", "nom_interdit", "identifiant_terrorisme", "text", "denoms_by_bce", "adresses_by_bce"
])
index.update_displayed_attributes([
    "id", "doc_hash", "date_doc", "title", "keyword", "extra_keyword", "nom", "date_jugement", "TVA",
    "num_nat", "date_naissance", "adresse", "nom_trib_entreprise", "date_deces",
    "extra_links", "administrateur", "text", "url", "nom_interdit", "identifiant_terrorisme", "denoms_by_bce", "adresses_by_bce"
])
last_task = index.get_tasks().results[-1]
client.wait_for_task(last_task.uid)

documents = []
with requests.Session() as session:
    for record in tqdm(final, desc="Préparation Meilisearch"):
        cleaned_url = clean_url(record[4])
        date_jugement = None  # Valeur par défaut si record[14] est None
        if record[14] is not None:
            brut = clean_date_jugement(record[14])
            date_jugement = convertir_date(brut)  # <= on récupère le résultat

        texte = record[3].strip()
        texte = texte.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        doc_hash = generate_doc_hash_from_html(record[3], record[1])  # ✅ Hash du texte brut + date
        doc = {
            "id": doc_hash,  # ✅ L’ID est celui généré dans scrap_informations_from_url
            "doc_hash": doc_hash,  # ✅ Tu peux aussi réutiliser cet ID comme hash si c’est ce que tu veux
            "date_doc": record[1],
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
            "date_jugement": date_jugement,
            "nom_trib_entreprise": record[15],
            "date_deces": record[16],
            "extra_links": record[17],
            "administrateur": record[18],
            "nom_interdit": record[20],
            "identifiant_terrorisme": record[21],
            "denoms_by_bce": record[22],
            "adresses_by_bce": record[23]

        }
        # rien a faire dans meili mettre dans postgre
        # if record[6]:
        # doc["publications_pdfs"] = get_publication_pdfs_for_tva(session, record[6][0])
        documents.append(doc)

        # 🔎 Indexation unique des dénominations TVA (après avoir rempli documents[])
        print("🔍 Indexation des dénominations par TVA (1 seule lecture du CSV)…")



        if keyword == "terrorisme":
            if isinstance(record[21], list):
                doc["nom_terrorisme"] = [pair[0] for pair in record[21] if len(pair) == 2]
                doc["num_nat_terrorisme"] = [pair[1] for pair in record[21] if len(pair) == 2]

                # ✅ Forcer administrateur à être une liste si ce n’est pas None
        if isinstance(doc["administrateur"], str):
            doc["administrateur"] = [doc["administrateur"]]
        elif doc["administrateur"] is None:
            doc["administrateur"] = None
        elif not isinstance(doc["administrateur"], list):
            doc["administrateur"] = [str(doc["administrateur"])]

# ✅ Enrichissement des dénominations – une seule passe
for doc in documents:
    denoms = set()
    for t in (doc.get("TVA") or []):
        bce = format_bce(t)
        if bce and bce in DENOM_INDEX:
            denoms.update(DENOM_INDEX[bce])
    doc["denoms_by_bce"] = sorted(denoms) if denoms else None

# ✅ Enrichissement des adresses – une seule passe
for doc in documents:
    addrs = set()
    for t in (doc.get("TVA") or []):
        bce = format_bce(t)
        if bce and bce in ADDRESS_INDEX:
            addrs.update(ADDRESS_INDEX[bce])
    doc["adresses_by_bce"] = sorted(addrs) if addrs else None
    # Fallback : si AUCUNE adresse dans le CSV, on va chercher la ligne d'adresse de l'article
    if not addrs:
        found = []
        for t in (doc.get("TVA") or []):
            found.extend(fetch_ejustice_article_addresses_by_tva(t) or [])

        if found:
            cur = doc.get("adresses_by_bce")
            cur_list = [] if cur is None else ([cur] if isinstance(cur, str) else list(cur))
            seen_local = set(cur_list)
            for addr in found:
                if addr not in seen_local:
                    cur_list.append(addr)
                    seen_local.add(addr)
            doc["adresses_by_bce"] = cur_list or None


# On va faire les logs ici
# 🧼 Nettoyage des champs adresse : suppression des doublons dans la liste
# 🧼 Nettoyage des champs noms

for doc in documents:
    adresse = doc.get("adresse")
    word = doc.get("keyword")
    nom = doc.get("nom")
    date_naissance = doc.get("date_naissance")
    date_deces = doc.get("date_deces")


    # ✅ Fonction utilitaire pour extraire le nom canonique
    def extraire_nom_canonique(nom_field) -> list[str]:
        """
        Récupère TOUS les noms trouvés (canonicals, records, aliases…).
        Pas de priorisation, juste une liste plate unique.
        """
        noms = []

        if isinstance(nom_field, dict):
            # canonicals
            noms.extend([c.strip() for c in (nom_field.get("canonicals") or []) if isinstance(c, str) and c.strip()])

            # records
            for r in nom_field.get("records", []):
                if isinstance(r, dict) and isinstance(r.get("canonical"), str):
                    val = r["canonical"].strip()
                    if val:
                        noms.append(val)

            # aliases_flat
            noms.extend([a.strip() for a in (nom_field.get("aliases_flat") or []) if isinstance(a, str) and a.strip()])

        elif isinstance(nom_field, list):
            noms.extend([s.strip() for s in nom_field if isinstance(s, str) and s.strip()])

        elif isinstance(nom_field, str):
            noms.append(nom_field.strip())

        # 🔄 déduplication case-insensitive mais en gardant la casse originale
        seen = set()
        result = []
        for n in noms:
            key = n.lower()
            if key not in seen:
                result.append(n)  # 👈 garde la version telle qu’elle est
                seen.add(key)
        return result or []


    # ✅ Vérif + nettoyage nom
    def est_nom_valide(nom: str) -> str | None:
        STOPWORDS = {"de", "la", "le", "et", "des", "du", "l’", "l'", "conformément", "à"}
        EXCLUSIONWORD = [
            "de l'intéressé",
            "et remplacée",
            "de la",
            "l'intéressé et",
            "l'intéressé",
            "suite au",
            "suite aux",
            "en sa qualité d'administrateur des biens de",
            "qualité d'administrateur des biens de",
            "l'égard des biens concernant",
            "à l'égard des biens concernant",
            "conformément à",
            "modifié les mesures de protection à l'égard des biens de",
            "l'égard des biens de",
            "à l'égard des biens de",
            "des biens de",
            "désigné par ordonnance",
            "a désigné par ordonnance",
            "d'administrateur",
            "la succession réputée vacante de",
            "division", "décision", "avenue", "rue", "suppléant",
            "tribunal", "parquet", "qualité", "curateur", "jugement"
        ]

        NOISE_TOKENS = {"alias", "dit", "époux", "épouse", "conjoint", "veuve", "veuf", "succession de", "domicilié", "domicilié,"}

        if not isinstance(nom, str):
            return None

            # On conserve l’original pour la sortie
        original = nom.strip()

        # version normalisée uniquement pour les tests
        norm = normaliser_espaces_invisibles(nom).replace("’", "'").lower()

        for bad in EXCLUSIONWORD:
            if bad.lower() in norm:
                return None

        tokens = norm.split()
        print(tokens)
        # 🔹 Découpage en tokens pour filtrer les parasites

        if len(tokens) < 2 or len("".join(tokens)) < 3:
            return None
        if len(tokens) == 2 and any(t in STOPWORDS for t in tokens):
            return None
        if all(t in STOPWORDS for t in tokens):
            return None
        # --- nettoyage des NOISE_TOKENS dans original
        pattern_noise = r"\b(" + "|".join(map(re.escape, NOISE_TOKENS)) + r")\b"
        cleaned = re.sub(pattern_noise, " ", original, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned if cleaned else None
    if isinstance(nom, dict):
        # canonicals
        cleaned = []
        for c in (nom.get("canonicals") or []):
            c_clean = est_nom_valide(c)
            if c_clean:
                cleaned.append(c_clean)
        nom["canonicals"] = cleaned

        # records
        new_records = []
        for r in nom.get("records", []):
            c_clean = est_nom_valide(r.get("canonical", ""))
            if c_clean:
                r["canonical"] = c_clean
                new_records.append(r)
        nom["records"] = new_records

        # aliases_flat
        cleaned = []
        for a in (nom.get("aliases_flat") or []):
            a_clean = est_nom_valide(a)
            if a_clean:
                cleaned.append(a_clean)
        nom["aliases_flat"] = cleaned


    elif isinstance(nom, list):
        doc["nom"] = [s for s in nom if est_nom_valide(s)]

    elif isinstance(nom, str):
        if not est_nom_valide(nom):
            doc["nom"] = None

    # 🔔 Vérifier si aucun nom exploitable après nettoyage
    if not doc.get("nom"):  # None, [] ou dict vide
            logger_nomspersonnes.warning(
                f"[AUCUN NOM] DOC={doc.get('doc_hash')} | Nom brut avant nettoyage='{nom}'"
            )

    _log_len_mismatch(doc, date_naissance, date_deces, nom)
    _log_nom_repetition_locale_first_token(doc, window=80)  # 👈 ajout ici
    # Si c’est une chaîne → transforme en liste
    if isinstance(adresse, str):
        adresse = [adresse]

    if isinstance(adresse, list):
        seen = set()
        adresse_cleaned = []

        for a in adresse:
            cleaned = a.strip()

            # Normaliser les espaces autour des virgules mais NE PAS les supprimer
            cleaned = re.sub(r'\s*,\s*', ', ', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,.;')

            # Artefact : une lettre isolée avant l’adresse (ex: "e 5600 ...")
            cleaned = re.sub(r'^[A-Za-z]\s+(?=\d{4}\b|[A-ZÀ-ÿ])', '', cleaned)
            # Couper le récit (ex: ", a été", "; BCE", etc.) — ta fonction interne
            cleaned = tronque_texte_apres_adresse(cleaned)
            nombres = re.findall(r'\b\d{1,5}\b', cleaned)

            # Filtrer : si un seul nombre ET c'est un CP → on ignore
            if len(nombres) == 1 and re.fullmatch(r'\d{4}', nombres[0]):
                print(f"[CP SEUL] Écarté : {cleaned}")
                continue
            if not cleaned or len(cleaned.split()) < 2:
                continue

            # CP + Ville seuls (2–4 tokens) → on jette SEULEMENT s'il n'y a pas d'autre nombre que le CP
            # (ça évite de jeter "5600 Philippeville, Gueule-du-Loup(SAU) 161")
            # Détection des adresses type "4032 Liège" → on ne garde pas
            # Mots à nettoyer : matcher en MOT ENTIER pour éviter les faux positifs ("home", etc.)
            if any(re.search(rf"\b{re.escape(tok)}\b", cleaned.lower()) for tok in NETTOIE_ADRESSE_SET):
                continue

            # Exclure institutions : comparer le préfixe avant la 1re virgule ou avant " à "
            cap = cleaned.upper()
            cap_prefix = re.split(r",\s*|\s+À\s+", cap, maxsplit=1)[0]
            if cap_prefix in ADRESSES_INSTITUTIONS_SET:
                continue

            # Déduplication : clé normalisée (sans toucher l’affichage final)
            key = re.sub(r'\s+', ' ', cap)  # tu peux ajouter unidecode si tu veux ignorer les accents
            if key not in seen:
                seen.add(key)
                adresse_cleaned.append(cleaned)

        # ❌ Supprimer trop court / trop long (après tout le reste)
        def nb_mots(s: str) -> int:
            # compte des "mots" alphanum (é, è, etc. inclus)
            return len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", s))


        MIN_MOTS_ADR = 3
        MAX_MOTS_ADR = 14  # ajuste à 14–18 si tu veux

        adresse_cleaned = [
            a for a in adresse_cleaned
            if MIN_MOTS_ADR <= nb_mots(a) <= MAX_MOTS_ADR
        ]
        adresse_cleaned = nettoyer_adresses_par_keyword(adresse_cleaned, word)
        adresse_cleaned = prioriser_adresse_proche_nom_struct(
            doc.get("nom"),
            doc.get("text", ""),
            adresse_cleaned,
        )

        doc["adresse"] = adresse_cleaned if adresse_cleaned else None
        adrs_norm = [re.sub(r"\s+", " ", a).strip() for a in (doc.get("adresse") or []) if
                     isinstance(a, str) and a.strip()]
        if adrs_norm and not has_cp_plus_other_number_aligned(adrs_norm[0]):
            logger_adresses.warning(
                f"[Adresse suspecte] DOC={doc.get('doc_hash')} | 1ère adresse sans (CP + autre n°) : {adrs_norm[0]}"
            )
        verifier_premiere_adresse_apres_nom(
            nom=doc.get("nom"),
            texte=doc.get("text", ""),
            adresse=(doc.get("adresse") or [None])[0],
            doc_hash=doc.get("doc_hash"),
            logger=logger_adresses
        )



if not documents:
    print("❌ Aucun document à indexer.")
    sys.exit(1)
# 🔁 Supprimer les doublons par ID (donc par URL nettoyée)
print("👉 DOC POUR MEILI", doc["url"], "| date_deces =", doc.get("date_deces"))
unique_docs = {}
for doc in documents:
    if doc["doc_hash"] not in unique_docs:
        unique_docs[doc["doc_hash"]] = doc
print(f"[📋] Total de documents avant déduplication: {len(documents)}")
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
            print(f" - URL: {d['url']} | Date: {d['date_doc']}")

# 🔁 Ensuite, suppression des doublons par doc_hash (garde le + récent)
unique_docs = {}
for doc in sorted(documents, key=lambda d: d["date_doc"], reverse=True):
    unique_docs[doc["doc_hash"]] = doc
documents = list(unique_docs.values())
print(f"[✅] Total après suppression des doublons: {len(documents)}")
print(f"[📉] Nombre de doublons supprimés: {len(final)} → {len(documents)}")
print(f"[🔍] Documents uniques pour Meilisearch (par doc_hash): {len(documents)}")

# Supprime explicitement tous les documents avec ces doc_hash
doc_ids = [doc["id"] for doc in documents]
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

test_id = documents[0]["id"]
print(f"\n🔍 Test récupération document avec ID = {test_id}")
try:
    found_doc = index.get_document(test_id)
    print("✅ Document trouvé dans Meilisearch :")
    print(json.dumps(dict(found_doc), indent=2))
except meilisearch.errors.MeilisearchApiError:
    print("❌ Document non trouvé par ID dans Meilisearch.")

# 📝 Sauvegarde en JSON local
os.makedirs("exports", exist_ok=True)
json_path = os.path.join("exports", f"documents_{keyword}.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(documents, f, indent=2, ensure_ascii=False)
print(f"[💾] Fichier JSON sauvegardé : {json_path}")

print("[📥] Mes Logs…")
# 🔔 Log TOUTES les adresses (doublons compris) dans UNE seule entrée par doc
for doc in documents:
    adrs = doc.get("adresse") or []  # toujours une liste
    # normalise un peu et garde même les doublons
    adrs_norm = [re.sub(r"\s+", " ", a).strip() for a in adrs if isinstance(a, str) and a.strip()]
    if not adrs_norm:
        continue

    # Regroupe tout dans un seul champ (séparateur au choix)
    all_in_one = " | ".join(adrs_norm)  # ex: "addr1 | addr2 | addr2 | addr3"
    # --- Récupère UNIQUEMENT le nom canonique depuis doc["nom"] ---
    nom_field = doc.get("nom")
    canon_name = ""

    if isinstance(nom_field, dict):
        # priorité aux canonicals
        canonicals = nom_field.get("canonicals") or []
        if isinstance(canonicals, list) and canonicals:
            canon_name = str(canonicals[0]).strip()
        elif nom_field.get("records"):
            for r in nom_field["records"]:
                if isinstance(r, dict) and isinstance(r.get("canonical"), str) and r["canonical"].strip():
                    canon_name = r["canonical"].strip()
                    break
        elif isinstance(nom_field.get("aliases_flat"), list) and nom_field["aliases_flat"]:
            canon_name = str(nom_field["aliases_flat"][0]).strip()
    elif isinstance(nom_field, list):
        # prend le premier string non vide
        for s in nom_field:
            if isinstance(s, str) and s.strip():
                canon_name = s.strip()
                break
    elif isinstance(nom_field, str):
        canon_name = nom_field.strip()
    logger_adresses.warning(
        f"DOC ID: '{doc['doc_hash']}'\n"
        f"NOM: '{canon_name}'\n"
        f"Adresse log general : '{all_in_one}'\n"
        f"Texte : {doc.get('text', '')}..."
    )

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
    CREATE TABLE IF NOT EXISTS moniteur_documents_postgre (
    id          SERIAL PRIMARY KEY,
    date_doc    DATE,
    lang        TEXT,
    text        TEXT,
    url         TEXT,
    doc_hash    TEXT UNIQUE,
    keyword     TEXT,
    tva         TEXT[],
    titre       TEXT,
    num_nat     TEXT[],
    extra_keyword TEXT,
    nom         TEXT,
    date_naissance        TEXT,
    adresse        TEXT,
    date_jugement TEXT,
    nom_trib_entreprise TEXT,
    date_deces TEXT,
    extra_links TEXT,
    administrateur TEXT,
    nom_interdit TEXT,
    identifiant_terrorisme TEXT[],
    denoms_by_bce TEXT[],
    adresses_by_bce TEXT[]


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
    INSERT INTO moniteur_documents_postgre (
    date_doc, lang, text, url, doc_hash, keyword, tva, titre, num_nat, extra_keyword,nom, 
    date_naissance, adresse, date_jugement, nom_trib_entreprise, date_deces, extra_links, administrateur, nom_interdit, identifiant_terrorisme, denoms_by_bce,     adresses_by_bce TEXT[]

)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s,%s, %s,%s,%s, %s, %s, %s, %s, %s)
ON CONFLICT (doc_hash) DO NOTHING
""", (
        doc["date_doc"],
        doc["lang"],
        text,
        doc["url"],
        doc["doc_hash"],
        doc["keyword"],
        doc["TVA"],
        doc["title"],
        doc["num_nat"],
        doc.get("extra_keyword"),
        doc["nom"],
        doc["date_naissance"],
        doc["adresse"],
        doc["date_jugement"],
        doc["nom_trib_entreprise"],
        doc["date_deces"],
        doc.get("extra_links"),
        doc["administrateur"],
        doc["nom_interdit"],
        doc["identifiant_terrorisme"],
        doc["denoms_by_bce"],
        doc["adresses_by_bce"]

    ))

conn.commit()
cur.close()
conn.close()
print("[✅] Insertion PostgreSQL terminée.")
