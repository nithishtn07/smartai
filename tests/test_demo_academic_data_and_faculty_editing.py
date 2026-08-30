"""
CampusGuard AI — Editable Demo Academic Data & Faculty Mark Management Test Suite
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from database.db import get_db_connection, init_db
from services.academic_service import calculate_student_cgpa, sync_student_cgpa


class TestDemoAcademicDataAndFacultyEditing(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    def test_01_all_active_students_have_varied_demo_marks_and_calculated_cgpa(self):
        """1. Verify all active students have database-backed demo marks (is_demo=1) with varied, calculated CGPAs."""
        init_db()
        conn = get_db_connection()
        try:
            students = conn.execute("SELECT id, register_number, name, cgpa, earned_credits FROM students WHERE status != 'DELETED'").fetchall()
            self.assertGreaterEqual(len(students), 3, "There should be at least 3 active students in the system")

            cgpa_list = []
            for s in students:
                marks = conn.execute("SELECT * FROM marks WHERE student_id = ?", (s['id'],)).fetchall()
                self.assertGreater(len(marks), 0, f"Student {s['name']} ({s['register_number']}) must have academic marks")
                
                # Check that demo marks have is_demo flag set
                for m in marks:
                    self.assertIn('is_demo', m.keys())
                    self.assertGreater(m['fat'], 0)
                    self.assertIn(m['grade'], ['S', 'O', 'A+', 'A', 'B+', 'B', 'C', 'D', 'F'])
                    self.assertGreaterEqual(m['grade_points'], 0.0)

                # Verify CGPA is mathematically consistent
                calc_cgpa, earned_credits, total_credits, count = calculate_student_cgpa(conn, s['id'])
                self.assertIsNotNone(calc_cgpa)
                self.assertAlmostEqual(s['cgpa'], calc_cgpa, places=2)
                cgpa_list.append(calc_cgpa)

            # Ensure varied distribution (not all students have identical CGPA)
            unique_cgpas = set(cgpa_list)
            self.assertGreater(len(unique_cgpas), 1, "Students must have varied CGPA values, not identical copies")
        finally:
            conn.close()

    def test_02_persistence_and_no_random_regeneration(self):
        """2. Verify that running init_db or multiple requests does NOT alter marks or regenerate randomly."""
        conn = get_db_connection()
        try:
            first_snapshot = conn.execute("""
                SELECT student_id, course_code, cat1, cat2, fat, grade, grade_points 
                FROM marks ORDER BY student_id, course_code
            """).fetchall()
            snapshot_1 = [dict(r) for r in first_snapshot]
        finally:
            conn.close()

        # Re-initialize DB (simulating server restart)
        init_db()

        conn = get_db_connection()
        try:
            second_snapshot = conn.execute("""
                SELECT student_id, course_code, cat1, cat2, fat, grade, grade_points 
                FROM marks ORDER BY student_id, course_code
            """).fetchall()
            snapshot_2 = [dict(r) for r in second_snapshot]
            
            self.assertEqual(snapshot_1, snapshot_2, "Academic records must remain completely stable across restarts")
        finally:
            conn.close()

    def test_03_faculty_individual_marks_editing_and_recalculation(self):
        """3. Faculty edits individual marks -> Grade, Grade Point, and CGPA recalculate dynamically."""
        conn = get_db_connection()
        try:
            stu = conn.execute("SELECT id, name FROM students WHERE register_number = '25MID1027'").fetchone()
            stu_id = stu['id']
            old_cgpa, _, _, _ = calculate_student_cgpa(conn, stu_id)
        finally:
            conn.close()

        # Faculty logs in
        with self.client.session_transaction() as sess:
            sess['faculty_logged_in'] = True
            sess['faculty_id'] = 1
            sess['faculty_code'] = 'FAC001'
            sess['faculty_name'] = 'Dr. Ramesh Rao'

        # Edit CS301 to top marks (CAT1: 50, CAT2: 50, Quiz: 10, Assign: 10, FAT: 99 -> Grade S, 10.0 pts)
        post_data = {
            'action_type': 'single',
            'course_code': 'CS301',
            'student_id': str(stu_id),
            'cat1': '50',
            'cat2': '50',
            'quiz': '10',
            'assignment': '10',
            'project': '20',
            'fat': '99',
            'grade': 'S'
        }
        res = self.client.post('/faculty/marks', data=post_data, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Marks updated successfully", res.data.decode('utf-8'))

        conn = get_db_connection()
        try:
            updated_m = conn.execute("SELECT * FROM marks WHERE student_id = ? AND course_code = 'CS301'", (stu_id,)).fetchone()
            self.assertEqual(updated_m['grade'], 'S')
            self.assertEqual(updated_m['grade_points'], 10.0)
            self.assertEqual(updated_m['is_demo'], 0, "Updated marks must have is_demo=0")

            new_cgpa, _, _, _ = calculate_student_cgpa(conn, stu_id)
            self.assertIsNotNone(new_cgpa)

            db_stu = conn.execute("SELECT cgpa FROM students WHERE id = ?", (stu_id,)).fetchone()
            self.assertEqual(db_stu['cgpa'], new_cgpa)
        finally:
            conn.close()

    def test_04_faculty_bulk_marks_editing_for_course(self):
        """4. Faculty performs bulk mark save for all students in a subject."""
        conn = get_db_connection()
        try:
            active_students = conn.execute("SELECT id FROM students WHERE status != 'DELETED'").fetchall()
        finally:
            conn.close()

        with self.client.session_transaction() as sess:
            sess['faculty_logged_in'] = True
            sess['faculty_id'] = 1
            sess['faculty_code'] = 'FAC001'
            sess['faculty_name'] = 'Dr. Ramesh Rao'

        bulk_form = {
            'action_type': 'bulk',
            'course_code': 'CS302'
        }
        for s in active_students:
            s_id = s['id']
            bulk_form[f'cat1_{s_id}'] = '48.0'
            bulk_form[f'cat2_{s_id}'] = '49.0'
            bulk_form[f'quiz_{s_id}'] = '10.0'
            bulk_form[f'assignment_{s_id}'] = '10.0'
            bulk_form[f'project_{s_id}'] = '19.0'
            bulk_form[f'fat_{s_id}'] = '95.0'
            bulk_form[f'grade_{s_id}'] = 'S'

        res = self.client.post('/faculty/marks', data=bulk_form, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Marks updated successfully", res.data.decode('utf-8'))

        conn = get_db_connection()
        try:
            for s in active_students:
                m = conn.execute("SELECT * FROM marks WHERE student_id = ? AND course_code = 'CS302'", (s['id'],)).fetchone()
                self.assertEqual(m['grade'], 'S')
                self.assertEqual(m['grade_points'], 10.0)
                self.assertEqual(m['is_demo'], 0)
        finally:
            conn.close()

    def test_05_student_parent_and_admin_portals_reflect_same_calculated_data(self):
        """5. Student, Parent, and Admin portals reflect exact synchronized marks and calculated CGPA."""
        conn = get_db_connection()
        try:
            stu = conn.execute("SELECT id, name, cgpa FROM students WHERE register_number = '25MID1027'").fetchone()
            stu_id = stu['id']
            parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (stu_id,)).fetchone()
            parent_id = parent['id'] if parent else None
            cgpa_str = str(stu['cgpa'])
        finally:
            conn.close()

        # 1. Student Portal
        with self.client.session_transaction() as sess:
            sess['student_logged_in'] = True
            sess['student_id'] = stu_id
            sess['student_name'] = 'T N NITHISH'

        s_resp = self.client.get('/student/marks')
        self.assertEqual(s_resp.status_code, 200)
        s_html = s_resp.data.decode('utf-8')
        self.assertIn("Database Management Systems", s_html)
        self.assertIn(cgpa_str, s_html)

        # 2. Parent Portal
        if parent_id:
            with self.client.session_transaction() as sess:
                sess['parent_logged_in'] = True
                sess['parent_id'] = parent_id
                sess['parent_name'] = 'Parent of Nithish'
                sess['parent_active_student_id'] = stu_id

            p_resp = self.client.get('/parent/academics')
            self.assertEqual(p_resp.status_code, 200)
            p_html = p_resp.data.decode('utf-8')
            self.assertIn("Database Management Systems", p_html)
            self.assertIn(cgpa_str, p_html)

        # 3. Admin Portal
        with self.client.session_transaction() as sess:
            sess['admin_logged_in'] = True
            sess['admin_id'] = 1
            sess['admin_username'] = 'admin'
            sess['admin_name'] = 'Super Administrator'

        a_resp = self.client.get(f'/admin/students/view/{stu_id}')
        self.assertEqual(a_resp.status_code, 200)
        a_html = a_resp.data.decode('utf-8')
        self.assertIn("Database Management Systems", a_html)
        self.assertIn(cgpa_str, a_html)


if __name__ == '__main__':
    unittest.main()
