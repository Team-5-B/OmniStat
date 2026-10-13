"""Task 1.8: connect the API to PostgreSQL."""
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Open a NEW database connection for one request/transaction.

    DATABASE_URL is appropriate for a shared PostgreSQL server.
    Without it, Psycopg uses your local Mac account/Unix socket defaults.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return psycopg.connect(url)
    return psycopg.connect(dbname=os.getenv("DB_NAME", "omnistat"))
