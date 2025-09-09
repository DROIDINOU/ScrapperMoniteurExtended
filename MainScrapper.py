# --- Imports standards ---
import concurrent.futures
import json
import locale
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from typing import List, Tuple

from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

# --- Bibliothèques tierces ---
import fitz  # PyMuPDF
import meilisearch
import psycopg2
import pytesseract
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from dotenv import load_dotenv
from PIL import Image
# from psycopg2.extras import Json
from tqdm import tqdm

# --- Modules internes au projet ---
from logger_config import setup_logger, setup_fallback3_logger, setup_dynamic_logger
from Constante.mesconstantes import BASE_URL, ADRESSES_INSTITUTIONS, ADRESSES_INSTITUTIONS_SET, NETTOIE_ADRESSE_SET
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
from Extraction.Dates.extraction_date_jugement import extract_jugement_date, extract_date_after_rendu_par
from Utilitaire.ConvertDateToMeili import convertir_date
from Utilitaire.outils.MesOutils import get_month_name, detect_erratum, extract_numero_tva, \
    extract_clean_text, clean_url, generate_doc_hash_from_html, convert_french_text_date_to_numeric\
    , clean_date_jugement, _norm_nrn, extract_nrn_variants, has_person_names, decode_nrn, norm_er, \
    liste_vide_ou_que_vides_lenient, clean_nom_trib_entreprise, build_denom_index, format_bce, chemin_csv, \
    build_address_index, _norm_spaces, digits_only, prioriser_adresse_proche_nom_struct, \
    strip_html_tags, extract_page_index_from_url, has_cp_plus_other_number
from ParserMB.MonParser import find_linklist_in_items, retry, get_publication_pdfs_for_tva, \
    convert_pdf_pages_to_text_range
from extractbis import extract_person_names

assert len(sys.argv) == 2, "Usage: python MainScrapper.py \"mot+clef\""
keyword = sys.argv[1]

# ---------------------------------------------------------------------------------------------------------------------
#                                    CONFIGURATION DES LOGGERS
# ----------------------------------------------------------------------------------------------------------------------
logger = setup_logger("extraction", level=logging.DEBUG)
logger.debug("✅ Logger initialisé dans le script principal.")

loggerfallback3 = setup_fallback3_logger("fallback3", level=logging.DEBUG)
loggerfallback3.debug("✅ Logger initialisé dans le script principal.")

# Par exemple pour la catégorie "succession"
logger_adresses = setup_dynamic_logger(name="adresses_logger", keyword=keyword, level=logging.DEBUG)
logger_adresses.debug("🔍 Logger 'adresses_logger' initialisé pour les adresses.")

# Par exemple pour la catégorie "succession"
logger_nomspersonnes = setup_dynamic_logger(name="nomspersonnes_logger", keyword=keyword, level=logging.DEBUG)
logger_nomspersonnes.debug("🔍 Logger 'nomspersonnes_logger' initialisé pour les noms.")

logger_nomsterrorisme = setup_dynamic_logger(name="nomsterrorisme_logger", keyword=keyword, level=logging.DEBUG)
logger_nomsterrorisme.debug("🔍 Logger 'nomsterrorisme_logger' initialisé pour les noms terrorisme.")
print(">>> CODE À JOUR")

logged_adresses: set[tuple[str, str]] = set()

# ---------------------------------------------------------------------------------------------------------------------
#                                          VARIABLES D ENVIRONNEMENT
# ----------------------------------------------------------------------------------------------------------------------
load_dotenv()
MEILI_URL = os.getenv("MEILI_URL")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")

# ---------------------------------------------------------------------------------------------------------------------
#                                            CONSTANTES MAINSCRAPPER
# ----------------------------------------------------------------------------------------------------------------------
# +++++++++++++++++++++++++++++++++++++++++++++++++
# DEMOM_INDEX : pour fichier csv bce denominations
# ADRESSES_INDEX : pour fichier csv bce adresses
# +++++++++++++++++++++++++++++++++++++++++++++++++
DENOM_INDEX = build_denom_index(
    chemin_csv("denomination.csv"),
    allowed_types=None,   # {"001","002"} si tu veux filtrer
    allowed_langs=None,   # {"2"} si tu veux uniquement FR
    skip_public=True
)

ADDRESS_INDEX = build_address_index(
    chemin_csv("address.csv"),
    lang="FR",           # "FR" ou "NL" (fallback auto si champ vide)
    allowed_types=None,  # ex: {"REGO","SEAT"} pour filtrer certains types d’adresse
    skip_public=True
)

# +++++++++++++++++++++++++++++++++++++++++++++++++
#  REGEX COMPILES: Code postal - Numéro BCE
# +++++++++++++++++++++++++++++++++++++++++++++++++
POSTAL_RE = re.compile(r"\b[1-9]\d{3}\s+[A-Za-zÀ-ÿ'’\- ]{2,}\b")
BCE_RE = re.compile(r"\b\d{3}\.\d{3}\.\d{3}\b")


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
        lines = [_norm_spaces(ln) for ln in text.split("\n") if ln.strip()]

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


from_date = date.fromisoformat("2025-07-01")
to_date = "2025-07-04"  # date.today()
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


