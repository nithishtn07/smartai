"""
=============================================================================
Test Suite: Admin Portal — Student & Parent Data Management
Tests viewing, searching, editing, and deleting student and parent records,
ensuring data integrity, authorization security, and relationship consistency.
=============================================================================
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from app import app
from database.db import get_db_connection, init_db


class TestAdminStudentParentManagement(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key-campusguard'
        self.client = app.test_client()

        # Re-initialize DB for clean test state
        init_db()

        # Seed test admin, student, and parent
        conn = get_db_connection()
        try:
            # Clean any leftover test records
            conn.execute("DELETE FROM parents WHERE parent_id LIKE 'TESTPAR%' OR email LIKE '%@test.edu'")
            conn.execute("DELETE FROM students WHERE register_number LIKE 'TESTSTU%' OR email LIKE '%@test.edu'")
            conn.execute("DELETE FROM parent_student WHERE student_id NOT IN (SELECT id FROM students)")
            conn.commit()

            # Check/create test admin
            admin = conn.execute("SELECT id FROM admins WHERE username = 'testadmin'").fetchone()
            if not admin:
                conn.execute("""
                    INSERT INTO admins (username, name, email, password_hash, role)
                    VALUES ('testadmin', 'Test Admin', 'admin@test.edu', 'hash123', 'SuperAdmin')
                """)
            
            # Create isolated test student
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO students (
                    name, register_number, email, password_hash, department, year, semester, section, phone, address, status
                ) VALUES (
                    'Test Student Alpha', 'TESTSTU01', 'alpha@test.edu', 'pw123', 'Computer Science & Engineering', 3, 5, 'A', '+91 99999 11111', 'Hostel Block A', 'ACTIVE'
                )
            """)
            self.test_student_id = cursor.lastrowid

            # Create isolated test parent
            cursor.execute("""
                INSERT INTO parents (
                    parent_id, name, email, phone, password_hash, relationship, student_id, occupation, address
                ) VALUES (
                    'TESTPAR01', 'Test Parent Alpha', 'parent_alpha@test.edu', '+91 88888 22222', 'pw123', 'Father', ?, 'Engineer', 'Bengaluru'
                )
            """, (self.test_student_id,))
            self.test_parent_id = cursor.lastrowid

            # Map in parent_student
            conn.execute("""
                INSERT OR REPLACE INTO parent_student (parent_id, student_id, relationship, is_primary)
                VALUES (?, ?, 'Father', 1)
            """, (self.test_parent_id, self.test_student_id))

            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM parents WHERE parent_id LIKE 'TESTPAR%' OR email LIKE '%@test.edu'")
            conn.execute("DELETE FROM students WHERE register_number LIKE 'TESTSTU%' OR email LIKE '%@test.edu'")
            conn.execute("DELETE FROM parent_student WHERE student_id NOT IN (SELECT id FROM students) OR parent_id NOT IN (SELECT id FROM parents)")
            conn.commit()
        finally:
            conn.close()

    def _login_admin(self):
        """Simulates admin authenticated session."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_role'] = 'admin'
            sess['admin_id'] = 1
            sess['name'] = 'Test Admin'
            sess['email'] = 'admin@test.edu'

    # 1. VIEW & SEARCH STUDENTS
    def test_01_admin_can_view_and_search_students(self):
        self._login_admin()
        
        # View all students
        res = self.client.get('/admin/students')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'TESTSTU01', res.data)
        self.assertIn(b'Test Student Alpha', res.data)

        # Search existing student by register number
        res_search = self.client.get('/admin/students?q=TESTSTU01')
        self.assertEqual(res_search.status_code, 200)
        self.assertIn(b'TESTSTU01', res_search.data)

        # Search by non-matching query
        res_empty = self.client.get('/admin/students?q=NONEXISTENT_QUERY_9999')
        self.assertEqual(res_empty.status_code, 200)
        self.assertIn(b'No student records found', res_empty.data)

    # 2. STUDENT API (JSON)
    def test_02_admin_student_api(self):
        self._login_admin()
        res = self.client.get(f'/admin/students/api/{self.test_student_id}')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['student']['register_number'], 'TESTSTU01')
        self.assertNotIn('password_hash', data['student'])

    # 3. EDIT STUDENT
    def test_03_admin_can_edit_student_and_persist(self):
        self._login_admin()
        
        edit_payload = {
            'name': 'Test Student Alpha Updated',
            'register_number': 'TESTSTU01',
            'email': 'alpha_updated@test.edu',
            'phone': '+91 99999 33333',
            'department': 'Information Technology',
            'program': 'B.Tech',
            'year': 4,
            'semester': 7,
            'section': 'B',
            'dob': '2004-05-15',
            'address': 'New Residence Delhi',
            'status': 'ACTIVE',
            'parent_name': 'Test Parent Alpha Renamed',
            'parent_phone': '+91 88888 44444',
            'parent_relationship': 'Mother'
        }

        res = self.client.post(f'/admin/students/edit/{self.test_student_id}', data=edit_payload, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify direct DB state
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT * FROM students WHERE id = ?", (self.test_student_id,)).fetchone()
            self.assertEqual(row['name'], 'Test Student Alpha Updated')
            self.assertEqual(row['email'], 'alpha_updated@test.edu')
            self.assertEqual(row['phone'], '+91 99999 33333')
            self.assertEqual(row['department'], 'Information Technology')
            self.assertEqual(row['year'], 4)
            self.assertEqual(row['semester'], 7)
            self.assertEqual(row['section'], 'B')
            self.assertEqual(row['dob'], '2004-05-15')
            self.assertEqual(row['address'], 'New Residence Delhi')

            # Verify synced parent record
            p_row = conn.execute("SELECT * FROM parents WHERE id = ?", (self.test_parent_id,)).fetchone()
            self.assertEqual(p_row['name'], 'Test Parent Alpha Renamed')
            self.assertEqual(p_row['phone'], '+91 88888 44444')
            self.assertEqual(p_row['relationship'], 'Mother')
        finally:
            conn.close()

    # 4. VIEW & SEARCH PARENTS
    def test_04_admin_can_view_and_search_parents(self):
        self._login_admin()
        
        # View all parents
        res = self.client.get('/admin/parents')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'TESTPAR01', res.data)
        self.assertIn(b'Test Parent Alpha', res.data)

        # Search by parent ID
        res_search = self.client.get('/admin/parents?q=TESTPAR01')
        self.assertEqual(res_search.status_code, 200)
        self.assertIn(b'TESTPAR01', res_search.data)

    # 5. PARENT API (JSON)
    def test_05_admin_parent_api(self):
        self._login_admin()
        res = self.client.get(f'/admin/parents/api/{self.test_parent_id}')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['parent']['parent_id'], 'TESTPAR01')
        self.assertNotIn('password_hash', data['parent'])
        self.assertTrue(len(data['parent']['children']) >= 1)

    # 6. EDIT PARENT
    def test_06_admin_can_edit_parent_and_persist(self):
        self._login_admin()
        
        edit_payload = {
            'parent_id': 'TESTPAR01_MOD',
            'name': 'Guardian S. Sharma',
            'email': 'guardian_sharma@test.edu',
            'phone': '+91 97777 55555',
            'relationship': 'Legal Guardian',
            'occupation': 'Executive Director',
            'address': 'Indiranagar Bengaluru',
            'student_id': self.test_student_id
        }

        res = self.client.post(f'/admin/parents/edit/{self.test_parent_id}', data=edit_payload, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify DB state
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT * FROM parents WHERE id = ?", (self.test_parent_id,)).fetchone()
            self.assertEqual(row['parent_id'], 'TESTPAR01_MOD')
            self.assertEqual(row['name'], 'Guardian S. Sharma')
            self.assertEqual(row['email'], 'guardian_sharma@test.edu')
            self.assertEqual(row['phone'], '+91 97777 55555')
            self.assertEqual(row['relationship'], 'Legal Guardian')
            self.assertEqual(row['occupation'], 'Executive Director')
            self.assertEqual(row['address'], 'Indiranagar Bengaluru')
        finally:
            conn.close()

    # 7. DELETE PARENT SAFELY
    def test_07_admin_can_delete_parent_safely(self):
        self._login_admin()
        
        res = self.client.post(f'/admin/parents/delete/{self.test_parent_id}', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify parent deleted and parent_student cleaned
        conn = get_db_connection()
        try:
            p_row = conn.execute("SELECT * FROM parents WHERE id = ?", (self.test_parent_id,)).fetchone()
            self.assertIsNone(p_row)

            ps_rows = conn.execute("SELECT * FROM parent_student WHERE parent_id = ?", (self.test_parent_id,)).fetchall()
            self.assertEqual(len(ps_rows), 0)

            # Student record itself should still be intact
            s_row = conn.execute("SELECT * FROM students WHERE id = ?", (self.test_student_id,)).fetchone()
            self.assertIsNotNone(s_row)
        finally:
            conn.close()

    # 8. DELETE STUDENT SAFELY
    def test_08_admin_can_delete_student_safely(self):
        self._login_admin()

        res = self.client.post(f'/admin/students/delete/{self.test_student_id}', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        conn = get_db_connection()
        try:
            s_row = conn.execute("SELECT status FROM students WHERE id = ?", (self.test_student_id,)).fetchone()
            self.assertEqual(s_row['status'], 'DELETED')

            ps_rows = conn.execute("SELECT * FROM parent_student WHERE student_id = ?", (self.test_student_id,)).fetchall()
            self.assertEqual(len(ps_rows), 0)
        finally:
            conn.close()

    # 9. SECURITY & NON-ADMIN ACCESS REJECTION
    def test_09_unauthorized_users_cannot_access_or_modify(self):
        # 1. Unauthenticated
        res = self.client.get('/admin/students')
        self.assertEqual(res.status_code, 302)  # Redirect to login

        res = self.client.post(f'/admin/students/edit/{self.test_student_id}', data={'name': 'Hacker'})
        self.assertEqual(res.status_code, 302)

        res = self.client.post(f'/admin/students/delete/{self.test_student_id}')
        self.assertEqual(res.status_code, 302)

        res = self.client.post(f'/admin/parents/edit/{self.test_parent_id}', data={'name': 'Hacker'})
        self.assertEqual(res.status_code, 302)

        res = self.client.post(f'/admin/parents/delete/{self.test_parent_id}')
        self.assertEqual(res.status_code, 302)

        # 2. Student role attempting admin action
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.test_student_id
            sess['user_role'] = 'student'
            sess['student_id'] = self.test_student_id

        res_stu = self.client.get('/admin/students')
        self.assertEqual(res_stu.status_code, 302)


if __name__ == '__main__':
    unittest.main()
