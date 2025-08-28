from bs4 import BeautifulSoup
import re
from Constante.mesconstantes import ADRESSES_INSTITUTIONS, ADRESSES_INSTITUTIONS_SET
from Utilitaire.outils.MesOutils import nettoyer_adresse, couper_fin_adresse

def extract_address(texte_html):
    adresse_list = []

    soup = BeautifulSoup(texte_html, 'html.parser')
    texte = soup.get_text(separator=' ')
    texte = re.sub(r'\s+', ' ', texte).strip()
    # — Cas 1 : "1325 Chaumont-Gistoux, Bas-Bonlez, résidence les Lilas 57"
    RX_CHAUMONT_RESIDENCE = re.compile(r"""
        \b(?P<cp>\d{4})\s+(?P<ville>Chaumont\-Gistoux)\s*,\s*
        (?P<localite>[A-ZÀ-ÿ'’\- ]+?)\s*,\s*
        r[ée]sidence\s+(?P<resname>[^,;]+?)\s+(?P<num>\d{1,4})
    """, re.IGNORECASE | re.VERBOSE)

    # — Cas 2 : "Les Avrils , 4520 Wanze, Rue des Loups 19"
    RX_LOCALITE_CP_VILLE_VOIE = re.compile(r"""
        (?P<localite>[A-ZÀ-ÿ'’\- ]+?)\s*,\s*
        (?P<cp>\d{4})\s+(?P<ville>[A-ZÀ-ÿ'’\- ]+?)\s*,\s*
        (?P<type>rue|avenue|chauss[ée]e|place|boulevard|impasse|chemin|square|all[ée]e|clos|voie)\s+
        (?P<nomvoie>[A-ZÀ-ÿa-z'’\- ]+?)\s+(?P<num>\d{1,4})
    """, re.IGNORECASE | re.VERBOSE)
    # ⚡ Fast-path ciblé sur le texte complet (pas de segmentation)
    for m in RX_CHAUMONT_RESIDENCE.finditer(texte):
        adr = f"résidence {m.group('resname').strip()} {m.group('num')}, à {m.group('cp')} {m.group('ville')}, {m.group('localite').strip()}"
        adresse_list.append(adr)

    for m in RX_LOCALITE_CP_VILLE_VOIE.finditer(texte):
        adr = f"{m.group('type').capitalize()} {m.group('nomvoie').strip()} {m.group('num')}, à {m.group('cp')} {m.group('ville')}, {m.group('localite').strip()}"
        adresse_list.append(adr)
    # 🧠 DEBUG ciblé : n'affiche que si "résidence" est présent
    if "résidence" in texte.lower():
        print("\n[DEBUG 1111111111111111111111111111111111111111111111111111111111111111111111111111111111] Texte contenant 'résidence' détecté :")
        print(texte)

    # Match : "domicilié à 3078 Kortenberg, Kiewistraat 30"
    m_cp_first = re.search(
        r"""domicili[ée]?\s+à\s+
            (\d{4})\s+                   # CP
            ([A-ZÀ-ÿ\-]+),\s+            # Ville
            ([A-ZÀ-ÿa-z'\- ]+?)\s+       # Rue
            (\d{1,4})                    # Numéro
            (?:\s*,?\s*(?:bo[îi]te|bte|bt|bus)\s*
                ([A-Z0-9/\.\-]+))?       # Boîte : lettres, chiffres, slash etc.
        """,
        texte,
        flags=re.IGNORECASE | re.VERBOSE
    )

    if m_cp_first:
        cp = m_cp_first.group(1)
        ville = m_cp_first.group(2)
        rue = m_cp_first.group(3).strip()
        num = m_cp_first.group(4)
        boite = m_cp_first.group(5)

        full = f"{rue} {num}"
        if boite:
            full += f", boîte {boite}"
        full += f", à {cp} {ville}"
        adresse_list.append(full)

    m_cp_apres = re.search(
        r"""(?:
            avenue|rue|boulevard|chauss[ée]e|place|impasse|all[ée]e|clos|voie|chemin|square
        )\s+
        ([A-ZÀ-ÿa-z'\- ]+?)\s+        # nom rue
        (\d{1,4})                     # numéro
        (?:\s*,?\s*(?:bo[îi]te|bte|bt|bus)\s*([A-Z0-9/\.\-]+))?    # boîte
        \s*,?\s*
        (\d{4})\s+                    # CP
        ([A-ZÀ-ÿ\- ]{2,})             # ville
        """,
        texte,
        flags=re.IGNORECASE | re.VERBOSE
    )
    if m_cp_apres:
        rue = m_cp_apres.group(1).strip()
        num = m_cp_apres.group(2)
        boite = m_cp_apres.group(3)
        cp = m_cp_apres.group(4)
        ville = m_cp_apres.group(5)

        full = f"{rue} {num}"
        if boite:
            full += f", boîte {boite}"
        full += f", à {cp} {ville}"
        adresse_list.append(full)

    m_simple = re.search(
        r"domicili[ée]?,?\s+(?P<adr>[A-ZÀ-ÿa-z\s'\-]+?\s+\d{1,4})(?:\s*,)?\s+à\s+(\d{4})\s+([A-ZÀ-ÿ\-]+)",
        texte,
        flags=re.IGNORECASE
    )

    if m_simple:
        rue = m_simple.group("adr").strip()
        cp = m_simple.group(2)
        ville = m_simple.group(3)
        full = f"{rue}, à {cp} {ville}".strip()
        adresse_list.append(full)

    # Match : "domicilié rue Charles Vanderstrappen 24, 1030 Schaerbeek"
    m_rue_first = re.search(
        r"domicili[ée]?\s+(?:rue|avenue|chauss[ée]e|place|boulevard|impasse|chemin|square|all[ée]e|clos|voie)\s+"
        r"([A-ZÀ-ÿa-z'\- ]+?)\s+(\d{1,4})\s*,\s*(\d{4})\s+([A-ZÀ-ÿ\-]+)",
        texte,
        flags=re.IGNORECASE
    )

    if m_rue_first:
        rue = m_rue_first.group(1).strip()
        num = m_rue_first.group(2)
        cp = m_rue_first.group(3)
        ville = m_rue_first.group(4)
        full = f"{rue} {num}, à {cp} {ville}"
        adresse_list.append(full)


    # ────────────────────────────────────────────────────────────────
    # 🔍 Définition des composants de motifs d'adresses postales
    # Objectif : construire des regex réutilisables pour capturer
    # les adresses (rue, numéro, boîte, etc.) dans des textes libres.
    # Utilisé dans la détection automatique d'adresses belges ou similaires.
    # ────────────────────────────────────────────────────────────────

    # Préfixes de voie en français et néerlandais (abréviations incluses),
    # utilisés pour reconnaître les débuts d’adresses (ex: "rue", "bd", "laan", etc.)
    ADRESSE_PREFIXES_FILTRE = (
        r"(?:rue|r\.|avenue|cours|cour|av\.|chee|chauss[ée]e|route|rte|place|pl\.?|"
        r"boulevard|bd|chemin|ch\.?|galerie|impasse|square|all[ée]e|clos|voie|ry|passage|"
        r"quai|parc|z\.i\.?|zone|site|promenade|faubourg|fbg|quartier|cite|hameau|"
        r"lotissement|residence)"
    )

    # Variante étendue incluant les types de voie + leurs formes néerlandaises
    VOIE_ALL = (
        rf"(?:{ADRESSE_PREFIXES_FILTRE}"
        r"|rue|route|grand[-\s]?route|grand[-\s]?place|avenue|chaussée|place|boulevard|impasse|"
        r"chemin|quai|straat|laan|steenweg|plein|weg|pad)"
    )

    # Représente les numéros dans une adresse :
    # - 1 à 4 chiffres
    # - éventuellement suivis d'une lettre (ex: 21B), sauf si c’est "B." (comme dans "B.C.E.")
    # - optionnellement suivi d’un séparateur ("/") et d’un identifiant (ex: "/bte14")
    NUM_TOKEN = r"\d{1,4}(?:[A-Za-z](?!\s*\.))?(?:/[A-ZÀ-ÿ0-9\-]+)?"

    # Un mot possible dans le nom d’une rue : lettres, chiffres, apostrophes, tirets, etc.
    # Inclut aussi des petits mots fréquents dans les noms (de, du, des, la, etc.)
    MOT_NOM_VOIE = r"(?:[A-ZÀ-ÿa-z0-9'’()/\.-]+|de|du|des|la|le|l’|l'|d’|d')"

    # Suite de mots pour un nom complet de voie (ex: "du Général de Gaulle")
    # Limité à 10 mots maximum
    MOTS_NOM_VOIE = rf"{MOT_NOM_VOIE}(?:\s+{MOT_NOM_VOIE}){{0,9}}"

    # Suffixe d’annexe (ex: "bte 16", "boîte 3") autorisé après le numéro
    ANNEXE_SUFFIX = (
        r"(?:\s*,?\s*(?:/|bus|bo[îi]te|bte\.?|bt\.?|b(?!\s*\.))"
        r"\s*(?=[A-ZÀ-ÿ0-9\-/.]*\d)[A-ZÀ-ÿ0-9\-/.]+)"
    )

    # Expression de coupure : permet de dire "on arrête l’extraction ici"
    # Si après l’adresse on tombe sur une virgule, un point-virgule, ou un mot-clé comme "B.C.E."
    END_CUT = r"(?=(?:\s*[;,]|(?:\s*B\.?C\.?E\.?)|(?:\s*TVA)|$))"

    # PROX : sert à limiter des recherches contextuelles à ~80 caractères autour
    # utile pour matcher "domicilié à ..." dans une phrase plus large
    PROX = r"[^\.]{0,80}?"

    # Motifs "core" réutilisables (tes définitions)
    core_1 = rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{MOTS_NOM_VOIE}\s*{VOIE_ALL}\s*{NUM_TOKEN})" + END_CUT
    core_2 = rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{MOTS_NOM_VOIE}{VOIE_ALL}\s*{NUM_TOKEN})" + END_CUT
    core_3 = rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE})" + END_CUT
    core_4 = rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}(?:{ANNEXE_SUFFIX})?)" + END_CUT
    core_5_any_before = (
        rf"(?:{MOTS_NOM_VOIE},\s*)?"
        rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?)" + END_CUT
    )

    core_5b_no_voie = (
        rf"(?:{MOTS_NOM_VOIE},\s*)?"
        rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?)" + END_CUT
    )
    core_6_nl = rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*(?:straat|laan|steenweg|plein|weg|pad)\s+{MOTS_NOM_VOIE})"
    core_7_fr = rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE})"
    core_8_rue_simple = (
        rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s+rue\s+{MOTS_NOM_VOIE}(?:\s+{NUM_TOKEN})?)"
        r"(?=[\.,])"
    )
    core_9_autres_voies = (
        rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s+(?:avenue|chaussée|place)\s+{MOTS_NOM_VOIE}(?:\s+{NUM_TOKEN})?)"
        r"(?=[\.,])"
    )
    core_10_fran_large = (
        rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s+{VOIE_ALL}\s+{MOTS_NOM_VOIE}(?:\s+{NUM_TOKEN})?)"
        r"(?=[\.,])"
    )
    core_11_any_before_generic = (
                                     rf"(?:{MOTS_NOM_VOIE},\s*)?"
                                     rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{VOIE_ALL}\s*{MOTS_NOM_VOIE})"
                                 ) + END_CUT
    core_12_wild = r"(.+?)(?=, [A-Z]{2}|, décédé|$)"
    # ex : "… est établi avenue Besme 107, 1190 Bruxelles"
    core_13_est_etabli = (
        rf"est\s+établi\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"  # avenue Besme 107
        rf"\s*,\s*\d{{4}}\s+{MOTS_NOM_VOIE}"  # , 1190 Bruxelles
        r")"
    )
    core_14_wild_end = r"(.{1,300}?)(?=\.|\bdécéd[ée]|$)"
    core_15_siege_social = (
        rf"(?:ayant\s+son\s+)?si[eè]ge\s+social\s*,\s*("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}\s*,\s*\d{{4}}\s+{MOTS_NOM_VOIE}"
        r")"
    )
    # ex: "… est établi, allée du Vieux Chêne 23, à 4480 Engis"
    core_14_est_etabli_cp_apres = (
        rf"est\s+établi[e]?\s*,?\s*("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"  # allée du Vieux Chêne 23
        rf"\s*,?\s*à\s*\d{{4}}\s+{MOTS_NOM_VOIE}"  # , à 4480 Engis
        r")"
    )

    core_16_siege_etabli_cp_then_street = (
        rf"(?:dont\s+le\s+)?si[eè]ge(?:\s+social)?\s+est\s+établi[e]?\s*à\s*("
        rf"\d{{4}}\s+{MOTS_NOM_VOIE}\s*,\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?"
        r")" + END_CUT
    )

    core_17_etabli_cp_then_street = (
        rf"est\s+établi[e]?\s*à\s*("
        rf"\d{{4}}\s+{MOTS_NOM_VOIE}\s*,\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?"
        r")" + END_CUT
    )

    core_18_siege_etabli_cp_then_street_stop = (
        rf"(?:dont\s+le\s+)?si[eè]ge(?:\s+social)?\s+est\s+établi[e]?\s*à\s*("
        rf"\d{{4}}\s+{MOTS_NOM_VOIE}\s*,\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?"
        r")(?=(?:\s*[;,]|(?:\s*B\.?C\.?E\.?)|(?:\s*TVA)|\s+et\b|$))"
    )

    core_19_ayant_siege_cp_then_street_stop = (
        rf"ayant\s+son\s+si[eè]ge(?:\s+social)?\s+à\s*("
        rf"\d{{4}}\s+{MOTS_NOM_VOIE}\s*,\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?"
        r")(?=(?:\s*[;,]|(?:\s*B\.?C\.?E\.?)|(?:\s*TVA)|\s+et\b|$))"
    )

    # ex : "… dont le siège social est situé à 4987 STOUMONT, Hasoumont 71, boîte 16, B.C.E. …"
    core_20_siege_situe_cp_then_no_voie_stop = (
        rf"(?:dont\s+le\s+)?si[eè]ge(?:\s+social)?\s+est\s+situ[ée]?\s*à\s*("
        rf"\d{{4}}\s+{MOTS_NOM_VOIE}\s*,\s*{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?"
        r")(?=(?:\s*[;,]|(?:\s*B\.?C\.?E\.?)|(?:\s*TVA)|\s+et\b|$))"
    )

    # Variante si jamais il y a un mot-clé de voie (rue/avenue/…)
    core_21_siege_situe_cp_then_voie_stop = (
        rf"(?:dont\s+le\s+)?si[eè]ge(?:\s+social)?\s+est\s+situ[ée]?\s*à\s*("
        rf"\d{{4}}\s+{MOTS_NOM_VOIE}\s*,\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?"
        r")(?=(?:\s*[;,]|(?:\s*B\.?C\.?E\.?)|(?:\s*TVA)|\s+et\b|$))"
    )
    core_22_residence = (
            rf"(\d{{4}}\s+{MOTS_NOM_VOIE},\s*{MOTS_NOM_VOIE},\s*résidence\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN})"
            + END_CUT
    )


    patterns_base = [

        r"domicili[ée](?:\(e\))?\s+à\s+" + core_1,
        r"domicili[ée]?\s+à\s+" + core_2,
        r"domicili[ée]?\s+à\s+" + core_3,
        r"domicili[ée]?\s+à\s+" + core_4,
        core_5_any_before,
        core_5b_no_voie,
        core_13_est_etabli,
        core_15_siege_social,
        core_14_est_etabli_cp_apres,
        core_16_siege_etabli_cp_then_street,  # << ajouté
        core_17_etabli_cp_then_street,        # << ajouté
        core_18_siege_etabli_cp_then_street_stop,  # << nouveau
        core_19_ayant_siege_cp_then_street_stop,    # << nouveau
        core_20_siege_situe_cp_then_no_voie_stop,   # << ajout
        core_21_siege_situe_cp_then_voie_stop,      # << ajout
        r"domicili[ée](?:\(e\))?\s+à\s+" + core_22_residence,

        r"domicili[ée]" + PROX + r"\bà\s+" + core_6_nl,
        r"domicili[ée]" + PROX + r"\bà\s+" + core_7_fr,
        r"domicili[ée]" + PROX + r"\bà\s+" + core_8_rue_simple,
        r"domicili[ée]" + PROX + r"\bà\s+" + core_9_autres_voies,
        r"domicili[ée]" + PROX + core_11_any_before_generic,

        r"domicili[ée](?:\(e\))?\s+à\s+" + core_12_wild,
        r"domiciliée\s+à\s+(.+?),?\s+est\s+décédée",
        r"domicili[ée](?:\(e\))?\s+à\s+" + core_14_wild_end,

        # ex: Domicile : rue de Jambes 319, à 5100 DAVE.
        rf"domicile\s*:\s*({VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}(?:{ANNEXE_SUFFIX})?\s*,\s*à\s+\d{{4}}\s+{MOTS_NOM_VOIE})",

        # ex: Domicile : 5100 DAVE, rue de Jambes 319
        rf"domicile\s*:\s*(\d{{4}}\s+{MOTS_NOM_VOIE}\s*,\s*{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}(?:{ANNEXE_SUFFIX})?)",

        # Ex: "Domicile : Grand-Route(VER) 245/0011, à 4537 Verlaine"
        rf"domicile\s*:\s*("
        rf"{VOIE_ALL}(?:\s+|(?=\())"
        rf"{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        r"\s*(?:,\s*)?à\s*\d{4}\s+" + MOTS_NOM_VOIE +
        r")",

        # ex: Domicile : rue de Jambes 319 - 5100 DAVE
        rf"domicile\s*:\s*({VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}(?:{ANNEXE_SUFFIX})?\s*,\s*à\s+\d{{4}}\s+{MOTS_NOM_VOIE})",

        # ex: Domicile : 5100 DAVE - rue de Jambes 319
        rf"domicile\s*:\s*({VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}(?:{ANNEXE_SUFFIX})?\s*(?:,|[-–])\s*\d{{4}}\s+{MOTS_NOM_VOIE})",

        # ── Variantes "de son vivant" — MISE À NIVEAU VERS NUM_TOKEN + ANNEXE_SUFFIX ──
        rf"domicili[ée](?:\(e\))?\s+de\s+son\s+vivant\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?)"
        r"\s*,\s*à\s*\d{4}\s+" + MOTS_NOM_VOIE,

        rf"domicili[ée](?:\(e\))?\s+de\s+son\s+vivant\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?)"
        r"\s*(?:,\s*)?à\s*\d{4}\s+" + MOTS_NOM_VOIE + r"(?=(?:\s*(?:,| et\b)|$))",
        # “de son vivant domiciliée …, à CP VILLE”
        rf"de\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?"
        r")\s*,?\s*à\s*\d{4}\s+" + MOTS_NOM_VOIE,

        # “de son vivant domiciliée AVENUE … NUM”
        rf"de\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?)",

        # Cas inversé : "… à VILLE, rue XXX 12"
        rf"domicili[ée](?:\(e\))?\s+de\s+son\s+vivant\s+à\s+{MOTS_NOM_VOIE},?\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?)",
        rf"domicili[ée]?,?\s+({MOTS_NOM_VOIE}\s+{NUM_TOKEN}\s*,?\s*à\s*\d{{4}}\s+{MOTS_NOM_VOIE})",

        # Virgule après "vivant"
        rf"domicili[ée](?:\(e\))?\s+de\s+son\s+vivant\s*,\s*("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?)"
        r"\s*,?\s*à\s*\d{4}\s+" + MOTS_NOM_VOIE,

        rf"domicili[ée]?,?\s+({MOTS_NOM_VOIE}\s+{NUM_TOKEN}\s*,?\s+à\s+\d{{4}}\s+{MOTS_NOM_VOIE})",


        # Variantes "en son vivant"
        rf"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?)"
        r"\s*(?:,\s*)?à\s*\d{4}\s+" + MOTS_NOM_VOIE,

        rf"(?:en|de)\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?)"
        r"\s*,\s*\d{4}\s+" + MOTS_NOM_VOIE,

        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_1,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_2,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_3,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_4,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_6_nl,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_7_fr,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_10_fran_large,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_11_any_before_generic,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_12_wild,
        r"en\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+à\s+" + core_14_wild_end,

        r"en\s+son\s+vivant\s+à\s+" + core_6_nl,
        r"en\s+son\s+vivant\s+à\s+" + core_7_fr,
        r"en\s+son\s+vivant\s+à\s+" + core_8_rue_simple,
        r"en\s+son\s+vivant\s+à\s+" + core_9_autres_voies,
        r"en\s+son\s+vivant\s+à\s+" + core_10_fran_large,
        r"en\s+son\s+vivant\s+à\s+" + core_11_any_before_generic,

        rf"(?:en|de)\s+son\s+vivant\s+domicili[ée](?:\(e\))?\s+("
        rf"{VOIE_ALL}\s+{MOTS_NOM_VOIE}\s+{NUM_TOKEN}"
        rf"(?:{ANNEXE_SUFFIX})?)"
        r"\s*(?:,\s*)?à\s*\d{4}\s+" + MOTS_NOM_VOIE,

        rf"(?:en|de)\s+son\s+vivant\s+({VOIE_ALL}\s+{MOTS_NOM_VOIE})"
        r"\s*(?:,\s*)?à\s*\d{4}\s+" + MOTS_NOM_VOIE,
    ]

    # ─────────────────────────────────────────────────────────────
    # Génération AUTOMATIQUE de variantes pour TOUS tes patterns
    #   - ajout (avant) "((en|de) son vivant, )?"
    #   - ajout (après 'domicilié(e)') " (en|de) son vivant, ?"
    #   - "à" rendu optionnel: \s+à\s+  ->  \s*(?:à\s+)?
    # On part STRICTEMENT de tes patterns_base.
    # ─────────────────────────────────────────────────────────────
    def with_optional_a(p: str) -> str:
        return re.sub(r"\\s\+à\\s\+", r"\\s*(?:à\\s+)?", p)

    def vivant_before_domicilie(p: str) -> str:
        # insère "(en|de) son vivant, ?" juste avant la 1ère occurrence de "domicilié(e)"
        return re.sub(
            r"(?i)(?=\bdomicili\[ée\]\(\?:\\\(e\\\)\)\?\b|\bdomicili\[ée\]\b)",
            r"(?:en|de)\\s+son\\s+vivant\\s*,?\\s*",
            p,
            count=1
        )

    def vivant_after_domicilie(p: str) -> str:
        # ajoute "(en|de) son vivant, ?" juste APRÈS "domicilié(e)" + espaces
        return re.sub(
            r"(?i)(domicili\[ée\](?:\\\(e\\\))?\\s+)",
            r"\\1(?:en|de)\\s+son\\s+vivant\\s*,?\\s+",
            p,
            count=1
        )

    patterns_expanded = set()
    for p in patterns_base:
        patterns_expanded.add(p)
        p_opt_a = with_optional_a(p)
        patterns_expanded.add(p_opt_a)

        if "domicili" in p.lower():
            patterns_expanded.add(vivant_before_domicilie(p))
            patterns_expanded.add(vivant_after_domicilie(p))

            patterns_expanded.add(vivant_before_domicilie(p_opt_a))
            patterns_expanded.add(vivant_after_domicilie(p_opt_a))

    patterns = list(patterns_expanded)

    # Optimisation : on segmente le texte en phrases ciblées
    phrases = re.split(r'(?<=[\.\n])', texte)
    phrases = [p.strip() for p in phrases if any(kw in p.lower() for kw in ['domicili', 'domicile', 'vivant', ' à ',
                                                                            'etabli', 'établi', 'etablie', 'établie',
                                                                            'établi,', 'siège social', 'siege social',
                                                                            'siège', 'siege'])]
    if not phrases:
        print("aucune phrase retenue => on ajoute tout le texte")
        phrases = [texte]

    for phrase in phrases:

        for pattern in patterns:
            try:
                matches = re.findall(pattern, phrase, flags=re.IGNORECASE)
            except re.error:
                # si une variante générée est invalide (rare), on la saute
                continue
            for m in matches:
                # Chaque match peut être un str (un seul groupe) ou un tuple (plusieurs)
                if isinstance(m, tuple):
                    m = next((x for x in m if isinstance(x, str) and x.strip()), " ".join(m))
                m = re.sub(r"\s+(et(\s+décédé[e]?)?)$", "", str(m).strip(), flags=re.IGNORECASE)
                m = nettoyer_adresse(m)
                m = couper_fin_adresse(m)
                # 🔧 Supprime le point final éventuel (ex: "283 bte 21." → "283 bte 21")
                m = m.rstrip(".")

                adresse_list.append(m)
    # Après avoir rempli adresse_list
    adresse_list = [a for a in adresse_list if 2 < len(a.split()) < 16]
    return list(set(adresse_list))
