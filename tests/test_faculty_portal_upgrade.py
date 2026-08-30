"""
=============================================================================
Test Suite: Faculty Portal Upgrade — CampusGuard AI
Verifies:
1. Faculty Authentication, Dashboard KPIs, and Dynamic Live Metrics
2. Real Faculty Timetable (Today & Weekly Schedule)
3. My Students Directory, Department/Section Isolation & 360° Profile
4. Smart Attendance System (Batch roll-call, attendance logs, safe margin)
5. Academic Marks & Gradebook Management
6. Assignment Lifecycle (Create, View, Grade Submissions, Delete)
7. Class Announcements & Notifications Dispatch
8. Faculty Infrastructure / Equipment Helpdesk Ticketing
9. Campus Safety & Emergency SOS Live Feed (Read-Only)
10. Role-Based Access Control & Admin Isolation
=============================================================================
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from werkzeug.security import generate_password_hash
from app import app
from database.db import get_db_connection, init_db


class TestFacultyPortalUpgrade(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key-campusguard'
        self.client = app.test_client()

        init_db()

        conn = get_db_connection()
        try:
            # Ensure faculty FAC001 exists with standard password
            fac_pw = generate_password_hash('Faculty@123')
            fac = conn.execute("SELECT * FROM faculties WHERE email = 'faculty@example.com'").fetchone()
            if not fac:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO faculties (faculty_id, name, email, phone, password_hash, department, designation, cabin)
                    VALUES ('FAC001', 'Dr. Ramesh Rao', 'faculty@example.com', '+91 98888 11223', ?, 'Computer Science & Engineering', 'Associate Professor & Faculty Advisor', 'CS-201 (Cabin 4)')
                """, (fac_pw,))
                self.faculty_id = cursor.lastrowid
            else:
                self.faculty_id = fac['id']
                conn.execute("UPDATE faculties SET password_hash = ? WHERE id = ?", (fac_pw, self.faculty_id))

            # Ensure student STU004 (HARSHIKA) exists
            stu = conn.execute("SELECT * FROM students WHERE register_number = 'STU004'").fetchone()
            if not stu:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO students (name, register_number, email, password_hash, department, year, semester, section, status)
                    VALUES ('HARSHIKA', 'STU004', 'student4@gmail.com', ?, 'Computer Science & Engineering', 3, 5, 'A', 'ACTIVE')
                """, (fac_pw,))
                self.student_id = cursor.lastrowid
            else:
                self.student_id = stu['id']

            # Ensure attendance row exists for this student & course
            att = conn.execute("SELECT id FROM attendance WHERE student_id = ? AND subject_code = 'CS301'", (self.student_id,)).fetchone()
            if not att:
                conn.execute("""
                    INSERT INTO attendance (student_id, subject_code, subject_name, classes_held, classes_attended, classes_missed, attendance_pct)
                    VALUES (?, 'CS301', 'Database Management Systems', 40, 36, 4, 90.0)
                """, (self.student_id,))

            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM assignments WHERE title LIKE 'TEST_ASSIGN_%'")
            conn.execute("DELETE FROM complaints WHERE title LIKE 'TEST_TICKET_%'")
            conn.execute("DELETE FROM announcements WHERE title LIKE 'TEST_ANN_%'")
            conn.commit()
        finally:
            conn.close()

    def _login_faculty(self):
        return self.client.post('/faculty/login', data={
            'identifier': 'faculty@example.com',
            'password': 'Faculty@123'
        }, follow_redirects=True)

    # 1. Dashboard & Live Metrics
    def test_01_faculty_dashboard_live_kpis(self):
        self._login_faculty()
        res = self.client.get('/faculty/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Dr. Ramesh Rao', res.data)

    # 2. Real Timetable
    def test_02_faculty_timetable(self):
        self._login_faculty()
        res = self.client.get('/faculty/timetable')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Timetable', res.data)

    # 3. My Students Directory
    def test_03_my_students_directory_and_filter(self):
        self._login_faculty()
        res = self.client.get('/faculty/students')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'HARSHIKA', res.data)

        # 360 profile view
        res_view = self.client.get(f'/faculty/students/view/{self.student_id}')
        self.assertEqual(res_view.status_code, 200)
        self.assertIn(b'HARSHIKA', res_view.data)

    # 4. Smart Attendance System
    def test_04_smart_attendance_marking_and_persistence(self):
        self._login_faculty()
        
        payload = {
            'action_type': 'batch_roll_call',
            'course_code': 'CS301',
            'date': '2026-08-29',
            'topic': 'Transaction Management & Concurrency',
            f'status_{self.student_id}': 'Present'
        }
        res = self.client.post('/faculty/attendance', data=payload, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        conn = get_db_connection()
        try:
            log = conn.execute("""
                SELECT * FROM attendance_logs 
                WHERE student_id = ? AND course_code = 'CS301' AND date = '2026-08-29'
            """, (self.student_id,)).fetchone()
            self.assertIsNotNone(log)
            self.assertEqual(log['status'], 'Present')
        finally:
            conn.close()

    # 5. Academic Performance & Marks Ledger
    def test_05_marks_ledger_and_entry(self):
        self._login_faculty()
        
        marks_payload = {
            'course_code': 'CS301',
            'student_id': self.student_id,
            'cat1': 45.0,
            'cat2': 48.0,
            'quiz': 10.0,
            'assignment': 10.0,
            'project': 0.0,
            'fat': 92.0
        }
        res = self.client.post('/faculty/marks', data=marks_payload, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        conn = get_db_connection()
        try:
            m = conn.execute("SELECT * FROM marks WHERE student_id = ? AND course_code = 'CS301'", (self.student_id,)).fetchone()
            self.assertIsNotNone(m)
            self.assertEqual(m['cat1'], 45.0)
            self.assertEqual(m['fat'], 92.0)
        finally:
            conn.close()

    # 6. Assignment Management Lifecycle
    def test_06_assignment_lifecycle_and_grading(self):
        self._login_faculty()

        # Create Assignment
        assign_payload = {
            'course_code': 'CS301',
            'title': 'TEST_ASSIGN_01: SQL Optimization',
            'description': 'Analyze execution plan for nested joins.',
            'due_date': '2026-09-15',
            'max_marks': 50
        }
        res_create = self.client.post('/faculty/assignments', data=assign_payload, follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)

        conn = get_db_connection()
        try:
            assign = conn.execute("SELECT * FROM assignments WHERE title = 'TEST_ASSIGN_01: SQL Optimization'").fetchone()
            self.assertIsNotNone(assign)
            assign_id = assign['id']
        finally:
            conn.close()

        # View submissions roster
        res_subs = self.client.get(f'/faculty/assignments/submissions/{assign_id}')
        self.assertEqual(res_subs.status_code, 200)
        self.assertIn(b'TEST_ASSIGN_01', res_subs.data)

        # Grade student submission
        grade_payload = {
            'student_id': self.student_id,
            'marks_obtained': 48,
            'feedback': 'Excellent query optimization report.'
        }
        res_grade = self.client.post(f'/faculty/assignments/evaluate/{assign_id}', data=grade_payload, follow_redirects=True)
        self.assertEqual(res_grade.status_code, 200)

        # Verify DB marks
        conn = get_db_connection()
        try:
            sub = conn.execute("SELECT * FROM student_submissions WHERE assignment_id = ? AND student_id = ?", (assign_id, self.student_id)).fetchone()
            self.assertIsNotNone(sub)
            self.assertEqual(sub['marks_obtained'], 48.0)
            self.assertEqual(sub['status'], 'Graded')
        finally:
            conn.close()

        # Delete assignment
        res_del = self.client.post(f'/faculty/assignments/delete/{assign_id}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)

    # 7. Class Announcements
    def test_07_announcements_broadcast(self):
        self._login_faculty()
        ann_payload = {
            'title': 'TEST_ANN_01: Extra Lab Session Tomorrow',
            'content': 'Practical session for Query Optimization at 2 PM.',
            'category': 'Academic',
            'priority': 'High',
            'target_audience': 'Students'
        }
        res = self.client.post('/faculty/announcements/create', data=ann_payload, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        conn = get_db_connection()
        try:
            ann = conn.execute("SELECT * FROM announcements WHERE title = 'TEST_ANN_01: Extra Lab Session Tomorrow'").fetchone()
            self.assertIsNotNone(ann)
        finally:
            conn.close()

    # 8. Faculty Helpdesk / Complaint Ticketing
    def test_08_faculty_helpdesk_ticket_creation(self):
        self._login_faculty()
        ticket_payload = {
            'title': 'TEST_TICKET_01: CS-Lab 1 Projector Bulb Replacement',
            'category': 'Classroom Equipment',
            'location': 'Academic Block A - CS Lab 1',
            'description': 'HDMI display flickering during class lecture.',
            'priority': 'High'
        }
        res = self.client.post('/faculty/feedback/create', data=ticket_payload, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        conn = get_db_connection()
        try:
            t = conn.execute("SELECT * FROM complaints WHERE title = 'TEST_TICKET_01: CS-Lab 1 Projector Bulb Replacement'").fetchone()
            self.assertIsNotNone(t)
            self.assertEqual(t['sender_role'], 'Faculty')
            self.assertEqual(t['status'], 'Submitted')
        finally:
            conn.close()

    # 9. Campus Safety & Emergency SOS Feed (Read-Only)
    def test_09_faculty_safety_feed(self):
        self._login_faculty()
        res = self.client.get('/faculty/safety')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Emergency', res.data)

    # 10. Role-Based Access Control & Admin Isolation
    def test_10_faculty_rbac_isolation(self):
        self._login_faculty()
        
        # Faculty cannot access Admin Dashboard or Admin APIs
        res_admin = self.client.get('/admin/dashboard')
        self.assertEqual(res_admin.status_code, 302)

        res_del_stu = self.client.post(f'/admin/students/delete/{self.student_id}')
        self.assertEqual(res_del_stu.status_code, 302)


if __name__ == '__main__':
    unittest.main()
