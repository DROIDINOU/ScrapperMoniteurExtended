import re
import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from playwright.sync_api import sync_playwright


RUBRIQUE_KEYWORDS = {
    "CONSTITUTION": ["constitution", "nouvelle personne morale", "ouverture succursale"],
    "FIN": ["cessation", "annulation", "dissolution", "reorganisation", "réorganisation", "clôture"],
    "RADIATION": ["radiation"],
    "SIEGE": ["siège social", "siege social", "transfert siège"],
    "DEMISSION-NOMINATION": ["demission", "nomination"],
}


def detect_rubrique(text: str) -> str:
    txt = text.lower()
    for rubrique, mots in RUBRIQUE_KEYWORDS.items():
        if any(m in txt for m in mots):
            return rubrique
    return "INCONNUE"


# ------------------------------------------------------------------------
# ✅ METHOD 1 : PLAYWRIGHT (nouvelle UI du site Moniteur)
# ------------------------------------------------------------------------
def scrape_with_playwright(bce_number: str):
    print("🟦 [PLAYWRIGHT] Dynamic scraping starting...")

    url = f"https://www.ejustice.just.fgov.be/cgi_tsv/article.pl?language=fr&btw_search={bce_number}&caller=list&page=1"
    print(f"🌐 Opening list page: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded")

        raw_links = page.locator("a[href*='view_numac']").all()
        print(f"🔗 Found NUMAC detail links : {len(raw_links)}")

        events = []

        for link in raw_links:
            href = link.get_attribute("href")
            if not href:
                continue

            # ✅ ignorer tous les liens non pertinents
            if any(x in href for x in ["welcome.pl", "summary.pl", "rech.pl"]):
                print(f"⛔ Ignored (garbage): {href}")
                continue

            if "article.pl" not in href:
                print(f"⛔ Ignored (not article.pl): {href}")
                continue

            # correction du format
            if not href.startswith("/"):
                href = "/" + href

            detail_url = "https://www.ejustice.just.fgov.be" + href
            print(f"➡️ Visiting ANNEXE : {detail_url}")

            page.goto(detail_url, wait_until="domcontentloaded")

            try:
                page.wait_for_selector("article", timeout=4000)
            except:
                print("⚠️ Aucun <article> trouvé sur cette page")
                continue

            soup = BeautifulSoup(page.content(), "html.parser")

            for art in soup.select("article"):
                txt = art.get_text(" ", strip=True)

                pdf_tag = art.find("a", href=True)
                pdf = f"https://www.ejustice.just.fgov.be{pdf_tag['href']}" if pdf_tag else None

                title_tag = art.find("font")
                titre = title_tag.get_text(strip=True) if title_tag else "INCONNU"

                m = re.search(r"(\d{4}-\d{2}-\d{2})", txt)
                date_pub = m.group(1) if m else timezone.now().date()

                events.append({
                    "societe": titre,
                    "rubrique": detect_rubrique(txt),
                    "date_publication": date_pub,
                    "url": pdf,
                })

        browser.close()

    print(f"✅ [PLAYWRIGHT] {len(events)} annexe(s) trouvée(s)")
    return events


# ------------------------------------------------------------------------
# ✅ METHOD 2 : REQUESTS (ancienne UI sans JS)
# ------------------------------------------------------------------------
def scrape_with_requests(bce_number: str):
    print("🟦 [REQUESTS] Fallback legacy scraping...")

    url = f"https://www.ejustice.just.fgov.be/cgi_tsv/article.pl?language=fr&btw_search={bce_number}&caller=list&page=1"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    r.encoding = "iso-8859-1"

    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.find("main")

    if not main:
        print("⚠️ [REQUESTS] No <main> → nothing to parse")
        return []

    events = []

    for block_html in main.decode_contents().split("<hr"):
        block = BeautifulSoup(block_html, "html.parser")
        txt = block.get_text("\n", strip=True)
        if not txt:
            continue

        title_tag = block.find("font")
        titre = title_tag.get_text(strip=True) if title_tag else "INCONNU"

        m = re.search(r"(\d{4}-\d{2}-\d{2})", txt)
        date_pub = m.group(1) if m else timezone.now().date()

        link = block.find("a")
        pdf = f"https://www.ejustice.just.fgov.be{link['href']}" if link else None

        events.append({
            "societe": titre,
            "rubrique": detect_rubrique(txt),
            "date_publication": date_pub,
            "url": pdf,
        })

    print(f"✅ [REQUESTS] {len(events)} event(s) legacy found")
    return events


# ------------------------------------------------------------------------
# ✅ PUBLIC CALL
# ------------------------------------------------------------------------
def scrap_annexes(bce_number: str):
    print(f"\n🚀 SCRAP TVA = {bce_number}")

    digits = re.sub(r"\D", "", bce_number)
    if digits.startswith("0"):
        digits = digits[1:]

    events = scrape_with_playwright(digits)
    if events:
        return events

    return scrape_with_requests(digits)
