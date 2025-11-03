from psycopg2.extras import Json
from tqdm import tqdm
from BaseDeDonnees.connexion_postgre import get_postgre_connection
import re


def normalize_bce(bce):
    """ Nettoie un numéro BCE/TVA : garde uniquement les chiffres """
    if not bce:
        return None
    bce = re.sub(r"[^0-9]", "", str(bce))
    # On veut 10 chiffres (ex: 0790225940). Si 9/11/plus: on laisse tel quel pour debug.
    return bce if bce else None


def extract_bce_candidates_from_text(text: str):
    """Retrouve des BCE possibles dans le texte (0790.225.940 ou 0790225940)."""
    if not text:
        return []
    patt = re.compile(r"\b(?:\d{4}\.\d{3}\.\d{3}|\d{10})\b")
    found = patt.findall(text)
    # normalise chaque match
    return [normalize_bce(x) for x in found if normalize_bce(x)]


def insert_documents_moniteur(documents):
    conn = get_postgre_connection()
    cur = conn.cursor()

    print(f"[📦] Insertion de {len(documents)} décisions…")

    for doc in tqdm(documents, desc="Insert PostgreSQL"):
        # DEBUG ciblé uniquement sur le document qui pose problème
        if doc.get("id") == "20c77b09788525debfa4e0dabcc56b63773242344b5754468008de6329cabd7b":
            print("\n\n=====================")
            print("🚨 DEBUG DOC CIBLE")
            print("=====================")
            print("ID:", doc.get("id"))
            print("date_doc:", doc.get("date_doc"))
            print("title:", doc.get("title"))
            print("TVA:", doc.get("TVA"))
            print("denoms_by_ejustice_flat:", doc.get("denoms_by_ejustice_flat"))
            print("adresses_by_ejustice:", doc.get("adresses_by_ejustice"))
            print("text:\n", doc.get("text"))
            print("=====================\n")
        # 1) DECISION
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

        # ⚠️ TOUJOURS initialiser pour éviter NameError
        societe_ids = []
        all_societes = []

        def debug(msg):
            if doc.get("id") == "20c77b09788525debfa4e0dabcc56b63773242344b5754468008de6329cabd7b":
                print("🔎", msg)

        # =========== eJustice ===========
        raw = doc.get("adresses_by_ejustice")
        debug(f"[eJustice] brut = {raw}")

        if isinstance(raw, dict) and "array" in raw:
            raw = raw["array"]
            debug(f"[eJustice] transformé (array) = {raw}")

        if isinstance(raw, list):
            for s in raw:
                debug(f"[eJustice] Société détectée → {s}")
                all_societes.append({
                    "bce": normalize_bce(s.get("bce")),
                    "nom": s.get("nom"),
                    "adresse": s.get("adresse"),
                    "source": "ejustice",
                    "confidence": 1.00,
                    "raw": s
                })

        # =========== TVA / regex Fallback ===========
        if not any(s.get("bce") for s in all_societes):

            debug("⚠️ Aucune société trouvée via eJustice, tentative fallback TVA + regex…")

            tva_list = doc.get("TVA") or []
            debug(f"[TVA] brut = {tva_list}")

            bce = None

            if isinstance(tva_list, list) and len(tva_list) > 0:
                bce = normalize_bce(tva_list[0])
                debug(f"[TVA] normalisée = {bce}")

            if not bce:
                # Extraction regex du texte
                found = extract_bce_candidates_from_text(doc.get("text"))
                debug(f"[regex] candidats détectés dans texte = {found}")

                if found:
                    bce = found[0]

            if bce:
                debug(f"✅ fallback → BCE retenue = {bce}")

                # nom minimal
                nom = (doc.get("denoms_by_ejustice_flat") or [None])[0] or doc.get("title") or "Société inconnue"

                all_societes.append({
                    "bce": bce,
                    "nom": nom,
                    "adresse": None,
                    "source": "tva_fallback",
                    "confidence": 0.50,
                    "raw": {"debug": "fallback TVA/regex"}
                })

        debug(f"✅ all_societes FINAL = {all_societes}")
        # 2.b) INSERT des sociétés + liaison décision
        for soc in all_societes:
            debug(f"🔥 INSERT société → BCE={soc.get('bce')} / nom={soc.get('nom')}")

            bce = soc.get("bce")
            if not bce:
                continue  # on ne crée rien sans BCE

            cur.execute("""
                INSERT INTO societe (bce, nom, adresse, source, confidence, json_source)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (bce) DO UPDATE SET
                    -- on garde nom/adresse existants si non nuls; sinon on prend la nouvelle valeur
                    nom        = COALESCE(societe.nom, EXCLUDED.nom),
                    adresse    = COALESCE(societe.adresse, EXCLUDED.adresse),
                    -- source/confidence: garder la "meilleure" source
                    source     = CASE
                                   WHEN societe.source = 'ejustice' THEN societe.source
                                   WHEN EXCLUDED.source = 'ejustice' THEN EXCLUDED.source
                                   ELSE societe.source
                                 END,
                    confidence = GREATEST(societe.confidence, EXCLUDED.confidence),
                    json_source = EXCLUDED.json_source
                RETURNING societe.id;
            """, (
                bce,
                soc.get("nom"),
                soc.get("adresse"),
                soc.get("source"),
                soc.get("confidence"),
                Json(soc.get("raw")),
            ))
            row = cur.fetchone()
            if not row:
                # (rare) si RETURNING ne renvoie rien
                cur.execute("SELECT id FROM societe WHERE bce = %s", (bce,))
                row = cur.fetchone()
            sid = row[0]
            societe_ids.append(sid)

            cur.execute("""
                INSERT INTO decision_societe (decision_id, societe_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
            """, (decision_id, sid))

        # 3) ADMINISTRATEURS (lié aux sociétés trouvées; si 0 société → 0 liaison)
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
            admin_id = cur.fetchone()[0]

            for sid in societe_ids:
                cur.execute("""
                    INSERT INTO societe_admin (societe_id, admin_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING;
                """, (sid, admin_id))

    conn.commit()
    conn.close()
    print("✅ Insertion FINIE (normalisation OK)")
