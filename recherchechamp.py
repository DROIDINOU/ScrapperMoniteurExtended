import meilisearch

# Connexion à Meilisearch
client = meilisearch.Client("http://127.0.0.1:7700", 'TBVEHV1dBQBT7mVQpHXw2RXeICzQvONQ5p9CqI84gF4')
index = client.index("moniteur_documents")

# Récupérer jusqu'à 2500 documents
result = index.search("", {"limit": 2500})

# Stocker les IDs des documents sans 'extra_keyword' ou avec champ vide
docs_sans_extra_keyword = []

for doc in result["hits"]:
    doc_id = doc.get("id", "(id inconnu)")
    extra_keyword = doc.get("extra_keyword")

    if not extra_keyword:  # None, "", ou []
        print(f"❌ ID sans 'extra_keyword' : {doc_id}")
        docs_sans_extra_keyword.append(doc_id)

print("\n📊 Nombre total de documents sans 'extra_keyword' :", len(docs_sans_extra_keyword))
