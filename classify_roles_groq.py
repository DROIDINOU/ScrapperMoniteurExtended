#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, re, sys
from groq import Groq

# ============================================================
# 1) REMPLACE par ta vraie clé Groq (format "gsk_...")
GROQ_API_KEY = "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"
# 2) Mets TON TEXTE ici (copie-colle l’ordonnance/le jugement)
TEXT = """ Tribunal de première instance du Luxembourg, division Marche-en-Famenne Par jugement du 17/02/2025, le tribunal de la Famille du Luxembourg, division Marche-en-Famenne, confirme l'ordonnance dont appel sous les émendations suivantes : - Eric MULLER, RN : 57.07.27-121.24, né à Usumbura, Burundi le 25/07/1957, domicilié à 1200 WOLUWE-SAINT-LAMBERT, rue Abbé de l'Epée 24, est désigné en qualité d'administrateur des biens et de la personne de Marie-Thérèse Kinet; - Myriam MULLER, RN : 59.08.25-122.35, née à Usumbura, Burundi le 25/08/1959, domiciliée à 6900 HOLLOGNE, rue des Tombes 4, est désignée en qualité de personne de confiance. Les données à caractère personnel reprises dans cette publication ne peuvent être utilisées à d'autres fins que celle de porter la décision à la connaissance des personnes tierces. Marche-en-Famenne, le 3 mars 2025. La greffière, (signé) M. GROYNE.
"""
# 3) Mets la liste de NOMS candidats exactement comme tu veux les détecter
NAMES = [
    "Eric MULLER"
    "Eric MULLER,",
    " Myriam MULLER",
    "BEDDEGENOODTS, Rose",
]
# 4) Modèle Groq (70B = meilleure qualité ; 8B = plus léger)
MODEL_ID = "llama-3.3-70b-versatile"
# ============================================================

PROMPT_TEMPLATE = """\
Tu es un classificateur juridique.

TÂCHE: À partir du TEXTE CI-DESSOUS, attribue à chaque nom fourni dans NOM_CANDIDATS un ou plusieurs rôles parmi:
- "personne_protegee"
- "administrateur"
- "administrateur_sortant"
- "personne_de_confiance"
- "autre_ou_inconnu" (si aucun indice fiable)

RÈGLES IMPORTANTES:
1) Tu NE DOIS UTILISER QUE les noms présents dans NOM_CANDIDATS. N’invente jamais de noms.
2) Si un nom ne correspond à aucun indice clair dans le texte, classe-le en "autre_ou_inconnu".
3) Base-toi sur des indices lexicaux robustes, par ex.:
   - administrateur: "désigne ... en qualité d’administrateur", "administrateur de la personne et des biens de"
   - administrateur_sortant: "mission ... prend fin", "décharge l’administrateur", "met fin à la mission de"
   - personne_protegee: "administrateur de ...", "la personne protégée", "de Monsieur/Madame X (RN ...)" dans un contexte de protection
   - personne_de_confiance: "désigne en qualité de personne(s) de confiance"
4) Lorsque tu attribues un rôle, fournis une courte "evidence" (extrait exact du texte) justifiant l’attribution.
5) Réponds UNIQUEMENT en JSON, au format:

{{
  "personne_protegee": [{{"nom": "...", "evidence": "..."}}],
  "administrateur": [{{"nom": "...", "evidence": "..."}}],
  "administrateur_sortant": [{{"nom": "...", "evidence": "..."}}],
  "personne_de_confiance": [{{"nom": "...", "evidence": "..."}}],
  "autre_ou_inconnu": [{{"nom": "...", "evidence": "aucun indice clair"}}]
}}

NOM_CANDIDATS = {noms_candidats_json}
TEXTE = \"\"\"{texte_brut}\"\"\"
"""

ROLES = [
    "personne_protegee",
    "administrateur",
    "administrateur_sortant",
    "personne_de_confiance",
    "autre_ou_inconnu",
]

def build_prompt(texte: str, noms: list[str]) -> str:
    return PROMPT_TEMPLATE.format(
        noms_candidats_json=json.dumps(noms, ensure_ascii=False),
        texte_brut=texte,
    )

def parse_json_strict(s: str) -> dict:
    # Essaie du JSON direct, sinon récupère le 1er bloc {...}
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", s)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    raise ValueError("Réponse non-JSON ou illisible.")

def validate_result(res: dict, noms_input: set[str]) -> list[str]:
    issues = []
    for role in ROLES:
        if role not in res or not isinstance(res[role], list):
            issues.append(f"Clé manquante ou invalide: {role}")
            res.setdefault(role, [])
        for item in res[role]:
            if not isinstance(item, dict):
                issues.append(f"Élément non-objet dans {role}")
                continue
            nom = item.get("nom", "")
            ev  = item.get("evidence", "")
            if nom not in noms_input:
                issues.append(f"Nom hors liste dans {role}: {nom!r}")
            if not ev or not isinstance(ev, str):
                issues.append(f"Evidence manquante pour {nom!r} dans {role}")
    all_assigned = {d.get("nom","") for r in ROLES for d in res.get(r, [])}
    missing = noms_input - all_assigned
    for m in missing:
        issues.append(f"Nom non classé (devrait être en 'autre_ou_inconnu'): {m!r}")
    return issues

def pretty_print(res: dict):
    for role in ROLES:
        print(f"\n=== {role} ===")
        for item in res.get(role, []):
            print(f"- {item.get('nom')}: {item.get('evidence')}")

def main():
    # Sécurité minimale
    if not GROQ_API_KEY or GROQ_API_KEY == "gsk_TA_CLE_ICI":
        print("❌ Renseigne GROQ_API_KEY dans le script (remplace 'gsk_TA_CLE_ICI').", file=sys.stderr)
        sys.exit(1)
    if not TEXT.strip():
        print("❌ Le texte est vide : renseigne la variable TEXT.", file=sys.stderr)
        sys.exit(1)
    if not NAMES:
        print("❌ La liste NAMES est vide : renseigne au moins un nom.", file=sys.stderr)
        sys.exit(1)

    prompt = build_prompt(TEXT, NAMES)
    noms_set = set(NAMES)

    client = Groq(api_key=GROQ_API_KEY)

    completion = client.chat.completions.create(
        model=MODEL_ID,
        response_format={"type": "json_object"},  # force une réponse JSON propre
        messages=[
            {"role": "system", "content": "Tu es un assistant utile et strictement factuel."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_completion_tokens=1500,
    )

    raw = completion.choices[0].message.content
    try:
        res = parse_json_strict(raw)
    except Exception:
        print("❌ Réponse non-JSON:", raw, file=sys.stderr)
        raise

    # Validations et affichage
    issues = validate_result(res, noms_set)
    if issues:
        print("\n⚠️  Avertissements/validations:", file=sys.stderr)
        for it in issues:
            print("- " + it, file=sys.stderr)

    pretty_print(res)
    print("\n--- JSON final ---")
    print(json.dumps(res, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
