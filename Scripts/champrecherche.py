import re
import os
import streamlit as st
from dotenv import load_dotenv
import meilisearch
from datetime import datetime

# Chargement des variables d'environnement
load_dotenv()
MEILI_URL = os.getenv("MEILI_URL")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")

# Liste des mois de l'année en français
mois_fr = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre"
]

# Connexion à MeiliSearch
client = meilisearch.Client(MEILI_URL, MEILI_KEY)
index = client.index(INDEX_NAME)

# Nombre total de docs
stats = index.get_stats()
total_docs = stats.number_of_documents
st.write(f"📊 Total de documents dans l'index : {total_docs}")

# Pagination pour récupérer les documents
all_docs = []
offset = 0
limit = 2000

while True:
    docs_batch = index.get_documents({"limit": limit, "offset": offset}).results
    if not docs_batch:
        break
    all_docs.extend([dict(doc) for doc in docs_batch])
    offset += limit
    st.write(f"📥 Récupérés : {len(all_docs)}/{total_docs}")
    if len(all_docs) >= total_docs:
        break

st.write(f"✅ Documents récupérés : {len(all_docs)} / {total_docs}")

# --- Fonction de validation des formats de date ---
# je pense que l on va pouvoir supprimer cette fonction
def is_valid_date(date):
    """
    Vérifie les formats de date suivants :
    - DD/MM/YYYY
    - YYYY-MM-DD
    - JJ Mois YYYY (ex: 29 juillet 1947 ou 2 juillet 2023)
    """
    date_pattern_1 = r"\d{2}/\d{2}/\d{4}"  # ex: 29/07/1947
    date_pattern_2 = r"\d{4}-\d{2}-\d{2}"  # ex: 1947-07-29
    date_pattern_3 = r"\d{1,2}\s+[a-zA-Zéûîà]+\s+\d{4}"  # ex: 29 juillet 1947 (en français)

    if isinstance(date, str):
        if bool(re.match(date_pattern_1, date)) or bool(re.match(date_pattern_2, date)):
            return True
        elif bool(re.match(date_pattern_3, date)):
            try:
                normalized_date = date.lower()
                day, month, year = normalized_date.split()
                month = mois_fr.index(month) + 1  # Conversion du mois en numérique (1-12)
                normalized_date = f"{day} {month} {year}"
                datetime.strptime(normalized_date, "%d %m %Y")
                return True
            except ValueError:
                return False
    return False

def check_date(date):
    if isinstance(date, list):
        for d in date:
            if is_valid_date(d):
                return True
        return False
    return is_valid_date(date)

# --- Fonction de validation des champs ---
def is_valid_adresse(adresse):
    return isinstance(adresse, str) and adresse.strip() or (isinstance(adresse, list) and any(isinstance(a, str) and a.strip() for a in adresse))

def is_valid_extra_keyword(extra_keyword):
    return isinstance(extra_keyword, str) and extra_keyword.strip() or (isinstance(extra_keyword, list) and any(isinstance(k, str) and k.strip() for k in extra_keyword))

def is_valid_nom_trib_entreprise(nom_trib_entreprise):
    if isinstance(nom_trib_entreprise, str):
        return bool(nom_trib_entreprise.strip())
    if isinstance(nom_trib_entreprise, list):
        return any(isinstance(k, str) and k.strip() for k in nom_trib_entreprise)
    if isinstance(nom_trib_entreprise, dict):
        return any([
            _nonempty_str(nom_trib_entreprise.get("canonical", "")),
            _nonempty_str(nom_trib_entreprise.get("name", "")),
            any(_nonempty_str(alias) for alias in nom_trib_entreprise.get("aliases", []))
        ])
    return False
# --- Fonction de validation pour le nom interdit ---
def is_valid_nom_interdit(nom_interdit):
    """
    Valide le champ "nom_interdit"
    """
    return isinstance(nom_interdit, str) and nom_interdit.strip()


