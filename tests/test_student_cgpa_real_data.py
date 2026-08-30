"""
CampusGuard AI — Student CGPA Real Database Calculation & Multi-Portal Test Suite
"""

import unittest
from app import app
from database.db import get_db_connection
from services.academic_service import (
    calculate_grade_point,
    calculate_student_cgpa,
    sync_student_cgpa,
    get_student_academic_profile
)
from models.examination import MarksModel


class TestStudentCGPARealData(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    def test_01_grade_point_mapping_and_formulas(self):
        """Test 1: Grade point calculation mappings."""
        self.assertEqual(calculate_grade_point('S'), 10.0)
        self.assertEqual(calculate_grade_point('O'), 10.0)
        self.assertEqual(calculate_grade_point('A+'), 9.0)
        self.assertEqual(calculate_grade_point('A'), 8.0)
        self.assertEqual(calculate_grade_point('B+'), 7.0)
        self.assertEqual(calculate_grade_point('B'), 6.0)
        self.assertEqual(calculate_grade_point('C'), 5.0)
        self.assertEqual(calculate_grade_point('D'), 4.0)
        self.assertEqual(calculate_grade_point('F'), 0.0)
        self.assertEqual(calculate_grade_point('FAIL'), 0.0)

    def test_02_student_with_no_marks_shows_not_available(self):
        """Test 2: Student without marks must show 'Not available' / None instead of 0 or fake CGPA."""
        conn = get_db_connection()
        try:
            # Pick or insert student with NO marks
            stu = conn.execute("SELECT id, name, email FROM students WHERE register_number = '25MID1082'").fetchone()
            if not stu:
                cursor = conn.execute("""
                    INSERT INTO students (name, register_number, email, password_hash, department, year, semester, status)
                    VALUES ('Test Empty Student', 'STU_EMPTY_01', 'empty@example.com', 'hash', 'Computer Science', 1, 1, 'ACTIVE')
                """)
                stu_id = cursor.lastrowid
                conn.commit()
            else:
                stu_id = stu['id']
                conn.execute("DELETE FROM marks WHERE student_id = ?", (stu_id,))
                conn.commit()

            cgpa, earned_credits, total_credits, count = calculate_student_cgpa(conn, stu_id)
            self.assertIsNone(cgpa)
            self.assertEqual(earned_credits, 0)
            self.assertEqual(count, 0)

            profile = get_student_academic_profile(conn, stu_id)
            self.assertIsNone(profile['cgpa'])
            self.assertEqual(profile['cgpa_display'], "Not available")
        finally:
            conn.close()

        # Check Student Portal Dashboard
        with self.client.session_transaction() as sess:
            sess['student_logged_in'] = True
            sess['student_id'] = stu_id
            sess['student_name'] = 'Test Empty Student'

        resp_dash = self.client.get('/student/dashboard')
        self.assertEqual(resp_dash.status_code, 200)
        html = resp_dash.data.decode('utf-8')
        self.assertIn("N/A", html)
        self.assertNotIn("0.0 / 10.0", html)

        resp_marks = self.client.get('/student/marks')
        self.assertEqual(resp_marks.status_code, 200)
        html_marks = resp_marks.data.decode('utf-8')
        self.assertIn("Academic records not available yet", html_marks)

    def test_03_student_with_real_marks_cgpa_calculation(self):
        """Test 3: Exact CGPA calculation Σ(Grade Point * Credits) / Σ(Credits)."""
        conn = get_db_connection()
        try:
            stu = conn.execute("SELECT id FROM students WHERE register_number = '25MID1027'").fetchone()
            stu_id = stu['id']
            # Clean existing marks for test isolation
            conn.execute("DELETE FROM marks WHERE student_id = ?", (stu_id,))
            conn.commit()
        finally:
            conn.close()
            
        # Add Course 1: CS301 (4 credits), Grade S (10.0) -> 40 pts
        # Add Course 2: CS302 (4 credits), Grade A (8.0)  -> 32 pts
        # Add Course 3: CS306 (2 credits), Grade A+ (9.0) -> 18 pts
        # Total weighted = 40 + 32 + 18 = 90
        # Total credits  = 4 + 4 + 2 = 10
        # Expected CGPA  = 90 / 10 = 9.00
        MarksModel.upsert_marks(stu_id, 'CS301', 'Database Management Systems', fat=95, grade='S', grade_points=10.0)
        MarksModel.upsert_marks(stu_id, 'CS302', 'Operating Systems & Architecture', fat=85, grade='A', grade_points=8.0)
        MarksModel.upsert_marks(stu_id, 'CS306', 'Campus Cyber Safety & Ethics', fat=90, grade='A+', grade_points=9.0)

        conn = get_db_connection()
        try:
            cgpa, earned_credits, total_credits, count = calculate_student_cgpa(conn, stu_id)
            self.assertEqual(cgpa, 9.00)
            self.assertEqual(earned_credits, 10)
            self.assertEqual(total_credits, 10)
            self.assertEqual(count, 3)

            # Sync in DB and verify students table update
            sync_student_cgpa(conn, stu_id)
            conn.commit()
            
            db_stu = conn.execute("SELECT cgpa, sgpa, earned_credits FROM students WHERE id = ?", (stu_id,)).fetchone()
            self.assertEqual(db_stu['cgpa'], 9.0)
            self.assertEqual(db_stu['earned_credits'], 10)
        finally:
            conn.close()

    def test_04_cross_portal_synchronized_cgpa(self):
        """Test 4: Student, Parent, Faculty, and Admin portals all show the exact synchronized CGPA."""
        conn = get_db_connection()
        try:
            stu = conn.execute("SELECT id, name FROM students WHERE register_number = '25MID1027'").fetchone()
            stu_id = stu['id']
            parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (stu_id,)).fetchone()
            parent_id = parent['id'] if parent else None
        finally:
            conn.close()

        # 1. Student Portal
        with self.client.session_transaction() as sess:
            sess['student_logged_in'] = True
            sess['student_id'] = stu_id
            sess['student_name'] = 'T N NITHISH'

        resp = self.client.get('/student/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn("9.0", resp.data.decode('utf-8'))

        # 2. Parent Portal
        if parent_id:
            with self.client.session_transaction() as sess:
                sess['parent_logged_in'] = True
                sess['parent_id'] = parent_id
                sess['parent_name'] = 'Parent of Nithish'
                sess['parent_active_student_id'] = stu_id

            p_resp = self.client.get('/parent/dashboard')
            self.assertEqual(p_resp.status_code, 200)
            self.assertIn("9.0", p_resp.data.decode('utf-8'))

        # 3. Faculty Portal
        with self.client.session_transaction() as sess:
            sess['faculty_logged_in'] = True
            sess['faculty_id'] = 1
            sess['faculty_code'] = 'FAC001'
            sess['faculty_name'] = 'Dr. Ramesh Rao'

        f_resp = self.client.get(f'/faculty/students/view/{stu_id}')
        self.assertEqual(f_resp.status_code, 200)
        self.assertIn("9.0", f_resp.data.decode('utf-8'))

        # 4. Admin Portal
        with self.client.session_transaction() as sess:
            sess['admin_logged_in'] = True
            sess['admin_id'] = 1
            sess['admin_username'] = 'admin'
            sess['admin_name'] = 'Super Administrator'

        a_resp = self.client.get(f'/admin/students/view/{stu_id}')
        self.assertEqual(a_resp.status_code, 200)
        self.assertIn("9.0", a_resp.data.decode('utf-8'))

    def test_05_faculty_marks_entry_updates_cgpa_dynamically(self):
        """Test 5: Faculty enters/edits marks -> Student CGPA updates in real-time."""
        conn = get_db_connection()
        try:
            stu = conn.execute("SELECT id FROM students WHERE register_number = '25MID1027'").fetchone()
            stu_id = stu['id']
        finally:
            conn.close()

        # Faculty updates CS302 from Grade A (8.0) to Grade S (10.0)
        with self.client.session_transaction() as sess:
            sess['faculty_logged_in'] = True
            sess['faculty_id'] = 1
            sess['faculty_code'] = 'FAC001'
            sess['faculty_name'] = 'Dr. Ramesh Rao'

        post_data = {
            'student_id': str(stu_id),
            'course_code': 'CS302',
            'cat1': '50',
            'cat2': '50',
            'quiz': '10',
            'assignment': '10',
            'project': '0',
            'fat': '98',
            'grade': 'S'
        }
        res = self.client.post('/faculty/marks', data=post_data, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # CS301 (4 cr, S=10) -> 40
        # CS302 (4 cr, S=10) -> 40
        # CS306 (2 cr, A+=9) -> 18
        # Weighted = 98 / 10 = 9.80
        conn = get_db_connection()
        try:
            cgpa, earned_credits, _, _ = calculate_student_cgpa(conn, stu_id)
            self.assertEqual(cgpa, 9.80)
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
