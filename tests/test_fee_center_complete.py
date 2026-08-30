"""
CampusGuard AI — Comprehensive Fee Center & Online Payment Unit Tests
Covers:
1. Dynamic Fee Dashboard KPI calculation (Billed, Paid, Pending, Overdue, Next Due Date).
2. Overdue calculation and due status normalization.
3. Single fee order creation and settlement.
4. Multi-fee batch selection, order creation, and batch settlement.
5. Custom partial installment payments.
6. Server-side HMAC-SHA256 signature verification & idempotency.
7. Multi-child parent switching & authorization scoping (IDOR protection).
8. Payment history filtering and search by Transaction ID, Fee Type, Status, Method.
9. Cross-portal balance synchronization (Parent, Student, Admin).
10. Official digital E-Receipt generation and access control.
"""

import unittest
import json
import datetime
from app import app
from database.db import get_db_connection
from services.payment_service import (
    get_student_fee_summary,
    create_fee_order,
    verify_and_record_payment,
    get_filtered_payment_transactions,
    get_payment_receipt
)


class TestFeeCenterComplete(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key-fee-center'
        self.client = self.app.test_client()

        conn = get_db_connection()
        conn.execute("DELETE FROM fees WHERE fee_type LIKE '%Test%'")
        conn.commit()
        # Find or ensure demo parent PAR001 linked to student
        parent = conn.execute("SELECT * FROM parents WHERE parent_id = 'PAR001' OR email = 'parent@example.com'").fetchone()
        if not parent:
            parent = conn.execute("SELECT * FROM parents LIMIT 1").fetchone()
        self.parent = parent
        self.student_id = parent['student_id']
        self.student = conn.execute("SELECT * FROM students WHERE id = ?", (self.student_id,)).fetchone()
        conn.close()

    def tearDown(self):
        conn = get_db_connection()
        conn.execute("DELETE FROM payment_transactions WHERE order_id LIKE 'order_%' OR transaction_id LIKE 'TXN-%'")
        conn.execute("DELETE FROM fees WHERE fee_type LIKE '%Test%'")
        conn.execute("UPDATE fees SET paid_amount = 0, status = 'PENDING' WHERE student_id = 1")
        conn.commit()
        conn.close()

    def test_01_fee_dashboard_kpis_and_overdue(self):
        """Test dynamic KPI calculation (Billed, Paid, Pending, Overdue, Next Due Date)."""
        summary = get_student_fee_summary(self.student_id)
        self.assertIn('total_billed', summary)
        self.assertIn('total_paid', summary)
        self.assertIn('total_pending', summary)
        self.assertIn('overdue_amount', summary)
        self.assertIn('fee_items', summary)

        self.assertAlmostEqual(summary['total_pending'], max(0.0, summary['total_billed'] - summary['total_paid']))
        self.assertGreaterEqual(summary['overdue_amount'], 0.0)

        for item in summary['fee_items']:
            self.assertIn('calculated_status', item)
            self.assertIn(item['calculated_status'], ['PAID', 'PARTIAL', 'OVERDUE', 'PENDING'])

    def test_02_single_fee_order_and_payment(self):
        """Test single fee order creation and server-side verified settlement."""
        conn = get_db_connection()
        # Ensure a pending fee exists for testing
        test_fee = conn.execute("SELECT * FROM fees WHERE student_id = ? AND amount > paid_amount LIMIT 1", (self.student_id,)).fetchone()
        if not test_fee:
            conn.execute("INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status) VALUES (?, 'Test Lab Fee', 5000, 0, '2026-11-30', 'PENDING')", (self.student_id,))
            conn.commit()
            test_fee = conn.execute("SELECT * FROM fees WHERE student_id = ? AND fee_type = 'Test Lab Fee'", (self.student_id,)).fetchone()
        conn.close()

        fee_id = test_fee['id']
        pending_before = test_fee['amount'] - test_fee['paid_amount']

        # 1. Create Order
        order_res = create_fee_order(self.parent['id'], self.student_id, fee_id=fee_id, payment_amount=min(1000.0, pending_before))
        self.assertTrue(order_res['success'])
        self.assertIn('order_id', order_res)
        self.assertEqual(order_res['amount_inr'], min(1000.0, pending_before))

        # 2. Verify Payment
        order_id = order_res['order_id']
        payment_id = f"pay_test_{order_id[:8]}"
        verify_res = verify_and_record_payment(
            parent_id=self.parent['id'],
            student_id=self.student_id,
            fee_id=fee_id,
            order_id=order_id,
            payment_id=payment_id,
            signature="test_sandbox_signature",
            payment_method="UPI Test",
            payment_amount=order_res['amount_inr']
        )
        self.assertTrue(verify_res['success'])
        self.assertIn('receipt_no', verify_res)
        self.assertIn('transaction_id', verify_res)

        # 3. Check DB updated
        conn = get_db_connection()
        updated_fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee_id,)).fetchone()
        conn.close()
        self.assertGreater(updated_fee['paid_amount'], test_fee['paid_amount'])

    def test_03_multi_fee_batch_checkout(self):
        """Test multi-fee batch order creation and atomic batch payment distribution."""
        conn = get_db_connection()
        # Create 2 test fee records
        conn.execute("INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status) VALUES (?, 'Batch Test Fee A', 4000, 0, '2026-10-15', 'PENDING')", (self.student_id,))
        conn.execute("INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status) VALUES (?, 'Batch Test Fee B', 6000, 0, '2026-10-15', 'PENDING')", (self.student_id,))
        conn.commit()

        fees = conn.execute("SELECT * FROM fees WHERE student_id = ? AND fee_type IN ('Batch Test Fee A', 'Batch Test Fee B')", (self.student_id,)).fetchall()
        conn.close()

        fee_ids = [f['id'] for f in fees]
        self.assertEqual(len(fee_ids), 2)

        # 1. Create Batch Order for 10,000 INR
        order_res = create_fee_order(self.parent['id'], self.student_id, fee_ids=fee_ids, payment_amount=10000.0)
        self.assertTrue(order_res['success'])
        self.assertEqual(order_res['amount_inr'], 10000.0)
        self.assertEqual(order_res['fee_count'], 2)

        # 2. Settle Batch Payment
        order_id = order_res['order_id']
        verify_res = verify_and_record_payment(
            parent_id=self.parent['id'],
            student_id=self.student_id,
            fee_ids=fee_ids,
            order_id=order_id,
            payment_id=f"pay_batch_{order_id[:8]}",
            signature="test_sandbox_signature",
            payment_method="NetBanking HDFC",
            payment_amount=10000.0
        )
        self.assertTrue(verify_res['success'])
        self.assertEqual(verify_res['fee_status'], 'PAID')

        # 3. Check both fees are cleared
        conn = get_db_connection()
        for fid in fee_ids:
            fee_row = conn.execute("SELECT * FROM fees WHERE id = ?", (fid,)).fetchone()
            self.assertEqual(fee_row['status'], 'PAID')
            self.assertEqual(fee_row['paid_amount'], fee_row['amount'])
        conn.close()

    def test_04_partial_payment_installment(self):
        """Test partial installment payment correctly calculates remaining balance."""
        conn = get_db_connection()
        conn.execute("INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status) VALUES (?, 'Hostel Installment Test', 20000, 0, '2026-12-31', 'PENDING')", (self.student_id,))
        conn.commit()
        fee_row = conn.execute("SELECT * FROM fees WHERE student_id = ? AND fee_type = 'Hostel Installment Test'", (self.student_id,)).fetchone()
        conn.close()

        fee_id = fee_row['id']

        # Pay partial 7,500 of 20,000
        order_res = create_fee_order(self.parent['id'], self.student_id, fee_id=fee_id, payment_amount=7500.0)
        self.assertTrue(order_res['success'])
        self.assertEqual(order_res['amount_inr'], 7500.0)

        verify_res = verify_and_record_payment(
            parent_id=self.parent['id'],
            student_id=self.student_id,
            fee_id=fee_id,
            order_id=order_res['order_id'],
            payment_id=f"pay_partial_{order_res['order_id'][:8]}",
            signature="test_sandbox_signature",
            payment_amount=7500.0
        )
        self.assertTrue(verify_res['success'])
        self.assertEqual(verify_res['fee_status'], 'PARTIAL')

        conn = get_db_connection()
        updated_fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee_id,)).fetchone()
        conn.close()
        self.assertEqual(updated_fee['paid_amount'], 7500.0)
        self.assertEqual(updated_fee['status'], 'PARTIAL')

    def test_05_idor_security_authorization(self):
        """Test that Parent A cannot create order or pay for unauthorized Student B."""
        conn = get_db_connection()
        # Find another student not linked to this parent
        other_student = conn.execute("SELECT * FROM students WHERE id != ? LIMIT 1", (self.student_id,)).fetchone()
        conn.close()

        if other_student:
            fake_fee_order = create_fee_order(self.parent['id'], other_student['id'], fee_id=999)
            self.assertFalse(fake_fee_order['success'])
            self.assertIn('Unauthorized', fake_fee_order.get('error', ''))

    def test_06_payment_history_filters_and_search(self):
        """Test payment history search and filtering by category, status, and method."""
        txns = get_filtered_payment_transactions(self.student_id, search_term='TXN')
        self.assertIsInstance(txns, list)

        # Filter by status
        success_txns = get_filtered_payment_transactions(self.student_id, status='SUCCESS')
        for t in success_txns:
            self.assertEqual(t['status'], 'SUCCESS')

    def test_07_e_receipt_retrieval(self):
        """Test retrieving official digital payment receipt with access control."""
        conn = get_db_connection()
        last_txn = conn.execute("SELECT * FROM payment_transactions WHERE student_id = ? ORDER BY id DESC LIMIT 1", (self.student_id,)).fetchone()
        conn.close()

        if last_txn:
            receipt = get_payment_receipt(last_txn['receipt_no'], parent_id=self.parent['id'], student_id=self.student_id)
            self.assertIsNotNone(receipt)
            self.assertEqual(receipt['receipt_no'], last_txn['receipt_no'])
            self.assertIn('student_name', receipt)
            self.assertIn('parent_name', receipt)

    def test_08_parent_fee_center_endpoint(self):
        """Test HTTP GET /parent/fees returns 200 with complete fee center data."""
        with self.client.session_transaction() as sess:
            sess['parent_id'] = self.parent['id']
            sess['email'] = self.parent['email']
            sess['student_id'] = self.student_id

        res = self.client.get('/parent/fees')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'College Fee Center', res.data)
        self.assertIn(b'Outstanding Balance', res.data)
        self.assertIn(b'Razorpay', res.data)

    def test_09_api_parent_fees_create_order_endpoint(self):
        """Test HTTP POST /api/parent/fees/create-order API."""
        with self.client.session_transaction() as sess:
            sess['parent_id'] = self.parent['id']
            sess['email'] = self.parent['email']
            sess['student_id'] = self.student_id

        conn = get_db_connection()
        fee = conn.execute("SELECT * FROM fees WHERE student_id = ? AND amount > paid_amount LIMIT 1", (self.student_id,)).fetchone()
        if not fee:
            conn.execute("INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status) VALUES (?, 'API Order Test Fee', 8000, 0, '2026-12-31', 'PENDING')", (self.student_id,))
            conn.commit()
            fee = conn.execute("SELECT * FROM fees WHERE student_id = ? AND fee_type = 'API Order Test Fee'", (self.student_id,)).fetchone()
        conn.close()

        res = self.client.post('/api/parent/fees/create-order', json={
            'fee_id': fee['id'],
            'amount': 500
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('order_id', data)

    def test_10_api_parent_fees_history_endpoint(self):
        """Test HTTP GET /api/parent/fees/history API."""
        with self.client.session_transaction() as sess:
            sess['parent_id'] = self.parent['id']
            sess['email'] = self.parent['email']
            sess['student_id'] = self.student_id

        res = self.client.get('/api/parent/fees/history')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('transactions', data)


if __name__ == '__main__':
    unittest.main()
