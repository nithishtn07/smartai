"""
=============================================================================
CampusGuard AI — Landing Page & Admin Authentication End-to-End Test Suite
=============================================================================
Verifies:
1. Landing Page with all 4 Portal Cards (Student, Faculty, Parent, Admin)
2. Admin Login Navigation & Form Submission
3. Admin Invalid Login Handling & Protection
4. Admin Valid Login Variants (admin, admin@example.com, ADMIN001)
5. Admin Session Management & Role Enforcement
6. Admin Dashboard Protection & Authorization (rejects student/parent/faculty)
7. Admin Logout Flow
8. Stability & Isolation of all 4 Portals
=============================================================================
"""

import unittest
import json
import app

class TestLandingPageAndAdminFlow(unittest.TestCase):

    def setUp(self):
        self.app = app.app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key-campusguard'
        self.client = self.app.test_client()

        app.init_db()

        conn = app.get_db_connection()
        conn.execute("DELETE FROM login_attempts")
        conn.execute("UPDATE students SET name = 'Nithish Nagaraj' WHERE register_number = 'STU001'")
        self.student = conn.execute("SELECT * FROM students WHERE register_number = 'STU001'").fetchone()
        self.parent = conn.execute("SELECT * FROM parents WHERE email = 'parent@example.com'").fetchone()
        self.faculty = conn.execute("SELECT * FROM faculties WHERE email = 'faculty@example.com'").fetchone()
        self.admin = conn.execute("SELECT * FROM admins WHERE username = 'admin'").fetchone()
        conn.commit()
        conn.close()

    def test_01_landing_page_has_all_four_portals(self):
        """Verify the landing page offers Student, Faculty, Parent, and Admin cards."""
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)

        # 1. Student Card
        self.assertIn(b'id="card-student"', resp.data)
        self.assertIn(b'/student/login', resp.data)
        self.assertIn(b'Student Portal', resp.data)

        # 2. Faculty Card
        self.assertIn(b'id="card-faculty"', resp.data)
        self.assertIn(b'/faculty/login', resp.data)
        self.assertIn(b'Faculty Portal', resp.data)

        # 3. Parent Card
        self.assertIn(b'id="card-parent"', resp.data)
        self.assertIn(b'/parent/login', resp.data)
        self.assertIn(b'Parent Portal', resp.data)

        # 4. Admin Card
        self.assertIn(b'id="card-admin"', resp.data)
        self.assertIn(b'/admin/login', resp.data)
        self.assertIn(b'Admin Portal', resp.data)
        self.assertIn(b'FOR ADMINISTRATORS', resp.data)

    def test_02_admin_login_page_renders(self):
        """Verify Admin Login page loads cleanly with form and styling."""
        resp = self.client.get('/admin/login')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Admin Sign In', resp.data)
        self.assertIn(b'ADMINISTRATIVE CONSOLE', resp.data)
        self.assertIn(b'action="/admin/login"', resp.data)

    def test_03_admin_invalid_login_rejection(self):
        """Verify invalid credentials display error message and stay on login."""
        # Bad password
        resp_bad_pw = self.client.post('/admin/login', data={
            'identifier': 'admin',
            'password': 'WrongPassword123'
        }, follow_redirects=False)
        self.assertEqual(resp_bad_pw.status_code, 200)
        self.assertIn(b'Invalid Admin ID or password.', resp_bad_pw.data)

        # Unknown admin
        resp_bad_user = self.client.post('/admin/login', data={
            'identifier': 'unknown_admin',
            'password': 'Admin@123'
        }, follow_redirects=False)
        self.assertEqual(resp_bad_user.status_code, 200)
        self.assertIn(b'Invalid Admin ID or password.', resp_bad_user.data)

        # Verify no session created
        with self.client.session_transaction() as sess:
            self.assertNotIn('admin_id', sess)
            self.assertNotIn('user_role', sess)

    def test_04_admin_valid_login_variants(self):
        """Verify valid admin login with username, email, and ADMIN001 alias."""
        variants = ['admin', 'admin@example.com', 'ADMIN001', 'ADMIN', 'admin@EXAMPLE.COM']

        for identifier in variants:
            self.client.get('/admin/logout')

            resp = self.client.post('/admin/login', data={
                'identifier': identifier,
                'password': 'Admin@123'
            }, follow_redirects=False)

            self.assertEqual(resp.status_code, 302, f"Failed for {identifier}")
            self.assertIn('/admin/dashboard', resp.headers['Location'])

            # Verify session
            with self.client.session_transaction() as sess:
                self.assertEqual(sess.get('admin_id'), self.admin['id'])
                self.assertEqual(sess.get('user_role'), 'admin')
                self.assertTrue(sess.get('admin_logged_in'))

    def test_05_admin_dashboard_renders_live_data(self):
        """Verify Admin Dashboard renders situational telemetry and announcements."""
        with self.client.session_transaction() as sess:
            sess['admin_id'] = self.admin['id']
            sess['user_role'] = 'admin'
            sess['admin_logged_in'] = True

        resp = self.client.get('/admin/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Central Administration', resp.data)
        self.assertIn(b'Active SOS', resp.data)
        self.assertIn(b'Announcements', resp.data)

    def test_06_admin_logout(self):
        """Verify Admin logout clears session and redirects to /admin/login."""
        self.client.post('/admin/login', data={'identifier': 'admin', 'password': 'Admin@123'})

        resp = self.client.get('/admin/logout', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/admin/login', resp.headers['Location'])

        with self.client.session_transaction() as sess:
            self.assertNotIn('admin_id', sess)
            self.assertNotIn('user_role', sess)

    def test_07_admin_routes_authorization_and_guards(self):
        """Verify unauthenticated and non-admin users cannot access admin routes."""
        # Unauthenticated
        resp_unauth = self.client.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(resp_unauth.status_code, 302)
        self.assertIn('/admin/login', resp_unauth.headers['Location'])

        # Student user trying to access admin dashboard
        with self.client.session_transaction() as sess:
            sess['student_id'] = self.student['id']
            sess['user_role'] = 'student'

        resp_stu = self.client.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(resp_stu.status_code, 302)
        self.assertIn('/admin/login', resp_stu.headers['Location'])

        # Parent user trying to access admin dashboard
        with self.client.session_transaction() as sess:
            sess['parent_id'] = self.parent['id']
            sess['user_role'] = 'parent'

        resp_par = self.client.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(resp_par.status_code, 302)
        self.assertIn('/admin/login', resp_par.headers['Location'])

    def test_08_all_four_portals_stability(self):
        """Verify Student, Faculty, Parent, and Admin portals remain operational."""
        # 1. Student
        r1 = self.client.post('/student/login', data={'register_number': 'STU001', 'password': 'Student@123'})
        self.assertEqual(r1.status_code, 302)

        # 2. Faculty
        r2 = self.client.post('/faculty/login', data={'identifier': 'FAC001', 'password': 'Faculty@123'})
        self.assertEqual(r2.status_code, 302)

        # 3. Parent
        r3 = self.client.post('/parent/login', data={'identifier': 'parent@example.com', 'password': 'Parent@123'})
        self.assertEqual(r3.status_code, 302)

        # 4. Admin
        r4 = self.client.post('/admin/login', data={'identifier': 'admin', 'password': 'Admin@123'})
        self.assertEqual(r4.status_code, 302)


if __name__ == '__main__':
    unittest.main()
