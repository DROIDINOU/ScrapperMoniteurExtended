import re
import unicodedata
# tout en haut (près des helpers)
ABS_PREF = r"(?:il\s+est\s+)?demand[ée]?\s+de\s+déclarer\s+l'absence\s+de"
PROT_PREF = r"modifi[ée]?\s+les\s+mesures\s+de\s+protection\s+à\s+l[’']?égard\s+de\s+la\s+personne\s+et\s+des?\s+biens\s+de\s+l[’']?intéress[ée]?"
# variantes où le texte ne contient plus "modifié..." et ne commence que sur la queue
INT_PREF_FULL = r"à\s+l[’']?égard\s+de\s+la\s+personne\s+et\s+des?\s+biens\s+de\s+l[’']?intéress[ée]?"
INT_PREF_TAIL = r"et\s+des?\s+biens\s+de\s+l[’']?intéress[ée]?"

PREFIXES = (
    r"(?:"
    r"né(?:e)?"
    r"|pour la succession de"
    r"|succession\s+(?:en\s+d[ée]sh[ée]rence|vacante)\s+de"
    r"|en qualité de curateur à la succession vacante de"
    r"|la succession vacante de"
    r"le\s+juge\s+de\s+paix\s+du\s+canton\s+de\s+Visé\s+a\s+désigné\s+(?:à\s+)?"
    r"|"
    + ABS_PREF +
    r"|"
    + PROT_PREF +
    r"|"
    + INT_PREF_FULL
    +
    r"|"
    + INT_PREF_TAIL +
    r")"
)
CONTEXT_CUT = (
    r"(?:\bné(?:e)?\b|\bRN\b|\bNRN\b|\(RN|\(RRN|\bRRN\b|,?\s+inscrit[e]?\b|,?\s+domicili[é]e?\b|,?\s+décédé[e]?\b)"
)

# Blocs prénoms / nom (robustes aux accents et aux noms composés)
UPWORD = r"[A-ZÉÈÀÂÊÎÔÛÇÄËÏÖÜŸ][A-ZÉÈÀÂÊÎÔÛÇÄËÏÖÜŸ'’\-]{1,}"
NOM_BLOCK = rf"{UPWORD}(?:\s+{UPWORD}){{0,4}}"              # LUYTEN | VAN DER MEER | D’ALMEIDA
PRENOM_WORD = r"[A-ZÉÈÀÂÊÎÔÛÇ][a-zà-öø-ÿ'’\-]{1,}"
PRENOMS_BLK = rf"{PRENOM_WORD}(?:\s+{PRENOM_WORD}){{0,5}}"    # Liliane Louise Victorine
# Token RN élargi (RN / RRN / NRN / NN — avec ou sans points/espaces)
RN_TOKEN = r"(?:(?:R\.?\s*){1,2}N\.?|N\.?\s*R\.?\s*N\.?|N\.?\s*N\.?)"
RN_TOKEN_ANY = RN_TOKEN
# Après tes blocs de constantes (avec NOM_BLOCK et PRENOMS_BLK déjà définis)
RX_INTERDIT_A = re.compile(rf"""
    \b(?:il\s+est\s+)?interdit\s+à\s+                 # "interdit à" (avec "il est" optionnel)
    (?:Monsieur|Madame|M(?:r|me)?\.?\s+)?             # civilité optionnelle
    (?:
        (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})      # Karl HOLTZHEIMER
        |
        (?P<nom2>{NOM_BLOCK})\s*,\s*(?P<prenoms2>{PRENOMS_BLK}) # HOLTZHEIMER, Karl
    )
    (?=                                               # on s'arrête proprement avant le contexte
        \s*,?\s*(?:né|née|né\(e\)|domicili|pour\s+une\s+durée|de\s+\d+\s+ans|;|\.|,|$)
    )
""", re.IGNORECASE | re.VERBOSE)

RX_MODIF_PROTECTION_INTERESSE = re.compile(rf"""
    modifi[ée]?\s+les\s+mesures\s+de\s+protection
    \s+à\s+l[’']?égard\s+de\s+la\s+personne\s+et\s+des?\s+biens\s+de\s+l[’']?intéress[ée]?\s+
    (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})
    (?=\s*(?:,|;|\.|$))
""", re.IGNORECASE | re.VERBOSE)


RX_PROTECTION_INTERESSE_NOM_SEUL = re.compile(rf"""
    modifi[ée]?\s+les\s+mesures\s+de\s+protection\s+à\s+l[’']?égard\s+de\s+la\s+personne\s+et\s+des?\s+biens\s+de\s+l[’']?intéress[ée]?\s+
    (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})
""", re.IGNORECASE | re.VERBOSE)

RX_PROTECTION_INTERESSE_NE = re.compile(rf"""
    mesures\s+de\s+protection\s+à\s+l[’']?égard\s+de\s+la\s+personne\s+et\s+des?\s+biens\s+de\s+l[’']?intéress[ée]\s+
    (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})   # prénoms puis NOM
    ,\s+(?:né|née|né\(e\))\s+à                           # suivi du "né à"
""", re.IGNORECASE | re.VERBOSE)


RX_NOM_ET_PRENOM_LABEL = re.compile(rf"""
    \bNom\s+et\s+prénom[s]?\s*:\s*          # "Nom et prénom :" ou "Nom et prénoms :"
    (?P<nom>{NOM_BLOCK})\s*,?\s*            # NOM, virgule optionnelle
    (?P<prenoms>                            # bloc prénoms autorisant espaces/virgules
        {PRENOM_WORD}
        (?:\s*,?\s*{PRENOM_WORD}){{0,5}}
    )
    (?=\s*(?:$|[\n\r]|,|;|\.|Lieu|Date|Domicile|Nationalité|N°|No|Nº))  # stop propre
""", re.IGNORECASE | re.VERBOSE)

# 1) “le nommé : [Nr. … - ] NOM, Prénoms …”
RX_LE_NOMME_NP = re.compile(rf"""
    \ble\s+nomm[ée]\s*[:\-]?\s*
    (?:Nr\.?\s*[\d./-]+\s*[-–]\s*)?         # ex: "Nr. 18.2025 - " (optionnel)
    (?P<nom>{NOM_BLOCK})\s*,\s*(?P<prenoms>{PRENOMS_BLK})
    (?=\s*,?\s*(?:né|née|né\(e\)|RR?N|NRN|\(|$))
""", re.IGNORECASE | re.VERBOSE)

# 2) “Nr. … - NOM, Prénoms …” (au cas où “le nommé :” est absent)
RX_NR_NP = re.compile(rf"""
    \bNr\.?\s*[\d./-]+\s*[-–]\s*
    (?P<nom>{NOM_BLOCK})\s*,\s*(?P<prenoms>{PRENOMS_BLK})
    (?=\s*,?\s*(?:né|née|né\(e\)|RR?N|NRN|\(|$))
""", re.IGNORECASE | re.VERBOSE)

