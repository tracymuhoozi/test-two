"""Create the tables if they do not exist. Runs once before the web server starts."""
from pathlib import Path

import db


def main():
    conn = db.connect(retries=30, delay=2)
    schema = Path(__file__).with_name("schema.sql").read_text()
    with conn.cursor() as cur:
        for statement in (part.strip() for part in schema.split(";")):
            if statement:
                cur.execute(statement)
    conn.close()
    print("Database schema is ready.", flush=True)


if __name__ == "__main__":
    main()
