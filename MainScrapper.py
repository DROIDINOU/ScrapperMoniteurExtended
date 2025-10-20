
# ------------------------------------------------------------------------------------------------------
# A FAIRE
# supprimer tqdm en prod
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
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tqdm import tqdm

# --- Modules internes au projet ---
from logger_config import setup_logger, setup_dynamic_logger
from Constante.mesconstantes import BASE_URL
# EXTRACTION DES MOTS CLEFS
from Extraction.Keyword.tribunal_entreprise_keyword import detect_tribunal_entreprise_keywords
from Extraction.Keyword.tribunal_premiere_instance_keyword import detect_tribunal_premiere_instance_keywords
from Extraction.Keyword.cour_appel_keyword import detect_courappel_keywords
from Extraction.Keyword.radiation_keyword import detect_radiations_keywords
# EXTRACTION DES MANDATAIRES (curateurs/liquidateurs)
from Extraction.Gerant.extraction_administrateurs import extract_administrateur
from Extraction.MandataireJustice.extraction_mandataire_justice_gen import trouver_personne_dans_texte
# EXTRACTION DATE JUGEMENT
from Extraction.Dates.extraction_date_jugement import extract_jugement_date
from Utilitaire.ConvertDateToMeili import convertir_date
from Utilitaire.outils.MesOutils import detect_erratum, extract_numero_tva, \
    extract_clean_text, clean_url, generate_doc_hash_from_html, \
    clean_date_jugement, extract_nrn_variants, norm_er, \
    format_bce, chemin_csv, dedupe_admins, \
    normaliser_espaces_invisibles, charger_indexes_bce, \
    verifier_tva_belge
from ParserMB.MonParser import find_linklist_in_items, retry
# Base de données POSTGRE
from BaseDeDonnees.creation_tables import create_table_moniteur
from BaseDeDonnees.insertion_moniteur import insert_documents_moniteur


