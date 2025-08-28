import csv
from Utilitaire.outils.MesOutils import chemin_csv

def clean_denom_csv(input_path, output_path):
    with open(input_path, newline="", encoding="utf-8-sig") as infile, \
         open(output_path, "w", newline="", encoding="utf-8-sig") as outfile:

        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
        writer.writeheader()

        for row in reader:
            bce = row["EntityNumber"].replace(".", "")
            if not bce.startswith("0200"):  # 🔥 supprime les entités publiques
                writer.writerow(row)

# Exécution
clean_denom_csv(chemin_csv("denomination.csv"), "denomination_sans_publiques.csv")
