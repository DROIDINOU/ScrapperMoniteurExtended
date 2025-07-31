import requests
from bs4 import BeautifulSoup
import pdfplumber
from io import BytesIO

# Fonction pour récupérer les liens PDF supplémentaires et les détails (titre et langue) dans la page d'affaire
def fetch_pdf_details_and_links(affaire_url):
    print(f"Exploring: {affaire_url}")
    
    # Récupérer la page de l'affaire
    resp = requests.get(affaire_url)
    resp.raise_for_status()  # Vérifie si la requête est réussie
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Chercher la table contenant les documents associés à l'affaire
    table = soup.find("table", class_="ia-block-filter-arrests__table_content is-single")
    
    pdf_data = []
    
    if table:
        tbody = table.find("tbody")
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 3:
                # Extraire les informations du document (titre, langue, date)
                title_text = tds[0].get_text(strip=True)  # Titre du document
                language_text = tds[1].get_text(strip=True)  # Langue
                date_text = tds[2].get_text(strip=True)  # Date du document
                
                # Extraire le lien du PDF
                pdf_link = tds[0].find("a")["href"] if tds[0].find("a") else "Lien PDF non disponible"
                
                # Extraire le texte du PDF
                pdf_text = extract_pdf_text(pdf_link)
                
                # Ajout dans la liste des données PDF
                pdf_data.append((title_text, language_text, date_text, pdf_link, pdf_text))
        
    else:
        print("Aucune table de documents trouvée dans cette affaire.")
    
    return pdf_data

# Fonction pour extraire le texte d'un fichier PDF
def extract_pdf_text(pdf_url):
    try:
        # Récupérer le PDF
        pdf_resp = requests.get(pdf_url)
        pdf_resp.raise_for_status()
        
        # Lire le PDF en utilisant pdfplumber
        with pdfplumber.open(BytesIO(pdf_resp.content)) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text()
            
            # Retourner le texte extrait du PDF
            return text[:1000] if text.strip() else "Aucun texte extrait du PDF."
    except Exception as e:
        print(f"Erreur lors de l'extraction du texte du PDF : {e}")
        return "Erreur lors de l'extraction du PDF."

# URL de la page des arrêts et conclusions
url = "https://www.courbeneluxhof.int/fr/arrets-conclusions/"

# Récupérer la page
resp = requests.get(url)
resp.raise_for_status()

# Parser la page HTML avec BeautifulSoup
soup = BeautifulSoup(resp.text, "html.parser")

# Trouver la section tbody contenant les données
tbody = soup.find("tbody")
affaires_data = set()  # Créer un set pour stocker les résultats

if tbody:
    # Parcours chaque ligne <tr> dans tbody
    for tr in tbody.find_all("tr"):
        # Récupérer toutes les <td> dans la ligne
        tds = tr.find_all("td")
        
        if len(tds) >= 3:  # Vérifie qu'il y a bien 3 colonnes (titre, langue, date)
            # Récupérer le titre, la langue et la date à partir des <td>
            role = tds[0].get_text(strip=True)  # Titre du document
            nom = tds[1].get_text(strip=True)  # Langue
            objet = tds[2].get_text(strip=True)  # Date du document
            date = tds[3].get_text(strip=True)  # Date du document

            # Trouver le lien dans la colonne "affaire" (première colonne)
            affaire_link = tds[1].find("a")
            affaire_href = affaire_link["href"] if affaire_link else "Lien non disponible"

            # Afficher les informations extraites
            print(f"Numéro de rôle: {role}")
            print(f"Nom de l'affaire: {nom}")
            print(f"Objet: {objet}")
            print(f"Lien affaire: {affaire_href}")
            print(f"Date: {date}")
            
            # Appel de la fonction pour explorer chaque lien d'affaire et récupérer les PDF et autres informations
            affaire_pdf_data = fetch_pdf_details_and_links(affaire_href)
            
            # Ajouter les données dans le set pour chaque PDF extrait
            for pdf_info in affaire_pdf_data:
                affaires_data.add((role, nom, objet, date, *pdf_info))

            print("---")
else:
    print("Tableau <tbody> non trouvé.")

# Afficher le set avec toutes les informations extraites
print(f"\nTotal des affaires extraites : {len(affaires_data)}")
for affaire in affaires_data:
    print(affaire)
