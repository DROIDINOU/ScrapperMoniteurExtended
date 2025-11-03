from psycopg2.extras import Json
from tqdm import tqdm
from BaseDeDonnees.connexion_postgre import get_postgre_connection


def insert_documents_moniteur(documents):
    conn = get_postgre_connection()
    cur = conn.cursor()

    print(f"[📦] Insertion de {len(documents)} décisions…")

    for doc in tqdm(documents, desc="Insert PostgreSQL"):

        # ---------------------------------------------------------
        # 1️⃣  INSERT dans decision
        # ---------------------------------------------------------
        cur.execute("""
            INSERT INTO decision (id, date_doc, lang, text, url, keyword, titre, extra_keyword, date_jugement)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                text = EXCLUDED.text,
                extra_keyword = EXCLUDED.extra_keyword,
                date_jugement = EXCLUDED.date_jugement;
        """, (
            doc.get("id"),
            doc.get("date_doc"),
            doc.get("lang"),
            (doc.get("text") or "").strip(),
            doc.get("url"),
            doc.get("keyword"),
            doc.get("title"),
            Json(doc.get("extra_keyword")),
            Json(doc.get("date_jugement")),
        ))

        decision_id = doc.get("id")

        # ---------------------------------------------------------
        # 2️⃣  INSERT sociétés (ejustice / bce / fallback)
        #     doc["adresses_by_ejustice"], doc["denom_fallback_bce"], ...
        # ---------------------------------------------------------
        all_societes = []

        # 🟢 eJustice
        if isinstance(doc.get("adresses_by_ejustice"), list):
            for s in doc["adresses_by_ejustice"]:
                all_societes.append({
                    "bce": s.get("bce"),
                    "nom": s.get("nom"),
                    "adresse": s.get("adresse"),
                    "source": "ejustice",
                    "confidence": 1.00,
                    "raw": s
                })

        # 🟡 BCE CSV
        if isinstance(doc.get("denoms_by_bce"), list):
            for group in doc["denoms_by_bce"]:
                for nom in group.get("noms", []):
                    all_societes.append({
                        "bce": group.get("bce"),
                        "nom": nom,
                        "adresse": None,
                        "source": "bce",
                        "confidence": 0.90,
                        "raw": group
                    })

        # 🟠 fallback BCE (scrape)
        if isinstance(doc.get("denom_fallback_bce"), list):
            for s in doc["denom_fallback_bce"]:
                all_societes.append({
                    "bce": s.get("bce"),
                    "nom": s.get("nom"),
                    "adresse": s.get("adresse"),
                    "source": "fallback",
                    "confidence": 0.60,
                    "raw": s
                })

        for soc in all_societes:

            cur.execute("""
                INSERT INTO societe (bce, nom, adresse, source, confidence, json_source)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                soc.get("bce"),
                soc.get("nom"),
                soc.get("adresse"),
                soc.get("source"),
                soc.get("confidence"),
                Json(soc.get("raw")),
            ))

            societe_id = cur.fetchone()[0]

            # liaison décision ⇆ société
            cur.execute("""
                INSERT INTO decision_societe (decision_id, societe_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
            """, (decision_id, societe_id))

        # ---------------------------------------------------------
        # 3️⃣  INSERT administrateurs (si présents)
        # ---------------------------------------------------------
        admins = doc.get("administrateur") or []

        for admin in admins:
            cur.execute("""
                INSERT INTO administrateur (nom, role, source, confidence)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
            """, (
                admin.get("entity"),
                admin.get("role"),
                admin.get("raw", "auto"),
                0.8,
            ))

    conn.commit()
    conn.close()
    print("✅ Insertion FINIE (normalisation complète)")
