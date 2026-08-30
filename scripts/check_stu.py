import sqlite3
import json

conn = sqlite3.connect('database.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
print("TABLE COUNTS:")
for t in sorted(tables):
    cnt = cursor.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t}: {cnt}")

print("\nSTUDENTS:")
for s in cursor.execute("SELECT id, register_number, name, email, department, year, semester, cgpa, phone FROM students").fetchall():
    print(f"  {dict(s)}")

print("\nPARENTS:")
for p in cursor.execute("SELECT id, parent_id, name, email, phone, relationship, student_id FROM parents").fetchall():
    print(f"  {dict(p)}")

print("\nFACULTIES:")
for f in cursor.execute("SELECT id, faculty_id, name, email, department, designation FROM faculties").fetchall():
    print(f"  {dict(f)}")

print("\nADMINS:")
for a in cursor.execute("SELECT id, username, name, email, role FROM admins").fetchall():
    print(f"  {dict(a)}")

conn.close()

import app
from werkzeug.security import check_password_hash

client = app.app.test_client()
r = client.post('/student/login', data={'register_number': 'STU001', 'password': 'Student@123'}, follow_redirects=False)
print("STATUS:", r.status_code)
print("LOCATION:", r.headers.get('Location'))
if r.status_code != 302:
    print("PAGE HTML SNIPPET:", r.data.decode('utf-8')[:1000])
