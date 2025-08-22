import re

BASE_URL = "https://www.ejustice.just.fgov.be/cgi/"

# faire une verif pour succession egalité date naissance et deces
# INDEX_NAME=mon_document_pft_11082025 contient succession et successions
# CONSTANTE VILLES UTILISEE DANS FONCTION extract_date_after_rendu_par
VILLE_TRIBUNAUX = [
    "Bruxelles", "Charleroi", "Mons", "Namur", "Liège", "Huy",
    "Tournai", "Neufchâteau", "Marche-en-Famenne", "Arlon", "Dinant", "Eupen", "Nivelles", "Verviers"
]

escaped_villes = [re.escape(v) for v in VILLE_TRIBUNAUX]
VILLES = "|".join(escaped_villes)

JOURMAP = {
        'premier': 1, 'un': 1, 'deux': 2, 'trois': 3, 'quatre': 4, 'cinq': 5, 'six': 6,
        'sept': 7, 'huit': 8, 'neuf': 9, 'dix': 10, 'onze': 11, 'douze': 12, 'treize': 13,
        'quatorze': 14, 'quinze': 15, 'seize': 16, 'dix-sept': 17, 'dix-huit': 18,
        'dix-neuf': 19, 'vingt': 20, 'vingt-et-un': 21, 'vingt-deux': 22, 'vingt-trois': 23,
        'vingt-quatre': 24, 'vingt-cinq': 25, 'vingt-six': 26, 'vingt-sept': 27,
        'vingt-huit': 28, 'vingt-neuf': 29, 'trente': 30, 'trente-et-un': 31
    }

MOISMAP = {
        'janvier': '01', 'février': '02', 'mars': '03', 'avril': '04',
        'mai': '05', 'juin': '06', 'juillet': '07', 'août': '08',
        'septembre': '09', 'octobre': '10', 'novembre': '11', 'décembre': '12'
    }


ANNEMAP = {
        'deux mille vingt': '2020',
        'deux mille vingt et un': '2021',
        'deux mille vingt deux': '2022',
        'deux mille vingt trois': '2023',
        'deux mille vingt quatre': '2024',
        'deux mille vingt cinq': '2025',
        'deux mille vingt six': '2026'
    }

# CONSTANTE UTILISEE PAR FONCTION : convert_french_text_date_to_numeric

JOURMAPBIS = {
        'premier': 1, 'un': 1, 'deux': 2, 'trois': 3, 'quatre': 4, 'cinq': 5, 'six': 6,
        'sept': 7, 'huit': 8, 'neuf': 9, 'dix': 10, 'onze': 11, 'douze': 12,
        'treize': 13, 'quatorze': 14, 'quinze': 15, 'seize': 16, 'dix-sept': 17,
        'dix-huit': 18, 'dix-neuf': 19, 'vingt': 20, 'vingt-et-un': 21, 'vingt-deux': 22,
        'vingt-trois': 23, 'vingt-quatre': 24, 'vingt-cinq': 25, 'vingt-six': 26,
        'vingt-sept': 27, 'vingt-huit': 28, 'vingt-neuf': 29, 'trente': 30, 'trente-et-un': 31
    }

MOISMAPBIS = {
        'janvier': 'janvier', 'février': 'février', 'mars': 'mars', 'avril': 'avril',
        'mai': 'mai', 'juin': 'juin', 'juillet': 'juillet', 'août': 'août',
        'septembre': 'septembre', 'octobre': 'octobre', 'novembre': 'novembre', 'décembre': 'décembre'
    }

ANNEEMAPBIS = {
        'deux mil vingt-trois': '2023', 'deux mille vingt-trois': '2023',
        'deux mil vingt-quatre': '2024', 'deux mille vingt-quatre': '2024',
        'deux mil vingt-cinq': '2025', 'deux mille vingt-cinq': '2025'
        # Ajouter plus de combinaisons si besoin
    }

