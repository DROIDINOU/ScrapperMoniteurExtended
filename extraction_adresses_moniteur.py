from bs4 import BeautifulSoup
import re

def extract_address(texte_html):

    soup = BeautifulSoup(texte_html, 'html.parser')
    texte = soup.get_text(separator=' ')
    texte = re.sub(r'\s+', ' ', texte).strip()


    adresse_list = []

    patterns = [

        # 1️⃣ Très structuré : "domicilié(e) à 1234 Ville, rue/avenue/... 12"
        # Utilise la ponctuation, type de voie et un numéro pour plus de fiabilité
        r"domicili[ée](?:\(e\))?\s+à\s+(\d{4}\s+[A-ZÀ-ÿa-z\-'’\s]+,\s*[A-ZÀ-ÿa-z\-'\s]*" +
        r"(?:straat|laan|rue|avenue|chaussée|place|boulevard|impasse|chemin|plein|steenweg|weg|pad)\s*\d{1,4})",

        # 2️⃣ Idem, mais sans "(e)" optionnel et plus permissif sur les accents/espaces
        r"domicili[ée]?\s+à\s+(\d{4}\s+[A-ZÀ-ÿa-z\-'’\s]+,\s*[A-ZÀ-ÿa-z\-'\s]+" +
        r"(?:straat|laan|rue|avenue|chaussée|place|boulevard|impasse|chemin|plein|steenweg|weg|pad)\s*\d{1,4})",

        # 3️⃣ Idem mais accepte des parenthèses dans ville/rue : ex. "(Que)" ou "(TOU)"
        r"domicili[ée]?\s+à\s+(\d{4}\s+[A-ZÀ-ÿa-z\-'’\s()]+,\s*" +
        r"(?:rue|avenue|chaussée|place|boulevard|impasse|chemin|" +
        r"straat|laan|steenweg|plein|weg|pad)\s+[A-ZÀ-ÿa-z0-9\-'’()\s]+)",

        # 4️⃣ Cas où la ville a plusieurs mots (ex. "Rhode-Saint-Genèse") + rue complète
        r"domicili[ée]?\s+à\s+(\d{4}\s+[A-ZÀ-ÿa-z\-'()]+(?:\s+[A-ZÀ-ÿa-z\-'()]+)*,\s*" +
        r"(?:rue|avenue|chaussée|place|boulevard|impasse|chemin|" +
        r"straat|laan|steenweg|plein|weg|pad)\s+[A-ZÀ-ÿa-z0-9\-'’()\s]+)",

        # 5️⃣ Cas sans "domicilié à", avec types de voies flamands (straat, laan...)
        r"(?:domicili[ée]?\s+)?à\s+(\d{4}\s+[A-ZÀ-ÿa-z\-'\s()]+,\s*" +
        r"(?:straat|laan|steenweg|plein|weg|pad)\s+[A-ZÀ-ÿa-z0-9\-'’()\s]+)",

        # 6️⃣ Idem, mais pour voies francophones (rue, avenue...)
        r"(?:domicili[ée]?\s+)?à\s+(\d{4}\s+[A-ZÀ-ÿa-z\-'\s()]+,\s*" +
        r"(?:rue|avenue|chaussée|place|boulevard|impasse|chemin)\s+[A-ZÀ-ÿa-z0-9\-'’()\s]+)",

        # 7️⃣ Format simple : "à 1234 Ville, rue Nom 12" (spécifique à "rue")
        r"\bà\s+(\d{4}\s+[A-ZÀ-ÿa-z\-']+(?:\s+[A-ZÀ-ÿa-z\-']+)*,\s+" +
        r"rue\s+[A-ZÀ-ÿa-z\-'\s]+(?:\s+\d+)?)(?=[\.,])",

        # 8️⃣ Idem avec "avenue", "chaussée", "place"
        r"\bà\s+(\d{4}\s+[A-ZÀ-ÿa-z\-']+(?:\s+[A-ZÀ-ÿa-z\-']+)*,\s+" +
        r"(?:avenue|chaussée|place)\s+[A-ZÀ-ÿa-z\-'\s]+(?:\s+\d+)?)(?=[\.,])",

        # 9️⃣ Encore un format "domicilié à" avec voies francophones — très souple
        r"domicili[ée]?\s+à\s+(\d{4}\s+[A-ZÀ-ÿa-z\-']+(?:\s+[A-ZÀ-ÿa-z\-']+)*,\s+" +
        r"(?:rue|avenue|chaussée|place)\s+[A-ZÀ-ÿa-z\-'\s]+(?:\s+\d+)?)(?=[\.,])",

        # 🔟 Moins fiable : capture tout après "domicilié à", jusqu'à une virgule, "décédé", ou fin
        r"domicili[ée](?:\(e\))?\s+à\s+(.+?)(?=, [A-Z]{2}|, décédé|$)",

        # 1️⃣1️⃣ Variante souple spécifique à "est décédée"
        r'domiciliée à (.+?),? est décédée',

        # 1️⃣2️⃣ Dernier recours : capture large sur 300 caractères, si rien d'autre n'a matché
        r"domicili[ée](?:\(e\))?\s+à\s+(.{1,300}?)(?=\.|\bdécéd[ée]|$)"
    ]

    for idx, pattern in enumerate(patterns, 1):
        matches = re.findall(pattern, texte)
        for m in matches:
            adresse_list.append(m.strip())
    # 🔄 Suppression des doublons
    adresse_list = list(set(adresse_list))
    return adresse_list
