import re
import unicodedata
from Utilitaire.outils.MesOutils import normalize_mois


DATE_RX = r"(?:\d{1,2}(?:er)?\s+\w+\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{2,4})"
DATE_OPT = rf"(?:\s+du\s+{DATE_RX})?"   # ← rend la date optionnelle
RG_TOKEN = r"\(RG"

APOST = r"[’']"  # apostrophe droite ou typographique

RX_APPEL = re.compile(r"(?:statuant|siégeant)\s+en\s+degr[ée]?\s+d[’']?appel|requête\s+d[’']?appel", re.IGNORECASE)
RX_CONDAMN = re.compile(r"\b(?:condamn[ée]?"
                        r"(?:es)?|emprisonnement|réclusion|peine\s+privative\s+de\s+liberté)\b", re.IGNORECASE)
RX_DESIGN = re.compile(
    r"[,:\s]*\bdésign(?:é|ée|ation)\b(.*?)(?:en\s+qualité\s+de\s+)?"
    r"\b(?:administrateur|administratrice|curateur|liquidateur)\b",
    re.IGNORECASE | re.DOTALL
)
RX_DISSOLUTION = re.compile(r"\bdissolution\s+judiciaire\b", re.IGNORECASE)
RX_REFORME_ORD = re.compile(r"r[ée]forme\s+l[’']?ordonnance", re.IGNORECASE)
RX_REFORME_JGMT = re.compile(r"r[ée]forme\s+(?:le|ce)\s+jugement", re.IGNORECASE)
RX_LEVEE_OBS = re.compile(r"\bl[èe]ve\s+la\s+mesure\s+d[’']?observation\b", re.IGNORECASE)
RX_CLOTURE_LIQ = re.compile(r"\bcl[ôo]ture\s+de\s+(?:la\s+)?liquidation(?:\s+judiciaire)?\b", re.IGNORECASE)
RX_NON_FONDEE_FIN = re.compile(
    r"dit\s+non\s+fond[ée]e\s+la\s+demande\s+visant\s+à\s+mettre\s+fin",
    re.IGNORECASE
)
RX_NOMME_ADMIN = re.compile(
    r"a\s+été\s+nomm[ée]?\s+en\s+qualité\s+d['’]administrateur\s+provisoire",
    re.IGNORECASE
)
# noinspection RegExpUnnecessaryNonCapturingGroup
RX_REFORME_DECISION_JP = re.compile(
    r"""
    r[ée]forme\s+                     # "réforme" ou "reforme" 
    (?:la\s+)?d[ée]cision\s+         # "la décision" ou "décision" 
    (?:rendue\s+par\s+)?             # optionnel : "rendue par"
    (?: 
        (?:la|le|du|de\s+la)\s+      # articles "la", "le", "du", "de la"
        (?:justice|juge)\s+de\s+paix # "justice de paix" ou "juge de paix"
    )
    """,
    re.IGNORECASE | re.VERBOSE
)

RX_ANNULATION_AG = re.compile(
    r"""
    (?:prononc[ée]e?|d[ée]cid[ée]e?)\s+        # "prononcée", "prononcé", "décidée", etc.
    l[’']?annulation\s+de\s+la\s+d[ée]cision   # "l'annulation de la décision"
    \s+de\s+l[’']?assembl[ée]e\s+g[ée]n[ée]rale # "de l'assemblée générale"
    """,
    re.IGNORECASE | re.VERBOSE
)
# Motifs “acte + (quelque part une) date” → on NE récupère PAS la date,
# on tag juste la présence du motif
# Levée simple
PAT_LEVEE_SIMPLE = re.compile(
    r"lev[ée]e\s+de\s+la\s+mesure(?:\s+de\s+protection)?",
    re.IGNORECASE
)
PAT_LEVEE = re.compile(rf"lev[ée]e\s+de\s+la\s+mesure(?:\s+de\s+protection)?[^.,:\n]{{0,80}}"
                       rf"{DATE_OPT}[^.\n]{{0,50}}\(RG", re.IGNORECASE)
PAT_REFORME_NEANT = re.compile(
    (
        rf"réforme\s+et\s+met\s+à\s+néant\s+la\s+d[ée]cision"
        rf"{DATE_OPT}"
        r"(?:,\s+du\s+juge\s+de\s+paix)?"
    ),
    re.IGNORECASE,
)
PAT_MET_NEANT = re.compile(rf"\bmet\s+à\s+néant\s+la\s+d[ée]cision{DATE_OPT}", re.IGNORECASE)
PAT_REFORME_ORD = re.compile(rf"réforme\s+l[’']?ordonnance{DATE_OPT}", re.IGNORECASE)
PAT_DECHARGE_MISSION = re.compile(
    r"\bd[ée]charg(?:é(?:e|es|s)?|er)?\s+(?:[^.\n]{0,120})?\bde\s+(?:sa|la)\s+mission\s+"
    r"(?:d['’]|de\s+)(?P<fonction>curateur|liquidateur|administrateur(?:\s+[a-zà-öø-ÿ'’\-]{1,20}){0,6})",
    flags=re.IGNORECASE
)
PAT_ARTICLE_CC = re.compile(
    r"art(?:\.|icl[ée])?s?\s+\d{1,4}(?:/\d{1,3})?(?:-\d+)?\s*(?:d['’]?(?:u|la)?)?\s+(?:code\s+civil|c\.\s*civ(?:il)?)",
    re.IGNORECASE
)

