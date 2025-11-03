import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv


def get_postgre_connection():
    """Crée automatiquement la base si elle n'existe pas, puis retourne une connexion."""
    load_dotenv()

    db_name = os.getenv("DB_NAME", "monsite_db")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")

    # ✅ Étape 1 : connexion à la base système "postgres"
    conn = psycopg2.connect(
        dbname="postgres",
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    # ✅ Étape 2 : vérifier si la DB existe déjà
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    exists = cur.fetchone()

    if not exists:
        print(f"🛠️ Base {db_name} absente → création…")
        cur.execute(f"CREATE DATABASE {db_name};")
    else:
        print(f"✅ Base {db_name} déjà existante.")

    cur.close()
    conn.close()

    # ✅ Étape 3 : connexion finale à la bonne base
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )

    print(f"[📥] Connecté à PostgreSQL → base: {db_name} ({db_host}:{db_port})")
    return conn
