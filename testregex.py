import csv, unicodedata

def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')

input_file = 'STREETS_ALL.csv'  # fichier téléchargé depuis Geoportail
output_csv = 'villages_wallonie.csv'

with open(input_file, newline='', encoding='utf-8') as fin, \
     open(output_csv, 'w', newline='', encoding='utf-8') as fout:
    reader = csv.DictReader(fin)
    writer = csv.writer(fout)
    writer.writerow(['Commune', 'Section', 'Village'])

    for row in reader:
        # Exemple : champ TYPE = "section"
        if row.get('TYPE', '').lower() not in ('section', 'hameau', 'village'):
            continue

        commune = strip_accents(row.get('COMMUNE', '')).upper().strip()
        section = strip_accents(row.get('SECTION', '')).upper().strip()
        village = strip_accents(row.get('NOM', '')).upper().strip()

        writer.writerow([commune, section, village])

print(f"✅ Généré : {output_csv}")