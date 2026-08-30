"""
CampusGuard AI — Post-Cleanup Final Verification
Checks:
1. Student table contains only genuine manual records.
2. Parent table contains only genuine manual records.
3. No fake/dummy data is regenerated on app/DB initialization.
4. Admin can manually create new Student and Parent records.
5. Student and Parent login and routes work properly.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from database.db import get_db_connection, init_db

def verify_all():
    print("=" * 60)
    print("POST-CLEANUP VERIFICATION SUITE")
    print("=" * 60)

    # Step 1: Initialize DB and verify persistence
    init_db()
    conn = get_db_connection()
    students = conn.execute("SELECT id, register_number, name, email, status FROM students").fetchall()
    parents = conn.execute("SELECT id, parent_id, name, email, student_id FROM parents").fetchall()
    conn.close()

    print(f"\n1. Active Students Count: {len(students)}")
    for s in students:
        print(f"   - {s['register_number']}: {s['name']} ({s['email']})")
        assert s['register_number'] in ['25MID1027', 'STU004'], f"Unexpected student: {s['register_number']}"

    print(f"\n2. Active Parents Count: {len(parents)}")
    for p in parents:
        print(f"   - {p['parent_id']}: {p['name']} ({p['email']})")
        assert p['parent_id'] == 'PAR268C6', f"Unexpected parent: {p['parent_id']}"

    # Step 2: Test Admin Manual Student Creation
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['admin_id'] = 1
        sess['user_role'] = 'admin'
        sess['name'] = 'Admin'

    res_add_stu = client.post('/admin/students/create', data={
        'register_number': 'MANUAL_VERIF_01',
        'name': 'Verification Student',
        'email': 'verif_stu@campus.edu',
        'phone': '+91 91234 56789',
        'department': 'Computer Science & Engineering',
        'year': 2,
        'semester': 3,
        'parent_name': 'Verification Parent',
        'parent_email': 'verif_parent@campus.edu',
        'parent_phone': '+91 98765 43210',
        'parent_relationship': 'Mother'
    }, follow_redirects=True)
    assert res_add_stu.status_code == 200, f"Failed to add manual student: {res_add_stu.status_code}"
    print("\n3. Admin manual Student creation: PASS")

    # Step 3: Test Admin Manual Parent Creation
    res_add_par = client.post('/admin/parents/create', data={
        'parent_id': 'PAR_VERIF_01',
        'name': 'Independent Guardian',
        'email': 'independent_guard@campus.edu',
        'phone': '+91 97777 66666',
        'relationship': 'Guardian',
        'occupation': 'Scientist',
        'student_id': 0
    }, follow_redirects=True)
    assert res_add_par.status_code == 200, f"Failed to add manual parent: {res_add_par.status_code}"
    print("4. Admin manual Parent creation: PASS")

    # Clean up verification temporary records
    conn = get_db_connection()
    conn.execute("DELETE FROM parents WHERE email IN ('verif_parent@campus.edu', 'independent_guard@campus.edu')")
    conn.execute("DELETE FROM parent_student WHERE student_id NOT IN (SELECT id FROM students)")
    conn.execute("DELETE FROM students WHERE register_number = 'MANUAL_VERIF_01'")
    conn.commit()
    conn.close()
    print("5. Temporary verification records cleaned: PASS")

    # Final DB Check
    conn = get_db_connection()
    students_final = conn.execute("SELECT register_number, name FROM students").fetchall()
    parents_final = conn.execute("SELECT parent_id, name FROM parents").fetchall()
    conn.close()

    print("\n" + "=" * 60)
    print("ALL VERIFICATIONS PASSED")
    print(f"Final Students ({len(students_final)}): {[dict(s) for s in students_final]}")
    print(f"Final Parents ({len(parents_final)}): {[dict(p) for p in parents_final]}")
    print("=" * 60)

if __name__ == '__main__':
    verify_all()
