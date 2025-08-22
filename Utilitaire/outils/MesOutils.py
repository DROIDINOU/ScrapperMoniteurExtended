# --- Imports standards ---
import re
import os
import hashlib

# --- Bibliothèques tierces ---
from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

# --- Modules internes au projet ---
from Constante.mesconstantes import VILLES, JOURMAP, MOISMAP, ANNEMAP, JOURMAPBIS, MOISMAPBIS, \
    ANNEEMAPBIS, EXCLUDEDSOURCES, SOCIETESABRV, SOCIETESFORMELLES, BASE_URL


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

def chemin_csv(nom_fichier: str) -> str:
    return os.path.abspath(os.path.join("Datas", nom_fichier))

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
    return [x for x in tvas if not (x in seen or seen.add(x))]


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


