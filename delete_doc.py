import meilisearch
from datetime import datetime

# Connexion
client = meilisearch.Client(MEILI_URL, MEILI_MASTER_KEY)
index = client.index("moniteur_documents")

# Formats de date
DATE_FORMATS = ["%d/%m/%Y", "%Y-%m-%d"]
start_date = datetime.strptime("01/06/2025", "%d/%m/%Y")
end_date = datetime.strptime("02/08/2025", "%d/%m/%Y")

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