def is_valid_admin(administrateur):
    return isinstance(administrateur, str) and administrateur.strip() or (isinstance(administrateur, list) and any(isinstance(ad, str) and ad.strip() for ad in administrateur))


def _nonempty_str(x):
    return isinstance(x, str) and x.strip()


def is_valid_nom(nom):
    # ancien format: str / list
    if _nonempty_str(nom):
        return True
    if isinstance(nom, list):
        return any(_nonempty_str(no) for no in nom)

    # nouveau format: dict avec {records, canonicals, aliases_flat}
    if isinstance(nom, dict):
        can = nom.get("canonicals") or []
        rec = nom.get("records") or []
        ali = nom.get("aliases_flat") or []
        has_can = any(_nonempty_str(c) for c in can)
        has_rec = any(_nonempty_str(r.get("canonical", "")) for r in rec if isinstance(r, dict))
        has_ali = any(_nonempty_str(a) for a in ali)
        return has_can or has_rec or has_ali

    return False


def is_valid_num_nat(num_nat):
    if isinstance(num_nat, str):
        return bool(num_nat.strip())
    if isinstance(num_nat, list):
        return any(isinstance(x, str) and x.strip() for x in num_nat)
    return False


# --- Fonction d'affichage des résultats ---
def show_results(docs, label):
    st.subheader(f"📋 {label}")
    for doc in docs[:1300]:  # Afficher un maximum de 5 documents
        st.write(f"ID: {doc.get('id')} | Texte: {repr(doc.get('text'))[:1000]}...")

# --- Classification des documents ---
docs_avec_adresse = []
docs_sans_adresse = []
docs_avec_extra_keyword = []
docs_sans_extra_keyword = []
docs_avec_admin = []
docs_sans_admin = []
docs_avec_nom = []
docs_sans_nom = []
docs_avec_num_nat = []
docs_sans_num_nat = []
docs_avec_date_naissance = []
docs_sans_date_naissance = []
docs_avec_date_jugement = []
docs_sans_date_jugement = []
docs_avec_nom_trib_entreprise = []
docs_sans_nom_trib_entreprise = []
docs_avec_date_deces = []
docs_sans_date_deces = []
docs_avec_nom_interdit = []
docs_sans_nom_interdit = []

for doc in all_docs:
    adresse = doc.get("adresse")
    extra_keyword = doc.get("extra_keyword")
    administrateur = doc.get("administrateur")
    nom = doc.get("nom")
    num_nat = doc.get("num_nat")
    date_naissance = doc.get("date_naissance")
    date_jugement = doc.get("date_jugement")
    nom_trib_entreprise = doc.get("nom_trib_entreprise")
    date_deces = doc.get("date_deces")
    nom_interdit = doc.get("nom_interdit")

    # Vérifications sur les différents champs
    if is_valid_adresse(adresse):
        docs_avec_adresse.append(doc)
    else:
        docs_sans_adresse.append(doc)

    if is_valid_extra_keyword(extra_keyword):
        docs_avec_extra_keyword.append(doc)
    else:
        docs_sans_extra_keyword.append(doc)

    if is_valid_admin(administrateur):
        docs_avec_admin.append(doc)
    else:
        docs_sans_admin.append(doc)

    if is_valid_nom(nom):
        docs_avec_nom.append(doc)
    else:
        docs_sans_nom.append(doc)

    if is_valid_num_nat(num_nat):
        docs_avec_num_nat.append(doc)
    else:
        docs_sans_num_nat.append(doc)

    if check_date(date_naissance):
        docs_avec_date_naissance.append(doc)
    else:
        docs_sans_date_naissance.append(doc)

    if is_valid_date(date_jugement):
        docs_avec_date_jugement.append(doc)
    else:
        docs_sans_date_jugement.append(doc)

    if is_valid_nom_trib_entreprise(nom_trib_entreprise):
        docs_avec_nom_trib_entreprise.append(doc)
    else:
        docs_sans_nom_trib_entreprise.append(doc)

    if check_date(date_deces):
        docs_avec_date_deces.append(doc)
    else:
        docs_sans_date_deces.append(doc)

    if is_valid_nom_interdit(nom_interdit):
        docs_avec_nom_interdit.append(doc)
    else:
        docs_sans_nom_interdit.append(doc)

