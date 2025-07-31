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

print(f"L'index '{index_name}' a été supprimé définitivement.")
