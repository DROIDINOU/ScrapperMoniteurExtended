import re
import sqlite3
import time
from datetime import date, datetime
from bs4 import BeautifulSoup
import requests
import locale
from tqdm import tqdm
import meilisearch

def extraire_texte_nettoye(soup_element, separator="\n"):
    """
    Extrait et nettoie le texte d'un élément BeautifulSoup ou d'une chaîne HTML.
    - Supprime les balises HTML
    - Remplace les multiples espaces par un seul
    - Nettoie les sauts de ligne consécutifs
    - Supprime les espaces début/fin
    """

    # Si c'est une chaîne HTML brute, la parser
    if isinstance(soup_element, str):
        soup_element = BeautifulSoup(soup_element, "html.parser")

    # Extraire le texte
    texte = soup_element.get_text(separator=separator).strip()

    # Nettoyer les espaces
    texte = re.sub(r"[ \t]+", " ", texte)
    texte = re.sub(r"\n+", "\n", texte)
    texte = texte.strip()

    return texte

# Liste des années souhaitées
YEARS = [str(y) for y in range(2020, 2026)]

# Ensemble pour éviter les doublons
celex_set = set()

# Boucle sur chaque année
for year in YEARS:
    url = f"https://eur-lex.europa.eu/collection/eu-law/eu-case-law/reports-search-result.html?collection=GRCJ&year={year}"
    




print(f"Fetching search page: {url}")
response = requests.get(url)

if response.status_code != 200:
    print(f"Erreur: {response.status_code}")
    exit()

soup = BeautifulSoup(response.text, "html.parser")
links = soup.find_all("a")

# Ensemble pour éviter les doublons
celex_set = set()

# Boucle sur chaque année
for year in YEARS:
    url = f"https://eur-lex.europa.eu/collection/eu-law/eu-case-law/reports-search-result.html?collection=GRCJ&year={year}"
    print(f"Fetching search page: {url}")

    response = requests.get(url)
    if response.status_code != 200:
        print(f"Erreur {response.status_code} pour l'année {year}")
        continue

    soup = BeautifulSoup(response.text, "html.parser")
    links = soup.find_all("a")

    for link in links:
        href = link.get("href")
        if href and "?uri=CELEX:" in href:
            m = re.search(r"\?uri=CELEX:([^&]+)", href)
            if m:
                celex = m.group(1)
                celex_set.add(celex)

# Après la boucle tu peux afficher:
print(f"\nNombre de CELEX trouvés : {len(celex_set)}")
for c in sorted(celex_set):
    print("-", c)


# URL simple + url SUM + URL res
BASE_URL = "https://eur-lex.europa.eu/legal-content/FR/TXT/HTML/?uri=CELEX:"
BASE_URL_SUM = "https://eur-lex.europa.eu/legal-content/FR/SUM/?uri=CELEX:"

results = {}

with requests.Session() as session:
    for celex in sorted(celex_set):

        # Toujours récupérer la version TXT
        full_url_txt = BASE_URL + celex
        print(f"\nFetching (TXT): {full_url_txt}")

        try:
            r_txt = session.get(full_url_txt, timeout=10)
            r_txt.raise_for_status()
        except requests.RequestException as e:
            print(f"[!] Error fetching TXT for {celex}: {e}")
            r_txt = None

        # Préparer stockage
        results[celex] = {
            "url_txt": full_url_txt,
            "titre_txt": None,
            "contenu_txt": None,
            "url_sum": None,
            "titre_sum": None,
            "contenu_sum": None
        }

        if r_txt:
            soup_txt = BeautifulSoup(r_txt.text, "html.parser")
            main_txt = soup_txt.find("body")
            if main_txt:
                h1_txt = main_txt.find("h1")
                titre_txt = h1_txt.get_text(strip=True) if h1_txt else "Sans titre"
                contenu_txt = main_txt.get_text(separator="\n").strip()
                texte = extraire_texte_nettoye(contenu_txt)
                results[celex]["titre_txt"] = titre_txt
                results[celex]["contenu_txt"] = texte

        # Si c'est un _SUM, on récupère AUSSI la version SUM
        if celex.endswith("_SUM"):
            full_url_sum = BASE_URL_SUM + celex
            print(f"Fetching (SUM): {full_url_sum}")

            try:
                r_sum = session.get(full_url_sum, timeout=10)
                r_sum.raise_for_status()
            except requests.RequestException as e:
                print(f"[!] Error fetching SUM for {celex}: {e}")
                r_sum = None

            if r_sum:
                soup_sum = BeautifulSoup(r_sum.text, "html.parser")
                main_sum = soup_sum.find("p", class_="title-bold")

                if main_sum:
                    print(f"il y a un titre????{main_sum}")
                    h1_sum = main_sum.find("h1")
                    titre_sum = main_sum.get_text(strip=True) if h1_sum else "Sans titre"
                    contenu_sum = main_sum.get_text(separator="\n").strip()
                    texte = extraire_texte_nettoye(contenu_sum)
                    results[celex]["url_sum"] = full_url_sum
                    results[celex]["titre_sum"] = titre_sum
                    results[celex]["contenu_sum"] = texte

# Affichage résumé
print("\nRésultats collectés :")
for k, v in results.items():
    if v["contenu_txt"]:
        print(f"- {k}: [TXT] {v['titre_txt']} ({len(v['contenu_txt'])} caractères)")

    else:
        print(f"- {k}: [TXT] Aucun contenu récupéré")
    if v["contenu_sum"]:
        print(f"       [SUM] {v['titre_sum']} ({len(v['contenu_sum'])} caractères)")
        print(f" SUM TEXT {v['contenu_sum']}")



# Connexion à Meilisearch (localhost:7700 par défaut)
client = meilisearch.Client("http://127.0.0.1:7700")

# Nom de l'index
index_name = "eurlex_docs_retry"

# Crée l'index s'il n'existe pas
try:
    index = client.get_index(index_name)
except meilisearch.errors.MeilisearchApiError:
    index = client.create_index(index_name, {"primaryKey": "id"})

# Préparer les documents à indexer
documents = []

for celex, v in results.items():
    if not v["contenu_txt"]:
        continue  # on ignore ceux qui n'ont rien récupéré

    # Nettoyer l'ID
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", celex)

    doc = {
        "id": safe_id,
        "titre": v["titre_txt"],
        "contenu": v["contenu_txt"],
        "url": v["url_txt"]
    }

    if v["contenu_sum"]:
        doc["contenu_sum"] = v["contenu_sum"]
        doc["titre_sum"] = v["titre_sum"]
        doc["url_sum"] = v["url_sum"]

    documents.append(doc)

print(f"\nNombre de documents à indexer : {len(documents)}")

# Envoi vers Meilisearch

response = index.add_documents(documents)

print("Indexation lancée !")
print("Task UID:", response.task_uid)

# Attendre la fin de la tâche
index.wait_for_task(response.task_uid, timeout_in_ms=60000)
print("Indexation terminée.")
task_info = index.get_task(response.task_uid)
print("\n=== Détails complets de la tâche ===")
print(task_info)

