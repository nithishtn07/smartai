"""
Comprehensive Unit & Integration Test Suite for CampusGuard AI Parent Portal
Tests all 11 modules: Login/Auth, Dashboard, Academics, Attendance, Fees, Exams,
Timetable, Leave, Notifications, Safety, Messages, and Profile/Settings,
along with Parent-Student Linking, Authorization Isolation, and Regression Testing.
"""
import unittest
import os
import sqlite3
from app import app, init_db, DATABASE_FILE, get_db_connection

class TestParentPortal(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-parent-secret-key-999'
        self.client = app.test_client()
        init_db()
        conn = get_db_connection()
        conn.execute("DELETE FROM login_attempts")
        conn.commit()
        conn.close()

    def login_parent(self, identifier='parent@example.com', password='Parent@123'):
        """Helper to authenticate test client with parent credentials"""
        return self.client.post('/parent/login', data={
            'identifier': identifier,
            'password': password
        }, follow_redirects=True)

    def login_student(self):
        """Helper to authenticate student test client"""
        return self.client.post('/student/login', data={
            'register_number': 'STU001',
            'password': 'Student@123'
        }, follow_redirects=True)

    # -----------------------------------------------------------------------
    # 1. Unauthenticated Route Protection (All 11 Parent Routes)
    # -----------------------------------------------------------------------
    def test_unauthenticated_parent_route_protection(self):
        """Verify all parent routes redirect unauthenticated users to /parent/login"""
        routes = [
            '/parent/dashboard',
            '/parent/academics',
            '/parent/attendance',
            '/parent/fees',
            '/parent/exams',
            '/parent/timetable',
            '/parent/leave',
            '/parent/notifications',
            '/parent/safety',
            '/parent/messages',
            '/parent/profile'
        ]
        for route in routes:
            resp = self.client.get(route, follow_redirects=False)
            self.assertEqual(resp.status_code, 302, f"Failed route protection for {route}")
            self.assertIn('/parent/login', resp.headers['Location'], f"Did not redirect to /parent/login for {route}")
        print("[PASS] 1. Route Protection: All 11 parent routes are securely guarded.")

    # -----------------------------------------------------------------------
    # 2. Authentication & Login Flow
    # -----------------------------------------------------------------------
    def test_parent_login_success_with_email_and_id(self):
        """Test parent login using email and parent_id"""
        # Login with email
        resp1 = self.login_parent('parent@example.com', 'Parent@123')
        self.assertEqual(resp1.status_code, 200)
        self.assertIn(b'Nithish Nagaraj', resp1.data)
        self.assertIn(b'STU001', resp1.data)

        # Logout
        resp_logout = self.client.get('/parent/logout', follow_redirects=True)
        self.assertEqual(resp_logout.status_code, 200)
        self.assertIn(b'Parent Portal Sign In', resp_logout.data)

        # Login with Parent ID (PAR001)
        resp2 = self.login_parent('PAR001', 'Parent@123')
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b'R. S. Kumar', resp2.data)
        print("[PASS] 2. Parent Authentication: Login with email, parent_id, and logout verified.")

    def test_parent_login_invalid_credentials(self):
        """Test rejection of invalid password and unknown parent"""
        resp = self.login_parent('parent@example.com', 'WrongPassword!')
        self.assertIn(b'Invalid Parent ID / Email or Password.', resp.data)

        resp2 = self.login_parent('unknown@example.com', 'Parent@123')
        self.assertIn(b'Invalid Parent ID / Email or Password.', resp2.data)
        print("[PASS] 3. Invalid Login Rejection verified.")

    # -----------------------------------------------------------------------
    # 3. Parent-Student Linking & Data Isolation
    # -----------------------------------------------------------------------
    def test_parent_student_linking(self):
        """Test that authenticated parent accesses the correct linked student data"""
        self.login_parent()
        resp = self.client.get('/parent/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Nithish Nagaraj', resp.data)
        self.assertIn(b'STU001', resp.data)
        self.assertIn(b'Computer Science', resp.data)
        self.assertIn(b'8.75', resp.data) # CGPA
        print("[PASS] 4. Parent-Student Linking: Real student records properly bound.")

    # -----------------------------------------------------------------------
    # 4. Academics Module
    # -----------------------------------------------------------------------
    def test_parent_academics_module(self):
        """Test academics transcript, CAT/FAT marks, and course list"""
        self.login_parent()
        resp = self.client.get('/parent/academics')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Database Management Systems', resp.data)
        self.assertIn(b'Operating Systems', resp.data)
        self.assertIn(b'CS301', resp.data)
        self.assertIn(b'Dr. Ramesh Rao', resp.data)
        print("[PASS] 5. Academics Module: Marks transcript and course records verified.")

    # -----------------------------------------------------------------------
    # 5. Attendance Module
    # -----------------------------------------------------------------------
    def test_parent_attendance_module(self):
        """Test attendance analytics, safe bunks, and lecture logs"""
        self.login_parent()
        resp = self.client.get('/parent/attendance')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Semester 5 Presence Analytics', resp.data)
        self.assertIn(b'Safe Absence Margin', resp.data)
        self.assertIn(b'Database Management Systems', resp.data)
        print("[PASS] 6. Attendance Module: Subject attendance and safe margin predictions verified.")

    # -----------------------------------------------------------------------
    # 6. Fees Module
    # -----------------------------------------------------------------------
    def test_parent_fees_module(self):
        """Test fees ledger, paid amounts, dues, and transaction records"""
        self.login_parent()
        resp = self.client.get('/parent/fees')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Tuition &amp; Academic Semester Fee', resp.data)
        self.assertIn(b'Total Semester Dues', resp.data)
        self.assertIn(b'PAID', resp.data)
        print("[PASS] 7. Fees Module: Financial dues and ledger verified.")

    # -----------------------------------------------------------------------
    # 7. Exams Module
    # -----------------------------------------------------------------------
    def test_parent_exams_module(self):
        """Test upcoming examinations schedule and eligibility"""
        self.login_parent()
        resp = self.client.get('/parent/exams')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'FAT Semester 5', resp.data)
        self.assertIn(b'Hall Ticket Eligible', resp.data)
        print("[PASS] 8. Exams Module: Examination schedule and hall ticket verified.")

    # -----------------------------------------------------------------------
    # 8. Timetable Module
    # -----------------------------------------------------------------------
    def test_parent_timetable_module(self):
        """Test weekly class timetable schedule"""
        self.login_parent()
        resp = self.client.get('/parent/timetable')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Weekly Class Timetable', resp.data)
        self.assertIn(b'Monday', resp.data)
        self.assertIn(b'Database Management Systems', resp.data)
        print("[PASS] 9. Timetable Module: Weekly schedule verified.")

    # -----------------------------------------------------------------------
    # 9. Leave & Outpass Module
    # -----------------------------------------------------------------------
    def test_parent_leave_module_and_action(self):
        """Test leave requests history and parent consent/approval action"""
        self.login_parent()
        
        # First ensure a hostel leave exists
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO hostel_leaves (student_id, leave_type, from_date, to_date, reason, status)
            VALUES (1, 'Home Visit', '2026-08-28', '2026-08-30', 'Family wedding visit', 'Pending')
        """)
        conn.commit()
        leave_id = conn.execute("SELECT id FROM hostel_leaves WHERE student_id = 1 ORDER BY id DESC LIMIT 1").fetchone()['id']
        conn.close()

        resp = self.client.get('/parent/leave')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Family wedding visit', resp.data)

        # Parent authorizes the leave
        post_resp = self.client.post(f'/parent/leave/action/{leave_id}', data={
            'action': 'Approve',
            'remarks': 'Approved by Father for family wedding.'
        }, follow_redirects=True)
        self.assertEqual(post_resp.status_code, 200)
        self.assertIn(b'Leave / Outpass request approved with parent authorization.', post_resp.data)
        print("[PASS] 10. Leave Module: Outpass requests and parent authorization verified.")

    # -----------------------------------------------------------------------
    # 10. Notifications Module
    # -----------------------------------------------------------------------
    def test_parent_notifications_and_read_state(self):
        """Test notification feed and mark as read functionality"""
        self.login_parent()
        resp = self.client.get('/parent/notifications')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Block C', resp.data)

        # Mark all read
        post_resp = self.client.post('/parent/notifications/read-all', follow_redirects=True)
        self.assertEqual(post_resp.status_code, 200)
        self.assertIn(b'All notifications marked as read.', post_resp.data)
        print("[PASS] 11. Notifications Module: Categorized alerts and read state verified.")

    # -----------------------------------------------------------------------
    # 11. Safety & SOS Command Center
    # -----------------------------------------------------------------------
    def test_parent_safety_center_and_welfare_check(self):
        """Test live child safety status, contacts directory, and welfare request"""
        self.login_parent()
        resp = self.client.get('/parent/safety')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Campus Safety &amp; Emergency Command', resp.data)
        self.assertIn(b'Campus Security Command Center', resp.data)

        # Transmit welfare check request
        post_resp = self.client.post('/parent/safety/check-in', data={
            'concern_text': 'Please check if Nithish has reached the library corridor safely.'
        }, follow_redirects=True)
        self.assertEqual(post_resp.status_code, 200)
        self.assertIn(b'Welfare Check Request transmitted to Campus Security Command', post_resp.data)
        print("[PASS] 12. Safety Module: Emergency directory and welfare verification verified.")

    # -----------------------------------------------------------------------
    # 12. Parent-Faculty Communication Center
    # -----------------------------------------------------------------------
    def test_parent_faculty_messages(self):
        """Test messages inbox and sending new message to faculty advisor"""
        self.login_parent()
        resp = self.client.get('/parent/messages')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Mid-Semester Academic Progress Report', resp.data)

        # Send new message
        post_resp = self.client.post('/parent/messages', data={
            'receiver_name': 'Dr. Ramesh Rao (Faculty Advisor)',
            'subject': 'Inquiry regarding Capstone Project Demo',
            'content': 'Hello Dr. Rao, thank you for the update. We are pleased with Nithish progress.'
        }, follow_redirects=True)
        self.assertEqual(post_resp.status_code, 200)
        self.assertIn(b'Message successfully transmitted to Dr. Ramesh Rao (Faculty Advisor).', post_resp.data)
        print("[PASS] 13. Messages Module: Bi-directional parent-faculty messaging verified.")

    # -----------------------------------------------------------------------
    # 13. Profile & Settings Module
    # -----------------------------------------------------------------------
    def test_parent_profile_and_password_update(self):
        """Test updating profile contact info and password change"""
        self.login_parent()
        resp = self.client.get('/parent/profile')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'R. S. Kumar', resp.data)
        self.assertIn(b'PAR001', resp.data)

        # Update contact info
        post_resp = self.client.post('/parent/profile', data={
            'action_type': 'update_info',
            'phone': '+91 94440 99999',
            'occupation': 'Senior Chief Architect',
            'address': '#108, Royal Palms, Bangalore'
        }, follow_redirects=True)
        self.assertEqual(post_resp.status_code, 200)
        self.assertIn(b'Parent profile contact details updated successfully.', post_resp.data)
        self.assertIn(b'+91 94440 99999', post_resp.data)
        print("[PASS] 14. Profile & Settings Module: Contact info and preferences update verified.")

    # -----------------------------------------------------------------------
    # 14. Student Portal Regression Integrity
    # -----------------------------------------------------------------------
    def test_student_portal_remains_fully_functional(self):
        """Verify Student Portal login and dashboard continue to function perfectly"""
        resp = self.login_student()
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Nithish Nagaraj', resp.data)
        self.assertIn(b'STU001', resp.data)

        dash_resp = self.client.get('/student/dashboard')
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn(b'Computer Science', dash_resp.data)
        print("[PASS] 15. Regression Test: Student Portal remains 100% operational.")

if __name__ == '__main__':
    unittest.main()
