# --- Imports standards ---
import re
import csv
import ast
import os

# --- Bibliothèques tierces ---
from meilisearch import Client
from dotenv import load_dotenv

# --- Chargement des variables d'environnement ---
load_dotenv()
MEILI_URL = os.getenv("MEILI_URL")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")

# --- CONSTANTES ---
ADRESSE_PREFIXES_FILTRE = (
    r"(RUE|R\.|AVENUE|COURS|COUR|AV\.|CHEE|CHAUSS[ÉE]E|ROUTE|RTE|PLACE|PL\.?"
    r"|BOULEVARD|BD|CHEMIN|CH\.?|GALERIE|IMPASSE|SQUARE|ALL[ÉE]E|CLOS|VOIE|RY|PASSAGE|QUAI"
    r"|PARC|Z\.I\.?|ZONE|SITE|PROMENADE|FAUBOURG|FBG|QUARTIER|CITE|HAMEAU|LOTISSEMENT|RESIDENCE)"
)

LOG_FILE = "logs/extraction.log"
CORRECTIONS_CSV = "corrections_faites.csv"
LONGUEUR_MIN = 60

client = Client(MEILI_URL, MEILI_KEY)
index = client.index(INDEX_NAME)

with open(CORRECTIONS_CSV, "a", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    if csvfile.tell() == 0:
        writer.writerow(["id", "ancienne_adresse", "nouvelle_adresse"])

    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            if "Résultat :" in line:
                id_match = re.search(r"ID=([0-9a-f]{64})", line)
                if not id_match:
                    continue
                doc_id = id_match.group(1)

                resultat_str = line.split("Résultat :", 1)[1].strip()

                try:
                    resultat = ast.literal_eval(resultat_str)  # lecture de structures Python
                except (ValueError, SyntaxError) as e:
                    print(f"⚠ Ligne illisible pour ID={doc_id}: {resultat_str} ({e})")
                    continue

                # Si c'est juste une chaîne ou une liste brute
                if isinstance(resultat, (list, tuple)):
                    adresse = resultat[0] if resultat else None
                    alerte = False
                elif isinstance(resultat, dict):
                    adresse = resultat.get("adresse")
                    alerte = resultat.get("alerte", False)
                else:
                    adresse = str(resultat)
                    alerte = False

                # 🔹 Vérification et correction de l'adresse
                if adresse and (
                    len(adresse) >= LONGUEUR_MIN
                    and not re.match(rf"^{ADRESSE_PREFIXES_FILTRE}\b", adresse, flags=re.IGNORECASE)
                ):
                    print(f"\n📌 ID trouvé: {doc_id}")
                    print(f"Ancienne adresse (log): {adresse}")
                    index.update_documents([{"id": doc_id, "adresse": None}])
                    print("⛔ Adresse supprimée.")
                    nouvelle_adresse = input("Nouvelle adresse : ").strip()
                    index.update_documents([{"id": doc_id, "adresse": nouvelle_adresse}])
                    print("✅ Nouvelle adresse insérée.")
                    writer.writerow([doc_id, adresse, nouvelle_adresse])
                    csvfile.flush()

                # 🔹 Vérification et correction du champ extra_keyword
                try:
                    doc = index.get_document(doc_id)
                    doc_data = dict(doc)  # 🔹 Conversion en dict
                except Exception as e:
                    print(f"⚠ Impossible de récupérer le document {doc_id} ({e})")
                    continue

                if not doc_data.get("extra_keyword"):
                    texte = doc_data.get("text", "")
                    extrait = texte[:200].replace("\n", " ") + "..." if texte else "[Pas de texte]"
                    print(f"\n📌 ID sans extra_keyword: {doc_id}")
                    print(f"Extrait du texte: {extrait}")
                    nouveau_keyword = input("Nouveau extra_keyword : ").strip()
                    index.update_documents([{"id": doc_id, "extra_keyword": nouveau_keyword}])
                    print("✅ extra_keyword inséré.")

