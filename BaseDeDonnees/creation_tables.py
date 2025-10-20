import psycopg2
from BaseDeDonnees.connexion_postgre import get_postgre_connection

def create_table_moniteur():
    """
    Crée la table moniteur_documents_postgre si elle n'existe pas encore
    et ajoute les index GIN/B-tree appropriés.
    """
    conn = get_postgre_connection()
    cur = conn.cursor()

    print("[📥] Connecté à PostgreSQL → base:", conn.get_dsn_parameters().get("dbname"))
    print("[🛠️] Vérification/création de la table moniteur_documents_postgre…")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS moniteur_documents_postgre (
            id SERIAL PRIMARY KEY,
            date_doc DATE,
            lang TEXT,
            text TEXT,
            url TEXT UNIQUE,
            keyword TEXT,
            tva JSONB,
            titre TEXT,
            num_nat JSONB,
            extra_keyword JSONB,
            nom JSONB,
            adresse JSONB,
            date_jugement TEXT,
            nom_trib_entreprise JSONB,
            date_deces JSONB,
            administrateur JSONB,
            denoms_by_bce JSONB,
            adresses_by_bce JSONB,
            denoms_by_ejustice JSONB
        );
    """)
    conn.commit()
    print("✅ Table moniteur_documents_postgre prête.")

    print("[⚙️] Vérification/création des index GIN et B-tree…")

    cur.execute("""
        -- B-tree (TEXT, DATE)
        CREATE INDEX IF NOT EXISTS idx_moniteur_keyword ON moniteur_documents_postgre (keyword);
        CREATE INDEX IF NOT EXISTS idx_moniteur_date_doc ON moniteur_documents_postgre (date_doc);
        CREATE INDEX IF NOT EXISTS idx_moniteur_url ON moniteur_documents_postgre (url);
        CREATE INDEX IF NOT EXISTS idx_moniteur_titre ON moniteur_documents_postgre (titre);
        CREATE INDEX IF NOT EXISTS idx_moniteur_lang ON moniteur_documents_postgre (lang);
        CREATE INDEX IF NOT EXISTS idx_moniteur_date_jugement ON moniteur_documents_postgre (date_jugement);

        -- GIN (JSONB)
        CREATE INDEX IF NOT EXISTS idx_moniteur_tva ON moniteur_documents_postgre USING GIN (tva);
        CREATE INDEX IF NOT EXISTS idx_moniteur_num_nat ON moniteur_documents_postgre USING GIN (num_nat);
        CREATE INDEX IF NOT EXISTS idx_moniteur_extra_keyword ON moniteur_documents_postgre USING GIN (extra_keyword);
        CREATE INDEX IF NOT EXISTS idx_moniteur_nom ON moniteur_documents_postgre USING GIN (nom);
        CREATE INDEX IF NOT EXISTS idx_moniteur_adresse ON moniteur_documents_postgre USING GIN (adresse);
        CREATE INDEX IF NOT EXISTS idx_moniteur_nom_trib ON moniteur_documents_postgre USING GIN (nom_trib_entreprise);
        CREATE INDEX IF NOT EXISTS idx_moniteur_date_deces ON moniteur_documents_postgre USING GIN (date_deces);
        CREATE INDEX IF NOT EXISTS idx_moniteur_admin ON moniteur_documents_postgre USING GIN (administrateur);
        CREATE INDEX IF NOT EXISTS idx_moniteur_denoms_bce ON moniteur_documents_postgre USING GIN (denoms_by_bce);
        CREATE INDEX IF NOT EXISTS idx_moniteur_adresses_bce ON moniteur_documents_postgre USING GIN (adresses_by_bce);
        CREATE INDEX IF NOT EXISTS idx_moniteur_denoms_ejustice ON moniteur_documents_postgre USING GIN (denoms_by_ejustice);
    """)

    conn.commit()
    print("✅ Index créés avec succès.")
    cur.close()
    conn.close()
