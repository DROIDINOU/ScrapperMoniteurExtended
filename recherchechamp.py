import meilisearch

# Connexion à Meilisearch
client = meilisearch.Client("http://127.0.0.1:7700", 'TBVEHV1dBQBT7mVQpHXw2RXeICzQvONQ5p9CqI84gF4')
print(client.get_indexes())  # Affiche les index existants

index = client.index("moniteur_documents")  # <- tu avais oublié cette ligne

# Récupérer jusqu'à 2500 documents
result = index.search("", {"limit": 2500})

# Stocker les IDs des documents sans 'adresse' ou avec champ vide
docs_sans_extra_keyword = []

for doc in result["hits"]:
    doc_id = doc.get("id")
    adresse = doc.get("adresse")

    if adresse:  # Si vide, None, ou []
        print(f"❌ ID : {doc_id} | adresse : {adresse}")
        docs_sans_extra_keyword.append(doc_id)

print("\n📊 Nombre total de documents sans 'adresse' :", len(docs_sans_extra_keyword))
