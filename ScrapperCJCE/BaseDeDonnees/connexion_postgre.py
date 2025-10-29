import os
import psycopg2
from dotenv import load_dotenv

def get_postgre_connection():
    """Crée et retourne une connexion PostgreSQL à partir des variables d'environnement .env"""
    load_dotenv()

    db_params = {
        "dbname": os.getenv("POSTGRE_DB", "mabase10"),
        "user": os.getenv("POSTGRE_USER", "postgres"),
        "password": os.getenv("POSTGRE_PASSWORD", ""),
        "host": os.getenv("POSTGRE_HOST", "localhost"),
        "port": os.getenv("POSTGRE_PORT", "5432"),
    }

    conn = psycopg2.connect(**db_params)
    print(f"[📥] Connecté à PostgreSQL → base: {db_params['dbname']} ({db_params['host']}:{db_params['port']})")
    return conn
