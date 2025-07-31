import requests
from bs4 import BeautifulSoup
import re
import os
import fitz  # PyMuPDF
import meilisearch
from urllib.parse import unquote
from datetime import datetime, timedelta
import argparse

BASE_URL = "https://www.raadvst-consetat.be"
index_name = "conseil_etat_arrets100"

# Connexion Meilisearch
client = meilisearch.Client(os.getenv("MEILI_URL"))
try:
    index = client.get_index(index_name)
except meilisearch.errors.MeilisearchApiError:
    task = client.create_index(index_name, {"primaryKey": "id"})
    client.wait_for_task(task.task_uid)
    index = client.get_index(index_name)

def try_fix_encoding(text):
    try:
        return text.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
    except Exception:
        return text

def get_date_ranges(start_year=2020):
    ranges = []
    today = datetime.today()
    current = datetime(start_year, 1, 1)
    while current < today:
        end = current + timedelta(days=60)
        ranges.append((current.strftime("%Y%m%d"), end.strftime("%Y%m%d")))
        current = end
    return ranges

def scrap_interval(start_date, end_date):
    SEARCH_URL = (
        f"https://www.raadvst-consetat.be/index.asp?"
        f"page=caselaw_adv&lang=fr&index=arr&s_lang=fr&"
        f"booleanConditions=%28dat_arr+contains+%28{start_date}~~{end_date}%29%29"
    )

    response = requests.get(SEARCH_URL)
    response.encoding = "cp1252"
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    pagination_div = soup.find("div", class_="searchresults_pages")
    if not pagination_div:
        page_urls = [SEARCH_URL]
    else:
        links = pagination_div.find_all("a", href=True)
        page_urls = [BASE_URL + "/" + a["href"].lstrip("./") for a in links]

    arret_infos = []
    for page_url in page_urls:
        resp = requests.get(page_url)
        resp.encoding = "cp1252"
        resp.raise_for_status()
        page_soup = BeautifulSoup(resp.text, "html.parser")
        item_divs = page_soup.find_all("div", class_="item")

        for div in item_divs:
            a_tag = div.find("a", href=True)
            if a_tag:
                href = a_tag["href"]
                full_link = BASE_URL + "/" + href.lstrip("./")
                text = a_tag.get_text(" ", strip=True)
                description_fixed = try_fix_encoding(text)
                arret_infos.append({
                    "url": full_link,
                    "description": description_fixed
                })

    print(f"[{start_date} → {end_date}] Arrêts collectés : {len(arret_infos)}")
    return arret_infos

def process_and_index(arret_infos, offset):
    documents = []

    for i, arret in enumerate(arret_infos, offset):
        print(f"Téléchargement PDF ({i}): {arret['url']}")
        try:
            pdf_resp = requests.get(arret["url"])
            pdf_resp.raise_for_status()
        except Exception as e:
            print(f"[!] Erreur téléchargement PDF: {e}")
            continue

        with open("temp.pdf", "wb") as f:
            f.write(pdf_resp.content)

        try:
            with fitz.open("temp.pdf") as pdf:
                text_content = "".join(page.get_text() for page in pdf)
        except Exception as e:
            print(f"[!] Erreur extraction texte: {e}")
            continue

        text_content = text_content.strip()
        print(f"[DEBUG] DESCRIPTION : {arret['description']}")

        num_arret = re.search(r"Arrêt\.?\s*<b>(\d+)</b>", arret["description"])
        date_document = re.search(r"du\s+(\d{2}/\d{2}/\d{4})", arret["description"])
        num_role = re.search(r"Numéro de Rôle\s*([^<]+)</a>", arret["description"])

        doc = {
            "id": f"arret_{i}",
            "num_arret": num_arret.group(1) if num_arret else None,
            "date_document": date_document.group(1) if date_document else None,
            "num_role": num_role.group(1).strip() if num_role else None,
            "text": text_content,
            "url": arret["url"],
            "description": arret["description"]
        }

        documents.append(doc)

    if documents:
        print(f"\nEnvoi vers Meilisearch ({len(documents)} documents)...")
        response = index.add_documents(documents)
        print(f"Task UID: {response.task_uid}")
        index.wait_for_task(response.task_uid, timeout_in_ms=60000)
        print("Indexation terminée.")
    else:
        print("Aucun document à indexer.")

def get_yesterday():
    yesterday = datetime.today() - timedelta(days=1)
    return yesterday.strftime("%Y%m%d")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="start", type=str, default=get_yesterday(),
                        help="Date de début (format: YYYYMMDD). Par défaut: hier.")
    parser.add_argument("--to", dest="end", type=str, default=get_yesterday(),
                        help="Date de fin (format: YYYYMMDD). Par défaut: hier.")
    args = parser.parse_args()

    offset = 1
    arrets = scrap_interval(args.start, args.end)
    process_and_index(arrets, offset)