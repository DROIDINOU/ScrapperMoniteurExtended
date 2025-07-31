import requests
import fitz  # PyMuPDF
import re  # Pour utiliser les expressions régulières

# URL du PDF à télécharger
pdf_url = "https://www.lachambre.be/FLWB/PDF/55/0081/55K0081001.pdf"

# Télécharger le PDF
response = requests.get(pdf_url)
pdf_path = "document.pdf"

# Enregistrer le PDF localement
with open(pdf_path, 'wb') as f:
    f.write(response.content)

# Ouvrir le PDF avec PyMuPDF
doc = fitz.open(pdf_path)

# Extraire le texte de la première page
page = doc.load_page(0)  # La première page est à l'index 0
text = page.get_text()

# Expression régulière pour extraire la date au format "9 juillet 2019"
# Nous incluons ici tous les mois en français avec leurs accents
mois_francais = r"(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)"

# Expression régulière pour une date au format "9 juillet 2019"
date_pattern = r"\b(\d{1,2}\s+" + mois_francais + r"\s+\d{4})\b"

# Recherche de la date dans le texte
match = re.search(date_pattern, text, re.IGNORECASE)

# Si une date est trouvée, l'afficher
if match:
    extracted_date = match.group(0)
    print(f"Date extraite : {extracted_date}")
else:
    print("Aucune date trouvée.")
