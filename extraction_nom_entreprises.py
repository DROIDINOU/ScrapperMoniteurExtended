from logger_config import setup_logger

logger = setup_logger(__name__)

from bs4 import BeautifulSoup
import re

# ─────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────

ADRESSE_REGEX = r"(RUE|R\.|AVENUE|AV\.|CHEE|CHAUSS[ÉE]E|PLACE|PL\.?|BOULEVARD|BD|CHEMIN|GALERIE|IMPASSE|SQUARE|ALLEE|CLOS|VOIE|RY|DREEF|STRAAT|LAAN)"
FLAMAND_ADRESSE_REGEX = r"(STRAAT|LAAN|DREEF|STEENWEG|WEG|PLEIN|LEI|BAAN|HOF|KAAI|DRIES|MARKT)"

DECLENCHEURS = [
    r"homologation\s+du\s+plan\s+de",
    r"faillite\s+de",
    r"dissolution(?:\s+judiciaire)?\s+de",
    r"réorganisation\s+judiciaire\s+de",
    r"accord\s+amiable\s+de",
    r"(?:[A-Za-z'\s]+)?plan\s+de\s+la\s+réorganisation\s+judiciaire\s+de",
    r"ouverture\s+de\s+la\s+réorganisation\s+judiciaire\s+de",
    r"en\s+application\s+de\s+l['’]?\s*art\.?\s*XX\.?30\s*CDE\s+pour"
]

FORMS = [
    "SA", "SPRL", "SRL", "SNC", "SCA", "SCS", "SCRL", "SSF", "SETR", "S.Agr.",
    "GEIE", "GIE", "ASBL", "ASS. ASSURANCES M.", "SCOO", "SCRI",
    "UNION PROFES.", "ASS. DE DROIT PUB.", "ASS. INTERNATIONALE",
    "FOND. D'UTIL. PUBLI.", "FONDATION PRIVEE", "SOCIETE EUROPEENNE",
    "ASSOCIATION DE PROJET", "DIENSTVERLENENDE VER", "ASS. C. DE MISSION",
    "REGIE COMMUNALE AUTONOME", "SC SA", "SC SPRL", "OFP", "SC SCRL",
    "SC SCA", "SC SNC", "SC SCS", "SC SCRI", "ASF", "SC GIE", "SC AG",
    "SCE", "MUT", "COM SIM FIN SOCIAL", "SCRI", "GIE", "GEIE", "AEP",
    "CAISSE COM. D'ASSU.", "REGIE PROVINCIALE AUTONOME",
    "FPEU", "PPEU", "SComm", "SRL DPU", "ScommDPU", "SC", "SC DPU"
]

# ─────────────────────────────────────────────────────────────
# FONCTIONS UTILITAIRES
# ─────────────────────────────────────────────────────────────

def fallback_nom_extraction(text, forms, doc_id=None):
    fallbackgroup = []
    escaped_forms = [re.escape(f) for f in forms]
    form_regex = r"(?:\(?\s*(?:" + "|".join(escaped_forms) + r")(?:\s*\([A-Z]{2,5}\))?\s*\)?)"
    head_text = text[:300]

    patterns = [
        rf"({form_regex})\s+([A-ZÉÈÀÙÂÊÎÔÛÇ0-9&.\-']{{2,}}(?:\s+[A-ZÉÈÀÙÂÊÎÔÛÇ0-9&.\-']{{2,}}){{0,3}})",
        rf"([A-ZÉÈÀÙÂÊÎÔÛÇ0-9&.\-']{{2,}}(?:\s+[A-ZÉÈÀÙÂÊÎÔÛÇ0-9&.\-']{{2,}}){{0,3}})\s+({form_regex})",
        rf"((?:[A-ZÉÈÀÙÂÊÎÔÛÇ0-9&.\-']+\s+){{1,3}})(?=\s*{form_regex})"
    ]

    for pat in patterns:
        match = re.search(pat, head_text)
        if match:
            groups = match.groups()
            nom = " ".join(g.strip() for g in groups if g)
            fallbackgroup.append(nom)
            break

    if not fallbackgroup:
        match = re.search(
            r"([A-ZÉÈÀÙÂÊÎÔÛÇ0-9&.\-']{2,}(?:\s+[A-ZÉÈÀÙÂÊÎÔÛÇ0-9&.\-']{2,}){0,4})",
            head_text
        )
        if match:
            fallbackgroup.append(match.group(1).strip())
    logger.debug(f"↪️ [Fallback Extraction]{f' ID={doc_id}' if doc_id else ''} Résultat : {fallbackgroup}")
    return fallbackgroup


