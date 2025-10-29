import json
from tqdm import tqdm
from BaseDeDonnees.connexion_postgre import get_postgre_connection


def insert_documents_moniteur(documents):
    """
    Insère une liste de documents dans la table PostgreSQL moniteur_documents_postgre
    en convertissant correctement les champs JSONB.
    """
    conn = get_postgre_connection()
    cur = conn.cursor()

    print(f"[📦] Insertion de {len(documents)} documents dans PostgreSQL (JSONB)…")

    def to_jsonb_safe(value):
        """Convertit les valeurs en JSONB valide pour PostgreSQL."""
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, str):
            # Vérifie si c’est déjà du JSON valide
            try:
                json.loads(value)
                return value
            except json.JSONDecodeError:
                return json.dumps(value, ensure_ascii=False)
        return json.dumps(str(value), ensure_ascii=False)

    for doc in tqdm(documents, desc="Insertion PostgreSQL"):
        text = (doc.get("text") or "").strip()

        cur.execute("""
            INSERT INTO moniteur_documents_postgre (
                date_doc, lang, text, url, keyword, tva, titre, num_nat,
                extra_keyword, nom, adresse, date_jugement,
                nom_trib_entreprise, date_deces, administrateur,
                denoms_by_bce, adresses_by_bce, denoms_by_ejustice
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s::jsonb, %s, %s::jsonb,
                %s::jsonb, %s::jsonb, %s::jsonb,
                %s, %s::jsonb, %s::jsonb, %s::jsonb,
                %s::jsonb, %s::jsonb, %s::jsonb
            )
            ON CONFLICT (url) DO NOTHING;
        """, (
            doc.get("date_doc"),
            doc.get("lang"),
            text,
            doc.get("url"),
            doc.get("keyword"),
            to_jsonb_safe(doc.get("TVA")),
            doc.get("title"),
            to_jsonb_safe(doc.get("num_nat")),
            to_jsonb_safe(doc.get("extra_keyword")),
            to_jsonb_safe(doc.get("nom")),
            to_jsonb_safe(doc.get("adresse")),
            doc.get("date_jugement"),
            to_jsonb_safe(doc.get("nom_trib_entreprise")),
            to_jsonb_safe(doc.get("date_deces")),
            to_jsonb_safe(doc.get("administrateur")),
            to_jsonb_safe(doc.get("denoms_by_bce")),
            to_jsonb_safe(doc.get("adresses_by_bce")),
            to_jsonb_safe(doc.get("denoms_by_ejustice")),
        ))

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Insertion terminée avec champs JSONB.")
