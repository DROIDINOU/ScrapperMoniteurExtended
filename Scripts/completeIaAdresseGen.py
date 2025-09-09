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

# ──────────────────────────────────────────────────────────────────────────────
# ENV & clients
# ──────────────────────────────────────────────────────────────────────────────
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MEILI_URL = os.getenv("MEILI_URL")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")
MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

groq_client = Groq(api_key=GROQ_API_KEY)
meili_client = meilisearch.Client(MEILI_URL, MEILI_KEY)
index = meili_client.get_index(INDEX_NAME)

# ──────────────────────────────────────────────────────────────────────────────
# Prompts IA
# ──────────────────────────────────────────────────────────────────────────────
SYSTEM_MSG = """Tu es un extracteur d’adresses. RÈGLES:
- Lis UNIQUEMENT le texte fourni. N’invente jamais.
- Cible EXCLUSIVEMENT la première occurrence de « domicilié(e) à … » située à DROITE du NOM donné.
- Ignore les adresses des tiers (avocat(e)s, cabinets, sièges, administrateurs).
- Renvoie UNE seule adresse complète, sur UNE seule ligne, au format :
  «<Voie ou toponyme> <numéro>[, boîte X], à <CP> <Ville>»
- Normalise les abréviations (ex: «Av.» → «avenue»).
- Autorise les toponymes sans voie (ex: «Gueule-du-Loup(SAU) 161»).
- Si rien n’est clairement identifiable : renvoie exactement `inconnue`.
"""

FEWSHOTS = """
Exemples (entrée → sortie) :
1) NOM: Huberte JADOT
   FENÊTRE: «domiciliée à 1140 Evere, Av. L. Grosjean 79, résidant ...»
   → avenue L. Grosjean 79, à 1140 Evere

2) NOM: Joachim Croes
   FENÊTRE: «domicilié à 5600 Philippeville, Gueule-du-Loup(SAU) 161, a été ...»
   → Gueule-du-Loup(SAU) 161, à 5600 Philippeville

3) NOM: Jenny JOARIS
   FENÊTRE: «domiciliée à 5101 Namur, Home "La Closière", avenue du Bois Williame 11 ...»
   → avenue du Bois Williame 11, à 5101 Namur

4) NOM: (quelconque)
   FENÊTRE: «... l’avocate, dont le cabinet est établi à 1000 Bruxelles, rue X 12, ...»
   → inconnue
"""

STOP_SEQS = ["\n\n", "\n—", "\n•", "\n>"]

# ──────────────────────────────────────────────────────────────────────────────
# Regex utilitaires
# ──────────────────────────────────────────────────────────────────────────────
POSTAL_RX = re.compile(r"\b([1-9]\d{3})\b")

