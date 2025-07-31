import meilisearch

# Connexion à Meilisearch
client = meilisearch.Client("http://127.0.0.1:7700")

# Nom de ton index
index_name = "moniteur_docs4"

# Récupérer l'index
index = client.index(index_name)

# Demander le mot-clé à l'utilisateur
query = input("Entrez le mot-clé à rechercher : ")

# Faire la recherche
results = index.search(
    query,
    {
        "limit": 10  # nombre de résultats à afficher
    }
)

# Récupérer les résultats
hits = results.get("hits", [])

print(f"\nNombre de résultats trouvés : {len(hits)}\n")

# Afficher les résultats
for i, hit in enumerate(hits, start=1):
    numac = hit.get("numac", "N/A")
    date = hit.get("date", "N/A")
    keyword = hit.get("keyword", "N/A")
    url = hit.get("url", "N/A")
    text = hit.get("text", "")

    extrait = text[:300].replace("\n", " ") + "..."

    print(f"{i}. [{date}] {keyword} (numac {numac})")
    print(f"   URL : {url}")
    print(f"   Extrait : {extrait}\n")
