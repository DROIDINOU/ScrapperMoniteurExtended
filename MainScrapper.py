
# ------------------------------------------------------------------------------------------------------
# A FAIRE
# cacher le champ nom meili rgpd
# supprimer tqdm en prod
# supprimer champs devenus inutiles
# failed urls
# faire les loggers
# Pour ton cas (Moniteur belge, plusieurs juridictions, mêmes champs globaux) :
# ➤ Garde un seul index global.
# ➤ Ajoute une pondération contextuelle dans la recherche,ou un champ fiabilité_nom_trib_entreprise.
# On va détailler calmement, car la différence entre raise et sys.exit() est fondamentale
# en architecture logicielle, surtout en prod.
# Commandes :
#            (venv) C:\Users\32471\ScrapperCJCE>del cache_bce\bce_indexes.pkl
#            (venv) C:\Users\32471\ScrapperCJCE>del .cache\denomination.denoms
# ------------------------------------------------------------------------------------------------------
# --- Imports standards ---
import concurrent.futures
import json
import locale
import logging
import os
import time
import re
import sys
import csv
from collections import defaultdict
from datetime import date
from functools import wraps

# --- Bibliothèques tierces ---
import meilisearch
import psycopg2
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tqdm import tqdm

# --- Modules internes au projet ---
from logger_config import setup_logger, setup_dynamic_logger
from Constante.mesconstantes import BASE_URL, ADRESSES_INSTITUTIONS_SET, NETTOIE_ADRESSE_SET, POSTAL_RE, BCE_RE
from Extraction.NomPrenom.extraction_noms_personnes_physiques import extract_name_from_text
from Extraction.NomPrenom.extraction_nom_interdit import extraire_personnes_interdites
from Extraction.Adresses.extract_adresses_entreprises import extract_add_entreprises
from Extraction.Denomination.extraction_entites_radiees import extract_noms_entreprises_radiees
from Extraction.Adresses.extraction_adresses_moniteur import extract_address
from Extraction.Denomination.extraction_nom_entreprises import extract_noms_entreprises
from Extraction.Gerant.extraction_administrateurs import extract_administrateur
from Extraction.Keyword.tribunal_entreprise_keyword import detect_tribunal_entreprise_keywords
from Extraction.Keyword.tribunal_premiere_instance_keyword import detect_tribunal_premiere_instance_keywords
from Extraction.Keyword.cour_appel_keyword import detect_courappel_keywords
from Extraction.Keyword.radiation_keyword import detect_radiations_keywords
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
    remove_av_parentheses, to_list_dates, names_list_from_nom, \
    remove_duplicate_paragraphs, dedupe_phrases_ocr, tronque_texte_apres_adresse, strip_accents, \
    normaliser_espaces_invisibles, fetch_ejustice_article_names_by_tva, corriger_tva_par_nom
from Utilitaire.outils.MesOutils import charger_indexes_bce
from ParserMB.MonParser import find_linklist_in_items, retry, convert_pdf_pages_to_text_range


