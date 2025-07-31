from meilisearch import Client

client = Client('http://127.0.0.1:7700')  # mets l'URL de prod ici si besoin

# Nouvelle config sans "."
new_separators = [" ", "\t", "\n", ",", ";", "-", "_", "(", ")", "[", "]", "{", "}", ":", "/", "\\", "?", "!", "@", "#", "$", "%", "&", "*", "+", "=", "<", ">", "|", "~", "`", "^"]

client.index('moniteur_docs').update_separator_tokens(new_separators)