# UTILISE??
EXCLUDEDSOURCES = {
    "Agence Fédérale pour la Sécurité de la Chaîne Alimentaire",
    "Agence Fédérale des Médicaments et des Produits de Santé",
    "Assemblée de la Commission Communautaire Française de la Région ...",
    "Autorité Flamande",
    "Banque Nationale de Belgique",
    "Chambre",
    "Collège de la Commission Communautaire Française",
    "Commission Bancaire et Financière",
    "Commission Communautaire Commune de Bruxelles-Capitale",
    "Commission Communautaire Française de la Région de Bruxelles-Capitale",
    "Commission de la Protection de la vie privee",
    "Communauté Française",
    "Conseil d'Etat",
    "Conseil Supérieur de la Justice",
    "Corps Interfédéral de l'Inspection des Finances",
    "Cour d'Arbitrage",
    "Cour des Comptes",
    "Cour Constitutionnelle",
    "Institut National d'Assurance Maladie-Invalidite",
    "Ministère de l'Emploi et du Travail",
    "Ministère de l'Intérieur",
    "Ministère de la Communauté Flamande",
    "Ministère de la Communauté Française",
    "Ministère de la Communauté Germanophone",
    "Ministère de la Défense Nationale",
    "Ministère de la Défense",
    "Ministère de la Fonction Publique",
    "Ministère de la Justice",
    "Ministère de la Région de Bruxelles-Capitale",
    "Ministere de la Region de Bruxelles-Capitale",
    "Ministere de la Region de Bruxelles-capitale",
    "Ministere de La Region de Bruxelles-Capitale",
    "Ministère de la Région Wallonne",
    "Ministère des Affaires Economiques",
    "Ministère des Affaires Etrangères",
    "Ministère des Affaires Sociales",
    "Ministère des Classes Moyennes et de l'Agriculture",
    "Ministère des Communications et de l'Infrastructure",
    "Ministère des Finances",
    "Ministère Wallon de l'Equipement et des Transports",
    "Pouvoir Judiciaire",
    "Selor - Bureau de Selection de l'Administration Fédérale",
    "Sénat",
    "Service Public de Wallonie",
    "Service Public Fédéral Affaires Etrangères, ...",
    "Service Public Fédéral Budget et controle de la gestion",
    "Service Public Fédéral Chancellerie du Premier Ministre",
    "Service Public Fédéral Chancellerie et Services Généraux",
    "Service Public Fédéral de Programmation Développement Durable",
    "Service Public Fédéral de Programmation Gestion des Actifs",
    "Service Public Fédéral de Programmation Intégration sociale",
    "Service Public Fédéral de Programmation Politique Scientifique",
    "Service Public Fédéral de Programmation Protection des Consommateurs",
    "Service Public Fédéral de Programmation Telecommunications",
    "Service Public Fédéral Economie, P.M.E., Classes Moyennes et Enérgie",
    "Service Public Fédéral Emploi, Travail et Concertation Sociale",
    "Service Public Fédéral Finances",
    "Service Public Fédéral Interieur",
    "Service Public Fédéral Justice",
    "Service Public Fédéral Mobilite et Transports",
    "Service Public Fédéral Personnel et Organisation",
    "Service Public Fédéral Sante Publique, Sécurité de la chaîne ...",
    "Service Public Fédéral Securite Sociale",
    "Service Public Fédéral Stratégie et Appui",
    "Service Public Fédéral Technologie de l'Information et de la Communication",
    "Services du Premier Ministre",
    "Services Fédéraux des Affaires Scientifiques, Techniques et Culturelles"
}

# UTILISE PAR detect_societe_title

SOCIETESABRV = {"SA", "SRL", "SE", "SPRL", "SIIC", "SC", "SNC", "SCS", "COMMV", "SCRL", "SAS", "ASBL", "SCA"}
SOCIETESFORMELLES = [
        "société anonyme", "société à responsabilité limitée", "société coopérative",
        "société européenne", "société en commandite", "société civile"
    ]

# 1) MOISMAP élargi (formes correctes, abréviations, fautes/OCR)
MOISMAPTEST = {
    # janvier
    "janvier": "01", "janv": "01", "jan": "01", "janiver": "01",
    # février
    "février": "02", "fevrier": "02", "fév": "02", "fev": "02", "fevr": "02",
    "fevrer": "02", "fevrie": "02", "feurier": "02", "feverier": "02", "fevier": "02",
    # mars
    "mars": "03", "mar": "03", "marsr": "03",
    # avril
    "avril": "04", "avr": "04", "avri": "04",
    # mai
    "mai": "05",
    # juin
    "juin": "06", "juiin": "06",
    # juillet
    "juillet": "07", "juil": "07", "juill": "07", "juiller": "07",
    # août / aout (et OCR)
    "août": "08", "aout": "08", "aoüt": "08", "aoút": "08", "a0ut": "08", "aou": "08", "aouts": "08",
    # septembre
    "septembre": "09", "sept": "09", "setpembre": "09", "septemre": "09", "septemb": "09",
    # octobre
    "octobre": "10", "oct": "10", "ocotbre": "10", "octobr": "10", "octber": "10",
    # novembre
    "novembre": "11", "nov": "11", "novemre": "11", "novenbre": "11",
    # décembre
    "décembre": "12", "decembre": "12", "dec": "12", "decebre": "12",
    "decemre": "12", "decrmbre": "12"
}

MOIS_PATTERN = "|".join(map(re.escape, sorted(MOISMAP.keys(), key=len, reverse=True)))

_MOISMAP_NORM = {
    # janvier
    "janvier": "01", "janv": "01", "jan": "01", "janiver": "01",
    # fevrier
    "fevrier": "02", "fevr": "02", "fev": "02", "fevrer": "02", "fevrie": "02",
    "feurier": "02", "feverier": "02", "fevier": "02",
    # mars
    "mars": "03", "mar": "03", "marsr": "03",
    # avril
    "avril": "04", "avr": "04", "avri": "04",
    # mai
    "mai": "05",
    # juin
    "juin": "06", "juiin": "06",
    # juillet
    "juillet": "07", "juil": "07", "juill": "07", "juiller": "07",
    # aout (toutes variantes)
    "aout": "08", "aou": "08", "aouts": "08",
    # septembre
    "septembre": "09", "sept": "09", "setpembre": "09", "septemre": "09", "septemb": "09",
    # octobre
    "octobre": "10", "oct": "10", "ocotbre": "10", "octobr": "10", "octber": "10",
    # novembre
    "novembre": "11", "nov": "11", "novenbre": "11", "novemre": "11",
    # decembre
    "decembre": "12", "dec": "12", "decebre": "12", "decemre": "12", "decrmbre": "12",
}
