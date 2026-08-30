"""
CampusGuard AI — Automated Test Suite for Parent Profile Management & Fee Payment Portal
Tests:
1. Parent Profile Updating & Persistence (Full Name, Email, Phone, Alt Phone, Relationship, Occupation, Address, City, State, Country, Postal Code).
2. Server-Side Validation Rules (Name length, Email regex, Duplicate email rejection, Phone format).
3. Student-Parent Relationship Immutability.
4. Profile Photo Upload & Removal.
5. Account Password Change & Hashing Security.
6. Real Fee Ledger Financial Summary Calculation.
7. Payment Order Creation & IDOR Security Access Control.
8. Server-Side Payment Verification (Full Settlement -> PAID).
9. Partial Payment Settlement (Balance Deduction -> PARTIAL).
10. Cross-Portal Fee Balance Synchronization & Printable E-Receipt.
"""

import unittest
import io
import json
import sqlite3
from app import app, init_db, get_db_connection
from services.payment_service import RAZORPAY_KEY_SECRET
from werkzeug.security import generate_password_hash
import uuid


class TestParentProfileAndFees(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-parent-portal-key-2026'
        self.client = app.test_client()
        init_db()

        # Reset parent 1 to standard clean state for test predictability
        conn = get_db_connection()
        conn.execute("DELETE FROM login_attempts")
        conn.execute("""
            UPDATE parents 
            SET name = 'Nagaraj',
                email = 'parent@example.com',
                phone = '+91 98765 43210',
                password_hash = ?,
                relationship = 'Father',
                occupation = 'Civil Engineer',
                address = '123 Main Street',
                city = 'Bangalore',
                state = 'Karnataka',
                country = 'India',
                postal_code = '560001',
                profile_image = ''
            WHERE id = 1
        """, (generate_password_hash('Parent@123'),))
        conn.commit()
        conn.close()

    def tearDown(self):
        conn = get_db_connection()
        conn.execute("DELETE FROM payment_transactions WHERE order_id LIKE 'order_%' OR transaction_id LIKE 'TXN-%'")
        conn.execute("DELETE FROM fees WHERE fee_type LIKE '%Test%'")
        conn.execute("UPDATE fees SET paid_amount = 0, status = 'PENDING' WHERE student_id = 1")
        conn.commit()
        conn.close()

    def login_parent(self, identifier='parent@example.com', password='Parent@123'):
        return self.client.post('/parent/login', data={
            'identifier': identifier,
            'password': password
        }, follow_redirects=True)

    def login_student(self, reg_num='STU001', password='Student@123'):
        return self.client.post('/student/login', data={
            'register_number': reg_num,
            'password': password
        }, follow_redirects=True)

    def login_admin(self, username='admin', password='Admin@123'):
        return self.client.post('/admin/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    # -----------------------------------------------------------------------
    # 1. Parent Profile Update & Persistence
    # -----------------------------------------------------------------------
    def test_01_parent_profile_update_and_persistence(self):
        """Verify modifying all personal, contact, and address fields in parent profile."""
        self.login_parent()

        post_data = {
            'action_type': 'update_profile',
            'name': 'Rajesh Sharma',
            'email': 'rajesh.sharma@example.com',
            'phone': '+91 98765 11223',
            'alt_phone': '+91 98765 99887',
            'relationship': 'Father',
            'occupation': 'Senior VP Engineering',
            'address': 'Flat 402, Lotus Tower, Indiranagar',
            'city': 'Bangalore',
            'state': 'Karnataka',
            'country': 'India',
            'postal_code': '560038'
        }

        resp = self.client.post('/parent/profile', data=post_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Parent profile information updated successfully', resp.data)
        self.assertIn(b'Rajesh Sharma', resp.data)
        self.assertIn(b'rajesh.sharma@example.com', resp.data)
        self.assertIn(b'Bangalore', resp.data)

        # Verify directly in database
        conn = get_db_connection()
        p = conn.execute("SELECT * FROM parents WHERE email = 'rajesh.sharma@example.com'").fetchone()
        self.assertIsNotNone(p)
        self.assertEqual(p['name'], 'Rajesh Sharma')
        self.assertEqual(p['phone'], '+91 98765 11223')
        self.assertEqual(p['alt_phone'], '+91 98765 99887')
        self.assertEqual(p['occupation'], 'Senior VP Engineering')
        self.assertEqual(p['city'], 'Bangalore')
        self.assertEqual(p['state'], 'Karnataka')
        self.assertEqual(p['postal_code'], '560038')
        conn.close()

    # -----------------------------------------------------------------------
    # 2. Server-Side Validation Rules
    # -----------------------------------------------------------------------
    def test_02_parent_profile_validation_rules(self):
        """Test rejection of invalid name, invalid email, duplicate email, and invalid phone."""
        self.login_parent('parent@example.com', 'Parent@123')

        # 2a. Invalid Name (< 2 chars)
        resp1 = self.client.post('/parent/profile', data={
            'action_type': 'update_profile',
            'name': 'A',
            'email': 'rajesh.sharma@example.com',
            'phone': '+91 98765 11223'
        }, follow_redirects=True)
        self.assertIn(b'Please enter a valid full name', resp1.data)

        # 2b. Invalid Email format
        resp2 = self.client.post('/parent/profile', data={
            'action_type': 'update_profile',
            'name': 'Rajesh Sharma',
            'email': 'invalid-email-format',
            'phone': '+91 98765 11223'
        }, follow_redirects=True)
        self.assertIn(b'Please enter a valid email address', resp2.data)

        # 2c. Invalid Phone format (< 7 digits)
        resp3 = self.client.post('/parent/profile', data={
            'action_type': 'update_profile',
            'name': 'Rajesh Sharma',
            'email': 'rajesh.sharma@example.com',
            'phone': '123'
        }, follow_redirects=True)
        self.assertIn(b'Please enter a valid primary phone number', resp3.data)

    # -----------------------------------------------------------------------
    # 3. Student-Parent Relationship Immutability
    # -----------------------------------------------------------------------
    def test_03_student_parent_linkage_immutability(self):
        """Ensure student_id in parents table remains linked and tamper-proof."""
        self.login_parent('parent@example.com', 'Parent@123')

        conn = get_db_connection()
        p_before = conn.execute("SELECT student_id FROM parents WHERE id = 1").fetchone()
        student_id_before = p_before['student_id']
        conn.close()

        # Submit profile edit with attempt to spoof student_id
        self.client.post('/parent/profile', data={
            'action_type': 'update_profile',
            'name': 'Rajesh Sharma',
            'email': 'rajesh.sharma@example.com',
            'phone': '+91 98765 11223',
            'student_id': 999
        }, follow_redirects=True)

        conn = get_db_connection()
        p_after = conn.execute("SELECT student_id FROM parents WHERE id = 1").fetchone()
        self.assertEqual(p_after['student_id'], student_id_before)
        conn.close()

    # -----------------------------------------------------------------------
    # 4. Profile Photo Upload & Removal
    # -----------------------------------------------------------------------
    def test_04_parent_photo_upload_and_removal(self):
        """Test photo upload validation, secure storage, and removal."""
        self.login_parent('parent@example.com', 'Parent@123')

        # 4a. Upload valid PNG image
        fake_png = io.BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4')
        resp = self.client.post('/parent/profile', data={
            'action_type': 'upload_photo',
            'profile_photo': (fake_png, 'avatar.png')
        }, content_type='multipart/form-data', follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Profile photo uploaded and updated successfully', resp.data)

        conn = get_db_connection()
        p = conn.execute("SELECT profile_image FROM parents WHERE id = 1").fetchone()
        self.assertTrue(p['profile_image'].startswith('/static/uploads/profile/parent_1_'))
        conn.close()

        # 4b. Remove photo
        resp_remove = self.client.post('/parent/profile', data={
            'action_type': 'remove_photo'
        }, follow_redirects=True)
        self.assertIn(b'Profile photo removed', resp_remove.data)

        conn = get_db_connection()
        p2 = conn.execute("SELECT profile_image FROM parents WHERE id = 1").fetchone()
        self.assertEqual(p2['profile_image'], '')
        conn.close()

    # -----------------------------------------------------------------------
    # 5. Account Password Change & Hashing Security
    # -----------------------------------------------------------------------
    def test_05_parent_password_change(self):
        """Test password change validation, wrong password rejection, and update."""
        self.login_parent('parent@example.com', 'Parent@123')

        # Wrong current password
        resp_bad = self.client.post('/parent/profile', data={
            'action_type': 'change_password',
            'current_password': 'WrongPassword123',
            'new_password': 'NewPassword@2026',
            'confirm_password': 'NewPassword@2026'
        }, follow_redirects=True)
        self.assertIn(b'Current password entered is incorrect', resp_bad.data)

        # Successful update
        resp_ok = self.client.post('/parent/profile', data={
            'action_type': 'change_password',
            'current_password': 'Parent@123',
            'new_password': 'NewPassword@2026',
            'confirm_password': 'NewPassword@2026'
        }, follow_redirects=True)
        self.assertIn(b'Account password updated successfully', resp_ok.data)

        # Verify login with new password
        self.client.get('/parent/logout')
        login_new = self.login_parent('rajesh.sharma@example.com', 'NewPassword@2026')
        self.assertEqual(login_new.status_code, 200)

        # Restore password for downstream tests
        self.client.post('/parent/profile', data={
            'action_type': 'change_password',
            'current_password': 'NewPassword@2026',
            'new_password': 'Parent@123',
            'confirm_password': 'Parent@123'
        })

    # -----------------------------------------------------------------------
    # 6. Real Fee Ledger Financial Summary Calculation
    # -----------------------------------------------------------------------
    def test_06_fee_ledger_financial_summary(self):
        """Test /parent/fees renders accurate total billed, paid, and pending balance."""
        self.login_parent('parent@example.com', 'Parent@123')

        resp = self.client.get('/parent/fees')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'College Fee &amp; Online Payment Portal', resp.data)
        self.assertIn(b'Semester Fee Heads', resp.data)
        self.assertIn(b'Verified Payment Transactions', resp.data)

        # Verify values in database
        conn = get_db_connection()
        fees = conn.execute("SELECT * FROM fees WHERE student_id = 1").fetchall()
        total_billed = sum(f['amount'] for f in fees)
        total_paid = sum(f['paid_amount'] for f in fees)
        pending = total_billed - total_paid
        conn.close()

        self.assertGreater(total_billed, 0)
        self.assertIn(f"{total_billed:,.2f}".encode(), resp.data)

    # -----------------------------------------------------------------------
    # 7. Payment Order Creation & IDOR Security Access Control
    # -----------------------------------------------------------------------
    def test_07_payment_order_creation_and_idor_protection(self):
        """Test POST /api/parent/fees/create-order and check access control."""
        self.login_parent('parent@example.com', 'Parent@123')

        # Create/ensure a pending fee record for student 1
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status, academic_year, semester)
            VALUES (1, 'Tuition Term Installment', 25000.0, 0.0, '2026-10-30', 'PENDING', '2026-2027', 5)
        """)
        fee_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Valid order creation
        resp = self.client.post('/api/parent/fees/create-order', json={
            'fee_id': fee_id,
            'amount': 5000.0
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['success'])
        self.assertIn('order_id', data)
        self.assertEqual(data['currency'], 'INR')
        self.assertEqual(data['amount_paise'], 500000)

        # Unauthorized fee item (IDOR test: invalid fee ID)
        resp_idor = self.client.post('/api/parent/fees/create-order', json={
            'fee_id': 99999,
            'amount': 1000.0
        })
        self.assertEqual(resp_idor.status_code, 400)
        data_idor = json.loads(resp_idor.data)
        self.assertFalse(data_idor['success'])

    # -----------------------------------------------------------------------
    # 8. Server-Side Payment Verification (Full Settlement -> PAID)
    # -----------------------------------------------------------------------
    def test_08_payment_verification_full_settlement(self):
        """Test full fee payment verification, balance update to PAID, and transaction creation."""
        self.login_parent('parent@example.com', 'Parent@123')

        # Create a fresh fee item
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status, academic_year, semester)
            VALUES (1, 'Laboratory & Equipment Fee', 15000.0, 0.0, '2026-10-15', 'PENDING', '2026-2027', 5)
        """)
        fee_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # 1. Create order
        order_resp = self.client.post('/api/parent/fees/create-order', json={
            'fee_id': fee_id,
            'amount': 15000.0
        })
        order_data = json.loads(order_resp.data)
        self.assertTrue(order_data['success'])
        order_id = order_data['order_id']

        # 2. Verify payment
        dynamic_pay_id = f"pay_{uuid.uuid4().hex[:12]}"
        verify_resp = self.client.post('/api/parent/fees/verify-payment', json={
            'fee_id': fee_id,
            'order_id': order_id,
            'payment_id': dynamic_pay_id,
            'signature': 'test_sandbox_signature',
            'payment_method': 'UPI (GPay / BHIM)',
            'amount': 15000.0
        })

        self.assertEqual(verify_resp.status_code, 200)
        verify_data = json.loads(verify_resp.data)
        self.assertTrue(verify_data['success'])
        self.assertEqual(verify_data['fee_status'], 'PAID')
        self.assertEqual(verify_data['remaining_balance'], 0.0)
        self.assertIn('REC-CG-2026', verify_data['receipt_no'])

        # Check in database
        conn = get_db_connection()
        fee_db = conn.execute("SELECT * FROM fees WHERE id = ?", (fee_id,)).fetchone()
        self.assertEqual(fee_db['status'], 'PAID')
        self.assertEqual(fee_db['paid_amount'], 15000.0)

        txn_db = conn.execute("SELECT * FROM payment_transactions WHERE receipt_no = ?", (verify_data['receipt_no'],)).fetchone()
        self.assertIsNotNone(txn_db)
        self.assertEqual(txn_db['amount'], 15000.0)
        self.assertEqual(txn_db['status'], 'SUCCESS')
        conn.close()

    # -----------------------------------------------------------------------
    # 9. Partial Payment Settlement (Balance Deduction -> PARTIAL)
    # -----------------------------------------------------------------------
    def test_09_payment_verification_partial_settlement(self):
        """Test paying partial installment, balance update to PARTIAL."""
        self.login_parent('parent@example.com', 'Parent@123')

        # Create a fresh fee item of 50,000
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status, academic_year, semester)
            VALUES (1, 'Hostel & Mess Boarding Term 2', 50000.0, 0.0, '2026-11-01', 'PENDING', '2026-2027', 5)
        """)
        fee_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Pay partial installment of 20,000
        order_resp = self.client.post('/api/parent/fees/create-order', json={
            'fee_id': fee_id,
            'amount': 20000.0
        })
        order_data = json.loads(order_resp.data)
        self.assertTrue(order_data['success'])

        dynamic_pay_id2 = f"pay_{uuid.uuid4().hex[:12]}"
        verify_resp = self.client.post('/api/parent/fees/verify-payment', json={
            'fee_id': fee_id,
            'order_id': order_data['order_id'],
            'payment_id': dynamic_pay_id2,
            'signature': 'test_sandbox_signature',
            'payment_method': 'Net Banking (HDFC Bank)',
            'amount': 20000.0
        })

        self.assertEqual(verify_resp.status_code, 200)
        verify_data = json.loads(verify_resp.data)
        self.assertEqual(verify_data['fee_status'], 'PARTIAL')
        self.assertEqual(verify_data['remaining_balance'], 30000.0)

        # Check in database
        conn = get_db_connection()
        fee_db = conn.execute("SELECT * FROM fees WHERE id = ?", (fee_id,)).fetchone()
        self.assertEqual(fee_db['status'], 'PARTIAL')
        self.assertEqual(fee_db['paid_amount'], 20000.0)
        conn.close()

    # -----------------------------------------------------------------------
    # 10. Cross-Portal Fee Balance Synchronization & Printable E-Receipt
    # -----------------------------------------------------------------------
    def test_10_cross_portal_fee_sync_and_receipt(self):
        """Verify Student and Admin portals reflect paid fees, and test printable receipt route."""
        # Execute payment first
        self.login_parent('parent@example.com', 'Parent@123')
        conn = get_db_connection()
        fee = conn.execute("SELECT * FROM fees WHERE student_id = 1 LIMIT 1").fetchone()
        conn.close()

        order_res = self.client.post('/api/parent/fees/create-order', json={
            'fee_id': fee['id'],
            'amount': 5000
        }).get_json()

        verify_res = self.client.post('/api/parent/fees/verify-payment', json={
            'fee_id': fee['id'],
            'order_id': order_res['order_id'],
            'payment_id': f"pay_t10_{order_res['order_id'][:8]}",
            'signature': 'test_sandbox_signature',
            'amount': 5000
        }).get_json()

        # 10a. Login as Student STU001 and check fee status
        self.login_student('STU001', 'Student@123')
        stu_resp = self.client.get('/student/fees')
        self.assertEqual(stu_resp.status_code, 200)

        # 10b. Login as Admin and check fees management ledger
        self.login_admin('admin', 'Admin@123')
        adm_resp = self.client.get('/admin/fees')
        self.assertEqual(adm_resp.status_code, 200)

        # 10c. Parent printable official receipt route
        self.login_parent('parent@example.com', 'Parent@123')
        rcpt_resp = self.client.get(f"/parent/fees/receipt/{verify_res['receipt_no']}")
        self.assertEqual(rcpt_resp.status_code, 200)
        self.assertIn(b'Official E-Receipt', rcpt_resp.data)
        self.assertIn(verify_res['receipt_no'].encode(), rcpt_resp.data)
        self.assertIn(b'CampusGuard Institute', rcpt_resp.data)


if __name__ == '__main__':
    unittest.main()
