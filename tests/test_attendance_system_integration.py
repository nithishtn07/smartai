"""
CampusGuard AI — Attendance System Integration & Cross-Portal Synchronization Test Suite
Validates the complete 20-point Attendance Architecture:
Faculty Marking -> Atomic Transaction -> Attendance Logs (Single Source of Truth) -> Aggregate Recalculation
-> Student Portal Sync -> Parent Portal Sync -> Admin Monitoring & Correction -> Duplicate Prevention -> Multi-Day Math.
"""

import unittest
import datetime
from app import app
from database.db import get_db_connection, init_db
from models.attendance import AttendanceModel


class TestAttendanceSystemIntegration(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-campusguard-key'
        self.client = self.app.test_client()
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

    def _login_parent(self, parent_id='PAR268C6'):
        conn = get_db_connection()
        try:
            par = conn.execute("SELECT * FROM parents WHERE parent_id = ?", (parent_id,)).fetchone()
            self.assertIsNotNone(par, f"Parent {parent_id} must exist")
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

    def test_01_faculty_marks_attendance_and_database_updates(self):
        """Test 1: Faculty marks Student A (Present) and Student B (Absent) -> Database updates."""
        self._login_faculty()
        conn = get_db_connection()
        try:
            stu1 = conn.execute("SELECT id FROM students WHERE register_number = '25MID1027'").fetchone()
            stu2 = conn.execute("SELECT id FROM students WHERE register_number = 'STU004'").fetchone()
            self.assertIsNotNone(stu1)
            self.assertIsNotNone(stu2)
            stu1_id = stu1['id']
            stu2_id = stu2['id']

            conn.execute("DELETE FROM attendance_logs WHERE course_code = 'CS301'")
            conn.execute("DELETE FROM attendance WHERE subject_code = 'CS301'")
            conn.commit()
        finally:
            conn.close()

        test_date = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
        res = self.client.post('/faculty/attendance', data={
            'course_code': 'CS301',
            'date': test_date,
            'topic': 'Database Normalization',
            'action_type': 'batch_roll_call',
            f'status_{stu1_id}': 'Present',
            f'status_{stu2_id}': 'Absent'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify attendance_logs and aggregate attendance table
        conn = get_db_connection()
        try:
            log1 = conn.execute("SELECT * FROM attendance_logs WHERE student_id = ? AND course_code = 'CS301' AND date = ?", (stu1_id, test_date)).fetchone()
            self.assertIsNotNone(log1)
            self.assertEqual(log1['status'], 'Present')

            log2 = conn.execute("SELECT * FROM attendance_logs WHERE student_id = ? AND course_code = 'CS301' AND date = ?", (stu2_id, test_date)).fetchone()
            self.assertIsNotNone(log2)
            self.assertEqual(log2['status'], 'Absent')

            att1 = conn.execute("SELECT * FROM attendance WHERE student_id = ? AND subject_code = 'CS301'", (stu1_id,)).fetchone()
            self.assertIsNotNone(att1)
            self.assertEqual(att1['classes_held'], 1)
            self.assertEqual(att1['classes_attended'], 1)
            self.assertEqual(att1['attendance_pct'], 100.0)

            att2 = conn.execute("SELECT * FROM attendance WHERE student_id = ? AND subject_code = 'CS301'", (stu2_id,)).fetchone()
            self.assertIsNotNone(att2)
            self.assertEqual(att2['classes_held'], 1)
            self.assertEqual(att2['classes_attended'], 0)
            self.assertEqual(att2['attendance_pct'], 0.0)
        finally:
            conn.close()

    def test_02_student_portal_reflects_exact_attendance(self):
        """Test 2: Open Student Portal -> Verify attendance appears accurately."""
        # Seed attendance for 25MID1027
        conn = get_db_connection()
        try:
            stu = conn.execute("SELECT id FROM students WHERE register_number = '25MID1027'").fetchone()
            stu_id = stu['id']
            AttendanceModel.record_student_attendance(conn, stu_id, 'CS301', 'Database Management Systems', '2026-08-20', 'Present', 'DBMS Relational Model')
            conn.commit()
        finally:
            conn.close()

        self._login_student('25MID1027')
        res = self.client.get('/student/attendance')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn("CS301", html)
        self.assertIn("Database Management Systems", html)

    def test_03_parent_portal_reflects_child_attendance(self):
        """Test 3: Open Parent Portal -> Verify child attendance is synchronized."""
        conn = get_db_connection()
        try:
            par = conn.execute("SELECT student_id FROM parents WHERE parent_id = 'PAR268C6'").fetchone()
            stu_id = par['student_id']
            AttendanceModel.record_student_attendance(conn, stu_id, 'CS301', 'Database Management Systems', '2026-08-20', 'Present', 'DBMS Intro')
            conn.commit()
        finally:
            conn.close()

        self._login_parent('PAR268C6')
        res = self.client.get('/parent/attendance')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn("CS301", html)

    def test_04_editing_attendance_corrects_aggregate_without_duplicate(self):
        """Test 4 & 5: Faculty edits Student B from Absent -> Present for the same date. No duplicates!"""
        self._login_faculty()
        conn = get_db_connection()
        try:
            stu2 = conn.execute("SELECT id FROM students WHERE register_number = 'STU004'").fetchone()
            stu2_id = stu2['id']
        finally:
            conn.close()

        test_date = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
        
        # 1. First record as Absent
        self.client.post('/faculty/attendance', data={
            'course_code': 'CS301',
            'date': test_date,
            'topic': 'Database Normalization Initial',
            'action_type': 'batch_roll_call',
            f'status_{stu2_id}': 'Absent'
        }, follow_redirects=True)

        # 2. Edit to Present for same date
        res = self.client.post('/faculty/attendance', data={
            'course_code': 'CS301',
            'date': test_date,
            'topic': 'Database Normalization (Corrected)',
            'action_type': 'batch_roll_call',
            f'status_{stu2_id}': 'Present'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify only ONE log row exists for (stu2_id, CS301, test_date)
        conn = get_db_connection()
        try:
            logs = conn.execute("SELECT * FROM attendance_logs WHERE student_id = ? AND course_code = 'CS301' AND date = ?", (stu2_id, test_date)).fetchall()
            self.assertEqual(len(logs), 1, "Must update existing log, NOT create duplicate record")
            self.assertEqual(logs[0]['status'], 'Present')

            att2 = conn.execute("SELECT * FROM attendance WHERE student_id = ? AND subject_code = 'CS301'", (stu2_id,)).fetchone()
            self.assertEqual(att2['classes_held'], 1)
            self.assertEqual(att2['classes_attended'], 1)
            self.assertEqual(att2['classes_missed'], 0)
            self.assertEqual(att2['attendance_pct'], 100.0)
        finally:
            conn.close()

    def test_05_multi_day_percentage_mathematical_precision(self):
        """Test 6: Multi-day attendance calculation: 3 Present, 1 Absent = 75.0%."""
        self._login_faculty()
        conn = get_db_connection()
        try:
            stu = conn.execute("SELECT id FROM students WHERE register_number = '25MID1027'").fetchone()
            stu_id = stu['id']
            conn.execute("DELETE FROM attendance_logs WHERE course_code = 'CS302' AND student_id = ?", (stu_id,))
            conn.execute("DELETE FROM attendance WHERE subject_code = 'CS302' AND student_id = ?", (stu_id,))
            conn.commit()
        finally:
            conn.close()

        # Day 1: Present, Day 2: Present, Day 3: Present, Day 4: Absent
        days = [
            ((datetime.date.today() - datetime.timedelta(days=4)).isoformat(), 'Present'),
            ((datetime.date.today() - datetime.timedelta(days=3)).isoformat(), 'Present'),
            ((datetime.date.today() - datetime.timedelta(days=2)).isoformat(), 'Present'),
            ((datetime.date.today() - datetime.timedelta(days=1)).isoformat(), 'Absent'),
        ]

        for d_str, status in days:
            res = self.client.post('/faculty/attendance', data={
                'course_code': 'CS302',
                'date': d_str,
                'topic': f'Lecture on {d_str}',
                'action_type': 'batch_roll_call',
                f'status_{stu_id}': status
            }, follow_redirects=True)
            self.assertEqual(res.status_code, 200)

        conn = get_db_connection()
        try:
            att = conn.execute("SELECT * FROM attendance WHERE student_id = ? AND subject_code = 'CS302'", (stu_id,)).fetchone()
            self.assertIsNotNone(att)
            self.assertEqual(att['classes_held'], 4)
            self.assertEqual(att['classes_attended'], 3)
            self.assertEqual(att['classes_missed'], 1)
            self.assertEqual(att['attendance_pct'], 75.0)
        finally:
            conn.close()

    def test_06_future_date_validation_rejected(self):
        """Test 7: Future attendance dates must be rejected."""
        self._login_faculty()
        future_date = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
        res = self.client.post('/faculty/attendance', data={
            'course_code': 'CS301',
            'date': future_date,
            'topic': 'Future Lecture',
            'action_type': 'batch_roll_call'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("future dates", res.data.decode('utf-8'))

    def test_07_admin_portal_monitoring_and_correction(self):
        """Test 9: Admin monitors attendance, dispatches warning, and corrects records."""
        # 1. Record an Absent attendance for CS303
        conn = get_db_connection()
        try:
            stu = conn.execute("SELECT id FROM students WHERE register_number = '25MID1027'").fetchone()
            stu_id = stu['id']
            conn.execute("DELETE FROM attendance_logs WHERE course_code = 'CS303' AND student_id = ?", (stu_id,))
            conn.execute("DELETE FROM attendance WHERE subject_code = 'CS303' AND student_id = ?", (stu_id,))
            yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
            AttendanceModel.record_student_attendance(conn, stu_id, 'CS303', 'Computer Networks', yesterday, 'Absent', 'TCP/IP Model')
            conn.commit()
        finally:
            conn.close()

        # 2. Check Admin Monitor page
        self._login_admin()
        res = self.client.get('/admin/attendance')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn("Institutional Attendance Monitor", html)

        # 3. Admin corrects attendance from Absent -> Present
        corr_res = self.client.post('/admin/attendance/correct', data={
            'student_id': str(stu_id),
            'course_code': 'CS303',
            'date': yesterday,
            'status': 'Present'
        }, follow_redirects=True)
        self.assertEqual(corr_res.status_code, 200)

        # Verify new aggregate percentage is 100.0%
        conn = get_db_connection()
        try:
            att = conn.execute("SELECT * FROM attendance WHERE student_id = ? AND subject_code = 'CS303'", (stu_id,)).fetchone()
            self.assertEqual(att['classes_held'], 1)
            self.assertEqual(att['classes_attended'], 1)
            self.assertEqual(att['classes_missed'], 0)
            self.assertEqual(att['attendance_pct'], 100.0)
        finally:
            conn.close()

    def test_08_rbac_security_students_cannot_post_attendance(self):
        """Test 10: Unauthorized users (students) cannot post attendance."""
        self._login_student('25MID1027')
        res = self.client.post('/faculty/attendance', data={'course_code': 'CS301'}, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/faculty/login', res.headers.get('Location', ''))


if __name__ == '__main__':
    unittest.main()
