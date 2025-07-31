import requests
from PyPDF2 import PdfReader
from io import BytesIO
from meilisearch import Client
from datetime import datetime
import re

def extract_date_from_text(text):
    match = re.search(r"du\s+(1er|\d{1,2})\s+([a-zéû]+)\s+(\d{4})", text, re.IGNORECASE)
    if match:
        day_str = match.group(1)
        day = 1 if day_str.lower() == "1er" else int(day_str)
        month_str = match.group(2).lower()
        year = int(match.group(3))

        mois = {
            "janvier": 1,
            "février": 2,
            "mars": 3,
            "avril": 4,
            "mai": 5,
            "juin": 6,
            "juillet": 7,
            "août": 8,
            "septembre": 9,
            "octobre": 10,
            "novembre": 11,
            "décembre": 12
        }

        month = mois.get(month_str)
        if month:
            return datetime(year, month, day).strftime("%Y-%m-%d")
    return None

def scrape_const_court_all_years(meili_url, index_name_prefix, start_year=2020, max_num=800):
    today = datetime.today()
    end_year = today.year

    client = Client(meili_url)

    for year in range(start_year, end_year + 1):
        print(f"\n📘 Traitement de l'année {year}...")
        index_name = f"{index_name_prefix}{year}"
        index = client.index(index_name)

        base_url = f"https://const-court.be/public/f/{year}/{year}-{{num:03d}}f.pdf"
        documents = []

        for num in range(1, max_num + 1):
            url = base_url.format(num=num)
            print(f"🔍 Test URL: {url}")

            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 404:
                    print("   ❌ Pas trouvé (404).")
                    continue

                r.raise_for_status()

                reader = PdfReader(BytesIO(r.content))
                text = "\n\n".join(page.extract_text() or "" for page in reader.pages)

                print(f"   ✅ PDF trouvé et texte extrait ({len(text)} caractères).")

                date_document = extract_date_from_text(text)
                if date_document:
                    print(f"   📅 Date trouvée: {date_document}")
                else:
                    print("   ⚠️ Date non trouvée dans le texte.")

                doc = {
                    "id": f"{year}-{num:03d}",
                    "year": str(year),
                    "number": num,
                    "url": url,
                    "scrape_date": datetime.now().strftime("%Y-%m-%d"),
                    "date_document": date_document,
                    "pdf_text": text
                }

                documents.append(doc)

            except Exception as e:
                print(f"   ⚠️ Erreur: {e}")
                continue

        print(f"\n✅ {len(documents)} jugements trouvés pour {year}.\n")

        if documents:
            print("🚀 Envoi vers Meilisearch...")
            res = index.add_documents(documents)
            print(f"✅ Import terminé pour {year} : taskUid={res.task_uid}")
        else:
            print(f"⚠️ Aucun document pour {year}.")

if __name__ == "__main__":
    scrape_const_court_all_years(
        meili_url="http://127.0.0.1:7700",
        index_name_prefix="constcourtjudgments_2025_07_08",
        start_year=2020,
        max_num=500
    )
