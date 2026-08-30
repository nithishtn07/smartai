import unittest
import json
import sqlite3
import datetime
from werkzeug.security import generate_password_hash
import app


class TestInterPortalCommunication(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.init_db()

    def setUp(self):
        self.app = app.app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key-campusguard'
        self.client = self.app.test_client()

        conn = app.get_db_connection()
        self.student = conn.execute("SELECT * FROM students WHERE register_number = 'STU001'").fetchone()
        if not self.student:
            conn.execute("""
                INSERT INTO students (register_number, name, email, department, semester, year, phone, status)
                VALUES ('STU001', 'Nithish Nagaraj', 'student@example.com', 'Computer Science & Engineering', 5, 3, '9876543210', 'ACTIVE')
            """)
            conn.commit()
            self.student = conn.execute("SELECT * FROM students WHERE register_number = 'STU001'").fetchone()
        else:
            conn.execute("UPDATE students SET name = 'Nithish Nagaraj', status = 'ACTIVE' WHERE id = ?", (self.student['id'],))
            conn.commit()

        self.parent = conn.execute("SELECT * FROM parents WHERE student_id = ?", (self.student['id'],)).fetchone()
        if not self.parent:
            conn.execute("""
                INSERT INTO parents (parent_id, student_id, name, email, phone, password_hash)
                VALUES ('PAR001', ?, 'Nagaraj T', 'parent@example.com', '9876543211', 'hash')
            """, (self.student['id'],))
            conn.commit()
            self.parent = conn.execute("SELECT * FROM parents WHERE student_id = ?", (self.student['id'],)).fetchone()
        
        # Ensure parent_student mapping and attendance records
        conn.execute("INSERT OR IGNORE INTO parent_student (parent_id, student_id, relationship, is_primary) VALUES (?, ?, 'Father', 1)", (self.parent['id'], self.student['id']))
        conn.execute("INSERT OR IGNORE INTO attendance (student_id, subject_code, subject_name, classes_held, classes_attended, classes_missed, attendance_pct) VALUES (?, 'CS301', 'Database Management Systems', 40, 37, 3, 92.5)", (self.student['id'],))
        conn.commit()

        self.faculty = conn.execute("SELECT * FROM faculties WHERE email = 'faculty@example.com'").fetchone()
        self.admin = conn.execute("SELECT * FROM admins WHERE username = 'admin'").fetchone()
        conn.close()

    def tearDown(self):
        # Restore standard seed values so other test suites run with pristine data
        conn = app.get_db_connection()
        conn.execute("UPDATE attendance SET classes_held = 40, classes_attended = 37, classes_missed = 3, attendance_pct = 92.5 WHERE student_id = ? AND subject_code = 'CS301'", (self.student['id'],))
        conn.commit()
        conn.close()

    def test_01_student_name_throughout_portals(self):
        """Verify Nithish Nagaraj appears in student, parent, faculty, and admin views."""
        # Student Dashboard
        with self.client.session_transaction() as sess:
            sess['student_id'] = self.student['id']
            sess['user_role'] = 'student'
        resp_stu = self.client.get('/student/dashboard')
        self.assertEqual(resp_stu.status_code, 200)
        self.assertIn(b'Nithish Nagaraj', resp_stu.data)

        # Parent Dashboard
        with self.client.session_transaction() as sess:
            sess['parent_id'] = self.parent['id']
            sess['user_role'] = 'parent'
        resp_par = self.client.get('/parent/dashboard')
        self.assertEqual(resp_par.status_code, 200)
        self.assertIn(b'Nithish Nagaraj', resp_par.data)

        # Faculty Attendance
        with self.client.session_transaction() as sess:
            sess['faculty_id'] = self.faculty['id']
            sess['user_role'] = 'faculty'
        resp_fac = self.client.get('/faculty/attendance')
        self.assertEqual(resp_fac.status_code, 200)
        self.assertIn(b'Nithish Nagaraj', resp_fac.data)

    def test_02_faculty_attendance_low_warning_trigger(self):
        """Verify marking low attendance generates alerts for both Student and Parent."""
        with self.client.session_transaction() as sess:
            sess['faculty_id'] = self.faculty['id']
            sess['user_role'] = 'faculty'

        # Force attendance to low percentage by marking multiple absents in CS301
        conn = app.get_db_connection()
        conn.execute("UPDATE attendance SET classes_held = 20, classes_attended = 14, classes_missed = 6, attendance_pct = 70.0 WHERE student_id = ? AND subject_code = 'CS301'", (self.student['id'],))
        conn.commit()
        conn.close()

        # Submit attendance via faculty route
        resp = self.client.post('/faculty/attendance', data={
            'course_code': 'CS301',
            'student_id': str(self.student['id']),
            'status': 'Absent',
            'date': '2026-08-21',
            'topic': 'Distributed Consensus'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Verify notifications created for student and parent
        conn = app.get_db_connection()
        stu_notif = conn.execute("SELECT * FROM notifications WHERE recipient_role = 'student' AND recipient_id = ? AND category = 'Attendance' ORDER BY id DESC LIMIT 1", (self.student['id'],)).fetchone()
        par_notif = conn.execute("SELECT * FROM notifications WHERE recipient_role = 'parent' AND recipient_id = ? AND category = 'Attendance' ORDER BY id DESC LIMIT 1", (self.parent['id'],)).fetchone()
        conn.close()

        self.assertIsNotNone(stu_notif)
        self.assertIn('Low Attendance Alert', stu_notif['title'])
        self.assertIsNotNone(par_notif)
        self.assertIn('Low Attendance', par_notif['title'])

    def test_03_faculty_marks_publishing_workflow(self):
        """Verify publishing marks updates assessment grades and notifies Student and Parent."""
        with self.client.session_transaction() as sess:
            sess['faculty_id'] = self.faculty['id']
            sess['user_role'] = 'faculty'

        resp = self.client.post('/faculty/marks', data={
            'course_code': 'CS302',
            'student_id': str(self.student['id']),
            'cat1': '48.0',
            'cat2': '49.0',
            'fat': '95.0'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Verify DB marks record and notifications
        conn = app.get_db_connection()
        mark = conn.execute("SELECT * FROM marks WHERE student_id = ? AND course_code = 'CS302'", (self.student['id'],)).fetchone()
        self.assertIsNotNone(mark)
        self.assertEqual(mark['grade'], 'S')

        stu_notif = conn.execute("SELECT * FROM notifications WHERE recipient_role = 'student' AND recipient_id = ? AND category = 'Academic' ORDER BY id DESC LIMIT 1", (self.student['id'],)).fetchone()
        self.assertIsNotNone(stu_notif)
        self.assertIn('CS302', stu_notif['title'])
        conn.close()

    def test_04_leave_approval_workflow(self):
        """Verify leave request submission and faculty approval updates status and dispatches alerts."""
        # 1. Student creates leave
        conn = app.get_db_connection()
        conn.execute("""
            INSERT INTO hostel_leaves (student_id, leave_type, from_date, to_date, reason, status)
            VALUES (?, 'Home Visit', '2026-08-28', '2026-08-30', 'Family wedding ceremony', 'Pending')
        """, (self.student['id'],))
        leave_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()

        # 2. Faculty approves leave
        with self.client.session_transaction() as sess:
            sess['faculty_id'] = self.faculty['id']
            sess['user_role'] = 'faculty'

        resp = self.client.post(f'/faculty/leaves/decision/{leave_id}', data={
            'decision': 'Approved'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # 3. Check status in DB and notifications
        conn = app.get_db_connection()
        leave = conn.execute("SELECT * FROM hostel_leaves WHERE id = ?", (leave_id,)).fetchone()
        self.assertEqual(leave['status'], 'Approved')

        stu_notif = conn.execute("SELECT * FROM notifications WHERE recipient_role = 'student' AND recipient_id = ? AND category = 'Leave' ORDER BY id DESC LIMIT 1", (self.student['id'],)).fetchone()
        self.assertIsNotNone(stu_notif)
        self.assertIn('Approved', stu_notif['title'])
        conn.close()

    def test_05_admin_announcement_broadcast(self):
        """Verify admin announcement broadcasts to all target portals and notifications."""
        with self.client.session_transaction() as sess:
            sess['admin_id'] = self.admin['id']
            sess['user_role'] = 'admin'

        resp = self.client.post('/admin/announcements', data={
            'title': 'Campus Wide Holiday Notice',
            'description': 'Campus will remain closed on Friday for Founder Day celebrations.',
            'category': 'General',
            'priority': 'High',
            'target_audience': 'All'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Verify announcement in DB
        conn = app.get_db_connection()
        ann = conn.execute("SELECT * FROM announcements WHERE title = 'Campus Wide Holiday Notice'").fetchone()
        self.assertIsNotNone(ann)

        # Verify notification fan-out
        stu_notif = conn.execute("SELECT * FROM notifications WHERE recipient_role = 'student' AND title LIKE '%Campus Wide Holiday Notice%'").fetchone()
        par_notif = conn.execute("SELECT * FROM notifications WHERE recipient_role = 'parent' AND title LIKE '%Campus Wide Holiday Notice%'").fetchone()
        fac_notif = conn.execute("SELECT * FROM notifications WHERE recipient_role = 'faculty' AND title LIKE '%Campus Wide Holiday Notice%'").fetchone()
        conn.close()

        self.assertIsNotNone(stu_notif)
        self.assertIsNotNone(par_notif)
        self.assertIsNotNone(fac_notif)

    def test_06_two_way_messaging_student_parent_faculty(self):
        """Verify messages sent between Student, Parent, and Faculty are stored and retrieved correctly."""
        # Student sends message to Parent
        with self.client.session_transaction() as sess:
            sess['student_id'] = self.student['id']
            sess['user_role'] = 'student'

        resp1 = self.client.post('/student/messages', data={
            'recipient_role': 'parent',
            'subject': 'Weekend Travel Update',
            'content': 'Hi Dad, I will be boarding the 5 PM bus this Friday.'
        }, follow_redirects=True)
        self.assertEqual(resp1.status_code, 200)

        # Parent views message in Parent Messages
        with self.client.session_transaction() as sess:
            sess['parent_id'] = self.parent['id']
            sess['user_role'] = 'parent'

        resp2 = self.client.get('/parent/messages')
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b'Weekend Travel Update', resp2.data)

        # Faculty sends message to Student
        with self.client.session_transaction() as sess:
            sess['faculty_id'] = self.faculty['id']
            sess['user_role'] = 'faculty'

        resp3 = self.client.post('/faculty/messages', data={
            'recipient_target': f"student_{self.student['id']}",
            'subject': 'Project Consultation Slot',
            'content': 'Please meet me in cabin CS-201 at 3 PM tomorrow.'
        }, follow_redirects=True)
        self.assertEqual(resp3.status_code, 200)

        # Student views message
        with self.client.session_transaction() as sess:
            sess['student_id'] = self.student['id']
            sess['user_role'] = 'student'

        resp4 = self.client.get('/student/messages')
        self.assertEqual(resp4.status_code, 200)
        self.assertIn(b'Project Consultation Slot', resp4.data)

    def test_07_sos_four_stage_state_engine(self):
        """Verify SOS lifecycle: ACTIVE -> ACKNOWLEDGED -> RESPONDING -> RESOLVED."""
        # 1. Student triggers SOS
        with self.client.session_transaction() as sess:
            sess['student_id'] = self.student['id']
            sess['user_role'] = 'student'

        resp1 = self.client.post('/student/emergency', data={
            'location': 'Hostel Block B Corridor',
            'latitude': '12.9716',
            'longitude': '77.5946'
        }, follow_redirects=True)
        self.assertEqual(resp1.status_code, 200)

        conn = app.get_db_connection()
        inc = conn.execute("SELECT * FROM incidents WHERE student_id = ? AND incident_type = 'EMERGENCY_SOS' ORDER BY id DESC LIMIT 1", (self.student['id'],)).fetchone()
        self.assertIsNotNone(inc)
        self.assertEqual(inc['status'], 'ACTIVE')
        incident_id = inc['incident_id']
        conn.close()

        # 2. Admin transitions to ACKNOWLEDGED
        with self.client.session_transaction() as sess:
            sess['admin_id'] = self.admin['id']
            sess['user_role'] = 'admin'

        resp_ack = self.client.post('/admin/sos/status-update', data={
            'incident_id': incident_id,
            'new_status': 'ACKNOWLEDGED'
        }, follow_redirects=True)
        self.assertEqual(resp_ack.status_code, 200)

        conn = app.get_db_connection()
        inc_ack = conn.execute("SELECT status FROM incidents WHERE incident_id = ?", (incident_id,)).fetchone()
        self.assertEqual(inc_ack['status'], 'ACKNOWLEDGED')

        # 3. Admin transitions to RESPONDING
        self.client.post('/admin/sos/status-update', data={
            'incident_id': incident_id,
            'new_status': 'RESPONDING'
        }, follow_redirects=True)
        inc_resp = conn.execute("SELECT status FROM incidents WHERE incident_id = ?", (incident_id,)).fetchone()
        self.assertEqual(inc_resp['status'], 'RESPONDING')

        # 4. Admin transitions to RESOLVED
        self.client.post('/admin/sos/status-update', data={
            'incident_id': incident_id,
            'new_status': 'RESOLVED'
        }, follow_redirects=True)
        inc_res = conn.execute("SELECT status FROM incidents WHERE incident_id = ?", (incident_id,)).fetchone()
        self.assertEqual(inc_res['status'], 'RESOLVED')
        conn.close()

    def test_08_notification_apis_and_unread_counters(self):
        """Verify /api/notifications/unread-count and /api/notifications/recent."""
        with self.client.session_transaction() as sess:
            sess['student_id'] = self.student['id']
            sess['user_role'] = 'student'

        resp = self.client.get('/api/notifications/unread-count')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn('unread_count', data)
        self.assertEqual(data['role'], 'student')

        resp_recent = self.client.get('/api/notifications/recent')
        self.assertEqual(resp_recent.status_code, 200)
        data_recent = json.loads(resp_recent.data)
        self.assertIn('notifications', data_recent)

    def test_09_role_authorization_and_guards(self):
        """Verify protected routes redirect unauthorized users."""
        # Anonymous access to faculty dashboard
        resp1 = self.client.get('/faculty/dashboard')
        self.assertEqual(resp1.status_code, 302)
        self.assertIn('/faculty/login', resp1.headers['Location'])

        # Anonymous access to admin dashboard
        resp2 = self.client.get('/admin/dashboard')
        self.assertEqual(resp2.status_code, 302)
        self.assertIn('/admin/login', resp2.headers['Location'])

        # Student session trying to access faculty dashboard
        with self.client.session_transaction() as sess:
            sess['student_id'] = self.student['id']
            sess['user_role'] = 'student'

        resp3 = self.client.get('/faculty/dashboard')
        self.assertEqual(resp3.status_code, 302)
        self.assertIn('/faculty/login', resp3.headers['Location'])


if __name__ == '__main__':
    unittest.main()
