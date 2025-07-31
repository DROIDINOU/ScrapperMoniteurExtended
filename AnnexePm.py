import asyncio
import aiohttp
from bs4 import BeautifulSoup
import csv
from itertools import islice
from meilisearch import Client
import re
from datetime import datetime
from sentence_transformers import SentenceTransformer  # ➕ Pour embeddings

# Connexion Meilisearch
MEILI_URL = "http://127.0.0.1:7700"
INDEX_NAME = "annexes_juridique_2025_07_14"
client = Client(MEILI_URL)
index = client.index(INDEX_NAME)
base_site = "https://www.ejustice.just.fgov.be"

semaphore = asyncio.Semaphore(3)
model = SentenceTransformer("distiluse-base-multilingual-cased-v1")  # ➕ Chargement du modèle

async def fetch_with_retry(session, url, params, retries=3):
    for attempt in range(retries):
        try:
            async with semaphore:
                async with session.get(url, params=params, timeout=20) as response:
                    return await response.text(encoding="latin1")
        except Exception as e:
            print(f"   ⚠️ Tentative {attempt + 1} échouée : {e}")
            await asyncio.sleep(2 * (attempt + 1))
    raise Exception(f"❌ Échec après {retries} tentatives.")

societes_list = []
with open("typesocietes.csv", newline="", encoding="utf-8") as csvfile:
    reader = csv.reader(csvfile)
    next(reader)
    for row in reader:
        value = row[0].strip()
        text = row[1].strip()
        textespace = text + " "
        if value:
            societes_list.append((value, textespace))

rubriques_list = []
with open("typerubrique.csv", newline="", encoding="utf-8") as csvfile:
    reader = csv.reader(csvfile)
    next(reader)
    for row in reader:
        value = row[0].strip()
        text = row[1].strip()
        textespace = text + " "

        if value:
            rubriques_list.append((value, textespace))

base_url = "https://www.ejustice.just.fgov.be/cgi_tsv/list.pl"

async def traiter_combinaison(session, societe, rubrique):
    jvorm_code, jvorm_label = societe
    akte_code, akte_label = rubrique

    print(f"\n🔍 Recherche pour '{jvorm_label}' ({jvorm_code}) et '{akte_label}' ({akte_code})")

    params = {
        "language": "fr",
        "jvorm": jvorm_code,
        "akte": akte_code,
        "pdd": "2024-01-01",
        "pdf": "2025-07-14",
        "page": "1"
    }

    try:
        text = await fetch_with_retry(session, base_url, params)
        soup = BeautifulSoup(text, "html.parser")

        pagination = soup.select("a.pagination-button")
        pages = [a.text.strip() for a in pagination if a.text.strip().isdigit()]
        last_page = max([int(p) for p in pages]) if pages else 1

        print(f"   ➜ {last_page} page(s).")

        for page_num in range(1, last_page + 1):
            params["page"] = str(page_num)
            page_text = await fetch_with_retry(session, base_url, params)
            s = BeautifulSoup(page_text, "html.parser")

            items = s.select("div.list-content div.list")
            print(f"\n   --- Page {page_num}: {len(items)} éléments ---")

            for i, item in enumerate(items, start=1):
                subtitle_tag = item.select_one("p.list-item--subtitle")
                subtitle = subtitle_tag.get_text(strip=True) if subtitle_tag else "(Pas de sous-titre)"

                links = [a for a in item.find_all("a") if a.has_attr("href")]
                url_html = links[0]["href"].strip() if len(links) >= 1 else None
                url = links[1]["href"].strip() if len(links) >= 2 else "(Pas de lien PDF)"

                lignes = []
                a_tag = item.select_one("a.list-item--title")
                if a_tag:
                    lignes = list(a_tag.stripped_strings)

                texte_full = "\n".join(lignes)

                # ➕ Regex TVA
                match_tva = re.search(r'(0\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{3})', texte_full)
                tva = '.'.join(match_tva.groups()) if match_tva else None

                # ➕ Regex registre national
                match_rn = re.search(r'(\d{2})[\.\-\s]*(\d{2})[\.\-\s]*(\d{2})[\.\-\s]*(\d{3})[\.\-\s]*(\d{2})', texte_full)
                registre_national = '.'.join(match_rn.groups()) if match_rn else None

                # ➕ Embedding IA
                embedding = model.encode(texte_full).tolist()

                date_document = None
                if url and isinstance(url, str):
                    match = re.search(r"pdf/(\d{4})/(\d{2})/(\d{2})/", url)
                    if match:
                        try:
                            date_obj = datetime.strptime("-".join(match.groups()), "%Y-%m-%d")
                            date_document = date_obj.date().isoformat()
                        except Exception:
                            pass

                doc = {
                    "id": f"{jvorm_code}-{akte_code}-{page_num}-{i}",
                    "societe_code": jvorm_code,
                    "societe_label": jvorm_label,
                    "rubrique_code": akte_code,
                    "rubrique_label": akte_label,
                    "subtitle": subtitle,
                    "url_html": f"{base_site}{url_html}" if url_html and url_html.startswith("/") else url_html,
                    "url": f"{base_site}{url}" if url and url.startswith("/") else url,
                    "titre_lignes": lignes,
                    "date_document": date_document,
                    "TVA": tva,
                    "registre_national": registre_national,
                    "embedding": embedding
                }

                index.add_documents([doc])

            await asyncio.sleep(1.1)

    except Exception as e:
        print(f"   ⚠️ Erreur : {e}")

def chunks(data, size):
    it = iter(data)
    return iter(lambda: list(islice(it, size)), [])

async def main():
    async with aiohttp.ClientSession() as session:
        societe_batches = list(chunks(societes_list, 3))
        rubrique_batches = list(chunks(rubriques_list, 4))

        for s_batch in societe_batches:
            for r_batch in rubrique_batches:
                tasks = []
                for societe in s_batch:
                    for rubrique in r_batch:
                        tasks.append(traiter_combinaison(session, societe, rubrique))
                await asyncio.gather(*tasks)
                print("\n⏳ Petite pause entre blocs...\n")
                await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
