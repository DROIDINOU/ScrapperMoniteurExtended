import meilisearch

# Connexion à MeiliSearch
client = meilisearch.Client(MEILI_URL, MEILI_MASTER_KEY)
index = client.index("moniteur_documents")

# Nombre total de docs
stats = index.get_stats()
total_docs = stats.number_of_documents
print(f"📊 Total de documents dans l'index : {total_docs}")

# Pagination avec search()
all_docs = []
offset = 0
limit = 1000

while True:
    res = index.search("", {"limit": limit, "offset": offset})
    hits = res["hits"]
    if not hits:
        break
    all_docs.extend(hits)
    offset += limit
    if len(all_docs) >= total_docs:
        break

print(f"✅ Documents récupérés : {len(all_docs)}")

# Classification
docs_avec = []
docs_sans = []

for doc in all_docs:
    doc_id = doc.get("id")
    adresse = doc.get("adresse")

    if adresse is None:
        docs_sans.append(doc)
    elif isinstance(adresse, str):
        if adresse.strip():
            docs_avec.append(doc)
        else:
            docs_sans.append(doc)
    elif isinstance(adresse, list):
        strings_valides = [a for a in adresse if isinstance(a, str) and a.strip()]
        if strings_valides:
            docs_avec.append(doc)
        else:
            docs_sans.append(doc)
    else:
        docs_sans.append(doc)

# 📊 Résumé
print("\n📊 Récapitulatif :")
print("Avec adresse :", len(docs_avec))
print("Sans adresse :", len(docs_sans))
print("Somme :", len(docs_avec) + len(docs_sans))

# 🔍 Afficher les 10 premiers sans adresse avec ID et texte
print("\n🔍 Exemples de documents sans adresse :")
for doc in docs_sans[:10]:
    print(f"- ID: {doc.get('id')} | texte: {repr(doc.get('text'))[:250]}...")
