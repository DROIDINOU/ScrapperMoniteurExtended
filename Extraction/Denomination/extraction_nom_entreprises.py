import logging
from bs4 import BeautifulSoup
import re
import unicodedata

# ─────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────
logger = logging.getLogger("extraction")  # 👈 on réutilise le même nom

# noms / abreviations debuts d'adresse pour FR et NL et DE
ADRESSE_REGEX = r"(RUE|R\.|AVENUE|AV\.|CHEE|CHAUSS[ÉE]E|ROUTE|RTE|PLACE|PL\.?|BOULEVARD|BD|CHEMIN|CH\.?|GALERIE|IMPASSE|SQUARE|ALL[ÉE]E|CLOS|VOIE|RY|PASSAGE|QUAI|PARC|Z\.I\.?|ZONE|SITE|PROMENADE|FAUBOURG|FBG|QUARTIER|CITE|HAMEAU|LOTISSEMENT|ENTRE LES GHETES(Z.-L.)|BELLEVAUX|LES PATURAGES)"
FLAMAND_ADRESSE_REGEX = r"(STRAAT|STRAATJE|LAAN|DREEF|STEENWEG|WEG|PLEIN|LEI|BAAN|HOF|KAAI|DRIES|MARKT|KANAAL|BERG|ZUID|NOORD|OOST|WEST|DOORN|VELD|NIEUWBUITENSTRAAT|VOORSTAD|BUITENWIJK|DORP|GEDEELTE|WIJK)"
GERMAN_ADRESSE_REGEX = r"(STRASSE|STR\.?|PLATZ|ALLEE|WEG|RING|GASSE|DORF|BERG|TOR|WALD|STEIG|MARKT|HOF|GARTENVORSTADT|STADTTEIL|STADTRAND|ORTSTEIL|DORF|AUSSENBEREICH)"

def _build_dirigeant_espece_rx(forms: list[str]) -> re.Pattern:
    """
    Ex.: « dirigeant, de droit ou de fait, d'une société commerciale,
          en l'espèce de l'ASBL ARBI ATSC dont ... » → capte « ASBL ARBI ATSC »
          (ou « NOM ... SRL » si la forme est en suffixe).
    """
    forms_re = r"(?:%s)" % "|".join(re.escape(f) for f in forms)
    token = r"[A-ZÀ-ÖØ-Þ0-9][A-ZÀ-ÖØ-Þ0-9&'’.\-]*"
    name_multi = rf"{token}(?:\s+{token}){{1,6}}"  # 2 à 7 tokens

    pattern = rf"""
        dirigeant(?:e)?                              # dirigeant / dirigeante
        (?:\s*,?\s*de\s+(?:droit|fait)
           (?:\s+ou\s+de\s+(?:droit|fait))?
        )?                                           # « de droit ou de fait » (optionnel mais toléré)
        (?:\s*,?\s*d['’]une\s+soci[ée]t[ée]\s+commerciale)?  # optionnel
        \s*,?\s*en\s+l['’]esp[eè]ce\s+de\s+           # « en l'espèce de »
        (?:l['’]|la|le|du|de\s+la)\s*                 # article: l'/la/le/du/de la
        (?P<societe>
            (?:
                (?:{forms_re})\s+{name_multi}        # forme en préfixe → « ASBL ARBI ATSC »
              | {name_multi}\s+(?:{forms_re})        # forme en suffixe → « ARBI ATSC ASBL »
            )
        )
        (?=\s*(?:,|\s+dont\b|\s+ayant\b|\s+qui\b|;|\.))  # on s'arrête net avant le contexte
    """
    return re.compile(pattern, re.IGNORECASE | re.VERBOSE)


def _canon(s: str) -> str:
    # normalise compatibilité (compose et homogénéise), puis nettoie
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u200b", "").replace("\ufeff", "")        # zero-width + BOM
    s = s.replace("\xa0", " ").replace("\u202f", " ").replace("\u2009", " ")
    s = s.replace("’", "'")                                   # apostrophe
    s = re.sub(r"\s+", " ", s)                                # compaction espaces
    return s.strip()


