# --- Imports standards ---
import re
import os
import pickle
import hashlib
import csv
import re
import difflib

# --- Bibliothèques tierces ---
from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse
from typing import List, Any, Optional


# --- Modules internes au projet ---
from Constante.mesconstantes import VILLES, JOURMAP, MOISMAP, ANNEMAP, JOURMAPBIS, MOISMAPBIS, \
    ANNEEMAPBIS, TVA_INSTITUTIONS




POSTAL_RX = re.compile(r"\b([1-9]\d{3})\b")



def strip_html_tags(text):
    return re.sub('<.*?>', '', text)


def extract_page_index_from_url(pdf_url):
    match = re.search(r'#page=(\d+)', pdf_url)
    if match:
        page_number = int(match.group(1))
        return page_number - 1  # PyMuPDF indexe à partir de 0
    return None


def _normalize_addr_for_match(s: str) -> str:
    """
    Nettoie une adresse ou une fenêtre de texte pour améliorer les matches fuzzy :
    - supprime articles et ponctuation courante
    - normalise les espaces
    - met en minuscules
    """
    s = s.lower()
    s = re.sub(r"[,]", " ", s)
    s = re.sub(r"\b(à|la|le|les|de|du|des|au|aux|et|d’|l’|sur|dans)\b", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def _first_index_diff(addr: str, text: str, min_ratio: float = 0.65, ctx: int = 200) -> Optional[int]:
    """
    Retourne l'index de la 1ʳᵉ occurrence *fuzzy* de `addr` dans `text`.
    Stratégie :
      1) essai exact (rapide)
      2) si CP dans l'adresse -> fenêtres autour des CP dans le texte
      3) sinon, fenêtres glissantes
    Renvoie None si aucun score n’atteint `min_ratio`.
    """
    if not addr or not text:
        return None

    T = re.sub(r"\s+", " ", text)
    a = re.sub(r"\s+", " ", addr).strip()
    if not a:
        return None

    # 1) exact match
    m = re.search(re.escape(a), T, flags=re.IGNORECASE)
    if m:
        return m.start()

    # 2) collect spans (CP-based or sliding)
    spans = []
    mcp = POSTAL_RX.search(a)
    if mcp:
        # autour des CP dans le texte
        for hit in re.finditer(rf"\b{re.escape(mcp.group())}\b", T):
            s = max(0, hit.start() - ctx)
            e = min(len(T), hit.end() + ctx)
            spans.append((s, e))
    else:
        # fallback : fenêtres glissantes
        step = max(50, len(a) // 2 or 1)
        win = min(len(T), max(len(a) + 200, 250))
        for i in range(0, len(T), step):
            spans.append((i, min(len(T), i + win)))

    # 3) best fuzzy match in windows
    best_ratio, best_pos = 0.0, None
    a_norm = _normalize_addr_for_match(a)

    for s, e in spans:
        window = T[s:e]
        window_norm = _normalize_addr_for_match(window)
        sm = difflib.SequenceMatcher(a=window_norm, b=a_norm)
        ratio = sm.ratio()
        if ratio >= min_ratio and ratio > best_ratio:
            mlong = sm.find_longest_match(0, len(window_norm), 0, len(a_norm))
            if mlong and mlong.size > 0:
                best_ratio, best_pos = ratio, s + mlong.a

    return best_pos


def prioriser_adresse_proche_nom_struct(nom: Any, texte: str, adresses: List[str], *, min_ratio: float = 0.80) -> List[str]:
    """
    Réordonne `adresses` pour mettre en tête celle(s) trouvée(s) *à droite* du nom dans le texte,
    la plus proche d'abord. Le repérage d'adresse utilise un match *fuzzy* (difflib).

    - nom : dict (records/canonicals/aliases_flat) ou str/list
    - texte : texte brut
    - adresses : list[str] (déjà nettoyées)
    - min_ratio : seuil difflib (0.0–1.0), défaut 0.80
    """
    if not adresses or not isinstance(adresses, list):
        return adresses

    # 1) flatten des noms possibles depuis la structure
    def _flat_names(n) -> List[str]:
        out = []
        if isinstance(n, dict):
            out += [c for c in (n.get("canonicals") or []) if isinstance(c, str)]
            out += [a for a in (n.get("aliases_flat") or []) if isinstance(a, str)]
            for r in (n.get("records") or []):
                c = r.get("canonical")
                if isinstance(c, str):
                    out.append(c)
        elif isinstance(n, (list, tuple, set)):
            out = [s for s in n if isinstance(s, str)]
        elif isinstance(n, str):
            out = [n]

        # dédup en conservant l'ordre
        seen, res = set(), []
        for s in out:
            if s and s not in seen:
                seen.add(s)
                res.append(s)
        return res

    noms = _flat_names(nom)
    if not noms:
        return adresses

    # 2) position du nom (on prend la 1ʳᵉ occurrence trouvée en exact, insensible à la casse)
    T = re.sub(r"\s+", " ", texte or "")
    name_pos = name_end = None
    for candidate in noms:
        m = re.search(re.escape(candidate), T, flags=re.IGNORECASE)
        if m:
            name_pos, name_end = m.start(), m.end()
            break
    if name_pos is None:
        # pas de nom localisé -> on ne réordonne pas
        return adresses

    # 3) pour chaque adresse, on cherche un index fuzzy
    right_with_dist = []
    rest_in_order = []

    for addr in adresses:
        idx = _first_index_diff(addr, T, min_ratio=min_ratio)
        if idx is not None and idx >= name_end:
            right_with_dist.append((idx - name_end, addr))
        else:
            rest_in_order.append(addr)

    # 4) tri par distance croissante pour celles à droite, puis concat
    right_with_dist.sort(key=lambda x: x[0])
    ordered = [a for _, a in right_with_dist] + rest_in_order
    return ordered


# --------------------------------------------------------------------------------------
# UNICODE_SPACES_MAP : Créer un dictionnaire de correspondance Unicode
# pour remplacer certains espaces spéciaux invisibles par un espace standard (" ").
# _norm_spaces :
# --------------------------------------------------------------------------------------
UNICODE_SPACES_MAP = dict.fromkeys(map(ord, "\u00A0\u202F\u2007\u2009\u200A\u200B"), " ")

def _norm_spaces(s: str) -> str:
    s = (s or "").translate(UNICODE_SPACES_MAP).replace("\xa0", " ").replace("\u202f", " ")
    return re.sub(r"\s+", " ", s).strip()

def digits_only(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def _pick(*vals: str) -> str:
    """Retourne le premier non-vide (après strip)."""
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
    suf_alt  = "NL" if lang == "FR" else "FR"

    street = _pick(row.get(f"Street{suf_main}"), row.get(f"Street{suf_alt}"))
    muni   = _pick(row.get(f"Municipality{suf_main}"), row.get(f"Municipality{suf_alt}"))
    country= _pick(row.get(f"Country{suf_main}"), row.get(f"Country{suf_alt}"))

    zipcode = (row.get("Zipcode") or "").strip()
    number  = (row.get("HouseNumber") or "").strip()
    box     = (row.get("Box") or "").strip()
    extra   = (row.get("ExtraAddressInfo") or "").strip()

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

# Filtre public (rapide, tu as déjà viré les 0200 du fichier mais on garde la sécurité)
def is_entite_publique(entite_bce: str) -> bool:
    s = re.sub(r"\D", "", entite_bce or "")
    if len(s) == 9:
        s = "0" + s
    return s.startswith("0200")

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
    "un":1,"une":1,"deux":2,"trois":3,"quatre":4,"cinq":5,"six":6,"sept":7,"huit":8,"neuf":9,
    "dix":10,"onze":11,"douze":12,"quinze":15,"vingt":20
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
    print(f"voici la liste !!!!!!!!!!!!!!!!!!!!!!!!!!!!!{noms}")
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

