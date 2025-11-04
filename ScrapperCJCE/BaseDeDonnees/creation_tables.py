import psycopg2
from BaseDeDonnees.connexion_postgre import get_postgre_connection


def create_table_moniteur():
    conn = get_postgre_connection()
    cur = conn.cursor()

    print("[📥] Connexion OK, création tables…")

    cur.execute("""

    -- =====================================================================
    -- TABLE 1 : décision du moniteur (document principal)
    -- =====================================================================
    CREATE TABLE decision (
        id CHAR(64) PRIMARY KEY,
        date_doc DATE,
        lang TEXT,
        text TEXT,
        url TEXT UNIQUE,
        keyword TEXT,
        titre TEXT,
        extra_keyword JSONB,
        date_jugement JSONB
    );

    CREATE INDEX idx_decision_date_doc  ON decision(date_doc);
    CREATE INDEX idx_decision_keyword   ON decision(keyword);
    CREATE INDEX idx_decision_titre     ON decision(titre);

    -- =====================================================================
    -- TABLE 2 : société associée (normalisation des données BCE/eJustice)
    -- =====================================================================
    CREATE TABLE societe (
        id SERIAL PRIMARY KEY,
        bce VARCHAR(20) UNIQUE,
        nom TEXT,
        adresse TEXT,
        source TEXT,
        confidence NUMERIC(3,2),      -- 1.00 ejustice / 0.9 csv / 0.6 fallback...
        json_source JSONB             -- raw JSON (utile pour debug et audit)
    );

    CREATE INDEX idx_societe_bce       ON societe(bce);
    CREATE INDEX idx_societe_nom       ON societe(nom);

    -- =====================================================================
    -- TABLE 3 : liaison décision ↔ société (N:N)
    -- =====================================================================
    CREATE TABLE decision_societe (
        decision_id CHAR(64) REFERENCES decision(id) ON DELETE CASCADE,
        societe_id INT REFERENCES societe(id) ON DELETE CASCADE,
        PRIMARY KEY (decision_id, societe_id)
    );

    -- =====================================================================
    -- TABLE 4 : administrateur (personnes physiques)
    -- =====================================================================
    CREATE TABLE administrateur (
        id SERIAL PRIMARY KEY,
        nom TEXT,
        role TEXT,             -- curateur / liquidateur / administrateur / avocat
        source TEXT,
        confidence NUMERIC(3,2)
    );

    CREATE INDEX idx_admin_nom ON administrateur(nom);

    -- =====================================================================
    -- TABLE 5 : liaison société ↔ administrateur (N:N)
    -- =====================================================================
    CREATE TABLE societe_admin (
        societe_id INT REFERENCES societe(id) ON DELETE CASCADE,
        admin_id INT REFERENCES administrateur(id) ON DELETE CASCADE,
        PRIMARY KEY (societe_id, admin_id)
    );
    """)

    # ---- VIEW fiche société (JOIN des infos) ----
    cur.execute("""
CREATE OR REPLACE VIEW vue_fiche_societe AS
SELECT
    s.id AS societe_id,
    regexp_replace(s.bce, '[^0-9]', '', 'g') AS bce_clean,
    s.bce AS bce_original,

        COALESCE(
        -- ✅ 1. nom BCE officiel
        s.json_source -> 'denoms_by_bce' -> 0 -> 'noms' ->> 0,

        -- ✅ 2. nom détecté dans adresses_by_ejustice
        s.json_source -> 'adresses_by_ejustice' -> 'array' -> 0 ->> 'nom',

        -- ✅ 3. fallback trouvé par Meili
        s.json_source -> 'denom_fallback_bce' -> 0 ->> 'nom',

        -- ✅ 4. nom stocké dans table societe (fallback moniteur)
        s.nom
    ) AS societe_nom,

    COALESCE(
        -- ✅ adresse BCE
        s.json_source -> 'adresses_by_bce' -> 0 -> 'adresses' -> 0 ->> 'adresse',

        -- ✅ adresse eJustice
        s.json_source -> 'adresses_by_ejustice' -> 'array' -> 0 ->> 'adresse',

        -- ✅ fallback ancien champ
        s.adresse
    ) AS adresse,


    s.source AS societe_source,

    d.id AS decision_id,
    d.date_doc,
    d.titre,
    d.keyword,
    d.url,

    json_agg(
        json_build_object(
            'nom', a.nom,
            'role', a.role,
            'source', a.source,
            'confidence', a.confidence
        )
    ) FILTER (WHERE a.id IS NOT NULL) AS administrateurs

FROM societe s
LEFT JOIN decision_societe ds ON s.id = ds.societe_id
LEFT JOIN decision d ON ds.decision_id = d.id
LEFT JOIN societe_admin sa ON s.id = sa.societe_id
LEFT JOIN administrateur a ON sa.admin_id = a.id
GROUP BY s.id, d.id;





    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Tables créées proprement (modèle normalisé).")
