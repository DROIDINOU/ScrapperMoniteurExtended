import re
import unicodedata


def nettoyer_noms_avances(noms, longueur_max=80):
    """
    Nettoie une liste de noms :
    - Extrait les noms à partir d'expressions du type "pour la succession de NOM"
    - Supprime les titres et doublons
    - Normalise pour éviter les répétitions ou versions tronquées
    """

    titres_regex = r"\b(madame|monsieur|mme|mr)\b[\s\-]*"
    deja_vus = set()
    noms_filtres = []

    def extraire_nom_depuis_phrase(nom):
        # Patterns possibles
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

def nettoyer_noms_avances(noms, longueur_max=80):
    """
    Nettoie une liste de noms :
    - Extrait les noms à partir d'expressions du type "pour la succession de NOM"
    - Supprime les titres et doublons
    - Normalise pour éviter les répétitions ou versions tronquées
    - Supprime les entrées contenant des termes comme "la personne"
    """

    titres_regex = r"\b(madame|monsieur|mme|mr)\b[\s\-]*"
    deja_vus = set()
    noms_filtres = []

    # Termes à ignorer
    termes_ignores = ["la personne", "personne", "Par ordonnance", "de la"]

    def extraire_nom_depuis_phrase(nom):
        # Patterns possibles
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
        nom = extraire_nom_depuis_phrase(nom)

        # Supprimer les titres
        nom = re.sub(titres_regex, '', nom, flags=re.IGNORECASE)

        # Inversion "NOM, Prénom"
        if ',' in nom:
            parts = [p.strip() for p in nom.split(',')]
            if len(parts) == 2:
                nom = f"{parts[1]} {parts[0]}"

        # Supprimer accents
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
        # Ignorer les noms contenant des termes comme "la personne"
        if any(terme in nom.lower() for terme in termes_ignores):
            continue

        if len(nom) > longueur_max:
            continue

        nom_nettoye, norm = nettoyer_et_normaliser(nom)

        if len(nom_nettoye.split()) < 2:
            continue

        if any(norm == exist or norm in exist or exist in norm for exist in noms_normalises):
            continue

        noms_nettoyes.append(nom_nettoye)
        noms_normalises.append(norm)

    return noms_nettoyes