# 3) générique “NOM, Prénoms, né …”
RX_NP_NE = re.compile(rf"""
    (?P<nom>{NOM_BLOCK})\s*,\s*(?P<prenoms>{PRENOMS_BLK})
    \s*,\s*(?:né|née|né\(e\))\b
""", re.IGNORECASE | re.VERBOSE)
# (A) “Monsieur/Madame + Prénom(s) + NOM (RN …)”
RX_CIVILITE_PN_RN = re.compile(rf"""
    (?:Monsieur|Madame|M(?:r|me)?\.?|Ma(?:ître|itre)|Me)\s+
    (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})   # Prénoms + NOM
    \s*\(\s*{RN_TOKEN_ANY}\b[^)]*\)                    # (RN|NRN|NN ...)
""", re.IGNORECASE | re.VERBOSE)

# (B) “appel interjeté par Monsieur/Madame + Prénom(s) + NOM (RN …)”
RX_APPEL_PAR_CIVILITE = re.compile(rf"""
    (?:dit\s+l['’]?appel|l['’]?appel)?\s*
    (?:interjet[ée]\s+par|de)\s+
    (?:Monsieur|Madame|M(?:r|me)?\.?)\s+
    (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})
    (?:\s*\(\s*{RN_TOKEN_ANY}\b[^)]*\))?
""", re.IGNORECASE | re.VERBOSE)

# (C) “relativement à la personne de Monsieur/Madame + Prénom(s) + NOM (RN …)”
RX_REL_PERSONNE_DE = re.compile(rf"""
    relativement\s+à\s+la\s+personne\s+de\s+
    (?:Monsieur|Madame|M(?:r|me)?\.?)\s+
    (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})
    (?:\s*\(\s*{RN_TOKEN_ANY}\b[^)]*\))?
""", re.IGNORECASE | re.VERBOSE)


RX_CURATEUR_SV_NP = re.compile(rf"""
    curateur
    \s+à\s+la?\s+succession
    \s+(?:
        (?:r[ée]put[ée]e?\s+)?vacante
      | en\s+d[ée]sh[ée]rence
    )
    \s+de\s*:?\s*
    (?:feu[e]?\s+)?(?:M(?:onsieur|me|adame)?\.?\s+)? 
    (?P<nom>{NOM_BLOCK})\s*,\s*(?P<prenoms>{PRENOMS_BLK})
    (?=\s*(?:\(|,|;|\.|$))
""", re.IGNORECASE | re.VERBOSE)

# — Personne visée par "succession vacante / en déshérence de ..."
RX_SV_PN = re.compile(rf"""
    succession\s+(?:(?:r[ée]put[ée]e?\s+)?vacante|en\s+d[ée]sh[ée]rence)\s+de\s+
    (?:feu[e]?\s+)?(?:M(?:me|adame|onsieur)?\.?\s+)?   # civilité/feu optionnels
    (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})
    (?=\s*(?:\(|,|;|\.|$))                         # stop avant (RN...), virgule, point, etc.
""", re.IGNORECASE | re.VERBOSE | re.DOTALL)

RX_SV_NP = re.compile(rf"""
    succession\s+(?:(?:r[ée]put[ée]e?\s+)?vacante|en\s+d[ée]sh[ée]rence)\s+de\s+
    (?:feu[e]?\s+)?(?:M(?:me|adame|onsieur)?\.?\s+)? 
    (?P<nom>{NOM_BLOCK})\s*,\s*(?P<prenoms>{PRENOMS_BLK})
    (?=\s*(?:\(|,|;|\.|$))
""", re.IGNORECASE | re.VERBOSE | re.DOTALL)

RX_CURATEUR_SV_PN = re.compile(rf"""
        curateur            # le terme curateur
        \s+à\s+la?\s+succession
        \s+(?:
            (?:r[ée]put[ée]e?\s+)?vacante
          | en\s+d[ée]sh[ée]rence
        )
        \s+de\s*:?\s*
        (?:feu[e]?\s+)?(?:M(?:onsieur|me|adame)?\.?\s+)?   # civilité/feu optionnels
        (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})
        (?=\s*(?:\(|,|;|\.|$))                         # s'arrêter avant (RN..., , née..., ;, fin)
    """, re.IGNORECASE | re.VERBOSE)

RX_CAPABLE_BIENS = re.compile(rf"""
    (?:Dit\s+pour\s+droit\s+que\s+)?(?:le\s+tribunal\s+)?   # optionnels
    (?:Monsieur|Madame)\s+
    (?:
        (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})   # Prénom(s) + NOM
      | (?P<nom_only>{NOM_BLOCK})                           # ou NOM seul
    )
    \s*,?\s*(?:est|soit)\s+capable\b
""", re.IGNORECASE | re.VERBOSE)

# =======================
# Regex PRECOMPILÉES — SUCCESSIONS
# =======================
RX_SV_ANY = re.compile(
    r"succession\s+(?:vacante|en\s+d[ée]sh[ée]rence)\s+de\s+((?:[A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+\s+){1,4}[A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+)",
    re.IGNORECASE,
)

RX_SV_NOM_COMPLET_VIRG = re.compile(
    r"succession\s+(?:en\s+d[ée]sh[ée]rence|vacante)?\s+de\s+((?:[A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+\s+){1,4}[A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+)",
    re.IGNORECASE,
)

RX_SRV_SIMPLE = re.compile(
    r"succession\s+réputée\s+vacante\s+de\s+(?:Madame|Monsieur)?\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+)",
    re.IGNORECASE,
)

RX_SRV_NP = re.compile(
    r"succession\s+réputée\s+vacante\s+de\s+(?:M(?:onsieur)?|Madame)?\.?\s*([A-ZÉÈÊÀÂ\-']+),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\- ]{2,})",
    re.IGNORECASE,
)

RX_SV_NOM_VIRG_PRENOMS = re.compile(
    r"succession\s+(?:vacante|en\s+d[ée]sh[ée]rence)?\s+de\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-\s]+)",
    re.IGNORECASE,
)

RX_SV_FEU_PAIRE = re.compile(
    r"(?:succession\s+de\s+feu|à\s+la\s+succession\s+de\s+feu).{0,30}?(?:M(?:onsieur)?|Madame)?\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+)[,\s]+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+)",
    re.IGNORECASE,
)

RX_SV_FEU_VARIANTES = re.compile(
    r"(?:succession\s+(?:déclarée\s+)?vacante\s+de\s+feu|succession\s+de\s+feu|à\s+la\s+succession\s+de\s+feu)\s*:?\s*(?:M(?:onsieur)?|Madame)?\.?\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+){1,4})",
    re.IGNORECASE,
)

