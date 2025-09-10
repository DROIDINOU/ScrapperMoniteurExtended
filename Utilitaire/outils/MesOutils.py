# --- Imports standards ---
import os
import pickle
import hashlib
import csv
import re

# --- Bibliothèques tierces ---
from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from typing import List, Any, Optional, Tuple

# --- Modules internes au projet ---
from Constante.mesconstantes import JOURMAPBIS, MOISMAPBIS, ANNEEMAPBIS, TVA_INSTITUTIONS
# ----------------------------------------------------------------------------------------------------------------------
#                                 NETTOYAGE FINAL DES ADRESSES
# Nettoie une liste d'adresses selon un mot-clé thématique (keyword).
# Les parties de texte non pertinentes (comme "personne protégée", "a été placé...", etc.)
# sont supprimées selon le contexte du keyword.
# :param adresses: liste d'adresses extraites (list[str])
# :param keyword: mot-clé du contexte (str), ex: "justice+de+paix", "terrorisme", ...
# :return: liste nettoyée d'adresses (list[str])
# ----------------------------------------------------------------------------------------------------------------------


def nettoyer_adresses_par_keyword(adresses, keyword):

    if not adresses:
        return []

    nettoyees = []

    for adr in adresses:
        original = adr  # sauvegarde avant nettoyage

        # Normalisation espaces
        cleaned = re.sub(r'\s+', ' ', adr).strip()

        # Nettoyages contextuels par keyword
        if keyword == "justice+de+paix":
            # Supprimer les mentions du récit typiques
            cleaned = re.sub(r"et des biens de", "", cleaned, flags=re.IGNORECASE)

        if cleaned:
            nettoyees.append(cleaned)
        else:
            # fallback : garder version originale si nettoyage vide
            nettoyees.append(original.strip())

    return nettoyees

# ---------------------------------------------------------------------------------------------------------------------
#     Supprime toutes les balises HTML d'une chaîne de texte.
#     Utilise une expression régulière pour matcher toute séquence de type <...>
#     (non-gourmande, pour ne pas avaler trop de contenu), puis la remplace par une chaîne vide.
# ----------------------------------------------------------------------------------------------------------------------
def strip_html_tags(text):
    return re.sub('<.*?>', '', text)


# ----------------------------------------------------------------------------------------------------------------------
#     Extrait l'index de page à partir de l'URL d'un PDF contenant '#page=X'.
#     Retourne un entier indexé à 0 (utilisable avec PyMuPDF).
#     Si aucun numéro de page n'est trouvé, retourne None.
# ----------------------------------------------------------------------------------------------------------------------
def extract_page_index_from_url(pdf_url):
    match = re.search(r'#page=(\d+)', pdf_url)
    if match:
        page_number = int(match.group(1))
        return page_number - 1  # PyMuPDF indexe à partir de 0
    return None


# va falloir étendre cela je pense
def _norm(s: str) -> str:
    s = s or ""
    s = s.lower()
    s = s.replace("’", "'")
    # unifier abréviations courantes
    s = re.sub(r"\bav\.?\b", "avenue", s)
    s = re.sub(r"\bbd\b", "boulevard", s)
    s = re.sub(r"\ball[ée]e\b", "allee", s)  # évite la variation é/ée
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# ---------------------------------------------------------------------------------------------------------------------
#                                    VERIFICATION LISTE ADRESSES A CODE POSTAL ET NUMERO
#                                    utilisé dans main pour verifier que la premiere adresse
#                                    qui est l'adresse de la personne concernée est correcte
# ----------------------------------------------------------------------------------------------------------------------
# Même idée que dans l’extraction, mais plus tolérante pour la validation
DASH_CHARS = r"\-\u2010-\u2015"  # -, ‐, ‒, –, —, ―
# Autorise espaces autour de / ou - (ex: "60 / 0-1")
NUM_TOKEN_LOOSE = rf"\d{{1,4}}(?:[A-Za-z](?!\s*\.))?(?:\s*[/[{DASH_CHARS}]]\s*[A-ZÀ-ÿ0-9\-]+)?"
NUM_LABEL = r"(?:num(?:[ée]ro)?\.?|n[°ºo]?\.?|nr\.?)"

CP_RX = re.compile(r"\b([1-9]\d{3})\b")
# Avec ou sans libellé "num./n°/nr" juste avant
ADDR_NUM_RX = re.compile(rf"(?:{NUM_LABEL}\s*)?({NUM_TOKEN_LOOSE})", re.IGNORECASE)

