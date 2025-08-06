import meilisearch
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
MEILI_URL = os.getenv("MEILI_URL")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")

# Connexion
client = meilisearch.Client(MEILI_URL, MEILI_KEY)
index = client.index(INDEX_NAME)

# Formats de date
DATE_FORMATS = ["%d/%m/%Y", "%Y-%m-%d"]
start_date = datetime.strptime("01/06/2025", "%d/%m/%Y")
end_date = datetime.strptime("05/08/2025", "%d/%m/%Y")

# Récupérer tous les documents
result = index.search("", {"limit": 3000})
ids_to_delete = []

for doc in result["hits"]:
    doc_id = doc.get("id")
    date_str = doc.get("date_document")

    if doc_id and date_str:
        parsed = False
        for fmt in DATE_FORMATS:
            try:
                doc_date = datetime.strptime(date_str, fmt)
                parsed = True
                if start_date <= doc_date <= end_date:
                    ids_to_delete.append(doc_id)
                break
            except ValueError:
                continue
        if not parsed:
            print(f"⚠️ Format de date invalide pour ID={doc_id} : '{date_str}'")

# Suppression et attente
if ids_to_delete:
    print(f"🗑️ Suppression de {len(ids_to_delete)} document(s)...")
    delete_task = index.delete_documents(ids_to_delete)
    client.wait_for_task(delete_task.task_uid)  # attendre la fin
    print("✅ Suppression terminée.")
else:
    print("✅ Aucun document à supprimer.")

# Vérifier le nombre de documents après suppression
check = index.search("", {"limit": 1})
print("📊 Nombre réel de documents restants :", check["estimatedTotalHits"])

r"""from dotenv import load_dotenv
import os

# Charger les variables d'environnement
load_dotenv()
MEILI_URL = os.getenv("MEILI_URL")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")

# Connexion au client Meilisearch
client = meilisearch.Client(MEILI_URL, MEILI_KEY)
index = client.index(INDEX_NAME)

# Supprimer tous les documents
print(f"🗑️ Suppression de tous les documents dans l'index '{INDEX_NAME}'...")
task = index.delete_all_documents()

# Attendre que la tâche soit terminée
client.wait_for_task(task.task_uid)
print("✅ Tous les documents ont été supprimés.")
"""
