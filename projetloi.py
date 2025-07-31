import requests
import fitz  # PyMuPDF
import re
import time
import os  # Pour supprimer le fichier PDF après extraction
import meilisearch  # Pour la connexion à MeiliSearch

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Chemins pour le chrome.exe et chromedriver
chrome_driver_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
chromedriver_path = r"C:\chrome\chromedriver.exe"  # Mettez ici le chemin correct vers votre chromedriver

# Configuration des options pour Chrome
chrome_options = Options()
chrome_options.binary_location = chrome_driver_path

# Ajouter un User-Agent personnalisé pour imiter un navigateur normal
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
chrome_options.add_argument("--headless")  # Si vous voulez exécuter le navigateur en mode headless

# Initialiser le service et le driver
service = Service(chromedriver_path)
driver = webdriver.Chrome(service=service, options=chrome_options)

# Set pour stocker les résultats uniques
result_set = set()

# Fonction pour extraire la date depuis le texte du PDF
def extract_date_from_pdf(pdf_url):
    # Télécharger le PDF
    response = requests.get(pdf_url)
    pdf_path = "documenttest.pdf"
    
    with open(pdf_path, 'wb') as f:
        f.write(response.content)
    
    # Ouvrir le PDF avec PyMuPDF
    doc = fitz.open(pdf_path)
    
    # Extraire le texte de la première page
    page = doc.load_page(0)
    text = page.get_text()

    # Expression régulière pour extraire la date au format "9 juillet 2019"
    mois_francais = r"(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)"
    date_pattern = r"\b(\d{1,2}\s+" + mois_francais + r"\s+\d{4})\b"
    
    match = re.search(date_pattern, text, re.IGNORECASE)
    
    # Si une date est trouvée, la retourner
    if match:
        # Fermer le fichier avant de supprimer
        doc.close()
        # Ajouter un délai pour garantir que le fichier soit bien libéré
        time.sleep(1)
        # Supprimer le fichier PDF après traitement
        os.remove(pdf_path)
        return match.group(0)
    else:
        # Fermer le fichier même s'il n'y a pas de date
        doc.close()
        # Ajouter un délai pour garantir que le fichier soit bien libéré
        time.sleep(1)
        # Supprimer le fichier PDF
        os.remove(pdf_path)
        return None  # Si aucune date n'est trouvée

# Fonction pour explorer l'URL
def explore_url(from_num, to_num):
    url = f"https://www.lachambre.be/kvvcr/showpage.cfm?section=/flwb&language=fr&cfm=ListFromTo.cfm?legislat=55&from={from_num}&to={to_num}"
    print(f"Exploration de l'URL : {url}")
    driver.get(url)

    # Attendre que le tableau <tbody> se charge
    wait = WebDriverWait(driver, 10)  # Attente de 10 secondes
    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "tbody")))
    except:
        print("Page non trouvée ou erreur de chargement")
        return False  # La page n'a pas pu être chargée

    # Récupérer tout le HTML de la page
    html = driver.page_source

    # Chercher tous les éléments <tbody> et extraire les données
    tbody = driver.find_element(By.TAG_NAME, "tbody")
    trs = tbody.find_elements(By.TAG_NAME, "tr")

    if not trs:
        print("Aucune donnée trouvée.")
        return False  # Aucune donnée à extraire

    # Extraire les informations à partir des tr et td
    for tr in trs:
        tds = tr.find_elements(By.TAG_NAME, "td")
        
        # Vérifier si la ligne contient suffisamment de td
        if len(tds) > 1:
            # Extraire le texte des td et afficher
            texts = []
            for td in tds:
                divs = td.find_elements(By.CLASS_NAME, "linklist_0") + td.find_elements(By.CLASS_NAME, "linklist_1")
                for div in divs:
                    texts.append(div.text)  # Récupère tous les textes de divs

            # Assumer que le premier texte extrait contient un numéro, et que le deuxième texte contient des informations sur le projet ou proposition
            if len(texts) > 1:
                first_text = texts[0].strip()  # Premier texte (numéro)
                second_text = texts[1].strip()  # Deuxième texte (proposition/loi)

                # Vérifier si le deuxième texte contient "proposition" ou "loi"
                if "proposition" in second_text.lower() or "loi" in second_text.lower():
                    # Extraire le numéro du premier texte
                    match = re.search(r"\d{4}", first_text)
                    if match:
                        number = match.group(0)  # Récupérer le numéro trouvé
                        print(f"Numéro extrait : {number}")
                        
                        # Créer l'URL avec le numéro extrait
                        dossier_url = f"https://www.lachambre.be/FLWB/PDF/55/{number}/55K{number}001.pdf"
                        print(f"URL générée : {dossier_url}")
                        
                        # Extraire la date du PDF
                        date = extract_date_from_pdf(dossier_url)
                        if date:
                            print(f"Date extraite : {date}")
                        else:
                            print("Aucune date trouvée dans le PDF.")
                        
                        # Ajouter l'information (texte extrait, numéro, date et URL) dans le set
                        result_set.add((second_text, number, date, dossier_url))

    return True  # Si tout est bon, renvoyer True

# Connexion à MeiliSearch
client = meilisearch.Client('http://127.0.0.1:7700')  # Assurez-vous que MeiliSearch fonctionne à cette adresse

# Créer l'index si ce n'est pas déjà fait
index_name = 'propositions_et_loisbisbis'
try:
    client.create_index(index_name)
except Exception as e:
    print(f"Index déjà existant : {e}")

# Accéder à l'index
index = client.index(index_name)

# Boucle pour parcourir les pages avec l'incrémentation
from_num = 0
to_num = 99
while to_num < 100:
    result = explore_url(from_num, to_num)
    if not result:
        break  # Si la réponse est incorrecte ou si aucune donnée n'est trouvée, on arrête le script
    from_num += 100
    to_num += 100
    time.sleep(1)  # Petite pause pour ne pas surcharger le serveur

# Préparer les documents à insérer dans MeiliSearch
documents = []
for entry in result_set:
    text, number, date, url = entry
    documents.append({
        'id': number,  # Utilisation du numéro comme ID unique
        'date_document': date,
        'numero': number,
        'url': url,
        'texte': text
    })

# Insérer les documents dans MeiliSearch
try:
    response = index.add_documents(documents)
    print(f"Documents ajoutés avec succès : {response}")
except Exception as e:
    print(f"Erreur lors de l'ajout des documents : {e}")

# Fermer le navigateur
driver.quit()
