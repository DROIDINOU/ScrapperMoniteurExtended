#!/usr/bin/env python3
# coding: utf-8
# python C:\Users\32471\ScrapperMoniteurAnnexes\ python scrappeAnnexes.py --source tribunal

# changement production : virer le try except pour meili
#

# -----------------------------------------------------------------------------------------
# - Scrape Annexes pour des numéros BCE/TVA trouvés dans log champs manquants obligatoires
# - Si Annexes ne renvoient rien : fallback sur la BCE
# - Cache local sur disque pour eviter requetes http sur meme numero de tva (cache_ejustice_bce.json)
# - Export JSON des documents enrichis
# - Mise à jour (merge) sécurisée vers MeiliSearch par batch
# -----------------------------------------------------------------------------------------


import os
import re
import json
import time
import random
import requests
import argparse
import glob
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pathlib import Path
import sys

try:
    import meilisearch
except Exception as e:
    raise ImportError("⚠️ Installe le client Meilisearch : pip install meilisearch") from e



# Chemin absolu vers ScrapperCJCE
BASE_PATH = Path(__file__).resolve().parents[1] / "ScrapperCJCE"
sys.path.append(str(BASE_PATH))
from BaseDeDonnees.insertion_moniteur import insert_documents_moniteur

# ============================================================== #
# ⚙️ ARGUMENTS CLI
# Cette section permet de passer des options au script
# directement depuis le terminal, par exemple :
#     python scrappeAnnexes.py --source cour --limit 10 --no-sleep
#     python scrappeAnnexes.py --help
# ============================================================== #
parser = argparse.ArgumentParser(description="Enrichissement eJustice + fallback BCE")
parser.add_argument("--source", choices=["liste", "tribunal", "instance", "cour"], default="liste")
parser.add_argument("--limit", type=int, default=None)
parser.add_argument("--no-sleep", action="store_true")
args = parser.parse_args()
SOURCE_TYPE = args.source
LIMIT = args.limit
NO_SLEEP = args.no_sleep
# ============================================================== #
# 🔧 CONFIGURATION
# ============================================================== #

# ============================================================== #
# 🔧 CONFIGURATION (corrigée pour dossier racine)
# ============================================================== #

# Dossier où se trouve ce script
SCRIPT_DIR = Path(__file__).resolve().parent

# Dossier racine du projet (1 niveau au-dessus de ScrapperMoniteurAnnexes)
PROJECT_ROOT = SCRIPT_DIR.parent

# Fichier .env est à la racine
ENV_PATH = PROJECT_ROOT / ".env"

# Dossier ScrapperCJCE (logs, cache, etc.)
CJCE_PATH = PROJECT_ROOT / "ScrapperCJCE"

LOGS_DIR = CJCE_PATH / "logs"

# Dossier export pour ce script uniquement
EXPORTS_DIR = SCRIPT_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

print("[DEBUG] SCRIPT_DIR:", SCRIPT_DIR)
print("[DEBUG] PROJECT_ROOT:", PROJECT_ROOT)
print("[DEBUG] ENV_PATH:", ENV_PATH)
print("[DEBUG] CJCE_PATH:", CJCE_PATH)

if not ENV_PATH.exists():
    raise FileNotFoundError(f"❌ Fichier .env introuvable : {ENV_PATH}")

load_dotenv(ENV_PATH)
MEILI_URL = os.getenv("MEILI_URL")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")

if not all([MEILI_URL, MEILI_KEY, INDEX_NAME]):
    raise RuntimeError("❌ Variables MEILI_URL / MEILI_MASTER_KEY / INDEX_NAME manquantes dans le .env")

client = meilisearch.Client(MEILI_URL, MEILI_KEY)
index = client.index(INDEX_NAME)
print(f"[🗂️] MeiliSearch connecté → {INDEX_NAME}")

# ============================================================== #
# 🔍 CHARGEMENT DU LOG
# ============================================================== #
if SOURCE_TYPE == "liste":
    pattern = "champs_manquants_obligatoires_csv_bce_Liste*entites*enregistrees*.log"
elif SOURCE_TYPE == "instance":
    pattern = "champs_manquants_obligatoires_csv_bce_tribunal*premiere*instance*.log"
