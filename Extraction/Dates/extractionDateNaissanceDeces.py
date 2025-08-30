import re
import unicodedata
from datetime import date, datetime
from bs4 import BeautifulSoup, NavigableString, Tag
from Constante.mesconstantes import _MOISMAP_NORM

DECEDE_ANCHOR = r"\b(d[ée]c[èe]s|d[ée]c[ée]d[ée]e?s?|decede|dcd|mort[e]?|d[ée]funts?)\b"
DEATH_STOP_REGEX = r"\b(naiss[ance]?|acceptation|n[ée]e?\b|domicili[ée]?|registre\s+national|RN\b|NRN\b|adresse|demeurant|résid(?:ant|ence)|jugement|ordonnance|arr[ée]t)\b"
UPWORD = r"[A-ZÉÈÀÂÊÎÔÛÇÄËÏÖÜŸ][A-ZÉÈÀÂÊÎÔÛÇÄËÏÖÜŸ'’\-]{1,}"
NOM_BLOCK = rf"{UPWORD}(?:\s+{UPWORD}){{0,4}}"
PRENOM_WORD = r"[A-ZÉÈÀÂÊÎÔÛÇ][a-zà-öø-ÿ'’\-]{1,}"
# ========= Helpers uniques (pas de doublons) =========
def _extract_after_anchor(text: str, anchor_regex: str, window: int = 120,
                          stop_regex: str | None = None) -> list[str]:
    out, seen = [], set()
    for m in re.finditer(anchor_regex, text, flags=re.IGNORECASE):
        following = text[m.end(): m.end()+window]

        # 🔹 Coupe si un mot-clé stop apparaît (ex: "décédé", "décès")
        if stop_regex:
            stop_m = re.search(stop_regex, following, flags=re.IGNORECASE)
            if stop_m:
                following = following[:stop_m.start()]

        for frag in RECALL_DATE_PAT.findall(following):
            iso = _parse_date_fragment(frag)
            if iso and iso not in seen:
                seen.add(iso); out.append(iso)
    return out

def _norm_spaces(s: str) -> str:
    s = unicodedata.normalize("NFC", unicodedata.normalize("NFKC", s))
    s = (s.replace("\u00a0", " ")
           .replace("\u202f", " ")
           .replace("\u200b", "")
           .replace("\ufeff", " "))
    return re.sub(r"\s+", " ", s).strip()

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def _fix_1er_dupes(t: str) -> str:
    # "1er er" / "1 er er" --> "1er"; "1 er" --> "1er"; "1er." --> "1er"
    t = re.sub(r"\b1\s*(?:e?r\.?)\s*(?:e?r\.?)\b", "1er", t, flags=re.IGNORECASE)
    t = re.sub(r"\b1\s*e?r\b", "1er", t, flags=re.IGNORECASE)
    t = re.sub(r"\b1er\.\b", "1er", t, flags=re.IGNORECASE)
    return t

def _month_key(s: str) -> str:
    s = s.strip(" .;,:\t\r\n").lower().replace("’", "'")
    s = _strip_accents(s)          # "décembre"/"déc." -> "decembre"/"dec."
    s = s.replace("aoüt", "aout").replace("aoút", "aout").replace("a0ut", "aout")
    s = s.rstrip(".")              # "dec." -> "dec"

    # Abréviations FR usuelles (sans accents après _strip_accents)
    fr_abbr = {
        "janv": "janvier",
        "fevr": "fevrier", "fev": "fevrier",
        "avr": "avril",
        "juil": "juillet",
        "aou": "aout",
        "sept": "septembre", "sep": "septembre",
        "oct": "octobre",
        "nov": "novembre",
        "dec": "decembre",         # couvre "déc"/"déc."
    }
    if s in fr_abbr:
        s = fr_abbr[s]

    # Anglais -> FR
    en_to_fr = {
        "january": "janvier", "jan": "janvier",
        "february": "fevrier", "feb": "fevrier",
        "march": "mars", "mar": "mars",
        "april": "avril", "apr": "avril",
        "may": "mai",
        "june": "juin", "jun": "juin",
        "july": "juillet", "jul": "juillet",
        "august": "aout", "aug": "aout",
        "september": "septembre", "sep": "septembre",
        "october": "octobre", "oct": "octobre",
        "november": "novembre", "nov": "novembre",
        "december": "decembre", "dec": "decembre",
    }
    if s in en_to_fr:
        s = en_to_fr[s]

    return re.sub(r"[^a-z]", "", s)  # ex: "decembre"


def _valid(y: int, m: int, d: int) -> bool:
    try:
        datetime(y, m, d); return True
    except ValueError:
        return False

def _to_iso(d: int, m: int, y: int) -> str | None:
    return f"{y:04d}-{m:02d}-{d:02d}" if (1 <= m <= 12 and _valid(y, m, d)) else None

# Rappelle large pour dates (maximiser le recall)
RECALL_DATE_PAT = re.compile(
    r"(\d{1,2}[./-]\d{1,2}[./-]\d{4}"           # 01/09/2024
    r"|\d{4}[./-]\d{2}[./-]\d{2}"               # 2024-09-01
    r"|\d{1,2}(?:\s*er)?\s+[A-Za-zÀ-ÖØ-öø-ÿ\.\-']{2,20}\s+\d{4})",  # 1er sept. 2024
    re.IGNORECASE
)

