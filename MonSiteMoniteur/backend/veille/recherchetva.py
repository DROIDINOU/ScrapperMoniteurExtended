from meilisearch import Client
from django.conf import settings

# --------------------------------------------------
# Connexion à Meilisearch (clé + URL depuis settings.py)
# --------------------------------------------------
client = Client(
    settings.MEILI_URL,          # http://127.0.0.1:7700
    settings.MEILI_MASTER_KEY    # Jamesbond007colibri+
)

# ⚠️ Ne jamais modifier directement dans les templates
index = client.index(settings.INDEX_NAME)

# Définition des séparateurs (avec le + inclut)
new_separators = [
    " ", "\t", "\n", ",", ";", "-", "_", "(", ")", "[", "]", "{", "}",
    ":", "/", "\\", "?", "!", "@", "#", "$", "%", "&", "*", "+", "=",
    "<", ">", "|", "~", "`", "^"
]

index.update_separator_tokens(new_separators)

print("✅ Config Meilisearch appliquée : séparateurs mis à jour")
