#!/usr/bin/env python3
# coding: utf-8

# -----------------------------------------------------------------------------------------
# Scrape Annexes pour numéros BCE/TVA trouvés dans les logs ScrapperCJCE
# Enrichissement eJustice + fallback BCE
# Mise à jour batch dans MeiliSearch
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
    raise ImportError("⚠ Installe Meilisearch : pip install meilisearch") from e

# -------------------------------------------------------------
# 📁 Structure des dossiers
# -------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent             # Racine du projet
ENV_PATH = PROJECT_ROOT / ".env"             # .env à la racine
CJCE_PATH = PROJECT_ROOT / "ScrapperCJCE"    # ScrapperCJCE
LOGS_DIR = CJCE_PATH / "logs"                # Logs utilisés
EXPORTS_DIR = SCRIPT_DIR / "exports"         # Export JSON final
EXPORTS_DIR.mkdir(exist_ok=True)

# Pour importer les outils CJCE :
sys.path.append(str(CJCE_PATH))

print("[DEBUG] SCRIPT_DIR :", SCRIPT_DIR)
print("[DEBUG] PROJECT_ROOT :", PROJECT_ROOT)
print("[DEBUG] ENV_PATH :", ENV_PATH)
print("[DEBUG] CJCE_PATH :", CJCE_PATH)

if not ENV_PATH.exists():
    raise FileNotFoundError(f".env introuvable : {ENV_PATH}")

# -------------------------------------------------------------
# 🔧 Chargement configuration MeiliSearch
# -------------------------------------------------------------

load_dotenv(ENV_PATH)

MEILI_URL = os.getenv("MEILI_URL")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")

if not all([MEILI_URL, MEILI_KEY, INDEX_NAME]):
    raise RuntimeError("⚠ Variables MEILI_URL / MEILI_MASTER_KEY / INDEX_NAME manquantes dans .env")

client = meilisearch.Client(MEILI_URL, MEILI_KEY)
index = client.index(INDEX_NAME)

print(f"🔗 MeiliSearch connecté → {INDEX_NAME}")

# -------------------------------------------------------------
# 🧭 Parsing arguments CLI
# -------------------------------------------------------------

parser = argparse.ArgumentParser(description="Enrichissement eJustice + fallback BCE")
parser.add_argument("--source", choices=["liste", "tribunal", "instance", "cour"], default="liste")
parser.add_argument("--limit", type=int, default=None)
parser.add_argument("--no-sleep", action="store_true")

args = parser.parse_args()

SOURCE_TYPE = args.source
LIMIT = args.limit
NO_SLEEP = args.no_sleep


# -------------------------------------------------------------
# 🔍 Détection automatique du log source
# -------------------------------------------------------------

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
    raise FileNotFoundError(f"Aucun log correspondant : {pattern}")

LOG_PATH = max(matches, key=os.path.getmtime)
print(f"📄 Log détecté : {LOG_PATH}")

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

print(f"🔍 {len(doc_to_bces)} documents à enrichir")


# -------------------------------------------------------------
# 💾 CACHE LOCAL
# -------------------------------------------------------------
CACHE_PATH = CJCE_PATH / "cache_ejustice_bce.json"

cache = {}
if CACHE_PATH.exists():
    try:
        cache = json.load(open(CACHE_PATH, "r", encoding="utf-8"))
    except:
        cache = {}


def save_cache():
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


# -------------------------------------------------------------
# 🧰 OUTILS
# -------------------------------------------------------------

def format_bce(value: str) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return f"{digits[:4]}.{digits[4:7]}.{digits[7:]}" if len(digits) == 10 else None


def maybe_sleep(a=0.6, b=1.4):
    if not NO_SLEEP:
        time.sleep(random.uniform(a, b))


# -------------------------------------------------------------
# 🌐 FETCH eJustice
# -------------------------------------------------------------
def fetch_ejustice(num_bce, debug=False):
    digits = re.sub(r"\D", "", num_bce)
    key = f"ejustice_{digits}"

    if key in cache:
        return cache[key]

    url = f"https://www.ejustice.just.fgov.be/cgi_tsv/list.pl?language=fr&btw={digits}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, timeout=(5, 15))
        r.raise_for_status()
    except:
        cache[key] = []
        save_cache()
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div.list-item--content")

    results = []
    for it in items:
        name, addr = None, None
        sub = it.find("p", class_="list-item--subtitle")
        if sub:
            name = sub.get_text(" ", strip=True)
        a = it.find("a", class_="list-item--title")
        if a:
            addr = a.get_text(" ", strip=True)

        if name or addr:
            results.append({
                "bce": digits,
                "nom": name,
                "adresse": addr,
                "source": "ejustice",
            })

    cache[key] = results
    save_cache()
    maybe_sleep()

    return results


