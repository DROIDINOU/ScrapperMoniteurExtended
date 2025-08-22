import re

PARTICULES = {
    "de","du","des","d","d'","da","das","do","dos","del","della","di",
    "van","von","der","den","le","la","les","mc","mac","o'","st","ste"
}

TITRES = r"(?:M(?:me|lle|\.?)|Monsieur|Madame|Ma(?:ître|itre|e)|Me|Dr|Docteur|Pr|Prof(?:esseur)?|Maître)\s+"
NAMEWORD = r"[A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ'’]*(?:-[A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ'’]*)*"
PART = r"(?:\s+(?:de|du|des|d|d'|da|das|do|dos|del|della|di|van|von|der|den|le|la|les|o'))?"

PAT_NOM_CANDIDAT = re.compile(
    rf"(?:{TITRES})?"
    rf"("
    rf"{NAMEWORD}"
    rf"(?:{PART}\s+{NAMEWORD}){{1,5}}"
    rf")\s*(?=,|\bet\b|à\b|—|-|–|\.|\)|$)",
    flags=re.UNICODE
)

def _compte_mots_nom(nom: str) -> int:
    tokens = [t for t in nom.strip().split() if t]
    compte = 0
    for t in tokens:
        t_clean = t.strip(" ,.;:()[]{}\"'’—–-")
        tl = t_clean.lower()
        if tl in PARTICULES:
            continue
        if re.match(rf"^{NAMEWORD}$", t_clean):
            compte += 1
        elif re.match(r"^[A-ZÀ-ÖØ-Ý]['’][A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ'’]*$", t_clean):
            compte += 1
    return compte

def extract_person_names(text: str) -> list[str]:
    """
    Extrait des noms propres comptant entre 2 et 4 mots-noms (hors particules).
    """
    out, seen = [], set()
    for m in PAT_NOM_CANDIDAT.finditer(text):
        nom = m.group(1).strip(" ,.;:()[]{}")
        n = _compte_mots_nom(nom)
        if 2 <= n <= 4:
            nom_norm = re.sub(r"\s+", " ", nom)
            if nom_norm not in seen:
                seen.add(nom_norm)
                out.append(nom_norm)
    return out
