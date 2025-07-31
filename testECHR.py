from playwright.sync_api import sync_playwright
import time
from meilisearch import Client
from urllib.parse import unquote
import json
import requests
from io import BytesIO
from PyPDF2 import PdfReader
from datetime import datetime
import re
import dateparser
import csv

def scrape_and_index_with_dateparser(meili_url, index_name):
    # Connexion Meilisearch
    client = Client(meili_url)
    index = client.index(index_name)

    documents = []

    # ---------------------------------
    # ÉTAPE 1 - SCROLL + collecte URLs
    # EXACTEMENT comme ton exemple
    # ---------------------------------
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print("[DEBUG] Ouverture HUDOC (jugements toutes dates)...")
        page.goto("https://hudoc.echr.coe.int/eng#%7B%22documentcollectionid2%22%3A%5B%22JUDGMENTS%22%5D%7D")
        page.wait_for_selector("#results-list")

        previous_count = 0
        scroll = 0
        while True:
            items = page.query_selector_all("#results-list a.document-link.headline")
            current_count = len(items)
            print(f"[DEBUG] Scroll #{scroll}: {current_count} résultats détectés.")
            if current_count == previous_count:
                break
            previous_count = current_count
            scroll += 1
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            time.sleep(1)

        print(f"\n✅ {current_count} résultats chargés. Enregistrement des URLs...\n")

        # Collecte des URLs
        for a in items:
            title = a.inner_text().strip()
            href = a.get_attribute("href")

            if href and "#" in href:
                parts = href.split("#", 1)
                json_str = unquote(parts[1])
                obj = json.loads(json_str)
                itemid = obj.get("itemid", [""])[0]
                doc_url = f"https://hudoc.echr.coe.int/eng?i={itemid}"
            else:
                itemid = "N/A"
                doc_url = "N/A"

            documents.append({
                "id": itemid,
                "title": title,
                "url": doc_url
            })

        page.close()
        browser.close()

    print(f"\n✅ {len(documents)} documents collectés avant filtrage.\n")

    # Sauvegarde CSV
    csv_filename = "hudoc_documents.csv"
    with open(csv_filename, mode="w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["id", "title", "url"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for doc in documents:
            writer.writerow(doc)

    print(f"\n✅ {len(documents)} documents sauvegardés dans {csv_filename}.\n")

    # ---------------------------------
    # ÉTAPE 2 - Réouverture des pages + filtrage date + PDF
    # Avec URL reconstruite
    # ---------------------------------
    all_docs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        for i, doc in enumerate(documents, start=1):
            print(f"\n[{i}/{len(documents)}] Récupération {doc['id']}...")

            pdf_text_en = ""
            pdf_text_fr = ""
            doc_date = None

            if doc["url"] != "N/A":
                # Reconstruit l'URL finale HUDOC avec #{"itemid":["..."]}
                final_url = f"https://hudoc.echr.coe.int/eng#{{\"itemid\":[\"{doc['id']}\"]}}"
                print(f"   URL reconstruite : {final_url}")

                detail_page = browser.new_page()
                try:
                    detail_page.goto(final_url, timeout=60000)
                    detail_page.wait_for_selector(".details", timeout=20000)

                    # Extraire date texte
                    date_tag = detail_page.query_selector("p")
                    if date_tag:
                        date_text = date_tag.inner_text().strip()
                        print(f"   🟢 Date brute: {date_text}")

                        # Pattern anglais
                        m_en = re.search(r"Published on (.+)", date_text)
                        if m_en:
                            date_parsed = dateparser.parse(m_en.group(1), languages=["en"])
                        else:
                            # Pattern français
                            m_fr = re.search(r"Publié le (.+)", date_text)
                            if m_fr:
                                date_parsed = dateparser.parse(m_fr.group(1), languages=["fr"])
                            else:
                                date_parsed = None

                        if date_parsed:
                            print(f"   ✅ Date reconnue: {date_parsed.strftime('%Y-%m-%d')}")
                        else:
                            print(f"   ❌ Impossible de parser la date: {date_text}")
                            detail_page.close()
                            continue

                        if date_parsed < datetime(2025, 1, 1):
                            print("   ⏭️ Ignoré car date < 2025.")
                            detail_page.close()
                            continue
                        doc_date = date_parsed
                    else:
                        print("   ❌ Aucune date trouvée.")
                        detail_page.close()
                        continue

                    # Récupérer les PDFs
                    pdf_links = detail_page.query_selector_all("a.document-link")
                    for link in pdf_links:
                        lang_label = link.inner_text().strip().upper()
                        href_pdf = link.get_attribute("href")
                        if not href_pdf or not href_pdf.endswith(".pdf"):
                            continue
                        pdf_url = href_pdf if href_pdf.startswith("http") else f"https://hudoc.echr.coe.int{href_pdf}"
                        print(f"   Téléchargement PDF: {pdf_url}")

                        try:
                            r = requests.get(pdf_url, timeout=30)
                            r.raise_for_status()
                            reader = PdfReader(BytesIO(r.content))
                            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)

                            if "EN" in lang_label:
                                pdf_text_en = text
                                print("   ✅ PDF EN extrait.")
                            elif "FR" in lang_label:
                                pdf_text_fr = text
                                print("   ✅ PDF FR extrait.")

                        except Exception as e:
                            print(f"   ❌ Erreur PDF : {e}")

                except Exception as e:
                    print(f"   ❌ Erreur page de détail : {e}")

                detail_page.close()
                time.sleep(0.5)

            all_docs.append({
                "id": doc["id"],
                "title": doc["title"],
                "url": final_url,
                "date": doc_date.strftime("%Y-%m-%d") if doc_date else "N/A",
                "pdf_text_en": pdf_text_en,
                "pdf_text_fr": pdf_text_fr
            })

            time.sleep(0.1)

        browser.close()

    print(f"\n✅ {len(all_docs)} documents filtrés avec date >= 2025.\n")

    if all_docs:
        print("\n🚀 Envoi vers Meilisearch...")
        res = index.add_documents(all_docs)
        print(f"✅ Import terminé : taskUid={res.task_uid}")
    else:
        print("\n⚠️ Aucun document à indexer.")

if __name__ == "__main__":
    scrape_and_index_with_dateparser(
        meili_url="http://127.0.0.1:7700",
        index_name="echr_documents"
    )
