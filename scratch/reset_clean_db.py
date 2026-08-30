import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sqlite3
from database.db import init_db, get_db_connection
from database.seed import seed_database

def reset_clean_database():
    db_path = 'database.db'
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed old {db_path}")

    # Re-initialize schema
    init_db()
    print("Database schema created.")

    # Re-seed baseline data
    conn = get_db_connection()
    seed_database(conn)
    conn.commit()

    print("\n--- Clean Initial Database Seed Verification ---")
    cursor = conn.cursor()
    tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
    for tbl in sorted(tables):
        count = cursor.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl}: {count} rows")

    conn.close()

if __name__ == '__main__':
    reset_clean_database()
