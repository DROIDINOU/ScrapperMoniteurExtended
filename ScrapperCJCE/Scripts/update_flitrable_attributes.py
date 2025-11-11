import os
from pathlib import Path
from dotenv import load_dotenv
import meilisearch

# ✅ Localiser le fichier .env dans le dossier parent
env_path = Path(__file__).resolve().parents[2] / ".env"
print(f"🔍 Loading .env from: {env_path}")

# ✅ Charger le .env
load_dotenv(dotenv_path=env_path, override=True)

# 🚨 Debug (temporaire)
print("➡️ MEILI_URL =", os.getenv("MEILI_URL"))
print("➡️ MEILI_MASTER_KEY =", os.getenv("MEILI_MASTER_KEY"))
print("➡️ INDEX_NAME =", os.getenv("INDEX_NAME"))

MEILI_URL = os.getenv("MEILI_URL")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")  # Assurez-vous que le nom de votre index est dans le .env

print("➡️ DEBUG MEILI_URL =", MEILI_URL)
print("➡️ DEBUG MEILI_MASTER_KEY =", MEILI_KEY)
print("➡️ DEBUG INDEX_NAME =", INDEX_NAME)

# 🔹 Connexion à MeiliSearch
client = meilisearch.Client(MEILI_URL, MEILI_KEY)

# 🔹 Récupérer l'index existant
try:
    index = client.get_index(INDEX_NAME)
    print(f"✅ Index '{INDEX_NAME}' trouvé.")
except meilisearch.errors.MeiliSearchAPIError as e:
    print(f"❌ Erreur lors de la récupération de l'index : {e}")
    exit()

# 🔹 Mettre à jour les attributs filtrables de l'index
index.update_filterable_attributes([
    "keyword", "extra_keyword", "date_doc",
    "denom_fallback_bce", "TVA",
    "admins_detectes", "denoms_fallback_bce_flat",
    "adresses_fallback_bce_flat"  # 👈 ici on ajoute le champ facetable
])

print(f"✅ Les attributs filtrables de l'index '{INDEX_NAME}' ont été mis à jour.")

# 🔹 Vérification de la mise à jour
settings = index.get_settings()
print(f"✅ Nouveaux paramètres de l'index : {settings['filterableAttributes']}")