def main():
    # ------------------------------------------------------------------------------------------------------------------
    # CONFIGURATION DE LA PÉRIODE ET DES VARIABLES DE SCRAPING ( à ameliorer)
    # ------------------------------------------------------------------------------------------------------------------
    assert len(sys.argv) == 2, "Usage: python MainScrapper.py \"mot+clef\""
    keyword = sys.argv[1]
    from_date = date.fromisoformat("2025-06-26")  # début
    to_date = date.today()  # fin
    locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")
    # --------------------------------------------------------------------------------------------------------------
    #                 CHARGEMENT DES INDEX BCE
    # --------------------------------------------------------------------------------------------------------------
    print("[📦] Chargement initial des indexes BCE…")
    denom_index, personnes_physiques, address_index, enterprise_index, establishment_index = charger_indexes_bce()
    print("[✅] Index BCE chargés :", len(denom_index or {}), "entrées")
    # A vérifier / modifier
    if not denom_index:
        raise RuntimeError("❌ Index BCE vides — vérifie le fichier CSV ou pickle.")
    # --------------------------------------------------------------------------------------------------------------
    #                 CONSTRUCTION FICHIER EXPORTS CONTENANT DONNEES NECESSAIRE A APPEL ANNEXES MONITEUR
    # --------------------------------------------------------------------------------------------------------------
    export_dir = "exports"
    os.makedirs(export_dir, exist_ok=True)
    csv_path = os.path.join(export_dir, "moniteur_enrichissement.csv")
    # --------------------------------------------------------------------------------------------------------------
    #                                    CONFIGURATION DES LOGGERS
    # --------------------------------------------------------------------------------------------------------------
    # **** LOGGER GENERAL
    logger = setup_logger("extraction", level=logging.DEBUG)
    logger.debug("✅ Logger initialisé dans le script principal.")

    # *** LOGGERS champs manquants obligatoires
    logger_champs_manquants_obligatoires = setup_dynamic_logger(name="champs_manquants_obligatoires",
                                                                keyword=keyword, level=logging.DEBUG)
    logger_champs_manquants_obligatoires.debug("🔍 Logger 'champs_manquants_obligatoires' initialisé "
                                               "pour les champs"
                                               " obligatoires.")
    # verifier avant suppression
    logged_adresses: set[tuple[str, str]] = set()
    print(">>> CODE À JOUR")

    # ---------------------------------------------------------------------------------------------------------------------
    #                                          VARIABLES D ENVIRONNEMENT
    # ----------------------------------------------------------------------------------------------------------------------
    load_dotenv()
    meili_url = os.getenv("MEILI_URL")
    meili_key = os.getenv("MEILI_MASTER_KEY")
    index_name = os.getenv("INDEX_NAME")
    # ---------------------------------------------------------------------------------------------------------------------
    #                                          VERIFICATION DES ERREURS HTTP
    # -------------------------------------------------------------------------------------------------

    failed_urls = []
    # ---------------------------------------------------------------------------------------------------------------------
    #                                         INITIALISATION MEILISEARCH A MODIFIER EN PROD
    # -------------------------------------------------------------------------------------------------
    max_workers = 12
    TIMEOUT_RESULT = 90
    TIMEOUT_FUTURE = 120
    print("[INFO] Initialisation Meilisearch (au début du script)…")
    client = meilisearch.Client(meili_url, meili_key)
    try:
        index = client.get_index(index_name)
        delete_task = index.delete()
        client.wait_for_task(delete_task.task_uid)
        print(f"[🗑️] Ancien index '{index_name}' supprimé.")
    except meilisearch.errors.MeilisearchApiError:
        print(f"[ℹ️] Aucun index existant à supprimer ({index_name}).")

    create_task = client.create_index(index_name, {"primaryKey": "id"})
    client.wait_for_task(create_task.task_uid)
    index = client.get_index(index_name)
    print(f"[✅] Index '{index_name}' prêt.")

    # --------------------------------------------------------------------------------------------------------------
    #                               FONCTIONS PRINCIPALES D EXTRACTION
    # --------------------------------------------------------------------------------------------------------------

    # Decorator pour limiter la fréquence des requêtes
    def throttle(delay_seconds=6):
        """
        Empêche d'appeler une fonction plus d'une fois toutes les X secondes.
        """

        def decorator(func):
            last_call_time = [0]

            @wraps(func)
            def wrapper(*args, **kwargs):
                now = time.time()
                elapsed = now - last_call_time[0]

                if elapsed < delay_seconds:
                    sleep_time = delay_seconds - elapsed
                    logging.debug(f"[Throttle] Attente de {sleep_time:.1f}s avant appel de {func.__name__}")
                    time.sleep(sleep_time)

                result = func(*args, **kwargs)
                last_call_time[0] = time.time()
                return result

            return wrapper

        return decorator

    @throttle(delay_seconds=6)
    def fetch_ejustice_article_addresses_by_tva(num_tva, page=1):
        """
        Va sur list.pl (Annexe Personnes morales) et récupère toutes les adresses
        affichées juste avant le numéro de TVA tronqué (9 chiffres) dans chaque item.
        """
        num_tva_clean = re.sub(r"\D", "", str(num_tva))

        url = (
            "https://www.ejustice.just.fgov.be/cgi_tsv/list.pl"
            f"?language=fr&sum_date=&page={page}&btw={num_tva_clean}"
        )
        logging.debug(f"[eJustice] URL: {url}")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127 Safari/537.36"
            )
        }

        try:
            resp = requests.get(url, headers=headers, timeout=(3, 10))
            resp.raise_for_status()
        except requests.Timeout:
            logging.warning(f"[eJustice] Timeout pour {url}")
            return []
        except Exception as e:
            logging.warning(f"[eJustice] Erreur {e} sur {url}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        anchors = soup.select("div.list-item--content a.list-item--title")
        logging.debug(f"[eJustice] {len(anchors)} items trouvés pour TVA {num_tva_clean}")

        if not anchors:
            logging.debug(resp.text[:600])
            return []

        addresses = []

        def is_tva_9_digits(line: str) -> bool:
            digits = re.sub(r"\D", "", line)
            return len(digits) == 9

        for a in anchors:
            block = a.get_text(separator="\n", strip=True)
            lines = [ln.strip() for ln in block.split("\n") if ln.strip()]

            for i, ln in enumerate(lines):
                if is_tva_9_digits(ln) and i > 0:
                    addr = lines[i - 1]
                    if addr and addr not in addresses:
                        addresses.append(addr)

        logging.debug(f"[eJustice] {len(addresses)} adresses trouvées pour {num_tva_clean}")
        return addresses


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

    # --------------------------------------------------------------------------------------------------------------
    #                                SCRAPER MONITEUR BELGE (publications tribunaux, listes radiation ...)
    # --------------------------------------------------------------------------------------------------------------
    def scrap_informations_from_url(url, numac, date_doc, langue, keyword, title, subtitle):
        # va certainement falloir enrichir ici
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
            if not response:
                print(f"[❌ Abandon définitif pour {url}]")
                return None  # ⚠️ important : on sort si la page ne répond jamais
            soup = BeautifulSoup(response.text, 'html.parser')
            extra_keywords = []
            extra_links = []

            main = soup.find("main", class_="page__inner page__inner--content article-text")
            if not main:
                return (
                    numac, date_doc, langue, "", url, keyword,
                    None, title, subtitle, None, None, None, None, None,
                    None, None, None, None, None, None, None, None, None, None, None
                )

            texte_brut = extract_clean_text(main, remove_links=False)
            date_jugement = None
            administrateur = None
            nom = None
            nom_trib_entreprise = None
            date_deces = None
            nom_interdit = None
            tvas = extract_numero_tva(texte_brut)
            tvas_valides = [t for t in tvas if format_bce(t)]
            denoms_by_bce = None
            adresses_by_bce = None
            denoms_by_ejustice = None
            adresses_by_ejustice = None
            match_nn_all = extract_nrn_variants(texte_brut)
            nns = match_nn_all
            doc_id = generate_doc_hash_from_html(texte_brut, date_doc)
            if detect_erratum(texte_brut):
                extra_keywords.append("erratum")

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

            if re.search(r"tribunal[\s+_]+de[\s+_]+premiere[\s+_]+instance", keyword, flags=re.IGNORECASE | re.DOTALL):
                if not tvas_valides:
                    return None
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

            # -----------------------------
            # TRIB ENTREPRISE
            # -----------------------------
            if re.search(r"tribunal\s+de\s+l", keyword.replace("+", " "), flags=re.IGNORECASE):
                if not tvas_valides:
                    return None
                # verifier à quoi sert id ici mais pense que peut etre utile
                nom_interdit = extraire_personnes_interdites(texte_brut)  # va falloir deplacer dans fonction ?
                nom_trib_entreprise = extract_noms_entreprises(texte_brut, doc_id=doc_id)
                administrateur = extract_administrateur(texte_brut)
                adresse = extract_add_entreprises(texte_brut, doc_id=doc_id)
                detect_tribunal_entreprise_keywords(texte_brut, extra_keywords)

            # ----------------------------------------------------------------
            # ENTREPRISES RADIEES
            #     > Les entreprises radiees ne sont que des Personnes Morales
            # ----------------------------------------------------------------
            if re.search(r"Liste\s+des\s+entites\s+enregistrees", keyword.replace("+", " "), flags=re.IGNORECASE):
                if not tvas_valides:
                    return None
                nom_trib_entreprise = extract_noms_entreprises_radiees(texte_brut, doc_id=doc_id)
                detect_radiations_keywords(texte_brut, extra_keywords)

            # ------------ -----------------
            # COUR D'APPEL
            # -----------------------------
            # probleme? exemple 730689335c260eba1ea29679ae3c3277759008a345f24b544393667a7e7a8aba
            # pas vraiment je pense en fait (nom et nom trib sont avec du bruit et pas grave
            if re.search(r"cour\s+d", keyword.replace("+", " "), flags=re.IGNORECASE):
                if not tvas_valides:
                    return None
                nom_interdit = extraire_personnes_interdites(texte_brut)
                nom_trib_entreprise = extract_noms_entreprises(texte_brut, doc_id=doc_id)
                detect_tribunal_entreprise_keywords(texte_brut, extra_keywords)
                detect_courappel_keywords(texte_brut, extra_keywords)
                detect_tribunal_premiere_instance_keywords(texte_brut, extra_keywords)
                nom = extract_name_from_text(texte_brut, keyword, doc_id=doc_id)

                # 🧼 Nettoyage spécifique Cour d'appel :
                # Dans les arrêts de cour d'appel, les noms de personnes physiques et les noms de sociétés
                # sont souvent extraits ensemble dans le champ `nom`.
                # Or, les sociétés sont déjà présentes dans `nom_trib_entreprise` (extrait via extract_noms_entreprises).
                # Ce bloc sert à nettoyer `nom` pour ne garder QUE les personnes physiques :
                # on supprime des sous-champs (`records`, `canonicals`, `aliases_flat`)
                # tous les noms qui correspondent à des entreprises déjà détectées.
                # ➤ Objectif : éviter les doublons et le bruit dans Meilisearch ou PostgreSQL.
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

            return (
                numac, date_doc, langue, texte_brut, url, keyword,
                tvas, title, subtitle, nns, extra_keywords, nom, date_naissance, adresse, date_jugement,
                nom_trib_entreprise,
                date_deces, extra_links, administrateur, doc_id, nom_interdit, denoms_by_bce,
                adresses_by_bce, adresses_by_ejustice, denoms_by_ejustice
            )

    # MAIN
    final = []
    with requests.Session() as session:

        raw_link_list = ask_belgian_monitor(session, from_date, to_date, keyword)
        link_list = raw_link_list  # on garde le nom pour compatibilité

        scrapped_data = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    scrap_informations_from_url, url, numac, date_doc, langue, keyword, title, subtitle
                ): url
                for (url, numac, date_doc, langue, keyword, title, subtitle) in link_list
            }

            total = len(futures)
            print(f"[DEBUG] Nombre total de futures : {total}")

            for future in tqdm(
                    concurrent.futures.as_completed(futures),
                    total=total,
                    desc=f"Scraping {keyword}",
            ):
                url = futures[future]
                try:
                    # ⏱️ Timeout dur : 90 s max par tâche
                    result = future.result(timeout=90)
                    if result and isinstance(result, tuple) and len(result) >= 5:
                        scrapped_data.append(result)
                except concurrent.futures.TimeoutError:
                    print(f"[⏰] Timeout sur {url}")
                    failed_urls.append(url)
                except Exception as e:
                    print(f"[❌] Erreur sur {url} : {type(e).__name__} – {e}")
                    failed_urls.append(url)

        print(f"[DEBUG] Futures terminées : {sum(f.done() for f in futures)} / {len(futures)}")
        print(f"[📉] Pages échouées : {len(failed_urls)} / {len(link_list)}")

        # --- 🔁 Sauvegarde pour relancer plus tard ---
        if failed_urls:
            with open("failed_urls.txt", "w", encoding="utf-8") as f:
                for u in failed_urls:
                    f.write(u + "\n")
            print("📄 Fichier 'failed_urls.txt' créé avec les pages à relancer.")

    # ✅ Supprime les None avant de les envoyer à Meilisearch
    final.extend(scrapped_data)  # ou final = [r for r in scrapped_data if r is not None]

    start_time = time.perf_counter()

    # ⚙️ 3️⃣ Configuration des attributs
    index.update_filterable_attributes(["keyword"])
    index.update_searchable_attributes([
        "id", "date_doc", "title", "keyword", "nom", "date_jugement", "TVA",
        "extra_keyword", "num_nat", "date_naissance", "adresse", "nom_trib_entreprise",
        "date_deces", "extra_links", "administrateur", "nom_interdit",
        "text", "denoms_by_bce", "adresses_by_bce", "adresses_by_ejustice", "denoms_by_ejustice"
    ])
    index.update_displayed_attributes([
        "id", "date_doc", "title", "keyword", "extra_keyword", "nom",
        "date_jugement", "TVA", "num_nat", "date_naissance", "adresse",
        "nom_trib_entreprise", "date_deces", "extra_links", "administrateur",
        "text", "url", "nom_interdit",
        "denoms_by_bce", "adresses_by_bce", "adresses_by_ejustice", "denoms_by_ejustice"
    ])

    print(f"[⚙️] Index '{index_name}' prêt en {time.perf_counter() - start_time:.2f}s.")
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
                "id": doc_hash,  # ✅ doc_id (hash unique généré)
                "date_doc": record[1],  # date du document
                "lang": record[2],  # langue
                "text": record[3],  # texte brut
                "url": cleaned_url,  # URL nettoyée
                "keyword": record[5],  # mot-clé
                "TVA": record[6],  # liste de TVA
                "title": record[7],
                "subtitle": record[8],
                "num_nat": record[9],  # numéros nationaux (NN)
                "extra_keyword": record[10],  # mots-clés supplémentaires
                "nom": record[11],  # noms de personnes
                "date_naissance": record[12],
                "adresse": record[13],
                "date_jugement": record[14],
                "nom_trib_entreprise": record[15],
                "date_deces": record[16],
                "extra_links": record[17],
                "administrateur": record[18],
                "nom_interdit": record[20],
                "denoms_by_bce": record[21],
                "adresses_by_bce": record[22],
                "adresses_by_ejustice": record[23],
                "denoms_by_ejustice": record[24]
            }

            # rien a faire dans meili mettre dans postgre
            # if record[6]:
            # doc["publications_pdfs"] = get_publication_pdfs_for_tva(session, record[6][0])
            documents.append(doc)

            # 🔎 Indexation unique des dénominations TVA (après avoir rempli documents[])
            print("🔍 Indexation des dénominations par TVA (1 seule lecture du CSV)…")

            # ✅ Forcer administrateur à être une liste si ce n’est pas None
            if isinstance(doc["administrateur"], str):
                doc["administrateur"] = [doc["administrateur"]]
            elif doc["administrateur"] is None:
                doc["administrateur"] = None
            elif not isinstance(doc["administrateur"], list):
                doc["administrateur"] = [str(doc["administrateur"])]

    # --------------------------------------------------------------------------------------------------------------
    # LOGGERS EN CAS DE CHAMPS OBLIGATOIRE VIDE (Pour tous les mots clefs)
    # Champs obligatoires : id - date_doc - text - keyword -extra_keyword - TVA
    # --------------------------------------------------------------------------------------------------------------
    for doc in documents:
        missing = []
        if not doc.get("id"):
            missing.append("id")
        if not doc.get("date_doc"):
            missing.append("date_doc")
        if not doc.get("text"):
            missing.append("text")
        if not doc.get("keyword"):
            missing.append("keyword")
        if not doc.get("extra_keyword"):
            missing.append("extra_keyword")
        if not doc.get("TVA"):
            missing.append("TVA")

        if missing:
            logger.warning(f"[❌ Champs manquants] DOC={doc.get('id')} | Manquants: {missing}")

    # --------------------------------------------------------------------------------------------------------------
    # 🧩 Enrichissement BCE (toujours crée les champs, même vides)
    # --------------------------------------------------------------------------------------------------------------

    for doc in documents:
        # Initialisation systématique
        doc["denoms_by_bce"] = None
        doc["adresses_by_bce"] = None

        # ⚠️ Ignorer les doublons annulés
        if "annulation_doublon" in (doc.get("extra_keyword") or []):
            continue

        tvas = doc.get("TVA") or []
        denoms_map = {}
        adresses_map = {}

        for tva in tvas:
            bce = format_bce(tva)
            if not bce:
                continue

            # 🔹 Dénominations + type d'entité
            noms = sorted(denom_index.get(bce, []))
            type_ent = personnes_physiques.get(bce, "inconnu")  # "physique" ou "morale"

            if noms:
                denoms_map[bce] = {
                    "type": type_ent,
                    "noms": noms
                }

            # 🔹 Adresses (siège + établissements)
            adresses = []
            if bce in address_index:
                adresses.extend(
                    {"adresse": addr, "source": "siege"} for addr in address_index[bce]
                )

            if bce in establishment_index:
                for etab in establishment_index[bce]:
                    etab_norm = re.sub(r"\D", "", etab)
                    if etab_norm in address_index:
                        adresses.extend(
                            {"adresse": addr, "source": "etablissement"}
                            for addr in address_index[etab_norm]
                        )

            if adresses:
                adresses_map[bce] = adresses

        # ✅ Affectation finale : TOUJOURS créer les champs
        doc["denoms_by_bce"] = (
            [
                {"bce": bce, "type": data["type"], "noms": data["noms"]}
                for bce, data in denoms_map.items()
            ]
            if denoms_map else None
        )

        doc["adresses_by_bce"] = (
            [{"bce": bce, "adresses": adresses} for bce, adresses in adresses_map.items()]
            if adresses_map else None
        )

    # ✅ Fallback eJustice séparé — NE PAS ÉCRASER adresses_by_bce
    for doc in documents:
        if not doc.get("adresses_by_bce"):
            adresses_ejustice = []

            # Exemple si tu veux réactiver la récupération plus tard :
            # for t in (doc.get("TVA") or []):
            #     found = fetch_ejustice_article_addresses_by_tva(t)
            #     for addr in found:
            #         adresses_ejustice.append({"adresse": addr, "source": "ejustice"})

            # ✅ Nouveau format compatible Meilisearch (liste d’objets)
            doc["adresses_by_ejustice"] = (
                [{"adresse": addr.get("adresse"), "source": addr.get("source", "ejustice")}
                 for addr in adresses_ejustice]
                if adresses_ejustice else None
            )

    # 🚨 Nouveau bloc séparé : enrichissement e-Justice
    for doc in documents:
        tvas = doc.get("TVA") or []
        noms_from_ejustice = []

        # Exemple si tu veux réactiver plus tard :
        # if tvas:
        #     try:
        #         noms_from_ejustice = fetch_ejustice_article_names_by_tva(tva=tvas[0])
        #     except Exception as e:
        #         logger.warning(f"[e-Justice fetch] DOC={doc.get('doc_hash')} | err={e}")

        # ✅ Nouveau format compatible Meilisearch
        doc["denoms_by_ejustice"] = (
            [{"bce": tva, "noms": noms_from_ejustice}]
            if noms_from_ejustice else None
        )

    # On va faire les logs ici
    # 🧼 Nettoyage des champs adresse : suppression des doublons dans la liste
    # 🧼 Nettoyage des champs noms

    # ✅ Vérification pour tribunal de l’entreprise sans BCE
    for doc in documents:
        if doc.get("keyword") and "tribunal de l" in doc["keyword"].lower():
            if not doc.get("denoms_by_bce") and not doc.get("adresses_by_bce"):
                logger_bce.warning(
                    f"[⚠️ Tribunal entreprise sans BCE] "
                    f"DOC={doc.get('id')} | URL={doc.get('url')}"
                )
    # --------------------------------------------------------------------------------------------------------------
    #                             NETTOYAGE ADRESSE ET NOMS
    # --------------------------------------------------------------------------------------------------------------
    for doc in documents:
        adresse = doc.get("adresse")
        word = doc.get("keyword")
        nom = doc.get("nom")

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

            NOISE_TOKENS = {"alias", "dit", "époux", "épouse", "conjoint", "veuve", "veuf", "succession de",
                            "domicilié", "domicilié,"}

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

    # --------------------------------------------------------------------------------------------------------------
    #                                       VERIFIVATION FINALE AVANT D ENVOYER A MEILI
    # --------------------------------------------------------------------------------------------------------------
    if not documents:
        print("❌ Aucun document à indexer.")
        sys.exit(1)

    # 🔍 Log des doublons avant déduplication
    print(f"[📋] Total initial de documents : {len(documents)}")
    hash_to_docs = defaultdict(list)
    for doc in documents:
        hash_to_docs[doc["id"]].append(doc)

    duplicates = {h: docs for h, docs in hash_to_docs.items() if len(docs) > 1}
    if duplicates:
        print(f"[⚠️] {len(duplicates)} doublons détectés avant nettoyage :")
        for h, docs in duplicates.items():
            print(f" - id = {h} (×{len(docs)})")
            for d in docs:
                print(f"    • URL: {d['url']} | Date: {d['date_doc']}")
    else:
        print("[✅] Aucun doublon détecté avant nettoyage.")

    # 🔁 Garde uniquement le plus récent par id
    unique_docs = {}
    for doc in sorted(documents, key=lambda d: d["date_doc"], reverse=True):
        unique_docs[doc["id"]] = doc
    documents = list(unique_docs.values())

    print(f"[✅] Total après déduplication : {len(documents)}")

    # 🚀 Indexation vers Meilisearch
    batch_size = 3000
    task_ids = []
    print(f"[📦] Indexation de {len(documents)} documents en batchs de {batch_size}…")

    for i in tqdm(range(0, len(documents), batch_size), desc="Envoi vers Meilisearch"):
        batch = documents[i:i + batch_size]
        task = index.add_documents(batch)
        task_ids.append(task.task_uid)

    # 🕒 Attente de la complétion
    print(f"[⏳] Attente de {len(task_ids)} tâches Meili…")
    for uid in task_ids:
        client.wait_for_task(uid, timeout_in_ms=180_000)
        task_info = client.get_task(uid)
        print(f" - Task {uid} → {task_info.status}")
        if task_info.status == "failed":
            print(f"   ❌ Erreur : {task_info.error}")

    # 📊 Vérifie résultat final
    stats = index.get_stats()
    print(f"[📊] Documents réellement indexés dans Meili : {stats.number_of_documents}")
    # ===============================================================================================================

    #                     -> CSV APPEL ANNEXES MONITEUR BELGE
    #                     -> POSTGRE
    #                     -> json file reconstruction meili
    # ===============================================================================================================

    # --------------------------------------------------------------------------------------------------------------
    #                   FICHIERS CSV CONTENANT LES DONNES NECESSAIRES POUR LES APPELS AUX ANNEXES
    #                                             DU MONITEUR BELGE
    # --------------------------------------------------------------------------------------------------------------
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["tva", "id", "url", "keyword", "denoms_by_bce", "adresses_by_bce"])
        for doc in documents:
            for tva in doc.get("TVA", []):
                writer.writerow([tva, doc["id"], doc["url"], doc["keyword"], doc["denoms_by_bce"],
                                 doc["adresses_by_bce"]])
    # --------------------------------------------------------------------------------------------------------------
    #                                                    BASE DE DONNEE : POSTGRE
    #
    # --------------------------------------------------------------------------------------------------------------
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
                        denoms_by_bce TEXT[],
                        adresses_by_bce TEXT[],
                        denoms_by_ejustice TEXT[]
                    
                    
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
                        date_doc, lang, text, url, keyword, tva, titre, num_nat, extra_keyword,nom, 
                        date_naissance, adresse, date_jugement, nom_trib_entreprise, date_deces, extra_links, administrateur, 
                        nom_interdit, denoms_by_bce,adresses_by_bce TEXT[]
                    
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s,%s, %s,%s,%s, %s, %s, %s, %s,%s)
                    ON CONFLICT (id) DO NOTHING
                    """, (
            doc["date_doc"],
            doc["lang"],
            text,
            doc["url"],
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
            doc["denoms_by_bce"],
            doc["adresses_by_bce"],
            doc["denoms_by_ejustice"]

        ))

    conn.commit()
    cur.close()
    conn.close()
    print("[✅] Insertion PostgreSQL terminée.")

    # --------------------------------------------------------------------------------------------------------------
    #                                 FICHIERS CSV CONTENANT LES DONNES INSEREES DANS MEILI
    # --------------------------------------------------------------------------------------------------------------
    # 📝 Sauvegarde finale en JSON local (version enrichie)
    os.makedirs("exports", exist_ok=True)
    json_path = os.path.join("exports", f"documents_enrichis_{keyword}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)

    print(f"[💾] Fichier JSON enrichi sauvegardé : {json_path}")


if __name__ == "__main__":
    main()
