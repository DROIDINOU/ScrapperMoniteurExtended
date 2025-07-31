import re
from datetime import datetime
from bs4 import BeautifulSoup
import requests
import meilisearch

def extraire_texte_nettoye(soup_element, separator="\n"):
    if isinstance(soup_element, str):
        soup_element = BeautifulSoup(soup_element, "html.parser")
    texte = soup_element.get_text(separator=separator).strip()
    texte = re.sub(r"[ \t]+", " ", texte)
    texte = re.sub(r"\n+", "\n", texte)
    return texte.strip()

CURRENT_YEAR = "2023"
print(f"[INFO] Scraping uniquement l'année {CURRENT_YEAR}")

celex_set = set()
results = {}
page = 1
while True:
    url = f"https://eur-lex.europa.eu/collection/eu-law/eu-case-law/reports-search-result.html?collection=GRCJ&year={CURRENT_YEAR}&page={page}"
    print(f"[INFO] Fetching page {page}: {url}")
    response = requests.get(url)
    if response.status_code != 200:
        print(f"[ERROR] Statut HTTP {response.status_code}")
        break

    soup = BeautifulSoup(response.text, "html.parser")
    links = soup.find_all("a")
    new_celex = 0

    for link in links:
        href = link.get("href")
        if href and "?uri=CELEX:" in href:
            m = re.search(r"\?uri=CELEX:([^&]+)", href)
            if m:
                celex = m.group(1)
                tr = link.find_parent("tr")
                date_str = None
                if tr:
                    td_list = tr.find_all("td")
                    for i, td in enumerate(td_list):
                        if td.find("a") == link and i > 0:
                            raw_date = td_list[i - 1].get_text(strip=True)
                            print(f"[DEBUG] CELEX {celex} → Date brute extraite : '{raw_date}'")
                            try:
                                date_str = datetime.strptime(raw_date, "%d/%m/%Y").date().isoformat()
                            except ValueError:
                                print(f"[WARN] Format date inconnu: {raw_date}")
                            break

                if celex not in celex_set:
                    celex_set.add(celex)
                    results[celex] = {"date_document": date_str}
                    print(f"   ➜ CELEX ajouté: {celex}, date = {date_str}")
                    new_celex += 1

    if new_celex == 0:
        print("[INFO] Fin de pagination : aucune nouvelle entrée trouvée.")
        break

    page += 1

print(f"[INFO] Total CELEX uniques: {len(celex_set)}")
if not celex_set:
    exit()

BASE_URL = "https://eur-lex.europa.eu/legal-content/FR/TXT/HTML/?uri=CELEX:"

with requests.Session() as session:
    for celex in sorted(celex_set):
        full_url_txt = BASE_URL + celex
        print(f"[INFO] Fetching TXT: {full_url_txt}")
        try:
            r_txt = session.get(full_url_txt, timeout=10)
            r_txt.raise_for_status()
        except requests.RequestException as e:
            print(f"[ERROR] {e}")
            continue

        soup_txt = BeautifulSoup(r_txt.text, "html.parser")
        main_txt = soup_txt.find("body")
        titre_txt = main_txt.find("h1").get_text(strip=True) if main_txt and main_txt.find("h1") else "Sans titre"
        contenu_txt = extraire_texte_nettoye(main_txt) if main_txt else None

        results[celex].update({
            "url_txt": full_url_txt,
            "titre_txt": titre_txt,
            "contenu_txt": contenu_txt
        })

documents = []
for celex, v in results.items():
    if not v.get("contenu_txt"):
        continue
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", celex)
    doc = {
        "id": safe_id,
        "titre": v.get("titre_txt"),
        "contenu": v.get("contenu_txt"),
        "url": v.get("url_txt"),
        "date_document": v.get("date_document")
    }
    print(f"[DOC] {safe_id} - {doc['date_document']}")
    documents.append(doc)

print(f"[INFO] Nombre de documents à indexer : {len(documents)}")
if not documents:
    print("[INFO] Aucun document valide.")
    exit()

# === Fonction propre pour gérer Meilisearch ===
def index_documents_meilisearch(documents, index_name):
    print("[INFO] Connexion à Meilisearch…")
    client = meilisearch.Client("http://127.0.0.1:7700")

    try:
        index = client.get_index(index_name)
    except meilisearch.errors.MeilisearchApiError:
        print("[INFO] Index introuvable, création…")
        task = client.create_index(index_name, {"primaryKey": "id"})
        client.wait_for_task(task.task_uid)
        index = client.get_index(index_name)

    print(f"[DEBUG] Type de 'index' avant add_documents: {type(index)}")
    task_info = index.add_documents(documents)
    print(f"[INFO] Task UID : {task_info.task_uid}")
    index.wait_for_task(task_info.task_uid, timeout_in_ms=300000)
    print("[INFO] Indexation terminée.")

# === Appel de la fonction ===
index_name = f"eurlex_daily_{CURRENT_YEAR}_extract07_08"
index_documents_meilisearch(documents, index_name)