def _norm_spaces(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\xa0", " ").replace("\u202f", " ").replace("\u2009", " ").replace("\u200a", " ")
    return re.sub(r"\s+", " ", s).strip()

def has_cp_plus_other_number_aligned(s: str) -> bool:
    """
    True s'il y a au moins 1 CP (4 chiffres) ET au moins 1 numéro d'adresse
    au sens de l’extraction (NUM_TOKEN tolérant), distinct du/des CP.
    Ex:
      - '7000 Mons, Boulevard Sainctelette 60 / 0-1' -> True
      - '4537 Verlaine, Grand-Route 245/0011'        -> True
      - '4802 Verviers, avenue de Thiervaux 2 322'   -> True (deux nombres distincts)
      - '5100 Namur'                                  -> False
    """
    s = _norm_spaces(s)
    if not s:
        return False

    cps = set(CP_RX.findall(s))
    if not cps:
        return False

    # Tous les tokens "numéro d'adresse" style extraction
    addr_nums = [m.group(1) for m in ADDR_NUM_RX.finditer(s)]
    if not addr_nums:
        # Dernier recours : s'il y a deux nombres "simples" ≠ CP (ex: "2 322")
        # on les comptera ci-dessous via le scan générique
        pass

    # 1) s'il y a un token d'adresse dont la partie de tête (digits) ≠ CP → OK
    for tok in addr_nums:
        head = re.match(r"\d{1,4}", tok)
        if head and head.group(0) not in cps:
            return True

    # 2) fallback : compter tous les nombres 1–4 chiffres (avec lettre optionnelle) hors CP.
    #    Ça couvre le cas "2 322" sans slash ni tiret.
    simple_nums = [m.group(1) for m in re.finditer(r"\b(\d{1,4}[A-Za-z]?)\b", s)]
    # Enlève les CP exacts
    simple_nums = [n for n in simple_nums if n not in cps]
    # S'il reste au moins un nombre hors CP -> True
    return len(simple_nums) >= 1
# ---------------------------------------------------------------------------------------------------------------------
#                                    ORDONNANCEMENT DES ADRESSES EN FONCTION DU NOM
#                         (Permet de mettre l'adresse de la personne visee en 1 dans la liste d'adresses)
# ----------------------------------------------------------------------------------------------------------------------

# ---------------------------
# Recherche positions dans le texte
# ---------------------------

def _first_after(T: str, pat: Optional[str], start: int) -> Optional[int]:
    if not pat:
        return None
    i = T.find(pat, start)
    return i if i >= 0 else None


def _first_any(T: str, pat: Optional[str]) -> Optional[int]:
    if not pat:
        return None
    i = T.find(pat)
    return i if i >= 0 else None

# ---------------------------------------------------------------------------------------------------------------------
#
# ---------------------------------------------------------------------------------------------------------------------



_NUM_RX  = r"\b\d{1,4}(?:[A-Za-z](?!\s*\.))?(?:/[A-ZÀ-ÿ0-9\-]+)?\b"



def _extract_cp(addr: str) -> Optional[str]:
    m = re.search(r"\b(\d{4})\b", addr)
    return m.group(1) if m else None


def verifier_si_premiere_adresse_est_bien_rapprochee_du_nom(nom: Any, texte: str, adresse: str, doc_hash: str, logger=None):
    """
    Vérifie si le 1er CP + numéro rencontrés après le nom correspondent à l’adresse donnée.
    Sinon, log un warning.
    """
    T = _norm(texte)
    name_end = _name_end_in_text(nom, texte)

    # Recherche du premier CP + numéro après le nom
    sub_T = T[name_end:]

    cp_match = re.search(r"\b\d{4}\b", sub_T)
    num_match = re.search(_NUM_RX, sub_T)

    first_cp = cp_match.group(0) if cp_match else None
    first_num = None
    if num_match:
        token = num_match.group(0)
        if not re.match(r"\b\d{1,4}/\d", token):  # ignorer "492/4" etc.
            first_num = token

    # Extraction CP + numéro depuis la 1ère adresse
    addr_cp = _extract_cp(adresse)
    addr_num = _extract_house_num(adresse)

    if not (first_cp and first_num):
        # Rien trouvé après le nom
        if logger:
            logger.warning(f"[❗️Aucun CP+num après nom] DOC={doc_hash} | adresse='{adresse}' | trouvé: CP={first_cp}, num={first_num}")
        else:
            print(f"[❗️Aucun CP+num après nom] DOC={doc_hash} | adresse='{adresse}' | trouvé: CP={first_cp}, num={first_num}")
        return

    # Comparaison stricte
    if first_cp != addr_cp or first_num != addr_num:
        msg = (f"[❗️1ère adresse différente du 1er CP+num après nom] DOC={doc_hash} | "
               f"adresse='{adresse}' | extrait: CP={addr_cp}, num={addr_num} | trouvé: CP={first_cp}, num={first_num}")
        if logger:
            logger.warning(msg)
        else:
            print(msg)

# Score “occurrences près du nom”
# ---------------------------
def _window_tokens_score(texte: str, start: int, addr: str, window: int = 220) -> Tuple[int, int]:
    """
    Compte le nb d'occurrences de tokens (>=3 lettres) de l'adresse
    dans la fenêtre [start, start+window] du texte normalisé.
    Renvoie (score_total, pos_min_token) pour tie-break.
    """
    T = _norm(texte)
    W = T[start:start+window]
    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{3,}", _norm(addr))
    if not tokens:
        return (0, 10**9)
    total = 0
    first_pos = 10**9
    for tok in set(tokens):
        j = W.find(tok)
        if j >= 0:
            total += W.count(tok)
            first_pos = min(first_pos, j)
    return (total, first_pos)

# ---------------------------
# Fonction principale
# ---------------------------
def prioriser_adresse_proche_nom_struct(
    nom: Any,
    texte: str,
    adresses: List[str],
    *,
    min_tokens_required: bool = False  # gardé pour compat, ignoré ici
) -> List[str]:
    """
    Règle :
      1) CP le plus proche après le nom
      2) si même CP → numéro d'adresse le plus proche après le nom
      3) si CP & numéro identiques → + d'occurrences de la chaîne près du nom (petite fenêtre)
      4) fallbacks : première occurrence 'anywhere', puis longueur, puis ordre initial
    """
    if not adresses:
        return adresses

    T = _norm(texte)
    name_end = _name_end_in_text(nom, texte)

    scored = []
    for idx, a in enumerate(adresses):
        a_norm = _norm(a)
        cp = _extract_cp(a)
        hn = _extract_house_num(a)

        # positions “après nom”
        cp_after = _first_after(T, cp, name_end) if cp else None
        hn_after = _first_after(T, _norm(hn) if hn else None, name_end) if hn else None

        # positions “n’importe où”
        cp_any  = _first_any(T, cp) if cp else None
        hn_any  = _first_any(T, _norm(hn) if hn else None) if hn else None

        # occurrences dans une petite fenêtre à droite du nom
        near_score, near_pos = _window_tokens_score(texte, name_end, a)

        # clé de tri (plus petit = mieux)
        key = (
            0 if cp_after is not None else 1,
            (cp_after - name_end) if cp_after is not None else 10**9,

            0 if hn_after is not None else 1,
            (hn_after - name_end) if hn_after is not None else 10**9,

            -near_score,                  # plus d’occurrences = mieux
            near_pos,                     # plus tôt dans la fenêtre = mieux

            cp_any if cp_any is not None else 10**9,
            hn_any if hn_any is not None else 10**9,

            -len(a_norm),                 # plus descriptif = mieux
            idx                           # stabilité d’ordre initial
        )
        scored.append((key, a))

    scored.sort(key=lambda x: x[0])
    return [a for _, a in scored]


# --------------------------------------------------------------------------------------
#                                             Logs

# --------------------------------------------------------------------------------------
# --------------------------- 🔧 Normalisation texte


def _norm(s: str) -> str:
    s = (s or "")
    s = s.replace("’", "'").replace('"', " ")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

# --------------------------- 🔍 Localiser le nom dans le texte
def _name_end_in_text(nom: Any, texte: str) -> int:
    T = _norm(texte)
    candidates = []
    if isinstance(nom, dict):
        candidates += [c for c in (nom.get("canonicals") or []) if isinstance(c, str)]
        candidates += [a for a in (nom.get("aliases_flat") or []) if isinstance(a, str)]
        for r in nom.get("records") or []:
            if isinstance(r, dict) and isinstance(r.get("canonical"), str):
                candidates.append(r["canonical"])
    elif isinstance(nom, (list, tuple, set)):
        candidates += [s for s in nom if isinstance(s, str)]
    elif isinstance(nom, str):
        candidates.append(nom)

    for c in candidates:
        c_norm = _norm(c)
        if not c_norm:
            continue
        i = T.find(c_norm)
        if i >= 0:
            return i + len(c_norm)
    return 0


def _clean_dates_and_grands_nombres(s: str) -> str:
    """Supprime les motifs de type dates + grands nombres (>6 chiffres, avec ou sans séparateur)."""
    MONTHS = r"(janvier|février|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|décembre)"

    # Dates classiques
    s = re.sub(rf"\b\d{{1,2}}\s+{MONTHS}\s+\d{{4}}\b", "", s, flags=re.IGNORECASE)
    s = re.sub(rf"\b{MONTHS}\s+\d{{4}}\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", "", s)
    s = re.sub(r"\b(19|20)\d{2}\b", "", s)

    # Suites de plus de 6 chiffres (avec ou sans séparateurs)
    s = re.sub(r"\b\d{7,}\b", "", s)                         # 1234567
    s = re.sub(r"\b(?:\d[\.\-]){6,}\d\b", "", s)             # 85.08.11-207.58 etc.

    return s


def _extract_house_num(addr: str) -> Optional[str]:
    cp = _extract_cp(addr)
    for m in re.finditer(r"\b\d{1,4}(?:/[A-ZÀ-ÿ0-9\-]+)?\b", addr):
        token = m.group(0)
        if re.match(r"\b\d{1,4}/\d", token):  # Exclure 492/4 etc.
            continue
        if cp and token == cp:
            continue
        return token
    return None


def verifier_premiere_adresse_apres_nom(nom: Any, texte: str, adresse: str, doc_hash: str, logger=None):
    """
    Compare la première adresse extraite après le nom (CP + numéro) à l'adresse priorisée.
    Logger si elles ne correspondent pas.
    """
    T = _norm(texte)
    name_end = _name_end_in_text(nom, texte)
    T_after_nom = _clean_dates_and_grands_nombres(T[name_end:])

    # Recherche CP puis numéro (≠ date ou grand nombre)
    RX_VALID_NUM = r"\b\d{1,4}(?:[A-Za-z](?!\s*\.))?(?:/[A-Z0-9\-]+)?\b"
    RX_GRAND_NB = r"\b\d{6,}(?:[.,-]\d+)?\b"

    def is_valid_num(n: str) -> bool:
        return not re.fullmatch(RX_GRAND_NB, n)

    # Trouver le premier CP suivi de n° valide
    cp = None
    num = None
    for m in re.finditer(r"\b\d{4}\b", T_after_nom):
        cp_candidate = m.group()
        remaining = T_after_nom[m.end():]

        num_match = re.search(RX_VALID_NUM, remaining)
        if num_match and is_valid_num(num_match.group()):
            cp = cp_candidate
            num = num_match.group()
            break

    if not (cp and num):
        return  # Pas d'adresse identifiable

    # Extraire CP + numéro de l’adresse priorisée
    cp_ref = _extract_cp(adresse)
    num_ref = _extract_house_num(adresse)

    if cp != cp_ref or num != num_ref:
        msg = (
            f"[❗️1ère vraie adresse ≠ adresse priorisée] DOC={doc_hash} | "
            f"Priorisée = '{adresse}' | Extrait après nom = {cp} {num}"
        )
        if logger:
            logger.warning(msg)
        else:
            print(msg)

# --------------------------------------------------------------------------------------
# UNICODE_SPACES_MAP : Créer un dictionnaire de correspondance Unicode
# pour remplacer certains espaces spéciaux invisibles par un espace standard (" ").
# _norm_spaces :
# --------------------------------------------------------------------------------------


UNICODE_SPACES_MAP = dict.fromkeys(map(ord, "\u00A0\u202F\u2007\u2009\u200A\u200B"), " ")


# --------------------------------------------------------------------------------------
# Retourne que les chiffres de la chaine
# Utilise pour transformer les tva avec points (0514.194.192)
# en tva sans point (0514194192)
# --------------------------------------------------------------------------------------
def digits_only(s: str) -> str:
    return re.sub(r"\D+", "", s or "")


# --------------------------------------------------------------------------------------
# Retourne le premier non-vide (après strip).
# --------------------------------------------------------------------------------------
def _pick(*vals: str) -> str:
    for v in vals:
        v = (v or "").strip()
        if v:
            return v
    return ""


def _format_address(row: dict, lang: str) -> str:
    """
    Construit une adresse lisible. Préférence pour la langue demandée,
    mais bascule sur l'autre si le champ est vide.
    """
    lang = (lang or "FR").upper()
    if lang not in {"FR", "NL"}:
        lang = "FR"

    # Suffixe principal et de repli
    suf_main = "FR" if lang == "FR" else "NL"
    suf_alt = "NL" if lang == "FR" else "FR"

    street = _pick(row.get(f"Street{suf_main}"), row.get(f"Street{suf_alt}"))
    muni = _pick(row.get(f"Municipality{suf_main}"), row.get(f"Municipality{suf_alt}"))
    country = _pick(row.get(f"Country{suf_main}"), row.get(f"Country{suf_alt}"))

    zipcode = (row.get("Zipcode") or "").strip()
    number = (row.get("HouseNumber") or "").strip()
    box = (row.get("Box") or "").strip()
    extra = (row.get("ExtraAddressInfo") or "").strip()

    # Libellé boîte selon langue (usage BE)
    box_lbl = "bte" if lang == "FR" else "bus"

    line1 = " ".join([s for s in [street, number] if s])
    if box:
        line1 = f"{line1} {box_lbl} {box}"

    line2 = " ".join([s for s in [zipcode, muni] if s])

    parts = [p for p in [line1, line2, country] if p]
    addr = ", ".join(parts)

    if extra:
        addr = f"{addr}, {extra}"

    return addr


def build_address_index(
    csv_path: str,
    *,
    lang: str = "FR",                       # "FR" ou "NL" (fallback auto si champ vide)
    allowed_types: set[str] | None = None,  # ex: {"REGO", "SEAT"} si tu veux filtrer
    skip_public: bool = True,               # idem à ta fonction précédente
) -> dict[str, set[str]]:
    """
    Lit address.csv en streaming et renvoie :
      { "xxxx.xxx.xxx": {"Adresse complète 1", "Adresse complète 2", ...}, ... }
    """

    index: dict[str, set[str]] = {}

    # petit cache disque pour gros CSV (même logique : mtime uniquement)
    pkl = _cache_path_for(csv_path)
    csv_mtime = _csv_mtime(csv_path)
    if os.path.exists(pkl):
        try:
            with open(pkl, "rb") as f:
                payload = pickle.load(f)
            if payload.get("mtime") == csv_mtime:
                return payload["index"]
        except Exception:
            pass  # on reconstruit si échec / cache obsolète

    # lecture streaming (utf-8-sig puis latin-1)
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(csv_path, newline="", encoding=enc) as f:
                r = csv.DictReader(f)
                for row in r:
                    ent = (row.get("EntityNumber") or "").strip()
                    if not ent:
                        continue
                    if skip_public and is_entite_publique(ent):
                        continue

                    typ = (row.get("TypeOfAddress") or "").strip()
                    if allowed_types and typ not in allowed_types:
                        continue

                    # Adresse éventuellement "radiée" : on garde la même philosophie que ton code,
                    # on ne filtre PAS sur DateStrikingOff (mais tu peux le faire ici si besoin).
                    addr = _format_address(row, lang)
                    if not addr:
                        continue

                    index.setdefault(ent, set()).add(addr)
            break
        except UnicodeDecodeError:
            continue

    # sauve en cache disque avec mtime du CSV
    try:
        with open(pkl, "wb") as f:
            pickle.dump({"mtime": csv_mtime, "index": index}, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass

    return index


# --------------------------------------------------------------------------------------
# Retourne le premier non-vide (après strip).
# Filtre public num public dans fichier bce
# Utilise pcq les numeros publics ne seront jamais visés par decisions (attention ce ne
# sera pas le cas si on étend a decision FSMA dans l avenir
# --------------------------------------------------------------------------------------

def is_entite_publique(entite_bce: str) -> bool:
    s = re.sub(r"\D", "", entite_bce or "")
    if len(s) == 9:
        s = "0" + s
    return s.startswith("0200")


# --------------------------------------------------------------------------------------
# transforme en format bce avec .
# --------------------------------------------------------------------------------------
def format_bce(n: str | None) -> str | None:
    if not n:
        return None
    d = re.sub(r"\D", "", str(n))
    if len(d) == 9:
        d = "0" + d
    if len(d) != 10:
        return None
    return f"{d[:4]}.{d[4:7]}.{d[7:]}"


def _csv_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _cache_path_for(csv_path: str) -> str:
    base = os.path.splitext(os.path.basename(csv_path))[0]
    os.makedirs(".cache", exist_ok=True)
    return os.path.join(".cache", f"{base}.denoms.pkl")


def build_denom_index(
    csv_path: str,
    *,
    allowed_types: set[str] | None = None,   # ex: {"001","002"} si tu veux restreindre
    allowed_langs: set[str] | None = None,   # ex: {"1","2"} (FR=2, NL=1, DE=0 selon ton fichier)
    skip_public: bool = True,
) -> dict[str, set[str]]:
    """
    Lit le CSV une seule fois et renvoie un dict:
      { "xxxx.xxx.xxx": {"Denom1","Denom2", ...}, ... }
    """
    index: dict[str, set[str]] = {}

    # petit cache disque pour gros CSV
    pkl = _cache_path_for(csv_path)
    csv_mtime = _csv_mtime(csv_path)
    if os.path.exists(pkl):
        try:
            with open(pkl, "rb") as f:
                payload = pickle.load(f)
            if payload.get("mtime") == csv_mtime:
                return payload["index"]
        except Exception:
            pass  # on reconstruit

    # lecture streaming (utf-8-sig puis latin-1)
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(csv_path, newline="", encoding=enc) as f:
                r = csv.DictReader(f)
                for row in r:
                    ent = (row.get("EntityNumber") or "").strip()
                    if not ent:
                        continue
                    if skip_public and is_entite_publique(ent):
                        continue

                    typ = (row.get("TypeOfDenomination") or "").strip()
                    if allowed_types and typ not in allowed_types:
                        continue

                    lang = (row.get("Language") or "").strip()
                    if allowed_langs and lang not in allowed_langs:
                        continue

                    denom = (row.get("Denomination") or "").strip()
                    if not denom:
                        continue

                    index.setdefault(ent, set()).add(denom)
            break
        except UnicodeDecodeError:
            continue

    # sauve en cache disque avec mtime du CSV
    try:
        with open(pkl, "wb") as f:
            pickle.dump({"mtime": csv_mtime, "index": index}, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass

    return index


def has_person_names(nom):
    if nom is None:
        return False
    if isinstance(nom, dict):
        return bool((nom.get("records") or []) or
                    (nom.get("canonicals") or []) or
                    (nom.get("aliases_flat") or []))
    if isinstance(nom, (list, str)):
        return bool(nom)
    return False
# --- Utils NRN ---


def _norm_nrn(yy, mm, dd, bloc, suffix):
    yy = yy.zfill(2); mm = mm.zfill(2); dd = dd.zfill(2)
    bloc = bloc.zfill(3); suffix = suffix.zfill(2)
    return f"{yy}.{mm}.{dd}-{bloc}.{suffix}"


def extract_nrn_variants(text: str):
    # Séparateurs autorisés entre blocs du NRN
    _NRSEP = r"[.\-/ ]"

    # Libellés possibles avant le NRN:
    # - NRN
    # - R.N. / R N / R.N / R. N. (avec ou sans points/espaces)
    # - Registre national
    LABEL = r"(?:NRN|R\.?\s*N\.?|REGISTRE\s+NATIONAL)"

    out = []

    # 1) NRN « isolé » (sans libellé)
    rx_nrn = rf"\b(\d{{2}}){_NRSEP}(\d{{2}}){_NRSEP}(\d{{2}}){_NRSEP}(\d{{3}}){_NRSEP}(\d{{2}})\b"
    for yy, mm, dd, bloc, suffix in re.findall(rx_nrn, text):
        out.append(_norm_nrn(yy, mm, dd, bloc, suffix))

    # 2) NRN précédé d’un libellé (inclut variantes et parenthèses)
    #    Ex : "NRN: 67.07.21-123.45"
    #         "(R.N. 33.06.22-133.39)"
    #         "Registre national 67-07-21 123 45"
    rx_labeled = rf"(?:\b|[\(\[])\s*(?:{LABEL})\s*[:\-]?\s*(\d{{2}}){_NRSEP}(\d{{2}}){_NRSEP}(\d{{2}}){_NRSEP}(\d{{3}}){_NRSEP}(\d{{2}})"
    for yy, mm, dd, bloc, suffix in re.findall(rx_labeled, text, flags=re.IGNORECASE):
        out.append(_norm_nrn(yy, mm, dd, bloc, suffix))

    # dédoublonnage en conservant l'ordre
    return list(dict.fromkeys(out))


def clean_date_jugement(raw):
    """
    Extrait uniquement la date au format '16 juin 2025'
    et ignore ce qui suit (points, texte...).
    """
    mois = (
        "janvier|février|mars|avril|mai|juin|juillet|août|"
        "septembre|octobre|novembre|décembre"
    )
    pattern_date = rf"\b\d{{1,2}}\s+(?:{mois})\s+\d{{4}}\b"
    match = re.search(pattern_date, raw, flags=re.IGNORECASE)
    if match:
        return match.group(0).strip()
    return None


# ***********************************
# get_month_name
# detect_erratum
# extract_numero_tva
# extract_clean_text
# ************************************
# Petit normaliseur des nombres en mots → int (pour le tag "…_X_ans")
_WORD2INT = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9,
    "dix": 10, "onze": 11, "douze": 12, "quinze": 15, "vingt": 20
}


def normalize_annees(val: str) -> int | None:
    v = (val or "").strip().lower()
    return int(v) if v.isdigit() else _WORD2INT.get(v)


# faire comme celui en dessous pour plus de securite
def chemin_csv(nom_fichier: str) -> str:
    return os.path.abspath(os.path.join("Datas", nom_fichier))


def chemin_csv_abs(nom_fichier: str) -> str:
    """Retourne le chemin absolu vers un fichier CSV situé dans le dossier 'Datas' (au même niveau que 'Scripts')."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))  # <- remonte 2 niveaux
    return os.path.join(base_dir, 'Datas', nom_fichier)


def chemin_log(nom_fichier: str = "succession.log") -> str:
    """
    Retourne le chemin absolu du fichier de log, situé dans le dossier 'logs',
    depuis la racine du projet (où est situé le dossier Utilitaire).
    """
    # Dossier du projet = 2 niveaux au-dessus de ce fichier
    projet_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(projet_dir, "logs", nom_fichier)


# ____________________________________________________________
    # Transforme numero de 1 à 12 en un mois de la liste mois.
# ____________________________________________________________
def get_month_name(month_num):
    mois = [
        "", "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"
    ]
    return mois[month_num] if 1 <= month_num <= 12 else ""


# ____________________________________________________________
    # Retourne True si 'erratum', 'errata' ou 'ordonnance rectificative' est détecté
    # dans les 400 premiers caractères du texte HTML. Sinon False.
# ____________________________________________________________
def detect_erratum(texte_html):

    soup = BeautifulSoup(texte_html, 'html.parser')
    full_text = soup.get_text(separator=" ").strip().lower()
    snippet = full_text[:400]

    if re.search(r"\berrat(?:um|a)\b", snippet):
        return True

    if re.search(r"\bordonnance\s+rectificative\b", snippet):
        return True

    return False


# ____________________________________________________________
    # extraits les numéros de tva
    # Exemples détectés : 1008.529.190, 0108 529 190, 0423456789, 05427-15196, etc.
# ____________________________________________________________
def extract_numero_tva(text: str, format_output: bool = False) -> list[str]:

    text = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")

    # Liste des résultats
    tvas = []

    # 🔹 1. Format standard 4+3+3 (avec espace, point, tiret ou rien)
    pattern_4_3_3 = r"\b(\d{4})[\s.\-]?(\d{3})[\s.\-]?(\d{3})\b"
    matches = re.findall(pattern_4_3_3, text)
    for a, b, c in matches:
        raw = f"{a}{b}{c}"
        if len(raw) == 10 and raw.isdigit():
            tvas.append(f"{raw[:4]}.{raw[4:7]}.{raw[7:]}" if format_output else raw)

    # 🔹 2. Format alternatif : 5 + 5 chiffres (souvent avec tiret)
    pattern_5_5 = r"\b(\d{5})[\s.\-]?(\d{5})\b"
    matches_alt = re.findall(pattern_5_5, text)
    for a, b in matches_alt:
        raw = f"{a}{b}"
        if len(raw) == 10 and raw.isdigit():
            tvas.append(f"{raw[:4]}.{raw[4:7]}.{raw[7:]}" if format_output else raw)

    # 🔁 Supprime les doublons tout en conservant l’ordre
    seen = set()
    tvas = [x for x in tvas if not (x in seen or seen.add(x))]

    # 🔹 3. Exclure ceux qui sont dans la liste TVA_ETAT
    if TVA_INSTITUTIONS:
        # on normalise sans points pour comparer
        tva_set = {x.replace(".", "") for x in TVA_INSTITUTIONS}
        tvas = [x for x in tvas if x.replace(".", "") not in tva_set]

    return tvas
# ____________________________________________________________
    # Extrait un texte propre à partir d’un objet BeautifulSoup.
    # Par défaut, supprime la section 'Liens :' et ses liens.
    # Passez remove_links=False pour ne pas la supprimer.
# ____________________________________________________________


def extract_clean_text(soup, remove_links: bool = True):
    """
    Extrait un texte propre à partir d’un objet BeautifulSoup.
    Par défaut, supprime la section 'Liens :' et ses liens.
    Passez remove_links=False pour ne pas la supprimer.
    """
    # ⬇️ Comportement inchangé par défaut
    if remove_links:
        for el in soup.select(
                'h2.links-title, a.links-link, #link-text, .links, button#link-button, button.button'
        ):
            el.decompose()

    output = []
    last_was_tag = None

    for elem in soup.descendants:
        if isinstance(elem, NavigableString):
            txt = elem.strip()
            if txt:
                if last_was_tag in ("font", "sup", "text"):
                    output.append(" ")
                output.append(txt)
                last_was_tag = "text"
        elif isinstance(elem, Tag):
            tag_name = elem.name.lower()
            if tag_name == "br":
                output.append(" ")
                last_was_tag = "br"
            elif tag_name == "sup":
                sup_text = elem.get_text(strip=True)
                if output and output[-1].isdigit():
                    output[-1] = output[-1] + sup_text
                else:
                    output.append(sup_text)
                last_was_tag = "sup"
            else:
                last_was_tag = tag_name

    text = "".join(output)
    text = text.replace('\u00a0', ' ').replace('\u200b', '').replace('\ufeff', '')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def clean_url(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    # Supprimer 'exp' de la query string s'il existe
    query.pop("exp", None)

    # Reconstruire l'URL sans 'exp'
    cleaned_query = urlencode(query, doseq=True)
    cleaned_url = urlunparse(parsed._replace(query=cleaned_query))
    return cleaned_url


def generate_doc_hash_from_html(html, date_doc):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(["script", "style", "font", "span", "mark"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"Liens\s*:.*?(Haut de la page|Copier le lien).*?$", "", text, flags=re.DOTALL)
    text = re.sub(r"https://www\.ejustice\.just\.fgov\.be[^\s]+", "", text)
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # 💡 Inclure la date dans le hash
    full_string = f"{date_doc}::{text}"
    return hashlib.sha256(full_string.encode("utf-8")).hexdigest()


def convert_french_text_date_to_numeric(text_date):
    """
    Convertit une date en lettres (ex : 'trente mai deux mil vingt-trois')
    en format '30 mai 2023'
    """

    words = text_date.lower().strip().split()

    # Créer une date si les 3 parties sont reconnaissables
    jour = next((v for k, v in JOURMAPBIS.items() if k in text_date), None)
    mois = next((v for k, v in MOISMAPBIS.items() if k in text_date), None)
    annee = next((v for k, v in ANNEEMAPBIS.items() if k in text_date), None)

    if jour and mois and annee:
        return f"{jour} {mois} {annee}"

    return None


def normalize_mois(val):
    mots = {
        "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
        "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
        "onze": 11, "douze": 12
    }
    if val.isdigit():
        return int(val)
    return mots.get(val.lower(), None)


def decode_nrn(nrn: str):
    """
    Décode un numéro de registre national belge en date de naissance + sexe.
    Retourne (YYYY-MM-DD, sexe).
    """
    nrn = re.sub(r"\D", "", nrn)  # garder seulement les chiffres
    if len(nrn) != 11:
        return None

    base = nrn[:9]    # YYMMDDXXX
    cle = int(nrn[9:])  # 2 chiffres finaux

    # Test siècle 1900
    if (97 - (int(base) % 97)) == cle:
        year = 1900 + int(base[:2])
    else:
        year = 2000 + int(base[:2])

    month = int(base[2:4])
    day = int(base[4:6])

    # Sexe = bloc XXX pair = femme / impair = homme
    sexe = "M" if int(base[6:9]) % 2 == 1 else "F"

    return f"{year:04d}-{month:02d}-{day:02d}", sexe


def norm_er(x):
    if isinstance(x, str):
            x = re.sub(r"\b(\d{1,2})\s*er\s*er\b", r"\1er", x)
            x = re.sub(r"\b(\d{1,2})\s*er\b", r"\1", x)
            return x
    return x


def liste_vide_ou_que_vides_lenient(lst):
    return (not lst) or all(
        (s is None) or (isinstance(s, str) and not s.strip())
        for s in lst
    )


def clean_nom_trib_entreprise(noms: list[str]) -> list[str]:
    """
    Supprime de la liste les noms qui correspondent exactement à 'en cause de' (espaces ignorés, insensible à la casse).

    Args:
        noms (list[str]): Liste de noms extraits à nettoyer.

    Returns:
        list[str]: Liste filtrée des noms.
    """
    return [
        nom for nom in noms
        if (nom.strip().lower() != "en cause de"
            and nom.strip().lower() != "qualité de curatrice sa"
            and nom.strip().lower() != "conformément e"
            and nom.strip().lower() != "conformément à"
            and nom.strip().lower() != "l'etat belge spf finances"
            and nom.strip().lower() != "1. l'etat belge spf finances"
            and nom.strip().lower() != "2. l etat belge spf finances"
            and nom.strip().lower() != "3. l etat belge spf finances"
            and nom.strip().lower() != "spf finances")

    ]


def nettoyer_adresse(adresse):
    # Supprime "à" ou "a" (avec ou sans accent) juste avant CP + Ville
    return re.sub(r"\b[àa]\s+(?=\d{4}\s+[A-ZÀ-Ÿ])", "", adresse, flags=re.IGNORECASE)


def couper_fin_adresse(adresse):
    # Coupe si des mots comme "Signifié", "N°", "Casier", "Nationalité", etc. apparaissent
    adresse = re.split(r"\b(Signifi[eé]|N°|Casier|Nationalit[eé]|Né[e]?\b|Date|le\s+\d{1,2}\s+\w+)", adresse)[0]
    return adresse.strip()