def extract_name_before_birth(texte_html):
    from bs4 import BeautifulSoup
    import re

    soup = BeautifulSoup(texte_html, 'html.parser')
    full_text = soup.get_text(separator=" ").strip()
    nom_list = []


    # ______________________________________________________________________________________________________

    #                       *******************  PERSONNES PHYSIQUES *****************************

    # _____________________________________________________________________________________________________

    # -----------------
    #     SUCCESSIONS
    # -----------------

    match_sv = re.findall(
        r"succession\s+(?:vacante|en\s+d[ée]sh[ée]rence)\s+de\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)",
        full_text,
        re.IGNORECASE
    )
    for m in match_sv:
        nom_list.append(m.strip())
    match_srv = re.findall(
        r"succession\s+réputée\s+vacante\s+de\s+(?:Madame|Monsieur)?\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)",
        full_text,
        re.IGNORECASE
    )
    for m in match_srv:
        nom_list.append(m.strip())

    match_sv_nom_prenoms = re.findall(
        r"succession\s+réputée\s+vacante\s+de\s+(?:M(?:onsieur)?|Madame)?\.?\s*([A-ZÉÈÊÀÂ\-']+),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\- ]{2,})",
        full_text,
        re.IGNORECASE
    )
    for nom, prenoms in match_sv_nom_prenoms:
        nom_complet = f"{nom.strip()}, {prenoms.strip()}"
        nom_list.append(nom_complet)

    match_curateur_sv = re.findall(
        r"curateur\s+à\s+succession\s+vacante\s+de\s+(?:M(?:onsieur)?\s+)?([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)",
        full_text,
        re.IGNORECASE
    )
    for nom in match_curateur_sv:
        nom_list.append(nom.strip())
    # Cas : "succession en déshérence de NOM, Prénom(s)"
    match_nom_virgule_prenom = re.findall(
        r"succession\s+(?:vacante|en\s+d[ée]sh[ée]rence)?\s+de\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-\s]+)",
        full_text,
        re.IGNORECASE
    )
    for nom, prenoms in match_nom_virgule_prenom:
        nom_complet = f"{nom.strip()}, {prenoms.strip()}"
        nom_list.append(nom_complet)

    match_feu_succession = re.findall(
        r"(?:succession\s+de\s+feu|à\s+la\s+succession\s+de\s+feu).{0,30}?(?:M(?:onsieur)?|Madame)?\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)[,\s]+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)",
        full_text,
        re.IGNORECASE
    )
    for nom, prenom in match_feu_succession:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)

    # ✅ Cas étendu : "succession [déclarée] vacante de feu [M./Madame] Prénom NOM"
    match_feu_decl_variantes = re.findall(
        r"(?:succession\s+(?:déclarée\s+)?vacante\s+de\s+feu|succession\s+de\s+feu|à\s+la\s+succession\s+de\s+feu)\s*:?\s*(?:M(?:onsieur)?|Madame)?\.?\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+){1,4})",
        full_text,
        re.IGNORECASE
    )
    for nom_complet in match_feu_decl_variantes:
        nom_list.append(nom_complet.strip())

    # Cas : curateur à la succession réputée vacante de M. <NOM COMPLET>
    match_succession_reputee_vacante = re.findall(
        r"succession\s+réputée\s+vacante\s+de\s+M\.?\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\- ]+?)(?=\s*\(RN)",
        full_text,
        flags=re.IGNORECASE
    )

    for nom_complet in match_succession_reputee_vacante:
        nom_list.append(nom_complet.strip())

    match_admin_succession_specifique = re.findall(
        r"administrateur\s+provisoire\s+à\s+succession,?\s+de\s+(?:Monsieur|Madame|M\.|Mme)?\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+){1,4})",
        full_text,
        re.IGNORECASE
    )
    for full_name in match_admin_succession_specifique:
        parts = full_name.strip().split()
        if len(parts) >= 2:
            nom = parts[-1]
            prenoms = " ".join(parts[:-1])
            nom_complet = f"{nom}, {prenoms}"
            nom_list.append(nom_complet)

    match_succession_part_vacante = re.findall(
        r"succession\s+partiellement\s+vacante\s+de\s+(?:Monsieur|Madame|M\.|Mme)?\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+){1,4})",
        full_text,
        re.IGNORECASE
    )
    for full_name in match_succession_part_vacante:
        parts = full_name.strip().split()
        if len(parts) >= 2:
            nom = parts[-1]
            prenoms = " ".join(parts[:-1])
            nom_complet = f"{nom}, {prenoms}"
            nom_list.append(nom_complet)

    match_admin_succession_vacante_alt = re.findall(
        r"administrateur\s+provisoire\s+à\s+succession\s+vacante,?\s+de\s+(?:Monsieur|Madame|M\.|Mme)?\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+){1,4})",
        full_text,
        re.IGNORECASE
    )
    for full_name in match_admin_succession_vacante_alt:
        parts = full_name.strip().split()
        if len(parts) >= 2:
            nom = parts[-1]
            prenoms = " ".join(parts[:-1])
            nom_complet = f"{nom}, {prenoms}"
            nom_list.append(nom_complet)

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





    # 🔹 0. Cas "succession de NOM, né(e) le"
    match0 = re.findall(
        r"succession?\s+de\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s\-']+?),\s*(né\(e\)?|né|née)\s+le",
        full_text,
        re.IGNORECASE
    )
    for m in match0:
        nom_list.append(m[0].strip())

    # 🔹 0.bis : Cas "succession en déshérence de NOM"
    match_sd = re.findall(
        r"succession?\s+(?:en\s+d[ée]sh[ée]rence\s+)?de\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s\-']+?),",
        full_text,
        re.IGNORECASE
    )
    for m in match_sd:
        nom_list.append(m.strip())

    # 🔹 0.ter : Cas "Madame/Monsieur NOM, Prénom, né(e) à ..."
    match_mp = re.findall(
        r"(?:Madame|Monsieur)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s\-']+?),\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö\s\-']+?),\s+(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )
    for nom_famille, prenoms, _ in match_mp:
        nom_complet = f"{nom_famille.strip()}, {prenoms.strip()}"
        nom_list.append(nom_complet)

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
    match_admin_succession = re.findall(
        r"administrateur\s+provisoire\s+à\s+la\s+succession\s+de\s*:?\s*(?:M(?:onsieur)?\.?\s+)?([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+){1,5})",
        full_text,
        re.IGNORECASE
    )
    for nom_complet in match_admin_succession:
        nom_list.append(nom_complet.strip())

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
        if (match_special_semicolon):
            print("2222222222222222222222222222222222222222222222222222222222222222222222222222")
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

    match_succession_rv_nomprenom = re.findall(
        r"succession\s+réputée\s+vacante\s+de\s+(?:M(?:onsieur)?\.?|Madame)?\s*([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)",
        full_text,
        re.IGNORECASE
    )
    for prenom, nom in match_succession_rv_nomprenom:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
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
        r"([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)[^()]{0,70}\(N[N|R]\s*\d{2}[.\-/]\d{2}[.\-/]\d{2}[-\s.]\d{3}[.\-/]\d{2}",
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

    seen = set()

    match_sv_monsieur = re.findall(
        r"succession\s+(?:vacante|en\s+d[ée]sh[ée]rence)?\s+de\s+Monsieur\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+(?:\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)*)\s+([A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s+[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+)",
        full_text,
        re.IGNORECASE
    )
    for prenom, nom in match_sv_monsieur:
        nom_complet = f"{nom.strip()}, {prenom.strip()}"
        nom_list.append(nom_complet)
    # Expression régulière pour capturer le nom complet avant "né à"
    match_noms_complets = re.findall(
        r"((?:[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+\s+){1,6}[A-ZÉÈÊÀÂa-zéèêàâçëïüö'\-]+),?\s+(né|née|né\(e\))\s+à",
        full_text,
        re.IGNORECASE
    )
    for nom_complet, _ in match_noms_complets:
        nom_list.append(nom_complet.strip())

    return nettoyer_noms_avances(nom_list)