"""
CampusGuard AI — Database Cleanup Script
Removes all fake, demo, test, and placeholder student and parent records,
while strictly preserving valid manually registered students, parents, and mappings.
"""

import sqlite3
import os

DATABASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database.db'))

def clean_database():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print("CAMPUSGUARD AI — DATABASE CLEANUP")
    print("=" * 60)

    # 1. Identify valid manual students to keep
    # Valid manual students in DB: 25MID1027 (T N NITHISH) and STU004 (HARSHIKA)
    keep_student_ids = []
    for row in cursor.execute("SELECT id, register_number, name, email FROM students").fetchall():
        if row['register_number'] in ['25MID1027', 'STU004'] or ('vitstudent.ac.in' in row['email'] or 'student4@gmail.com' in row['email']):
            keep_student_ids.append(row['id'])
            print(f"[KEEP STUDENT] id={row['id']} | reg={row['register_number']} | name={row['name']} | email={row['email']}")

    # 2. Identify fake/demo/test students to remove
    delete_student_ids = []
    for row in cursor.execute("SELECT id, register_number, name, email FROM students").fetchall():
        if row['id'] not in keep_student_ids:
            delete_student_ids.append(row['id'])
            print(f"[REMOVE STUDENT] id={row['id']} | reg={row['register_number']} | name={row['name']} | email={row['email']}")

    # 3. Identify valid manual parents to keep
    keep_parent_ids = []
    for row in cursor.execute("SELECT id, parent_id, name, email FROM parents").fetchall():
        if row['parent_id'] == 'PAR268C6' or row['email'] == 'suminagaraj06@gmail.com':
            keep_parent_ids.append(row['id'])
            print(f"[KEEP PARENT] id={row['id']} | pid={row['parent_id']} | name={row['name']} | email={row['email']}")

    # 4. Identify fake/demo/test parents to remove
    delete_parent_ids = []
    for row in cursor.execute("SELECT id, parent_id, name, email FROM parents").fetchall():
        if row['id'] not in keep_parent_ids:
            delete_parent_ids.append(row['id'])
            print(f"[REMOVE PARENT] id={row['id']} | pid={row['parent_id']} | name={row['name']} | email={row['email']}")

    # 5. Clean dependent records for deleted students
    if delete_student_ids:
        placeholders = ','.join('?' for _ in delete_student_ids)
        cursor.execute(f"DELETE FROM attendance WHERE student_id IN ({placeholders})", delete_student_ids)
        cursor.execute(f"DELETE FROM marks WHERE student_id IN ({placeholders})", delete_student_ids)
        cursor.execute(f"DELETE FROM fees WHERE student_id IN ({placeholders})", delete_student_ids)
        cursor.execute(f"DELETE FROM hostel_leaves WHERE student_id IN ({placeholders})", delete_student_ids)
        cursor.execute(f"DELETE FROM incidents WHERE student_id IN ({placeholders})", delete_student_ids)
        cursor.execute(f"DELETE FROM complaints WHERE student_id IN ({placeholders})", delete_student_ids)
        cursor.execute(f"DELETE FROM parent_messages WHERE student_id IN ({placeholders})", delete_student_ids)
        cursor.execute(f"DELETE FROM student_transport WHERE student_id IN ({placeholders})", delete_student_ids)
        cursor.execute(f"DELETE FROM parent_student WHERE student_id IN ({placeholders})", delete_student_ids)
        cursor.execute(f"DELETE FROM notifications WHERE recipient_role = 'student' AND recipient_id IN ({placeholders})", delete_student_ids)
        cursor.execute(f"DELETE FROM students WHERE id IN ({placeholders})", delete_student_ids)

    # 6. Clean dependent records for deleted parents
    if delete_parent_ids:
        p_placeholders = ','.join('?' for _ in delete_parent_ids)
        cursor.execute(f"DELETE FROM parent_messages WHERE parent_id IN ({p_placeholders})", delete_parent_ids)
        cursor.execute(f"DELETE FROM parent_alert_reads WHERE parent_id IN ({p_placeholders})", delete_parent_ids)
        cursor.execute(f"DELETE FROM parent_student WHERE parent_id IN ({p_placeholders})", delete_parent_ids)
        cursor.execute(f"DELETE FROM notifications WHERE recipient_role = 'parent' AND recipient_id IN ({p_placeholders})", delete_parent_ids)
        cursor.execute(f"DELETE FROM parents WHERE id IN ({p_placeholders})", delete_parent_ids)

    # Clean any orphan parent_student links
    cursor.execute("""
        DELETE FROM parent_student 
        WHERE student_id NOT IN (SELECT id FROM students)
           OR parent_id NOT IN (SELECT id FROM parents)
    """)

    # Clean old login attempts
    cursor.execute("DELETE FROM login_attempts")

    conn.commit()

    # 7. Print final state verification
    print("\n" + "=" * 60)
    print("FINAL DATABASE STATE (AFTER CLEANUP)")
    print("=" * 60)
    
    final_students = cursor.execute("SELECT id, register_number, name, email, phone, status FROM students").fetchall()
    print(f"Remaining Students ({len(final_students)}):")
    for s in final_students:
        print(f"  - [{s['register_number']}] {s['name']} ({s['email']}) [Status: {s['status']}]")

    final_parents = cursor.execute("SELECT id, parent_id, name, email, phone, student_id FROM parents").fetchall()
    print(f"\nRemaining Parents ({len(final_parents)}):")
    for p in final_parents:
        print(f"  - [{p['parent_id']}] {p['name']} ({p['email']}) [Linked Student ID: {p['student_id']}]")

    final_ps = cursor.execute("""
        SELECT ps.id, p.name as parent_name, p.parent_id, s.name as student_name, s.register_number, ps.relationship
        FROM parent_student ps
        JOIN parents p ON ps.parent_id = p.id
        JOIN students s ON ps.student_id = s.id
    """).fetchall()
    print(f"\nRemaining Parent-Student Links ({len(final_ps)}):")
    for link in final_ps:
        print(f"  - Parent: {link['parent_name']} ({link['parent_id']}) <--> Ward: {link['student_name']} ({link['register_number']}) [{link['relationship']}]")

    conn.close()
    print("\n[SUCCESS] Fake student and parent cleanup completed successfully.")

if __name__ == '__main__':
    clean_database()
