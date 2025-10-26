import os
from meilisearch import Client
from dotenv import load_dotenv

def compter_admins_meili():
    # Charger les variables d'environnement (.env)
    load_dotenv()
    MEILI_URL = os.getenv("MEILI_URL")
    MEILI_KEY = os.getenv("MEILI_MASTER_KEY")
    INDEX_NAME = os.getenv("INDEX_NAME")

    # Connexion au client MeiliSearch
    client = Client(MEILI_URL, MEILI_KEY)
    index = client.index(INDEX_NAME)

    print(f"[🔍] Connexion à MeiliSearch : {MEILI_URL}")
    print(f"[📁] Index analysé : {INDEX_NAME}\n")

    # Requête : pas de texte, juste les facettes
    response = index.search(
        "",  # terme de recherche vide
        {
            "facets": ["admins_detectes"],
            "limit": 0
        }
    )
    # Extraire la distribution
    facets = response.get("facetDistribution", {}).get("admins_detectes", {})
    if not facets:
        print("⚠️ Aucun administrateur détecté dans l'index.")
        return

    # Trier par fréquence décroissante
    top_admins = sorted(facets.items(), key=lambda x: x[1], reverse=True)

    print(f"[📊] {len(top_admins)} administrateurs détectés :\n")
    for i, (name, count) in enumerate(top_admins[:30], start=1):
        print(f"{i:2d}. {name:40} → {count} occurrence(s)")


if __name__ == "__main__":
    compter_admins_meili()