def extract_nom_forme(text, déclencheur, form_regex, nom_list, is_nl=False):
    ending = (
        rf"(?=\s+(?:BCE\s+\d{{4}}[.\d]+|{ADRESSE_REGEX}\s+[A-Z]|{FLAMAND_ADRESSE_REGEX}\s+[A-Z]))"
        if not is_nl else
        rf"(?=\s+[A-ZÉÈÊÀÂ'\-]+(?:\s+\d{{1,4}})?(?:,|\s))"
    )

    pattern = rf"""
        {déclencheur}\s*:?\s*
        (?:
            \(?(?P<forme1>{form_regex})\)?\s+(?P<nom1>(?:[A-Z0-9&.\-']+\s*){{1,5}})
            |
            (?P<nom2>(?:[A-Z0-9&.\-']+\s*){{1,5}})\s*\(?(?P<forme2>{form_regex})\)?
        )
        {ending}
    """
    matches = re.findall(pattern, text, flags=re.IGNORECASE | re.DOTALL | re.VERBOSE)
    for m in matches:
        forme = m[0] or m[3]
        nom = m[1] or m[2]
        if forme and nom:
            # ⚠️ Toujours remettre le nom suivi de la forme
            nom_complet = f"{nom.strip()} {forme.strip()}"
            nom_list.append(nom_complet)


def extract_by_patterns(text, patterns, nom_list, flags=re.IGNORECASE | re.DOTALL):
    for pat in patterns:
        matches = re.findall(pat, text, flags=flags)
        for m in matches:
            nom_list.append(m.strip() if isinstance(m, str) else m[0].strip())


# ─────────────────────────────────────────────────────────────
# MAIN FUNCTION
# ─────────────────────────────────────────────────────────────

