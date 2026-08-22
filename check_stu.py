import app
from werkzeug.security import check_password_hash

app.init_db()
conn = app.get_db_connection()
conn.execute("DELETE FROM login_attempts")
conn.commit()
stu = conn.execute("SELECT * FROM students WHERE register_number = 'STU001'").fetchone()
print("STU:", dict(stu) if stu else None)
if stu:
    print("PW match:", check_password_hash(stu['password_hash'], 'Student@123'))

client = app.app.test_client()
r = client.post('/student/login', data={'register_number': 'STU001', 'password': 'Student@123'}, follow_redirects=False)
print("STATUS:", r.status_code)
print("LOCATION:", r.headers.get('Location'))
if r.status_code != 302:
    print("PAGE HTML SNIPPET:", r.data.decode('utf-8')[:1000])
