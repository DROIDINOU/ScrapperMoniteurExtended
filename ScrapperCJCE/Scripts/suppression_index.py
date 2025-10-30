import os
from pathlib import Path
from dotenv import load_dotenv
import meilisearch

# ✅ Localise le fichier .env dans le dossier parent
env_path = Path(__file__).resolve().parents[2] / ".env"
print(f"🔍 Loading .env from: {env_path}")

# ✅ Force le chargement du .env, même si un .env existe ailleurs
load_dotenv(dotenv_path=env_path, override=True)

# 🚨 Debug (temporaires)
print("➡️ MEILI_URL =", os.getenv("MEILI_URL"))
print("➡️ MEILI_MASTER_KEY =", os.getenv("MEILI_MASTER_KEY"))
print("➡️ INDEX_NAME =", os.getenv("INDEX_NAME"))
MEILI_URL = os.getenv("MEILI_URL")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY")
print("➡️ DEBUG MEILI_URL =", os.getenv("MEILI_URL"))
print("➡️ DEBUG MEILI_MASTER_KEY =", os.getenv("MEILI_MASTER_KEY"))
# 🔹 Connexion
client = meilisearch.Client(MEILI_URL, MEILI_KEY)

# 🔹 Récupérer tous les index
indexes = client.get_indexes()

# Si c'est un dict (nouveau SDK), il faut lire indexes["results"]
if isinstance(indexes, dict):
    indexes = indexes.get("results", [])

if not indexes:
    print("✅ Aucun index trouvé, Meilisearch est déjà vide.")
else:
    print(f"⚠️ {len(indexes)} index trouvés, suppression en cours...")
    for idx in indexes:
        uid = idx["uid"] if isinstance(idx, dict) else idx.uid
        print(f"🗑️ Suppression de l'index : {uid}")
        task = client.delete_index(uid)
        client.wait_for_task(task.task_uid)

    print("✅ Tous les index ont été supprimés.")