RX_SRV_M_RN = re.compile(
    r"succession\s+réputée\s+vacante\s+de\s+M\.?\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\- ]+?)(?=\s*\(RN)",
    re.IGNORECASE,
)

RX_ADMIN_SV_SPEC = re.compile(
    r"administrateur\s+provisoire\s+à\s+succession,?\s+de\s+(?:Monsieur|Madame|M\.|Mme)?\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+){1,4})",
    re.IGNORECASE,
)

RX_SV_PART_VAC = re.compile(
    r"succession\s+partiellement\s+vacante\s+de\s+(?:Monsieur|Madame|M\.|Mme)?\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+){1,4})",
    re.IGNORECASE,
)

RX_ADMIN_SV_VAC_ALT = re.compile(
    r"administrateur\s+provisoire\s+à\s+succession\s+vacante,?\s+de\s+(?:Monsieur|Madame|M\.|Mme)?\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+){1,4})",
    re.IGNORECASE,
)

RX_SV_NE_LE = re.compile(
    r"succession?\s+de\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s'’\-]+?),\s*(né\(e\)?|né|née)\s+le",
    re.IGNORECASE,
)

RX_SV_DESHERENCE_SIMPLE = re.compile(
    r"succession?\s+(?:en\s+d[ée]sh[ée]rence\s+)?de\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s'’\-]+?),",
    re.IGNORECASE,
)

RX_ADMIN_PROV_SUCC_DE = re.compile(
    r"administrateur\s+provisoire\s+à\s+la\s+succession\s+de\s*:?\s*(?:M(?:onsieur)?\.?\s+)?([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+){1,5})",
    re.IGNORECASE,
)

RX_SRV_NOMPRENOM = re.compile(
    r"succession\s+réputée\s+vacante\s+de\s+(?:M(?:onsieur)?\.?|Madame)?\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+)",
    re.IGNORECASE,
)

RX_SV_MONSIEUR_PN = re.compile(
    r"succession\s+(?:vacante|en\s+d[ée]sh[ée]rence)?\s+de\s+Monsieur\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+)*)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'’\-]+)",
    re.IGNORECASE,
)

# Bloc "En cause de : … (jusqu'à Contre : / Intimés : / fin)"
RX_EN_CAUSE_BLOCK = re.compile(
    r"en\s*cause\s*de\s*:?\s*(?P<bloc>.+?)(?=\b(?:contre|intim[ée]s?|défendeur|defendeur|défenderesse|defenderesse)\b\s*:|$)",
    re.IGNORECASE | re.DOTALL
)

# Items "NOM, Prénoms" avec numérotation et RN optionnel
RX_EN_CAUSE_ITEM_NP = re.compile(rf"""
    (?:^|\s*;\s*)                     # début d'item (début bloc ou après ;)
    (?:\d+\s*[\.\)]\s*)?              # "1." / "2)" optionnel
    (?P<nom>{NOM_BLOCK})\s*,\s*(?P<prenoms>{PRENOMS_BLK})
    (?:\s*\(\s*{RN_TOKEN_ANY}\b[^)]*\))?   # (RN/NRN/NN …) optionnel
""", re.IGNORECASE | re.VERBOSE)

# Items "Prénoms NOM" (au cas où) avec civilité et RN optionnels
RX_EN_CAUSE_ITEM_PN = re.compile(rf"""
    (?:^|\s*;\s*)
    (?:\d+\s*[\.\)]\s*)?
    (?:Monsieur|Madame|M(?:r|me)?\.?)?\s*
    (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})
    (?:\s*\(\s*{RN_TOKEN_ANY}\b[^)]*\))?
""", re.IGNORECASE | re.VERBOSE)


RX_EN_CAUSE_DE_NOM = re.compile(
    r"""
    en\s*cause\s*de\s*:?\s*                 # libellé 'EN CAUSE DE :'
    (?P<nom>[^,\n\r]+?)\s*,\s*              # nom(s) de famille en bloc avant la virgule
    (?P<prenoms>(?:[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ'’\-]+
                 (?:\s+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ'’\-]+){0,3})) # 1 à 4 prénoms
    """,
    re.IGNORECASE | re.VERBOSE,
)
# En cause de : Monsieur Prénom(s) NOM (RN/NN/NRN optionnel)
RX_EN_CAUSE_PN = re.compile(rf"""
    en\s+cause\s+de\s*:\s*
    (?:Monsieur|Madame|M(?:r|me)?\.?)\s+
    (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})
    (?:\s*[,;]?\s*\(?(?:{RN_TOKEN})\)?\s*[\d.\-/\s]{{6,}})?   # RN/NN/NRN optionnel
    (?=\s*(?:,|;|\.|\(|\)|\bdomicili|\bné|\bdec|$))          # stop propre
""", re.IGNORECASE | re.VERBOSE)

# Variante « NOM, Prénoms » (au cas où l’ordre est inversé)
RX_EN_CAUSE_NP = re.compile(rf"""
    en\s+cause\s+de\s*:\s*
    (?:Monsieur|Madame|M(?:r|me)?\.?)\s+
    (?P<nom>{NOM_BLOCK})\s*,\s*(?P<prenoms>{PRENOMS_BLK})
    (?:\s*[,;]?\s*\(?(?:{RN_TOKEN})\)?\s*[\d.\-/\s]{{6,}})?   # RN/NN/NRN optionnel
    (?=\s*(?:,|;|\.|\(|\)|\bdomicili|\bné|\bdec|$))
""", re.IGNORECASE | re.VERBOSE)

# 1) Forme NP avec virgule : "le nommé : NOM, Prénoms"
RX_CONDAMNE_LE_NOMME_NP = re.compile(rf"""
    condamn[éée]\s+                # a condamné / a été condamné(e) (souple)
    (?:par\s+)?(?:la\s+)?(?:cour|tribunal)?\s*   # optionnel, tolérant
    .*?\b(?:le|la)\s+nomm[ée]\s*   # le/la nommé(e)
    [:–-]?\s*                      # : ou tiret optionnel
    (?P<nom>{NOM_BLOCK})\s*,\s*(?P<prenoms>{PRENOMS_BLK})
    (?=\s*(?:,|;|\.|\(|\)|\bné|\bnee|\bné\(e\)|{RN_TOKEN}|\bRR?N\b|$))
""", re.IGNORECASE | re.VERBOSE | re.DOTALL)

# 2) Forme PN (au cas où l’ordre apparaît sans virgule) : "le nommé : Prénoms NOM"
RX_CONDAMNE_LE_NOMME_PN = re.compile(rf"""
    condamn[éée]\s+.*?\b(?:le|la)\s+nomm[ée]\s*[:–-]?\s*
    (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})
    (?=\s*(?:,|;|\.|\(|\)|\bné|\bnee|\bné\(e\)|{RN_TOKEN}|\bRR?N\b|$))
""", re.IGNORECASE | re.VERBOSE | re.DOTALL)


