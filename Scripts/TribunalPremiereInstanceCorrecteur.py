import os
import re
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
import meilisearch

# ------------------------------------------------------------------------------
# Config & Connexion Meili
# ------------------------------------------------------------------------------
load_dotenv()
MEILI_URL = os.getenv("MEILI_URL", "").strip()
MEILI_KEY = os.getenv("MEILI_MASTER_KEY", "").strip()
INDEX_NAME = os.getenv("INDEX_NAME", "").strip()

if not MEILI_URL or not MEILI_KEY or not INDEX_NAME:
    st.error("⚠️ MEILI_URL, MEILI_MASTER_KEY ou INDEX_NAME manquant(s) dans l'environnement.")
    st.stop()

client = meilisearch.Client(MEILI_URL, MEILI_KEY)
index = client.index(INDEX_NAME)

# ------------------------------------------------------------------------------
# Utilitaires de nettoyage (champ nom / adresse / date_deces)
# ------------------------------------------------------------------------------
MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre"
]
MAITRE_PREFIX_RE = re.compile(r"(?i)^(?:par\s+)?(?:ma[îi]tre|me)\s+")
WS_RE = re.compile(r"\s+")

def _norm_ws(s: str) -> str:
    return WS_RE.sub(" ", s).strip() if isinstance(s, str) else s

def strip_maitre_prefix(s: str) -> str:
    if not isinstance(s, str):
        return s
    return _norm_ws(MAITRE_PREFIX_RE.sub("", s))

RE_LAST_FIRST = re.compile(
    r"^\s*(?P<last>[A-ZÉÈÀÂÊÎÔÛÇ'’\-]+(?:\s+[A-ZÉÈÀÂÊÎÔÛÇ'’\-]+){0,2})\s+"
    r"(?P<first>[A-Z][a-zà-öø-ÿ'’\-]+(?:\s+[A-Z][a-zà-öø-ÿ'’\-]+)*)\s*$"
)

def reorder_last_first_if_upper(s: str) -> str:
    """Optionnel: COLLART Luc -> Luc COLLART (si 'last' est en MAJ). Non utilisé par défaut."""
    if not isinstance(s, str):
        return s
    m = RE_LAST_FIRST.match(s)
    if not m:
        return _norm_ws(s)
    last = m.group("last")
    first = m.group("first")
    # Evite de toucher aux adresses (RUE, AVENUE, ...)
    if last.split()[0] in {"RUE", "AVENUE", "BOULEVARD", "PLACE", "CHEMIN", "IMPASSE"}:
        return _norm_ws(s)
    return f"{first} {last}"

