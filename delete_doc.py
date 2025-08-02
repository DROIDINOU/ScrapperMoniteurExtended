import meilisearch
from datetime import datetime

# Connexion à Meilisearch
client = meilisearch.Client("http://127.0.0.1:7700", 'TBVEHV1dBQBT7mVQpHXw2RXeICzQvONQ5p9CqI84gF4')
index = client.index("moniteur_documents")

# Accepter plusieurs formats de date
DATE_FORMATS = ["%d/%m/%Y", "%Y-%m-%d"]
start_date = datetime.strptime("01/06/2025", "%d/%m/%Y")
end_date = datetime.strptime("01/08/2025", "%d/%m/%Y")

# Récupération des documents
result = index.search("", {"limit": 2500})
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
                break  # dès qu’un format a fonctionné, on sort
            except ValueError:
                continue
        if not parsed:
            print(f"⚠️ Format de date invalide pour ID={doc_id} : '{date_str}'")

# Suppression si nécessaire
if ids_to_delete:
    print(f"🗑️ Suppression de {len(ids_to_delete)} document(s)...")
    delete_response = index.delete_documents(ids_to_delete)
    print("✅ Suppression lancée. Réponse Meili:", delete_response)
else:
    print("✅ Aucun document à supprimer dans l'intervalle spécifié.")
