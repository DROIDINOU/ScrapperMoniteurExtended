from pathlib import Path
from dotenv import load_dotenv
from meilisearch import Client
import csv
import os
import unicodedata
import re

# --------------------------------------------
# 1) Charger dotenv (clé MeiliSearch)
# --------------------------------------------
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path, override=True)

client = Client(
    os.getenv("MEILI_URL"),
    os.getenv("MEILI_MASTER_KEY")
)

index_name = os.getenv("MEILI_INDEX_RUES", "mesrues_be")

# --------------------------------------------
# 2) Supprimer l’index avant import (clean)
# --------------------------------------------
try:
    client.index(index_name).delete()
    print(f"🗑️ Index supprimé : {index_name}")
except:
    print("ℹ️ Aucun index existant")

client.create_index(index_name, {"primaryKey": "id"})
print(f"🆕 Index créé : {index_name}")

csv_folder = Path(__file__).resolve().parents[1] / "Datas" / "ProvincesRues"

docs = []
unique_streets = set()  # ✅ déduplication uniquement sur le nom de rue
uid = 1

# --------------------------------------------
# 3) Fonction de normalisation
# --------------------------------------------
def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.category(c).startswith("M"))
    value = re.sub(r"\s+", " ", value)
    return value.strip().lower()

# --------------------------------------------
# 4) Lecture des CSV
# --------------------------------------------
for csv_file in csv_folder.glob("*.csv"):
    print(f"📄 Lecture : {csv_file.name}")

    with open(csv_file, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")

        for row in reader:
            if not row or len(row) < 1:
                continue

            street = row[0].strip()
            if not street:
                continue

            # ✅ Déduplication uniquement sur le nom
            s_norm = normalize(street)
            if s_norm in unique_streets:
                continue

            unique_streets.add(s_norm)

            docs.append({
                "id": uid,
                "name": street,   # champ Meili utilisé pour la recherche & l'affichage
                "label": street   # ✅ label = juste nom de rue
            })
            uid += 1

# --------------------------------------------
# 5) Import Meilisearch en batch
# --------------------------------------------
print(f"✅ {len(docs)} rues uniques à indexer")

batch_size = 10_000
for i in range(0, len(docs), batch_size):
    chunk = docs[i:i + batch_size]
    print(f"📤 Batch {i//batch_size + 1} — {len(chunk)} rues")
    task = client.index(index_name).add_documents(chunk)

print("✅ Import terminé")
print(f"➡️ Dernière Task ID : {task.task_uid}")
