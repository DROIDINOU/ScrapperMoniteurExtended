r"""
from meilisearch import Client

# Connexion à Meilisearch
client = Client("http://127.0.0.1:7700")

# Nom de ton index
index_name = "moniteur_documents"

# Récupération de l'index
index = client.get_index(index_name)

# Suppression complète de l'index
response = index.delete()

print("Suppression de l'index lancée. Task UID:", response.task_uid)

# Attendre la fin de la tâche
client.wait_for_task(response.task_uid)

print(f"L'index '{index_name}' a été supprimé définitivement.")"""

import meilisearch

# Connecte-toi à MeiliSearch
client = meilisearch.Client("http://127.0.0.1:7700")

# Accède à l'index
index = client.get_index('moniteur_documents')

# Recherche tous les documents où le champ 'date' est vide
result = index.search("", filters="date=''", attributes_to_retrieve=['id', 'date'])

# Récupérer les ids des documents avec une date vide
documents_with_empty_date = [doc['id'] for doc in result['hits']]

# Afficher les ids récupérés
print(f"ID des documents avec 'date' vide : {documents_with_empty_date}")

