"""
Unit and Integration Test Suite for CampusGuard AI Authentication System
"""
import unittest
import os
import sqlite3
from app import app, init_db, DATABASE_FILE

class TestCampusGuardAuth(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key-123'
        self.client = app.test_client()
        init_db()
        conn = sqlite3.connect(DATABASE_FILE)
        conn.execute("DELETE FROM login_attempts")
        conn.execute("UPDATE students SET name = 'Nithish Nagaraj', email = 'student@example.com' WHERE register_number = 'STU001'")
        conn.commit()
        conn.close()

    def test_1_home_page_student_link(self):
        """Test 1: GET / contains link to Student Portal /student/login"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'/student/login', response.data)
        self.assertIn(b'Student Portal', response.data)
        print("[PASS] Test 1: Home landing page renders with Student Portal link.")

    def test_2_and_3_valid_login_and_dashboard_data(self):
        """Test 2 & 3: Valid demo credentials login & dashboard profile verification"""
        response = self.client.post('/student/login', data={
            'register_number': 'STU001',
            'password': 'Student@123'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        # Verify student details are displayed in HTML
        self.assertIn(b'Nithish Nagaraj', response.data)
        self.assertIn(b'STU001', response.data)
        self.assertIn(b'Computer Science', response.data)
        self.assertIn(b'student@example.com', response.data)
        print("[PASS] Test 2 & 3: Valid login successfully loads dashboard with live DB info.")

    def test_4_invalid_password(self):
        """Test 4: Invalid password shows generic error and does not redirect to dashboard"""
        response = self.client.post('/student/login', data={
            'register_number': 'STU001',
            'password': 'WrongPassword999'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid register number or password', response.data)
        self.assertNotIn(b'Welcome, Nithish Nagaraj', response.data)
        print("[PASS] Test 4: Invalid password displays correct error message without revealing specifics.")

    def test_5_empty_fields(self):
        """Test 5: Empty fields validation"""
        response = self.client.post('/student/login', data={
            'register_number': '',
            'password': ''
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Please enter both Register Number and Password', response.data)
        print("[PASS] Test 5: Empty field validation caught on backend.")

    def test_6_unauthenticated_dashboard_access(self):
        """Test 6: /student/dashboard without logging in redirects to /student/login"""
        response = self.client.get('/student/dashboard', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/student/login', response.headers['Location'])
        
        # Follow redirect and check message
        redirect_response = self.client.get('/student/dashboard', follow_redirects=True)
        self.assertIn(b'Please log in to access the Student Portal', redirect_response.data)
        print("[PASS] Test 6: Unauthenticated dashboard access is blocked and redirected to login.")

    def test_7_and_8_logout_and_post_logout_access(self):
        """Test 7 & 8: Login -> Dashboard -> Logout -> verify dashboard blocked after logout"""
        # Step A: Log in
        self.client.post('/student/login', data={
            'register_number': 'STU001',
            'password': 'Student@123'
        })
        
        # Step B: Logout
        logout_resp = self.client.get('/student/logout', follow_redirects=True)
        self.assertEqual(logout_resp.status_code, 200)
        self.assertIn(b'You have been signed out successfully', logout_resp.data)

        # Step C: Attempt to access dashboard again after logout
        post_logout_access = self.client.get('/student/dashboard', follow_redirects=False)
        self.assertEqual(post_logout_access.status_code, 302)
        self.assertIn('/student/login', post_logout_access.headers['Location'])
        print("[PASS] Test 7 & 8: Logout clears session and blocks subsequent dashboard access.")

    def test_9_cache_headers(self):
        """Test 9: Verify Cache-Control security headers exist"""
        response = self.client.get('/student/login')
        self.assertIn('no-cache', response.headers.get('Cache-Control', ''))
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))
        print("[PASS] Test 9: Security Cache-Control headers verified.")

if __name__ == '__main__':
    unittest.main()
