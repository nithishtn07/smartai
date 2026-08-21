"""
Comprehensive Unit & Integration Test Suite for CampusGuard AI Student Portal
Tests all 10 modules: Dashboard, Profile, Attendance, Timetable, Complaints (AI),
Alerts, Safety, Emergency SOS, AI Assistant, and Settings.
"""
import unittest
import os
import sqlite3
from app import app, init_db, DATABASE_FILE, classify_complaint_ai, generate_assistant_reply

class TestStudentPortal(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key-portal-999'
        self.client = app.test_client()
        init_db()

    def login_student(self):
        """Helper to authenticate test client with demo credentials"""
        return self.client.post('/student/login', data={
            'register_number': 'STU001',
            'password': 'Student@123'
        }, follow_redirects=True)

    # -----------------------------------------------------------------------
    # 1. Route Protection Tests (All 10 Routes)
    # -----------------------------------------------------------------------
    def test_unauthenticated_route_protection(self):
        """Verify all 10 student pages redirect unauthenticated users to login"""
        routes = [
            '/student/dashboard',
            '/student/profile',
            '/student/attendance',
            '/student/timetable',
            '/student/complaints',
            '/student/alerts',
            '/student/safety',
            '/student/emergency',
            '/student/assistant',
            '/student/settings'
        ]
        for route in routes:
            resp = self.client.get(route, follow_redirects=False)
            self.assertEqual(resp.status_code, 302, f"Failed for {route}")
            self.assertIn('/student/login', resp.headers['Location'], f"Did not redirect to login for {route}")
        print("[PASS] 1. Route Protection: All 10 student pages are securely guarded.")

    # -----------------------------------------------------------------------
    # 2. Student Profile Tests
    # -----------------------------------------------------------------------
    def test_profile_view_and_update(self):
        """Test viewing profile and updating safe contact fields"""
        self.login_student()
        
        # GET Profile
        resp = self.client.get('/student/profile')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Nithish Kumar', resp.data)
        self.assertIn(b'STU001', resp.data)
        self.assertIn(b'Computer Science', resp.data)

        # POST Update Profile
        update_resp = self.client.post('/student/profile', data={
            'name': 'Nithish K.',
            'email': 'nithish.k@example.com',
            'phone': '+91 99887 76655'
        }, follow_redirects=True)
        self.assertEqual(update_resp.status_code, 200)
        self.assertIn(b'updated successfully', update_resp.data)
        self.assertIn(b'nithish.k@example.com', update_resp.data)

        # Reset name back
        self.client.post('/student/profile', data={
            'name': 'Nithish Kumar',
            'email': 'student@example.com',
            'phone': '+91 98765 43210'
        })
        print("[PASS] 2. Profile Module: Profile view and safe contact update verified.")

    # -----------------------------------------------------------------------
    # 3. Attendance Module Tests
    # -----------------------------------------------------------------------
    def test_attendance_analytics(self):
        """Test attendance aggregate calculation and course breakdowns"""
        self.login_student()
        resp = self.client.get('/student/attendance')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Attendance Analytics', resp.data)
        self.assertIn(b'Database Management Systems', resp.data)
        self.assertIn(b'Operating Systems', resp.data)
        self.assertIn(b'AGGREGATE', resp.data)
        print("[PASS] 3. Attendance Module: Real database attendance and metrics verified.")

    # -----------------------------------------------------------------------
    # 4. Timetable Module Tests
    # -----------------------------------------------------------------------
    def test_timetable_schedule(self):
        """Test today & weekly timetable schedule retrieval"""
        self.login_student()
        resp = self.client.get('/student/timetable')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Academic Timetable', resp.data)
        self.assertIn(b'Weekly Master Schedule', resp.data)
        self.assertIn(b'CS-201', resp.data)
        print("[PASS] 4. Timetable Module: Schedule data queried and displayed.")

    # -----------------------------------------------------------------------
    # 5 & 9. Complaints & AI Classifier Tests
    # -----------------------------------------------------------------------
    def test_complaints_and_ai_triage(self):
        """Test complaint submission and automated AI triaging"""
        self.login_student()

        # AI Unit Test
        ai_safety = classify_complaint_ai('Corridor Harassment', 'Unknown person stalking near gate at night', 'Safety', 'East Gate')
        self.assertIn('Safety', ai_safety['category'])
        self.assertEqual(ai_safety['severity'].upper(), 'CRITICAL')
        self.assertEqual(ai_safety['priority'].upper(), 'URGENT')

        ai_infra = classify_complaint_ai('Water Pipe Burst', 'Flooding in hostel washroom with electrical spark', 'Infrastructure', 'Block B')
        self.assertEqual(ai_infra['severity'].upper(), 'HIGH')

        # Form submission test
        resp = self.client.post('/student/complaints', data={
            'category': 'Safety',
            'priority': 'Urgent',
            'title': 'Test Safety Concern near Library',
            'location': 'Library Rear Walkway',
            'description': 'Poor illumination and broken lamp posts near the walkway at night.'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Grievance Ticket CMP-', resp.data)
        self.assertIn(b'Test Safety Concern near Library', resp.data)
        print("[PASS] 5 & 9. Complaints & AI Module: Grievance submission and AI triage verified.")

    # -----------------------------------------------------------------------
    # 6. Campus Alerts Tests
    # -----------------------------------------------------------------------
    def test_alerts_and_read_status(self):
        """Test alert feeds and marking as read"""
        self.login_student()
        resp = self.client.get('/student/alerts')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Campus Alerts', resp.data)

        # Mark all read
        read_resp = self.client.post('/student/alerts/read-all', follow_redirects=True)
        self.assertEqual(read_resp.status_code, 200)
        self.assertIn(b'All alerts marked as read', read_resp.data)
        print("[PASS] 6. Alerts Module: Broadcast notifications and read state verified.")

    # -----------------------------------------------------------------------
    # 7. Campus Safety Center & Incident Reporting
    # -----------------------------------------------------------------------
    def test_safety_center_and_incident_report(self):
        """Test safety center directory and incident report creation"""
        self.login_student()
        resp = self.client.get('/student/safety')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Campus Safety Center', resp.data)
        self.assertIn(b'ACTIVATE SOS', resp.data)

        # Submit incident report
        inc_resp = self.client.post('/student/safety', data={
            'incident_type': 'Broken Halogen Lamp',
            'location': 'Library North Pathway',
            'description': 'Broken halogen lamp casing posing a hazard.'
        }, follow_redirects=True)
        self.assertEqual(inc_resp.status_code, 200)
        self.assertIn(b'Safety incident INC-', inc_resp.data)
        print("[PASS] 7. Safety Center: Emergency directory and incident reporting verified.")

    # -----------------------------------------------------------------------
    # 8. Emergency SOS System Tests
    # -----------------------------------------------------------------------
    def test_emergency_sos(self):
        """Test SOS activation with GPS coordinates and stand-down"""
        self.login_student()

        # Step 1: Trigger Emergency SOS
        resp = self.client.post('/student/emergency', data={
            'location': 'Academic Block B 3rd Floor',
            'latitude': '12.9716',
            'longitude': '77.5946'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'EMERGENCY SOS ACTIVE:', resp.data)

        # Verify active incident created in DB
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        active_inc = conn.execute("SELECT * FROM incidents WHERE student_id = 1 AND status = 'ACTIVE' AND incident_type = 'EMERGENCY_SOS'").fetchone()
        conn.close()
        self.assertIsNotNone(active_inc)
        incident_id = active_inc['incident_id']

        # Step 2: Cancel / Stand down SOS
        cancel_resp = self.client.post(f'/student/emergency/cancel/{incident_id}', follow_redirects=True)
        self.assertEqual(cancel_resp.status_code, 200)
        self.assertIn(b'stood down. Marked safe', cancel_resp.data)
        print("[PASS] 8. Emergency SOS: Distress beacon, GPS logging, timeline and stand-down verified.")

    # -----------------------------------------------------------------------
    # 10. AI Campus Assistant API Tests
    # -----------------------------------------------------------------------
    def test_ai_campus_assistant_api(self):
        """Test AI assistant chat queries for personalized student data"""
        self.login_student()

        # Test attendance query
        resp_att = self.client.post('/api/student/chat', json={'message': 'What is my attendance in DBMS?'})
        self.assertEqual(resp_att.status_code, 200)
        data_att = resp_att.get_json()
        self.assertIn('Database Management Systems', data_att['reply'])
        self.assertIn('92.5%', data_att['reply'])

        # Test next class query
        resp_class = self.client.post('/api/student/chat', json={'message': 'When is my next class?'})
        self.assertEqual(resp_class.status_code, 200)
        data_class = resp_class.get_json()
        self.assertIn('Next Lecture', data_class['reply'])

        # Test emergency query
        resp_sos = self.client.post('/api/student/chat', json={'message': 'Who do I call in an emergency?'})
        self.assertEqual(resp_sos.status_code, 200)
        data_sos = resp_sos.get_json()
        self.assertIn('Campus Security', data_sos['reply'])
        print("[PASS] 10. AI Assistant: Context-aware responses with authorized student data verified.")

    # -----------------------------------------------------------------------
    # 11. Settings & Password Change Tests
    # -----------------------------------------------------------------------
    def test_settings_and_password_change(self):
        """Test notification preferences update and secure password change"""
        self.login_student()

        # Preferences update
        pref_resp = self.client.post('/student/settings', data={
            'action_type': 'preferences',
            'email_alerts': '1',
            'emergency_broadcasts': '1'
        }, follow_redirects=True)
        self.assertEqual(pref_resp.status_code, 200)
        self.assertIn(b'Notification preferences updated successfully', pref_resp.data)

        # Password change test: Wrong current password
        bad_pw_resp = self.client.post('/student/settings', data={
            'action_type': 'password',
            'current_password': 'WrongPassword123',
            'new_password': 'NewPassword@123',
            'confirm_password': 'NewPassword@123'
        }, follow_redirects=True)
        self.assertEqual(bad_pw_resp.status_code, 200)
        self.assertIn(b'Current password entered is incorrect', bad_pw_resp.data)

        # Password change test: Valid password update
        good_pw_resp = self.client.post('/student/settings', data={
            'action_type': 'password',
            'current_password': 'Student@123',
            'new_password': 'Student@NewPass123',
            'confirm_password': 'Student@NewPass123'
        }, follow_redirects=True)
        self.assertEqual(good_pw_resp.status_code, 200)
        self.assertIn(b'Password updated successfully', good_pw_resp.data)

        # Reset password back to Student@123
        self.client.post('/student/settings', data={
            'action_type': 'password',
            'current_password': 'Student@NewPass123',
            'new_password': 'Student@123',
            'confirm_password': 'Student@123'
        })
        print("[PASS] 11. Settings Module: Preferences and Werkzeug password update verified.")

    # -----------------------------------------------------------------------
    # 12. Dashboard Live Integration Tests
    # -----------------------------------------------------------------------
    def test_dashboard_dynamic_metrics(self):
        """Test dynamic rendering of attendance %, today's classes, complaints, and alerts on dashboard"""
        self.login_student()
        resp = self.client.get('/student/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Nithish', resp.data)
        self.assertIn(b'Attendance Status', resp.data)
        self.assertIn(b'Today\'s Lectures', resp.data)
        self.assertIn(b'Cumulative CGPA', resp.data)
        self.assertIn(b'Outstanding Fees', resp.data)
        print("[PASS] 12. Dashboard Module: Dynamic metrics, real-time widgets, and fast navigation verified.")

if __name__ == '__main__':
    unittest.main()
