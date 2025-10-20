import json
from BaseDeDonnees.connexion_postgre import get_postgre_connection


def update_document_moniteur(doc):
    """
    Met à jour un document existant dans la table PostgreSQL moniteur_documents_postgre.
    S'il n'existe pas encore, il sera ignoré (à gérer par insert_documents_moniteur).
    """
    conn = get_postgre_connection()
    cur = conn.cursor()

    def to_jsonb_safe(value):
        """Prépare les valeurs pour les colonnes JSONB."""
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        try:
            json.loads(value)
            return value
        except Exception:
            return json.dumps(value, ensure_ascii=False)

    cur.execute("""
        UPDATE moniteur_documents_postgre
        SET
            date_doc = %s,
            lang = %s,
            text = %s,
            keyword = %s,
            tva = %s,
            titre = %s,
            num_nat = %s,
            extra_keyword = %s,
            nom = %s,
            date_naissance = %s,
            adresse = %s,
            date_jugement = %s,
            nom_trib_entreprise = %s,
            administrateur = %s,
            denoms_by_bce = %s,
            adresses_by_bce = %s,
            denoms_by_ejustice = %s
        WHERE url = %s;
    """, (
        doc.get("date_doc"),
        doc.get("lang"),
        (doc.get("text") or "").strip(),
        doc.get("keyword"),
        to_jsonb_safe(doc.get("TVA")),
        doc.get("title"),
        to_jsonb_safe(doc.get("num_nat")),
        to_jsonb_safe(doc.get("extra_keyword")),
        to_jsonb_safe(doc.get("nom")),
        to_jsonb_safe(doc.get("date_naissance")),
        to_jsonb_safe(doc.get("adresse")),
        doc.get("date_jugement"),
        to_jsonb_safe(doc.get("nom_trib_entreprise")),
        to_jsonb_safe(doc.get("administrateur")),
        to_jsonb_safe(doc.get("denoms_by_bce")),
        to_jsonb_safe(doc.get("adresses_by_bce")),
        to_jsonb_safe(doc.get("denoms_by_ejustice")),
        doc.get("url"),
    ))

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Document mis à jour pour URL : {doc.get('url')}")
