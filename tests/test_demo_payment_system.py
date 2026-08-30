"""
Unit & Integration Tests for CampusGuard AI — Demo Payment System (Hackathon Safe Simulation)
"""

import unittest
import uuid
from app import app
from database.db import get_db_connection, init_db


class TestDemoPaymentSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    def test_01_parent_views_fee_breakdown(self):
        """Parent views child fee ledger with real database values."""
        conn = get_db_connection()
        parent = conn.execute("SELECT * FROM parents LIMIT 1").fetchone()
        student = conn.execute("SELECT * FROM students WHERE id = ?", (parent['student_id'],)).fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess.clear()
            sess['parent_id'] = parent['id']
            sess['parent_name'] = parent['name']
            sess['parent_active_student_id'] = student['id']

        res = self.client.get('/parent/fees')
        self.assertEqual(res.status_code, 200)
        self.assertIn(student['name'].encode('utf-8'), res.data)
        self.assertIn(b'Demo Fee Checkout', res.data)

    def test_02_successful_demo_payment_flow(self):
        """Parent completes demo payment -> DB updated -> Receipt generated -> Synced across portals."""
        conn = get_db_connection()
        parent = conn.execute("SELECT * FROM parents LIMIT 1").fetchone()
        student = conn.execute("SELECT * FROM students WHERE id = ?", (parent['student_id'],)).fetchone()
        
        unique_title = f"Demo Tuition Head {uuid.uuid4().hex[:6]}"
        conn.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status, academic_year, semester)
            VALUES (?, ?, 25000, 0, '2026-10-30', 'PENDING', '2026-2027', 5)
        """, (student['id'], unique_title))
        conn.commit()
        fee = conn.execute("SELECT * FROM fees WHERE student_id = ? AND fee_type = ?", (student['id'], unique_title)).fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess.clear()
            sess['parent_id'] = parent['id']
            sess['parent_name'] = parent['name']
            sess['parent_active_student_id'] = student['id']

        # Settle via demo-pay API
        res = self.client.post('/api/parent/fees/demo-pay', json={
            'student_id': student['id'],
            'fee_id': fee['id'],
            'amount': 25000,
            'payment_method': 'Demo UPI (Google Pay)',
            'simulate_failure': False
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['receipt_no'].startswith('REC-DEMO-'))
        receipt_no = data['receipt_no']

        # Verify DB fee state
        conn = get_db_connection()
        updated_fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee['id'],)).fetchone()
        self.assertEqual(updated_fee['status'], 'PAID')
        self.assertEqual(float(updated_fee['paid_amount']), 25000.0)
        conn.close()

        # Verify Parent Receipt View
        res_rcp = self.client.get(f'/parent/fees/receipt/{receipt_no}')
        self.assertEqual(res_rcp.status_code, 200)
        self.assertIn(b'DEMO TRANSACTION', res_rcp.data)

        # Verify Student Portal Sync
        with self.client.session_transaction() as sess:
            sess.clear()
            sess['student_id'] = student['id']
            sess['student_name'] = student['name']
            sess['register_number'] = student['register_number']

        res_stu = self.client.get('/student/fees')
        self.assertEqual(res_stu.status_code, 200)
        self.assertIn(unique_title.encode('utf-8'), res_stu.data)

    def test_03_simulated_payment_failure(self):
        """Simulating payment failure returns error and preserves PENDING fee status."""
        conn = get_db_connection()
        parent = conn.execute("SELECT * FROM parents LIMIT 1").fetchone()
        student = conn.execute("SELECT * FROM students WHERE id = ?", (parent['student_id'],)).fetchone()
        
        unique_title = f"Demo Failure Test {uuid.uuid4().hex[:6]}"
        conn.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status, academic_year, semester)
            VALUES (?, ?, 15000, 0, '2026-11-15', 'PENDING', '2026-2027', 5)
        """, (student['id'], unique_title))
        conn.commit()
        fee = conn.execute("SELECT * FROM fees WHERE student_id = ? AND fee_type = ?", (student['id'], unique_title)).fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess.clear()
            sess['parent_id'] = parent['id']
            sess['parent_name'] = parent['name']
            sess['parent_active_student_id'] = student['id']

        res = self.client.post('/api/parent/fees/demo-pay', json={
            'student_id': student['id'],
            'fee_id': fee['id'],
            'amount': 15000,
            'payment_method': 'Demo Card',
            'simulate_failure': True
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('declined the transaction', data['error'])

        # Fee must remain PENDING
        conn = get_db_connection()
        chk_fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee['id'],)).fetchone()
        self.assertEqual(chk_fee['status'], 'PENDING')
        self.assertEqual(float(chk_fee['paid_amount']), 0.0)
        conn.close()

    def test_04_duplicate_payment_blocked(self):
        """Already paid fee cannot be paid again."""
        conn = get_db_connection()
        parent = conn.execute("SELECT * FROM parents LIMIT 1").fetchone()
        student = conn.execute("SELECT * FROM students WHERE id = ?", (parent['student_id'],)).fetchone()
        
        unique_title = f"Already Paid Demo {uuid.uuid4().hex[:6]}"
        conn.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status, academic_year, semester)
            VALUES (?, ?, 10000, 10000, '2026-09-01', 'PAID', '2026-2027', 5)
        """, (student['id'], unique_title))
        conn.commit()
        fee = conn.execute("SELECT * FROM fees WHERE student_id = ? AND fee_type = ?", (student['id'], unique_title)).fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess.clear()
            sess['parent_id'] = parent['id']
            sess['parent_name'] = parent['name']
            sess['parent_active_student_id'] = student['id']

        res = self.client.post('/api/parent/fees/demo-pay', json={
            'student_id': student['id'],
            'fee_id': fee['id'],
            'amount': 10000
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('already been fully paid', data['error'])

    def test_05_parent_authorization_security(self):
        """Parent A cannot pay fees for Student B."""
        conn = get_db_connection()
        parents = conn.execute("SELECT * FROM parents LIMIT 2").fetchall()
        parent_a = parents[0]
        # Get another student not linked to Parent A
        other_student = conn.execute("SELECT * FROM students WHERE id != ? LIMIT 1", (parent_a['student_id'],)).fetchone()
        other_fee = conn.execute("SELECT * FROM fees WHERE student_id = ? LIMIT 1", (other_student['id'],)).fetchone()
        if not other_fee:
            conn.execute("""
                INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status)
                VALUES (?, 'Other Student Fee', 12000, 0, '2026-10-30', 'PENDING')
            """, (other_student['id'],))
            conn.commit()
            other_fee = conn.execute("SELECT * FROM fees WHERE student_id = ? LIMIT 1", (other_student['id'],)).fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess.clear()
            sess['parent_id'] = parent_a['id']
            sess['parent_name'] = parent_a['name']
            sess['parent_active_student_id'] = parent_a['student_id']

        res = self.client.post('/api/parent/fees/demo-pay', json={
            'student_id': other_student['id'],
            'fee_id': other_fee['id'],
            'amount': 12000
        })
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Unauthorized access', data['error'])

    def test_06_direct_checkout_redirect_and_form_payment(self):
        """Parent clicks Pay Now -> redirected to /parent/fees/checkout/<fee_id> -> submits form -> payment completed -> redirects to receipt."""
        conn = get_db_connection()
        parent = conn.execute("SELECT * FROM parents LIMIT 1").fetchone()
        student = conn.execute("SELECT * FROM students WHERE id = ?", (parent['student_id'],)).fetchone()
        
        unique_title = f"Direct Checkout Test {uuid.uuid4().hex[:6]}"
        conn.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status, academic_year, semester)
            VALUES (?, ?, 18000, 0, '2026-11-20', 'PENDING', '2026-2027', 5)
        """, (student['id'], unique_title))
        conn.commit()
        fee = conn.execute("SELECT * FROM fees WHERE student_id = ? AND fee_type = ?", (student['id'], unique_title)).fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess.clear()
            sess['parent_id'] = parent['id']
            sess['parent_name'] = parent['name']
            sess['parent_active_student_id'] = student['id']

        # 1. Access Checkout Page
        res_checkout = self.client.get(f"/parent/fees/checkout/{fee['id']}")
        self.assertEqual(res_checkout.status_code, 200)
        self.assertIn(b'Secure Fee Payment Checkout', res_checkout.data)
        self.assertIn(unique_title.encode('utf-8'), res_checkout.data)

        # 2. Submit Payment Form
        res_pay = self.client.post('/parent/fees/pay', data={
            'fee_id': str(fee['id']),
            'student_id': str(student['id']),
            'payment_mode': 'full',
            'payment_method': 'Demo UPI (Google Pay / PhonePe)'
        }, follow_redirects=False)
        
        # Should redirect to receipt
        self.assertEqual(res_pay.status_code, 302)
        self.assertIn('/parent/fees/receipt/', res_pay.headers.get('Location', ''))

        # 3. Follow Redirect to Receipt Page
        res_rcp = self.client.get(res_pay.headers.get('Location'))
        self.assertEqual(res_rcp.status_code, 200)
        self.assertIn(b'DEMO TRANSACTION', res_rcp.data)

        # 4. Verify DB updated to PAID
        conn = get_db_connection()
        chk_fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee['id'],)).fetchone()
        self.assertEqual(chk_fee['status'], 'PAID')
        self.assertEqual(float(chk_fee['paid_amount']), 18000.0)
        conn.close()


if __name__ == '__main__':
    unittest.main()

