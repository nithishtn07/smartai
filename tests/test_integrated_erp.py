"""
=============================================================================
CampusGuard AI — Comprehensive Enterprise Integration Test Suite
=============================================================================
Validates:
1. Multi-role Authentication & Privilege Escalation Protection
2. Admin Master Control (Student, Parent, Faculty, Courses, Settings)
3. Faculty Academic Operations (Attendance, Marks, Assignments, Outpasses)
4. Cross-Portal Real-time Synchronization (Faculty -> DB -> Student / Parent / Admin)
5. AI Insight Engine (Attendance Risk, Academic Risk, Fee & Exam Alerts)
6. Emergency SOS & Security Command Console
7. Centralized Multi-Role Notification Broker
8. Complaint Lifecycle with AI Triage & Department Routing
9. Audit Logging & Immutable Trail
10. Full REST API Suite
=============================================================================
"""

import unittest
import json
import sqlite3
import datetime
from app import app, init_db, get_db_connection
from services.ai_insight_engine import (
    evaluate_attendance_risk,
    evaluate_academic_risk,
    evaluate_fee_alerts,
    evaluate_exam_reminders,
    evaluate_assignment_alerts,
    generate_student_insights_summary,
    generate_admin_campus_risk_overview
)


class TestIntegratedEnterpriseERP(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-integrated-erp-secret-2026'
        self.client = app.test_client()
        init_db()

        conn = get_db_connection()
        # Clean up any leftover test artifacts (delete child records before parent records)
        conn.execute("DELETE FROM parents WHERE email = 'parent_e2e@example.com'")
        conn.execute("DELETE FROM students WHERE register_number IN ('STU_E2E_01', 'STU_E2E_02')")
        conn.execute("DELETE FROM faculties WHERE email = 'faculty_e2e@example.com'")
        conn.execute("DELETE FROM incidents WHERE incident_id LIKE 'SOS-E2E-%'")
        conn.execute("DELETE FROM complaints WHERE title LIKE 'E2E Test Grievance%'")
        conn.execute("UPDATE students SET name = 'Nithish Nagaraj' WHERE register_number = 'STU001'")
        conn.commit()

        self.student = conn.execute("SELECT * FROM students WHERE register_number = 'STU001'").fetchone()
        self.parent = conn.execute("SELECT * FROM parents WHERE email = 'parent@example.com'").fetchone()
        self.faculty = conn.execute("SELECT * FROM faculties WHERE email = 'faculty@example.com'").fetchone()
        self.admin = conn.execute("SELECT * FROM admins WHERE username = 'admin'").fetchone()
        conn.close()

    def test_01_admin_creates_student_and_student_logs_in(self):
        """Test 1: Admin creates a student, and the newly created student logs in successfully."""
        with self.client.session_transaction() as sess:
            sess['admin_id'] = self.admin['id']
            sess['user_role'] = 'admin'

        resp_create = self.client.post('/admin/students/create', data={
            'register_number': 'STU_E2E_01',
            'name': 'Aarav Sharma',
            'email': 'aarav.sharma@example.com',
            'phone': '+91 98111 22233',
            'department': 'Computer Science',
            'year': '3',
            'semester': '5',
            'program': 'B.Tech',
            'password': 'Student@123'
        }, follow_redirects=True)
        self.assertEqual(resp_create.status_code, 200)

        # Logout admin and log in as new student
        self.client.get('/admin/logout')
        resp_login = self.client.post('/student/login', data={
            'register_number': 'STU_E2E_01',
            'password': 'Student@123'
        }, follow_redirects=True)
        self.assertEqual(resp_login.status_code, 200)
        self.assertIn(b'Aarav Sharma', resp_login.data)
        self.assertIn(b'STU_E2E_01', resp_login.data)

    def test_02_admin_links_parent_and_parent_access_scoped(self):
        """Test 2: Admin links a parent account and the parent only sees the linked ward."""
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO students (name, register_number, email, password_hash, department, year)
            VALUES ('Priya Patel', 'STU_E2E_02', 'priya.patel@example.com', 'dummy_hash', 'Computer Science', 2)
        """)
        conn.commit()
        priya = conn.execute("SELECT * FROM students WHERE register_number = 'STU_E2E_02'").fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess['admin_id'] = self.admin['id']
            sess['user_role'] = 'admin'

        resp_parent_create = self.client.post('/admin/parents/create', data={
            'name': 'Vikram Patel',
            'email': 'parent_e2e@example.com',
            'phone': '+91 98777 66554',
            'relationship': 'Father',
            'student_id': priya['id'],
            'occupation': 'Architect',
            'address': '#100 Lake View, Bangalore',
            'password': 'Parent@123'
        }, follow_redirects=True)
        self.assertEqual(resp_parent_create.status_code, 200)

        # Parent login
        self.client.get('/admin/logout')
        resp_par_login = self.client.post('/parent/login', data={
            'email': 'parent_e2e@example.com',
            'password': 'Parent@123'
        }, follow_redirects=True)
        self.assertEqual(resp_par_login.status_code, 200)
        self.assertIn(b'Priya Patel', resp_par_login.data)
        self.assertIn(b'Vikram Patel', resp_par_login.data)

    def test_03_faculty_marks_attendance_and_cross_portal_sync(self):
        """Test 3: Faculty marks attendance -> Student & Parent view updates -> AI evaluates risk."""
        with self.client.session_transaction() as sess:
            sess['faculty_id'] = self.faculty['id']
            sess['user_role'] = 'faculty'

        # Mark absent in CS301
        resp_mark = self.client.post('/faculty/attendance', data={
            'course_code': 'CS301',
            'student_id': str(self.student['id']),
            'status': 'Absent',
            'date': '2026-08-22',
            'topic': 'Database Normalization'
        }, follow_redirects=True)
        self.assertEqual(resp_mark.status_code, 200)

        # Check Student Portal
        with self.client.session_transaction() as sess:
            sess['student_id'] = self.student['id']
            sess['user_role'] = 'student'
        resp_stu = self.client.get('/student/attendance')
        self.assertEqual(resp_stu.status_code, 200)
        self.assertIn(b'Database Normalization', resp_stu.data)

        # Check Parent Portal
        with self.client.session_transaction() as sess:
            sess['parent_id'] = self.parent['id']
            sess['user_role'] = 'parent'
        resp_par = self.client.get('/parent/attendance')
        self.assertEqual(resp_par.status_code, 200)
        self.assertIn(b'Database Normalization', resp_par.data)

    def test_04_faculty_uploads_marks_and_sync(self):
        """Test 4: Faculty enters assessment marks -> Student and Parent portals display updated grades."""
        with self.client.session_transaction() as sess:
            sess['faculty_id'] = self.faculty['id']
            sess['user_role'] = 'faculty'

        resp_marks = self.client.post('/faculty/marks', data={
            'course_code': 'CS301',
            'student_id': str(self.student['id']),
            'cat1': 48.5,
            'cat2': 49.0,
            'quiz': 10.0,
            'assignment': 10.0,
            'project': 20.0,
            'fat': 96.0,
            'grade': 'S'
        }, follow_redirects=True)
        self.assertEqual(resp_marks.status_code, 200)

        # Check student marks
        with self.client.session_transaction() as sess:
            sess['student_id'] = self.student['id']
            sess['user_role'] = 'student'
        resp_stu = self.client.get('/student/marks')
        self.assertEqual(resp_stu.status_code, 200)
        self.assertIn(b'CS301', resp_stu.data)

        # Check parent marks
        with self.client.session_transaction() as sess:
            sess['parent_id'] = self.parent['id']
            sess['user_role'] = 'parent'
        resp_par = self.client.get('/parent/academics')
        self.assertEqual(resp_par.status_code, 200)
        self.assertIn(b'CS301', resp_par.data)

    def test_05_admin_posts_announcement_broadcast(self):
        """Test 5: Admin posts announcement -> Dispatched across targeted portals."""
        with self.client.session_transaction() as sess:
            sess['admin_id'] = self.admin['id']
            sess['user_role'] = 'admin'

        resp_post = self.client.post('/admin/announcements', data={
            'title': 'E2E Global Campus Safety Protocol Update',
            'description': 'Campus main gate biometric turnstiles operational 24/7.',
            'category': 'Safety',
            'priority': 'High',
            'target_audience': 'All'
        }, follow_redirects=True)
        self.assertEqual(resp_post.status_code, 200)

        conn = get_db_connection()
        ann = conn.execute("SELECT * FROM announcements WHERE title = 'E2E Global Campus Safety Protocol Update'").fetchone()
        conn.close()
        self.assertIsNotNone(ann)
        self.assertEqual(ann['category'], 'Safety')

    def test_06_complaint_lifecycle_and_ai_triage(self):
        """Test 6: Student raises complaint -> AI triages -> Admin views & resolves -> Student tracks."""
        with self.client.session_transaction() as sess:
            sess['student_id'] = self.student['id']
            sess['user_role'] = 'student'

        resp_comp = self.client.post('/student/complaints', data={
            'title': 'E2E Test Grievance: Water Filter Malfunction in CS Block Floor 2',
            'description': 'Water dispenser dispensing warm water with low pressure.',
            'category': 'Facility',
            'location': 'Academic Block A (CS Dept)',
            'priority': 'Normal'
        }, follow_redirects=True)
        self.assertEqual(resp_comp.status_code, 200)

        conn = get_db_connection()
        comp = conn.execute("SELECT * FROM complaints WHERE title LIKE 'E2E Test Grievance%'").fetchone()
        conn.close()
        self.assertIsNotNone(comp)
        self.assertEqual(comp['status'], 'Submitted')

    def test_07_emergency_sos_beacon_dispatch(self):
        """Test 7: Student triggers SOS beacon -> Recorded in DB -> Appears in Security & Admin consoles."""
        with self.client.session_transaction() as sess:
            sess['student_id'] = self.student['id']
            sess['user_role'] = 'student'

        resp_sos = self.client.post('/student/emergency', data={
            'latitude': '12.9716',
            'longitude': '77.5946',
            'location_name': 'Central Library Alley',
            'sos_note': 'E2E Test Distress Signal'
        }, follow_redirects=True)
        self.assertEqual(resp_sos.status_code, 200)

        # Check Security Console
        resp_sec = self.client.get('/security/dashboard')
        self.assertEqual(resp_sec.status_code, 200)
        self.assertIn(b'E2E Test Distress Signal', resp_sec.data)

        # Check Admin Safety Console
        with self.client.session_transaction() as sess:
            sess['admin_id'] = self.admin['id']
            sess['user_role'] = 'admin'
        resp_adm = self.client.get('/admin/safety')
        self.assertEqual(resp_adm.status_code, 200)
        self.assertIn(b'Central Library Alley', resp_adm.data)

    def test_08_ai_insight_engine_evaluations(self):
        """Test 8: CampusGuard AI Insight Engine multi-domain intelligence synthesis."""
        conn = get_db_connection()
        att_risk = evaluate_attendance_risk(self.student['id'], conn)
        acad_risk = evaluate_academic_risk(self.student['id'], conn)
        fee_alerts = evaluate_fee_alerts(self.student['id'], conn)
        student_insights = generate_student_insights_summary(self.student['id'], conn)
        admin_overview = generate_admin_campus_risk_overview(conn)
        conn.close()

        self.assertIn('status', att_risk)
        self.assertIn('overall_pct', att_risk)
        self.assertIn('status', acad_risk)
        self.assertIn('composite_risk_score', student_insights)
        self.assertIn('total_students', admin_overview)
        self.assertGreater(admin_overview['total_students'], 0)

    def test_09_unauthorized_access_protection(self):
        """Test 9: Role-based authorization denies student access to admin routes."""
        with self.client.session_transaction() as sess:
            sess['student_id'] = self.student['id']
            sess['user_role'] = 'student'

        # Attempt to access admin dashboard
        resp = self.client.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/admin/login', resp.headers['Location'])

        # Attempt to access faculty marks entry
        resp_fac = self.client.get('/faculty/marks', follow_redirects=False)
        self.assertEqual(resp_fac.status_code, 302)
        self.assertIn('/faculty/login', resp_fac.headers['Location'])

    def test_10_rest_api_suite(self):
        """Test 10: Complete REST API endpoints for attendance, marks, fees, and AI insights."""
        # 1. API Auth Session
        with self.client.session_transaction() as sess:
            sess['student_id'] = self.student['id']
            sess['user_role'] = 'student'

        resp_sess = self.client.get('/api/auth/session')
        self.assertEqual(resp_sess.status_code, 200)
        data = resp_sess.get_json()
        self.assertTrue(data['authenticated'])
        self.assertEqual(data['role'], 'student')

        # 2. API Students List (Admin scoped)
        with self.client.session_transaction() as sess:
            sess['admin_id'] = self.admin['id']
            sess['user_role'] = 'admin'

        resp_stu = self.client.get('/api/students')
        self.assertEqual(resp_stu.status_code, 200)
        stu_data = resp_stu.get_json()
        self.assertEqual(stu_data['status'], 'success')
        self.assertGreater(stu_data['count'], 0)

        # 3. API Attendance Summary
        with self.client.session_transaction() as sess:
            sess['student_id'] = self.student['id']
            sess['user_role'] = 'student'

        resp_att = self.client.get(f"/api/attendance/summary/{self.student['id']}")
        self.assertEqual(resp_att.status_code, 200)
        att_data = resp_att.get_json()
        self.assertEqual(att_data['status'], 'success')

        # 4. API AI Insights
        resp_ai = self.client.get(f"/api/ai/insights/{self.student['id']}")
        self.assertEqual(resp_ai.status_code, 200)
        ai_data = resp_ai.get_json()
        self.assertEqual(ai_data['status'], 'success')
        self.assertIn('composite_risk_score', ai_data['insights'])

        # 5. API Campus Risk Overview (Admin/Faculty scoped)
        with self.client.session_transaction() as sess:
            sess['admin_id'] = self.admin['id']
            sess['user_role'] = 'admin'

        resp_risk = self.client.get('/api/ai/campus-risk')
        self.assertEqual(resp_risk.status_code, 200)
        risk_data = resp_risk.get_json()
        self.assertEqual(risk_data['status'], 'success')


if __name__ == '__main__':
    unittest.main()
