import csv, re
from pathlib import Path

est_path = Path("C:/Users/32471/ScrapperCJCE/Datas/establishment.csv")
addr_path = Path("C:/Users/32471/ScrapperCJCE/Datas/address.csv")

addr_path = Path("chemin/vers/address.csv")

def clean_num(num):
    """Supprime tous les caractères non numériques"""
    return re.sub(r"\D", "", num or "")

# --- lecture des deux CSV ---
est_map = {}  # BCE -> {etab}
with est_path.open(encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        bce = clean_num(row.get("EnterpriseNumber"))
        etab = clean_num(row.get("EstablishmentNumber"))
        if bce and etab:
            est_map.setdefault(bce, set()).add(etab)

addr_map = {}  # entité (BCE ou établissement) -> adresses
with addr_path.open(encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        ent = clean_num(row.get("EntityNumber"))
        if not ent:
            continue
        adr = ", ".join(filter(None, [
            row.get("StreetFR") or row.get("StreetNL"),
            row.get("HouseNumber"),
            row.get("Box"),
            (row.get("Zipcode") or ""),
            (row.get("MunicipalityFR") or row.get("MunicipalityNL")),
        ]))
        addr_map.setdefault(ent, set()).add(adr.strip(", "))

# --- vérification ---
count_linked = 0
count_missing = 0

for bce, etabs in est_map.items():
    for etab in etabs:
        if etab in addr_map:
            count_linked += 1
        else:
            count_missing += 1
            print(f"[❌ Manque adresse pour établissement {etab}] lié à {bce}")

print(f"✅ {count_linked} établissements ont une adresse trouvée")
print(f"⚠️ {count_missing} établissements sans correspondance")
