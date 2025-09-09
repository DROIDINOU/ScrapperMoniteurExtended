import re

RX_DOMICILE_AVEC_PRECISION = re.compile(
    r"""
    domicili[ée]?\s+à\s+                         # "domicilié à"
    (?P<cp>\d{4})\s+                             # Code postal
    (?P<ville>[A-ZÀ-ÿ'\- ]+)\s*,\s*              # Ville
    (?P<precision>[^,]+?)\s*,\s*                 # Résidence, home, etc.
    (?P<type>rue|avenue|chauss[ée]e|place|boulevard|impasse|
        chemin|square|all[ée]e|clos|voie)\s+
    (?P<nomvoie>[A-ZÀ-ÿa-z'\- ]+)\s+
    (?P<num>\d{1,4})                             # Numéro
    """,
    flags=re.IGNORECASE | re.VERBOSE
)



texte = """Monsieur Tommy BINARD, né à Charleroi le 30 juillet 2007, domicilié à 4020 Liège, La Maison Heureuse, Rue Winston-Churchill 353, personne à protéger, a été placé sous un régime de représentation."""

m = RX_DOMICILE_AVEC_PRECISION.search(texte)
if m:
    adresse = f"{m.group('type').capitalize()} {m.group('nomvoie').strip()} {m.group('num')}, à {m.group('cp')} {m.group('ville')}"
    print("✅ Adresse trouvée :", adresse)
else:
    print("❌ Aucun match")