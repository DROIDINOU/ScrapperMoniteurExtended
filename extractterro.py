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

def convert_pdf_pages_to_text_range(pdf_url, start_page_index, page_count=6):
    """
    Télécharge un PDF depuis une URL, applique l’OCR sur plusieurs pages à partir de start_page_index.
    Gère automatiquement les erreurs de rendu, les fichiers manquants, les permissions et les profils ICC.
    """
    try:
        response = requests.get(pdf_url)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement du PDF : {e}")
        return ""

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(response.content)
        tmp_path = tmp_file.name
        print(f"[📄] PDF temporaire sauvegardé : {tmp_path}")

    full_text = ""
    pdf = None

    try:
        pdf = fitz.open(tmp_path)
        total_pages = len(pdf)

        # 🔒 Protection contre start_page_index = None
        if start_page_index is None:
            print(f"[⚠️] start_page_index est None — on démarre à la page 0")
            start_page_index = 0

        end_page_index = min(start_page_index + page_count, total_pages)

        for i in range(start_page_index, end_page_index):
            try:
                page = pdf.load_page(i)
                # ✅ Matrice à 2x + suppression des profils ICC
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csRGB)
                img_path = f"ocr_page_{i + 1}.png"
                pix.save(img_path)

                if not os.path.exists(img_path):
                    print(f"[❌] Image non créée pour la page {i + 1} : {img_path}")
                    continue

                # ✅ Libère le fichier après lecture
                with Image.open(img_path) as img:
                    text = pytesseract.image_to_string(img)

                full_text += f"\n--- Page {i + 1} ---\n{text}"

                try:
                    os.remove(img_path)
                except Exception as e_rm:
                    print(f"[⚠️] Impossible de supprimer '{img_path}' : {e_rm}")

            except Exception as e_page:
                print(f"⚠️ Erreur OCR sur la page {i + 1} : {e_page}")
                continue

    except Exception as e_open:
        print(f"❌ Erreur d’ouverture ou d’OCR : {e_open}")
        return ""

    finally:
        if pdf:
            pdf.close()
        try:
            os.remove(tmp_path)
        except Exception as e_rm:
            print(f"[⚠️] Erreur suppression fichier temporaire : {e_rm}")

    return full_text.strip()


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