def clean_doublons_debut_fin(s: str) -> str:
    """
    Supprime un doublon exact au tout début ou à la toute fin de la chaîne.
    Ex: 'Jean Jean Dupont' -> 'Jean Dupont' ; 'Dupont Marc Marc' -> 'Dupont Marc'
    Ne touche pas aux prénoms composés type 'Jean-Baptiste'.
    """
    s = _norm_spaces(s)
    if not s:
        return s
    parts = s.split()

    # doublon en tête
    if len(parts) >= 2 and parts[0].lower() == parts[1].lower():
        parts = parts[1:]

    # doublon en fin
    if len(parts) >= 2 and parts[-1].lower() == parts[-2].lower():
        parts = parts[:-1]

    return " ".join(parts)



def extract_name_from_text(text):
    return extract_name_before_birth(text)


def invert_if_comma(s: str) -> str:
    if "," in s:
        left, right = [p.strip() for p in s.split(",", 1)]
        if left and right:
            return f"{right} {left}"
    return s

# === AJOUTS UTILES EN HAUT DU FICHIER ===
# ⬇️ AJOUT ICI : supprime les doublons en début/fin



def _strip_accents(s: str) -> str:
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def _norm_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def _drop_single_letter_initials(s: str) -> str:
    tokens = s.split()
    keep = [t for t in tokens if not re.fullmatch(r"[A-Za-z]\.?", t)]
    return " ".join(keep) if keep else s

def _norm_key_loose(s: str) -> str:
    # clé de regroupement “souple”: minuscule, sans accents, sans initiales d’1 lettre
    s = _strip_accents(s).lower()
    s = _drop_single_letter_initials(s)
    return _norm_spaces(s)

def _choose_canonical(variants: list[str]) -> str:
    # on préfère la variante avec le + de mots “utiles” (sans initiales d’1 lettre)
    def score(v: str):
        no_init = _drop_single_letter_initials(v)
        return (len(no_init.split()), len(v))  # nb mots utiles puis longueur
    return sorted(variants, key=score, reverse=True)[0]

def group_names_for_meili(noms_nettoyes: list[str]):
    """
    Regroupe les variantes d’un même nom en {canonical, aliases}
    et prépare des champs prêts pour Meili/Postgre.
    """
    groups = {}  # key_loose -> set(variants)
    for n in noms_nettoyes:
        # --- pré-nettoyage anti "né ..." / "pour la succession de ..." ---
        prefix_regex = re.compile(rf"^\s*{PREFIXES}\s+", flags=re.IGNORECASE)
        n = prefix_regex.sub("", n)
        n = re.split(CONTEXT_CUT, n, 1, flags=re.IGNORECASE)[0]
        n = n.replace("|", " ").replace(";", " ").replace(":", " ")
        n = invert_if_comma(n)
        n = clean_doublons_debut_fin(n)
        n = re.sub(r"\b([A-Za-zÀ-ÿ'-]+)\s+\1\b$", r"\1", n, flags=re.IGNORECASE)
        n = _norm_spaces(n)

        key = _norm_key_loose(n)
        if not key:
            continue
        groups.setdefault(key, set()).add(n)

    records, canonicals, all_aliases = [], [], set()
    for key, variants in groups.items():
        variants = list(dict.fromkeys(_norm_spaces(v) for v in variants))
        canonical = _choose_canonical(variants)
        aliases = [v for v in variants if v != canonical]
        records.append({"canonical": canonical, "aliases": aliases})
        canonicals.append(canonical)
        all_aliases.update(variants)

    return {"records": records, "canonicals": canonicals, "aliases_flat": list(all_aliases)}



