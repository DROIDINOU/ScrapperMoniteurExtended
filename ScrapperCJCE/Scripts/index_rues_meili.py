from pathlib import Path
from dotenv import load_dotenv
from meilisearch import Client
import csv
import os

# ✅ Localiser le .env exactement comme MainScrapper.py
env_path = Path(__file__).resolve().parents[2] / ".env"
print(f"🔍 Loading .env from: {env_path}")

load_dotenv(dotenv_path=env_path, override=True)

# DEBUG (affiche la vraie clé chargée)
print("➡️ MEILI_URL =", os.getenv("MEILI_URL"))
print("➡️ MEILI_MASTER_KEY =", os.getenv("MEILI_MASTER_KEY"))

# Connexion MeiliSearch
client = Client(
    os.getenv("MEILI_URL"),
    os.getenv("MEILI_MASTER_KEY")
)

# ---- INDEXATION DES RUES ----

index_name = os.getenv("MEILI_INDEX_RUES", "mesrues_be")

# ✅ Création de l’index si inexistant
try:
    client.get_index(index_name)
    print(f"ℹ️ Index déjà existant : {index_name}")
except:
    client.create_index(index_name, {"primaryKey": "id"})
    print(f"🆕 Index créé : {index_name}")

# ✅ Chemin vers le CSV
csv_path = Path(__file__).resolve().parents[1] / "Datas" / "rues_belgique.csv"
print(f"📄 CSV load: {csv_path}")

docs = []
uid = 1

# ✅ Lecture du CSV sans header
with open(csv_path, encoding="utf-8") as f:
    reader = csv.reader(f, delimiter=";")

    for row in reader:
        if len(row) < 2:
            continue  # ignore lignes invalides

        name = row[1].strip()  # ✅ La rue est dans la 2e colonne

        if not name:
            continue  # ignore lignes vides

        docs.append({
            "id": uid,
            "name": name,
        })
        uid += 1

print(f"➡️ {len(docs)} rues détectées")
print("🚀 Envoi dans MeiliSearch...")

task = client.index(index_name).add_documents(docs)

print(f"🆗 Indexation lancée — Task ID : {task.task_uid}")