def normalize_date_fr_to_iso(d: str) -> str | None:
    """Retourne 'YYYY-MM-DD' si possible, sinon None."""
    if not isinstance(d, str):
        return None
    s = d.strip()

    # DD/MM/YYYY
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$", s)
    if m:
        try:
            day, month, year = map(int, m.groups())
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    # YYYY-MM-DD
    m = re.match(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*$", s)
    if m:
        try:
            year, month, day = map(int, m.groups())
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    # JJ Mois YYYY (fr)
    m = re.match(r"^\s*(\d{1,2})\s+([A-Za-zéûîàôùç]+)\s+(\d{4})\s*$", s)
    if m:
        day, month_name, year = m.groups()
        try:
            idx = MOIS_FR.index(month_name.lower()) + 1
            return datetime(int(year), idx, int(day)).strftime("%Y-%m-%d")
        except (ValueError, IndexError):
            return None

    return None

def is_empty(value) -> bool:
    """True si None, '', [], ou liste de strings vides."""
    if value is None:
        return True
    if isinstance(value, str):
        return len(value.strip()) == 0
    if isinstance(value, list):
        return all((not isinstance(x, str)) or (len(x.strip()) == 0) for x in value)
    return False

# ------------------------------------------------------------------------------
# Sidebar / contrôles
# ------------------------------------------------------------------------------
st.set_page_config(page_title="Complétion Meili: nom / adresse / date_deces", layout="wide")
st.title("🧩 Complétion Meili — nom / adresse / date_deces")

with st.sidebar:
    st.header("Paramètres")
    page_size = st.number_input("Taille de page", min_value=50, max_value=5000, value=500, step=50)
    page = st.number_input("Page", min_value=1, value=1, step=1)
    apply_clean_maitre = st.checkbox("Nettoyer les préfixes (Maître / Me / par Maître)", value=True)
    apply_date_iso = st.checkbox("Normaliser la date_deces en YYYY-MM-DD", value=True)
    show_text_len = st.slider("Longueur extrait texte", 100, 2000, 600, 50)

# ------------------------------------------------------------------------------
# Récupération des documents (seulement les champs utiles)
# ------------------------------------------------------------------------------
params = {"limit": int(page_size), "offset": int(page_size) * (int(page) - 1), "fields": ["id", "nom", "adresse", "date_deces", "text"]}
docs_batch = index.get_documents(params).results if hasattr(index.get_documents(params), "results") else index.get_documents(params)

if not docs_batch:
    st.info("Aucun document pour cette page.")
    st.stop()

docs = [dict(d) for d in docs_batch]

# ------------------------------------------------------------------------------
# 1) Tableau récap (id, nom, adresse, date_deces)
# ------------------------------------------------------------------------------
st.subheader("📋 Vue d’ensemble (id, nom, adresse, date_deces)")
def _fmt(v):
    if isinstance(v, list):
        return " | ".join([x for x in v if isinstance(x, str)])
    return v

st.dataframe(
    [
        {
            "id": d.get("id"),
            "nom": _fmt(d.get("nom")),
            "adresse": _fmt(d.get("adresse")),
            "date_deces": _fmt(d.get("date_deces")),
        }
        for d in docs
    ],
    use_container_width=True,
)

# ------------------------------------------------------------------------------
# 2) Edition des champs vides (au moins un vide parmi nom/adresse/date_deces)
# ------------------------------------------------------------------------------
st.subheader("✏️ Compléter les champs vides")

empties = []
for d in docs:
    if any([
        is_empty(d.get("nom")),
        is_empty(d.get("adresse")),
        is_empty(d.get("date_deces")),
    ]):
        empties.append(d)

st.caption(f"{len(empties)} document(s) avec au moins un champ vide parmi nom/adresse/date_deces.")

def preview_text(s: str, n=600) -> str:
    if not isinstance(s, str):
        return ""
    s = s.replace("\n", " ")
    return (s[:n] + "…") if len(s) > n else s

for d in empties:
    doc_id = d.get("id")
    col = st.container()
    with col:
        st.markdown("---")
        st.markdown(f"**ID:** `{doc_id}`")
        st.write(preview_text(d.get("text", ""), show_text_len))

        with st.form(key=f"form_{doc_id}", clear_on_submit=False):
            c1, c2, c3 = st.columns(3)
            nom_val = "" if is_empty(d.get("nom")) else (_fmt(d.get("nom")) or "")
            adr_val = "" if is_empty(d.get("adresse")) else (_fmt(d.get("adresse")) or "")
            dec_val = "" if is_empty(d.get("date_deces")) else (_fmt(d.get("date_deces")) or "")

            new_nom = c1.text_input("nom (laisser vide pour ne pas modifier)", value=nom_val)
            new_adr = c2.text_area("adresse (laisser vide pour ne pas modifier)", value=adr_val, height=80)
            new_dec = c3.text_input("date_deces (YYYY-MM-DD ou fr)", value=dec_val)

            submitted = st.form_submit_button("💾 Mettre à jour ce document")
            if submitted:
                payload = {"id": doc_id}
                # Nettoyage/normalisation si demandé
                if new_nom.strip():
                    nom_clean = strip_maitre_prefix(new_nom) if apply_clean_maitre else _norm_ws(new_nom)
                    # si tu veux activer l'inversion NOM/Prénom en maj, décommente la ligne suivante :
                    # nom_clean = reorder_last_first_if_upper(nom_clean)
                    payload["nom"] = _norm_ws(nom_clean)

                if new_adr.strip():
                    adr_clean = strip_maitre_prefix(new_adr) if apply_clean_maitre else _norm_ws(new_adr)
                    payload["adresse"] = _norm_ws(adr_clean)

                if new_dec.strip():
                    if apply_date_iso:
                        iso = normalize_date_fr_to_iso(new_dec)
                        payload["date_deces"] = iso if iso else _norm_ws(new_dec)
                    else:
                        payload["date_deces"] = _norm_ws(new_dec)

                if len(payload.keys()) == 1:
                    st.warning("Aucune modification à envoyer (tous les champs sont vides).")
                else:
                    try:
                        resp = index.update_documents([payload])
                        # Gestion des différentes versions de client Meili
                        task_uid = getattr(resp, "taskUid", None) or resp.get("taskUid") if isinstance(resp, dict) else None
                        update_id = getattr(resp, "updateId", None) or resp.get("updateId") if isinstance(resp, dict) else None
                        st.success(f"Mise à jour envoyée ✅ (taskUid={task_uid or update_id})")
                    except Exception as e:
                        st.error(f"Erreur lors de la mise à jour: {e}")

# ------------------------------------------------------------------------------
# Astuces
# ------------------------------------------------------------------------------
with st.expander("ℹ️ Astuces"):
    st.markdown("""
- Les champs vides (ou listes vides) sont détectés dans **nom**, **adresse**, **date_deces**.
- Le bouton **Mettre à jour** n’envoie **que les champs saisis** (les autres ne sont pas modifiés).
- Coche **“Nettoyer les préfixes”** pour enlever *Maître / Me / par Maître*.
- Coche **“Normaliser la date_deces”** pour tenter un format **YYYY-MM-DD**.
- Ajuste la **taille de page** et la **page** dans la barre latérale.
""")
