"""
CampusGuard AI — Fee & Payment Transaction Models
"""

import datetime
import uuid
from database.db import get_db_connection


class FeeModel:
    @staticmethod
    def get_by_student(student_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM fees WHERE student_id = ? ORDER BY id ASC", (student_id,)).fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_all_with_students():
        conn = get_db_connection()
        try:
            return conn.execute("""
                SELECT f.*, s.name as student_name, s.register_number, s.department
                FROM fees f
                JOIN students s ON f.student_id = s.id
                ORDER BY f.id DESC
            """).fetchall()
        finally:
            conn.close()

    @staticmethod
    def create(student_id, fee_type, amount, due_date, paid_amount=0, status="PENDING"):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (int(student_id), fee_type, float(amount), float(paid_amount), due_date, status))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    @staticmethod
    def mark_paid(fee_id):
        conn = get_db_connection()
        try:
            fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee_id,)).fetchone()
            if fee:
                conn.execute("""
                    UPDATE fees SET paid_amount = amount, status = 'PAID' WHERE id = ?
                """, (fee_id,))
                
                # Record payment transaction
                tx_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
                rcp_no = f"REC-{uuid.uuid4().hex[:6].upper()}"
                paid_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                conn.execute("""
                    INSERT INTO payment_transactions (transaction_id, student_id, fee_type, amount, payment_method, receipt_no, paid_at)
                    VALUES (?, ?, ?, ?, 'Admin Cash/Transfer', ?, ?)
                """, (tx_id, fee['student_id'], fee['fee_type'], fee['amount'], rcp_no, paid_at))
                
                conn.commit()
                return True
            return False
        finally:
            conn.close()


class PaymentTransactionModel:
    @staticmethod
    def get_by_student(student_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM payment_transactions WHERE student_id = ? ORDER BY id DESC", (student_id,)).fetchall()
        finally:
            conn.close()
