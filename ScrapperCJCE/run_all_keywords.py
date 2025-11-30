import subprocess
import sys
from datetime import date
from pathlib import Path

# 🔧 Chemin vers ce dossier
BASE_DIR = Path(__file__).resolve().parent

# 🔧 Chemin vers ScrapperMoniteurAnnexes/
ANNEXES_DIR = BASE_DIR.parent / "ScrapperMoniteurAnnexes"
SCRAPPE_ANNEXES = ANNEXES_DIR / "scrappeAnnexes.py"

KEYWORDS = [
    "tribunal+de+premiere+instance",
    "tribunal+de+l",
    "cour+d",
    "justice+de+paix",
    "Liste+des+entites+enregistrees",
]

FROM = "2024-01-01"
TO = date.today().isoformat()


# ============================================================
# 🧹  IMPORTANT : nettoyer l'ancien CSV avant de lancer les scrapers
# ============================================================
csv_global = BASE_DIR / "exports" / "moniteur_enrichissement.csv"
if csv_global.exists():
    csv_global.unlink()
    print("🧹 CSV global supprimé (démarrage pipeline propre).")


print("\n Lancement du scraping principal…\n")
# ========== 1️⃣ SCRAPING PRINCIPAL ==========
for kw in KEYWORDS:
    print(f"️ Scraping : {kw}")
    result = subprocess.run(
        [sys.executable, "MainScrapper.py", kw, FROM, TO],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    print(result.stderr)

print("\n Tous les mots-clefs ont été scrapés !\n")

# ========== 2️⃣ ENRICHISSEMENT ANNEXES ==========

ANNEXES_SOURCES = [
    ("tribunal", "Tribunal de l’entreprise"),
    ("instance", "Tribunal de première instance"),
    ("cour", "Cours d’appel"),
    ("liste", "Liste des entités enregistrées"),
]

print("\n Lancement de l'enrichissement eJustice + BCE…\n")

for src, label in ANNEXES_SOURCES:
    print(f" Enrichissement pour : {label}")
    result = subprocess.run(
        [sys.executable, str(SCRAPPE_ANNEXES), "--source", src],
        capture_output=True,
        text=True,
        cwd=str(ANNEXES_DIR)  # IMPORTANT : exécuter dans le bon dossier
    )
    print(result.stdout)
    print(result.stderr)

print("\n🎯 Pipeline complet terminé : scraping + enrichissement !\n")
