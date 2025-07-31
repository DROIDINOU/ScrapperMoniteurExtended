import meilisearch
import re

client = meilisearch.Client("http://127.0.0.1:7700", 'TBVEHV1dBQBT7mVQpHXw2RXeICzQvONQ5p9CqI84gF4')
index = client.index("moniteur_documents")

# Récupère jusqu'à 1000 documents
result = index.search("", {"limit": 1000})

# Listes distinctes
ids_sans_admin_ni_motcle = []
ids_sans_extra_keywords = []

# Mots-clés à exclure du texte
mot_cles = ["administrateur", "liquidateur", "liquidatrice", "administratrice", "Maître", "Ouverture", "clôture", "Homologation du plan"]
pattern = re.compile(r"\b(" + "|".join(mot_cles) + r")\b", flags=re.IGNORECASE)

for doc in result["hits"]:
    doc_id = doc.get("id", "(id inconnu)")
    champ_admin = doc.get("administrateur")
    champ_text = doc.get("text", "")
    extra_keywords = doc.get("extra_keyword")

    # Condition 1 : sans admin ET sans mots-clés dans le texte
    if champ_admin in [None, "", [], {}] and not pattern.search(champ_text):
        ids_sans_admin_ni_motcle.append(doc_id)

    # Condition 2 : sans extra_keywords
    if not extra_keywords:  # None, "", or empty list
        ids_sans_extra_keywords.append(doc_id)

# 🔍 Affichage des résultats

print("📄 Documents SANS champ 'administrateur' ET SANS mot-clé dans 'text' :\n")
for doc_id in ids_sans_admin_ni_motcle:
    print(f"- {doc_id}")
print(f"\n📄 Total : {len(ids_sans_admin_ni_motcle)}\n")

print("📄 Documents SANS champ 'extra_keywords' :\n")
for doc_id in ids_sans_extra_keywords:
    print(f"- {doc_id}")
print(f"\n📄 Total : {len(ids_sans_extra_keywords)}")
