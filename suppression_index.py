import os
from dotenv import load_dotenv
import meilisearch

# 🔹 Charger les variables d'environnement
load_dotenv()
MEILI_URL = os.getenv("MEILI_URL")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY")

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