def extract_noms_entreprises(texte_html, doc_id=None):
    soup = BeautifulSoup(texte_html, 'html.parser')
    full_text = soup.get_text(separator=" ").strip()

    form_regex = '|'.join(re.escape(f) for f in FORMS)
    nom_list = []
    flags = re.IGNORECASE | re.DOTALL

    # 🔹 Extractions simples
    simple_patterns = [
        r"ouverture\s+de\s+la\s+faillite\s*:?\s*.{0,40}?\b((?:[A-Z0-9&.\-']+\s*){1,5})",
        r"a\s+condamné\s*:?\s*.{0,40}?\b((?:[A-Z0-9&.\-']+\s*){1,5})",
        r"clôture\s+de(?:\s+la\s+liquidation)?\s*:?\s*.{0,40}?\b((?:[A-Z0-9&.\-']+\s*){1,5})",
        r"dissolution(?:\s+judiciaire)?\s*:?\s*.{0,40}?\b((?:[A-Z0-9&.\-']+\s*){1,5})",
        r"faillite\s+de\s*:?\s*.{0,40}?\b((?:[A-Z0-9&.\-']+\s*){1,5})"
    ]
    extract_by_patterns(full_text, simple_patterns, nom_list)

    # 🔹 Cas avec adresses, procureur, etc.
    adresse_patterns = [
        rf"faillite\s+de\s*:?\s*(?:Monsieur|Madame)?\.?\s*((?:[A-ZÉÈÊÀÂ'\-]+\s*){{1,4}})(?=,\s*{ADRESSE_REGEX})",
        rf"faillite\s+de\s*:?\s*(?:Monsieur|Madame)?\.?\s*((?:[A-ZÉÈÊÀÂ'\-]+\s*){{1,4}})(?=,\s*{FLAMAND_ADRESSE_REGEX})",
        rf"faillite\s+de\s*:?\s*((?:[A-ZÉÈÊÀÂ'\-]+\s*){{1,5}})(?=\s*,?\s*C\s*/\s*O\s+PROCUREUR\s+DU\s+ROI)",
        rf"pour\s*:?\s*((?:[A-ZÉÈÊÀÂ'\-]+\s*){{1,5}})(?=,\s*{ADRESSE_REGEX})",
        rf"pour\s*:?\s*((?:[A-ZÉÈÊÀÂ'\-]+\s*){{1,5}})(?=,\s*{FLAMAND_ADRESSE_REGEX})",
        rf"homologation\s+du\s+plan\s+de\s*:?\s*((?:[A-ZÉÈÊÀÂ'\-]+\s*){{1,5}})(?=,\s*{ADRESSE_REGEX})",
        rf"homologation\s+du\s+plan\s+de\s*:?\s*((?:[A-ZÉÈÊÀÂ'\-]+\s*){{1,5}})(?=,\s*{FLAMAND_ADRESSE_REGEX})",
        rf"réorganisation\s+judiciaire\s+de\s*:?\s*((?:[A-ZÉÈÊÀÂ'\-]+\s*){{1,5}})(?=,\s*{ADRESSE_REGEX})",
        rf"réorganisation\s+judiciaire\s+de\s*:?\s*((?:[A-ZÉÈÊÀÂ'\-]+\s*){{1,5}})(?=,\s*{FLAMAND_ADRESSE_REGEX})",
        rf"ouverture\s+de\s+la\s+réorganisation\s+judiciaire\s+de\s*:?\s*((?:[A-ZÉÈÊÀÂ'\-]+\s*){{1,5}})(?=,\s*{ADRESSE_REGEX})",
        rf"ouverture\s+de\s+la\s+réorganisation\s+judiciaire\s+de\s*:?\s*((?:[A-ZÉÈÊÀÂ'\-]+\s*){{1,5}})(?=,\s*{FLAMAND_ADRESSE_REGEX})",
        rf"dissolution(?:\s+judiciaire)?(?:\s+et\s+clôture\s+immédiate)?\s+de\s*:?\s*([^,]{{5,150}}?)(?=,\s*{ADRESSE_REGEX})",
        rf"dissolution(?:\s+judiciaire)?(?:\s+et\s+clôture\s+immédiate)?\s+van\s*:?\s*([^,]{{5,150}}?)(?=,\s*{FLAMAND_ADRESSE_REGEX})"
    ]
    extract_by_patterns(full_text, adresse_patterns, nom_list)

    # 🔹 Extraction via déclencheurs + formes juridiques
    for déclencheur in DECLENCHEURS:
        extract_nom_forme(full_text, déclencheur, form_regex, nom_list, is_nl=False)
        extract_nom_forme(full_text, déclencheur, form_regex, nom_list, is_nl=True)

    # 🔹 Nettoyage doublons
    seen = set()
    noms_uniques = []
    for nom in nom_list:
        nom_clean = re.sub(r"\s+", " ", nom.strip())
        nom_clean = re.sub(r"-\s*$", "", nom_clean)
        if nom_clean and nom_clean.lower() not in {"de", "et cl"} and nom_clean not in seen:
            noms_uniques.append(nom_clean)
            seen.add(nom_clean)

    # Fallback avec log d'ID
    if not noms_uniques:
            print("le fall back a été activé..........................................................................")
            logger.warning(f"⚠️ Fallback activé pour le document ID={doc_id}")
            noms_uniques = fallback_nom_extraction(full_text, FORMS, doc_id)
            if noms_uniques:
                logger.info(f"✅ Fallback réussi pour ID={doc_id} : {noms_uniques}")
            else:
                logger.error(f"❌ Fallback échoué pour ID={doc_id} — aucun nom trouvé.")

    return noms_uniques
