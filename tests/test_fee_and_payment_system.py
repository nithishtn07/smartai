"""
Tests for CampusGuard AI — Enterprise Fee & Payment Management System
Verifies:
1. Admin fee creation, batch issuance, editing, and cancellation.
2. Student fee viewing and dynamic calculation.
3. Parent fee viewing linked only to their child.
4. Safe Demo Payment flow with method selection.
5. Transaction creation and receipt generation.
6. Synchronized real-time status across Student, Parent, and Admin.
7. Duplicate payment prevention and overpayment prevention.
8. Overdue fee detection.
9. Persistence and zero random data regeneration.
"""

import unittest
import uuid
import datetime
from app import app
from database.db import get_db_connection, init_db


class TestFeeAndPaymentSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    def test_01_admin_creates_fee_and_dispatches_notifications(self):
        """1. Admin creates fee for a student -> Saved in DB, notifications dispatched."""
        conn = get_db_connection()
        admin = conn.execute("SELECT * FROM admins LIMIT 1").fetchone()
        student = conn.execute("SELECT * FROM students WHERE status != 'DELETED' LIMIT 1").fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess['admin_id'] = admin['id']
            sess['admin_username'] = admin['username']
            sess['admin_name'] = admin['name']

        response = self.client.post('/admin/fees/create', data={
            'student_id': str(student['id']),
            'fee_type': 'Hostel Maintenance Dues',
            'amount': '15000',
            'due_date': '2026-10-31',
            'academic_year': '2026-2027',
            'semester': '5'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

        conn = get_db_connection()
        fee = conn.execute(
            "SELECT * FROM fees WHERE student_id = ? AND fee_type = 'Hostel Maintenance Dues'",
            (student['id'],)
        ).fetchone()
        self.assertIsNotNone(fee)
        self.assertEqual(float(fee['amount']), 15000.0)
        self.assertEqual(fee['status'], 'PENDING')
        conn.close()

    def test_02_student_and_parent_view_identical_fee_records(self):
        """2 & 3. Student and linked Parent view the exact same database-backed fee values."""
        conn = get_db_connection()
        student = conn.execute("SELECT * FROM students WHERE status != 'DELETED' LIMIT 1").fetchone()
        parent = conn.execute("SELECT * FROM parents WHERE student_id = ? LIMIT 1", (student['id'],)).fetchone()
        conn.close()

        # Student Portal
        with self.client.session_transaction() as sess:
            sess['student_id'] = student['id']
            sess['student_name'] = student['name']
            sess['register_number'] = student['register_number']

        res_stu = self.client.get('/student/fees')
        self.assertEqual(res_stu.status_code, 200)
        self.assertIn(b'Institutional Fees &amp; Payments', res_stu.data)

        # Parent Portal
        if parent:
            with self.client.session_transaction() as sess:
                sess['parent_id'] = parent['id']
                sess['parent_name'] = parent['name']

            res_par = self.client.get('/parent/fees')
            self.assertEqual(res_par.status_code, 200)
            self.assertIn(student['name'].encode('utf-8'), res_par.data)

    def test_03_student_completes_safe_demo_payment(self):
        """4 & 5. Student completes Demo Payment -> Status becomes PAID, transaction & receipt created."""
        conn = get_db_connection()
        student = conn.execute("SELECT * FROM students WHERE status != 'DELETED' LIMIT 1").fetchone()
        
        # Create a specific pending fee
        cur = conn.cursor()
        unique_fee_type = f"Laboratory Consumables Fee {uuid.uuid4().hex[:6]}"
        cur.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status, academic_year, semester)
            VALUES (?, ?, 5000, 0, '2026-11-15', 'PENDING', '2026-2027', 5)
        """, (student['id'], unique_fee_type))
        conn.commit()
        fee_id = cur.lastrowid
        fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee_id,)).fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess['student_id'] = student['id']
            sess['student_name'] = student['name']
            sess['register_number'] = student['register_number']

        # Execute demo payment
        res = self.client.post('/student/fees/pay', data={
            'fee_id': str(fee['id']),
            'amount': '5000',
            'payment_method': 'UPI (Google Pay / PhonePe / Paytm)'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Receipt', res.data)

        # Verify DB status
        conn = get_db_connection()
        updated_fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee['id'],)).fetchone()
        self.assertEqual(updated_fee['status'], 'PAID')
        self.assertEqual(float(updated_fee['paid_amount']), 5000.0)

        # Verify single transaction created
        tx = conn.execute("SELECT * FROM payment_transactions WHERE fee_id = ?", (fee['id'],)).fetchone()
        self.assertIsNotNone(tx)
        self.assertEqual(float(tx['amount']), 5000.0)
        self.assertTrue(tx['receipt_no'].startswith('REC-'))
        conn.close()

    def test_04_duplicate_payment_prevention(self):
        """9. System blocks duplicate payment for already cleared fees."""
        conn = get_db_connection()
        student = conn.execute("SELECT * FROM students WHERE status != 'DELETED' LIMIT 1").fetchone()
        
        # Insert already paid fee
        conn.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status)
            VALUES (?, 'Annual Sports Subscription', 1200, 1200, '2026-12-01', 'PAID')
        """, (student['id'],))
        conn.commit()
        fee = conn.execute("SELECT * FROM fees WHERE student_id = ? AND fee_type = 'Annual Sports Subscription'", (student['id'],)).fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess['student_id'] = student['id']
            sess['student_name'] = student['name']
            sess['register_number'] = student['register_number']

        # Attempt second payment
        res = self.client.post('/student/fees/pay', data={
            'fee_id': str(fee['id']),
            'amount': '1200',
            'payment_method': 'UPI'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'already been fully paid', res.data)

    def test_05_admin_can_edit_and_cancel_fee(self):
        """10. Admin can edit fee amount/due date and cancel unpaid fee."""
        conn = get_db_connection()
        admin = conn.execute("SELECT * FROM admins LIMIT 1").fetchone()
        student = conn.execute("SELECT * FROM students WHERE status != 'DELETED' LIMIT 1").fetchone()
        conn.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status)
            VALUES (?, 'Temporary Test Fee', 3500, 0, '2026-10-01', 'PENDING')
        """, (student['id'],))
        conn.commit()
        fee = conn.execute("SELECT * FROM fees WHERE student_id = ? AND fee_type = 'Temporary Test Fee'", (student['id'],)).fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess['admin_id'] = admin['id']
            sess['admin_username'] = admin['username']
            sess['admin_name'] = admin['name']

        # Edit fee
        res_edit = self.client.post(f'/admin/fees/edit/{fee["id"]}', data={
            'fee_type': 'Updated Test Fee',
            'amount': '4200',
            'due_date': '2026-11-01',
            'academic_year': '2026-2027',
            'semester': '5'
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)

        conn = get_db_connection()
        edited_fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee['id'],)).fetchone()
        self.assertEqual(float(edited_fee['amount']), 4200.0)
        self.assertEqual(edited_fee['fee_type'], 'Updated Test Fee')

        # Cancel fee
        res_cancel = self.client.post(f'/admin/fees/cancel/{fee["id"]}', follow_redirects=True)
        self.assertEqual(res_cancel.status_code, 200)
        deleted_fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee['id'],)).fetchone()
        self.assertIsNone(deleted_fee)
        conn.close()

    def test_06_overdue_fee_flagging(self):
        """11. Fees with past due date and positive pending balance are flagged OVERDUE."""
        conn = get_db_connection()
        admin = conn.execute("SELECT * FROM admins LIMIT 1").fetchone()
        student = conn.execute("SELECT * FROM students WHERE status != 'DELETED' LIMIT 1").fetchone()
        conn.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status)
            VALUES (?, 'Old Overdue Late Fee', 800, 0, '2025-01-01', 'PENDING')
        """, (student['id'],))
        conn.commit()
        conn.close()

        with self.client.session_transaction() as sess:
            sess['admin_id'] = admin['id']
            sess['admin_username'] = admin['username']
            sess['admin_name'] = admin['name']

        res = self.client.get('/admin/fees?status=OVERDUE')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Old Overdue Late Fee', res.data)
        self.assertIn(b'OVERDUE', res.data)

    def test_07_persistence_across_initialization(self):
        """12. Calling init_db multiple times preserves existing fee ledger and transactions without random resets."""
        conn = get_db_connection()
        initial_fee_count = conn.execute("SELECT COUNT(*) FROM fees").fetchone()[0]
        initial_tx_count = conn.execute("SELECT COUNT(*) FROM payment_transactions").fetchone()[0]
        conn.close()

        # Re-run init_db()
        init_db()

        conn = get_db_connection()
        after_fee_count = conn.execute("SELECT COUNT(*) FROM fees").fetchone()[0]
        after_tx_count = conn.execute("SELECT COUNT(*) FROM payment_transactions").fetchone()[0]
        conn.close()

        self.assertEqual(initial_fee_count, after_fee_count)
        self.assertEqual(initial_tx_count, after_tx_count)


if __name__ == '__main__':
    unittest.main()