DECLENCHEURS = [
    r"homologation\s+du\s+plan\s+de",
    r"faillite\s+de",
    r"dissolution(?:\s+judiciaire)?\s+de",
    r"réorganisation\s+judiciaire\s+de",
    r"accord\s+amiable\s+de",
    r"(?:[A-Za-z'\s]+)?plan\s+de\s+la\s+réorganisation\s+judiciaire\s+de",
    r"ouverture\s+de\s+la\s+réorganisation\s+judiciaire\s+de",
    r"en\s+application\s+de\s+l['’]?\s*art\.?\s*XX\.?\d{1,3}\s*CDE\s+pour",
    r"dissolution(?:\s+judiciaire)?(?:\s+et\s+clôture\s+immédiate)?\s+de",
    r"liquidation\s+de",
    r"révocation\s+du\s+plan\s+de.*?réorganisation\s+judiciaire.*?de",
    r"ouverture\s+du\s+transfert\s+sous\s+autorité\s+judiciaire\s+de",
    r"transfert\s+sous\s+autorité\s+judiciaire\s+de"

]
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

NAME_TOKEN = r"(?:[A-ZÉÈÀÂÎÔÙÜÇ][a-zà-öø-ÿ'’\-]+|[A-ZÉÈÀÂÎÔÙÜÇ]{2,})"

# 🔹 Pattern spécial pour interdiction visant une personne physique
PAT_INTERDICTION_PERSONNE = re.compile(r"""
    il\s+est\s+fait\s+interdiction\s+à\s+
    (?:Monsieur|Madame)\s+
    (?P<prenom>[A-ZÉÈÀÂÎÔÙÜÇ][a-zà-öø-ÿ'\-]+)   # Prénom
    \s+
    (?P<nom>[A-ZÉÈÀÂÎÔÙÜÇ][A-ZÉÈÀÂÎÔÙÜÇ'\-]+)   # NOM en majuscules
""", re.IGNORECASE | re.VERBOSE)

# "faillite de ... inscrite sous" → capture uniquement le bloc nom
PAT_FAILLITE_INSCRITE_SOUS = re.compile(
    r"""faillite\s+de\s*:?\s*
        (?:l['’]|la|le|du|de\s+la)?\s*   # article optionnel, hors capture
        (?P<nom>.+?)                     # ← ce qu'on veut (nom + forme, dans n'importe quel ordre)
        \s*,?\s*inscrit(?:e)?\s+sous\b   # stop net avant "inscrit(e) sous"
    """,
    re.IGNORECASE | re.VERBOSE
)
# ➕ à côté de tes autres patterns (avant le nettoyage/dédoublonnage)
PAT_FAILLITE_NOM_PRENOM = re.compile(
    rf"""
    faillite\s+de\s*:?\s*
    (?:M\.|Monsieur|Madame|Mme)?\s*
    (?P<nom>[A-ZÉÈÀÂÎÔÙÜÇ][A-ZÉÈÀÂÎÔÙÜÇ'’\-]+)   # NOM en ALLCAPS
    \s*,\s*
    (?P<prenom>{NAME_TOKEN})                     # Prénom (Maj+minuscules ou ALLCAPS)
    (?=                                         # Lookahead: on s'arrête avant l'adresse
        \s*,?\s*(?:domicili[ée]?\s+à|{ADRESSE_REGEX}\b|\d{{4}}\s+[A-Z])
        | \s*,                                  # ou simplement la prochaine virgule si tu veux être large
    )
    """,
    flags=re.IGNORECASE | re.VERBOSE
)


