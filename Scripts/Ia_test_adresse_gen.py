#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import re
import json
from typing import Optional, List
from dotenv import load_dotenv

from groq import Groq
import meilisearch

from Utilitaire.outils.MesOutils import chemin_log

# ------------------------------------------------------------------------------
# ENV
# ------------------------------------------------------------------------------
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MEILI_URL = os.getenv("MEILI_URL")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")

# ------------------------------------------------------------------------------
# Clients
# ------------------------------------------------------------------------------
groq_client = Groq(api_key=GROQ_API_KEY)
meili_client = meilisearch.Client(MEILI_URL, MEILI_KEY)
index = meili_client.get_index(INDEX_NAME)

# ------------------------------------------------------------------------------
# Prompt IA
# ------------------------------------------------------------------------------
MODEL = "llama3-70b-8192"
PROMPT_TEMPLATE = """
Tu es un assistant qui lit un texte juridique. On t'indique un extrait d'adresse partiel (code postal + commune), et tu dois retrouver l'adresse complète correspondante dans le texte ci-dessous.

DOC_ID = "{doc_id}"
EXTRAIT_ADRESSE = "{adresse}"
TEXTE = \"\"\"{texte}\"\"\"

Réponds uniquement avec l'adresse complète trouvée, ou "inconnue" si rien de clair.
"""

def construire_prompt(doc_id: str, adresse: str, texte: str) -> str:
    return PROMPT_TEMPLATE.format(doc_id=doc_id, adresse=adresse, texte=texte)

def find_address_completion(doc_id: str, adresse: str, texte: str) -> Optional[str]:
    prompt = construire_prompt(doc_id, adresse, texte)
    try:
        resp = groq_client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        out = (resp.choices[0].message.content or "").strip()
        return out
    except Exception as e:
        print(f"❌ Erreur Groq (doc_id={doc_id}): {e}")
        return None

# ------------------------------------------------------------------------------
# Utils Meili
# ------------------------------------------------------------------------------
def _as_list(v) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [x for x in v if isinstance(x, str)]
    if isinstance(v, str) and v.strip():
        return [v.strip()]
    return []

def _norm_addr(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def doc_has_address_covering_partial(doc_id: str, partial: str) -> bool:
    """Très tolérant: si une adresse du doc contient le fragment partiel (normalisé), on considère couvert."""
    try:
        doc = dict(index.get_document(doc_id))
    except Exception:
        return False
    partial_n = _norm_addr(partial).lower()
    for a in _as_list(doc.get("adresse")):
        if partial_n and partial_n in _norm_addr(a).lower():
            return True
    return False

def upsert_address_in_meili(doc_id: str, new_address: str) -> bool:
    try:
        doc = dict(index.get_document(doc_id))
    except Exception as e:
        print(f"❌ Impossible de récupérer le document {doc_id} dans Meili: {e}")
        return False

    current = _as_list(doc.get("adresse"))
    current_norm = {_norm_addr(a) for a in current if a}

    candidate = _norm_addr(new_address)
    if not candidate or candidate.lower() == "inconnue":
        print("↪️ IA a répondu 'inconnue' ou vide : pas d'update.")
        return False

    if candidate in current_norm:
        print("↪️ Adresse déjà présente, pas d'update.")
        return False

    updated_list = current + [candidate]
    payload = {"id": doc_id, "adresse": updated_list}

    try:
        task = index.update_documents([payload])
        print(f"✅ Meili mis à jour (taskUid={getattr(task, 'task_uid', None) or getattr(task, 'updateId', None)})")
        return True
    except Exception as e:
        print(f"❌ Erreur update Meili (doc_id={doc_id}): {e}")
        return False

# ------------------------------------------------------------------------------
# Parsing log
# ------------------------------------------------------------------------------
LOG_BLOCK_RX = re.compile(
    r"DOC ID:\s*'(?P<doc_id>[a-f0-9]{64})'.*?"
    r"Adresse incomplète ou suspecte\s*:\s*'(?P<adresse>[^']+)'.*?"
    r"(?:Texte|texte)\s*[:=]\s*(?P<texte>.+?)(?=\n\S|\Z)",
    re.DOTALL | re.IGNORECASE
)

def load_cache(cache_path: str) -> dict:
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache_path: str, cache: dict) -> None:
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Impossible d’écrire le cache: {e}")

def make_key(doc_id: str, partial: str) -> str:
    return f"{doc_id}||{_norm_addr(partial).lower()}"

def process_log_file(log_file_name: str = "succession.log"):
    full_path = chemin_log(log_file_name)
    print(f"📂 Fichier log : {full_path}")

    if not os.path.exists(full_path):
        print(f"❌ Fichier introuvable : {full_path}")
        return

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = LOG_BLOCK_RX.findall(content)
    print(f"🔍 {len(blocks)} bloc(s) détecté(s)")

    # Cache persistant à côté du log
    cache_path = os.path.join(os.path.dirname(full_path), "ia_addr_cache.json")
    cache = load_cache(cache_path)

    # Dédoublonnage in-memory pour cette exécution
    seen_pairs = set()

    for doc_id, adresse_partielle, texte in blocks:
        adresse_partielle = adresse_partielle.strip()
        texte = texte.strip()
        key = make_key(doc_id, adresse_partielle)

        print("\n" + "-"*80)
        print(f"📄 DOC ID : {doc_id}")
        print(f"🔍 Adresse partielle : {adresse_partielle}")

        # 1) Skip si déjà traité dans cette exécution
        if key in seen_pairs:
            print("⏭️ Déjà vu dans ce run → skip IA.")
            continue

        # 2) Skip si déjà dans le cache persistant
        if key in cache:
            print(f"⏭️ Déjà en cache → {cache[key]!r}")
            # on tente aussi l’upsert si nécessaire
            if cache[key] and cache[key].lower() != "inconnue":
                upsert_address_in_meili(doc_id, cache[key])
            seen_pairs.add(key)
            continue

        # 3) Skip si Meili contient déjà une adresse couvrant le fragment partiel
        if doc_has_address_covering_partial(doc_id, adresse_partielle):
            print("⏭️ Doc contient déjà une adresse couvrant le fragment → skip IA.")
            seen_pairs.add(key)
            cache[key] = ""  # on note comme traité sans appel IA
            continue

        print("🧠 IA (Groq) en cours...")
        completion = find_address_completion(doc_id, adresse_partielle, texte)
        if completion is None:
            print("⚠️ Erreur IA → on passe.")
            seen_pairs.add(key)
            cache[key] = None
            continue

        print(f"🤖 IA propose : {completion}")
        cache[key] = completion  # on mémorise la proposition

        updated = upsert_address_in_meili(doc_id, completion)
        if updated:
            print(f"💾 Ajouté à Meili pour {doc_id} : {completion}")
        else:
            print("ℹ️ Pas de mise à jour.")

        seen_pairs.add(key)
        save_cache(cache_path, cache)  # flush régulier

    # Sauvegarde finale
    save_cache(cache_path, cache)

# ------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    log_name = sys.argv[1] if len(sys.argv) > 1 else "succession.log"
    process_log_file(log_name)
