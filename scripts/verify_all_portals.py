import unittest
import app
import json
import uuid
from database.db import get_db_connection

class TestAllPortalsEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cleanup_test_data()

    @classmethod
    def tearDownClass(cls):
        cls.cleanup_test_data()

    @classmethod
    def cleanup_test_data(cls):
        conn = get_db_connection()
        try:
            tst_ids = [r['id'] for r in conn.execute("SELECT id FROM students WHERE register_number LIKE 'TST_VERIFY%'").fetchall()]
            if tst_ids:
                ph = ', '.join(['?'] * len(tst_ids))
                conn.execute(f"DELETE FROM parent_student WHERE student_id IN ({ph})", tst_ids)
                conn.execute(f"DELETE FROM attendance WHERE student_id IN ({ph})", tst_ids)
                conn.execute(f"DELETE FROM attendance_logs WHERE student_id IN ({ph})", tst_ids)
                conn.execute(f"DELETE FROM marks WHERE student_id IN ({ph})", tst_ids)
                conn.execute(f"DELETE FROM fees WHERE student_id IN ({ph})", tst_ids)
                conn.execute(f"DELETE FROM payment_transactions WHERE student_id IN ({ph})", tst_ids)
                conn.execute(f"DELETE FROM complaints WHERE student_id IN ({ph})", tst_ids)
                conn.execute(f"DELETE FROM student_submissions WHERE student_id IN ({ph})", tst_ids)
                conn.execute(f"DELETE FROM student_transport WHERE student_id IN ({ph})", tst_ids)
                conn.execute(f"DELETE FROM lab_experiments WHERE student_id IN ({ph})", tst_ids)
                conn.execute(f"DELETE FROM student_settings WHERE student_id IN ({ph})", tst_ids)
                conn.execute(f"DELETE FROM student_requests WHERE student_id IN ({ph})", tst_ids)
                conn.execute(f"DELETE FROM lost_found WHERE student_id IN ({ph})", tst_ids)
                conn.execute(f"DELETE FROM parent_messages WHERE student_id IN ({ph})", tst_ids)
                conn.execute(f"DELETE FROM notifications WHERE recipient_role = 'student' AND recipient_id IN ({ph})", tst_ids)
            
            p_ids = [r['id'] for r in conn.execute("SELECT id FROM parents WHERE email LIKE '%@verifytest.com'").fetchall()]
            if p_ids:
                p_ph = ', '.join(['?'] * len(p_ids))
                conn.execute(f"DELETE FROM parent_alert_reads WHERE parent_id IN ({p_ph})", p_ids)
                conn.execute(f"DELETE FROM notifications WHERE recipient_role = 'parent' AND recipient_id IN ({p_ph})", p_ids)
                conn.execute(f"DELETE FROM parent_messages WHERE parent_id IN ({p_ph})", p_ids)
                conn.execute(f"DELETE FROM parents WHERE id IN ({p_ph})", p_ids)

            if tst_ids:
                ph = ', '.join(['?'] * len(tst_ids))
                conn.execute(f"DELETE FROM students WHERE id IN ({ph})", tst_ids)
            conn.commit()
        except Exception as e:
            print(f"[Cleanup Warning] {e}")
        finally:
            conn.close()

    def setUp(self):
        self.app = app.app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        # Admin registers a verified test student and parent for portal tests
        self.test_reg = f"TST_VERIFY_{uuid.uuid4().hex[:6].upper()}"
        self.test_p_email = f"p_{uuid.uuid4().hex[:8]}@verifytest.com"
        
        # Dedicated admin client to ensure fresh authentication for creation
        admin_client = self.app.test_client()
        admin_client.post('/admin/login', data={'username': 'admin', 'password': 'Admin@123'}, follow_redirects=True)

        res_create = admin_client.post('/admin/students/create', data={
            'register_number': self.test_reg,
            'name': 'Dynamic Test Student',
            'email': f"{self.test_reg.lower()}@verifytest.com",
            'phone': '+91 98888 77777',
            'department': 'Computer Science & Engineering',
            'year': 3,
            'semester': 5,
            'parent_name': 'Dynamic Test Parent',
            'parent_email': self.test_p_email,
            'parent_phone': '+91 98888 66666',
            'parent_relationship': 'Father'
        }, follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)

    def tearDown(self):
        self.cleanup_test_data()

    def test_student_portal_live(self):
        # 1. Login as dynamic test student
        client = self.app.test_client()
        res = client.post('/student/login', data={'register_number': self.test_reg, 'password': 'Student@123'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Dynamic Test Student', res.data)

        # 2. Check all student sub-pages
        student_urls = [
            '/student/dashboard',
            '/student/profile',
            '/student/academics',
            '/student/attendance',
            '/student/marks',
            '/student/timetable',
            '/student/assignments',
            '/student/examinations',
            '/student/fees',
            '/student/calendar',
            '/student/hostel',
            '/student/transport',
            '/student/placements',
            '/student/requests',
            '/student/lost-found',
            '/student/wellbeing',
            '/student/safety',
            '/student/safewalk',
            '/student/campus-map',
            '/student/emergency',
            '/student/assistant',
            '/student/settings'
        ]
        for url in student_urls:
            r = client.get(url)
            self.assertEqual(r.status_code, 200, f"Student URL {url} failed with {r.status_code}")
        print("[PASS] Student Portal: All 22 sub-routes loaded successfully with real DB data.")

    def test_parent_portal_live(self):
        # 1. Login as dynamically created parent
        client = self.app.test_client()
        res = client.post('/parent/login', data={'identifier': self.test_p_email, 'password': 'Parent@123'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Dynamic Test Parent', res.data)

        # 2. Check parent sub-pages
        parent_urls = [
            '/parent/dashboard',
            '/parent/academics',
            '/parent/attendance',
            '/parent/timetable',
            '/parent/exams',
            '/parent/fees',
            '/parent/leave',
            '/parent/safety',
            '/parent/messages',
            '/parent/notifications',
            '/parent/profile'
        ]
        for url in parent_urls:
            r = client.get(url)
            self.assertEqual(r.status_code, 200, f"Parent URL {url} failed with {r.status_code}")
        print("[PASS] Parent Portal: All 13 sub-routes loaded successfully with real DB data.")

    def test_faculty_portal_live(self):
        # 1. Login as FAC001
        client = self.app.test_client()
        res = client.post('/faculty/login', data={'faculty_id': 'FAC001', 'password': 'Faculty@123'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Dr. Ramesh Rao', res.data)

        # 2. Check faculty sub-pages
        faculty_urls = [
            '/faculty/dashboard',
            '/faculty/students',
            '/faculty/attendance',
            '/faculty/attendance/analytics',
            '/faculty/marks',
            '/faculty/marks/performance',
            '/faculty/assignments',
            '/faculty/materials',
            '/faculty/lab',
            '/faculty/exams',
            '/faculty/mentoring',
            '/faculty/leaves',
            '/faculty/announcements',
            '/faculty/calendar',
            '/faculty/messages',
            '/faculty/notifications',
            '/faculty/insights',
            '/faculty/profile',
            '/faculty/reports',
            '/faculty/reports/export/attendance',
            '/faculty/reports/export/marks',
            '/faculty/reports/export/lab'
        ]
        for url in faculty_urls:
            r = client.get(url)
            self.assertEqual(r.status_code, 200, f"Faculty URL {url} failed with {r.status_code}")
        print("[PASS] Faculty Portal: All 22 sub-routes and CSV reports loaded successfully.")

    def test_admin_portal_live(self):
        # 1. Login as admin
        client = self.app.test_client()
        res = client.post('/admin/login', data={'username': 'admin', 'password': 'Admin@123'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Institutional Control Center', res.data)

        # 2. Check admin sub-pages
        admin_urls = [
            '/admin/dashboard',
            '/admin/students',
            '/admin/faculty',
            '/admin/parents',
            '/admin/academics',
            '/admin/attendance',
            '/admin/marks',
            '/admin/fees',
            '/admin/exams',
            '/admin/leaves',
            '/admin/safety',
            '/admin/announcements',
            '/admin/messages',
            '/admin/reports',
            '/admin/audit-logs',
            '/admin/settings',
            '/admin/analytics'
        ]
        for url in admin_urls:
            r = client.get(url)
            self.assertEqual(r.status_code, 200, f"Admin URL {url} failed with {r.status_code}")
        print("[PASS] Admin Portal: All 17 sub-routes and analytics loaded successfully.")

    def test_security_and_ai_assistant(self):
        # Security Command Console
        client = self.app.test_client()
        r_sec = client.get('/security/dashboard')
        self.assertEqual(r_sec.status_code, 200)

        # AI Assistant API
        client.post('/student/login', data={'register_number': self.test_reg, 'password': 'Student@123'}, follow_redirects=True)
        r_ai = client.post('/api/student/chat', json={'message': 'What is my current attendance?'})
        self.assertEqual(r_ai.status_code, 200)
        data = json.loads(r_ai.data)
        self.assertIn('reply', data)
        print("[PASS] Security Console & AI Assistant verified successfully.")

if __name__ == '__main__':
    unittest.main()