# --- Résumé des documents ---
st.subheader("📊 Récapitulatif des documents")
st.markdown(f"Documents avec adresse : {len(docs_avec_adresse)} <span style='color: green;'>S JP</span>", unsafe_allow_html=True)
st.markdown(f"Documents sans adresse : {len(docs_sans_adresse)} <span style='color: green;'>S JP</span>", unsafe_allow_html=True)
st.markdown(f"Documents avec extra_keyword : {len(docs_avec_extra_keyword)} <span style='color: green;'>  S JP</span>", unsafe_allow_html=True)
st.markdown(f"Documents sans extra_keyword : {len(docs_sans_extra_keyword)} <span style='color: green;'>  S JP</span>", unsafe_allow_html=True)
st.markdown(f"Documents avec administrateur : {len(docs_avec_admin)} <span style='color: green;'>  - JP</span>", unsafe_allow_html=True)
st.markdown(f"Documents sans administrateur : {len(docs_sans_admin)} <span style='color: green;'>  - JP</span>", unsafe_allow_html=True)
st.markdown(f"Documents avec nom : {len(docs_avec_nom)} <span style='color: green;'>S JP</span>", unsafe_allow_html=True)
st.markdown(f"Documents sans nom : {len(docs_sans_nom)} <span style='color: green;'>S JP</span>", unsafe_allow_html=True)
st.markdown(f"Documents avec numéro national : {len(docs_avec_num_nat)} <span style='color: green;'>  - JP</span>", unsafe_allow_html=True)
st.markdown(f"Documents sans numéro national : {len(docs_sans_num_nat)} <span style='color: green;'>  - JP</span>", unsafe_allow_html=True)
st.markdown(f"Documents avec date de naissance : {len(docs_avec_date_naissance)} <span style='color: green;'>  S JP</span>", unsafe_allow_html=True)
st.markdown(f"Documents sans date de naissance : {len(docs_sans_date_naissance)} <span style='color: green;'>  S JP</span>", unsafe_allow_html=True)
st.markdown(f"Documents avec date de jugement : {len(docs_avec_date_jugement)} <span style='color: green;'>  -  JP</span>", unsafe_allow_html=True)
st.markdown(f"Documents sans date de jugement : {len(docs_sans_date_jugement)} <span style='color: green;'>  - JP</span>", unsafe_allow_html=True)
st.markdown(f"Documents avec nom tribunal entreprise : {len(docs_avec_nom_trib_entreprise)} <span style='color: green;'>  -  -</span>", unsafe_allow_html=True)
st.markdown(f"Documents sans nom tribunal entreprise : {len(docs_sans_nom_trib_entreprise)} <span style='color: green;'>  -  -</span>", unsafe_allow_html=True)
st.markdown(f"Documents avec date de décès : {len(docs_avec_date_deces)} <span style='color: green;'>  S  -</span>", unsafe_allow_html=True)
st.markdown(f"Documents sans date de décès : {len(docs_sans_date_deces)} <span style='color: green;'>  S  -</span>", unsafe_allow_html=True)
st.markdown(f"Documents avec nom interdit : {len(docs_avec_nom_interdit)} <span style='color: green;'>  -  ?</span>", unsafe_allow_html=True)
st.markdown(f"Documents sans nom interdit : {len(docs_sans_nom_interdit)} <span style='color: green;'>  -  ?</span>", unsafe_allow_html=True)

