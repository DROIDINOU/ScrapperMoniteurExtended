import re
from pdfminer.high_level import extract_text

def extract_from_moniteur(pdf_path):
    text = extract_text(pdf_path)
    data = {}

    # Exemple de patterns à extraire
    # Numéro d’entreprise
    m = re.search(r"N° d’entreprise\s*:\s*([0-9]+)", text)
    if m:
        data['numéro_entreprise'] = m.group(1)

    # Dénomination sociale
    m = re.search(r"Nom et forme\s*.*?dénommée «([^»]+)»", text)
    if m:
        data['dénomination'] = m.group(1).strip()

    # Forme légale
    m = re.search(r"Forme légale\s*:\s*(.+)", text)
    if m:
        data['forme_légale'] = m.group(1).strip()

    # Adresse complète du siège
    m = re.search(r"Adresse complète du siège\s*(.+?)\n", text)
    if m:
        data['adresse_siège'] = m.group(1).strip()

    # Date de l’acte
    m = re.search(r"le\s+([0-9]{1,2}\s+\w+\s+[0-9]{4})", text)
    if m:
        data['date_acte'] = m.group(1).strip()

    return data

if __name__ == "__main__":
    pdf_file = "21355024.pdf"  # chemin vers ton PDF téléchargé
    info = extract_from_moniteur(pdf_file)
    print("Infos extraites :", info)
