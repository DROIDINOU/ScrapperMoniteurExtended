from playwright.sync_api import sync_playwright
import json
import os


def fetch_fsma_playwright(tva):
    tva_clean = tva.replace(".", "")
    search_url = f"https://www.fsma.be/fr/data-portal?search_api_fulltext={tva_clean}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Étape 1 : Recherche
        page.goto(search_url, timeout=60000)

        # Trouver le lien
        link = page.locator("a.search-result-teaser__link").first
        if not link:
            print("Pas de profil trouvé")
            return None

        href = link.get_attribute("href")
        profile_url = "https://www.fsma.be" + href

        # Étape 2 : Charger la fiche
        page.goto(profile_url, timeout=60000)

        # Étape 3 : Export JSON EN TÉLÉCHARGEMENT
        with page.expect_download() as download_info:
            page.click("text=Export JSON")  # clique sur le bouton export

        download = download_info.value
        file_path = download.path()

        # Lire contenu JSON téléchargé
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        browser.close()
        return data


data = fetch_fsma_playwright("0872.695.538")
print("\n### Résultat JSON ###")
print(data)
