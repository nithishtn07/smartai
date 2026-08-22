"""
=============================================================================
CampusGuard AI — Extended Faculty Portal ERP Modules Test Suite (11 to 29)
Tests all newly added and enhanced modules:
- Module 11 & 12: Attendance Analytics & Dynamic Threshold Alerts
- Module 13, 14 & 15: Marks Management & Academic Performance Analytics
- Module 16: Assignment Creation, Submissions & Evaluation
- Module 17: Learning Materials Organization (Unit/Topic)
- Module 18: Practical Lab Management & Experiments
- Module 19: Examinations & Invigilation Roster
- Module 21 & 22: Mentorship & Student Risk Alerts
- Module 24: Course Announcements & Multi-Portal Broadcasting
- Module 27: Academic Calendar
- Module 28: Reports Generation & CSV Streaming Export
- Module 29: Faculty Feedback & Administrative Helpdesk
=============================================================================
"""

import unittest
import sqlite3
import app

class TestFacultyExtendedModules(unittest.TestCase):

    def setUp(self):
        app.app.config['TESTING'] = True
        app.app.config['SECRET_KEY'] = 'test-secret-faculty-extended-key'
        self.client = app.app.test_client()

        # Reset login attempts
        conn = app.get_db_connection()
        conn.execute("DELETE FROM login_attempts")
        conn.commit()
        conn.close()

    def _login_faculty(self):
        """Helper to log in as Faculty Dr. Ramesh Rao."""
        return self.client.post('/faculty/login', data={
            'identifier': 'FAC001',
            'password': 'Faculty@123'
        }, follow_redirects=True)

    def test_01_attendance_analytics_and_dynamic_threshold(self):
        """Test Attendance Analytics with dynamic threshold from system settings."""
        self._login_faculty()

        resp = self.client.get('/faculty/attendance/analytics')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Course Attendance Analytics &amp; Trends', resp.data)
        self.assertIn(b'Class Average Attendance', resp.data)
        self.assertIn(b'Dynamic Threshold:', resp.data)

        # Test filtering by subject
        resp_filtered = self.client.get('/faculty/attendance/analytics?subject=CS301')
        self.assertEqual(resp_filtered.status_code, 200)
        self.assertIn(b'CS301', resp_filtered.data)

    def test_02_marks_performance_analytics(self):
        """Test Academic Performance Analytics, grade distributions, and remedial watchlist."""
        self._login_faculty()

        resp = self.client.get('/faculty/marks/performance')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Academic Performance &amp; Grade Trajectory', resp.data)
        self.assertIn(b'CAT 1 Average', resp.data)
        self.assertIn(b'FAT Exam Average', resp.data)
        self.assertIn(b'Grade Distribution Spectrum', resp.data)

    def test_03_assignments_submissions_and_evaluation(self):
        """Test assignment submissions view, grading evaluation, and student/parent notification."""
        self._login_faculty()

        # 1. View Submissions
        resp_sub = self.client.get('/faculty/assignments/submissions/1')
        self.assertEqual(resp_sub.status_code, 200)
        self.assertIn(b'Student Submissions &amp; Evaluation Roster', resp_sub.data)

        # 2. Evaluate submission
        resp_eval = self.client.post('/faculty/assignments/evaluate/1', data={
            'student_id': '1',
            'marks_obtained': '48.5',
            'feedback': 'Exceptional execution of distributed 2PC recovery protocol.'
        }, follow_redirects=True)
        self.assertEqual(resp_eval.status_code, 200)
        self.assertIn(b'Assignment evaluation and marks successfully submitted', resp_eval.data)

    def test_04_learning_materials_upload_and_delete(self):
        """Test uploading unit/topic categorized study materials and removal."""
        self._login_faculty()

        # 1. Upload Material
        resp_upload = self.client.post('/faculty/materials/upload', data={
            'course_code': 'CS301',
            'unit': 'Unit 3: Implementation & Design',
            'topic': 'B+ Tree Concurrency & Write-Ahead Logging',
            'title': 'Unit 3 WAL Implementation Guide (PDF)',
            'material_type': 'Lecture Notes PDF',
            'link_url': ''
        }, follow_redirects=True)
        self.assertEqual(resp_upload.status_code, 200)
        self.assertIn(b'successfully uploaded and published', resp_upload.data)

        # Verify in DB
        conn = app.get_db_connection()
        mat = conn.execute("SELECT * FROM study_materials WHERE title = 'Unit 3 WAL Implementation Guide (PDF)'").fetchone()
        self.assertIsNotNone(mat)
        mat_id = mat['id']
        conn.close()

        # 2. Delete Material
        resp_del = self.client.post(f'/faculty/materials/delete/{mat_id}', follow_redirects=True)
        self.assertEqual(resp_del.status_code, 200)
        self.assertIn(b'Study material removed successfully', resp_del.data)

    def test_05_lab_management_and_experiments(self):
        """Test Practical Lab Management, recording experiment scores and viva marks."""
        self._login_faculty()

        # 1. Lab Dashboard
        resp = self.client.get('/faculty/lab?course=CS301L')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Lab Management &amp; Practical Experiments', resp.data)

        # 2. Record Experiment
        resp_post = self.client.post('/faculty/lab', data={
            'course_code': 'CS301L',
            'student_id': '1',
            'experiment_no': '7',
            'title': 'Query Optimizer Execution Plan Analysis & Index Tuning',
            'conducted_date': '2026-08-21',
            'practical_marks': '10.0',
            'viva_marks': '9.5',
            'record_status': 'Verified',
            'remarks': 'Optimal execution plan demonstrated with index scan.'
        }, follow_redirects=True)
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn(b'Lab experiment #7 successfully saved and verified', resp_post.data)

    def test_06_examinations_module(self):
        """Test Faculty Examinations timetable and invigilation duties view."""
        self._login_faculty()

        resp = self.client.get('/faculty/exams')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Examination Schedule &amp; Invigilation Roster', resp.data)
        self.assertIn(b'Official Examination Timetable', resp.data)

    def test_07_mentoring_and_student_risk_alerts(self):
        """Test Mentorship module, mentee KPIs, and real-time student risk calculation."""
        self._login_faculty()

        resp = self.client.get('/faculty/mentoring')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Mentoring, Advisee Guidance &amp; Risk Alerts', resp.data)
        self.assertIn(b'Total Assigned Mentees', resp.data)
        self.assertIn(b'Real-Time Student Risk Intelligence Alerts', resp.data)

    def test_08_course_announcements_broadcast(self):
        """Test creating course-targeted announcements and cross-portal alert propagation."""
        self._login_faculty()

        resp_get = self.client.get('/faculty/announcements')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Course Announcements &amp; Circulars', resp_get.data)

        resp_post = self.client.post('/faculty/announcements/create', data={
            'course_code': 'CS301',
            'title': 'Mini-Project Schema Review Deadline',
            'description': 'All student groups must upload their ER schema diagrams by 5 PM Friday.',
            'category': 'Academic',
            'priority': 'High',
            'target_audience': 'Students & Parents'
        }, follow_redirects=True)
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn(b'Course announcement broadcasted successfully', resp_post.data)

    def test_09_academic_calendar_module(self):
        """Test Faculty Academic Calendar displaying institutional milestones."""
        self._login_faculty()

        resp = self.client.get('/faculty/calendar')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Institutional Academic Calendar &amp; Milestones', resp.data)
        self.assertIn(b'Commencement of Fall 2026 Semester', resp.data)

    def test_10_reports_generation_and_csv_export(self):
        """Test Reports view and CSV streaming download."""
        self._login_faculty()

        # 1. Reports UI
        resp_ui = self.client.get('/faculty/reports?type=attendance')
        self.assertEqual(resp_ui.status_code, 200)
        self.assertIn(b'Reports Generation &amp; CSV Exports', resp_ui.data)

        # 2. Export Attendance CSV
        resp_csv_att = self.client.get('/faculty/reports/export/attendance')
        self.assertEqual(resp_csv_att.status_code, 200)
        self.assertEqual(resp_csv_att.mimetype, 'text/csv')
        self.assertIn(b'Student Name', resp_csv_att.data)

        # 3. Export Marks CSV
        resp_csv_marks = self.client.get('/faculty/reports/export/marks')
        self.assertEqual(resp_csv_marks.status_code, 200)
        self.assertEqual(resp_csv_marks.mimetype, 'text/csv')
        self.assertIn(b'CAT 1 (50)', resp_csv_marks.data)

    def test_11_feedback_and_administrative_requests(self):
        """Test submitting feedback / request ticket to Central Administration."""
        self._login_faculty()

        resp_get = self.client.get('/faculty/feedback')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Faculty Feedback &amp; Administrative Requests', resp_get.data)

        resp_post = self.client.post('/faculty/feedback/create', data={
            'category': 'Classroom Issue',
            'title': 'Request for Smartboard Calibration in Hall 201',
            'description': 'Touch sensitivity on the interactive smartboard in Hall 201 needs calibration.',
            'priority': 'Normal'
        }, follow_redirects=True)
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn(b'Your administrative request has been submitted', resp_post.data)


if __name__ == '__main__':
    unittest.main()