def scrap_informations_from_url(session, url, numac, date_doc, langue, keyword, title, subtitle):
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
                    None, title, subtitle, None, extra_keywords, None, None, None, None, nom_trib_entreprise, None, None,
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
    nom = extract_name_from_text(str(main), keyword, doc_id=doc_id)
    raw_naissance = extract_date_after_birthday(str(main))  # liste ou str
    if isinstance(raw_naissance, list):
        raw_naissance = [norm_er(s) for s in raw_naissance]
    elif isinstance(raw_naissance, str):
        raw_naissance = norm_er(raw_naissance)
    date_naissance = convertir_date(raw_naissance)  # -> liste ISO ou None

    adresse = extract_address(str(texte_brut), doc_id=doc_id)
    if not date_jugement:
        date_jugement = extract_jugement_date(str(texte_brut))

    if re.search(r"succession[s]?", keyword, flags=re.IGNORECASE):
        raw_deces = extract_dates_after_decede(str(texte_brut), first_only=False)  # liste ou str

        # Normalise les "er" dans la/les dates extraites
        def _norm_er(x):
            if isinstance(x, str):
                x = re.sub(r"\b(\d{1,2})\s*er\s*er\b", r"\1er", x)
                x = re.sub(r"\b(\d{1,2})\s*er\b", r"\1", x)
                return x
            return x

        if isinstance(raw_deces, list):
            raw_deces = [_norm_er(s) for s in raw_deces]
        elif isinstance(raw_deces, str):
            raw_deces = _norm_er(raw_deces)

        date_deces = convertir_date(raw_deces)  # -> liste ISO ou None
        adresse = extract_address(str(texte_brut), doc_id=doc_id)
        detect_succession_keywords(texte_brut, extra_keywords)

    if re.search(r"tribunal[\s+_]+de[\s+_]+premiere[\s+_]+instance", keyword, flags=re.IGNORECASE | re.DOTALL):
        if re.search(r"\bsuccessions?\b", texte_brut, flags=re.IGNORECASE):
            raw_deces = extract_dates_after_decede(str(main))

            def _norm_er(x):
                if isinstance(x, str):
                    x = re.sub(r"\b(\d{1,2})\s*er\s*er\b", r"\1er", x)
                    x = re.sub(r"\b(\d{1,2})\s*er\b", r"\1", x)
                    return x
                return x

            if isinstance(raw_deces, list):
                raw_deces = [_norm_er(s) for s in raw_deces]
            elif isinstance(raw_deces, str):
                raw_deces = _norm_er(raw_deces)

            date_deces = convertir_date(raw_deces)

        administrateur = trouver_personne_dans_texte(texte_brut, chemin_csv("curateurs.csv"),
                                                     ["avocate", "avocat", "Maître", "bureaux", "cabinet", "curateur"])
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
        adresse = prioriser_adresse_proche_nom_struct(nom, texte_brut, adresse)

    if re.search(r"tribunal\s+de\s+l", keyword.replace("+", " "), flags=re.IGNORECASE):

        # verifier a quoi sert id ici
        nom_interdit = extraire_personnes_interdites(texte_brut) # va falloir deplacer dans fonction ?
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
        nom = extract_name_from_text(texte_brut)

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

        # Normalise les "er" dans la/les dates extraites
        def _norm_er(x):
            if isinstance(x, str):
                x = re.sub(r"\b(\d{1,2})\s*er\s*er\b", r"\1er", x)
                x = re.sub(r"\b(\d{1,2})\s*er\b", r"\1", x)
                return x
            return x

        if isinstance(raw_deces, list):
            raw_deces = [_norm_er(s) for s in raw_deces]
        elif isinstance(raw_deces, str):
            raw_deces = _norm_er(raw_deces)

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
        tvas, title, subtitle, nns, extra_keywords, nom, date_naissance, adresse, date_jugement, nom_trib_entreprise,
        date_deces, extra_links, administrateur, doc_id, nom_interdit, identifiants_terrorisme, denoms_by_bce, adresses_by_bce
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
    "id", "date_doc", "title", "keyword", "extra_keyword", "nom", "date_jugement", "TVA",
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
            cleaned = a.strip()

            # Normaliser les espaces autour des virgules mais NE PAS les supprimer
            cleaned = re.sub(r'\s*,\s*', ', ', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,.;')

            # Artefact : une lettre isolée avant l’adresse (ex: "e 5600 ...")
            cleaned = re.sub(r'^[A-Za-z]\s+(?=\d{4}\b|[A-ZÀ-ÿ])', '', cleaned)

            # Couper le récit (ex: ", a été", "; BCE", etc.) — ta fonction interne
            cleaned = tronque_texte_apres_adresse(cleaned)

            # Trop court / vide après tronquage
            if not cleaned or len(cleaned.split()) < 2:
                continue

            # CP + Ville seuls (2–4 tokens) → on jette SEULEMENT s'il n'y a pas d'autre nombre que le CP
            # (ça évite de jeter "5600 Philippeville, Gueule-du-Loup(SAU) 161")
            has_only_cp = (
                    re.fullmatch(r"\d{4}\s+[A-ZÀ-ÿ][\wÀ-ÿ'’\-() ]{1,}$", cleaned) and
                    not re.search(r"\b\d{1,4}(?:[A-Za-z](?!\s*\.))?(?:/[A-ZÀ-ÿ0-9\-]+)?\b", cleaned)
            )
            if has_only_cp:
                continue

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

        doc["adresse"] = adresse_cleaned if adresse_cleaned else None
        adrs_norm = [re.sub(r"\s+", " ", a).strip() for a in (doc.get("adresse") or []) if
                     isinstance(a, str) and a.strip()]
        if adrs_norm and not has_cp_plus_other_number(adrs_norm[0]):
            logger_adresses.warning(
                f"[Adresse suspecte] DOC={doc.get('doc_hash')} | 1ère adresse sans (CP + autre n°) : {adrs_norm[0]}"
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
        f"Adresse incomplète ou suspecte : '{all_in_one}'\n"
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
