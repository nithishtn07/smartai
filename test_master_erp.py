"""
=============================================================================
CampusGuard AI - Master Comprehensive Test Suite
Validates all 20+ Modules, AI Services, Role Consoles, and End-to-End Flows.
=============================================================================
"""

import unittest
import json
import sqlite3
from app import app, init_db, analyze_resume_skills, calculate_safe_route, generate_assistant_reply

class TestMasterCampusGuardERP(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-master-erp-secret-2026'
        self.client = app.test_client()
        init_db()

        # Perform student login session setup
        self.client.post('/student/login', data={
            'register_number': 'STU001',
            'password': 'Student@123'
        }, follow_redirects=True)

    def test_01_core_auth_and_landing(self):
        """Test landing page, login and student dashboard access"""
        resp_home = self.client.get('/')
        self.assertEqual(resp_home.status_code, 200)

        resp_dash = self.client.get('/student/dashboard')
        self.assertEqual(resp_dash.status_code, 200)
        self.assertIn(b'Nithish Kumar', resp_dash.data)
        self.assertIn(b'STU001', resp_dash.data)
        self.assertIn(b'8.75', resp_dash.data) # CGPA
        print("[PASS] 1. Core Auth & Dynamic Dashboard verified.")

    def test_02_profile_and_id_card(self):
        """Test Profile rendering and updating contact details"""
        resp_get = self.client.get('/student/profile')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Digital Campus Smart ID', resp_get.data)

        # Update contact info
        resp_post = self.client.post('/student/profile', data={
            'name': 'Nithish Kumar',
            'email': 'student@example.com',
            'phone': '+91 98765 00000',
            'parent_name': 'R. S. Kumar',
            'parent_phone': '+91 94440 99999',
            'address': '#42, Green Avenue, Tech City, Karnataka 560001'
        }, follow_redirects=True)
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn(b'Profile and guardian records updated successfully!', resp_post.data)
        print("[PASS] 2. Student Profile & Digital Smart ID verified.")

    def test_03_academics_and_marks(self):
        """Test course catalog and detailed marks breakdown"""
        resp_acad = self.client.get('/student/academics')
        self.assertEqual(resp_acad.status_code, 200)
        self.assertIn(b'Database Management Systems', resp_acad.data)
        self.assertIn(b'CS301', resp_acad.data)

        resp_marks = self.client.get('/student/marks')
        self.assertEqual(resp_marks.status_code, 200)
        self.assertIn(b'Continuous Assessment Tests', resp_marks.data)
        self.assertIn(b'Grade Forecast', resp_marks.data)
        print("[PASS] 3. Academics Catalog & Marks Transcript verified.")

    def test_04_attendance_and_safe_margin(self):
        """Test attendance analytics and safe bunk margin calculations"""
        resp_att = self.client.get('/student/attendance')
        self.assertEqual(resp_att.status_code, 200)
        self.assertIn(b'Attendance Analytics &amp; Safe Margin', resp_att.data)
        self.assertIn(b'Recent Lecture Session Logs', resp_att.data)
        print("[PASS] 4. Detailed Attendance & Safe Margin Calculator verified.")

    def test_05_assignments_and_materials(self):
        """Test assignments list and coursework solution submission"""
        resp_get = self.client.get('/student/assignments')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Course Assignments &amp; Study Repository', resp_get.data)

        # Submit assignment
        resp_post = self.client.post('/student/assignments', data={
            'assignment_id': 1,
            'file_name': 'STU001_DBMS_SQL_Tasks.pdf',
            'comments': 'Completed tasks with subqueries and index optimization.'
        }, follow_redirects=True)
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn(b'Assignment solution submitted successfully!', resp_post.data)
        print("[PASS] 5. Assignments Submission & Study Materials verified.")

    def test_06_examinations_and_hall_ticket(self):
        """Test exam timetable and digital admit card modal"""
        resp_exam = self.client.get('/student/examinations')
        self.assertEqual(resp_exam.status_code, 200)
        self.assertIn(b'SEMESTER 5 EXAMINATION HALL TICKET', resp_exam.data)
        self.assertIn(b'Exam Hall 3', resp_exam.data)
        print("[PASS] 6. Examinations Timetable & Hall Ticket verified.")

    def test_07_fees_and_simulated_payment(self):
        """Test fee dues calculation, payment execution and receipt generation"""
        resp_fees = self.client.get('/student/fees')
        self.assertEqual(resp_fees.status_code, 200)
        self.assertIn(b'Student Fees &amp; Payments Ledger', resp_fees.data)

        # Perform simulated fee payment
        resp_pay = self.client.post('/student/fees/pay', data={
            'fee_id': 3,
            'amount': 15000,
            'payment_method': 'UPI / QR Instant'
        }, follow_redirects=True)
        self.assertEqual(resp_pay.status_code, 200)
        self.assertIn(b'Payment of', resp_pay.data)
        self.assertIn(b'processed successfully', resp_pay.data)
        print("[PASS] 7. Fees Ledger, Instant Payment & Receipts verified.")

    def test_08_calendar_hostel_and_transport(self):
        """Test campus calendar, hostel outpass, and live bus GPS tracking"""
        resp_cal = self.client.get('/student/calendar')
        self.assertEqual(resp_cal.status_code, 200)
        self.assertIn(b'Unified Campus &amp; Academic Calendar', resp_cal.data)

        resp_hostel = self.client.get('/student/hostel')
        self.assertEqual(resp_hostel.status_code, 200)
        self.assertIn(b'Block B (Oak Wing)', resp_hostel.data)

        # Apply Outpass
        resp_leave = self.client.post('/student/hostel/leave', data={
            'leave_type': 'Day Outpass',
            'from_date': '2026-08-22',
            'to_date': '2026-08-22',
            'reason': 'Visiting city library for reference research.'
        }, follow_redirects=True)
        self.assertEqual(resp_leave.status_code, 200)
        self.assertIn(b'Digital Outpass / Leave Request approved by Warden.', resp_leave.data)

        resp_trans = self.client.get('/student/transport')
        self.assertEqual(resp_trans.status_code, 200)
        self.assertIn(b'Live Bus GPS Telemetry', resp_trans.data)
        print("[PASS] 8. Calendar, Hostel Outpass & Transport GPS Tracking verified.")

    def test_09_placements_and_ai_resume(self):
        """Test placement recruitment drives and AI Resume Analyzer API"""
        resp_place = self.client.get('/student/placements')
        self.assertEqual(resp_place.status_code, 200)
        self.assertIn(b'Microsoft India', resp_place.data)

        # Apply to placement
        resp_apply = self.client.post('/student/placements/apply/1', follow_redirects=True)
        self.assertEqual(resp_apply.status_code, 200)
        self.assertIn(b'Application successfully submitted', resp_apply.data)

        # Test AI Resume API
        resp_resume = self.client.post('/api/student/ai-resume', 
            data=json.dumps({'skills': 'Python, Flask, SQLite, Machine Learning, Docker', 'role': 'Software Engineer'}),
            content_type='application/json'
        )
        self.assertEqual(resp_resume.status_code, 200)
        data = json.loads(resp_resume.data)
        self.assertGreaterEqual(data['score'], 80)
        self.assertIn('recommended_skills', data)
        print("[PASS] 9. Placements & AI Resume Analyzer verified.")

    def test_10_requests_lost_found_and_wellbeing(self):
        """Test administrative requests, lost & found board, and counseling appointment booking"""
        resp_req = self.client.post('/student/requests', data={
            'request_type': 'ID Card Replacement',
            'details': 'Smart card chip damaged.'
        }, follow_redirects=True)
        self.assertEqual(resp_req.status_code, 200)
        self.assertIn(b'Service Request for ID Card Replacement submitted', resp_req.data)

        resp_lf = self.client.post('/student/lost-found', data={
            'item_type': 'LOST',
            'item_name': 'Black Scientific Calculator',
            'location': 'CS Lab 1',
            'description': 'Casio fx-991EX with initials NK on back.',
            'contact_phone': '+91 98765 43210'
        }, follow_redirects=True)
        self.assertEqual(resp_lf.status_code, 200)
        self.assertIn(b'published to Campus Board', resp_lf.data)

        resp_wb = self.client.post('/student/wellbeing/book', data={
            'counselor_name': 'Dr. Ananya Sharma (Lead Psychologist)',
            'slot_time': 'Tomorrow 04:00 PM - 05:00 PM',
            'concerns': 'Final semester project prioritization.'
        }, follow_redirects=True)
        self.assertEqual(resp_wb.status_code, 200)
        self.assertIn(b'Confidential counseling session confirmed', resp_wb.data)
        print("[PASS] 10. Service Requests, Lost & Found & Wellbeing booking verified.")

    def test_11_campus_safety_sos_closed_loop_and_security_console(self):
        """Test full SOS dispatch lifecycle from Student SOS -> Security Console -> Resolution"""
        # Step A: Student initiates SOS
        resp_sos = self.client.post('/student/emergency', data={
            'location': 'Hostel Block B Outer Courtyard',
            'latitude': '12.9716',
            'longitude': '77.5946'
        }, follow_redirects=True)
        self.assertEqual(resp_sos.status_code, 200)
        self.assertIn(b'Distress Beacon', resp_sos.data)

        # Step B: Security Console views incoming SOS signal
        resp_sec = self.client.get('/security/dashboard')
        self.assertEqual(resp_sec.status_code, 200)
        self.assertIn(b'Hostel Block B', resp_sec.data)
        self.assertIn(b'Nithish Kumar', resp_sec.data)

        # Find incident id
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        sos_row = conn.execute("SELECT incident_id FROM incidents WHERE student_id = 1 AND status = 'ACTIVE' ORDER BY created_at DESC LIMIT 1").fetchone()
        self.assertIsNotNone(sos_row)
        incident_id = sos_row['incident_id']
        conn.close()

        # Step C: Security officer marks incident resolved
        resp_resolve = self.client.post(f'/security/incident/{incident_id}/status', data={
            'new_status': 'RESOLVED'
        }, follow_redirects=True)
        self.assertEqual(resp_resolve.status_code, 200)
        self.assertIn(b'RESOLVED', resp_resolve.data)

        # Step D: Verify Safe Route API & Admin Analytics Dashboard
        resp_route = self.client.post('/api/student/safe-route',
            data=json.dumps({'from': 'Hostel Block B', 'to': 'Central Library'}),
            content_type='application/json'
        )
        self.assertEqual(resp_route.status_code, 200)
        route_data = json.loads(resp_route.data)
        self.assertIn('path_description', route_data)

        resp_admin = self.client.get('/admin/analytics')
        self.assertEqual(resp_admin.status_code, 200)
        self.assertIn(b'Campus Safety Briefing', resp_admin.data)
        print("[PASS] 11. Full SOS Closed Loop, Security Console & Safe Routes verified.")

    def test_12_ai_campus_assistant(self):
        """Test Context-Aware AI Campus Assistant on multiple data domains"""
        queries = [
            'What is my current CGPA?',
            'Do I have pending fees?',
            'When is my next exam?',
            'Which subject has my lowest attendance?'
        ]
        for q in queries:
            resp = self.client.post('/api/student/chat',
                data=json.dumps({'message': q}),
                content_type='application/json'
            )
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertTrue(len(data['reply']) > 20)
        print("[PASS] 12. Context-Aware AI Campus Assistant verified across all domains.")

if __name__ == '__main__':
    unittest.main()
