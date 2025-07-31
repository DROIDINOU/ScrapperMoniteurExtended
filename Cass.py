import requests
from bs4 import BeautifulSoup
import re
import meilisearch

# URL de base
base_url = "https://juricaf.org/recherche/+/facet_pays%3ABelgique%2Cfacet_pays_juridiction%3ABelgique_%7C_Cour_de_cassation?tri=DESC&pays=Belgique&juridiction=Belgique+%7C+Cour+de+cassation&page="

# Fonction pour récupérer les titres, résumés, href et dates des arrêts
def get_arret_details(page_num):
    url = base_url + str(page_num)
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Recherche des div contenant les arrêts
    cards = soup.find_all('div', class_='card bloc-search-item')

    # Si aucun arrêt n'est trouvé, retourner None pour arrêter
    if not cards:
        return None

    # Extraction des titres, résumés, href et dates
    arrets = []
    for card in cards:
        title_element = card.find('a')  # Lien du titre
        title = title_element.get_text(strip=True)  # Titre de l'arrêt
        href = "https://juricaf.org" + title_element['href']  # URL complète du lien
        summary = card.find('p', class_='card-text text-justify').get_text(strip=True)  # Résumé de l'arrêt
        
        # Extraction de la date
        date_text = card.find('small', class_='card-header text-muted').get_text(strip=True)
        date_match = re.search(r'(\d{2})\s([a-zéè]+\s[a-z]+)\s(\d{4})', date_text)
        date = None
        if date_match:
            day = date_match.group(1)
            month = date_match.group(2)
            year = date_match.group(3)
            date = f"{day} {month} {year}"
        
        # Créer un id unique basé sur le href
        doc_id = href.split("/")[-1]  # L'ID sera la dernière partie de l'URL

        arrets.append({
            'id': doc_id,
            'title': title,
            'href': href,
            'summary': summary,
            'date': date
        })
    
    return arrets

# Connecter à MeiliSearch
client = meilisearch.Client('http://localhost:7700')  # URL de MeiliSearch
index = client.index('juris')

# Parcours des pages et ajout dans MeiliSearch
page_num = 1
while page_num <=10:
    print(f"Page {page_num}:")
    arrets = get_arret_details(page_num)
    
    if not arrets:  # Si aucune donnée n'est récupérée, on arrête
        print("Aucun résultat ou fin de page.")
        break
    
    # Ajouter les documents dans MeiliSearch
    documents = [{'id': arret['id'], 'text': arret['summary'], 'title': arret['title'], 'href': arret['href'], 'date': arret['date']} for arret in arrets]
    index.add_documents(documents)
    
    # Passer à la page suivante
    page_num += 1
    print(f"Documents ajoutés pour la page {page_num - 1}.")