elif SOURCE_TYPE == "tribunal":
    pattern = "champs_manquants_obligatoires_csv_bce_tribunal*de*l*.log"
elif SOURCE_TYPE == "cour":
    pattern = "champs_manquants_obligatoires_csv_bce_cour*d.log"

matches = glob.glob(str(LOGS_DIR / pattern))
if not matches:
    raise FileNotFoundError(f"❌ Aucun fichier log correspondant au pattern : {pattern}")
LOG_PATH = max(matches, key=os.path.getmtime)
print(f"[📖] Log détecté automatiquement : {LOG_PATH}")

doc_to_bces = {}
with open(LOG_PATH, "r", encoding="utf-8") as f:
    for line in f:
        m = re.search(r"DOC=([a-f0-9]{64}).*?(?:BCE|TVA)[^\d]*([\d\.]{9,})", line)
        if m:
            doc_id, bce = m.groups()
            digits = re.sub(r"\D", "", bce)
            doc_to_bces.setdefault(doc_id, []).append(digits)

if LIMIT:
    doc_to_bces = dict(list(doc_to_bces.items())[:LIMIT])

print(f"[🎯] {len(doc_to_bces)} documents à enrichir.")


# ============================================================== #
# 💾 CACHE LOCAL
# ============================================================== #
CACHE_PATH = CJCE_PATH / "cache_ejustice_bce.json"
cache = {}
if CACHE_PATH.exists():
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except:
        cache = {}


def save_cache():
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


# ============================================================== #
# ⚙️ OUTILS DE BASE
# format_bce : tva -> 0542.715.196
# maybe_sleep : si l'argument no sleep est pas active
# impose une pause aleatoire entre deux requetes http
# ============================================================== #
def format_bce(value: str) -> str | None:
    if not value:
        return None
    nombre = re.sub(r"\D", "", value)
    return f"{nombre[:4]}.{nombre[4:7]}.{nombre[7:]}" if len(nombre) == 10 else None


def maybe_sleep(min_s=0.6, max_s=1.4):
    if not NO_SLEEP:
        time.sleep(random.uniform(min_s, max_s))


