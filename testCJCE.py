import re
import requests
from bs4 import BeautifulSoup
import meilisearch

def extraire_texte_nettoye(soup_element, separator="\n"):
    """
    Extrait et nettoie le texte d'un élément BeautifulSoup ou d'une chaîne HTML.
    """
    if isinstance(soup_element, str):
        soup_element = BeautifulSoup(soup_element, "html.parser")
    texte = soup_element.get_text(separator=separator).strip()
    texte = re.sub(r"[ \t]+", " ", texte)
    texte = re.sub(r"\n+", "\n", texte)
    return texte.strip()

# Liste des années
YEARS = [str(y) for y in range(2020, 2026)]

# Collecte CELEX
celex_set = set()
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
                celex_set.add(m.group(1))

print(f"\nNombre de CELEX trouvés : {len(celex_set)}")
for c in sorted(celex_set):
    print("-", c)

# Préparation des URLs
BASE_URL = "https://eur-lex.europa.eu/legal-content/FR/TXT/HTML/?uri=CELEX:"
BASE_URL_SUM = "https://eur-lex.europa.eu/legal-content/FR/SUM/?uri=CELEX:"

results = {}
with requests.Session() as session:
    for celex in sorted(celex_set):
        full_url_txt = BASE_URL + celex
        print(f"\nFetching (TXT): {full_url_txt}")
        try:
            r_txt = session.get(full_url_txt, timeout=10)
            r_txt.raise_for_status()
        except requests.RequestException as e:
            print(f"[!] Error fetching TXT for {celex}: {e}")
            r_txt = None

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
                texte = extraire_texte_nettoye(main_txt)
                results[celex]["titre_txt"] = titre_txt
                results[celex]["contenu_txt"] = texte

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
                    titre_sum = main_sum.get_text(strip=True)
                    texte = extraire_texte_nettoye(main_sum)
                    results[celex]["url_sum"] = full_url_sum
                    results[celex]["titre_sum"] = titre_sum
                    results[celex]["contenu_sum"] = texte

# Résumé
print("\nRésultats collectés :")
for k, v in results.items():
    if v["contenu_txt"]:
        print(f"- {k}: [TXT] {v['titre_txt']} ({len(v['contenu_txt'])} caractères)")
    else:
        print(f"- {k}: [TXT] Aucun contenu récupéré")
    if v["contenu_sum"]:
        print(f"       [SUM] {v['titre_sum']} ({len(v['contenu_sum'])} caractères)")

# Connexion Meilisearch
print("\n[DEBUG] Connexion à Meilisearch...")
client = meilisearch.Client("http://127.0.0.1:7700")
print("[DEBUG] Client Meilisearch créé.")

index_name = "eurlex_testing"
print("[DEBUG] Nom de l'index:", index_name)

try:
    index = client.get_index(index_name)
    print("[DEBUG] Index récupéré existant.")
except meilisearch.errors.MeilisearchApiError:
    print("[DEBUG] L'index n'existe pas, création...")
    create_task = client.create_index(index_name, {"primaryKey": "id"})
    print("[DEBUG] Task de création:", create_task)
    client.wait_for_task(create_task.task_uid)
    index = client.get_index(index_name)
    print("[DEBUG] Index récupéré après création.")

print("[DEBUG] Type de 'index':", type(index))

# Préparer documents
documents = []
for celex, v in results.items():
    if not v["contenu_txt"]:
        continue
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
print("[DEBUG] Premier document:", documents[0] if documents else "Aucun")

# Indexation
print("[DEBUG] Envoi des documents avec add_documents()...")
task = index.add_documents(documents)

print("[DEBUG] Type de 'task':", type(task))
print("[DEBUG] Contenu brut de 'task':", task)

print("Indexation lancée !")
print("Task UID:", task.task_uid)

index.wait_for_task(task.task_uid, timeout_in_ms=60000)
print("Indexation terminée.")

task_info = index.get_task(task.task_uid)
print("\n=== Détails complets de la tâche ===")
print(task_info)