PAT_DANS_L_AFFAIRE = re.compile(
        r"(?is)"  # i = ignorecase, s = DOTALL
        r"dans\W*l\W*affaire\W*:?\W*"  # "Dans l'affaire" tolérant
        r"(?P<nom>[^,\n\r;]+)"  # tout jusqu'à la 1re virgule/fin de ligne
    )



def _build_en_cause_de_societe_rx(forms:list[str]) -> re.Pattern:
    """
    Capture le nom de société juste après « En cause de : ».
    Accepte forme juridique en préfixe *ou* suffixe.
    Ex.: « En cause de : FRIGOMAN SPRL, … » → 'FRIGOMAN SPRL'
         « En cause de : SCOMM NOPPS SERVICES, … » → 'SCOMM NOPPS SERVICES'
    """
    forms_re = r"(?:%s)" % "|".join(re.escape(f) for f in forms)
    token = r"[A-ZÀ-ÖØ-Þ0-9][A-ZÀ-ÖØ-Þ0-9&'’.\-]*"
    name_multi = rf"{token}(?:\s+{token})+"  # ≥ 2 tokens pour éviter 'BRAUN' (personne)

    pattern = rf"""
        en\s*cause\s*de\s*:?\s*
        (?P<societe>
            (?:
                (?:{forms_re})\s+{name_multi}        # forme en préfixe
                |
                {name_multi}(?:\s+(?:{forms_re}))?   # nom (≥2 tokens) + forme éventuelle en suffixe
            )
        )
        \s*(?=,|;|—|-|\n|$)                           # stop avant la virgule/fin de ligne
    """
    return re.compile(pattern, re.IGNORECASE | re.VERBOSE)

RX_EN_CAUSE_DE_SOCIETE = _build_en_cause_de_societe_rx(FORMS)
RX_DIRIGEANT_ESPECE = _build_dirigeant_espece_rx(FORMS)
# ─────────────────────────────────────────────────────────────
# FONCTIONS FALLBACK AVEC LOG
# ─────────────────────────────────────────────────────────────

def fallback_nom_extraction(text, forms, doc_id=None):
    fallbackgroup = []
    escaped_forms = [re.escape(f) for f in forms]
    form_regex = r"(?:\(?\s*(?:" + "|".join(escaped_forms) + r")(?:\s*\([A-Z]{2,5}\))?\s*\)?)"
    head_text = text[:300]

    patterns = [
        rf"({form_regex})\s+([A-ZÉÈÀÙÂÊÎÔÛÇ0-9&@.\-']{{2,}}(?:\s+[A-ZÉÈÀÙÂÊÎÔÛÇ0-9&@.\-']{{2,}}){{0,3}})",
        rf"([A-ZÉÈÀÙÂÊÎÔÛÇ0-9&@.\-']{{2,}}(?:\s+[A-ZÉÈÀÙÂÊÎÔÛÇ0-9&@.\-']{{2,}}){{0,3}})\s+({form_regex})",
        rf"((?:[A-ZÉÈÀÙÂÊÎÔÛÇ0-9&@.\-']+\s+){{1,3}})(?=\s*{form_regex})"
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
            r"([A-ZÉÈÀÙÂÊÎÔÛÇ0-9&@.\-']{2,}(?:\s+[A-ZÉÈÀÙÂÊÎÔÛÇ0-9&@.\-']{2,}){0,4})",
            head_text
        )
        if match:
            candidat = match.group(1).strip()
            if not candidat.isdigit():  # ⚠️ exclure les pures suites numériques
                fallbackgroup.append(candidat)
    logger.debug(f"↪️ [Fallback Extraction]{f' ID={doc_id}' if doc_id else ''} Résultat : {fallbackgroup}")
    return fallbackgroup


# ─────────────────────────────────────────────────────────────
# SOUS FONCTIONS DE: extract_noms_entreprises
# ─────────────────────────────────────────────────────────────

