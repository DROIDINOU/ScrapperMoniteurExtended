import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import requests
import tempfile
import os
import re

# Définir le chemin vers l'exécutable Tesseract si nécessaire (en cas de problème)
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Télécharger le fichier PDF
url = "https://www.ejustice.just.fgov.be/mopdf/2025/04/01_1.pdf#page=41"
response = requests.get(url)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# Vérification si le téléchargement a réussi
if response.status_code == 200:
    print("Fichier PDF téléchargé avec succès.")
else:
    print(f"Échec du téléchargement du PDF, code d'état: {response.status_code}")
    exit(1)

# Sauvegarde le PDF dans un fichier temporaire
with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
    tmp_file.write(response.content)
    tmp_file_path = tmp_file.name
    print(f"Fichier temporaire enregistré à : {tmp_file_path}")

# Fonction pour convertir une page du PDF en image (300 DPI)
def convert_pdf_to_image(pdf_path, page_number):
    try:
        pdf_document = fitz.open(pdf_path)
        page = pdf_document.load_page(page_number)  # Page indexée à partir de 0
        
        # Convertir la page en image à 300 DPI (haute résolution)
        pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))  # dpi=300
        img_path = f"page_{page_number + 1}.png"
        pix.save(img_path)
        pdf_document.close()
        print(f"Page {page_number + 1} convertie en image et sauvegardée sous : {img_path}")
        return img_path
    except Exception as e:
        print(f"Erreur lors de la conversion de la page {page_number + 1} en image : {e}")
        return None

# Fonction pour extraire le texte de l'image avec OCR (Tesseract)
def extract_text_from_image(image_path):
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        print(f"Erreur lors de l'extraction du texte avec OCR sur l'image {image_path}: {e}")
        return None

# Fonction pour extraire les noms et numéros de registre national (NRN) avec une regex
def extract_names_and_nns(text):
    # Regex pour extraire les noms et NRN
    pattern = r"(\d+)[,\.]\s*([A-Za-z\s]+)\s*\(NRN:\s*(\d{2}\.\d{2}\.\d{2}-\d{3}\.\d{2})\)"
    matches = re.findall(pattern, text)
    
    # Afficher les résultats extraits
    names_and_nns = []
    for match in matches:
        number, name, nn = match
        names_and_nns.append((name.strip(), nn.strip()))  # Ajouter le nom et le NRN dans la liste
        print(f"Nom: {name.strip()}, NRN: {nn.strip()}")
    return names_and_nns

# Convertir la page 41 (page 40 en index PyMuPDF) en image
img_path = convert_pdf_to_image(tmp_file_path, 43)

# Si la conversion en image a réussi, appliquer l'OCR
if img_path:
    print("Exécution de l'OCR sur l'image...")
    text = extract_text_from_image(img_path)

    # Si le texte est extrait avec succès, afficher un extrait
    if text:
        print("\nTexte extrait avec succès :")
        print(text[:500])  # Afficher les 500 premiers caractères du texte extrait

        # Extraire les noms et NRN du texte
        names_and_nns = extract_names_and_nns(text)
    else:
        print("Impossible d'extraire le texte de l'image.")

# Nettoyage du fichier temporaire
os.remove(tmp_file_path)
print(f"Fichier temporaire {tmp_file_path} supprimé.")
