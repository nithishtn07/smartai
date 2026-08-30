"""
CampusGuard AI — Single Faculty Architecture & Cross-Portal Workflow Test Suite
Validates the complete workflow:
ONE Faculty (Dr. Ramesh Rao) -> All Subjects -> All Students -> Connected Student & Parent Portals -> AI Assistant -> Admin Management.
"""

import unittest
import datetime
from app import app
from database.db import get_db_connection, init_db
from werkzeug.security import generate_password_hash


class TestSingleFacultyWorkflow(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-campusguard-key'
        self.client = self.app.test_client()

        # Ensure database is clean and seeded
        init_db()

    def _login_admin(self):
        with self.client.session_transaction() as sess:
            sess.clear()
            sess['admin_logged_in'] = True
            sess['admin_id'] = 1
            sess['admin_username'] = 'admin'
            sess['admin_role'] = 'SuperAdmin'

    def _login_faculty(self):
        conn = get_db_connection()
        try:
            fac = conn.execute("SELECT * FROM faculties WHERE email = 'faculty@example.com'").fetchone()
            self.assertIsNotNone(fac, "Primary faculty account FAC001 must exist")
            with self.client.session_transaction() as sess:
                sess.clear()
                sess['faculty_logged_in'] = True
                sess['faculty_id'] = fac['id']
                sess['faculty_name'] = fac['name']
                sess['faculty_email'] = fac['email']
                sess['faculty_department'] = fac['department']
                sess['role'] = 'faculty'
            return fac
        finally:
            conn.close()

    def _login_student(self, reg_num='25MID1027'):
        conn = get_db_connection()
        try:
            stu = conn.execute("SELECT * FROM students WHERE register_number = ?", (reg_num,)).fetchone()
            self.assertIsNotNone(stu, f"Student {reg_num} must exist")
            with self.client.session_transaction() as sess:
                sess.clear()
                sess['student_logged_in'] = True
                sess['student_id'] = stu['id']
                sess['student_name'] = stu['name']
                sess['register_number'] = stu['register_number']
                sess['student_dept'] = stu['department']
                sess['role'] = 'student'
            return stu
        finally:
            conn.close()

    def _login_parent(self):
        conn = get_db_connection()
        try:
            par = conn.execute("SELECT * FROM parents WHERE parent_id = 'PAR268C6'").fetchone()
            self.assertIsNotNone(par, "Parent PAR268C6 must exist")
            with self.client.session_transaction() as sess:
                sess.clear()
                sess['parent_logged_in'] = True
                sess['parent_id'] = par['id']
                sess['parent_name'] = par['name']
                sess['parent_code'] = par['parent_id']
                sess['linked_student_id'] = par['student_id']
                sess['role'] = 'parent'
            return par
        finally:
            conn.close()

    def test_01_single_faculty_dashboard_and_all_subjects(self):
        """1. Faculty Dashboard displays real single faculty info and all subjects."""
        fac = self._login_faculty()
        res = self.client.get('/faculty/dashboard')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn("Dr. Ramesh Rao", html)
        self.assertIn("CS301", html)

    def test_02_faculty_sees_all_valid_students(self):
        """2. Single faculty member can view all valid registered students."""
        self._login_faculty()
        res = self.client.get('/faculty/students')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        # All valid students should be displayed
        self.assertIn("HARSHIKA", html)
        self.assertIn("T  N NITHISH", html)

    def test_03_attendance_marking_and_multi_portal_sync(self):
        """3. Faculty marks attendance for DBMS -> Stored in DB -> Synced to Student & Parent portals."""
        self._login_faculty()
        conn = get_db_connection()
        try:
            stu = conn.execute("SELECT id FROM students WHERE register_number = '25MID1027'").fetchone()
            self.assertIsNotNone(stu)
            stu_id = stu['id']
        finally:
            conn.close()

        test_date = datetime.date.today().isoformat()
        res = self.client.post('/faculty/attendance', data={
            'course_code': 'CS301',
            'date': test_date,
            'topic': 'Relational Algebra & Normalization',
            'action_type': 'batch_roll_call',
            f'status_{stu_id}': 'Present'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify in DB
        conn = get_db_connection()
        try:
            log = conn.execute("SELECT * FROM attendance_logs WHERE student_id = ? AND course_code = 'CS301' AND date = ?", (stu_id, test_date)).fetchone()
            self.assertIsNotNone(log)
            self.assertEqual(log['status'], 'Present')

            att = conn.execute("SELECT * FROM attendance WHERE student_id = ? AND subject_code = 'CS301'", (stu_id,)).fetchone()
            self.assertIsNotNone(att)
            self.assertGreaterEqual(att['attendance_pct'], 100.0)
        finally:
            conn.close()

        # Check Student Portal Attendance View
        self._login_student('25MID1027')
        stu_res = self.client.get('/student/attendance')
        self.assertEqual(stu_res.status_code, 200)
        stu_html = stu_res.data.decode('utf-8')
        self.assertIn("CS301", stu_html)

        # Check Parent Portal Child Attendance View
        self._login_parent()
        par_res = self.client.get('/parent/attendance')
        self.assertEqual(par_res.status_code, 200)
        par_html = par_res.data.decode('utf-8')
        self.assertIn("CS301", par_html)

    def test_04_assignment_lifecycle_and_grading(self):
        """4. Faculty creates assignment -> Student submits -> Faculty grades with feedback."""
        self._login_faculty()
        due_date = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
        res = self.client.post('/faculty/assignments', data={
            'course_code': 'CS302',
            'title': 'Operating Systems Process Scheduling Simulator',
            'description': 'Implement Round Robin and Priority Scheduling in Python or C++.',
            'due_date': due_date,
            'max_marks': '50'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        conn = get_db_connection()
        try:
            assign = conn.execute("SELECT * FROM assignments WHERE title LIKE '%Process Scheduling Simulator%'").fetchone()
            self.assertIsNotNone(assign)
            assign_id = assign['id']
            stu = conn.execute("SELECT id FROM students WHERE register_number = '25MID1027'").fetchone()
            stu_id = stu['id']

            # Student submits
            conn.execute("""
                INSERT INTO student_submissions (assignment_id, student_id, submission_text, status, submitted_at)
                VALUES (?, ?, 'https://github.com/nithish/os-scheduler-simulation', 'Submitted', CURRENT_TIMESTAMP)
            """, (assign_id, stu_id))
            conn.commit()
        finally:
            conn.close()

        # Faculty reviews submissions
        self._login_faculty()
        sub_res = self.client.get(f'/faculty/assignments/submissions/{assign_id}')
        self.assertEqual(sub_res.status_code, 200)
        self.assertIn("T  N NITHISH", sub_res.data.decode('utf-8'))

        # Faculty evaluates submission
        eval_res = self.client.post(f'/faculty/assignments/evaluate/{assign_id}', data={
            'student_id': str(stu_id),
            'marks_obtained': '48.5',
            'feedback': 'Excellent implementation with comprehensive Gantt charts!'
        }, follow_redirects=True)
        self.assertEqual(eval_res.status_code, 200)

        # Verify evaluation in DB
        conn = get_db_connection()
        try:
            sub = conn.execute("SELECT * FROM student_submissions WHERE assignment_id = ? AND student_id = ?", (assign_id, stu_id)).fetchone()
            self.assertEqual(sub['status'], 'Graded')
            self.assertEqual(sub['marks_obtained'], 48.5)
            self.assertIn("Gantt charts", sub['feedback'])
        finally:
            conn.close()

    def test_05_faculty_ai_assistant_real_database_queries(self):
        """5. Faculty AI Assistant answers queries using real DB data without fake values."""
        self._login_faculty()

        # Query 1: Low attendance
        res1 = self.client.post('/faculty/api/ai-insights', json={'query': 'Which students have attendance below the threshold?'})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.get_json()
        self.assertIn('reply', data1)

        # Query 2: Specific subject attendance
        res2 = self.client.post('/faculty/api/ai-insights', json={'query': 'Show DBMS attendance.'})
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertIn('CS301', data2['reply'])

        # Query 3: Missing submissions
        res3 = self.client.post('/faculty/api/ai-insights', json={'query': 'Who hasn\'t submitted assignments?'})
        self.assertEqual(res3.status_code, 200)
        data3 = res3.get_json()
        self.assertTrue(len(data3['reply']) > 10)

    def test_06_admin_faculty_management_and_rbac_isolation(self):
        """6. Admin can manage single faculty account, while faculty cannot access Admin endpoints."""
        self._login_admin()
        res = self.client.get('/admin/faculties')
        self.assertEqual(res.status_code, 200)
        self.assertIn("Dr. Ramesh Rao", res.data.decode('utf-8'))

        # Faculty cannot access Admin dashboard
        self._login_faculty()
        admin_res = self.client.get('/admin/dashboard')
        self.assertEqual(admin_res.status_code, 302)
        self.assertIn('/admin/login', admin_res.headers.get('Location', ''))


if __name__ == '__main__':
    unittest.main()
