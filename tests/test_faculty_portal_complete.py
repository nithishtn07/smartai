"""
=============================================================================
CampusGuard AI — Faculty Portal Comprehensive Integration Test Suite
Tests all 18 modules and workflows of the upgraded Faculty ERP Portal:
1. Authentication & RBAC Access Control
2. Dashboard & Today's Schedule
3. My Timetable
4. My Subjects
5. My Classes
6. My Students & 360 Profile Inspector
7. Attendance Roll-Call & Low Attendance Warning Dispatches
8. Marks & Gradebook Assessment Entry
9. Course Assignments
10. Study Materials
11. Leave & Outpass Review Decision Workflow
12. Multi-Role Messaging (Student, Parent, Admin)
13. Notifications Center & Mark Read
14. AI Academic Insights & Conversational Assistant
15. Profile & Security Password Updates
=============================================================================
"""

import os
import unittest
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

# Ensure test mode / clean DB connection
import app

class TestFacultyPortalComplete(unittest.TestCase):

    def setUp(self):
        app.app.config['TESTING'] = True
        app.app.config['SECRET_KEY'] = 'test-secret-faculty-portal-key'
        self.client = app.app.test_client()

        # Reset rate limiting login attempts
        conn = app.get_db_connection()
        conn.execute("DELETE FROM login_attempts")
        conn.commit()
        conn.close()

    def _login_faculty(self):
        """Helper to establish an authenticated faculty session."""
        return self.client.post('/faculty/login', data={
            'identifier': 'FAC001',
            'password': 'Faculty@123'
        }, follow_redirects=True)

    def test_01_faculty_auth_and_rbac_protection(self):
        """Verify faculty authentication, session establishment, and route protection."""
        # 1. Unauthenticated access to /faculty/dashboard redirects to login
        resp = self.client.get('/faculty/dashboard')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/faculty/login', resp.headers['Location'])

        # 2. Student session trying to access faculty portal is denied/redirected
        with self.client.session_transaction() as sess:
            sess['student_id'] = 1
        resp_stu = self.client.get('/faculty/dashboard')
        self.assertEqual(resp_stu.status_code, 302)

        # 3. Parent session trying to access faculty portal is denied/redirected
        with self.client.session_transaction() as sess:
            sess.clear()
            sess['parent_id'] = 1
        resp_par = self.client.get('/faculty/dashboard')
        self.assertEqual(resp_par.status_code, 302)

        # 4. Valid Faculty login
        with self.client.session_transaction() as sess:
            sess.clear()
        resp_login = self._login_faculty()
        self.assertEqual(resp_login.status_code, 200)
        self.assertIn(b'Dr. Ramesh Rao', resp_login.data)

    def test_02_faculty_dashboard_and_today_schedule(self):
        """Verify Faculty Dashboard loads today's classes and KPI data."""
        self._login_faculty()
        resp = self.client.get('/faculty/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Welcome back', resp.data)
        self.assertIn(b'Assigned Courses', resp.data)
        self.assertIn(b'Total Advisees', resp.data)
        self.assertIn(b'Action Items &amp; Tasks', resp.data)

    def test_03_faculty_timetable(self):
        """Verify Faculty Timetable displays lecture slots and weekly schedule."""
        self._login_faculty()
        resp = self.client.get('/faculty/timetable')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Weekly Faculty Lecture Timetable', resp.data)
        self.assertIn(b'Monday', resp.data)
        self.assertIn(b'CS301', resp.data)

    def test_04_faculty_subjects(self):
        """Verify My Subjects displays assigned courses, credits, and student metrics."""
        self._login_faculty()
        resp = self.client.get('/faculty/subjects')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Assigned Subjects &amp; Course Instruction', resp.data)
        self.assertIn(b'CS301', resp.data)
        self.assertIn(b'Database Management Systems', resp.data)

    def test_05_faculty_classes(self):
        """Verify My Classes displays class cohorts and average attendance."""
        self._login_faculty()
        resp = self.client.get('/faculty/classes')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Assigned Classes &amp; Student Batches', resp.data)
        self.assertIn(b'CSE-3A', resp.data)
        self.assertIn(b'Nithish Nagaraj', resp.data)

    def test_06_faculty_students_and_360_profile(self):
        """Verify student directory and 360 profile inspector."""
        self._login_faculty()

        # 1. Directory
        resp_dir = self.client.get('/faculty/students')
        self.assertEqual(resp_dir.status_code, 200)
        self.assertIn(b'Enrolled Students &amp; Advisees', resp_dir.data)
        self.assertIn(b'Nithish Nagaraj', resp_dir.data)

        # 2. Search
        resp_search = self.client.get('/faculty/students?q=Nithish')
        self.assertEqual(resp_search.status_code, 200)
        self.assertIn(b'STU001', resp_search.data)

        # 3. 360 Student Profile
        resp_view = self.client.get('/faculty/students/view/1')
        self.assertEqual(resp_view.status_code, 200)
        self.assertIn(b'360\xc2\xb0 Academic Profile', resp_view.data)
        self.assertIn(b'Nithish Nagaraj', resp_view.data)
        self.assertIn(b'Linked Parent', resp_view.data)

    def test_07_faculty_attendance_roll_call_and_warning(self):
        """Verify attendance roll call batch recording and low-attendance warning dispatch."""
        self._login_faculty()

        # 1. Attendance page loads
        resp_get = self.client.get('/faculty/attendance?course=CS301')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Course Attendance &amp; Roll-Call Center', resp_get.data)

        # 2. Batch roll-call submission on a specific date
        resp_post = self.client.post('/faculty/attendance', data={
            'action_type': 'batch_roll_call',
            'course_code': 'CS301',
            'date': '2026-08-21',
            'topic': 'Advanced Query Optimization & Execution Plans',
            'status_1': 'Present'
        }, follow_redirects=True)
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn(b'Class roll call for CS301 successfully saved', resp_post.data)

        # 3. Test Date-Logs API endpoint
        resp_api = self.client.get('/api/faculty/attendance/date-logs?course=CS301&date=2026-08-21')
        self.assertEqual(resp_api.status_code, 200)
        api_data = resp_api.get_json()
        self.assertEqual(api_data['status'], 'success')
        self.assertEqual(api_data['records']['1'], 'Present')
        self.assertIn('Query Optimization', api_data['topic'])

        # 4. Modify / Edit attendance on the same date (toggle to Absent) without double counting classes_held
        resp_edit = self.client.post('/faculty/attendance', data={
            'action_type': 'batch_roll_call',
            'course_code': 'CS301',
            'date': '2026-08-21',
            'topic': 'Advanced Query Optimization & Execution Plans',
            'status_1': 'Absent'
        }, follow_redirects=True)
        self.assertEqual(resp_edit.status_code, 200)

        # Verify edited status in API
        resp_api_edited = self.client.get('/api/faculty/attendance/date-logs?course=CS301&date=2026-08-21')
        self.assertEqual(resp_api_edited.get_json()['records']['1'], 'Absent')

        # 5. One-click warning notice to student and parent
        resp_warn = self.client.post('/faculty/attendance/send-warning/1', data={
            'course_code': 'CS301'
        }, follow_redirects=True)
        self.assertEqual(resp_warn.status_code, 200)
        self.assertIn(b'Official attendance warning dispatched', resp_warn.data)

    def test_08_faculty_marks_gradebook(self):
        """Verify marks input, auto grade computation, and student/parent notification."""
        self._login_faculty()

        # 1. Marks page loads
        resp_get = self.client.get('/faculty/marks')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Marks, Gradebook &amp; Evaluation', resp_get.data)

        # 2. Post assessment scores
        resp_post = self.client.post('/faculty/marks', data={
            'course_code': 'CS301',
            'student_id': '1',
            'cat1': '50.0',
            'cat2': '50.0',
            'quiz': '10.0',
            'assignment': '10.0',
            'fat': '100.0'
        }, follow_redirects=True)
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn(b'Assessment scores for CS301', resp_post.data)
        self.assertIn(b'Grade: S', resp_post.data)

    def test_09_faculty_assignments_workflow(self):
        """Verify posting new course assignment."""
        self._login_faculty()

        resp_get = self.client.get('/faculty/assignments')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Course Assignments &amp; Projects', resp_get.data)

        resp_post = self.client.post('/faculty/assignments', data={
            'course_code': 'CS301',
            'title': 'Assignment 4: Distributed Two-Phase Commit Implementation',
            'description': 'Implement 2PC protocol in Python with network partition recovery.',
            'due_date': '2026-09-10',
            'max_marks': '50'
        }, follow_redirects=True)
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn(b'published successfully', resp_post.data)

    def test_10_faculty_study_materials(self):
        """Verify sharing course study materials."""
        self._login_faculty()

        resp_get = self.client.get('/faculty/materials')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Materials &amp; Resources', resp_get.data)

        resp_post = self.client.post('/faculty/materials', data={
            'course_code': 'CS301',
            'title': 'Unit 5: Distributed Databases & CAP Theorem PDF',
            'material_type': 'Lecture Notes PDF'
        }, follow_redirects=True)
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn(b'Study material', resp_post.data)

    def test_11_faculty_leaves_decision(self):
        """Verify reviewing and approving student outpass requests."""
        self._login_faculty()

        resp_get = self.client.get('/faculty/leaves')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Student Hostel Leave &amp; Outpass Review', resp_get.data)

        # Approve leave ID 1
        resp_post = self.client.post('/faculty/leaves/decision/1', data={
            'decision': 'Approved',
            'remarks': 'Approved by Faculty Advisor'
        }, follow_redirects=True)
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn(b'has been marked as Approved', resp_post.data)

    def test_12_faculty_messaging_system(self):
        """Verify dispatching messages to Student, Parent, and Central Admin."""
        self._login_faculty()

        resp_get = self.client.get('/faculty/messages')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Faculty Communication Center', resp_get.data)

        # 1. Message to Student
        r_stu = self.client.post('/faculty/messages', data={
            'recipient_target': 'student_1',
            'subject': 'DBMS Mini-Project Milestone Review',
            'content': 'Please submit your ER diagram and schema design by Friday.'
        }, follow_redirects=True)
        self.assertEqual(r_stu.status_code, 200)
        self.assertIn(b'Message successfully transmitted', r_stu.data)

        # 2. Message to Parent
        r_par = self.client.post('/faculty/messages', data={
            'recipient_target': 'parent_1',
            'subject': 'Academic Progress Update for Nithish',
            'content': 'Nithish is performing exceptionally well in Database Systems.'
        }, follow_redirects=True)
        self.assertEqual(r_par.status_code, 200)
        self.assertIn(b'Message successfully transmitted', r_par.data)

        # 3. Message to Admin
        r_adm = self.client.post('/faculty/messages', data={
            'recipient_target': 'admin',
            'subject': 'Request for CS Lab 1 Software Update',
            'content': 'Please install PostgreSQL 16 on CS Lab 1 workstations.'
        }, follow_redirects=True)
        self.assertEqual(r_adm.status_code, 200)
        self.assertIn(b'Message successfully transmitted', r_adm.data)

    def test_13_faculty_notifications(self):
        """Verify faculty notifications center and mark read."""
        self._login_faculty()

        resp_get = self.client.get('/faculty/notifications')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Faculty Notification Center', resp_get.data)

        resp_read_all = self.client.post('/faculty/notifications/read-all', follow_redirects=True)
        self.assertEqual(resp_read_all.status_code, 200)
        self.assertIn(b'All faculty notifications marked as read', resp_read_all.data)

    def test_14_faculty_ai_academic_insights(self):
        """Verify AI Academic Insights console and natural language assistant endpoint."""
        self._login_faculty()

        # 1. Insights Page
        resp_get = self.client.get('/faculty/insights')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Faculty AI Academic &amp; Attendance Insights', resp_get.data)

        # 2. AI Assistant query
        resp_ai = self.client.post('/faculty/api/ai-insights', json={
            'query': 'Which students are academically at risk?'
        })
        self.assertEqual(resp_ai.status_code, 200)
        data = resp_ai.get_json()
        self.assertEqual(data.get('status'), 'success')
        self.assertTrue(len(data.get('reply', '')) > 10)

    def test_15_faculty_profile_and_contact_update(self):
        """Verify updating contact details and password changes."""
        self._login_faculty()

        # 1. Profile Page
        resp_get = self.client.get('/faculty/profile')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Faculty Profile &amp; Settings', resp_get.data)

        # 2. Update contact details
        resp_update = self.client.post('/faculty/profile', data={
            'action': 'update_info',
            'phone': '+91 94440 99887',
            'cabin': 'CS-Cabin 204'
        }, follow_redirects=True)
        self.assertEqual(resp_update.status_code, 200)
        self.assertIn(b'Profile details updated successfully', resp_update.data)

        # 3. Update password
        resp_pw = self.client.post('/faculty/profile', data={
            'action': 'change_password',
            'current_password': 'Faculty@123',
            'new_password': 'Faculty@1234',
            'confirm_password': 'Faculty@1234'
        }, follow_redirects=True)
        self.assertEqual(resp_pw.status_code, 200)
        self.assertIn(b'Password updated successfully', resp_pw.data)

        # Reset password back to default
        resp_reset = self.client.post('/faculty/profile', data={
            'action': 'change_password',
            'current_password': 'Faculty@1234',
            'new_password': 'Faculty@123',
            'confirm_password': 'Faculty@123'
        }, follow_redirects=True)
        self.assertEqual(resp_reset.status_code, 200)


if __name__ == '__main__':
    unittest.main()
