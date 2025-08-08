# --- Imports standards ---
import re
import os
# --- Bibliothèques tierces ---
from dotenv import load_dotenv
import meilisearch

# --- Chargement des variables d'environnement ---
load_dotenv()
MEILI_URL = os.getenv("MEILI_URL")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")

# Connexion à MeiliSearch
client = meilisearch.Client(MEILI_URL, MEILI_KEY)
index = client.index(INDEX_NAME)

# Nombre total de docs
stats = index.get_stats()
total_docs = stats.number_of_documents
print(f"📊 Total de documents dans l'index : {total_docs}")

# Pagination
all_docs = []
offset = 0
limit = 2000

while True:
    docs_batch = index.get_documents({"limit": limit, "offset": offset}).results
    if not docs_batch:
        break
    all_docs.extend([dict(doc) for doc in docs_batch])
    offset += limit
    print(f"📥 Récupérés : {len(all_docs)}/{total_docs}")
    if len(all_docs) >= total_docs:
        break

print(f"✅ Documents récupérés : {len(all_docs)} / {total_docs}")

# Classification
docs_avec_adresse = []
docs_sans_adresse = []
docs_avec_extra_keyword = []
docs_sans_extra_keyword = []
docs_avec_admin = []
docs_sans_admin = []
docs_avec_nom = []
docs_sans_nom = []


for doc in all_docs:
    adresse = doc.get("adresse")
    extra_keyword = doc.get("extra_keyword")
    administrateur = doc.get("administrateur")
    nom = doc.get("nom")

    has_adresse = (
        isinstance(adresse, str) and adresse.strip()
    ) or (
        isinstance(adresse, list) and any(isinstance(a, str) and a.strip() for a in adresse)
    )

    has_extra_keyword = (
        isinstance(extra_keyword, str) and extra_keyword.strip()
    ) or (
        isinstance(extra_keyword, list) and any(isinstance(k, str) and k.strip() for k in extra_keyword)
    )

    has_admin = (
        isinstance(administrateur, str) and administrateur.strip()
    ) or (
        isinstance(administrateur, list) and any(isinstance(ad, str) and ad.strip() for ad in administrateur)
    )

    has_nom = (
                        isinstance(nom, str) and nom.strip()
                ) or (
                        isinstance(nom, list) and any(
                    isinstance(no, str) and no.strip() for no in nom)
                )

    if has_adresse:
        docs_avec_adresse.append(doc)
    else:
        docs_sans_adresse.append(doc)

    if has_extra_keyword:
        docs_avec_extra_keyword.append(doc)
    else:
        docs_sans_extra_keyword.append(doc)

    if has_admin:
        docs_avec_admin.append(doc)
    else:
        docs_sans_admin.append(doc)

    if has_nom:
        docs_avec_nom.append(doc)
    else:
        docs_sans_nom.append(doc)

# 📊 Résumé
print("\n📊 Récapitulatif :")
print("Avec adresse :", len(docs_avec_adresse))
print("Sans adresse :", len(docs_sans_adresse))
print("Avec extra_keyword :", len(docs_avec_extra_keyword))
print("Sans extra_keyword :", len(docs_sans_extra_keyword))
print("Avec administrateur :", len(docs_avec_admin))
print("Sans administrateur :", len(docs_sans_admin))
print("Avec nom :", len(docs_avec_nom))
print("Sans nom :", len(docs_sans_nom))



# 🔍 Exemples
print("\n🔍 Exemples de documents SANS adresse :")
for doc in docs_sans_adresse[:10]:
    print(f"- ID: {doc.get('id')} | texte: {repr(doc.get('text'))[:250]}...")

print("\n🔍 Exemples de documents SANS extra_keyword :")
for doc in docs_sans_extra_keyword[:10]:
    print(f"- ID: {doc.get('id')} | texte: {repr(doc.get('text'))[:250]}...")

print("\n🔍 Exemples de documents SANS administrateur (contenant 'liquidateur') :")
for doc in [d for d in docs_sans_admin if re.search(r"\bliquidateur(s|\(s\))?\b", d.get("text", ""), flags=re.IGNORECASE)][:100]:
    print(f"- ID: {doc.get('id')} | titre: {doc.get('titre', '[Pas de titre]')} | texte: {repr(doc.get('text'))[:600]}...")

# 📋 Liste des documents AVEC administrateur
print("\n📋 Liste des documents SANS administrateur :")
for doc in docs_sans_admin:
    print(f"- ID: {doc.get('id')} | administrateur: {doc.get('administrateur')}")

print("\n📋 Liste des documents SANS administrateur :")
for doc in docs_avec_nom:
    print(f"- ID: {doc.get('id')} | nom: {doc.get('nom')}")



# 📋 Liste des documents AVEC administrateur
# print("\n📋 Liste des documents AVEC nom :")
# for doc in docs_avec_nom:
    # print(f"- ID: {doc.get('id')} | nom: {doc.get('nom')}| texte: {repr(doc.get('text'))[:600]}...")

# 📋 Liste des documents AVEC administrateur
# print("\n📋 Liste des documents SANS nom :")
# for doc in docs_sans_nom:
    # print(f"- ID: {doc.get('id')} | nom: {doc.get('nom')} | texte: {repr(doc.get('text'))[:300]}...")

print("\n🔍 Documents SANS administrateur mais contenant 'Maître', 'avocat' ou 'avocate' :")
motifs = re.compile(r"\b(ma[iî]tre|avocat(?:e)?)\b", re.IGNORECASE)

docs_sans_admin_avec_mention_avocat = [
    doc for doc in docs_sans_admin
    if motifs.search(doc.get("text", ""))
]

for doc in docs_sans_admin_avec_mention_avocat[:100]:  # Affiche jusqu'à 100 résultats
    print(f"- ID: {doc.get('id')} | texte: {repr(doc.get('text'))[:600]}...")

