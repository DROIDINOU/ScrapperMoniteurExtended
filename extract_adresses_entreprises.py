# --- Imports standards ---
import logging
import re
import csv
import unicodedata

# --- Bibliothèques tierces ---
# --- Configuration du logger ---
logger = logging.getLogger("extraction")
loggerfallback3 = logging.getLogger("fallback3")


def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')

# =========================
# 📜 Chargement des noms de rue dans un set
# =========================
noms_de_rue = set()

with open('STREETS_ALL.csv', newline='', encoding='latin1') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        nom_complet = row['ICAR_NOM_RUE'].strip().upper()
        if nom_complet:
            nom_sans_accents = strip_accents(nom_complet)
            if "-" in nom_sans_accents:
                noms_de_rue.add(nom_sans_accents.replace("-", " "))
            if nom_sans_accents.startswith("EN "):
                print(nom_sans_accents)
                noms_de_rue.add(nom_sans_accents)
            else:
                noms_de_rue.add("NEBLON-LE-MOULIN")
                premier_mot = nom_sans_accents.split()[0]
                noms_de_rue.add(premier_mot)

# =========================
# 📌 Regex fixes (précompilées une seule fois)
# =========================
ADRESSE_REGEX_bis = r"(RUE|R\.|AVENUE|AV\.|COURS|COUR|CHEE|GRAND ROUTE|CHAUSS[ÉE]E|ROUTE|RTE|PLACE|PL\.?|BOULEVARD|BD|CHEMIN|CH\.?|GALERIE|IMPASSE|SQUARE|ALL[ÉE]E|CLOS|RESIDENCE|VOIE|RY|PASSAGE|QUAI|PARC|Z\.I\.?|ZONE|SITE|PROMENADE|FAUBOURG|FBG|QUARTIER|CITE|DREVE|HAMEAU|LOTISSEMENT|NEBLON)"
FLAMAND_ADRESSE_REGEX = r"(STRAAT|STRAATJE|LAAN|DREEF|STEENWEG|WEG|PLEIN|LEI|BAAN|HOF|KAAI|DRIES|MARKT|KANAAL|BERG|ZUID|NOORD|OOST|WEST|DOORN|VELD|NIEUWBUITENSTRAAT|VOORSTAD|BUITENWIJK|DORP|GEDEELTE|WIJK)"
GERMAN_ADRESSE_REGEX = r"(STRASSE|STR\.?|PLATZ|ALLEE|WEG|RING|GASSE|DORF|BERG|TOR|WALD|STEIG|MARKT|HOF|GARTENVORSTADT|STADTTEIL|STADTRAND|ORTSTEIL|AUSSENBEREICH)"

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
    "FPEU", "PPEU", "SComm", "SRL DPU", "ScommDPU", "SC", "SC DPU",
    "VOG", "GMBH", "UG", "AG", "EV", "E.V.", "GMBH & CO. KG", "OHG",
    "KG", "GMBH & CO KG"
]
FORM_PATTERN = "|".join(re.escape(f) for f in FORMS)

ADRESSE_PREFIXES = rf"({ADRESSE_REGEX_bis}|{FLAMAND_ADRESSE_REGEX}|{GERMAN_ADRESSE_REGEX})"

ADDRESS_UNTIL_POSTAL = rf"""
    (?<![A-ZÉ])
    \b{ADRESSE_PREFIXES}
    (?:\s+[^\d]{{1,}}){{0,6}}
    \s+
    (?:\d+[A-Z]*\s?[A-Z]?                          
        (?:\s*(?:BTE|BOX|BP|BOITE)\s*\d+)?         
        (?:[\/\+-][0-9A-Z]+(?:\s[0-9A-Z]+)*)*
      |[A-Z]+\d+(?:[\/\+-][0-9A-Z]+(?:\s[0-9A-Z]+)*)*
      |S\.?N\.?
    )
    ,?\s*\d{{4,5}}
    (?=\s|,|\.|$)
"""

ADRESSE_PREFIXES_FILTRE = r"(RUE|R\.|AVENUE|COURS|COUR|AV\.|CHEE|CHAUSS[ÉE]E|ROUTE|RTE|PLACE|PL\.?|BOULEVARD|BD|CHEMIN|CH\.?|GALERIE|IMPASSE|SQUARE|ALL[ÉE]E|CLOS|VOIE|RY|PASSAGE|QUAI|PARC|Z\.I\.?|ZONE|SITE|PROMENADE|FAUBOURG|FBG|QUARTIER|CITE|HAMEAU|LOTISSEMENT|RESIDENCE)"

