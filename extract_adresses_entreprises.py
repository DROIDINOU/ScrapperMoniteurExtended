import logging
logger = logging.getLogger("extraction")
loggerfallback3 = logging.getLogger("fallback3")

from bs4 import BeautifulSoup
import re
import csv
import unicodedata


def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')

noms_de_rue = set()

# Lire le fichier avec un encodage tolérant
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
                noms_de_rue.add(nom_sans_accents)  # prendre tout
            else:
                noms_de_rue.add("NEBLON-LE-MOULIN")
                premier_mot = nom_sans_accents.split()[0]
                noms_de_rue.add(premier_mot)

escaped_noms = [re.escape(nom) for nom in sorted(noms_de_rue)]
# Construire la regex avec les noms joints par |
ADRESSE_REGEX = r"("+"|".join(sorted(escaped_noms)) + ")"
# Préfixes d'adresse (FR, NL, DE)
ADRESSE_REGEX_bis = r"(RUE|R\.|AVENUE|AV\.|COURS|COUR|CHEE|GRAND ROUTE|CHAUSS[ÉE]E|ROUTE|RTE|PLACE|PL\.?|BOULEVARD|BD|CHEMIN|CH\.?|GALERIE|IMPASSE|SQUARE|ALL[ÉE]E|CLOS|RESIDENCE|VOIE|RY|PASSAGE|QUAI|PARC|Z\.I\.?|ZONE|SITE|PROMENADE|FAUBOURG|FBG|QUARTIER|CITE|DREVE|HAMEAU|LOTISSEMENT)"
FLAMAND_ADRESSE_REGEX = r"(STRAAT|STRAATJE|LAAN|DREEF|STEENWEG|WEG|PLEIN|LEI|BAAN|HOF|KAAI|DRIES|MARKT|KANAAL|BERG|ZUID|NOORD|OOST|WEST|DOORN|VELD|NIEUWBUITENSTRAAT|VOORSTAD|BUITENWIJK|DORP|GEDEELTE|WIJK)"
GERMAN_ADRESSE_REGEX = r"(STRASSE|STR\.?|PLATZ|ALLEE|WEG|RING|GASSE|DORF|BERG|TOR|WALD|STEIG|MARKT|HOF|GARTENVORSTADT|STADTTEIL|STADTRAND|ORTSTEIL|AUSSENBEREICH)"

# abréviations sociétés en FR et NL
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

# Préparer un pattern regex avec tous les forms
FORM_PATTERN = "|".join(re.escape(f) for f in FORMS)

ADRESSE_PREFIXES = rf"({ADRESSE_REGEX}|{FLAMAND_ADRESSE_REGEX}|{GERMAN_ADRESSE_REGEX})"

ADDRESS_UNTIL_NUMBER = rf"""
    (?<![A-ZÉ])
    \b{ADRESSE_PREFIXES}
    (?:\s+[^\d\s,\.]{{1,}}){{0,6}}
    \s+(?:\d+[A-Z]*|[A-Z]+\d+|S\.?N\.?) (?:[\/\+-]?[0-9A-Z]+)?\
    (?:[\/\+-][0-9A-Z]+)?                 
    ,?
    (?=\s|,|\.|$)
"""

ADDRESS_UNTIL_POSTAL = rf"""
    (?<![A-ZÉ])
    \b{ADRESSE_PREFIXES}
    (?:\s+[^\d\s,]{{1,}}){{0,6}}
    \s+(?:\d+[A-Z]*|S\.?N\.?) (?:[\/\+-][0-9A-Z]+)?
    ,?\s*\d{{4,5}}
    (?=\s|,|\.|$)
"""
ADRESSE_PREFIXES_FILTRE = r"(RUE|R\.|AVENUE|COURS|COUR|AV\.|CHEE|CHAUSS[ÉE]E|ROUTE|RTE|PLACE|PL\.?|BOULEVARD|BD|CHEMIN|CH\.?|GALERIE|IMPASSE|SQUARE|ALL[ÉE]E|CLOS|VOIE|RY|PASSAGE|QUAI|PARC|Z\.I\.?|ZONE|SITE|PROMENADE|FAUBOURG|FBG|QUARTIER|CITE|HAMEAU|LOTISSEMENT|RESIDENCE)"


