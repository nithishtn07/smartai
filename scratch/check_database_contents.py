import sqlite3

def check_all_tables():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
    print(f"Total Tables in database.db: {len(tables)}\n")

    for tbl in sorted(tables):
        count = cursor.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"Table '{tbl}': {count} rows")
        if count > 0 and tbl in ['emergencies', 'payment_transactions', 'complaints', 'emergency_reports', 'service_requests']:
            rows = cursor.execute(f"SELECT * FROM {tbl} LIMIT 5").fetchall()
            for r in rows:
                print("   ", dict(r))

    conn.close()

if __name__ == '__main__':
    check_all_tables()
