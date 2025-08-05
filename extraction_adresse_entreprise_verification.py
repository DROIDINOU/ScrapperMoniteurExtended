import re
import csv
import ast
from meilisearch import Client

INDEX_NAME = "moniteur_documents"

ADRESSE_PREFIXES_FILTRE = r"(RUE|R\.|AVENUE|COURS|COUR|AV\.|CHEE|CHAUSS[ÉE]E|ROUTE|RTE|PLACE|PL\.?|BOULEVARD|BD|CHEMIN|CH\.?|GALERIE|IMPASSE|SQUARE|ALL[ÉE]E|CLOS|VOIE|RY|PASSAGE|QUAI|PARC|Z\.I\.?|ZONE|SITE|PROMENADE|FAUBOURG|FBG|QUARTIER|CITE|HAMEAU|LOTISSEMENT|RESIDENCE)"

log_file = "logs/extraction.log"
corrections_csv = "corrections_faites.csv"
LONGUEUR_MIN = 60

client = Client(MEILI_URL, MEILI_MASTER_KEY)
index = client.index(INDEX_NAME)

with open(corrections_csv, "a", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    if csvfile.tell() == 0:
        writer.writerow(["id", "ancienne_adresse", "nouvelle_adresse"])

    with open(log_file, encoding="utf-8") as f:
        for line in f:
            if "Résultat :" in line:
                id_match = re.search(r"ID=([0-9a-f]{64})", line)
                if not id_match:
                    continue
                doc_id = id_match.group(1)

                resultat_str = line.split("Résultat :", 1)[1].strip()

                try:
                    resultat = ast.literal_eval(resultat_str)  # lecture de structures Python
                except Exception:
                    print(f"⚠️ Ligne illisible pour ID={doc_id} : {resultat_str}")
                    continue

                # Si c'est juste une chaîne ou une liste brute
                if isinstance(resultat, (list, tuple)):
                    adresse = resultat[0] if resultat else None
                    alerte = False
                elif isinstance(resultat, dict):
                    adresse = resultat.get("adresse")
                    alerte = resultat.get("alerte", False)
                else:
                    adresse = str(resultat)
                    alerte = False

                if not adresse:
                    continue

                if len(adresse) >= LONGUEUR_MIN and not re.match(rf"^{ADRESSE_PREFIXES_FILTRE}\b", adresse, flags=re.IGNORECASE):
                    print(f"\n📌 ID trouvé : {doc_id}")
                    print(f"Ancienne adresse (log) : {adresse}")

                    index.update_documents([{"id": doc_id, "adresse": None}])
                    print("⛔ Adresse supprimée.")

                    nouvelle_adresse = input("Nouvelle adresse : ").strip()
                    index.update_documents([{"id": doc_id, "adresse": nouvelle_adresse}])
                    print("✅ Nouvelle adresse insérée.")

                    writer.writerow([doc_id, adresse, nouvelle_adresse])
                    csvfile.flush()
