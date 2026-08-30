import sqlite3

def main():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row

    conn.execute("UPDATE parents SET name = 'Nagaraj' WHERE parent_id = 'PAR001' OR email = 'parent@example.com' OR name LIKE '%Kumar%'")
    conn.execute("UPDATE students SET parent_name = 'Nagaraj' WHERE id = 1 OR parent_name LIKE '%Kumar%'")
    conn.execute("UPDATE parent_messages SET receiver_name = 'Nagaraj' WHERE receiver_name LIKE '%Kumar%'")
    conn.execute("UPDATE parent_messages SET content = REPLACE(content, 'Dear Mr. Kumar', 'Dear Mr. Nagaraj')")
    conn.execute("UPDATE emergency_notifications SET recipient_name = 'Nagaraj' WHERE recipient_name LIKE '%Kumar%'")
    conn.commit()

    conn.execute("DELETE FROM payment_transactions")
    conn.execute("UPDATE fees SET paid_amount = 0, status = 'PENDING' WHERE student_id = 1")
    conn.execute("UPDATE fees SET status = 'OVERDUE' WHERE due_date < '2026-08-23' AND student_id = 1")
    conn.commit()

    print("Updated Parents:")
    for p in conn.execute("SELECT id, parent_id, name, email FROM parents").fetchall():
        print(dict(p))

    print("\nUpdated Students:")
    for s in conn.execute("SELECT id, name, parent_name FROM students").fetchall():
        print(dict(s))

    print(f"\nPayment Transactions Count: {conn.execute('SELECT COUNT(*) FROM payment_transactions').fetchone()[0]}")
    conn.close()

if __name__ == '__main__':
    main()