# ============================================================== #
# 🌐 FONCTIONS FETCH
# ============================================================== #
def fetch_ejustice(num_bce, debug=False):
    digits = re.sub(r"\D", "", num_bce)
    cache_key = f"ejustice_{digits}"
    if cache_key in cache:
        return cache[cache_key]

    url = f"https://www.ejustice.just.fgov.be/cgi_tsv/list.pl?language=fr&btw={digits}"
    headers = {"User-Agent": "Mozilla/5.0 Chrome/128 Safari/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=(5, 15))
        if r.status_code == 429:
            time.sleep(2)
            r = requests.get(url, headers=headers, timeout=(5, 15))
        r.raise_for_status()
    except Exception as e:
        if debug:
            print(f"[⚠️] Erreur eJustice: {e}")
        cache[cache_key] = []
        save_cache()
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div.list-item--content")
    results = []
    for it in items:
        name = addr = None
        subtitle = it.find("p", class_="list-item--subtitle")
        if subtitle:
            name = subtitle.get_text(" ", strip=True)
        a_tag = it.find("a", class_="list-item--title")
        if a_tag:
            addr = a_tag.get_text(" ", strip=True)
        if name or addr:
            results.append({"bce": digits, "nom": name, "adresse": addr, "source": "ejustice"})

    cache[cache_key] = results
    save_cache()
    maybe_sleep()
    return results


def fetch_bce(num_bce, debug=False):
    digits = re.sub(r"\D", "", num_bce)
    cache_key = f"bce_{digits}"
    if cache_key in cache:
        return cache[cache_key]

    url = f"https://kbopub.economie.fgov.be/kbopub/zoeknummerform.html?lang=fr&nummer={digits}&actionLu=Zoek"
    headers = {"User-Agent": "Mozilla/5.0 Chrome/128 Safari/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=(5, 15))
        r.raise_for_status()
    except Exception as e:
        if debug:
            print(f"[⚠️] Erreur BCE: {e}")
        cache[cache_key] = []
        save_cache()
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # ✅ On cherche toutes les lignes du tableau
    table = soup.find("table")
    denomination = adresse = None
    if table:
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue

            label = tds[0].get_text(" ", strip=True).lower()

            # --- Helper: nettoyer une cellule avant d’en extraire le texte ---
            def clean_cell(td):
                # supprime la balise mais garde le texte qu'elle contient
                for tag in td.find_all(["span", "small", "font", "i", "b"]):
                    tag.unwrap()

                text = td.get_text(" ", strip=True)
                return text

            # --- Dénomination ---
            if "dénomination" in label or "denomination" in label:
                denomination = clean_cell(tds[1])

            # --- Adresse ---
            elif any(x in label for x in ["adresse", "siège", "siege"]):
                adresse = clean_cell(tds[1])

    # ✅ N’enregistre QUE si au moins une donnée non vide
    results = []
    if any([denomination, adresse]):
        results.append({
            "bce": format_bce(digits),
            "nom": denomination or "",
            "adresse": adresse or "",
            "source": "bce_fallback"
        })

    if debug:
        print(f"[DEBUG BCE PARSE] {results}")

    cache[cache_key] = results
    save_cache()
    maybe_sleep()
    return results


# ============================================================== #
# 🚀 TRAITEMENT PRINCIPAL
# ============================================================== #
enriched_docs = []
LOG_MISSING_PATH = CJCE_PATH / f"logs/champs_non_trouves_ejustice_{SOURCE_TYPE}.log"
log_missing = open(LOG_MISSING_PATH, "w", encoding="utf-8")

for idx, (doc_id, bces) in enumerate(doc_to_bces.items(), 1):
    print("\n" + "=" * 90)
    print(f"[{idx}/{len(doc_to_bces)}] DOC={doc_id}")

    try:
        doc = dict(index.get_document(doc_id))
    except Exception as e:
        print(f"[❌] Erreur doc {doc_id}: {e}")
        continue

    # ✅ Ne JAMAIS toucher aux valeurs déjà présentes dans Meili
    if "adresses_by_ejustice" not in doc or doc["adresses_by_ejustice"] is None:
        doc["adresses_by_ejustice"] = []

    if "denom_fallback_bce" not in doc or doc["denom_fallback_bce"] is None:
        doc["denom_fallback_bce"] = []

    # ------------------------------------------------------------------ #
    # Boucle sur tous les BCE trouvés dans le log pour ce document
    # ------------------------------------------------------------------ #
    for bce in bces:
        bce_fmt = format_bce(bce)
        if not bce_fmt:
            continue

        print(f"[🔍] Traitement BCE {bce_fmt}")

        res_ejustice = fetch_ejustice(bce_fmt)
        res_bce = []

        if res_ejustice:
            print(f"   [EJUSTICE OK] {len(res_ejustice)} résultat(s)")
            doc["adresses_by_ejustice"].extend(res_ejustice)

        else:
            print(f"   [EJUSTICE VIDE] → fallback BCE")
            res_bce = fetch_bce(bce_fmt)

            if res_bce:
                print("   [BCE Fallback OK]")
                doc["denom_fallback_bce"].extend(res_bce)
            else:
                print("   [FAILED] Aucun résultat trouvé")
                log_missing.write(f"{doc_id} | {bce_fmt}\n")
                log_missing.flush()

    # ------------------------------------------------------------------ #
    # ✅ FLATTEN NOM / ADRESSES en séparant eJustice et BCE
    # ------------------------------------------------------------------ #

    doc["denoms_by_ejustice_flat"] = [
        x.get("nom").strip()
        for x in doc["adresses_by_ejustice"]
        if x.get("source") == "ejustice" and x.get("nom")
    ]



    doc["adresses_ejustice_flat"] = [
        x.get("adresse").strip()
        for x in doc["adresses_by_ejustice"]
        if x.get("source") == "ejustice" and x.get("adresse")
    ]
    # ✅ FLAT spécifiques AU FALLBACK BCE (NE PAS toucher à denoms_by_bce_flat !!)
    if isinstance(doc.get("denom_fallback_bce"), list):
        doc["denoms_fallback_bce_flat"] = [
            x.get("nom").strip()
            for x in doc["denom_fallback_bce"]
            if x.get("nom")
        ]

        doc["adresses_fallback_bce_flat"] = [
            x.get("adresse").strip()
            for x in doc["denom_fallback_bce"]
            if x.get("adresse")
        ]
    else:
        doc["denoms_fallback_bce_flat"] = []
        doc["adresses_fallback_bce_flat"] = []

    # ✅ Ajouter le document dans enriched_docs uniquement si AU MOINS UNE info trouvée
    if doc["denoms_by_ejustice_flat"] \
            or doc["adresses_ejustice_flat"] \
            or doc["denoms_fallback_bce_flat"] \
            or doc["adresses_fallback_bce_flat"]:
        enriched_docs.append(doc)

log_missing.close()
# ✅ Remplace le log initial par le log filtré (seuls les NON ENRICHIS restent)
if os.path.getsize(LOG_MISSING_PATH) > 0:
    print("⚠️ Tous les enrichissements n'ont pas réussi → mise à jour du log avec les lignes restantes.")
    os.replace(LOG_MISSING_PATH, LOG_PATH)  # ÉCRASE l'ancien fichier log par le nouveau
else:
    print("✅ Tous les BCE ont été enrichis → suppression du log d'origine.")
    os.remove(LOG_PATH)  # Plus rien à traiter → suppression

# ============================================================== #
# 💾 EXPORT + MISE À JOUR MEILI
# ============================================================== #
EXPORT_PATH = EXPORTS_DIR / f"documents_enrichis_ejustice_bce_{SOURCE_TYPE}.json"
with open(EXPORT_PATH, "w", encoding="utf-8") as f:
    json.dump(enriched_docs, f, indent=2, ensure_ascii=False)
print(f"[💾] Export terminé → {EXPORT_PATH}")

if enriched_docs:

    print(f"[⬆️] Mise à jour de {len(enriched_docs)} documents dans MeiliSearch...")
    try:
        primary_key = index.get_primary_key() or "id"
    except:
        primary_key = "id"

    to_update = []
    for d in enriched_docs:
        if d.get(primary_key):
            update_doc = {
                primary_key: d[primary_key],
            }

            if "adresses_by_ejustice" in d and d["adresses_by_ejustice"]:
                update_doc["adresses_by_ejustice"] = d["adresses_by_ejustice"]

            if "adresses_ejustice_flat" in d and d["adresses_ejustice_flat"]:
                update_doc["adresses_ejustice_flat"] = d["adresses_ejustice_flat"]

            if "denom_fallback_bce" in d and d["denom_fallback_bce"]:
                update_doc["denom_fallback_bce"] = d["denom_fallback_bce"]

            if "denoms_by_ejustice_flat" in d and d["denoms_by_ejustice_flat"]:
                update_doc["denoms_by_ejustice_flat"] = d["denoms_by_ejustice_flat"]

            # ✅ Ajouter denoms_by_bce_flat dans MeiliSearch
            if "denoms_by_bce_flat" in d and d["denoms_by_bce_flat"]:
                update_doc["denoms_by_bce_flat"] = d["denoms_by_bce_flat"]
            # ✅ Envoyer aussi les FALLBACK vers MeiliSearch
            if "denoms_fallback_bce_flat" in d and d["denoms_fallback_bce_flat"]:
                update_doc["denoms_fallback_bce_flat"] = d["denoms_fallback_bce_flat"]

            if "adresses_fallback_bce_flat" in d and d["adresses_fallback_bce_flat"]:
                update_doc["adresses_fallback_bce_flat"] = d["adresses_fallback_bce_flat"]

            to_update.append(update_doc)

    BATCH_SIZE = 300
    for i in range(0, len(to_update), BATCH_SIZE):
        batch = to_update[i:i+BATCH_SIZE]
        try:
            task = index.update_documents(batch)
            print(f"[📤] Batch {i//BATCH_SIZE + 1} envoyé ({len(batch)} docs)")
        except Exception as e:
            print(f"[⚠️] Erreur batch {i//BATCH_SIZE + 1}: {e}")
    print("[✅] Tous les documents ont été envoyés à MeiliSearch.")
    # print("[📥] Mise à jour PostgreSQL…")
    #insert_documents_moniteur(enriched_docs, update_only=True)
    # print("[✅] PostgreSQL mis à jour avec les adresses eJustice")
else:
    print("[ℹ️] Aucun document enrichi à envoyer.")
