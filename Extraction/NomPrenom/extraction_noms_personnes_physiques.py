import re
import unicodedata
from bs4 import BeautifulSoup
import logging

# --- Modules internes au projet ---
from Utilitaire.outils.MesOutils import strip_accents
from logger_config import setup_logger, setup_dynamic_logger, LoggedList

# ______________________________________________________________________________________________
#                                          VARIABLES GLOBALES
# -----------------------------------------------------------------------------------------------

# logger + set pour eviter les doublons de log (doc_id +adresses)
seen_nomspersonnes = set()

# ++++++++++++++++++++++++++++++++++++++
#     VARIABLES / REGEX DE NETTOYAGE
# ++++++++++++++++++++++++++++++++++++++
# ⟶ Détecte la formule “il est demandé(e) de déclarer l’absence de ”
ABS_PREF = r"(?:il\s+est\s+)?demand[ée]?\s+de\s+déclarer\s+l'absence\s+de"
# ⟶ “modifié(e) les mesures de protection à l’égard de la personne et des biens de l’intéressé”
PROT_PREF = r"modifi[ée]?\s+les\s+mesures\s+de\s+protection\s+à\s+l[’']?égard\s+de\s+la\s+personne\s+et\s+des?\s+biens\s+de\s+l[’']?intéress[ée]?"
# ⟶ Variante : queue seule “à l’égard de la personne et des biens de l’intéressé…”
INT_PREF_FULL = r"à\s+l[’']?égard\s+de\s+la\s+personne\s+et\s+des?\s+biens\s+de\s+l[’']?intéress[ée]?"
# ⟶ Variante plus courte : “et des biens de l’intéressé ”
INT_PREF_TAIL = r"et\s+des?\s+biens\s+de\s+l[’']?intéress[ée]?"
# ⟶ Liste de préfixes textuels à retirer/ignorer avant un nom (ex: “né(e)”, “succession de …”, etc.)
PREFIXES = (
    r"(?:"
    r"né(?:e)?"
    r"|pour la succession de"
    r"|succession\s+(?:en\s+d[ée]sh[ée]rence|vacante)\s+de"
    r"|en qualité de curateur à la succession vacante de"
    r"|la succession vacante de"
    r"|le\s+juge\s+de\s+paix\s+du\s+canton\s+de\s+[A-ZÉÈÊÎÔÛÀÂÇ][a-zà-ÿ\-]+(?:\s+[A-ZÉÈÊÎÔÛÀÂÇ][a-zà-ÿ\-]+)*\s+a\s+désigné\s+(?:à\s+)?" 
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

# Groupe non-capturant (?: … ) qui matche l’un des “déclencheurs” suivants (séparés par |).
# Ces déclencheurs sont utilisés pour couper / segmenter le contexte (ex: fin d’un nom ou début d’une
# info administrative).
CONTEXT_CUT = (
    r"(?:\bné(?:e)?\b|\bRN\b|\bNRN\b|\(RN|\(RRN|\bRRN\b|,?\s+inscrit[e]?\b|,?\s+domicili[é]e?\b|,?\s+décédé[e]?\b)"
)
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#   VARIABLES / REGEX PRENOMS ET NOMS ET RN
# Objectif : pouvoir reconnaître des noms/prénoms écrits en capitales, avec accents,
# apostrophes droites (') ou typographiques (’), et noms composés (espaces, traits d’union).
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# Mot en MAJUSCULES (nom de famille typique) :
# - Première lettre : majuscule avec accents possibles (ÉÈÀÂÊÎÔÛÇÄËÏÖÜŸ)
# - Suite : au moins 1 caractère parmi MAJUSCULES, apostrophes (’ ou '), tirets
#   → couvre : LUYTEN, VAN, D’ALMEIDA, O’CONNOR, VAN-DER, etc.
UPWORD = r"[A-ZÉÈÀÂÊÎÔÛÇÄËÏÖÜŸ][A-ZÉÈÀÂÊÎÔÛÇÄËÏÖÜŸ'’\-]{1,}"

# Bloc NOM (un ou plusieurs "UPWORD" séparés par espaces) :
# - 1 mot majuscule minimum, jusqu'à 5 mots (0..4 supplémentaires)
#   → LUYTEN | VAN DER MEER | D’ALMEIDA | VAN DEN BROECK
NOM_BLOCK = rf"{UPWORD}(?: \s+{UPWORD}){{0, 4}}"

# Mot prénom en "Casse Nom-Propre" :
# - 1ère lettre majuscule (accents inclus), puis minuscules/accents/apostrophes/tirets
#   → Jean, Liliane, André-Marie, D’Artagnan (le D’ est géré côté NOM_BLOCK, mais un prénom
#     composé avec tiret reste couvert, ex. Jean-Marc)
PRENOM_WORD = r"[A-ZÉÈÀÂÊÎÔÛÇ][a-zà-öø-ÿ'’\-]{1,}"

# Bloc PRÉNOMS (1 à 6 prénoms séparés par espaces)
#   → Liliane Louise Victorine, Jean Pierre Michel, etc.
PRENOMS_BLK = rf"{PRENOM_WORD}(?: \s+{PRENOM_WORD}){{0, 5}}"

# Token RN élargi (RN / RRN / NRN / NN — avec ou sans points/espaces)
RN_TOKEN = r"(?:(?:R\.?\s*){1,2}N\.?|N\.?\s*R\.?\s*N\.?|N\.?\s*N\.?)"
RN_TOKEN_ANY = RN_TOKEN # on utilisera RN_TOKEN_STRICT PAR APRES SI NECESSAIRE
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                    REGEX NETTOYAGE CHAMP
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Bruit légal à retirer des candidats de noms (avant tout filtrage)
STRIP_PHRASES_REGEX = [
    re.compile(r"\bde\s+l[’']?ancien\s+code\s+civil\b", re.IGNORECASE),
    # variantes utiles (optionnelles) :
    re.compile(r"\b(?:conform[ée]ment\s+à\s+)?(?:l[’']?)?article\s+\d+/\d+\s+de\s+l[’']?ancien\s+code\s+civil\b",
               re.IGNORECASE),
]

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                                   LES REGEX DE RECHERCHES
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ==============================
# INTERDIT
# ==============================
# Détecte les personnes à qui il est "interdit de" faire quelque chose
# Gère les civilités (Monsieur, Madame, Mr, etc.)
# Capture nom + prénoms, que ce soit dans l'ordre "Jean Dupont" ou "Dupont, Jean"
# S'arrête dès qu'on rencontre un mot du contexte (né, domicilié, etc.)
RX_INTERDIT_A = re.compile(rf"""
    \b(?:il\s+est\s+)?interdit\s+à\s+                 
    (?:Monsieur|Madame|M(?:r|me)?\.?\s+)?             
    (?:
        (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})      
        | (?P<nom2>{NOM_BLOCK})\s*, \s*(?P<prenoms2>{PRENOMS_BLK}) 
    )
    (?=                                               
        \s*,?\s*(?:né|née|né\(e\)|domicili|pour\s+une\s+durée|de\s+\d+\s+ans|;|\.|,|$)
    )
""", re.IGNORECASE | re.VERBOSE)
# ==============================
# MESURES DE PROTECTION
# ==============================
# Détecte les phrases signalant une modification des mesures de protection
# Cherche la personne concernée (intéressée), avec ses prénoms et nom
# Ne match que si la fin est propre (virgule, point, etc.)
RX_MODIF_PROTECTION_INTERESSE = re.compile(rf"""
    modifi[ée]?\s+les\s+mesures\s+de\s+protection
    \s+à\s+l[’']?égard\s+de\s+la\s+personne\s+et\s+des?\s+biens\s+de\s+l[’']?intéress[ée]?\s+
    (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})
    (?=\s*(?:,|;|\.|$))
""", re.IGNORECASE | re.VERBOSE)
# Même chose que le précédent, mais sans contrainte de ponctuation à la fin
# Utile si tu veux détecter la personne même dans des phrases mal formées
RX_PROTECTION_INTERESSE_NOM_SEUL = re.compile(rf"""
    modifi[ée]?\s+les\s+mesures\s+de\s+protection\s+à\s+l[’']?égard\s+de\s+la\s+personne\s+et\s+des?\s+biens\s+de\s+l[’']?intéress[ée]?\s+
    (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})
""", re.IGNORECASE | re.VERBOSE)
# Détecte les phrases qui précisent la personne protégée, avec contexte "né à"
# Très utile pour lier prénoms/nom + date ou lieu de naissance
RX_PROTECTION_INTERESSE_NE = re.compile(rf"""
    mesures\s+de\s+protection\s+à\s+l[’']?égard\s+de\s+la\s+personne\s+et\s+des?\s+biens\s+de\s+l[’']?intéress[ée]\s+
    (?P<prenoms>{PRENOMS_BLK})\s+(?P<nom>{NOM_BLOCK})   # prénoms puis NOM
    ,\s+(?:né|née|né\(e\))\s+à                           # suivi du "né à"
""", re.IGNORECASE | re.VERBOSE)
# ==============================
# NOMS PRENOMS GENERAL
# ==============================
RX_PRENOM_NOM_NE_A = re.compile(rf"""
    (?P<prenoms>{PRENOM_WORD}(?:\s+{PRENOM_WORD}){{0,5}})   # 1 à 6 prénoms
    \s+
    (?P<nom>[A-ZÉÈÀÂÊÎÔÛÇ][a-zà-öø-ÿ'’\-]{{1,}}             # Nom de famille casse Nom-Propre
       (?:\s+[A-ZÉÈÀÂÊÎÔÛÇ][a-zà-öø-ÿ'’\-]{{1,}}){{0,3}})   # Nom composé possible
    \s*,?\s+
    (né|née|né\(e\))\s+à                                    # Contexte obligatoire
""", re.IGNORECASE | re.VERBOSE)

# 1) Cherche : "Nom et prénom(s) : NOM, Prénom(s)" (souvent dans les formulaires ou décisions)
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
RX_ABSENCE = re.compile(
    r"présomption\s+d['’]absence\s+à\s+l[’']égard\s+de\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s'\-]+)",
    flags=re.IGNORECASE
)
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
    (?P<prenoms>{PRENOMS_BLK})\s+
    (?P<nom>{NOM_BLOCK})
    (?:\s*\(\s*{RN_TOKEN_ANY}\b[^)]*\))? 
