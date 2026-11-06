"""
Create the database named in DATABASE_URL if it doesn't exist yet. Never drops or alters an
existing database. Used by the `api-e2e` compose service for its dedicated test database.
"""

import os
import sys

import environ
import psycopg
from psycopg import sql


def main() -> int:
    config = environ.Env.db_url_config(os.environ["DATABASE_URL"])
    name = config["NAME"]
    with psycopg.connect(
        host=config["HOST"],
        port=config["PORT"] or 5432,
        user=config["USER"],
        password=config["PASSWORD"],
        dbname="postgres",
        autocommit=True,
    ) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", [name]).fetchone()
        if exists:
            print(f"Database {name!r} already exists.")
        else:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            print(f"Created database {name!r}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
