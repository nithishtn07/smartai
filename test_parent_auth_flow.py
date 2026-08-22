"""
=============================================================================
CampusGuard AI — Dedicated Parent Authentication & Flow Verification Test Suite
=============================================================================
Covers STEP 27 Test Scenarios (TEST A to TEST G) End-to-End:
- TEST A: Landing Page Parent button navigation
- TEST B: Invalid Parent credentials handling and error messages
- TEST C: Valid Parent credentials (Email, PAR001, P1001) authentication & redirect
- TEST D: Parent Dashboard data loading (Parent name, Linked student, Modules)
- TEST E: Parent Logout flow & session clearance
- TEST F: Protected route redirection when unauthenticated
- TEST G: Student, Faculty, and Admin Portal isolation and stability
=============================================================================
"""

import unittest
import json
import app

class TestParentAuthFlow(unittest.TestCase):

    def setUp(self):
        self.app = app.app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key-campusguard'
        self.client = self.app.test_client()

        # Initialize and seed database
        app.init_db()

        conn = app.get_db_connection()
        conn.execute("DELETE FROM login_attempts")
        conn.execute("UPDATE students SET name = 'Nithish Nagaraj' WHERE register_number = 'STU001'")
        self.student = conn.execute("SELECT * FROM students WHERE register_number = 'STU001'").fetchone()
        self.parent = conn.execute("SELECT * FROM parents WHERE email = 'parent@example.com'").fetchone()
        conn.commit()
        conn.close()

    def test_a_landing_page_parent_button(self):
        """TEST A — Landing Page: Verify Landing page links directly to Parent Login."""
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'/parent/login', resp.data)
        self.assertIn(b'Parent Portal', resp.data)
        self.assertIn(b'FOR PARENTS', resp.data)

    def test_b_invalid_parent_login(self):
        """TEST B — Invalid Login: Verify bad password and nonexistent accounts fail gracefully."""
        # 1. Nonexistent account
        resp_bad_user = self.client.post('/parent/login', data={
            'identifier': 'unknown_parent@example.com',
            'password': 'WrongPassword@123'
        }, follow_redirects=False)
        self.assertEqual(resp_bad_user.status_code, 200)
        self.assertIn(b'Invalid Parent ID / Email or Password', resp_bad_user.data)

        # 2. Existing account with wrong password
        resp_bad_pw = self.client.post('/parent/login', data={
            'identifier': 'parent@example.com',
            'password': 'IncorrectPassword123'
        }, follow_redirects=False)
        self.assertEqual(resp_bad_pw.status_code, 200)
        self.assertIn(b'Invalid Parent ID / Email or Password', resp_bad_pw.data)

        # Verify session is empty
        with self.client.session_transaction() as sess:
            self.assertNotIn('parent_id', sess)
            self.assertNotIn('user_role', sess)

    def test_c_valid_parent_login_variants(self):
        """TEST C — Valid Login: Verify login by email, PAR001, and P1001 redirects to /parent/dashboard."""
        conn = app.get_db_connection()
        conn.execute("DELETE FROM login_attempts")
        conn.commit()
        conn.close()

        variants = ['parent@example.com', 'PAR001', 'P1001', 'par001', 'PARENT@EXAMPLE.COM']
        
        for identifier in variants:
            # Clear cookie jar / session
            self.client.get('/parent/logout')

            resp = self.client.post('/parent/login', data={
                'identifier': identifier,
                'password': 'Parent@123',
                'remember': '1'
            }, follow_redirects=False)
            
            # Verify 302 redirect to /parent/dashboard
            self.assertEqual(resp.status_code, 302, f"Failed for identifier: {identifier}")
            self.assertIn('/parent/dashboard', resp.headers['Location'])

            # Verify session variables
            with self.client.session_transaction() as sess:
                self.assertEqual(sess.get('parent_id'), self.parent['id'])
                self.assertEqual(sess.get('user_role'), 'parent')
                self.assertEqual(sess.get('student_id'), self.student['id'])
                self.assertTrue(sess.get('parent_logged_in'))

    def test_d_parent_dashboard_and_modules(self):
        """TEST D — Dashboard: Verify Parent Dashboard loads ward data and all modules render."""
        with self.client.session_transaction() as sess:
            sess['parent_id'] = self.parent['id']
            sess['user_role'] = 'parent'
            sess['parent_logged_in'] = True
            sess['student_id'] = self.student['id']

        # 1. Parent Dashboard
        resp_dash = self.client.get('/parent/dashboard')
        self.assertEqual(resp_dash.status_code, 200)
        self.assertIn(b'R. S. Kumar', resp_dash.data)
        self.assertIn(b'Nithish Nagaraj', resp_dash.data)
        self.assertIn(b'STU001', resp_dash.data)
        self.assertIn(b'Live Connected', resp_dash.data)

        # 2. All Parent Modules
        modules = [
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

        for mod in modules:
            r = self.client.get(mod)
            self.assertEqual(r.status_code, 200, f"Module {mod} failed to load.")
            self.assertIn(b'Nithish Nagaraj', r.data, f"Student name missing in {mod}")

    def test_e_parent_logout(self):
        """TEST E — Logout: Verify logging out clears session and redirects to login."""
        # Log in first
        self.client.post('/parent/login', data={
            'identifier': 'parent@example.com',
            'password': 'Parent@123'
        })

        # Call logout
        resp_logout = self.client.get('/parent/logout', follow_redirects=False)
        self.assertEqual(resp_logout.status_code, 302)
        self.assertIn('/parent/login', resp_logout.headers['Location'])

        # Verify session cleared
        with self.client.session_transaction() as sess:
            self.assertNotIn('parent_id', sess)
            self.assertNotIn('user_role', sess)
            self.assertNotIn('student_id', sess)

    def test_f_protected_routes_unauthenticated(self):
        """TEST F — Protected Route: Verify accessing parent pages without auth redirects to login."""
        protected_routes = [
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

        for route in protected_routes:
            resp = self.client.get(route, follow_redirects=False)
            self.assertEqual(resp.status_code, 302, f"Route {route} was not protected.")
            self.assertIn('/parent/login', resp.headers['Location'])

    def test_g_student_faculty_admin_stability(self):
        """TEST G — Student, Faculty, Admin Portals: Verify existing portals continue working."""
        # 1. Student Portal
        resp_stu_login = self.client.post('/student/login', data={
            'register_number': 'STU001',
            'password': 'Student@123'
        }, follow_redirects=False)
        self.assertEqual(resp_stu_login.status_code, 302)
        self.assertIn('/student/dashboard', resp_stu_login.headers['Location'])

        # 2. Faculty Portal
        resp_fac_login = self.client.post('/faculty/login', data={
            'identifier': 'FAC001',
            'password': 'Faculty@123'
        }, follow_redirects=False)
        self.assertEqual(resp_fac_login.status_code, 302)
        self.assertIn('/faculty/dashboard', resp_fac_login.headers['Location'])

        # 3. Admin Portal
        resp_adm_login = self.client.post('/admin/login', data={
            'identifier': 'admin',
            'password': 'Admin@123'
        }, follow_redirects=False)
        self.assertEqual(resp_adm_login.status_code, 302)
        self.assertIn('/admin/dashboard', resp_adm_login.headers['Location'])


if __name__ == '__main__':
    unittest.main()