# --- Documents sans adresse MAIS contenant "domicilié" ---
docs_sans_adresse_avec_domicilie = [
    doc for doc in docs_sans_adresse
    if re.search(r"domicili", doc.get("text", ""), flags=re.IGNORECASE)
]
# --- Documents sans adresse MAIS contenant "résidence" ---
docs_sans_adresse_avec_residence = [
    doc for doc in docs_sans_adresse
    if re.search(r"residence", doc.get("text", ""), flags=re.IGNORECASE)
]

docs_sans_adresse_avec_radie = [
    doc for doc in docs_sans_adresse
    if re.search(r"radié", doc.get("text", ""), flags=re.IGNORECASE)
]



st.subheader("📋 Documents SANS adresse mais contenant 'domicilié'")
for doc in docs_sans_adresse_avec_domicilie[:500]:  # limiter l'affichage
    st.write(f"ID: {doc.get('id')} | Texte: {repr(doc.get('text'))[:800]}...")

st.subheader("📋 Documents SANS adresse mais contenant 'residence'")
for doc in docs_sans_adresse_avec_residence[:500]:  # limiter l'affichage
    st.write(f"ID: {doc.get('id')} | Texte: {repr(doc.get('text'))[:800]}...")

st.subheader("📋 Documents SANS adresse mais contenant 'radié")
for doc in docs_sans_adresse_avec_radie[:500]:  # limiter l'affichage
    st.write(f"ID: {doc.get('id')} | Texte: {repr(doc.get('text'))[:800]}...")


# --- Exemples ---
show_results(docs_sans_date_naissance, "Documents SANS date de naissance")
show_results(docs_sans_date_deces, "Documents SANS date de décès")
show_results(docs_sans_adresse, "Documents SANS adresse")
show_results(docs_avec_num_nat, "Documents AVEC num_nat")
show_results(docs_sans_num_nat, "Documents SANS num_nat")
show_results(docs_sans_nom, "Documents SANS nom")
show_results(docs_avec_nom, "Documents AVEC nom")
show_results(docs_sans_admin, "Documents SANS admin")
show_results(docs_avec_nom_trib_entreprise, "Documents AVEC nom trib entreprise")


# --- Recherche spécifique pour "liquidateur" ---
motifs = re.compile(r"\bliquidateur(s|\(s\))?\b", re.IGNORECASE)
docs_sans_admin_avec_mention_liquidateur = [doc for doc in docs_sans_admin if motifs.search(doc.get("text", ""))]


#st.subheader("🔍 Recherche pour 'liquidateur' dans les documents sans administrateur")
#for doc in docs_sans_admin_avec_mention_liquidateur[:100]:  # Afficher jusqu'à 100 résultats
    #st.write(f"ID: {doc.get('id')} | Texte: {repr(doc.get('text'))[:600]}...")

# --- Liste des documents avec administrateur et nom ---
def print_docs_avec_administrateur_et_nom(docs):
    st.subheader("📋 Liste des documents AVEC administrateur:")
    for doc in docs:
        st.write(f"- ID: {doc.get('id')} | administrateur: {doc.get('administrateur')}")

def print_docs_sans_administrateur_et_nom(docs):
    st.subheader("📋 Liste des documents SANS administrateur:")
    for doc in docs:
        st.write(f"- ID: {doc.get('id')} | Texte: {repr(doc.get('text'))[:1200]}...")

def print_docs_avec_adresse(docs):
    st.subheader("📋 Liste des documents AVEC adresse:")
    for doc in docs:
        st.write(f"- ID: {doc.get('id')} | adresse: {doc.get('adresse')}")

def print_docs_avec_nom(docs):
    st.subheader("📋 Liste des documents AVEC nom:")
    for doc in docs:
        st.write(f"- ID: {doc.get('id')} | nom: {doc.get('nom')}")

def print_docs_sans_nom(docs):
    st.subheader("📋 Liste des documents SANS nom:")
    for doc in docs:
        st.write(f"- ID: {doc.get('id')} | Texte: {repr(doc.get('text'))[:1200]}...")