# retourne nom complet
def extract_nom_forme(text, déclencheur, form_regex, nom_list, is_nl=False):
    # Détermine la fin de capture possible pour un nom d'entreprise après un déclencheur.
    # Ce lookahead permet de vérifier que ce qui suit la forme et le nom est bien une structure attendue,
    # comme une adresse ou un numéro BCE, pour augmenter la précision des extractions.
    #
    # Si le texte est en français (`is_nl=False`) :
    #   - On s'assure que le nom est suivi d'au moins un espace, puis :
    #       - soit "BCE" + un numéro (ex. BCE 0123.456.789),
    #       - soit un mot-clé d'adresse française (ex. RUE, AVENUE) suivi d'une majuscule (ex. RUE DES FLEURS).
    #
    # Si le texte est en néerlandais (`is_nl=True`) :
    #   - On vérifie que le nom est suivi d'une suite de mots en majuscules (ex. adresse flamande),
    #     avec éventuellement un nombre et une virgule ou un espace après (structure fréquente d’adresse NL).
    ending = (
        rf"(?=\s+(?:BCE\s+\d{{4}}[.\d]+|{ADRESSE_REGEX}\s+[A-Z]|{FLAMAND_ADRESSE_REGEX}\s+[A-Z]|{GERMAN_ADRESSE_REGEX}\s+[A-Z]))"
        if not is_nl else
        rf"(?=\s+[A-ZÉÈÊÀÂ'\-]+(?:\s+\d{{1,4}})?(?:,|\s))"
    )
    # Ce pattern recherche une structure textuelle du type : "[déclencheur] ... forme juridique + nom d’entreprise".
    # Il couvre deux cas :
    #   - soit la forme précède le nom (forme1 + nom1), ex. "SRL TOTO CONSTRUCTION"
    #   - soit le nom précède la forme (nom2 + forme2), ex. "TOTO CONSTRUCTION SRL"
    #
    # Le déclencheur (ex. "faillite de", "dissolution judiciaire de", etc.) est suivi optionnellement d’un ":" ou d’un espace.
    # Ensuite, on capture :
    #   - soit la forme entre parenthèses facultatives, suivie d’un ou plusieurs mots majuscules comme nom,
    #   - soit l’inverse : le nom suivi de la forme.
    #
    # Le tout est suivi d’un lookahead (`ending`) pour s’assurer que l’extraction est suivie d’une adresse ou d’une structure attendue.

    pattern = rf"""
        {déclencheur}\s*:?\s*
        (?:
            \(?(?P<forme1>{form_regex})\)?[-\s]*+(?P<nom1>(?:[A-Z0-9&@".\-',]+[-\s]*){{1,5}})
            |
            (?P<nom2>(?:[A-Z0-9&@".\-',]+[-\s]*){{1,5}})[-\s]*+\(?(?P<forme2>{form_regex})\)?
        )
        {ending}
    """
    matches = re.findall(pattern, text, flags=re.IGNORECASE | re.VERBOSE)
    for m in matches:
        forme = (m[0] or m[3]).strip(" -:.,")
        nom = (m[1] or m[2]).strip(" -:.,")
        if forme and nom:
            # ⚠️ Toujours remettre le nom suivi de la forme
            nom_complet = f"{nom.strip()} {forme.strip()}"
            nom_list.append(nom_complet)


def extract_by_patterns(text, patterns, nom_list, flags=re.IGNORECASE):
    for pat in patterns:
        matches = re.findall(pat, text, flags=flags)
        for m in matches:
            nom_list.append(m.strip() if isinstance(m, str) else m[0].strip())


# ─────────────────────────────────────────────────────────────
# FONCTION PRINCIPALE
# ─────────────────────────────────────────────────────────────

