import concurrent.futures
import re
import sqlite3
import time
from datetime import date, datetime
from bs4 import BeautifulSoup
import requests
import locale
from tqdm import tqdm
import meilisearch

DB = 'C:\\Users\\m.losson\\DjangoApi\\FinalDjango\\hopes.db'
FIRST_DATE = "2025-06-28"
second_date = str(date.today())
from_date = date.fromisoformat(FIRST_DATE)
to_date = date.fromisoformat(second_date)

SEARCHES = (
    "Liste+des+entites+enregistrees",
    "tribunal+de+l",
    "justice+de+paix",
    "tribunal+de+premiere+instance",
    "cour+d",
    "terrorisme",
    "succession",
    "successions",
)

BASE_URL = "https://www.ejustice.just.fgov.be/cgi/"
locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")

def retry(url, session):
    try:
        response = session.get(url)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"[!] Connection to {BASE_URL} failed. Trying again...")
        print(f"URL => {url}")
        time.sleep(10)
        return retry(url, session)

def find_linklist_in_items(item, keyword, link_list):
    divListItemButton = item.find("div", class_="list-item--button").find("a")
    numac_search = re.search(r'numac_search=\s*(\d+)', divListItemButton["href"])
    datepub_search = re.search(r'pd_search=\s*(\d{4}-\d{2}-\d{2})', divListItemButton["href"])
    numac = numac_search.group(1)
    datepub = datepub_search.group(1)
    lang_search = "FR"
    link_list.append((BASE_URL + divListItemButton["href"], numac, datepub, lang_search, keyword))

def last_date_database(keyword):
    con = None
    try:
        con = sqlite3.connect(DB)
        cur = con.cursor()
        cur.execute(f'SELECT MAX(date) FROM "{keyword}"')
        latest_date = cur.fetchone()[0]
        if latest_date:
            latest_date_obj = datetime.strptime(latest_date, '%Y-%m-%d')
            latest_date_obj_formatted = latest_date_obj.strftime('%d %B %Y')
            return latest_date_obj_formatted
        else:
            return None
    except Exception as e:
        print(f"[!] Erreur dans last_date_database pour '{keyword}': {e}")
        return None
    finally:
        if con:
            con.close()


def get_page_amount(session, start_date, end_date, keyword):
    encoded = keyword.replace(" ", "+")
    today = date.today()
    url = f'{BASE_URL}list.pl?language=fr&sum_date={today}&page=&pdd={start_date}&pdf={end_date}&choix1=et&choix2=et&exp={encoded}&fr=f&trier=promulgation'
    response = retry(url, session)
    soup = BeautifulSoup(response.text, 'html.parser')
    divPagination = soup.find("div", class_="pagination-container")
    allA = divPagination.find_all("a")
    lastA = allA[-1]
    lastAHref = lastA["href"]
    parsed = lastAHref.split("&")
    for item in parsed:
        if "page=" in item:
            page_amount = item.split("=")[1]
            return int(page_amount)
    return 0

def ask_belgian_monitor(session, start_date, end_date, keyword):
    page_amount = get_page_amount(session, start_date, end_date, keyword)
    print(f"Nombre de pages trouvées pour {keyword}: {page_amount}")
    link_list = []

    def process_page(page):
        encoded = keyword.replace(" ", "+")
        today = date.today()
        url = f'{BASE_URL}list.pl?language=fr&sum_date={today}&page={page}&pdd={start_date}&pdf={end_date}&choix1=et&choix2=et&exp={encoded}&fr=f&trier=promulgation'
        response = retry(url, session)
        soup = BeautifulSoup(response.text, 'html.parser')
        classList = soup.find("div", class_="list")
        listItems = classList.find_all(class_="list-item")

        for item in listItems:
            parSubtitle = item.find("p", class_="list-item--subtitle").get_text(strip=True)
            date_article = item.find("p", class_="list-item--date").get_text(strip=True)
            if date_article and last_date_insertion and datetime.strptime(date_article, '%d %B %Y') <= datetime.strptime(last_date_insertion, '%d %B %Y'):
                print(f"Already processed up to date {last_date_insertion} for keyword {keyword}")
                return
            elif keyword in SEARCHES[0] and parSubtitle == "Service public fédéral Economie, P.M.E., Classes moyennes et Énergie":
                find_linklist_in_items(item, keyword, link_list)
            elif keyword in SEARCHES[1:5] and not parSubtitle:
                find_linklist_in_items(item, keyword, link_list)
            elif             keyword in SEARCHES[5:] and parSubtitle == "Service public fédéral Finances":
                find_linklist_in_items(item, keyword, link_list)

    with concurrent.futures.ThreadPoolExecutor(max_workers=80) as executor:
        futures = [executor.submit(process_page, page) for page in range(1, page_amount + 1)]
        for future in concurrent.futures.as_completed(futures):
            future.result()

    return link_list

def strip_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def scrap_informations_from_url(session, url, numac, date, langue, keyword):
    response = retry(url, session)
    soup = BeautifulSoup(response.text, 'html.parser')
    mainWithClass = soup.find("main", class_="page__inner page__inner--content article-text")
    text = strip_html_tags(str(mainWithClass.find("p").get_text())).strip()
    return (numac, date, langue, text, url, keyword)

final = []

with requests.Session() as session:
    for keyword in SEARCHES:
        last_date_insertion = last_date_database(keyword)
        print(f"Last date of insertion for {keyword}: {last_date_insertion}")

        link_list = ask_belgian_monitor(session, from_date, to_date, keyword)
        print(f"Nombre de liens trouvés pour {keyword}: {len(link_list)}")

        scrapped_data = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=80) as executor:
            for item in tqdm(link_list, desc=f'Scraping data for {keyword}'):
                future = executor.submit(scrap_informations_from_url, session, item[0], item[1], item[2], item[3], item[4])
                scrapped_data.append(future.result())

        final.extend(scrapped_data)

# Connexion à Meilisearch
client = meilisearch.Client("http://127.0.0.1:7700")

index_name = "moniteur_docs"

try:
    index = client.get_index(index_name)
except meilisearch.errors.MeilisearchApiError:
    client.create_index(index_name, {"primaryKey": "id"})
    index = client.get_index(index_name)

# Préparer les documents
documents = []
for record in tqdm(final, desc="Préparation des documents Meilisearch"):
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", record[0])
    doc = {
        "id": safe_id,
        "numac": record[0],
        "date": record[1],
        "lang": record[2],
        "text": record[3],
        "url": record[4],
        "keyword": record[5]
    }
    documents.append(doc)

print(f"\nNombre de documents à indexer dans Meilisearch : {len(documents)}")

# Indexation
response = index.add_documents(documents)

print("Indexation lancée.")
print("Task UID:", response.task_uid)

# Attendre la fin
index.wait_for_task(response.task_uid, timeout_in_ms=60000)
print("Indexation terminée avec succès.")
