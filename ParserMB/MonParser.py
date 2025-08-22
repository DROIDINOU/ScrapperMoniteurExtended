# --- Imports standards ---
import re
import os
import requests
import time

# --- Bibliothèques tierces ---
from bs4 import BeautifulSoup, NavigableString, Tag
from PIL import Image
import fitz  # PyMuPDF
import tempfile
import pytesseract

# --- Modules internes au projet ---
from Constante.mesconstantes import BASE_URL


def retry(url, session, params=None):
    try:
        response = session.get(url, params=params)
        response.encoding = "Windows-1252"
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException:
        print(f"[!] Retry needed for {url}")
        time.sleep(10)
        return retry(url, session, params)


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


def convert_pdf_pages_to_text_range(pdf_url, start_page_index, page_count=6):
    """
    Télécharge un PDF depuis une URL, applique l’OCR sur plusieurs pages à partir de start_page_index.
    Corrige les problèmes de permission, fichiers verrouillés, noms en conflit et profils ICC.
    """
    try:
        response = requests.get(pdf_url)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement du PDF: {e}")
        return ""

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(response.content)
        tmp_path = tmp_file.name
        print(f"[📄] PDF temporaire sauvegardé: {tmp_path}")

    full_text = ""
    pdf = None

    try:
        pdf = fitz.open(tmp_path)
        total_pages = len(pdf)

        # 🔒 start_page_index par défaut
        if start_page_index is None:
            print(f"[⚠️] start_page_index est None — on démarre à la page 0")
            start_page_index = 0

        end_page_index = min(start_page_index + page_count, total_pages)

        for i in range(start_page_index, end_page_index):
            try:
                page = pdf.load_page(i)
                # ✅ Matrice haute résolution + couleurs RGB pour éviter les erreurs ICC
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csRGB)

                # ✅ Nom de fichier unique
                timestamp = int(time.time() * 1000)
                img_path = f"ocr_page_{i + 1}_{os.getpid()}_{timestamp}.png"
                pix.save(img_path)

                if not os.path.exists(img_path):
                    print(f"[❌] Image non créée pour la page {i + 1}: {img_path}")
                    continue

                try:
                    img = Image.open(img_path)
                    text = pytesseract.image_to_string(img)
                    img.close()
                except Exception as e_ocr:
                    print(f"[⚠️] Erreur OCR sur la page {i + 1}: {e_ocr}")
                    text = ""

                full_text += f"\n--- Page {i + 1} ---\n{text}"

                try:
                    os.remove(img_path)
                except Exception as e_rm:
                    print(f"[⚠️] Impossible de supprimer '{img_path}': {e_rm}")

            except Exception as e_page:
                print(f"⚠️ Erreur OCR sur la page {i + 1}: {e_page}")
                continue

    except Exception as e_open:
        print(f"❌ Erreur d’ouverture ou d’OCR: {e_open}")
        return ""

    finally:
        if pdf:
            pdf.close()
        try:
            os.remove(tmp_path)
        except Exception as e_rm:
            print(f"[⚠️] Erreur suppression fichier temporaire: {e_rm}")

    return full_text.strip()