# -------------------------------------------------------------
# 🌐 FETCH BCE (fallback)
# -------------------------------------------------------------
def fetch_bce(num_bce, debug=False):
    digits = re.sub(r"\D", "", num_bce)
    key = f"bce_{digits}"

    if key in cache:
        return cache[key]

    url = f"https://kbopub.economie.fgov.be/kbopub/zoeknummerform.html?lang=fr&nummer={digits}&actionLu=Zoek"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, timeout=(5, 15))
        r.raise_for_status()
    except:
        cache[key] = []
        save_cache()
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")

    denomination = adresse = None

    if table:
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue

            label = tds[0].get_text(" ", strip=True).lower()

            # Nettoyage HTML de la valeur
            for tag in tds[1].find_all(["span", "small", "font", "i", "b"]):
                tag.unwrap()

            val = tds[1].get_text(" ", strip=True)

            if "dénomination" in label or "denomination" in label:
                denomination = val
            elif any(x in label for x in ["adresse", "siège", "siege"]):
                adresse = val

    results = []
    if denomination or adresse:
        results.append({
            "bce": format_bce(digits),
            "nom": denomination or "",
            "adresse": adresse or "",
            "source": "bce_fallback",
        })

    cache[key] = results
    save_cache()
    maybe_sleep()

    return results


# -------------------------------------------------------------
# 🚀 TRAITEMENT PRINCIPAL
# -------------------------------------------------------------

enriched_docs = []

LOG_MISSING_PATH = CJCE_PATH / f"logs/champs_non_trouves_ejustice_{SOURCE_TYPE}.log"
log_missing = open(LOG_MISSING_PATH, "w", encoding="utf-8")

for idx, (doc_id, bces) in enumerate(doc_to_bces.items(), 1):
    print(f"[{idx}/{len(doc_to_bces)}] DOC={doc_id}")

    try:
        doc = dict(index.get_document(doc_id))
    except Exception as e:
        print(f"❌ Erreur document {doc_id} : {e}")
        continue

    # Champs à préparer
    doc.setdefault("adresses_by_ejustice", [])
    doc.setdefault("denom_fallback_bce", [])

    for bce in bces:
        bce_fmt = format_bce(bce)
        if not bce_fmt:
            continue

        print(f" → BCE {bce_fmt}")

        res_ej = fetch_ejustice(bce_fmt)

        if res_ej:
            print("   ✓ eJustice OK")
            doc["adresses_by_ejustice"].extend(res_ej)
        else:
            print("   ✗ eJustice vide → fallback BCE")
            res_bce = fetch_bce(bce_fmt)
            if res_bce:
                print("   ✓ BCE OK")
                doc["denom_fallback_bce"].extend(res_bce)
            else:
                print("   ✗ Aucun résultat")
                log_missing.write(f"{doc_id} | {bce_fmt}\n")

    # Flatten
    doc["denoms_by_ejustice_flat"] = [
        x["nom"].strip()
        for x in doc["adresses_by_ejustice"]
        if x.get("nom")
    ]

    doc["adresses_ejustice_flat"] = [
        x["adresse"].strip()
        for x in doc["adresses_by_ejustice"]
        if x.get("adresse")
    ]

    doc["denoms_fallback_bce_flat"] = [
        x["nom"].strip()
        for x in doc["denom_fallback_bce"]
        if x.get("nom")
    ]

    doc["adresses_fallback_bce_flat"] = [
        x["adresse"].strip()
        for x in doc["denom_fallback_bce"]
        if x.get("adresse")
    ]

    # Ajouter si enrichi
    if any([doc["denoms_by_ejustice_flat"],
            doc["adresses_ejustice_flat"],
            doc["denoms_fallback_bce_flat"],
            doc["adresses_fallback_bce_flat"]]):

        enriched_docs.append(doc)

log_missing.close()

# Mise à jour du log initial
if os.path.getsize(LOG_MISSING_PATH) > 0:
    os.replace(LOG_MISSING_PATH, LOG_PATH)
else:
    os.remove(LOG_PATH)

# -------------------------------------------------------------
# 💾 EXPORT JSON
# -------------------------------------------------------------

EXPORT_PATH = EXPORTS_DIR / f"documents_enrichis_ejustice_bce_{SOURCE_TYPE}.json"

with open(EXPORT_PATH, "w", encoding="utf-8") as f:
    json.dump(enriched_docs, f, indent=2, ensure_ascii=False)

print(f"📦 Export → {EXPORT_PATH}")


# -------------------------------------------------------------
# 📤 ENVOI VERS MEILISEARCH
# -------------------------------------------------------------
if enriched_docs:
    print(f"🚀 Mise à jour MeiliSearch ({len(enriched_docs)} docs)…")

    try:
        primary_key = index.get_primary_key() or "id"
    except:
        primary_key = "id"

    to_update = []

    for d in enriched_docs:
        if primary_key not in d:
            continue

        update_doc = {primary_key: d[primary_key]}

        for key in [
            "adresses_by_ejustice",
            "adresses_ejustice_flat",
            "denom_fallback_bce",
            "denoms_by_ejustice_flat",
            "denoms_fallback_bce_flat",
            "adresses_fallback_bce_flat",
        ]:
            if key in d and d[key]:
                update_doc[key] = d[key]

        to_update.append(update_doc)

    # Batch
    BATCH_SIZE = 300
    for i in range(0, len(to_update), BATCH_SIZE):
        batch = to_update[i:i + BATCH_SIZE]
        try:
            index.update_documents(batch)
            print(f" ✓ Batch {i//BATCH_SIZE + 1} envoyé")
        except Exception as e:
            print(f" ❌ Erreur batch : {e}")

    print("✔ Tous les documents envoyés à MeiliSearch.")

else:
    print("Aucun document enrichi.")

