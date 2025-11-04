from psycopg2.extras import Json
from tqdm import tqdm
from BaseDeDonnees.connexion_postgre import get_postgre_connection
import re
import json


# =============================================================
# ✅ UTILS FORMATS
# =============================================================

def normalize_bce(bce):
    if not bce:
        return None
    bce = re.sub(r"[^0-9]", "", str(bce))
    return bce if bce else None


def extract_bce_candidates_from_text(text: str):
    if not text:
        return []
    patt = re.compile(r"\b(?:\d{4}\.\d{3}\.\d{3}|\d{10})\b")
    return [normalize_bce(x) for x in patt.findall(text) if normalize_bce(x)]


def _first_non_empty_str(value):
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


# =============================================================
# ✅ NORMALISATION eJUSTICE (permet JSON double-encodé)
# =============================================================

def normalize_ejustice_list(raw):
    if raw is None:
        return []

    if isinstance(raw, str):         # JSON double-encodé
        try:
            raw = json.loads(raw)
        except Exception:
            return []

    if isinstance(raw, dict) and "array" in raw:
        raw = raw["array"]

    if isinstance(raw, list):
        res = []
        for x in raw:
            if not isinstance(x, dict):
                continue
            res.append({
                "bce": normalize_bce(x.get("bce")),
                "nom": _first_non_empty_str(x.get("nom")),
                "adresse": _first_non_empty_str(x.get("adresse")),
                "source": "ejustice"
            })
        return res

    return []


# =============================================================
# ✅ EXTRACTION BCE CSV
# =============================================================

def extract_nom_from_bce(doc):
    denoms = doc.get("denoms_by_bce")
    if not isinstance(denoms, list) or not denoms:
        return None

    first = denoms[0]

    if isinstance(first, dict):
        noms = first.get("noms") or []
        if isinstance(noms, list) and noms:
            return _first_non_empty_str(noms[0])

        return _first_non_empty_str(first.get("nom") or first.get("denomination"))

    if isinstance(first, str):
        return _first_non_empty_str(first)

    return None


def extract_adresse_from_bce(doc):
    adrs = doc.get("adresses_by_bce")
    if not isinstance(adrs, list) or not adrs:
        return None

    first = adrs[0]

    if isinstance(first, dict):
        arr = first.get("adresses") or []
        if isinstance(arr, list) and arr:
            return _first_non_empty_str(arr[0].get("adresse"))

        return _first_non_empty_str(first.get("adresse"))

    if isinstance(first, str):
        return _first_non_empty_str(first)

    return None


# =============================================================
# ✅ PRIORITISATION DE LA BCE
# =============================================================

def choose_bce(doc, ej_list):
    tvas = doc.get("TVA") or []
    for t in tvas:
        b = normalize_bce(t)
        if b:
            return b

    if ej_list:
        b = normalize_bce(ej_list[0].get("bce"))
        if b:
            return b

    found = extract_bce_candidates_from_text(doc.get("text"))
    if found:
        return found[0]

    return None


# =============================================================
# ✅ INSERT / UPDATE COMPLET
# =============================================================

def insert_documents_moniteur(documents, update_only=False):

    conn = get_postgre_connection()
    cur = conn.cursor()

    print(f"[📦] INSERT/UPDATE PostgreSQL sur {len(documents)} documents…")

    for doc in tqdm(documents, desc="PostgreSQL"):

        # --- TABLE DECISION ---
        if not update_only:
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
        societe_ids = []


        # --- CLEAN DATA ---

        ej_list = normalize_ejustice_list(doc.get("adresses_by_ejustice"))
        bce = choose_bce(doc, ej_list)


        # NOM
        nom = (
            extract_nom_from_bce(doc)
            or (ej_list[0]["nom"] if ej_list and ej_list[0].get("nom") else None)
        )

        fb = doc.get("denom_fallback_bce")
        if not nom and isinstance(fb, list) and fb:
            nom = _first_non_empty_str(fb[0].get("nom") if isinstance(fb[0], dict) else fb[0])

        nom = nom or "Société inconnue"


        # ADRESSE
        adresse = (
            (ej_list[0]["adresse"] if ej_list and ej_list[0].get("adresse") else None)
            or extract_adresse_from_bce(doc)
        )

        if not adresse and isinstance(fb, list) and fb:
            adresse = _first_non_empty_str(fb[0].get("adresse") if isinstance(fb[0], dict) else fb[0])


        # SOURCE / CONFIDENCE
        if ej_list:
            source = "ejustice"
            confidence = 1.0
        elif extract_nom_from_bce(doc) or extract_adresse_from_bce(doc):
            source = "bce"
            confidence = 0.8
        else:
            source = "fallback"
            confidence = 0.5


        # --- DEBUG ---
        print("---------")
        print("🔍 DEBUG RESOLUTION SOCIETE")
        print(f"ID decision     : {decision_id}")
        print(f"BCE choisie     : {bce}")
        print(f"→ NOM RETENU    : {nom}")
        print(f"→ ADR RETENUE   : {adresse}")
        print(f"Source retenue  : {source} (conf={confidence})")
        print("---------")


        # --- INSERT / UPDATE SOCIETE (une seule par doc) ---
        if bce:
            cur.execute("""
                INSERT INTO societe (bce, nom, adresse, source, confidence, json_source)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (bce) DO UPDATE SET
                    nom = CASE
                            WHEN EXCLUDED.source = 'ejustice' THEN EXCLUDED.nom
                            WHEN societe.nom = 'Société inconnue' THEN EXCLUDED.nom
                            ELSE societe.nom
                          END,
                    adresse = CASE
                                WHEN EXCLUDED.source = 'ejustice' THEN EXCLUDED.adresse
                                WHEN societe.adresse IS NULL OR societe.adresse = '' THEN EXCLUDED.adresse
                                ELSE societe.adresse
                              END,
                    source = CASE
                                WHEN EXCLUDED.source = 'ejustice' THEN 'ejustice'
                                ELSE societe.source
                             END,
                    confidence = GREATEST(societe.confidence, EXCLUDED.confidence),
                    json_source = EXCLUDED.json_source
                RETURNING societe.id;
            """, (
                bce,
                nom,
                adresse,
                source,
                confidence,
                Json({
                    "denoms_by_bce": doc.get("denoms_by_bce"),
                    "adresses_by_bce": doc.get("adresses_by_bce"),
                    "adresses_by_ejustice": ej_list,
                    "denom_fallback_bce": doc.get("denom_fallback_bce"),
                })
            ))

            sid = cur.fetchone()[0]
            societe_ids.append(sid)


            if not update_only:
                cur.execute("""
                    INSERT INTO decision_societe (decision_id, societe_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING;
                """, (decision_id, sid))


        # --- ADMINISTRATEURS ---
        if not update_only:
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
    print("✅ FINI — PostgreSQL mis à jour")