def print_docs_avec_nom_trib_entreprise(docs):
    st.subheader("📋 Liste des documents AVEC nom_trib_entreprise :")
    for doc in docs:
        nom_tri = doc.get("nom_trib_entreprise")
        doc_id = doc.get("id")
        texte = doc.get("text", "")

        # Si c’est une liste → joindre les noms
        if isinstance(nom_tri, list):
            nom_tri_str = ", ".join(n.strip() for n in nom_tri if isinstance(n, str) and n.strip())
        else:
            nom_tri_str = str(nom_tri).strip() if nom_tri else ""

        st.write(f"- ID: {doc_id} | nom_trib_entreprise: {nom_tri_str}")


def print_docs_sans_num_nat(docs):
    st.subheader("📋 Liste des documents SANS num_nat :")
    for doc in docs:
        st.write(f"- ID: {doc.get('id')} | Texte: {repr(doc.get('text'))[:600]}...")

def print_docs_avec_num_nat(docs):
    st.subheader("📋 Liste des documents AVEC num_nat :")
    for doc in docs:
        st.write(f"- ID: {doc.get('id')} | Texte: {repr(doc.get('text'))[:600]}...")
# --- Liste des documents SANS date de décès ---
def print_docs_sans_date_deces(docs):
    st.subheader("📋 Liste des documents SANS date de décès :")
    for doc in docs:
        st.write(f"- ID: {doc.get('id')} | Texte: {repr(doc.get('text'))[:600]}...")

def print_docs_avec_date_naissance(docs):
    st.subheader("📋 Liste des documents AVEC date de naissance :")
    for doc in docs:
        st.write(f"- ID: {doc.get('id')} | Texte: {repr(doc.get('text'))[:600]}...|date de naissance: {doc.get('date_naissance')}")

def print_docs_sans_extra_keyword(docs):
    st.subheader("📋 Liste des documents SANS extra_keyword :")
    for doc in docs:
        st.write(f"- ID: {doc.get('id')} | Texte: {repr(doc.get('text'))[:600]}...")


def print_docs_avec_extra_keyword(docs):
    st.subheader("📋 Liste des documents AVEC extra_keyword :")
    for doc in docs:
        st.write(f"- ID: {doc.get('id')} | Texte: {repr(doc.get('text'))[:1200]}...Extra_Keyword: {doc.get('extra_keyword')}")

def print_docs_sans_adresse(docs):
    st.subheader("📋 Liste des documents SANS adresse :")
    for doc in docs:
        st.write(f"- ID: {doc.get('id')} | Texte: {repr(doc.get('text'))[:600]}...")

# Affichage des exemples des documents SANS date de naissance et SANS date de décès
print_docs_sans_date_deces(docs_sans_date_deces)
print_docs_avec_administrateur_et_nom(docs_avec_admin)
print_docs_sans_administrateur_et_nom(docs_sans_admin)
print_docs_sans_num_nat(docs_sans_num_nat)
print_docs_avec_num_nat(docs_avec_num_nat)
print_docs_sans_administrateur_et_nom(docs_sans_admin)
print_docs_sans_adresse(docs_sans_adresse)
print_docs_avec_adresse(docs_avec_adresse)
print_docs_sans_extra_keyword(docs_sans_extra_keyword)
print_docs_avec_extra_keyword(docs_avec_extra_keyword)
print_docs_avec_nom(docs_avec_nom)
print_docs_sans_nom(docs_sans_nom)
print_docs_avec_date_naissance(docs_avec_date_naissance)
print_docs_avec_nom_trib_entreprise(docs_avec_nom_trib_entreprise)




# --- Instructions supplémentaires ---
st.subheader("📝 Instructions supplémentaires")
st.write("""
**Mot clef succession à vérifier :**
- nom
- date_deces
- date_naissance
- adresse
- extra_keyword
- NA :
  - TVA
  - nom_trib_entreprise
  - num_nat
  - administrateur
  - nom_interdit
  - extra_links
  _ date_jugement (même si il y en a une le jugement est pas publié)
- NA ALL THE TIME :
""")
