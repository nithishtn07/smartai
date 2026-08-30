import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import json
import uuid
import app
from database.db import get_db_connection
from werkzeug.security import check_password_hash

class TestAutoParentCreationAndLinking(unittest.TestCase):
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
            tst_ids = [r['id'] for r in conn.execute("SELECT id FROM students WHERE register_number LIKE 'TST%'").fetchall()]
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
            
            p_ids = [r['id'] for r in conn.execute("SELECT id FROM parents WHERE email LIKE '%@testparent.com' OR email LIKE '%@testorphan.com' OR email LIKE '%@testjson.com'").fetchall()]
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

        # Admin session
        with self.client.session_transaction() as sess:
            sess['admin_id'] = 1
            sess['user_role'] = 'admin'

    def test_01_new_student_new_parent_atomic(self):
        """Case 1: New student + new parent -> Both created, linked, and hashed password set"""
        reg = f"TST{uuid.uuid4().hex[:6].upper()}"
        p_email = f"p_{uuid.uuid4().hex[:8]}@testparent.com"
        p_phone = f"+91 9{uuid.uuid4().hex[:9]}"
        payload = {
            'register_number': reg,
            'name': 'Aarav Sharma',
            'email': f"{reg.lower()}@test.edu",
            'phone': f"+91 8{uuid.uuid4().hex[:9]}",
            'department': 'Computer Science & Engineering',
            'year': 2,
            'semester': 3,
            'parent_name': 'Meera Sharma',
            'parent_email': p_email,
            'parent_phone': p_phone,
            'parent_relationship': 'Mother',
            'parent_address': 'Flat 101, Test Residency, Bengaluru'
        }
        res = self.client.post('/admin/students/create', data=payload, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        conn = get_db_connection()
        try:
            student = conn.execute("SELECT * FROM students WHERE register_number = ?", (reg,)).fetchone()
            self.assertIsNotNone(student)
            self.assertEqual(student['name'], 'Aarav Sharma')

            parent = conn.execute("SELECT * FROM parents WHERE email = ?", (p_email,)).fetchone()
            self.assertIsNotNone(parent)
            self.assertEqual(parent['name'], 'Meera Sharma')
            self.assertTrue(check_password_hash(parent['password_hash'], 'Parent@123'))

            link = conn.execute("SELECT * FROM parent_student WHERE parent_id = ? AND student_id = ?", (parent['id'], student['id'])).fetchone()
            self.assertIsNotNone(link)
            self.assertEqual(link['relationship'], 'Mother')
        finally:
            conn.close()

    def test_02_new_student_existing_parent_reuse(self):
        """Case 2: New student + existing parent -> Existing parent linked, no duplicate parent account"""
        reg1 = f"TST{uuid.uuid4().hex[:6].upper()}"
        reg2 = f"TST{uuid.uuid4().hex[:6].upper()}"
        p_email = f"shared_{uuid.uuid4().hex[:8]}@testparent.com"
        p_phone = f"+91 9{uuid.uuid4().hex[:9]}"

        # Create child 1
        p1 = {
            'register_number': reg1,
            'name': 'First Child',
            'email': f"{reg1.lower()}@test.edu",
            'phone': f"+91 8{uuid.uuid4().hex[:9]}",
            'department': 'Computer Science & Engineering',
            'year': 2,
            'semester': 3,
            'parent_name': 'Shared Parent',
            'parent_email': p_email,
            'parent_phone': p_phone,
            'parent_relationship': 'Father'
        }
        self.client.post('/admin/students/create', data=p1, follow_redirects=True)

        # Create child 2 with same parent email & phone
        p2 = {
            'register_number': reg2,
            'name': 'Second Child',
            'email': f"{reg2.lower()}@test.edu",
            'phone': f"+91 8{uuid.uuid4().hex[:9]}",
            'department': 'Electronics & Communication',
            'year': 1,
            'semester': 1,
            'parent_name': 'Shared Parent',
            'parent_email': p_email,
            'parent_phone': p_phone,
            'parent_relationship': 'Father'
        }
        res2 = self.client.post('/admin/students/create', data=p2, follow_redirects=True)
        self.assertEqual(res2.status_code, 200)

        conn = get_db_connection()
        try:
            parent_count = conn.execute("SELECT COUNT(*) FROM parents WHERE email = ?", (p_email,)).fetchone()[0]
            self.assertEqual(parent_count, 1, "Duplicate parent account created!")

            parent = conn.execute("SELECT id FROM parents WHERE email = ?", (p_email,)).fetchone()
            links = conn.execute("SELECT * FROM parent_student WHERE parent_id = ?", (parent['id'],)).fetchall()
            self.assertEqual(len(links), 2, "Parent should have 2 linked children")
        finally:
            conn.close()

    def test_03_transaction_rollback_on_duplicate_student(self):
        """Case 3 & 4: Rollback when duplicate student register number occurs (no orphan parent)"""
        reg = f"TST{uuid.uuid4().hex[:6].upper()}"
        p_email_orphan = f"orphan_{uuid.uuid4().hex[:8]}@testorphan.com"

        # Create initial student
        p_init = {
            'register_number': reg,
            'name': 'Initial Student',
            'email': f"{reg.lower()}@test.edu",
            'phone': f"+91 8{uuid.uuid4().hex[:9]}",
            'department': 'Computer Science & Engineering',
            'year': 1,
            'semester': 1,
            'parent_name': 'Init Parent',
            'parent_email': f"init_{reg.lower()}@testparent.com",
            'parent_phone': f"+91 9{uuid.uuid4().hex[:9]}"
        }
        self.client.post('/admin/students/create', data=p_init, follow_redirects=True)

        # Attempt to create duplicate with new parent
        p_dup = {
            'register_number': reg, # duplicate
            'name': 'Duplicate Person',
            'email': f"other_{reg.lower()}@test.edu",
            'phone': f"+91 8{uuid.uuid4().hex[:9]}",
            'department': 'Computer Science & Engineering',
            'year': 1,
            'semester': 1,
            'parent_name': 'Orphan Parent',
            'parent_email': p_email_orphan,
            'parent_phone': f"+91 9{uuid.uuid4().hex[:9]}"
        }
        res = self.client.post('/admin/students/create', data=p_dup, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        conn = get_db_connection()
        try:
            orphan = conn.execute("SELECT * FROM parents WHERE email = ?", (p_email_orphan,)).fetchone()
            self.assertIsNone(orphan, "Orphan parent created on student conflict!")
        finally:
            conn.close()

    def test_04_multi_child_parent_portal_switching(self):
        """Case 5: Parent with multiple children can log in and switch active child context"""
        reg1 = f"TST{uuid.uuid4().hex[:6].upper()}"
        reg2 = f"TST{uuid.uuid4().hex[:6].upper()}"
        p_email = f"multi_{uuid.uuid4().hex[:8]}@testparent.com"
        p_phone = f"+91 9{uuid.uuid4().hex[:9]}"

        self.client.post('/admin/students/create', data={
            'register_number': reg1, 'name': 'Alpha Student', 'email': f"{reg1.lower()}@test.edu",
            'phone': f"+91 8{uuid.uuid4().hex[:9]}", 'department': 'Computer Science & Engineering',
            'year': 2, 'semester': 3, 'parent_name': 'Multi Parent', 'parent_email': p_email,
            'parent_phone': p_phone, 'parent_relationship': 'Mother'
        }, follow_redirects=True)

        self.client.post('/admin/students/create', data={
            'register_number': reg2, 'name': 'Beta Student', 'email': f"{reg2.lower()}@test.edu",
            'phone': f"+91 8{uuid.uuid4().hex[:9]}", 'department': 'Electronics & Communication',
            'year': 1, 'semester': 1, 'parent_name': 'Multi Parent', 'parent_email': p_email,
            'parent_phone': p_phone, 'parent_relationship': 'Mother'
        }, follow_redirects=True)

        # Parent login
        p_client = self.app.test_client()
        res_login = p_client.post('/parent/login', data={'identifier': p_email, 'password': 'Parent@123'}, follow_redirects=True)
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b'/parent/logout', res_login.data)

        conn = get_db_connection()
        try:
            stu1 = conn.execute("SELECT id, name FROM students WHERE register_number = ?", (reg1,)).fetchone()
            stu2 = conn.execute("SELECT id, name FROM students WHERE register_number = ?", (reg2,)).fetchone()

            # Switch to Student 2
            res_s2 = p_client.get(f'/parent/switch-student/{stu2["id"]}', follow_redirects=True)
            self.assertEqual(res_s2.status_code, 200)
            self.assertIn(b'Beta Student', res_s2.data)

            # Switch back to Student 1
            res_s1 = p_client.get(f'/parent/switch-student/{stu1["id"]}', follow_redirects=True)
            self.assertEqual(res_s1.status_code, 200)
            self.assertIn(b'Alpha Student', res_s1.data)
        finally:
            conn.close()

    def test_05_unauthorized_student_access_isolation(self):
        """Case 6: Parent attempts to switch to an unlinked student -> Denied"""
        reg1 = f"TST{uuid.uuid4().hex[:6].upper()}"
        p_email = f"iso_{uuid.uuid4().hex[:8]}@testparent.com"
        p_phone = f"+91 9{uuid.uuid4().hex[:9]}"

        self.client.post('/admin/students/create', data={
            'register_number': reg1, 'name': 'Isolated Student', 'email': f"{reg1.lower()}@test.edu",
            'phone': f"+91 8{uuid.uuid4().hex[:9]}", 'department': 'Computer Science & Engineering',
            'year': 2, 'semester': 3, 'parent_name': 'Iso Parent', 'parent_email': p_email,
            'parent_phone': p_phone, 'parent_relationship': 'Mother'
        }, follow_redirects=True)

        p_client = self.app.test_client()
        res_login = p_client.post('/parent/login', data={'identifier': p_email, 'password': 'Parent@123'}, follow_redirects=True)
        self.assertEqual(res_login.status_code, 200)

        # Create second unlinked student
        reg2 = f"TST{uuid.uuid4().hex[:6].upper()}"
        p2_email = f"other_{uuid.uuid4().hex[:8]}@testparent.com"
        self.client.post('/admin/students/create', data={
            'register_number': reg2, 'name': 'Other Student', 'email': f"{reg2.lower()}@test.edu",
            'phone': f"+91 8{uuid.uuid4().hex[:9]}", 'department': 'Electronics & Communication',
            'year': 1, 'semester': 1, 'parent_name': 'Other Parent', 'parent_email': p2_email,
            'parent_phone': f"+91 9{uuid.uuid4().hex[:9]}", 'parent_relationship': 'Father'
        }, follow_redirects=True)

        conn = get_db_connection()
        try:
            stu_other = conn.execute("SELECT id FROM students WHERE register_number = ?", (reg2,)).fetchone()
            res_unauth = p_client.get(f'/parent/switch-student/{stu_other["id"]}', follow_redirects=True)
            self.assertIn(b'Unauthorized access', res_unauth.data)
        finally:
            conn.close()

    def test_06_admin_edit_student_and_linked_parent(self):
        """Case 7: Admin edits student details and linked parent info"""
        reg = f"TST{uuid.uuid4().hex[:6].upper()}"
        p_email = f"edit_{uuid.uuid4().hex[:8]}@testparent.com"
        p_phone = f"+91 9{uuid.uuid4().hex[:9]}"

        self.client.post('/admin/students/create', data={
            'register_number': reg, 'name': 'Pre-Edit Student', 'email': f"{reg.lower()}@test.edu",
            'phone': f"+91 8{uuid.uuid4().hex[:9]}", 'department': 'Computer Science & Engineering',
            'year': 2, 'semester': 3, 'parent_name': 'Pre-Edit Parent', 'parent_email': p_email,
            'parent_phone': p_phone, 'parent_relationship': 'Mother'
        }, follow_redirects=True)

        conn = get_db_connection()
        try:
            student = conn.execute("SELECT id FROM students WHERE register_number = ?", (reg,)).fetchone()
            p_phone_new = f"+91 9{uuid.uuid4().hex[:9]}"
            edit_data = {
                'name': 'Post-Edit Student',
                'phone': f"+91 8{uuid.uuid4().hex[:9]}",
                'department': 'Information Technology',
                'year': 3,
                'semester': 5,
                'parent_name': 'Post-Edit Parent',
                'parent_phone': p_phone_new,
                'parent_relationship': 'Mother'
            }
            res_edit = self.client.post(f'/admin/students/edit/{student["id"]}', data=edit_data, follow_redirects=True)
            self.assertEqual(res_edit.status_code, 200)

            s = conn.execute("SELECT name, department FROM students WHERE id = ?", (student['id'],)).fetchone()
            self.assertEqual(s['name'], 'Post-Edit Student')
            self.assertEqual(s['department'], 'Information Technology')

            p = conn.execute("SELECT name, phone FROM parents WHERE email = ?", (p_email,)).fetchone()
            self.assertEqual(p['name'], 'Post-Edit Parent')
            self.assertEqual(p['phone'], p_phone_new)
        finally:
            conn.close()

    def test_07_safe_student_deletion(self):
        """Case 8: Delete Child 1 -> Parent account remains active with Child 2"""
        reg1 = f"TST{uuid.uuid4().hex[:6].upper()}"
        reg2 = f"TST{uuid.uuid4().hex[:6].upper()}"
        p_email = f"del_{uuid.uuid4().hex[:8]}@testparent.com"
        p_phone = f"+91 9{uuid.uuid4().hex[:9]}"

        self.client.post('/admin/students/create', data={
            'register_number': reg1, 'name': 'Delete Me Student', 'email': f"{reg1.lower()}@test.edu",
            'phone': f"+91 8{uuid.uuid4().hex[:9]}", 'department': 'Computer Science & Engineering',
            'year': 2, 'semester': 3, 'parent_name': 'Safe Parent', 'parent_email': p_email,
            'parent_phone': p_phone, 'parent_relationship': 'Mother'
        }, follow_redirects=True)

        self.client.post('/admin/students/create', data={
            'register_number': reg2, 'name': 'Keep Me Student', 'email': f"{reg2.lower()}@test.edu",
            'phone': f"+91 8{uuid.uuid4().hex[:9]}", 'department': 'Electronics & Communication',
            'year': 1, 'semester': 1, 'parent_name': 'Safe Parent', 'parent_email': p_email,
            'parent_phone': p_phone, 'parent_relationship': 'Mother'
        }, follow_redirects=True)

        conn = get_db_connection()
        try:
            stu1 = conn.execute("SELECT id FROM students WHERE register_number = ?", (reg1,)).fetchone()
            stu2 = conn.execute("SELECT id FROM students WHERE register_number = ?", (reg2,)).fetchone()
            parent = conn.execute("SELECT id FROM parents WHERE email = ?", (p_email,)).fetchone()

            # Delete student 1
            res_del = self.client.post(f'/admin/students/delete/{stu1["id"]}', follow_redirects=True)
            self.assertEqual(res_del.status_code, 200)

            # Parent must still exist and point to stu2
            p = conn.execute("SELECT * FROM parents WHERE id = ?", (parent['id'],)).fetchone()
            self.assertIsNotNone(p)
            self.assertEqual(p['student_id'], stu2['id'])

            links = conn.execute("SELECT * FROM parent_student WHERE parent_id = ?", (parent['id'],)).fetchall()
            self.assertEqual(len(links), 1)
            self.assertEqual(links[0]['student_id'], stu2['id'])
        finally:
            conn.close()

    def test_08_json_api_response(self):
        """Case 9: JSON API request returns structured creation/link payload"""
        reg = f"TST{uuid.uuid4().hex[:6].upper()}"
        p_email = f"json_{uuid.uuid4().hex[:8]}@testjson.com"
        p_phone = f"+91 9{uuid.uuid4().hex[:9]}"
        payload = {
            'register_number': reg,
            'name': 'API Student',
            'email': f"{reg.lower()}@test.edu",
            'phone': f"+91 8{uuid.uuid4().hex[:9]}",
            'department': 'Computer Science & Engineering',
            'year': 1,
            'semester': 1,
            'parent_name': 'API Parent',
            'parent_email': p_email,
            'parent_phone': p_phone,
            'parent_relationship': 'Father'
        }
        res = self.client.post('/admin/students/create', json=payload)
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertTrue(data['student_created'])
        self.assertTrue(data['parent_created'])
        self.assertTrue(data['linked'])
        self.assertIn('PAR', data['parent_id'])

    def test_09_manual_entry_required_no_fake_dummy_defaults(self):
        """Case 10: Missing manual student or parent fields are rejected without generating fake data"""
        reg = f"TST{uuid.uuid4().hex[:6].upper()}"
        # Incomplete payload (missing parent fields and department)
        incomplete_payload = {
            'register_number': reg,
            'name': 'Partial Student',
            'email': f"{reg.lower()}@test.edu",
            'phone': '+91 99999 11111'
        }
        res = self.client.post('/admin/students/create', json=incomplete_payload)
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertFalse(data['success'])
        self.assertIn('Department', data['error'])
        self.assertIn('Parent/Guardian Name', data['error'])

        # Verify nothing was inserted into the database
        conn = get_db_connection()
        try:
            student = conn.execute("SELECT id FROM students WHERE register_number = ?", (reg,)).fetchone()
            self.assertIsNone(student, "Partial student record should not be created")
        finally:
            conn.close()

if __name__ == '__main__':
    unittest.main()