""", re.IGNORECASE | re.VERBOSE)
# ==============================
#      NOMS PRENOMS GENERAL
# ==============================
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

# ==============================
#      CAPABLE
# ==============================
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
#         SUCCESSIONS
# =======================
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
    r"succession?\s+(?:en\s+d[ée]sh[ée]rence\s+)?de\s+"
    r"([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s'’\-,]+?)"
    r"(?=\s+(?:né|née|domicilié|domiciliée|décédé|décédée|est|sans\s+laisser))",
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

# =======================
#      EN CAUSE DE
# =======================
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

# =======================
#      CONDAMNE
# =======================
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


# Supprime un doublon exact au tout début ou à la toute fin de la chaîne.
# Exemple 'Jean Jean Dupont' -> 'Jean Dupont' ; 'Dupont Marc Marc' -> 'Dupont Marc'
# Ne touche pas aux prénoms composés type 'Jean-Baptiste'
def clean_doublons_debut_fin(s: str) -> str:

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


def extract_name_from_text(text, keyword, doc_id):
    return extract_name_before_birth(text, keyword, doc_id)


def invert_if_comma(s: str) -> str:
    if "," in s:
        left, right = [p.strip() for p in s.split(",", 1)]
        if left and right:
            return f"{right} {left}"
    return s


def _norm_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


#Supprime les initiales isolées d’une chaîne (ex: "J. Dupont", "A B. Martin").
# - Découpe la chaîne en tokens (mots séparés par des espaces).
# - Filtre tous les tokens qui sont une seule lettre (maj/min) optionnellement suivie d’un point.
#   Regex : r"[A-Za-z]\.?" → une lettre entre A–Z ou a–z suivie éventuellement d’un ".".
#   - Rejoint les tokens restants avec des espaces.
#   - Si tout a été supprimé, retourne la chaîne originale pour éviter de renvoyer vide.
def _drop_single_letter_initials(s: str) -> str:

    tokens = s.split()
    keep = [t for t in tokens if not re.fullmatch(r"[A-Za-z]\.?", t)]
    return " ".join(keep) if keep else s


def _norm_key_loose(s: str) -> str:
    # clé de regroupement “souple”: minuscule, sans accents, sans initiales d’1 lettre
    s = strip_accents(s).lower()
    s = _drop_single_letter_initials(s)
    return _norm_spaces(s)


def _choose_canonical(variants: list[str]) -> str:
    """
    Sélectionne la meilleure variante d’un nom parmi plusieurs possibilités.

    ⚙️ Stratégie :
    - On préfère les variantes avec le plus de "mots utiles"
      (c’est-à-dire en ignorant les initiales d’une seule lettre).
    - En cas d’égalité, on départage par la longueur totale de la chaîne.

    Exemple :
        ["J. Dupont", "Jean Dupont", "Dupont"]
        ➝ "Jean Dupont" (car 2 mots utiles contre 1 pour les autres)
    """

    # Fonction interne qui calcule un "score" pour chaque variante
    def score(v: str):
        no_init = _drop_single_letter_initials(v)   # Supprime les initiales isolées
        return (
            len(no_init.split()),  # 1️⃣ Priorité au nombre de mots "utiles"
            len(v)                 # 2️⃣ Puis la longueur totale de la chaîne
        )

    # Trie toutes les variantes par score décroissant et prend la meilleure
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
        Fonction avancée de nettoyage et de normalisation de noms extraits de texte libre.

        Étapes effectuées :
        ---------------------------------------------------------------------
        1. Suppression des préfixes contextuels :
            - Ex. : "né le...", "pour la succession de...", etc.
            - Détection spéciale pour certaines phrases juridiques longues.

        2. Extraction du nom à partir de formulations types :
            - Ex. : "succession de Jean Dupont" → "Jean Dupont"

        3. Nettoyage syntaxique :
            - Suppression des titres (Monsieur, Madame, etc.)
            - Suppression des chiffres, formats numériques (ex. "12/3", "45-A")
            - Nettoyage des ponctuations parasites (| ; :)

        4. Reformatage du nom :
            - Inversion automatique si au format "NOM, Prénom"
            - Suppression des doublons ("Dupont Dupont" → "Dupont")
            - Uniformisation des espaces

        5. Génération d'une clé normalisée :
            - Minuscules
            - Sans accents
            - Espaces uniformisés
            - Objectif : comparer les noms même s'ils sont formulés différemment

        6. Filtres d’exclusion :
            - Supprime les noms contenant certains termes juridiques ou administratifs non pertinents
            - Ignore les noms trop longs (> longueur_max)
            - Ignore les noms trop courts sauf s’ils ressemblent à un NOM majuscule valide (UPWORD)

        7. Détection et élimination des doublons :
            - Évite d'ajouter plusieurs fois des noms très similaires ou inclus les uns dans les autres

        8. Filtrage final :
            - Exclut les noms contenant "greffier" (pas une personne cible)

        Retour :
            - Une liste de noms nettoyés et pertinents pour traitement ultérieur
        """

    titres_regex = r"\b(madame|monsieur|mme|mr)\b[\s\-]*"

    # Termes à ignorer
    termes_ignores = ["la personne", "personne", "Par ordonnance", "de la", "dans les",
                      "feu M", "feu", "feue", "désigné Maître", "présente publication",
                      "de sexe masculin", "de sexe féminin", "de sexe feminin",  # <-- corrigé
                      "sexe masculin", "sexe féminin", "sexe feminin",
                      "masculin", "féminin", "feminin", "comptabilité", "intention frauduleuse", "avoir détourné",
                      "avoir detourne", "contrevenu", "dispositions", "partie appelante", "représentée", "appelante",
                      "l'etat belge spf finances", "l etat belge spf finances", "L'ETAT BELGE SPF FINANCES",
                      "etat belge", "spf finances"]


    def invert_if_comma(s: str) -> str:
        if "," in s:
            left, right = [p.strip() for p in s.split(",", 1)]
            # inverser seulement si la partie avant la virgule ressemble à un NOM en majuscules
            if re.fullmatch(r"[A-ZÉÈÀÂÊÎÔÛÇÄËÏÖÜŸ'’\-]+", left):
                return f"{right} {left}"
        return s


    def extraire_nom_depuis_phrase(nom):
        patterns = [
            r"pour la succession de\s+(.*)",
            r"en possession de la succession de\s+(.*)",
            r"succession\s+(?:en\s+d[ée]sh[ée]rence|vacante)?\s+de\s+(.*)",
            r"en qualité de curateur à la succession vacante de\s+(.*)",
            r"la succession vacante de\s+(.*)",
            r"le\s+juge\s+de\s+paix\s+du\s+canton\s+de\s+visé\s+a\s+désigné\s+(?:à\s+)?(.*)",


        ]
        for pattern in patterns:
            match = re.search(pattern, nom, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return nom.strip()


    def nettoyer_et_normaliser(nom):
        # 👉 extraire un éventuel nom après "succession de ..."
        extrait = extraire_nom_depuis_phrase(nom)
        if extrait != nom:  # éviter récursion infinie
            nom = extrait

        # 🆕 suppression de blocs répétés 2× (OCR → "Tasnier Anne Marie Tasnier Anne Marie")
        tokens = nom.split()
        half = len(tokens) // 2
        if half > 2 and tokens[:half] == tokens[half:]:
            nom = " ".join(tokens[:half])

        # --- Nettoyage neutre ---
        for rx in STRIP_PHRASES_REGEX:
            nom = rx.sub(" ", nom)

        # suppression préfixes "né ..." etc.
        nom = re.sub(rf"^\s*{PREFIXES}\s+", "", nom, flags=re.IGNORECASE)

        # suppression titres
        nom = re.sub(titres_regex, '', nom, flags=re.IGNORECASE)

        # suppression chiffres et formats "12/3", "45-A"...
        nom = re.sub(r"\d+", "", nom)
        nom = re.sub(r"\s*[\/\-]\s*\d+\w*", "", nom)

        # coupe le contexte après le nom
        nom = re.split(CONTEXT_CUT, nom, 1, flags=re.IGNORECASE)[0]

        # normalisation ponctuation/espace
        nom = nom.replace(";", " ").replace("|", " ").replace(":", " ")
        nom = re.sub(r"\s+", " ", nom).strip(" ,;-")

        # inversion éventuelle "NOM, Prénom"
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

    def _dedupe_tokens(nom: str) -> str:
        tokens = nom.split()
        seen = []
        for t in tokens:
            if not seen or seen[-1].lower() != t.lower():
                seen.append(t)
        return " ".join(seen)

    def _dedupe_blocks(n: str) -> str:
        tokens = n.split()
        half = len(tokens) // 2
        if half > 2 and tokens[:half] == tokens[half:]:
            return " ".join(tokens[:half])
        return n

    for nom in noms:

        nom_nettoye, norm = nettoyer_et_normaliser(nom)
        # 👉 étape anti-répétition OCR
        nom_nettoye_dedup = _dedupe_tokens(nom_nettoye)
        nom_nettoye_dedup = _dedupe_blocks(nom_nettoye_dedup)
        nom_nettoye = nom_nettoye_dedup

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
            if norm == exist:  # égalité stricte seulement
                dup = True
                break
            # si tu veux vraiment supprimer la plus courte :
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


def extract_name_before_birth(texte_html, keyword, doc_id):

    dyn_log = setup_dynamic_logger(name="extraction_names", keyword=keyword)

    soup = BeautifulSoup(texte_html, 'html.parser')
    full_text = soup.get_text(separator=" ").strip()

    nom_list = LoggedList(full_text, doc_id, logger=dyn_log)

    absence = RX_ABSENCE.search(full_text)
    if absence:
        nom_list.append(absence.group(1).strip(), regex_name="RX_ABSENCE", m=absence)

    for interdit_a in RX_INTERDIT_A.finditer(full_text):
        nom = (interdit_a.group('nom') or interdit_a.group('nom2')).strip()
        prenoms = (interdit_a.group('prenoms') or interdit_a.group('prenoms2')).strip()
        nom_list.append(f"{nom}, {prenoms}", regex_name="RX_INTERDIT_A", m=interdit_a)

    for lenomme in RX_LE_NOMME_NP.finditer(full_text):
        nom_list.append(f"{lenomme.group('nom').strip()}, {lenomme.group('prenoms').strip()}", regex_name="RX_LE_NOMME_NP", m=lenomme)

    for rxnrnp in RX_NR_NP.finditer(full_text):
        nom_list.append(f"{rxnrnp.group('nom').strip()}, {rxnrnp.group('prenoms').strip()}")

    for rxnpne in RX_NP_NE.finditer(full_text):
        nom_list.append(f"{rxnpne.group('nom').strip()}, {rxnpne.group('prenoms').strip()}")

    for succession_any in RX_SV_ANY.finditer(full_text):
        nom_list.append(succession_any.group(1).strip(), regex_name="RX_SV_ANY", m=succession_any)

    for rxsvnomcomplet in RX_SV_NOM_COMPLET_VIRG.finditer(full_text):
        nom_list.append(f"{rxsvnomcomplet.group(1).strip()}, {rxsvnomcomplet.group(2).strip()}", regex_name="RX_SV_NOM_COMPLET_VIRG", m=rxsvnomcomplet)

    for rxsrvsimple in RX_SRV_SIMPLE.finditer(full_text):
        nom_list.append(rxsrvsimple.group(1).strip(), regex_name="RX_SRV_SIMPLE", m=rxsrvsimple)

    for rxsrvnp in RX_SRV_NP.finditer(full_text):
        nom_list.append(f"{rxsrvnp.group(1).strip()}, {rxsrvnp.group(2).strip()}", regex_name="RX_SRV_NP", m=rxsrvnp)

    # (déjà précompilés ailleurs) — personnes visées par la succession / curateur
    for rxsvpn in RX_SV_PN.finditer(full_text):
        nom_list.append(f"{rxsvpn.group('nom').strip()}, {rxsvpn.group('prenoms').strip()}", regex_name="RX_SV_PN", m=rxsvpn)

    for rxsvnp in RX_SV_NP.finditer(full_text):
        nom_list.append(f"{rxsvnp.group('nom').strip()}, {rxsvnp.group('prenoms').strip()}", regex_name="RX_SV_NP", m=rxsvnp)

    for rxcurateursvpn in RX_CURATEUR_SV_PN.finditer(full_text):
        nom_list.append(f"{rxcurateursvpn.group('nom').strip()}, {rxcurateursvpn.group('prenoms').strip()}", regex_name="RX_CURATEUR_SV_PN", m=rxcurateursvpn)

    for rxcurateursvnp in RX_CURATEUR_SV_NP.finditer(full_text):
        nom_list.append(f"{rxcurateursvnp.group('nom').strip()}, {rxcurateursvnp.group('prenoms').strip()}", regex_name="RX_CURATEUR_SV_NP", m=rxcurateursvnp)

    # variantes supplémentaires
    for rxsvnomvirgprenoms in RX_SV_NOM_VIRG_PRENOMS.finditer(full_text):
        nom_list.append(f"{rxsvnomvirgprenoms.group(1).strip()}, {rxsvnomvirgprenoms.group(2).strip()}", regex_name="RX_SV_NOM_VIRG_PRENOMS", m=rxsvnomvirgprenoms)

    for rxsvfeupaire in RX_SV_FEU_PAIRE.finditer(full_text):
        nom_list.append(f"{rxsvfeupaire.group(1).strip()}, {rxsvfeupaire.group(2).strip()}", regex_name="RX_SV_FEU_PAIRE", m=rxsvfeupaire)

    # 🔹 Ajout spécifique pour : "mesures de protection à l’égard de la personne et des biens de l’intéressé Prénom Nom, né à ..."
    for rxprotectioninteressene in RX_PROTECTION_INTERESSE_NE.finditer(full_text):
        nom_list.append(f"{rxprotectioninteressene.group('nom').strip()}, {rxprotectioninteressene.group('prenoms').strip()}", regex_name="RX_PROTECTION_INTERESSE_NE", m= rxprotectioninteressene)

    for rxsvfeuvariantes in RX_SV_FEU_VARIANTES.finditer(full_text):
        nom_list.append(rxsvfeuvariantes.group(1).strip(), regex_name="RX_SV_FEU_VARIANTES", m=rxsvfeuvariantes)

    for rxsrvmrn in RX_SRV_M_RN.finditer(full_text):
        nom_list.append(rxsrvmrn.group(1).strip(), regex_name="RX_SRV_M_RN", m=rxsrvmrn)

    for rxadminsvspec in RX_ADMIN_SV_SPEC.finditer(full_text):
        parts = rxadminsvspec.group(1).strip().split()
        if len(parts) >= 2:
            nom_list.append(f"{parts[-1]}, {' '.join(parts[:-1])}", regex_name="RX_ADMIN_SV_SPEC", m=rxadminsvspec)

    for rxsvpartvac in RX_SV_PART_VAC.finditer(full_text):
        parts = rxsvpartvac.group(1).strip().split()
        if len(parts) >= 2:
            nom_list.append(f"{parts[-1]}, {' '.join(parts[:-1])}", regex_name="RX_SV_PART_VAC", m=rxsvpartvac)

    for rxadminsvvacalt in RX_ADMIN_SV_VAC_ALT.finditer(full_text):
        parts = rxadminsvvacalt.group(1).strip().split()
        if len(parts) >= 2:
            nom_list.append(f"{parts[-1]}, {' '.join(parts[:-1])}", regex_name="RX_ADMIN_SV_VAC_ALT", m=rxadminsvvacalt)

    for rxsvnele in RX_SV_NE_LE.finditer(full_text):
        nom_list.append(rxsvnele.group(1).strip(), regex_name="RX_SV_NE_LE", m=rxsvnele)

    for rxsvdesherencesimple in RX_SV_DESHERENCE_SIMPLE.finditer(full_text):
        nom_list.append(rxsvdesherencesimple.group(1).strip(), regex_name="RX_SV_DESHERENCE_SIMPLE", m=rxsvdesherencesimple)

    for rxadminprovsuccde in RX_ADMIN_PROV_SUCC_DE.finditer(full_text):
        nom_list.append(rxadminprovsuccde.group(1).strip(), regex_name="RX_ADMIN_PROV_SUCC_DE", m=rxadminprovsuccde)

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

    # ==============================
    #      NOMS AVEC RN
    # ==============================
    # Détecte les déclarations du type :
    # "déclare NOM, Prénom(s) (RN ...)"
    # Extrait le nom et les prénoms de la personne déclarée, suivis d’un identifiant RN (RN, RRN, NRN, etc.)
    # Exemple :
    #     "déclare DUPONT, Jean Pierre (RRN 12.12.2000-123.45)"
    RX_DECL_NP_RRN = re.compile(rf"""
        \bdéclare\b\s+
        (?P<nom>{NOM_BLOCK})\s*,\s*(?P<prenoms>{PRENOMS_BLK})
        \s*\(\s*{RN_TOKEN_ANY}.*?\)
    """, re.IGNORECASE | re.VERBOSE)
    # 📌 Variante de déclaration incluant une civilité :
    # "déclare Monsieur/Madame NOM, Prénom(s) (RN ...)"
    # ➤ Extrait le nom et les prénoms de la personne, précédés d'une civilité,
    #     et suivis d’un identifiant RN (RN, RRN, NRN, etc.)
    # Exemple :
    #     "déclare Madame DUPONT, Jeanne Louise (RRN 01.01.1980-123.45)"
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
        r"(.{1,50})\b(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )

    for m in match_ne_a_context:
        contexte = m.group(1).strip()
        print(f"voila le pution de salopard: {m.group(1)}")
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
    for m in RX_PRENOM_NOM_NE_A.finditer(full_text):
        nom_list.append(f"{m.group('nom').strip()}, {m.group('prenoms').strip()}")
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


# _______________________________________________________________________________________________________________________
#                          NETTOYAGE DES NOMS + EMPECHER DES NOMS EN DOUBLE
# _______________________________________________________________________________________________________________________
    noms_nettoyes = nettoyer_noms_avances(nom_list)
    # 1) Calcule la liste locale des nouveaux noms (pas besoin d’être global)
    nouveaux_noms = []
    for nom in noms_nettoyes:
        key = (doc_id, nom.strip().lower())
        if key not in seen_nomspersonnes:
            nouveaux_noms.append(nom)

    # 2) Si rien de nouveau, on sort vite
    if not nouveaux_noms:
        return group_names_for_meili(noms_nettoyes)



    # 4) Mise à jour de l’état externe (persistant en mémoire)
    seen_nomspersonnes.update(
        (doc_id, n.strip().lower()) for n in nouveaux_noms
    )
    if isinstance(nom_list, LoggedList):
        nom_list.flush()
    return group_names_for_meili(noms_nettoyes)