def main():
    # ------------------------------------------------------------------------------------------------------------------
    # CONFIGURATION DE LA PÉRIODE ET DES VARIABLES DE SCRAPING ( à ameliorer)
    # ------------------------------------------------------------------------------------------------------------------
    assert len(sys.argv) == 2, "Usage: python MainScrapper.py \"mot+clef\""
    keyword = sys.argv[1]
    from_date = date.fromisoformat("2024-04-01")  # début
    to_date = date.fromisoformat("2024-06-30")  # date.today()  # fin
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
    # *** LOGGER Tva invalide
    logger_tva_invalide = setup_dynamic_logger(name="tva_invalide", keyword=keyword, level=logging.DEBUG)
    logger_tva_invalide.debug("🔍 Logger 'tva_invalide' initialisé ")
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
    # remplacer en prod par ceci a retravailler eventuellement
    """client = meilisearch.Client(meili_url, meili_key)
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
"""
    # --------------------------------------------------------------------------------------------------------------
    #                               FONCTIONS PRINCIPALES D EXTRACTION
    # --------------------------------------------------------------------------------------------------------------

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

    def ask_belgian_monitor(http_session, start_date, end_date, motclef):
        page_amount = get_page_amount(http_session, start_date, end_date, motclef)
        print(f"[INFO] Pages à scraper pour '{motclef}': {page_amount}")
        link_list = []

        def process_page(page):
            encoded = motclef.replace(" ", "+")
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
                if motclef == "Liste+des+entites+enregistrees" and \
                        subtitle_text == "Service public fédéral Economie, P.M.E., Classes moyennes et Énergie":
                    find_linklist_in_items(item, motclef, link_list)
                elif motclef == "Conseil+d+'+Etat" and subtitle_text == "Conseil d'État" \
                        and title.lower().startswith("avis prescrit"):
                    find_linklist_in_items(item, motclef, link_list)
                elif motclef == "Cour+constitutionnelle" and subtitle_text == "Cour constitutionnelle":
                    find_linklist_in_items(item, motclef, link_list)

                elif motclef in "tribunal+de+premiere+instance":
                    if title.lower().startswith("tribunal de première instance"):
                        find_linklist_in_items(item, motclef, link_list)

                elif motclef in "tribunal+de+l":
                    if (
                            title.lower().startswith("tribunal de l")

                    ):
                        find_linklist_in_items(item, motclef, link_list)

                elif motclef in "cour+d":
                    if (
                            title.lower().startswith("cour d'appel")

                    ):
                        find_linklist_in_items(item, motclef, link_list)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            list(tqdm(executor.map(process_page, range(1, page_amount + 1)), total=page_amount, desc="Pages"))

        return link_list

    # ------------------------------------------------------------------------------------------------------------------
    #             FONCTION PRINCIPALE EXTRACTION SCRAPER MONITEUR BELGE (publications tribunaux, listes radiation ...)
    # ------------------------------------------------------------------------------------------------------------------
    def scrap_informations_from_url(url, numac, date_doc, langue, keyword, title, subtitle):
        # va certainement falloir enrichir ici
        with requests.Session() as s:

            response = retry(url, session)
            if not response:
                print(f"[❌ Abandon définitif pour {url}]")
                return None  # ⚠️ important : on sort si la page ne répond jamais
            soup = BeautifulSoup(response.text, 'html.parser')
            extra_keywords = []

            main = soup.find("main", class_="page__inner page__inner--content article-text")
            if not main:
                return (
                    numac, date_doc, langue, "", url, keyword,
                    None, title, subtitle, None, None, None, None,
                    None, None, None, None, None
                )

            texte_brut = extract_clean_text(main, remove_links=False)
            date_jugement = None
            administrateur = None
            tvas = extract_numero_tva(texte_brut)
            tvas_valides = [t for t in tvas if format_bce(t)]
            denoms_by_bce = None
            adresses_by_bce = None
            denoms_by_ejustice = None
            adresses_by_ejustice = None

            doc_id = generate_doc_hash_from_html(texte_brut, date_doc)
            if detect_erratum(texte_brut):
                extra_keywords.append("erratum")

            # Cas normal
            # on va devoir deplacer nom
            if not date_jugement:
                date_jugement = extract_jugement_date(str(texte_brut))

            if re.search(r"tribunal[\s+_]+de[\s+_]+premiere[\s+_]+instance", keyword, flags=re.IGNORECASE | re.DOTALL):
                if not tvas_valides:
                    return None
                # A vérifier avant d'étendre aux autres
                if re.search(
                            r"\bsuccessions?\s*(?:de|vacantes?|en\s+d[ée]sh[ée]rences?)\b",
                            texte_brut,
                            flags=re.IGNORECASE):
                    return None
                # recherche des administrateurs avec les deux fonctions complementaires d'extraction d'administrateurs
                admins_csv = trouver_personne_dans_texte(
                    texte_brut,
                    chemin_csv("curateurs.csv"),
                    ["avocate", "avocat", "Maître", "bureaux", "cabinet", "curateur"]
                )
                admins_rx = extract_administrateur(texte_brut)

                administrateur = dedupe_admins(admins_csv, admins_rx)
                detect_tribunal_premiere_instance_keywords(texte_brut, extra_keywords)
                if all("delai de contact" not in element for element in extra_keywords):
                    detect_tribunal_entreprise_keywords(texte_brut, extra_keywords)

            # -----------------------------
            # TRIB ENTREPRISE
            # -----------------------------
            if re.search(r"tribunal\s+de\s+l", keyword.replace("+", " "), flags=re.IGNORECASE):
                if not tvas_valides:
                    return None
                # recherche des administrateurs avec les deux fonctions complementaires d'extraction d'administrateurs
                admins_csv = trouver_personne_dans_texte(
                    texte_brut,
                    chemin_csv("curateurs.csv"),
                    ["avocate", "avocat", "Maître", "bureaux", "cabinet", "curateur"]
                )
                admins_rx = extract_administrateur(texte_brut)

                administrateur = dedupe_admins(admins_csv, admins_rx)
                detect_tribunal_entreprise_keywords(texte_brut, extra_keywords)

            # ----------------------------------------------------------------
            # ENTREPRISES RADIEES
            #     > Les entreprises radiees ne sont que des Personnes Morales
            # ----------------------------------------------------------------
            if re.search(r"Liste\s+des\s+entites\s+enregistrees", keyword.replace("+", " "), flags=re.IGNORECASE):
                if not tvas_valides:
                    return None
                detect_radiations_keywords(texte_brut, extra_keywords)

            # ------------ -----------------
            # COUR D'APPEL
            # -----------------------------
            # probleme? exemple 730689335c260eba1ea29679ae3c3277759008a345f24b544393667a7e7a8aba
            # pas vraiment je pense en fait (nom et nom trib sont avec du bruit et pas grave
            if re.search(r"cour\s+d", keyword.replace("+", " "), flags=re.IGNORECASE):
                if not tvas_valides:
                    return None
                # recherche des administrateurs avec les deux fonctions complementaires d'extraction d'administrateurs
                admins_csv = trouver_personne_dans_texte(
                    texte_brut,
                    chemin_csv("curateurs.csv"),
                    ["avocate", "avocat", "Maître", "bureaux", "cabinet", "curateur"]
                )
                admins_rx = extract_administrateur(texte_brut)

                administrateur = dedupe_admins(admins_csv, admins_rx)
                detect_tribunal_entreprise_keywords(texte_brut, extra_keywords)
                detect_courappel_keywords(texte_brut, extra_keywords)
                detect_tribunal_premiere_instance_keywords(texte_brut, extra_keywords)

                # 🧼 Nettoyage spécifique Cour d'appel :
                # Dans les arrêts de cour d'appel, les noms de personnes physiques et les noms de sociétés
                # sont souvent extraits ensemble dans le champ `nom`.
                # Or, les sociétés sont déjà présentes dans `nom_trib_entreprise` (extrait via extract_noms_entreprises)
                # Ce bloc sert à nettoyer `nom` pour ne garder QUE les personnes physiques :
                # on supprime des sous-champs (`records`, `canonicals`, `aliases_flat`)
                # tous les noms qui correspondent à des entreprises déjà détectées.
                # ➤ Objectif : éviter les doublons et le bruit dans Meilisearch ou PostgreSQL.

            return (
                numac, date_doc, langue, texte_brut, url, keyword,
                tvas, title, subtitle, extra_keywords, date_jugement,
                administrateur, doc_id, denoms_by_bce,
                adresses_by_bce, adresses_by_ejustice, denoms_by_ejustice
            )

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
    index.update_filterable_attributes(["keyword", "denom_fallback_bce"])

    index.update_searchable_attributes([
        "id", "date_doc", "title", "keyword", "date_jugement", "TVA",
        "extra_keyword",
        "administrateur", "text",
        "denoms_by_bce", "adresses_by_bce",
        "adresses_by_ejustice", "denoms_by_ejustice",
        "denom_fallback_bce"  # 🆕 ajouté ici
    ])

    index.update_displayed_attributes([
        "id", "date_doc", "title", "keyword", "extra_keyword",
        "date_jugement", "TVA",
        "administrateur", "text", "url",
        "denoms_by_bce", "adresses_by_bce",
        "adresses_by_ejustice", "denoms_by_ejustice",
        "denom_fallback_bce"  # 🆕 ajouté ici aussi
    ])

    print(f"[⚙️] Index '{index_name}' prêt en {time.perf_counter() - start_time:.2f}s.")
    documents = []
    with requests.Session() as session:
        for record in tqdm(final, desc="Préparation Meilisearch"):
            cleaned_url = clean_url(record[4])
            date_jugement = None  # Valeur par défaut si record[14] est None
            if record[10] is not None:
                brut = clean_date_jugement(record[10])
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
                "extra_keyword": record[9],  # mots-clés supplémentaires
                "date_jugement": record[10],
                "administrateur": record[11],
                "denoms_by_bce": record[13],
                "adresses_by_bce": record[14],
                "adresses_by_ejustice": record[15],
                "denoms_by_ejustice": record[16],
                "denom_fallback_bce": None  # 🆕 ajouté ici
            }

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
            logger_champs_manquants_obligatoires.warning(f"[❌ Champs manquants] DOC={doc.get('id')} | Manquants: {missing}")

    # --------------------------------------------------------------------------------------------------------------
    # 🧩 Enrichissement BCE (uniquement depuis le fichier CSV local, sans fetch ni fallback)
    # --------------------------------------------------------------------------------------------------------------

    for doc in documents:
        # Initialisation systématique
        doc["denoms_by_bce"] = None
        doc["adresses_by_bce"] = None
        doc["denom_fallback_bce"] = None  # restera toujours None ici

        if "annulation_doublon" in (doc.get("extra_keyword") or []):
            continue

        tvas = doc.get("TVA") or []
        denoms_map = {}
        adresses_map = {}

        for tva in tvas:
            if not verifier_tva_belge(tva):
                logger_tva_invalide.warning(
                    f"[❌ TVA invalide] {tva} | DOC={doc.get('id')} | URL={doc.get('url')}"
                )
                continue

            bce = format_bce(tva)
            if not bce:
                continue

            # 🔹 Lecture depuis les index locaux uniquement
            noms = sorted(denom_index.get(bce, []))
            type_ent = personnes_physiques.get(bce, "inconnu")

            if noms:
                denoms_map[bce] = {"type": type_ent, "noms": noms}

            adresses = []
            if bce in address_index:
                adresses.extend({"adresse": addr, "source": "siege"} for addr in address_index[bce])

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

            # ❌ Aucun fallback ici : il sera géré dans enrichissement_ejustice_bce.py

        # ✅ Affectations finales
        doc["denoms_by_bce"] = (
            [{"bce": bce, "type": data["type"], "noms": data["noms"]}
             for bce, data in denoms_map.items()]
            if denoms_map else None
        )

        doc["adresses_by_bce"] = (
            [{"bce": bce, "adresses": adresses}
             for bce, adresses in adresses_map.items()]
            if adresses_map else None
        )

        # ⚠️ On garde ce champ vide ici pour le prochain script
        doc["denom_fallback_bce"] = None

    # 🧼 Nettoyage des champs adresse : suppression des doublons dans la liste
    # ================================================================
    # ✅ Vérification générique : cohérence nom/adresse pour chaque BCE
    # ================================================================
    for doc in documents:
        keyword = (doc.get("keyword") or "").lower()
        tvas = doc.get("TVA") or []
        denoms_by_bce = doc.get("denoms_by_bce") or []
        adresses_by_bce = doc.get("adresses_by_bce") or []

        # Indexer les noms et adresses par BCE au format "xxxx.xxx.xxx"
        denom_map = {
            format_bce(entry.get("bce")): entry.get("noms", [])
            for entry in denoms_by_bce if entry.get("bce")
        }
        addr_map = {
            format_bce(entry.get("bce")): entry.get("adresses", [])
            for entry in adresses_by_bce if entry.get("bce")
        }

        for tva in tvas:
            bce = format_bce(tva)
            if not bce:
                logger_tva_invalide.warning(
                    f"[❌ TVA invalide] {tva} | DOC={doc.get('id')} | URL={doc.get('url')}"
                )
                continue

            noms = denom_map.get(bce, [])
            adrs = addr_map.get(bce, [])

            has_nom = bool(noms and any(isinstance(n, str) and n.strip() for n in noms))
            has_adresse = bool(
                adrs and any(
                    isinstance(addr, dict) and any(str(v).strip() for v in addr.values())
                    for addr in adrs
                )
            )

            if not has_nom and not has_adresse:
                logger_champs_manquants_obligatoires.warning(
                    f"[⚠️ BCE sans dénomination ni adresse] "
                    f"DOC={doc.get('id')} | BCE={bce} | keyword={keyword} | URL={doc.get('url')}"
                )

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
    print(f"[📊] Documents réellement indexés dans Meili: {stats.number_of_documents}")
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
        writer.writerow(["tva", "id", "url", "keyword", "denoms_by_bce", "adresses_by_bce", "denom_fallback_bce"])
        for doc in documents:
            for tva in doc.get("TVA", []):
                writer.writerow([tva, doc["id"], doc["url"], doc["keyword"], doc["denoms_by_bce"],
                                 doc["adresses_by_bce"], doc["denom_fallback_bce"]])
    # --------------------------------------------------------------------------------------------------------------
    #                                                    BASE DE DONNEE : POSTGRE
    #
    # --------------------------------------------------------------------------------------------------------------
    print("[📥] Connexion à PostgreSQL…")
    create_table_moniteur()
    insert_documents_moniteur(documents)

    # --------------------------------------------------------------------------------------------------------------
    #                                 FICHIERS CSV CONTENANT LES DONNES INSEREES DANS MEILI
    # --------------------------------------------------------------------------------------------------------------
    # 📝 Sauvegarde finale en JSON local (version enrichie)
    os.makedirs("exports", exist_ok=True)
    json_path = os.path.join("exports", f"documents_enrichis_{keyword}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)

    print(f"[💾] Fichier JSON enrichi sauvegardé: {json_path}")


if __name__ == "__main__":
    main()