def extract_noms_entreprises(texte_html, doc_id=None):
    nom_list = []

    # --- DEBUG IMMEDIAT : type + longueur + décodage bytes ---
    if isinstance(texte_html, bytes):
        try:
            texte_html = texte_html.decode("utf-8", errors="ignore")
        except Exception:
            texte_html = texte_html.decode("latin-1", errors="ignore")
            print("[DEBUG] decoded bytes as latin-1", flush=True)

    soup = BeautifulSoup(texte_html, 'html.parser')
    full_text = _canon(soup.get_text(separator=" "))
    # 🚀 Sécurité : tronquer les textes trop longs pour éviter le backtracking infini
    if len(full_text) > 8000:
        logger.warning(f"[Troncature] Texte trop long ({len(full_text)} chars) → coupé à 8000 pour ID={doc_id}")
        full_text = full_text[:8000]

    for m in PAT_FAILLITE_INSCRITE_SOUS.finditer(full_text):
        nom = _canon(m.group("nom")).strip(" .;,-")
        if nom:
            nom_list.append(nom)

    # regex "Dans l'affaire" robuste
    m = PAT_DANS_L_AFFAIRE.search(full_text)
    if m:
        nom = m.group("nom").strip(" .;-")
        nom_list.append(nom)
    # Nettoyage : remplacer les SRL- / SA- etc. par "SRL "
    for form in FORMS:
        full_text = re.sub(rf"({re.escape(form)})[\s\-:]+", r"\1 ", full_text)
    form_regex = '|'.join(re.escape(f) for f in FORMS)
    form_regex = rf"(?:{form_regex})[-:]?"  # 👈 accepte un tiret à la fin (optionnel)
    flags = re.IGNORECASE


    # 🆕 1) Détection dédiée : « En cause de : … »
    for m in RX_EN_CAUSE_DE_SOCIETE.finditer(full_text):
        nom_list.append(m.group("societe").strip())
    # 🔹 Extractions simples
    simple_patterns = [
        r"ouverture\s+de\s+la\s+faillite\s*:?\s*((?:[A-Z0-9&@\".\-']+\s*){1,8})",
        r"a\s+condamné\s*:?\s*((?:[A-Z0-9&@\".\-']+\s*){1,8})",
        r"a\s+accordé\s+à\s*((?:[A-Z0-9&@\".\-']+\s*){1,8})",
        r"clôture\s+de(?:\s+la\s+liquidation)?\s*:?\s*((?:[A-Z0-9&@\".\-']+\s*){1,8})",
        r"dissolution(?:\s+judiciaire)?\s*:?\s*((?:[A-Z0-9&@\".\-']+\s*){1,8})",
        r"faillite\s+de\s*:?\s*((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){1,3})(?=\s*(?:domicile|né|rue|avenue|BCE|\d{4}\s+[A-Z]))",
        r"faillite\s+de\s*:?\s*((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){1,4})(?=\s*(?:domicile|né|rue|avenue|BCE|\d{4}\s+[A-Z]))",

    ]
    extract_by_patterns(full_text, simple_patterns, nom_list)

    # Cibler les noms proches d'adresses FR/NL	Très utile quand il n’y a pas de forme juridique
    adresse_patterns = [
        # --- Faillite - FR ---
        (
            rf"faillite\s+de\s*:?\s*"
            rf"(?:Monsieur|Madame)?\.?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,4}})"
            rf"(?=,\s*{ADRESSE_REGEX})"
        ),
        (
            rf"faillite\s+de\s*:?\s*"
            rf"(?:Monsieur|Madame)?\.?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,4}})"
            rf"(?=\s+{ADRESSE_REGEX})"
        ),

        # --- Faillite - NL ---
        (
            rf"faillite\s+de\s*:?\s*"
            rf"(?:Monsieur|Madame)?\.?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,4}})"
            rf"(?=,\s*{FLAMAND_ADRESSE_REGEX})"
        ),
        (
            rf"faillite\s+de\s*:?\s*"
            rf"(?:Monsieur|Madame)?\.?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,4}})"
            rf"(?=\s+{FLAMAND_ADRESSE_REGEX})"
        ),

        # --- Faillite - DE ---
        (
            rf"faillite\s+de\s*:?\s*"
            rf"(?:Monsieur|Madame)?\.?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,4}})"
            rf"(?=,\s*{GERMAN_ADRESSE_REGEX})"
        ),
        (
            rf"faillite\s+de\s*:?\s*"
            rf"(?:Monsieur|Madame)?\.?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,4}})"
            rf"(?=\s+{GERMAN_ADRESSE_REGEX})"
        ),

        # --- Autres motifs (pour) ---
        (
            rf"pour\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=,\s*{ADRESSE_REGEX})"
        ),
        (
            rf"pour\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=\s+{ADRESSE_REGEX})"
        ),
        (
            rf"pour\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=,\s*{FLAMAND_ADRESSE_REGEX})"
        ),
        (
            rf"pour\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=\s+{FLAMAND_ADRESSE_REGEX})"
        ),
        (
            rf"pour\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=,\s*{GERMAN_ADRESSE_REGEX})"
        ),
        (
            rf"pour\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=\s+{GERMAN_ADRESSE_REGEX})"
        ),

        # --- Homologation ---
        (
            rf"homologation\s+du\s+plan\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=,\s*{ADRESSE_REGEX})"
        ),
        (
            rf"homologation\s+du\s+plan\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=\s+{ADRESSE_REGEX})"
        ),
        (
            rf"homologation\s+du\s+plan\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=,\s*{FLAMAND_ADRESSE_REGEX})"
        ),
        (
            rf"homologation\s+du\s+plan\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=\s+{FLAMAND_ADRESSE_REGEX})"
        ),
        (
            rf"homologation\s+du\s+plan\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=,\s*{GERMAN_ADRESSE_REGEX})"
        ),
        (
            rf"homologation\s+du\s+plan\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=\s+{GERMAN_ADRESSE_REGEX})"
        ),

        # --- Réorganisation judiciaire ---
        (
            rf"réorganisation\s+judiciaire\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=,\s*{ADRESSE_REGEX})"
        ),
        (
            rf"réorganisation\s+judiciaire\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=\s+{ADRESSE_REGEX})"
        ),
        (
            rf"réorganisation\s+judiciaire\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=,\s*{FLAMAND_ADRESSE_REGEX})"
        ),
        (
            rf"réorganisation\s+judiciaire\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=\s+{FLAMAND_ADRESSE_REGEX})"
        ),
        (
            rf"réorganisation\s+judiciaire\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=,\s*{GERMAN_ADRESSE_REGEX})"
        ),
        (
            rf"réorganisation\s+judiciaire\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=\s+{GERMAN_ADRESSE_REGEX})"
        ),

        # --- Ouverture de réorganisation judiciaire ---
        (
            rf"ouverture\s+de\s+la\s+réorganisation\s+judiciaire\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=,\s*{ADRESSE_REGEX})"
        ),
        (
            rf"ouverture\s+de\s+la\s+réorganisation\s+judiciaire\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=\s+{ADRESSE_REGEX})"
        ),
        (
            rf"ouverture\s+de\s+la\s+réorganisation\s+judiciaire\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=,\s*{FLAMAND_ADRESSE_REGEX})"
        ),
        (
            rf"ouverture\s+de\s+la\s+réorganisation\s+judiciaire\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=\s+{FLAMAND_ADRESSE_REGEX})"
        ),
        (
            rf"ouverture\s+de\s+la\s+réorganisation\s+judiciaire\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=,\s*{GERMAN_ADRESSE_REGEX})"
        ),
        (
            rf"ouverture\s+de\s+la\s+réorganisation\s+judiciaire\s+de\s*:?\s*"
            rf"((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,5}})"
            rf"(?=\s+{GERMAN_ADRESSE_REGEX})"
        ),

        # --- Dissolution ---
        (
            rf"dissolution(?:\s+judiciaire)?(?:\s+et\s+clôture\s+immédiate)?\s+de\s*:?\s*"
            rf"([^,]{{5,150}}?)"
            rf"(?=[,\s\-]*\s*{ADRESSE_REGEX})"
        ),
        (
            rf"dissolution(?:\s+judiciaire)?(?:\s+et\s+clôture\s+immédiate)?\s+van\s*:?\s*"
            rf"([^,]{{5,150}}?)"
            rf"(?=[,\s\-]*\s*{FLAMAND_ADRESSE_REGEX})"
        ),
        (
            rf"dissolution(?:\s+judiciaire)?(?:\s+et\s+clôture\s+immédiate)?\s+van\s*:?\s*"
            rf"([^,]{{5,150}}?)"
            rf"(?=[,\s\-]*\s*{GERMAN_ADRESSE_REGEX})"
        )
    ]

    extract_by_patterns(full_text, adresse_patterns, nom_list)

    # 🔹 Extraction via déclencheurs + formes juridiques
    for déclencheur in DECLENCHEURS:

        extract_nom_forme(full_text, déclencheur, form_regex, nom_list, is_nl=False)
        extract_nom_forme(full_text, déclencheur, form_regex, nom_list, is_nl=True)

    # 🔹 Cas spéciaux : formes juridiques en préfixe (ASBL SOCOBEL → SOCOBEL ASBL)
    for form in FORMS:
        pattern = rf"\b{re.escape(form)}\s+([A-ZÉÈÀÙÂÊÎÔÛÇ0-9&@.\-']{{2,}}(?:\s+[A-ZÉÈÀÙÂÊÎÔÛÇ0-9&@.\-']{{2,}}){{0,5}})"
        matches = re.findall(pattern, full_text, flags=re.IGNORECASE)
        for m in matches:
            nom_list.append(f"{m.strip()} {form}")
    # Cas spécial : "a accordé à ..."
    adresse_patterns.append(
        rf"a\s+accordé\s+à\s*((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,6}})\s+{form_regex}(?=,?\s*{ADRESSE_REGEX})"
    )
    adresse_patterns.append(
        rf"a\s+accordé\s+à\s*((?:[A-ZÉÈÊÀÂ@\"'\-]+\s*){{1,6}})\s+{form_regex}"
    )
    for m in RX_DIRIGEANT_ESPECE.finditer(full_text):
        nom_list.append(m.group("societe").strip())

    # 🔹 Cas spécial : "il est fait interdiction à Monsieur/Madame ..."
    for m in PAT_INTERDICTION_PERSONNE.finditer(full_text):
        personne = f"{m.group('prenom').strip()} {m.group('nom').strip()}"
        nom_list.append(personne)
    # … dans extract_noms_entreprises(), après avoir construit full_text :
    for m in PAT_FAILLITE_NOM_PRENOM.finditer(full_text):
        nom_list.append(f"{m.group('prenom').strip()} {m.group('nom').strip()}")

    # 🔹 Nettoyage doublons
    seen = set()
    noms_uniques = []
    for nom in nom_list:
        nom_clean = re.sub(r"\s+", " ", nom.strip())
        nom_clean = re.sub(r"-\s*$", "", nom_clean)
        if "qualité d'associé" in nom_clean.lower() or "liquidateur" in nom_clean.lower():
            continue
        if nom_clean and nom_clean.lower() not in {"de", "et cl"} and nom_clean not in seen:
            noms_uniques.append(nom_clean)
            seen.add(nom_clean)

    if not noms_uniques:
            print("le fall back a été activé..........................................................................")
            logger.warning(f"⚠️ Fallback activé pour le document ID={doc_id}")
            noms_uniques = fallback_nom_extraction(full_text, FORMS, doc_id)
            if noms_uniques:
                logger.info(f"✅ Fallback réussi pour ID={doc_id} : {noms_uniques}")
            else:
                logger.error(f"❌ Fallback échoué pour ID={doc_id} — aucun nom trouvé.")

    return noms_uniques
