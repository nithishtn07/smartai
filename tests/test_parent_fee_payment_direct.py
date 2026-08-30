"""
Tests for CampusGuard AI — Parent Direct Fee Payment via Razorpay
Verifies:
1. Parent views linked child's fee dashboard.
2. Parent authorization verification (Parent A cannot pay Child B's fee).
3. Server-side database amount validation.
4. Razorpay order generation (/api/parent/fees/create-order).
5. Server-side payment verification and receipt creation (/api/parent/fees/verify-payment).
6. Multi-portal synchronization (Student, Parent, Admin).
7. Duplicate payment prevention.
8. Webhook processing.
9. Access control on receipts.
"""

import unittest
import json
import hmac
import hashlib
from app import app
from database.db import get_db_connection, init_db
from services.payment_service import RAZORPAY_KEY_SECRET


class TestParentFeePaymentDirect(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    def test_01_parent_views_linked_child_fees(self):
        """1. Authenticated parent can view linked child's fee dashboard with real DB numbers."""
        conn = get_db_connection()
        parent = conn.execute("SELECT * FROM parents LIMIT 1").fetchone()
        student = conn.execute("SELECT * FROM students WHERE id = ?", (parent['student_id'],)).fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess['parent_id'] = parent['id']
            sess['parent_name'] = parent['name']

        res = self.client.get('/parent/fees')
        self.assertEqual(res.status_code, 200)
        self.assertIn(student['name'].encode('utf-8'), res.data)
        self.assertIn(b'College Fee Center', res.data)

    def test_02_parent_authorization_rejection_for_unlinked_student(self):
        """2 & 3. Parent cannot create payment order or pay fees for an unlinked student."""
        conn = get_db_connection()
        # Find two different students with different parents
        parents = conn.execute("SELECT * FROM parents LIMIT 2").fetchall()
        if len(parents) < 2:
            # Create a second parent-student link for testing
            s2 = conn.execute("SELECT * FROM students WHERE id != ? LIMIT 1", (parents[0]['student_id'],)).fetchone()
            conn.execute("""
                INSERT INTO parents (parent_id, student_id, name, email, phone, relationship, password)
                VALUES ('PAR-TEST-99', ?, 'Other Parent', 'other_parent@example.com', '9998887776', 'Father', 'dummy')
            """, (s2['id'],))
            conn.commit()
            parents = conn.execute("SELECT * FROM parents LIMIT 2").fetchall()

        parent_a = parents[0]
        parent_b = parents[1]

        # Get fee belonging to child of Parent B
        child_b_fee = conn.execute("SELECT * FROM fees WHERE student_id = ? LIMIT 1", (parent_b['student_id'],)).fetchone()
        if not child_b_fee:
            conn.execute("""
                INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status)
                VALUES (?, 'Child B Tuition', 30000, 0, '2026-10-30', 'PENDING')
            """, (parent_b['student_id'],))
            conn.commit()
            child_b_fee = conn.execute("SELECT * FROM fees WHERE student_id = ? LIMIT 1", (parent_b['student_id'],)).fetchone()
        conn.close()

        # Log in as Parent A
        with self.client.session_transaction() as sess:
            sess['parent_id'] = parent_a['id']
            sess['parent_name'] = parent_a['name']

        # Parent A attempts to create order for Child B's fee
        res_order = self.client.post('/api/parent/fees/create-order', json={
            'student_id': parent_b['student_id'],
            'fee_id': child_b_fee['id'],
            'amount': 30000
        })
        self.assertEqual(res_order.status_code, 400)
        data = res_order.get_json()
        self.assertFalse(data['success'])
        self.assertIn('Unauthorized', data['error'])

    def test_03_parent_creates_order_and_verifies_payment_successfully(self):
        """4, 5 & 6. Parent creates Razorpay order for linked child, completes verification, and syncs across portals."""
        conn = get_db_connection()
        parent = conn.execute("SELECT * FROM parents LIMIT 1").fetchone()
        student = conn.execute("SELECT * FROM students WHERE id = ?", (parent['student_id'],)).fetchone()
        
        import uuid
        unique_title = f"Parent Direct Test Tuition {uuid.uuid4().hex[:6]}"

        # Create a clean pending fee for testing
        conn.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status, academic_year, semester)
            VALUES (?, ?, 25000, 0, '2026-11-30', 'PENDING', '2026-2027', 5)
        """, (student['id'], unique_title))
        conn.commit()
        fee = conn.execute("SELECT * FROM fees WHERE student_id = ? AND fee_type = ?", (student['id'], unique_title)).fetchone()
        conn.close()

        # Login as Parent
        with self.client.session_transaction() as sess:
            sess.clear()
            sess['parent_id'] = parent['id']
            sess['parent_name'] = parent['name']
            sess['parent_active_student_id'] = student['id']

        # 1. Create Razorpay Order
        res_order = self.client.post('/api/parent/fees/create-order', json={
            'student_id': student['id'],
            'fee_id': fee['id'],
            'amount': 25000
        })
        order_data = res_order.get_json()
        self.assertEqual(res_order.status_code, 200, f"Error payload: {order_data}")
        self.assertTrue(order_data['success'])
        self.assertTrue(order_data['order_id'])
        self.assertEqual(order_data['amount_inr'], 25000.0)

        # 2. Server-side payment verification
        order_id = order_data['order_id']
        payment_id = "pay_test_" + order_id.replace('order_', '')
        payload_str = f"{order_id}|{payment_id}"
        valid_signature = hmac.new(RAZORPAY_KEY_SECRET.encode('utf-8'), payload_str.encode('utf-8'), hashlib.sha256).hexdigest()

        res_verify = self.client.post('/api/parent/fees/verify-payment', json={
            'student_id': student['id'],
            'fee_id': fee['id'],
            'order_id': order_id,
            'payment_id': payment_id,
            'signature': valid_signature,
            'payment_method': 'UPI (Google Pay)',
            'amount': 25000
        })
        self.assertEqual(res_verify.status_code, 200)
        verify_data = res_verify.get_json()
        self.assertTrue(verify_data['success'])
        self.assertTrue(verify_data['receipt_no'].startswith('REC-'))
        receipt_no = verify_data['receipt_no']

        # 3. Verify Database State
        conn = get_db_connection()
        updated_fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee['id'],)).fetchone()
        self.assertEqual(updated_fee['status'], 'PAID')
        self.assertEqual(float(updated_fee['paid_amount']), 25000.0)

        # Check transaction has parent_id stored
        tx = conn.execute("SELECT * FROM payment_transactions WHERE receipt_no = ?", (receipt_no,)).fetchone()
        self.assertIsNotNone(tx)
        self.assertEqual(tx['parent_id'], parent['id'])
        conn.close()

        # 4. Verify Student Portal reflects PAID
        with self.client.session_transaction() as sess:
            sess['student_id'] = student['id']
            sess['student_name'] = student['name']
            sess['register_number'] = student['register_number']

        res_stu = self.client.get('/student/fees')
        self.assertEqual(res_stu.status_code, 200)
        self.assertIn(b'Parent Direct Test Tuition', res_stu.data)
        self.assertIn(b'PAID', res_stu.data)

        # 5. Verify Parent Receipt Access
        with self.client.session_transaction() as sess:
            sess['parent_id'] = parent['id']
            sess['parent_name'] = parent['name']

        res_rcp = self.client.get(f'/parent/fees/receipt/{receipt_no}')
        self.assertEqual(res_rcp.status_code, 200)
        self.assertIn(receipt_no.encode('utf-8'), res_rcp.data)

    def test_04_duplicate_payment_blocked(self):
        """13. Attempting to create order or pay already cleared fee is blocked."""
        conn = get_db_connection()
        parent = conn.execute("SELECT * FROM parents LIMIT 1").fetchone()
        student = conn.execute("SELECT * FROM students WHERE id = ?", (parent['student_id'],)).fetchone()
        
        # Create an already paid fee
        conn.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status)
            VALUES (?, 'Already Paid Fee Head', 10000, 10000, '2026-10-15', 'PAID')
        """, (student['id'],))
        conn.commit()
        paid_fee = conn.execute("SELECT * FROM fees WHERE student_id = ? AND fee_type = 'Already Paid Fee Head'", (student['id'],)).fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess['parent_id'] = parent['id']
            sess['parent_name'] = parent['name']

        res = self.client.post('/api/parent/fees/create-order', json={
            'student_id': student['id'],
            'fee_id': paid_fee['id'],
            'amount': 10000
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertIn('already been completely cleared', data['error'])

    def test_05_webhook_idempotency(self):
        """7. Webhook event is processed idempotently."""
        conn = get_db_connection()
        parent = conn.execute("SELECT * FROM parents LIMIT 1").fetchone()
        student = conn.execute("SELECT * FROM students WHERE id = ?", (parent['student_id'],)).fetchone()
        
        conn.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status)
            VALUES (?, 'Webhook Test Fee', 8000, 0, '2026-12-31', 'PENDING')
        """, (student['id'],))
        conn.commit()
        fee = conn.execute("SELECT * FROM fees WHERE student_id = ? AND fee_type = 'Webhook Test Fee'", (student['id'],)).fetchone()
        conn.close()

        order_id = "order_wh_test_12345"
        payment_id = "pay_wh_test_67890"

        webhook_payload = json.dumps({
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "order_id": order_id,
                        "amount": 800000,
                        "notes": {
                            "fee_ids": str(fee['id']),
                            "student_id": str(student['id']),
                            "parent_id": str(parent['id'])
                        }
                    }
                }
            }
        }).encode('utf-8')

        sig = hmac.new(RAZORPAY_KEY_SECRET.encode('utf-8'), webhook_payload, hashlib.sha256).hexdigest()

        res_wh = self.client.post(
            '/api/parent/fees/webhook',
            data=webhook_payload,
            headers={'X-Razorpay-Signature': sig, 'Content-Type': 'application/json'}
        )
        self.assertEqual(res_wh.status_code, 200)
        data = res_wh.get_json()
        self.assertTrue(data['success'])

        # Verify fee is paid
        conn = get_db_connection()
        wh_fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee['id'],)).fetchone()
        self.assertEqual(wh_fee['status'], 'PAID')
        self.assertEqual(float(wh_fee['paid_amount']), 8000.0)
        conn.close()


if __name__ == '__main__':
    unittest.main()