RX_LIEU_DATE_NAISS = re.compile(r"""
    lieu\s*et\s*date\s*de\s*naissance      # le libellé
    \s*[:\-–]?\s*
    [^,\n\r]{0,200}?                        # la ville (souple)
    ,\s*
    (?:le\s*)?                              # "le" optionnel
    (?P<date>
        \d{1,2}[./-]\d{1,2}[./-]\d{4}              # 31/12/1980
      | \d{4}[./-]\d{2}[./-]\d{2}                  # 1980-12-31
      | \d{1,2}(?:\s*er)?\s+[A-Za-zÀ-ÖØ-öø-ÿ.'-]{2,20}\s+\d{4}  # 31 décembre 1980 / 1er déc. 1980
    )
""", re.IGNORECASE | re.VERBOSE)

def _parse_date_fragment(fragment: str) -> str | None:
    t = _fix_1er_dupes(fragment.strip())

    # dd/mm/yyyy | dd-mm-yyyy | dd.mm.yyyy
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", t)
    if m:
        d, mo, y = map(int, m.groups())
        return _to_iso(d, mo, y)

    # yyyy-mm-dd | yyyy/mm/dd | yyyy.mm.dd
    m = re.fullmatch(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", t)
    if m:
        y, mo, d = map(int, m.groups())
        return _to_iso(d, mo, y)

    # 1/1er + mois + yyyy
    m = re.fullmatch(r"(?:1|1er)\s+([A-Za-zÀ-ÖØ-öø-ÿ\.\-']{2,20})\s+(\d{4})", t, flags=re.IGNORECASE)
    if m:
        mk = _month_key(m.group(1))
        LOCAL_MOIS = {
            "janvier": "01", "fevrier": "02", "mars": "03", "avril": "04", "mai": "05", "juin": "06",
            "juillet": "07", "aout": "08", "septembre": "09", "octobre": "10", "novembre": "11", "decembre": "12"
        }
        mnum = _MOISMAP_NORM.get(mk) or LOCAL_MOIS.get(mk)
        y = int(m.group(2))
        if mnum and _valid(y, int(mnum), 1):
            return f"{y:04d}-{mnum}-01"

    # dd (2–31) + mois + yyyy
    m = re.fullmatch(r"([2-9]|[12]\d|3[01])\s+([A-Za-zÀ-ÖØ-öø-ÿ\.\-']{2,20})\s+(\d{4})", t, flags=re.IGNORECASE)
    if m:
        d = int(m.group(1));
        mk = _month_key(m.group(2));
        y = int(m.group(3))
        LOCAL_MOIS = {
            "janvier": "01", "fevrier": "02", "mars": "03", "avril": "04", "mai": "05", "juin": "06",
            "juillet": "07", "aout": "08", "septembre": "09", "octobre": "10", "novembre": "11", "decembre": "12"
        }
        mnum = _MOISMAP_NORM.get(mk) or LOCAL_MOIS.get(mk)

        if mnum:
            return _to_iso(d, int(mnum), y)

    return None


def extract_dates_after_decede(html: str, first_only: bool = True) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    text = _norm_spaces(soup.get_text(separator=" "))

    # On coupe la fenêtre aux mots-clés parasites (naissance, domicilé, RN, etc.)
    dates = _extract_after_anchor(
        text,
        DECEDE_ANCHOR,          # ← utilise la constante globale déjà définie
        window=140,             # tu peux mettre 110–160 selon tes textes
        stop_regex=DEATH_STOP_REGEX
    )

    # Si tu veux strictement la 1re date de décès (recommandé) :
    return dates[:1] if first_only else dates


def extract_date_after_birthday(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    text = _norm_spaces(soup.get_text(separator=" "))
    full_text = re.sub(r"\b(\d{1,2})\s*er\s*er\b", r"\1er", text)  # "1er er" -> "1er"
    full_text = re.sub(r"\b(\d{1,2})\s*er\b", r"\1", full_text)  # "1er" -> "1"
    # 1) même logique "ancre + fenêtre"
    birthday_anchor = r"(lieu\s+et\s+date\s+de\s+naissance\s*:?)|(n[ée](?:\(?e\)?)?\s+le)|(né[e]?\s+à)"
    dates = _extract_after_anchor(full_text, birthday_anchor,
                                  window=140,
                                  stop_regex=DECEDE_ANCHOR)
    # 2) (optionnel) motifs supplémentaires spécifiques aux RN/NN, etc.
    extra_patterns = [
        r"\(NN\s*(\d{2})[.\-/](\d{2})[.\-/](\d{2})",
        r"RN\s+(\d{2})[.\-/](\d{2})[.\-/](\d{2})",
    ]
    for pat in extra_patterns:
        for yy, mm, dd in re.findall(pat, text, flags=re.IGNORECASE):
            yy = int(yy); yyyy = 1900 + yy if yy > 30 else 2000 + yy
            iso = _to_iso(int(dd), int(mm), int(yyyy))
            if iso and iso not in dates:
                dates.append(iso)
    # 3) Fallback dédié au libellé "Lieu et date de naissance : Ville, le <DATE>"
    m_lbl = RX_LIEU_DATE_NAISS.search(full_text)
    if m_lbl:
        parsed = _parse_date_fragment(m_lbl.group("date"))
        if parsed and parsed not in dates:
            dates.append(parsed)

    return dates