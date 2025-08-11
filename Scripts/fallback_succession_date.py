import re
import difflib
from datetime import date

MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2,
    "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
    "août": 8, "aout": 8, "septembre": 9, "octobre": 10,
    "novembre": 11, "décembre": 12, "decembre": 12
}


def strip_accents(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


month_keys = list(MONTHS.keys())
month_keys_norm = [strip_accents(k) for k in month_keys]


def guess_month(token, cutoff=0.6):
    t_norm = strip_accents(token)
    best = difflib.get_close_matches(t_norm, month_keys_norm, n=1, cutoff=cutoff)
    if best:
        idx = month_keys_norm.index(best[0])
        return MONTHS[month_keys[idx]]
    return None


def find_dates_fr(text):
    pattern = re.compile(r"\b(\d{1,2})(?:er)?\s+([A-Za-zÀ-ÿ\-\.]+)\s+(\d{4})\b")
    out = []
    for m in pattern.finditer(text):
        day = int(m.group(1))
        month_token = m.group(2).strip(" .,-;:!?)(")
        year = int(m.group(3))
        month_num = guess_month(month_token)
        if month_num:
            try:
                out.append(date(year, month_num, day).isoformat())
            except ValueError:
                pass
    return out