ADDRESS_FALLBACK_NO_PREFIX = rf"""
    (?:
        [A-ZÉÈÀÙÂÊÎÔÛÇ]+(?:\s+[A-ZÉÈÀÙÂÊÎÔÛÇ]+)*
    )
    (?:\s+[^\d\s,\.]{{0,6}})?
    \s+(?:\d+[A-Z]*|[A-Z]+\d+|S\.?N\.?) (?:[\/\+-]?[0-9A-Z]+)?
    (?:[\/\+-][0-9A-Z]+)?
    ,?\s*\d{{4,5}}?
    (?=\s|,|\.|$)
"""

# 📌 Regex précompilées
RE_FORM_PATTERN = re.compile(rf"\b({FORM_PATTERN})\b")
RE_ADRESSE_PREFIXES_FILTRE = re.compile(rf"\b{ADRESSE_PREFIXES_FILTRE}\b", flags=re.IGNORECASE)
RE_ADRESSE_PREFIXES = re.compile(rf"\b{ADRESSE_PREFIXES}\b", flags=re.IGNORECASE)
RE_ADDRESS_UNTIL_POSTAL = re.compile(ADDRESS_UNTIL_POSTAL, flags=re.IGNORECASE | re.VERBOSE)
RE_ADDRESS_FALLBACK_NO_PREFIX = re.compile(ADDRESS_FALLBACK_NO_PREFIX, flags=re.IGNORECASE | re.VERBOSE)

# =========================
# 🧹 Nettoyage adresse
# =========================
def nettoyer_adresse(adresse):
    if not adresse:
        return None, False
    if "AVENUE DU 11E" in adresse:
        print(f"elle est bien trouvée c est pas les lignes: {adresse}")
    alerte = False

    match = RE_FORM_PATTERN.search(adresse)
    if match:
        avant_forme = adresse[:match.start()]
        if RE_ADRESSE_PREFIXES_FILTRE.search(avant_forme):
            alerte = True
        adresse = adresse[match.end():].strip()

    match2 = RE_ADRESSE_PREFIXES_FILTRE.search(adresse)
    if match2:
        adresse = adresse[match2.start():]

    adresse = re.sub(r"\s+", " ", adresse).strip(" ,.-")

    if len(adresse) < 5:
        return None, alerte

    return adresse, alerte

# =========================
# 🔍 Extraction
# =========================
def extract_add_entreprises(texte, doc_id=None):
    texte = re.sub(r'\s+', ' ', texte).strip().upper()
    lignes = texte.splitlines()
    lignes = [l.strip() for l in lignes if l.strip()][:8]

    for ligne in lignes:
        # D'abord vérifier un préfixe rapide
        if not RE_ADRESSE_PREFIXES.search(ligne):
            continue

        # Puis vérifier si un mot de la ligne est dans noms_de_rue
        if not any(mot in noms_de_rue for mot in ligne.split()):
            continue

        # Match avec code postal
        fallback = RE_ADDRESS_UNTIL_POSTAL.search(ligne)
        if fallback:
            adresse_nettoyee_fallback = nettoyer_adresse(fallback.group(0).strip())
            if adresse_nettoyee_fallback:
                logger.debug(f"↪️ [Extraction adresse entreprise avec post verif]{f' ID={doc_id}' if doc_id else ''} Résultat : {adresse_nettoyee_fallback}")
                return adresse_nettoyee_fallback

    # Fallback sans préfixe
    for ligne in lignes:
        if any(mot in noms_de_rue for mot in ligne.split()):
            fallback_no_prefix = RE_ADDRESS_FALLBACK_NO_PREFIX.search(ligne)
            if fallback_no_prefix:
                loggerfallback3.debug(f"↪️ [Fallback Extractionbis]{f' ID={doc_id}' if doc_id else ''} Résultat : {fallback_no_prefix}")
                return fallback_no_prefix.group(0).strip()

    if doc_id:
        loggerfallback3.debug(f"↪️ [Fallback ExtractionId]{f' ID={doc_id}' if doc_id else ''} Aucune adresse trouvée")
        print(f"❌ ID : {doc_id} | aucune adresse trouvée dans les 5 premières lignes")
    return None