def nettoyer_noms_avances(noms, longueur_max=80):
    """
    Nettoie une liste de noms :
    - Supprime les préfixes 'né', 'née', 'pour la succession de', etc.
    - Coupe le contexte inutile (née à..., RN..., domicilié...)
    - Supprime les titres et doublons
    - Normalise pour éviter les répétitions ou versions tronquées
    """

    titres_regex = r"\b(madame|monsieur|mme|mr)\b[\s\-]*"

    # Termes à ignorer
    termes_ignores = ["la personne", "personne", "Par ordonnance", "de la", "dans les",
        "feu M", "feu", "feue", "désigné Maître", "présente publication",
        "de sexe masculin", "de sexe féminin", "de sexe feminin",  # <-- corrigé
        "sexe masculin", "sexe féminin", "sexe feminin",
        "masculin", "féminin", "feminin", "comptabilité", "intention frauduleuse", "avoir détourné",
        "avoir detourne", "contrevenu", "dispositions", "partie appelante", "représentée", "appelante",
        "l'etat belge spf finances","l etat belge spf finances", "L'ETAT BELGE SPF FINANCES", "etat belge", "spf finances"]

    def invert_if_comma(s: str) -> str:
        if "," in s:
            parts = [p.strip() for p in s.split(",", 1)]
            if len(parts) == 2:
                return f"{parts[1]} {parts[0]}"
        return s

    def extraire_nom_depuis_phrase(nom):
        patterns = [
            r"pour la succession de\s+(.*)",
            r"en possession de la succession de\s+(.*)",
            r"succession de\s+(.*)",

        ]
        for pattern in patterns:
            match = re.search(pattern, nom, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return nom.strip()

    def nettoyer_et_normaliser(nom):
        # extraction initiale
        if nom.lower().startswith("le juge de paix du canton de visé a désigné à".lower()):
            nom = re.sub(r"le\s+juge\s+de\s+paix\s+du\s+canton\s+de\s+Visé\s+a\s+désigné\s+à\s+", "", nom,
                         flags=re.IGNORECASE)

        nom = extraire_nom_depuis_phrase(nom)

        # suppression préfixes "né ...", "pour la succession ..."
        nom = re.sub(rf"^\s*{PREFIXES}\s+", "", nom, flags=re.IGNORECASE)

        # suppression titres
        nom = re.sub(titres_regex, '', nom, flags=re.IGNORECASE)
        # 🔹 suppression de tous les chiffres et signes associés
        nom = re.sub(r"\d+", "", nom)  # chiffres simples
        nom = re.sub(r"\s*[\/\-]\s*\d+\w*", "", nom)  # ex: 12/3, 45-A, 123B
        # coupe le contexte après le nom
        nom = re.split(CONTEXT_CUT, nom, 1, flags=re.IGNORECASE)[0]

        # normalisation ponctuation/espace
        nom = nom.replace(";", " ").replace("|", " ").replace(":", " ")
        nom = re.sub(r"\s+", " ", nom).strip(" ,;-")

        # inversion éventuelle "Nom, Prénom"
        nom = invert_if_comma(nom)

        # suppression doublon final ("Moll Moll" → "Moll")
        nom = re.sub(r"\b([A-Za-zÀ-ÿ'-]+)\s+\1\b$", r"\1", nom, flags=re.IGNORECASE)

        # génération clé normalisée
        nom_normalise = ''.join(
            c for c in unicodedata.normalize('NFD', nom)
            if unicodedata.category(c) != 'Mn'
        ).lower().strip()
        nom_normalise = re.sub(r'\s+', ' ', nom_normalise)
        nom = re.sub(r'\s+', ' ', nom).strip()

        return nom, nom_normalise

    noms_nettoyes = []
    noms_normalises = []
    for nom in noms:

        # ignorer si ça commence par "ne pas avoir ..."

        nom_nettoye, norm = nettoyer_et_normaliser(nom)
        print(nom_nettoye, norm)
        if any(terme.strip() in nom_nettoye.lower().strip() for terme in termes_ignores):
            continue
        if len(nom_nettoye) > longueur_max:
            continue


        # Accepte un token unique s'il ressemble à un NOM en majuscules (UPWORD)
        if len(nom_nettoye.split()) < 2 and not re.fullmatch(UPWORD, nom_nettoye):
            continue

        to_remove = []
        dup = False
        for i, exist in enumerate(noms_normalises):
            if norm == exist or norm in exist:
                dup = True
                break
            if exist in norm:
                to_remove.append(i)

        if dup:
            continue
        for idx in reversed(to_remove):
            del noms_normalises[idx]
            del noms_nettoyes[idx]

        noms_nettoyes.append(nom_nettoye)
        noms_normalises.append(norm)
    # ⚠️ avant le return, applique le filtre
    filtrés_nettoyes = []
    filtrés_normalises = []

    for nom_nettoye, norm in zip(noms_nettoyes, noms_normalises):
        if "greffier" not in nom_nettoye.lower() and "greffier" not in norm.lower():
            filtrés_nettoyes.append(nom_nettoye)
            filtrés_normalises.append(norm)

    return filtrés_nettoyes


def extract_name_before_birth(texte_html):
    from bs4 import BeautifulSoup
    import re

    soup = BeautifulSoup(texte_html, 'html.parser')
    full_text = soup.get_text(separator=" ").strip()

    nom_list = []
    if "Toussaint" in full_text:
        print(f"→ OKDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD: Nom trouvé dans le texte brut: {full_text}")

    # ______________________________________________________________________________________________________

    #                       *******************  PERSONNES PHYSIQUES *****************************

    # _____________________________________________________________________________________________________

    # -----------------
    #     SUCCESSIONS
    # -----------------

    # -----------------
    #     SUCCESSIONS
    # -----------------
    for m in RX_INTERDIT_A.finditer(full_text):
        nom = (m.group('nom') or m.group('nom2')).strip()
        prenoms = (m.group('prenoms') or m.group('prenoms2')).strip()
        nom_list.append(f"{nom}, {prenoms}")

    for m in RX_LE_NOMME_NP.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    for m in RX_NR_NP.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    for m in RX_NP_NE.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    for m in RX_SV_ANY.finditer(full_text):
        nom_list.append(m.group(1).strip())

    for m in RX_SV_NOM_COMPLET_VIRG.finditer(full_text):
        nom_list.append(f"{m.group(1).strip()}, {m.group(2).strip()}")

    for m in RX_SRV_SIMPLE.finditer(full_text):
        nom_list.append(m.group(1).strip())

    for m in RX_SRV_NP.finditer(full_text):
        nom_list.append(f"{m.group(1).strip()}, {m.group(2).strip()}")

    # (déjà précompilés ailleurs) — personnes visées par la succession / curateur
    for m in RX_SV_PN.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    for m in RX_SV_NP.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    for m in RX_CURATEUR_SV_PN.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    for m in RX_CURATEUR_SV_NP.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    # variantes supplémentaires
    for m in RX_SV_NOM_VIRG_PRENOMS.finditer(full_text):
        nom_list.append(f"{m.group(1).strip()}, {m.group(2).strip()}")

    for m in RX_SV_FEU_PAIRE.finditer(full_text):
        nom_list.append(f"{m.group(1).strip()}, {m.group(2).strip()}")

    # 🔹 Ajout spécifique pour : "mesures de protection à l’égard de la personne et des biens de l’intéressé Prénom Nom, né à ..."
    for m in RX_PROTECTION_INTERESSE_NE.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    for m in RX_SV_FEU_VARIANTES.finditer(full_text):
        nom_list.append(m.group(1).strip())

    for m in RX_SRV_M_RN.finditer(full_text):
        nom_list.append(m.group(1).strip())

    for m in RX_ADMIN_SV_SPEC.finditer(full_text):
        parts = m.group(1).strip().split()
        if len(parts) >= 2:
            nom_list.append(f"{parts[-1]}, {' '.join(parts[:-1])}")

    for m in RX_SV_PART_VAC.finditer(full_text):
        parts = m.group(1).strip().split()
        if len(parts) >= 2:
            nom_list.append(f"{parts[-1]}, {' '.join(parts[:-1])}")

    for m in RX_ADMIN_SV_VAC_ALT.finditer(full_text):
        parts = m.group(1).strip().split()
        if len(parts) >= 2:
            nom_list.append(f"{parts[-1]}, {' '.join(parts[:-1])}")

    for m in RX_SV_NE_LE.finditer(full_text):
        nom_list.append(m.group(1).strip())

    for m in RX_SV_DESHERENCE_SIMPLE.finditer(full_text):
        nom_list.append(m.group(1).strip())

    for m in RX_ADMIN_PROV_SUCC_DE.finditer(full_text):
        nom_list.append(m.group(1).strip())

    for m in RX_SRV_NOMPRENOM.finditer(full_text):
        nom_list.append(f"{m.group(2).strip()}, {m.group(1).strip()}")

    for m in RX_PROTECTION_INTERESSE_NOM_SEUL.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    for m in RX_SV_MONSIEUR_PN.finditer(full_text):
        nom_list.append(f"{m.group(2).strip()}, {m.group(1).strip()}")

    for m in RX_EN_CAUSE_DE_NOM.finditer(full_text):
        nom_list.append(f"{m.group(2).strip()}, {m.group(1).strip()}")

    for m in RX_EN_CAUSE_PN.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    for m in RX_EN_CAUSE_NP.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    for m in RX_CONDAMNE_LE_NOMME_NP.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    for m in RX_CONDAMNE_LE_NOMME_PN.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")
    # (A) Civilité + Prénoms + NOM suivi d’un (RN …)
    for m in RX_CIVILITE_PN_RN.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    # (B) “appel interjeté par …” (ou “appel de …”), civilité + Prénoms + NOM (RN optionnel)
    for m in RX_APPEL_PAR_CIVILITE.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    # (C) “relativement à la personne de …”, civilité + Prénoms + NOM (RN optionnel)
    for m in RX_REL_PERSONNE_DE.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    # -----------------
    #  MONSIEUR/MADAME
    # -----------------

    # -----------------
    #   NOM
    # -----------------

    # -----------------
    #   ADMINISTRATEUR
    # -----------------

    # -----------------
    #    DECLARE
    # -----------------
    RX_DECL_NP_RRN = re.compile(rf"""
        \bdéclare\b\s+
        (?P<nom>{NOM_BLOCK})\s*,\s*(?P<prenoms>{PRENOMS_BLK})
        \s*\(\s*{RN_TOKEN_ANY}.*?\)
    """, re.IGNORECASE | re.VERBOSE)

    RX_DECL_CIVILITE_NP_RRN = re.compile(rf"""
        \bdéclare\b\s+
        (?:Monsieur|Madame|M(?:r|me)?\.?)\s+
        (?P<nom>{NOM_BLOCK})\s*,\s*(?P<prenoms>{PRENOMS_BLK})
        \s*\(\s*{RN_TOKEN_ANY}.*?\)
    """, re.IGNORECASE | re.VERBOSE)

    # 🔹 0.ter : Cas "Madame/Monsieur NOM, Prénom, né(e) à ..."
    match_mp = re.findall(
        r"(?:Madame|Monsieur)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s\-']+?),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s\-']+?),\s+(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )
    for nom_famille, prenoms, _ in match_mp:
        nom_complet = f"{nom_famille.strip()}, {prenoms.strip()}"
        nom_list.append(nom_complet)

    # 🔹 0.ter.a : Cas "… concernant NOM, Prénom :"
    match_concernant = re.findall(
        r"\bconcernant\s+([A-ZÀ-Ÿ][A-ZÀ-Ÿ\-']+)\s*,\s*([A-ZÀ-ÿ][A-Za-zÀ-ÿ\-'\s]+?)\s*:",
        full_text,
        re.IGNORECASE
    )
    for nom, prenoms in match_concernant:
        nom_list.append(f"{nom.strip()}, {prenoms.strip()}")

    # 🔹 0.ter.b : Cas "Madame/Monsieur/Me NOM, Prénom, née/né …"
    match_admin_nomprenom = re.findall(
        r"\b(?:Madame|Monsieur|M(?:me|lle)?|Mme|Mlle|Ma(?:ître|itre)|Me)\s+"
        r"([A-ZÀ-Ÿ][A-ZÀ-Ÿ\-']+)\s*,\s*"
        r"([A-ZÀ-ÿ][A-Za-zÀ-ÿ\-'\s]+?)"
        r"(?=,\s*n[ée]e|\s+n[ée]\b|,\s*domicili|,\s*à\b|\s+a\s+été\b|\s+ayant\b|\s+dont\b|$)",
        full_text,
        re.IGNORECASE
    )
    for nom, prenoms in match_admin_nomprenom:
        nom_list.append(f"{nom.strip()}, {prenoms.strip()}")

    match_incapable_nom = re.finditer(
        r"(.{1,60})\b(est\s+(?:déclaré\s+)?incapable)\b",
        full_text,
        re.IGNORECASE
    )
    for m in match_incapable_nom:
        avant = m.group(1).strip()

        # Essaye d'extraire jusqu'à 4 composants pour le nom complet
        nom_candidat = re.search(
            r"(?:Monsieur|Madame|Mr|Mme)?\s*((?:[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]{2,}\s*){1,4})$",
            avant,
            re.IGNORECASE
        )
        if nom_candidat:
            nom_brut = nom_candidat.group(1).strip()
            nom_parts = nom_brut.split()
            if len(nom_parts) >= 2:
                # dernière partie = nom de famille, le reste = prénoms
                nom_complet = f"{nom_parts[-1]}, {' '.join(nom_parts[:-1])}"
                nom_list.append(nom_complet.strip())
    match_structured_nom_prenom = re.findall(
        r"\b\d\)\s*Nom\s+et\s+prénoms\s*:\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s*((?:[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s*){1,4})",
        full_text,
        re.IGNORECASE
    )
    for nom, prenoms in match_structured_nom_prenom:
        nom_complet = f"{nom.strip()}, {prenoms.strip()}"
        nom_list.append(nom_complet)
    match_le_nommer_nrn = re.findall(
        r"le nommé\s*:?\s*\S*\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+((?:[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s*){1,5}),?\s+NRN",
        full_text,
        re.IGNORECASE
    )
    for nom, prenoms in match_le_nommer_nrn:
        nom_complet = f"{nom.strip()}, {prenoms.strip()}"
        nom_list.append(nom_complet)


    # 🔹 1. "NOM, né(e) le jj/mm/aaaa à VILLE"
    match1 = re.findall(
        r"([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s\-']+),\s*(né\(e\)?|né|née)\s*le\s*\d{2}/\d{2}/\d{4}\s*à\s*[A-Za-z\s\-']+",
        full_text,
        re.IGNORECASE
    )
    for m in match1:
        nom_list.append(m[0].strip())

    # 🔹 2. "NOM, né(e) le aaaa-mm-jj à VILLE"
    match2 = re.findall(
        r"([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s\-']+),\s*(né\(e\)?|né|née)\s*le\s*\d{4}-\d{2}-\d{2}\s*à\s*[A-Za-z\s\-']+",
        full_text,
        re.IGNORECASE
    )
    for m in match2:
        nom_list.append(m[0].strip())

    # 🔹 3. "NOM, né(e) le jj mois aaaa à VILLE"
    match3 = re.findall(
        r"([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s\-']+),\s*(né\(e\)?|né|née)\s*le\s*\d{1,2}\s+\w+\s+\d{4}\s*à\s*[A-Za-z\s\-']+",
        full_text,
        re.IGNORECASE
    )
    for m in match3:
        nom_list.append(m[0].strip())

    # 🔹 4. Cas léger : "NOM né à"
    match4 = re.findall(
        r"([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s\-']+?)\s+(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )
    for m in match4:
        nom_list.append(m[0].strip())

    # 🔹 5. "NOM, né(e) à VILLE le jj mois aaaa"
    match5 = re.findall(
        r"([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s\-']+),\s*(né\(e\)?|né|née)\s+à\s+[A-Za-z\s\-']+\s+le\s+\d{1,2}\s+\w+\s+\d{4}",
        full_text,
        re.IGNORECASE
    )
    for m in match5:
        nom_list.append(m[0].strip())

    match6 = re.findall(
        r"([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s\-']+),\s*(né\(e\)?|né|née)\s+à\s+le\s+\d{1,2}\s+\w+\s+\d{4}",
        full_text,
        re.IGNORECASE
    )
    for m in match6:
        nom_list.append(m[0].strip())
    # va falloir autoriser plus de prenoms
    match7 = re.findall(
        r"(Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )
    for titre, prenom, nom, _ in match7:
        nom_complet = f"{nom}, {prenom}"
        nom_list.append(nom_complet.strip())
    # ✅ Supprimer doublons tout en gardant l’ordre
    match7b = re.findall(
        r"(?:Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )
    for prenom, nom, _ in match7b:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)
    # 🔹 Cas : "Monsieur Prénom NOM; né à ..."
    match7d = re.findall(
        r"(?:Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+);?\s+(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )
    for prenom, nom, _ in match7d:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)
    match7c = re.findall(
        r"(?:Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+né\s+à",
        full_text,
        re.IGNORECASE
    )
    for prenom, nom in match7c:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)

    # 🔹 Cas : "Monsieur NOM, Prénom; né à ..."
    match_special_semicolon = re.findall(
        r"(?:Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+);\s+(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )
    for nom, prenom, _ in match_special_semicolon:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)

    match_semicolon = re.findall(
        r"(?:Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\- ]+),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+);?\s+(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )
    for nom, prenom, _ in match_semicolon:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)
    # 🔹 Cas : "Monsieur NOM, Prénom; né à <ville> le <date>"
    match_semi = re.findall(
        r"(Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+);\s+(né|née)\s+à",
        full_text,
        re.IGNORECASE
    )
    for civ, nom, prenom, _ in match_semi:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)

    match_condamne = re.findall(
        r"a\s+condamné\s*:?\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)",
        full_text,
        re.IGNORECASE
    )
    for nom, prenom in match_condamne:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)

    # 🔹 Cas spécial : "Monsieur NOM, Prénom; né à ..."
    match_pg_semicolon = re.findall(
        r"(?:Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+);\s+(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )
    for nom, prenom, _ in match_pg_semicolon:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)
    # 🔹 Cas : "Monsieur NOM, Prénom; né à ..."
    match_pg = re.findall(
        r"(?:Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+);\s+(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )
    for nom, prenom, _ in match_pg:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)

    matches = re.findall(
        r"administrateur\s+des\s+biens\s+de.{0,30}?(?:Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)",
        full_text,
        flags=re.IGNORECASE
    )
    for nom, prenom in matches:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)

    matches = re.findall(
        r"(?:des\s+biens\s+et\s+de\s+la\s+personne|de\s+la\s+personne\s+et\s+des\s+biens|des\s+biens\s+de|de\s+la\s+personne\s+de)\s+.{0,30}?(?:M(?:onsieur|me)?\s+)?([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)",
        full_text,
        flags=re.IGNORECASE
    )
    for prenom, nom in matches:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)

    # 🔹 Cas : "1) Nom et prénoms : Prénom NOM NOM2 ..."
    match_structured_numbered = re.findall(
        r"\d\)\s*Nom\s+et\s+prénoms?\s*:\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)*)",
        full_text,
        flags=re.IGNORECASE
    )
    for nom_complet in match_structured_numbered:
        nom_list.append(nom_complet.strip())
    # 🔹 0.quater : Cas "[Prénom NOM], né(e) à ..."
    match8 = re.findall(
        r"\b([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )
    for nom in match8:
        nom_list.append(nom[0].strip())

    # 🔹 8. Cas : "Prénom NOM, né(e) le <date>" (sans 'à' ensuite)
    match9 = re.findall(
        r"\b([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+(né|née|né\(e\))\s+le\s+\d{1,2}\s+\w+\s+\d{4}",
        full_text,
        re.IGNORECASE
    )
    for nom in match9:
        nom_list.append(nom[0].strip())

    # 🔹 9. Cas : "Monsieur/Madame NOM Prénom, inscrit au registre national..."
    match10 = re.findall(
        r"(Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+inscrit(?:e)?\s+au\s+registre\s+national",
        full_text,
        re.IGNORECASE
    )
    for civ, nom, prenom in match10:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)

    match11 = re.findall(
        r"\b([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+RN\s+\d{5,15},?\s+(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )
    for nom in match11:
        nom_list.append(nom[0].strip())

    match12 = re.findall(
        r"(?:Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),[\s\S]{0,300}personne\s+(?:à\s+protéger|protégée)",
        full_text,
        re.IGNORECASE
    )
    for prenom, nom in match12:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)

    # 🔹 13. Cas : "Prénom NOM, ayant pour numéro de registre national ..., né à ..., personne à protéger"
    match13 = re.findall(
        r"\b([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+ayant\s+pour\s+numéro\s+de\s+registre\s+national\s+\d{11,12},\s+(né|née|né\(e\))\s+à\s",
        full_text,
        re.IGNORECASE
    )
    for nom in match13:
        nom_list.append(nom[0].strip())

    # 🔹 10. Cas : "Prénom NOM, RN <numéro>, né(e) à ..."
    match14 = re.findall(
        r"\b([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+RN\s+\d{9,15},?\s+(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )
    for nom in match14:
        nom_list.append(nom[0].strip())
    # 🔹 11. Cas : "Monsieur/Madame Prénom NOM, registre national numéro ..."
    match15 = re.findall(
        r"(Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+registre\s+national\s+numéro\s+\d{9,15}",
        full_text,
        re.IGNORECASE
    )
    for civ, prenom, nom in match15:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)
    match16 = re.findall(
        r"(?:Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),[\s\S]{0,200}?(?:placé|placée)\s+sous\s+un\s+régime\s+de\s+représentation",
        full_text,
        re.IGNORECASE
    )
    for prenom, nom in match16:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)

    match_fixed = re.findall(
        r"(?:Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s*né\s+à\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s+le\s+\d{1,2}\s+\w+\s+\d{4}",
        full_text,
        re.IGNORECASE
    )
    for prenom, nom in match_fixed:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)
    # 🔹 Cas : "Monsieur NOM, Prénom, né le <date>"
    match_mn_nomprenom = re.findall(
        r"(?:Monsieur|Madame)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-\s]+?),\s+(né|née|né\(e\))\s+le\s+\d{2}/\d{2}/\d{4}",
        full_text,
        re.IGNORECASE
    )
    for nom, prenom, _ in match_mn_nomprenom:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)

    # 🔹 Cas : "le nommé <code> - NOM Prénom, NRN ..."
    match_nom_nr_flexible = re.findall(
        r"le nommé\s+\S+\s*[-–]\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+NRN",
        full_text,
        re.IGNORECASE
    )
    for nom, prenom in match_nom_nr_flexible:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)


    match_absence = re.findall(
        r"(?:déclare|a\s+déclaré)\s+l'absence\s+de\s*:?\s*.{0,30}?(?:Monsieur|Madame|M\.|Mme)?\s*([A-ZÉÈÊÀÂ'\-]+),?\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\- ]+)",
        full_text,
        flags=re.IGNORECASE
    )
    for nom, prenoms in match_absence:
        nom_complet = f"{nom.strip()}, {prenoms.strip()}"
        nom_list.append(nom_complet)


    # 🔹 Cas : "Monsieur Prénom NOM NOM2 NOM3 (RN ...)"
    match_rn_nom = re.findall(
        r"(?:Monsieur|Madame)\s+((?:[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s+){1,3}[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)\s+\(RN\s+\d{2}[.\-/]\d{2}[.\-/]\d{2}",
        full_text,
        re.IGNORECASE
    )

    for full_nom in match_rn_nom:
        noms = full_nom.strip().split()
        if len(noms) >= 2:
            prenom = noms[0]
            nom = " ".join(noms[1:])
            nom_complet = f"{nom}, {prenom}"
            nom_list.append(nom_complet)

    match_appel_fonde = re.findall(
        r"déclare\s+fondé\s+l[’']?appel\s+de\s+(?:Monsieur|Madame|Mr|Mme)?\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+){0,3})",
        full_text,
        flags=re.IGNORECASE
    )

    for nom_complet in match_appel_fonde:
        noms = nom_complet.strip().split()
        if len(noms) >= 2:
            prenom = noms[0]
            nom = " ".join(noms[1:])
            nom_list.append(f"{nom}, {prenom}")

    # ✅ Cas : "succession vacante de M./Mme/Monsieur/Madame Prénom NOM [Nom2 Nom3...]"
    match_sv_flexible = re.findall(
        r"succession\s+(?:vacante|en\s+d[ée]sh[ée]rence)?\s+de\s+(?:M(?:me|adame|onsieur)?\.?\s+)?([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+){0,3})",
        full_text,
        re.IGNORECASE
    )
    for nom_complet in match_sv_flexible:
        nom_list.append(nom_complet.strip())

    # ✅ Cas : "à la succession de M./Mme NOM [NOM2...]"
    match_succession_simple = re.findall(
        r"(?:à\s+la\s+succession\s+de|succession\s+de)\s+(?:M(?:me|adame|onsieur)?\.?\s+)?([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+){0,3})",
        full_text,
        re.IGNORECASE
    )
    for nom_complet in match_succession_simple:
        nom_list.append(nom_complet.strip())


    # 🔹 Cas : "le nommé : 1492 C 2025 NOM, Prénom, NRN ..."
    match_nom_nr = re.findall(
        r"le nommé\s*:\s*(?:\d+\s*[A-Z]\s*\d{4})\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+NRN\s+\d{2}[.\-/]\d{2}[.\-/]\d{2}[-\s.]\d{3}[.\-/]\d{2}",
        full_text,
        re.IGNORECASE
    )
    for nom, prenom in match_nom_nr:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)
        # 🔹 Cas : "Nom prénom : NOM, Prénom"
    match_structured = re.findall(
        r"Nom\s+prénom\s*:\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)",
        full_text,
        re.IGNORECASE
    )
    for nom, prenom in match_structured:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)

    # Cas "succession vacante de NOM, Prénom"
    match_sv_nomprenom = re.findall(
        r"succession\s+vacante\s+de\s+(?:M(?:onsieur|me)?\s+)?([A-ZÉÈÊÀÂa-zéèêàâçëïüö\-']+),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö\-']+)",
        full_text,
        re.IGNORECASE
    )
    for nom, prenom in match_sv_nomprenom:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)

    # Cas "NOM, Prénom, né à VILLE le 3 septembre 1951"
    match_na_le = re.findall(
        r"([A-ZÉÈÊÀÂa-zéèêàâçëïüö\-']+),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö\-']+),\s+(né|née)\s+à\s+[A-Za-z\s\-']+\s+le\s+\d{1,2}\s+\w+\s+\d{4}",
        full_text,
        re.IGNORECASE
    )
    for nom, prenom, _ in match_na_le:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)

    match_nn_generic = re.findall(
        rf"((?:{PRENOMS_BLK}\s+{NOM_BLOCK})|(?:{NOM_BLOCK}\s+{PRENOMS_BLK}))"
        rf"[^()]{0, 70}\b{RN_TOKEN}\s*\d{{2}}[.\-/]\d{{2}}[.\-/]\d{{2}}[-\s.]?\d{{3}}[.\-/]\d{{2}}",
        full_text,
        re.IGNORECASE
    )
    for m in match_nn_generic:
        nom_list.append(m.strip())

    # 🔹 Cas : "[Nom Prénom] recouvre sa pleine capacité"
    matches = re.findall(
        r"([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)[^A-Za-z]{0,30}recouvre\s+sa\s+pleine\s+capacité",
        full_text,
        flags=re.IGNORECASE
    )
    for m in matches:
        nom_list.append(m.strip())
    match_ne_a_context = re.finditer(
        r"(.{1,30})\b(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )

    for m in match_ne_a_context:
        contexte = m.group(1).strip()

        # Tente d'extraire un NOM ou "Prénom NOM" à la fin du contexte
        nom_candidat = re.search(
            r"(?:Monsieur|Madame)?\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)[,;\s]+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)?$",
            contexte,
            re.IGNORECASE
        )
        if nom_candidat:
            if nom_candidat.group(2):  # Prénom et nom
                nom_list.append(f"{nom_candidat.group(1).strip()}, {nom_candidat.group(2).strip()}")
            else:  # Un seul mot → probablement nom de famille seul
                nom_list.append(nom_candidat.group(1).strip())

    match_observation_protectrice = re.findall(
        r"mesures?\s+d[’']?observation\s+protectrice.{0,30}?(?:à\s+l'égard\s+de\s+)(?:(?:Monsieur|Madame|Mr|Mme)\s+)?([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)",
        full_text,
        flags=re.IGNORECASE
    )
    for nom in match_observation_protectrice:
        nom_list.append(nom.strip())

    for m in RX_DECL_NP_RRN.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    for m in RX_DECL_CIVILITE_NP_RRN.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    for m in RX_NOM_ET_PRENOM_LABEL.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip().replace(',', ' ')}")

    # Expression régulière pour capturer le nom complet avant "né à"
    match_noms_complets = re.findall(
        r"((?:[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s+){1,6}[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),?\s+(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )
    for nom_complet, _ in match_noms_complets:
        nom_list.append(nom_complet.strip())



    # --- En cause de : bloc + items (liste 1., 2., …) ---
    for mb in RX_EN_CAUSE_BLOCK.finditer(full_text):
        bloc = mb.group("bloc")
        for m in RX_EN_CAUSE_ITEM_NP.finditer(bloc):
            nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")
        for m in RX_EN_CAUSE_ITEM_PN.finditer(bloc):
            nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")

    noms_nettoyes = nettoyer_noms_avances(nom_list)
    return group_names_for_meili(noms_nettoyes)