# --- Imports standards ---
import re
import requests
import time

# --- Bibliothèques tierces ---
from bs4 import BeautifulSoup


# --- Modules internes au projet ---
from Constante.mesconstantes import BASE_URL


def retry(url, session, params=None, retries=3, delay=10):
    """
    Fait jusqu'à 'retries' tentatives avec un timeout.
    Empêche les blocages indéfinis.
    """
    print("[DEBUG] retry() called with", url, flush=True)

    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, params=params, timeout=(5, 30))  # ⏱️ 5s connect / 30s lecture
            response.encoding = "Windows-1252"
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            print(f"[⏰ Timeout] ({attempt}/{retries}) pour {url}")
        except requests.exceptions.RequestException as e:
            print(f"[⚠️ Requête échouée] ({attempt}/{retries}) {url} → {e}")

        if attempt < retries:
            time.sleep(delay)
            print(f"[🔁 Nouvelle tentative dans {delay}s] {url}")

    print(f"[❌ Abandon après {retries} tentatives] {url}")
    return None


def find_linklist_in_items(item, keyword, link_list):
    link_tag = item.find("div", class_="list-item--button").find("a")
    numac = re.search(r'numac_search=(\d+)', link_tag["href"]).group(1)
    datepub = re.search(r'pd_search=(\d{4}-\d{2}-\d{2})', link_tag["href"]).group(1)
    lang = "FR"
    full_url = BASE_URL + link_tag["href"]

    title_element = item.find("a", class_="list-item--title")
    title = title_element.get_text(strip=True) if title_element else ""

    subtitle_element = item.find("p", class_="list-item--subtitle")
    subtitle = subtitle_element.get_text(strip=True) if subtitle_element else ""

    link_list.append((full_url, numac, datepub, lang, keyword, title, subtitle))


# va certainement falloir mettre aileurs
def get_publication_pdfs_for_tva(session, tva, max_pages=7):
    base_url = "https://www.ejustice.just.fgov.be/cgi_tsv/article.pl"
    tva_clean = tva.lstrip("0")
    publications = []
    for page in range(1, max_pages + 1):
        url = f"{base_url}?language=fr&btw_search={tva_clean}&page={page}&la_search=f"
        response = retry(url, session)
        soup = BeautifulSoup(response.text, "html.parser")
        pdf_links = soup.find_all("a", href=re.compile(r"/tsv_pdf/"))
        if not pdf_links:
            break
        for link in pdf_links:
            publications.append("https://www.ejustice.just.fgov.be" + link["href"])
    return publications