# A TESTER
r"""def nettoyer_adresse(adresse):
    if not adresse:
        return None

    # 1. Essayer de couper après la forme juridique (si précédée d’un tiret)
    match = re.search(rf".*?[-–—]\s*\(?({FORM_PATTERN})\)?\s*[:-]?\s*", adresse)
    if match:
        adresse = adresse[match.end():]

    # 2. Supprimer formes juridiques résiduelles
    adresse = re.sub(rf"\b({FORM_PATTERN})\b", "", adresse)

    # 3. Si on a déjà coupé après le nom, on peut commencer à chercher le préfixe
    match2 = re.search(rf"\b{ADRESSE_PREFIXES_FILTRE}\b", adresse, flags=re.IGNORECASE)
    if match2:
        # ⚠️ Ne couper ici QUE si on avait une coupure par forme juridique au-dessus
        adresse = adresse[match2.start():]

        # 4. Vérifier unicité du préfixe (évite les erreurs si RUE est dans le nom)
        all_prefixes = re.findall(rf"\b{ADRESSE_PREFIXES_FILTRE}\b", adresse, flags=re.IGNORECASE)
        if len(all_prefixes) != 1:
            return None

    # 5. Nettoyage final
    adresse = re.sub(r"\s+", " ", adresse).strip(" ,.-")

    # 6. Trop court ?
    if len(adresse) < 5:
        return None

    return adresse
"""
def nettoyer_adresse(adresse):
    if not adresse:
        return None

    original = adresse.strip()

    # 1. Couper tout ce qui est AVANT la vraie adresse si forme juridique trouvée avant
    match = re.search(rf".*?[-–—]\s*\(?({FORM_PATTERN})\)?\s*[:-]?\s*", original)
    if match:
        adresse = original[match.end():]
    else:
        adresse = original  # sinon, garder toute la chaîne

    # 2. Supprimer les formes juridiques restantes dans l'adresse
    adresse = re.sub(rf"\b({FORM_PATTERN})\b", "", adresse)

    # 3. Nettoyage final : enlever espaces superflus et ponctuation finale
    adresse = re.sub(r"\s+", " ", adresse)
    adresse = adresse.strip(" ,.-")

    # 4. Vérifier que c’est bien une adresse plausible
    if len(adresse) < 5 or not re.search(r"\d", adresse):
        return None  # trop court ou pas de numéro → pas une adresse

    return adresse

def extract_add_entreprises(texte, doc_id=None):
    texte = re.sub(r'\s+', ' ', texte).strip().upper()
    lignes = texte.splitlines()
    lignes = [l.strip() for l in lignes if l.strip()][:5]  # max 5 lignes

    for ligne in lignes:
        if not re.search(rf"\b{ADRESSE_PREFIXES}\b", ligne, flags=re.IGNORECASE):
            continue

        # 1. Match avec préfixe et numéro
        match = re.search(ADDRESS_UNTIL_NUMBER, ligne, flags=re.IGNORECASE | re.VERBOSE)
        if match:
            adresse_nettoyee = nettoyer_adresse(match.group(0).strip())
            print(adresse_nettoyee)
            if adresse_nettoyee:
                logger.debug(f"✅ [Fallback1 Extraction]{f' ID={doc_id}' if doc_id else ''} Résultat : {adresse_nettoyee}")

                return adresse_nettoyee

        # 2. Fallback avec code postal
        fallback = re.search(ADDRESS_UNTIL_POSTAL, ligne, flags=re.IGNORECASE | re.VERBOSE)
        if fallback:
            adresse_nettoyee_fallback = nettoyer_adresse(fallback.group(0).strip())
            if adresse_nettoyee_fallback:
                logger.debug(f"↪️ [Fallback1 Extraction]{f' ID={doc_id}' if doc_id else ''} Résultat : {adresse_nettoyee_fallback}")
                return adresse_nettoyee_fallback

    # 3. Dernier fallback : sans préfixe, pour cas comme NEBLON-LE-MOULIN
    ADDRESS_FALLBACK_NO_PREFIX = rf"""
        \b{ADRESSE_REGEX}                         # ex: NEBLON-LE-MOULIN
        (?:\s+[^\d\s,\.]{{0,6}})?                 # éventuels mots suivants
        \s+(?:\d+[A-Z]*|[A-Z]+\d+|S\.?N\.?) (?:[\/\+-]?[0-9A-Z]+)?
        (?:[\/\+-][0-9A-Z]+)?                     # complément
        ,?\s*\d{{4,5}}?                           # CP facultatif
        (?=\s|,|\.|$)
    """

    for ligne in lignes:
        fallback_no_prefix = re.search(ADDRESS_FALLBACK_NO_PREFIX, ligne, flags=re.IGNORECASE | re.VERBOSE)
        if fallback_no_prefix:
            loggerfallback3.debug(f"↪️ [Fallback Extractionbis]{f' ID={doc_id}' if doc_id else ''} Résultat : {fallback_no_prefix}")
            return fallback_no_prefix.group(0).strip()

    if doc_id:
        loggerfallback3.debug(f"↪️ [Fallback ExtractionId]{f' ID={doc_id}' if doc_id else ''} Résultat : {fallback_no_prefix}")

        print(f"❌ ID : {doc_id} | aucune adresse trouvée dans les 5 premières lignes")
    return None
