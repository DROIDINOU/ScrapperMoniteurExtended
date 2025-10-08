import re
from bs4 import BeautifulSoup

def extract_noms_entreprises_radiees(texte_html: str, doc_id: str | None = None) -> list[str]:
    """
    Extrait les noms d'entreprises après chaque 'N° ent. <BCE>'.
    Règles d'arrêt :
      - mot commençant par une minuscule
      - mot commençant par Majuscule suivie de minuscule (ex: En, Pour, Concept...)
    Seuls les tokens FULL UPPER sont gardés.
    """

    # Décodage si bytes
    if isinstance(texte_html, bytes):
        try:
            texte_html = texte_html.decode("utf-8", errors="ignore")
        except Exception:
            texte_html = texte_html.decode("latin-1", errors="ignore")

    # Texte brut
    try:
        soup = BeautifulSoup(texte_html, "html.parser")
        full_text = soup.get_text(separator=" ")
    except Exception:
        full_text = str(texte_html)

    results = []
    bce_rx = re.compile(r"N[°º]?\s*ent\.?\s*(\d{4}\.\d{3}\.\d{3})")

    for m in bce_rx.finditer(full_text):
        start = m.end()
        tail = full_text[start:].strip()

        tokens = tail.split()
        name_parts = []

        for tok in tokens:
            # stop si minuscule ou Maj+minuscule
            if re.match(r"^[a-z]", tok) or re.match(r"^[A-Z][a-z]", tok):
                break
            # garder uniquement full majuscules
            if tok.isupper():
                name_parts.append(tok)
            else:
                break

        if name_parts:
            name = " ".join(name_parts)
            name = re.sub(r"\s{2,}", " ", name).strip(" .,:;")
            results.append(name)

    # dédup
    seen = set()
    final = []
    for r in results:
        if r not in seen:
            seen.add(r)
            final.append(r)

    return final
