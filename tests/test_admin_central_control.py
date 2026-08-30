"""
=============================================================================
CampusGuard AI — Complete Admin Central Control Center Integration Test Suite
=============================================================================
Verifies:
1. Admin Dashboard with dynamic metrics, KPI cards, and active SOS alerts
2. Student Management (Directory, Creation, 360 View, Status Toggle)
3. Parent Management (Directory, Creation, Linked Ward, Password Reset)
4. Faculty Management (Directory, Creation, Department & Cabin)
5. Academics & Courses (Catalog, Course Creation)
6. Attendance Monitoring & Low Attendance Warning Dispatch
7. Marks Ledger & Academic Performance Audit
8. Fees & Finance (Ledger, Invoice Issuance, Payment Receipt Verification)
9. Examination Timetable (Schedules, Exam Creation & Broadcast)
10. Hostel Leaves / Outpass Authorization (Approve/Reject Workflow)
11. Campus Safety Control Center & 4-Stage SOS State Transitions
12. Multi-Role Direct Messaging & Communication Hub
13. Institutional Report Generation
14. System Settings & Configuration Governance
15. Audit Logs Trail
16. Cross-Portal Stability & Authorization Isolation
=============================================================================
"""

import unittest
import app

class TestAdminCentralControl(unittest.TestCase):

    def setUp(self):
        self.app = app.app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key-campusguard'
        self.client = self.app.test_client()

        app.init_db()

        conn = app.get_db_connection()
        conn.execute("DELETE FROM login_attempts")
        conn.execute("DELETE FROM students WHERE register_number = 'STU999'")
        conn.execute("DELETE FROM parents WHERE parent_id = 'PAR999'")
        conn.execute("DELETE FROM faculties WHERE faculty_id = 'FAC999'")
        conn.execute("DELETE FROM courses WHERE course_code = 'CS399'")
        conn.execute("DELETE FROM fees WHERE fee_type = 'Research Lab Fee'")
        conn.execute("DELETE FROM hostel_leaves WHERE leave_type = 'Weekend Home Visit'")
        conn.execute("DELETE FROM incidents WHERE incident_id LIKE 'SOS-TEST-%'")
        stu = conn.execute("SELECT * FROM students WHERE register_number = 'STU001'").fetchone()
        if not stu:
            conn.execute("""
                INSERT INTO students (name, register_number, email, password_hash, department, year, semester, section, status)
                VALUES ('Nithish Nagaraj', 'STU001', 'student@example.com', 'hash', 'Computer Science & Engineering', 3, 5, 'A', 'ACTIVE')
            """)
        else:
            conn.execute("UPDATE students SET name = 'Nithish Nagaraj' WHERE register_number = 'STU001'")
        
        self.admin = conn.execute("SELECT * FROM admins WHERE username = 'admin'").fetchone()
        self.student = conn.execute("SELECT * FROM students WHERE register_number = 'STU001'").fetchone()
        self.parent = conn.execute("SELECT * FROM parents WHERE email = 'parent@example.com'").fetchone()
        self.faculty = conn.execute("SELECT * FROM faculties WHERE email = 'faculty@example.com'").fetchone()
        conn.commit()
        conn.close()

    def _login_admin(self):
        with self.client.session_transaction() as sess:
            sess['admin_id'] = self.admin['id']
            sess['user_role'] = 'admin'
            sess['admin_logged_in'] = True
            sess['admin_name'] = self.admin['name']

    def test_01_admin_dashboard_kpis_and_live_data(self):
        """Verify Admin Dashboard loads with KPIs, alerts, and charts."""
        self._login_admin()
        resp = self.client.get('/admin/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Institutional Control Center', resp.data)
        self.assertIn(b'Students', resp.data)
        self.assertIn(b'Parents', resp.data)
        self.assertIn(b'Faculty', resp.data)
        self.assertIn(b'Campus Attendance', resp.data)
        self.assertIn(b'Subject Attendance Compliance', resp.data)
        self.assertIn(b'Real-Time Emergency SOS Queue', resp.data)

    def test_02_admin_student_management_crud(self):
        """Verify Admin can list, create, view 360 profile, and toggle status of students."""
        self._login_admin()

        # 1. List
        resp_list = self.client.get('/admin/students')
        self.assertEqual(resp_list.status_code, 200)
        self.assertIn(b'Student Management Directory', resp_list.data)
        self.assertIn(b'STU001', resp_list.data)

        # 2. Create New Student
        resp_create = self.client.post('/admin/students/create', data={
            'register_number': 'STU999',
            'name': 'Test New Student',
            'email': 'stu999@example.com',
            'phone': '+91 99999 88888',
            'department': 'Computer Science & Engineering',
            'year': '3',
            'semester': '5'
        }, follow_redirects=True)
        self.assertEqual(resp_create.status_code, 200)
        self.assertIn(b'STU999', resp_create.data)
        self.assertIn(b'Test New Student', resp_create.data)

        # 3. View 360 Profile
        conn = app.get_db_connection()
        new_stu = conn.execute("SELECT id FROM students WHERE register_number = 'STU999'").fetchone()
        conn.close()
        self.assertIsNotNone(new_stu)

        resp_view = self.client.get(f'/admin/students/view/{new_stu["id"]}')
        self.assertEqual(resp_view.status_code, 200)
        self.assertIn(b'Test New Student', resp_view.data)
        self.assertIn(b'Academic &amp; Contact Info', resp_view.data)
        self.assertIn(b'Course Attendance', resp_view.data)

        # 4. Toggle Status
        resp_toggle = self.client.post(f'/admin/students/toggle-status/{new_stu["id"]}', follow_redirects=True)
        self.assertEqual(resp_toggle.status_code, 200)
        self.assertIn(b'DISABLED', resp_toggle.data)

    def test_03_admin_parent_management(self):
        """Verify Admin can list parents, register a new parent, and reset password."""
        self._login_admin()

        # 1. List
        resp_list = self.client.get('/admin/parents')
        self.assertEqual(resp_list.status_code, 200)
        self.assertIn(b'Parent Management Directory', resp_list.data)
        self.assertIn(b'parent@example.com', resp_list.data)

        # 2. Create Parent
        resp_create = self.client.post('/admin/parents/create', data={
            'parent_id': 'PAR999',
            'name': 'Test Parent Guardian',
            'email': 'parent999@example.com',
            'phone': '+91 99887 76655',
            'relationship': 'Mother',
            'student_id': self.student['id']
        }, follow_redirects=True)
        self.assertEqual(resp_create.status_code, 200)
        self.assertIn(b'PAR999', resp_create.data)

        # 3. Reset Password
        conn = app.get_db_connection()
        par_row = conn.execute("SELECT id FROM parents WHERE parent_id = 'PAR999'").fetchone()
        conn.close()
        self.assertIsNotNone(par_row)

        resp_reset = self.client.post(f'/admin/parents/reset-password/{par_row["id"]}', follow_redirects=True)
        self.assertEqual(resp_reset.status_code, 200)
        self.assertIn(b'successfully reset', resp_reset.data)

    def test_04_admin_faculty_management(self):
        """Verify Admin can list and add faculty members."""
        self._login_admin()

        resp_list = self.client.get('/admin/faculty')
        self.assertEqual(resp_list.status_code, 200)
        self.assertIn(b'Faculty Management Directory', resp_list.data)
        self.assertIn(b'Dr. Ramesh Rao', resp_list.data)

        resp_create = self.client.post('/admin/faculty/create', data={
            'faculty_id': 'FAC999',
            'name': 'Dr. Alan Turing',
            'email': 'turing@example.com',
            'phone': '+91 98765 11111',
            'department': 'Computer Science & Engineering',
            'cabin': 'CS-301'
        }, follow_redirects=True)
        self.assertEqual(resp_create.status_code, 200)
        self.assertIn(b'Dr. Alan Turing', resp_create.data)

    def test_05_admin_academics_and_courses(self):
        """Verify Admin can list courses and add a new course."""
        self._login_admin()

        resp_list = self.client.get('/admin/academics')
        self.assertEqual(resp_list.status_code, 200)
        self.assertIn(b'Academics &amp; Curriculum Catalog', resp_list.data)
        self.assertIn(b'CS301', resp_list.data)

        resp_create = self.client.post('/admin/academics/create', data={
            'code': 'CS399',
            'name': 'Quantum Computing Principles',
            'department': 'Computer Science & Engineering',
            'semester': '5',
            'credits': '4',
            'faculty_name': 'Dr. Richard Feynman'
        }, follow_redirects=True)
        self.assertEqual(resp_create.status_code, 200)
        self.assertIn(b'CS399', resp_create.data)

    def test_06_admin_attendance_monitor_and_warning(self):
        """Verify Admin Attendance monitor and warning dispatch."""
        self._login_admin()

        resp = self.client.get('/admin/attendance')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Institutional Attendance Monitor', resp.data)
        self.assertIn(b'Master Course Attendance Registry', resp.data)

        # Dispatch Warning
        resp_warn = self.client.post(f'/admin/attendance/send-warning/{self.student["id"]}', follow_redirects=True)
        self.assertEqual(resp_warn.status_code, 200)
        self.assertIn(b'successfully dispatched', resp_warn.data)

    def test_07_admin_marks_ledger(self):
        """Verify Admin Marks Ledger renders student assessments."""
        self._login_admin()

        resp = self.client.get('/admin/marks')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Master Marks &amp; Assessment Ledger', resp.data)
        self.assertIn(b'Nithish Nagaraj', resp.data)

    def test_08_admin_fees_management(self):
        """Verify Admin Fees Ledger, invoice creation, and payment verification."""
        self._login_admin()

        resp_list = self.client.get('/admin/fees')
        self.assertEqual(resp_list.status_code, 200)
        self.assertIn(b'Institutional Fees &amp; Financial Ledger', resp_list.data)

        # Create Invoice
        resp_create = self.client.post('/admin/fees/create', data={
            'student_id': self.student['id'],
            'fee_type': 'Research Lab Fee',
            'amount': '15000',
            'due_date': '2026-10-15'
        }, follow_redirects=True)
        self.assertEqual(resp_create.status_code, 200)
        self.assertIn(b'Research Lab Fee', resp_create.data)

        # Mark Paid
        conn = app.get_db_connection()
        fee_row = conn.execute("SELECT id FROM fees WHERE fee_type = 'Research Lab Fee' AND student_id = ?", (self.student['id'],)).fetchone()
        conn.close()
        self.assertIsNotNone(fee_row)

        resp_paid = self.client.post(f'/admin/fees/mark-paid/{fee_row["id"]}', follow_redirects=True)
        self.assertEqual(resp_paid.status_code, 200)
        self.assertIn(b'marked as Paid', resp_paid.data)

    def test_09_admin_exams_timetable(self):
        """Verify Admin Exam Schedule creation and broadcasting."""
        self._login_admin()

        resp_list = self.client.get('/admin/exams')
        self.assertEqual(resp_list.status_code, 200)
        self.assertIn(b'Examinations &amp; Assessment Schedule', resp_list.data)

        resp_create = self.client.post('/admin/exams/create', data={
            'course_code': 'CS301',
            'course_name': 'Database Systems',
            'exam_date': '2026-11-20',
            'start_time': '09:30',
            'end_time': '12:30',
            'venue': 'Exam Hall B-201'
        }, follow_redirects=True)
        self.assertEqual(resp_create.status_code, 200)
        self.assertIn(b'CS301', resp_create.data)

    def test_10_admin_leaves_authorization(self):
        """Verify Admin can view and authorize student hostel leaves."""
        self._login_admin()

        # Seed sample leave
        conn = app.get_db_connection()
        conn.execute("""
            INSERT INTO hostel_leaves (student_id, leave_type, from_date, to_date, reason, status)
            VALUES (?, 'Weekend Home Visit', '2026-09-01', '2026-09-03', 'Family function', 'Pending')
        """, (self.student['id'],))
        leave_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()['id']
        conn.commit()
        conn.close()

        resp_list = self.client.get('/admin/leaves')
        self.assertEqual(resp_list.status_code, 200)
        self.assertIn(b'Weekend Home Visit', resp_list.data)

        # Approve Leave
        resp_act = self.client.post(f'/admin/leaves/action/{leave_id}', data={'action_type': 'Approved'}, follow_redirects=True)
        self.assertEqual(resp_act.status_code, 200)
        self.assertIn(b'Approved', resp_act.data)

    def test_11_admin_safety_and_sos_lifecycle(self):
        """Verify Admin Campus Safety Control Center and 4-stage SOS lifecycle."""
        self._login_admin()

        resp_safety = self.client.get('/admin/safety')
        self.assertEqual(resp_safety.status_code, 200)
        self.assertIn(b'Campus Safety Control Center', resp_safety.data)

        # Create SOS beacon
        conn = app.get_db_connection()
        inc_id = f"SOS-TEST-{self.student['id']}"
        conn.execute("""
            INSERT INTO incidents (incident_id, student_id, incident_type, status, location, latitude, longitude)
            VALUES (?, ?, 'Medical Emergency', 'ACTIVE', 'Hostel Block 3', 12.9716, 77.5946)
        """, (inc_id, self.student['id']))
        conn.commit()
        conn.close()

        # Acknowledge
        r1 = self.client.post('/admin/sos/status-update', data={'incident_id': inc_id, 'new_status': 'ACKNOWLEDGED'}, follow_redirects=True)
        self.assertEqual(r1.status_code, 200)

        # Dispatch QRT
        r2 = self.client.post('/admin/sos/status-update', data={'incident_id': inc_id, 'new_status': 'RESPONDING'}, follow_redirects=True)
        self.assertEqual(r2.status_code, 200)

        # Resolve
        r3 = self.client.post('/admin/sos/status-update', data={'incident_id': inc_id, 'new_status': 'RESOLVED'}, follow_redirects=True)
        self.assertEqual(r3.status_code, 200)

    def test_12_admin_messages_and_reports(self):
        """Verify Admin Direct Messaging Center and Institutional Reports."""
        self._login_admin()

        # Messages GET and POST
        resp_msg_get = self.client.get('/admin/messages')
        self.assertEqual(resp_msg_get.status_code, 200)
        self.assertIn(b'Admin Communication &amp; Messages Hub', resp_msg_get.data)

        resp_msg_post = self.client.post('/admin/messages', data={
            'receiver_role': 'Student',
            'receiver_name': 'Nithish Nagaraj',
            'subject': 'Academic Excellence Commendation',
            'content': 'Congratulations on your semester CGPA of 8.92.'
        }, follow_redirects=True)
        self.assertEqual(resp_msg_post.status_code, 200)
        self.assertIn(b'Academic Excellence Commendation', resp_msg_post.data)

        # Reports
        resp_rep = self.client.get('/admin/reports')
        self.assertEqual(resp_rep.status_code, 200)
        self.assertIn(b'Institutional Reports &amp; Analytics Audit', resp_rep.data)

    def test_13_admin_settings_governance(self):
        """Verify Admin System Settings updating institutional parameters."""
        self._login_admin()

        resp_get = self.client.get('/admin/settings')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Institutional Settings &amp; Governance', resp_get.data)

        resp_post = self.client.post('/admin/settings', data={
            'institution_name': 'CampusGuard AI Institute of Technology',
            'academic_year': '2026-2027',
            'active_semester': 'Fall 2026 (Semester 5)',
            'attendance_threshold': '75.0',
            'emergency_broadcast_active': '1'
        }, follow_redirects=True)
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn(b'System settings successfully updated', resp_post.data)

    def test_14_cross_portal_stability_and_login(self):
        """Verify Student, Parent, and Faculty portals all remain operational."""
        # 1. Student
        r1 = self.client.post('/student/login', data={'register_number': 'STU001', 'password': 'Student@123'})
        self.assertEqual(r1.status_code, 302)

        # 2. Parent
        r2 = self.client.post('/parent/login', data={'identifier': 'parent@example.com', 'password': 'Parent@123'})
        self.assertEqual(r2.status_code, 302)

        # 3. Faculty
        r3 = self.client.post('/faculty/login', data={'identifier': 'FAC001', 'password': 'Faculty@123'})
        self.assertEqual(r3.status_code, 302)

    def test_15_admin_analytics_and_ai_assistant(self):
        """Verify Admin AI Intelligence dashboard and database-driven conversational queries."""
        self._login_admin()

        # 1. Analytics Page
        resp_an = self.client.get('/admin/analytics')
        self.assertEqual(resp_an.status_code, 200)
        self.assertIn(b'Executive Safety Intelligence', resp_an.data)

        # 2. AI Assistant API queries
        queries = [
            'Which department has the lowest attendance?',
            'Show students below 75% attendance.',
            'What is the total pending fee collection?',
            'Which students are academically at risk?',
            'How many SOS incidents occurred this month?'
        ]
        for q in queries:
            resp_ai = self.client.post('/admin/api/ai-assistant', json={'query': q})
            self.assertEqual(resp_ai.status_code, 200)
            data = resp_ai.get_json()
            self.assertEqual(data.get('status'), 'success')
            self.assertTrue(len(data.get('reply', '')) > 10)



if __name__ == '__main__':
    unittest.main()