RX_DELAI_CONTACT = re.compile(
    r"""
    toute\s+personne\s+(?:concernée|intéressée)   # intro
    .*?est\s+prié[e]?[e]?\s+de                    # est prié(e) de
    .*?dans\s+les?\s+                             # "dans les" ou "dans le"
    (?P<nb>(\d+|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze))  # le nombre (chiffre ou lettre)
    \s+mois                                       # le mot "mois"
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE
)

# ====================================================================================================
# 🔎 AJOUT : REGEX POUR RÉPARATION COLLECTIVE & ARTICLES DU CODE DE DROIT ÉCONOMIQUE
# ----------------------------------------------------------------------------------------------------
# Ces expressions régulières servent à détecter :
#   - les "actions en réparation collective"
#   - les références à des articles du Code de droit économique (ex : article XVII.55 CDE)
#
# Un logger est également prévu dans detect_tribunal_premiere_instance_keywords()
# pour vérifier les déclenchements (utile pendant debugging).
# ====================================================================================================

RX_REPARATION_COLLECTIVE = re.compile(
    r"(action|procédure)\s+en\s+r[ée]paration\s+collective",
    re.IGNORECASE,
)

RX_ARTICLE_CDE = re.compile(
    r"article\s+([0-9a-zA-Z\./\-]+)\s+du\s+code\s+de\s+droit\s+économique",
    re.IGNORECASE,
)


# 1. Nettoyage du texte pour éviter les problèmes d'encodage
def normalize(text):
    text = unicodedata.normalize("NFC", text)  # normalise les accents
    text = text.replace("\u00A0", " ").replace("\u202F", " ")  # remplace les espaces spéciaux
    return text


def detect_tribunal_premiere_instance_keywords(texte_brut, extra_keywords):
    """Ajoute des tags normalisés en fonction des motifs détectés (aucune extraction de date)."""

    def add(tag: str):
        if tag not in extra_keywords:
            extra_keywords.append(tag)

    if RX_APPEL.search(texte_brut):
        add("appel")
    if PAT_REFORME_NEANT.search(texte_brut):
        add("reforme_mise_a_neant")
    if RX_REFORME_ORD.search(texte_brut):
        add("reforme_ordonnance")
    if RX_REFORME_JGMT.search(texte_brut):
        add("reforme_jugement")
    if PAT_LEVEE_SIMPLE.search(texte_brut):
        add("levee_mesure")
    if PAT_MET_NEANT.search(texte_brut):
        add("mise_a_neant")
    if PAT_DECHARGE_MISSION.search(texte_brut):
        add("fin de mission")
    if PAT_ARTICLE_CC.search(texte_brut):
        add("fin_mesure")
    if RX_LEVEE_OBS.search(texte_brut):
        add("levee_mesure_observation")
    if RX_CLOTURE_LIQ.search(texte_brut):
        add("cloture_liquidation")
    if PAT_LEVEE.search(texte_brut):
        add("levee_mesure")
    if RX_CONDAMN.search(texte_brut):
        add("condamnation")
    if RX_DESIGN.search(texte_brut):
        add("désignation")
    if RX_DISSOLUTION.search(texte_brut):
        add("dissolution_judiciaire")
    if RX_NON_FONDEE_FIN.search(texte_brut):
        add("rejet_demande")
    if RX_REFORME_DECISION_JP.search(texte_brut):
        add("reforme_decision_jp")
    if RX_NOMME_ADMIN.search(texte_brut):
        add("nommination_administrateur")
    if RX_ANNULATION_AG.search(texte_brut):
        add("annulation_decision_AG")
    match = RX_DELAI_CONTACT.search(texte_brut)
    if match:
        mois = normalize_mois(match.group('nb'))
        add(f"délai de contact {mois}")
    # ====================================================================================================
    # 🔎 AJOUT (LOGS) — motifs réparation collective & article du Code de droit économique
    # ====================================================================================================

    # Action en réparation collective
    if RX_REPARATION_COLLECTIVE.search(texte_brut):
        add("action_reparation_collective")

    # Article du Code de droit économique, ex : article XVII.55
    art = RX_ARTICLE_CDE.search(texte_brut)
    if art:
        numero = art.group(1).replace(".", "_").replace("/", "_").replace("-", "_")
        add(f"article_CDE_{numero}")
