# --- Imports standards ---
import os
# --- Bibliothèques tierces ---
from dotenv import load_dotenv
import meilisearch

# --- Chargement des variables d'environnement ---
load_dotenv()
MEILI_URL = os.getenv("MEILI_URL")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")
# Charger les variables d'environnement


# Connexion au client Meilisearch
client = meilisearch.Client(MEILI_URL, MEILI_KEY)
index = client.index(INDEX_NAME)

# Supprimer tous les documents
print(f"🗑️ Suppression de tous les documents dans l'index '{INDEX_NAME}'...")
task = index.delete_all_documents()

# Attendre que la tâche soit terminée
client.wait_for_task(task.task_uid)
print("✅ Tous les documents ont été supprimés.")