# numéro maison « étendu » : 7, 7A, 7/001, 183 0005, 5.3, 32 b3, 293 b025, 21 boîte 4, 21 bte 4, 21 bus 4
NUM_TOKEN_RX = re.compile(
    r"""
    \b
    (?P<num>\d{1,4})
    (?:/[0-9A-Za-z]+|[A-Za-z])?           # /001, A, b
    (?:\s+\d{1,4}(?:\.\d+)?)?             # 0005, 5.3
    (?:\s+(?:bo[iî]te|bte|bt|bus|b)\s*\w{1,6}|\s+[A-Za-z]\d{1,5})?
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Fenêtre « domicilié(e) à … » à droite du nom
CLAUSE_DOM_RX = re.compile(
    r"""
    domicili[ée](?:\(e\))?\s+à\s+
    (?P<clause>[^.;\n]*?)
    (?=\s*(?:,?\s*(?:r[ée]sid(?:ant|ente?)|r[ée]sident(?:e)?))|\s*[.;]|$)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Extraction du bloc de log
LOG_BLOCK_RX = re.compile(
    r"DOC ID:\s*'(?P<doc_id>[a-f0-9]{64})'\s*"
    r"\nNOM:\s*'(?P<nom>[^']*)'\s*"
    r"\nAdresse incomplète ou suspecte\s*:\s*'(?P<adresse>[^']*)'\s*"
    r"\n(?:Texte|texte)\s*:\s*(?P<texte>.+?)(?=\n\[\d{4}-\d{2}-\d{2}\s|\nDOC ID:|$)",
    re.DOTALL | re.IGNORECASE
)

# ──────────────────────────────────────────────────────────────────────────────
# Nettoyages & helpers tokens
# ──────────────────────────────────────────────────────────────────────────────
def _norm_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def _cp_in(s: str) -> Optional[str]:
    m = POSTAL_RX.search(s or "")
    return m.group(1) if m else None

def _first_house_num_root(s: str, known_cp: Optional[str] = None) -> Optional[str]:
    if not s:
        return None
    tmp = s
    if known_cp:
        tmp = re.sub(rf"\b{re.escape(known_cp)}\b", " ", tmp)
    for m in NUM_TOKEN_RX.finditer(tmp):
        val = m.group("num")
        if known_cp and val == known_cp:
            continue
        return str(int(val))
    return None

def _name_end(texte: str, nom: str) -> int:
    T = _norm_spaces(texte or "")
    n = _norm_spaces(nom or "")
    m = re.search(re.escape(n), T, flags=re.IGNORECASE)
    return m.end() if m else -1

def _clause_domicilie_a_droite(texte: str, nom: str, right_ctx: int = 1200) -> str:
    """Retourne la clause 'domicilié(e) à …' à DROITE du nom (fenêtre limitée)."""
    if not texte or not nom:
        return ""
    T = _norm_spaces(texte)
    end = _name_end(T, nom)
    if end < 0:
        return ""
    window = T[end:end + right_ctx]
    m = CLAUSE_DOM_RX.search(window)
    return (m.group("clause").strip() if m else "")

def _tokens_from_address(addr: str) -> tuple[Optional[str], Optional[str]]:
    addr_n = _norm_spaces(addr)
    cp = _cp_in(addr_n)
    num = _first_house_num_root(addr_n, known_cp=cp)
    return cp, num

def _has_cp_and_num(addr: str) -> bool:
    """True ssi l'adresse contient CP ET numéro (peu importe l'ordre)."""
    cp, num = _tokens_from_address(addr)
    return (cp is not None) and (num is not None)

# ──────────────────────────────────────────────────────────────────────────────
# IA helpers
# ──────────────────────────────────────────────────────────────────────────────
VOIE_MAP = {"av": "avenue", "bd": "boulevard", "ch": "chaussée", "r": "rue"}

ADDR_LINE_RX = re.compile(
    r"""
    ^\s*
    ([^\n,]+?)                              # 1: libellé voie/toponyme
    \s+
    (                                       # 2: numéro principal + extensions
      \d{1,4}
      (?:/[0-9A-Za-z]+|[A-Za-z])?
      (?:\s+\d{1,4}(?:\.\d+)?)?
      (?:\s+(?:bo[iî]te|bte|bt|bus|b)\s*\w{1,6}|\s+[A-Za-z]\d{1,5})?
    )
    \s*,\s*à\s*
    ([1-9]\d{3})                            # 3: CP
    \s+
    ([A-ZÀ-ÿ'’\- ]+?)                       # 4: Ville
    \s*$
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)

def _normalize_head(head: str) -> str:
    head = re.sub(r"\s+", " ", (head or "").strip())
    m = re.match(r"^(av\.?|bd\.?|ch\.?|r\.?)\b", head, flags=re.IGNORECASE)
    if m:
        abbr = m.group(1).lower().rstrip(".")
        mapped = VOIE_MAP.get(abbr, abbr)
        return mapped + head[m.end():]
    return head

def _clean_address_line(raw: str) -> Optional[str]:
    """Valide/normalise la ligne IA -> «<Voie/toponyme> <num>, à <CP> <Ville>» ou None."""
    if not raw:
        return None
    s = raw.strip().strip("“”\"' ")
    print(f"🧪 DEBUG before clean: {s!r}")
    if s.lower() == "inconnue":
        return "inconnue"
    m = ADDR_LINE_RX.match(s)
    if not m:
        print("🧪 DEBUG: ADDR_LINE_RX did not match.")
        return None
    head = _normalize_head(m.group(1))
    num  = re.sub(r"\s+", " ", m.group(2).strip())
    cp   = m.group(3).strip()
    city = re.sub(r"\s+", " ", m.group(4).strip())
    return f"{head} {num}, à {cp} {city}"

def _build_prompt(nom: str, fenetre: str) -> list[dict]:
    user = f"""NOM: {nom}

FENÊTRE (texte après le NOM, à partir de «domicilié(e) à …»):
\"\"\"{fenetre}\"\"\"

Rappel: Choisis uniquement l’adresse de la personne “domicilié(e) à …”.
Ignore les tiers. Rends une ligne au format requis, sinon “inconnue”.
"""
    return [
        {"role": "system", "content": SYSTEM_MSG},
        {"role": "user", "content": FEWSHOTS.strip()},
        {"role": "user", "content": user},
    ]

def _chat_once(model: str, messages: list[dict]) -> Optional[str]:
    try:
        resp = groq_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0,
            top_p=0.1,
            max_tokens=64,
            stop=STOP_SEQS,
        )
        raw = (resp.choices[0].message.content or "").strip()
        print(f"🧪 IA raw ({model}): {raw!r}")
        return raw
    except Exception as e:
        print(f"❌ Chat error ({model}): {e}")
        return None

def find_address_completion(doc_id: str, nom: str, fenetre: str) -> Optional[str]:
    if not fenetre or not nom:
        print("⚠️ IA skip: fenêtre vide ou nom vide → 'inconnue'")
        return "inconnue"
    messages = _build_prompt(nom, fenetre)
    print("📤 Prompt preview:", {
        "nom": nom,
        "fenêtre": fenetre[:200] + ("…" if len(fenetre) > 200 else "")
    })
    raw = _chat_once(MODEL, messages)
    cleaned = _clean_address_line(raw)
    print(f"🧹 Cleaned ({MODEL}): {cleaned!r}")
    return cleaned or "inconnue"

# ──────────────────────────────────────────────────────────────────────────────
# Meili helpers
# ──────────────────────────────────────────────────────────────────────────────
def _as_list(v) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [x for x in v if isinstance(x, str)]
    if isinstance(v, str) and v.strip():
        return [v.strip()]
    return []

def _norm_addr_pretty(s: str) -> str:
    s = (s or "").replace(",", " ")
    return re.sub(r"\s+", " ", s).strip()

def promote_address_in_meili(doc_id: str, candidate: str) -> bool:
    try:
        doc = dict(index.get_document(doc_id))
    except Exception as e:
        print(f"❌ Impossible de récupérer le document {doc_id} dans Meili: {e}")
        return False

    lst = _as_list(doc.get("adresse"))
    cand_norm = _norm_addr_pretty(candidate).lower()
    new = [a for a in lst if _norm_addr_pretty(a).lower() != cand_norm]
    new.insert(0, candidate)
    try:
        task = index.update_documents([{"id": doc_id, "adresse": new}])
        print(f"✅ Promote OK (taskUid={getattr(task, 'task_uid', None) or getattr(task, 'updateId', None)})")
        return True
    except Exception as e:
        print(f"❌ Erreur promote Meili (doc_id={doc_id}): {e}")
        return False

# ──────────────────────────────────────────────────────────────────────────────
# Cache IA
# ──────────────────────────────────────────────────────────────────────────────
def make_key(doc_id: str, label: str) -> str:
    return f"{doc_id}||{label}"

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

# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def process_log_file(log_file_name: str = "adresses.log"):
    full_path = chemin_log(log_file_name)
    print(f"📂 Fichier log : {full_path}")

    if not os.path.exists(full_path):
        print(f"❌ Fichier introuvable : {full_path}")
        return

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = LOG_BLOCK_RX.findall(content)
    print(f"🔍 {len(blocks)} bloc(s) détecté(s)")

    cache_path = os.path.join(os.path.dirname(full_path), "ia_addr_cache.json")
    cache = load_cache(cache_path)

    seen_doc = set()

    for doc_id, nom, adresses_logged, texte in blocks:
        if doc_id in seen_doc:
            print(f"⏭️ Doc {doc_id} déjà traité → skip.")
            continue
        seen_doc.add(doc_id)

        nom = (nom or "").strip()
        texte = (texte or "").strip()
        candidates = [a.strip() for a in (adresses_logged or "").split("|") if a.strip()]
        if not candidates:
            print(f"⚠️ Aucune adresse dans le bloc pour {doc_id}")
            continue

        first_addr = candidates[0]
        cp_first, num_first = _tokens_from_address(first_addr)

        print("\n" + "-"*80)
        print(f"📄 DOC ID : {doc_id}")
        print(f"👤 NOM    : {nom!r}")
        print(f"🏷️ 1ʳᵉ adr : {first_addr!r}")
        print(f"🧩 Tokens 1ʳᵉ adr : CP={cp_first!r} NUM={num_first!r}")

        # ── RÈGLE DEMANDÉE : on n'appelle PAS l'IA seulement si la 1ʳᵉ adresse a CP ET numéro
        if _has_cp_and_num(first_addr):
            print("✅ 1ʳᵉ adresse complète (CP ET numéro) → pas d'IA.")
            continue

        print("🧠 1ʳᵉ adresse incomplète (CP ou numéro manquant) → IA requise.")

        # Fenêtre la plus pertinente : clause « domicilié(e) à … » à droite du nom
        clause = _clause_domicilie_a_droite(texte, nom)
        if not clause:
            print("⚠️ Aucune clause 'domicilié(e) à …' trouvée à droite du nom → IA quand même sur une petite fenêtre.")
            end = _name_end(_norm_spaces(texte), nom)
            clause = _norm_spaces(texte[end:end+800]) if end >= 0 else _norm_spaces(texte[:800])

        key = make_key(doc_id, f"CLAUSE::{_norm_spaces(clause)}")
        if key in cache and cache[key]:
            print(f"⏭️ Déjà en cache → {cache[key]!r}")
            promote_address_in_meili(doc_id, cache[key])
            continue

        completion = find_address_completion(doc_id, nom, clause)

        if completion and completion.lower() != "inconnue":
            cache[key] = completion
            promote_address_in_meili(doc_id, completion)
        else:
            cache[key] = None

        save_cache(cache_path, cache)

# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("❌ Usage : python script.py <keyword>")
        sys.exit(1)

    keyword = sys.argv[1]
    keyword_clean = keyword.replace("+", "_")
    log_filename = f"adresses_logger_{keyword_clean}.log"
    process_log_file(log_filename)
