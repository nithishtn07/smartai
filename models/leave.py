"""
CampusGuard AI — Hostel & Leave / Outpass Models
"""

from database.db import get_db_connection


class HostelModel:
    @staticmethod
    def get_by_student(student_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM hostel_details WHERE student_id = ?", (student_id,)).fetchone()
        finally:
            conn.close()


class HostelLeaveModel:
    @staticmethod
    def get_by_student(student_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM hostel_leaves WHERE student_id = ? ORDER BY id DESC", (student_id,)).fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_all_with_students():
        conn = get_db_connection()
        try:
            return conn.execute("""
                SELECT hl.*, s.name as student_name, s.register_number, s.department
                FROM hostel_leaves hl
                JOIN students s ON hl.student_id = s.id
                ORDER BY hl.id DESC
            """).fetchall()
        finally:
            conn.close()

    @staticmethod
    def create(student_id, leave_type, from_date, to_date, reason):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO hostel_leaves (student_id, leave_type, from_date, to_date, reason, status)
                VALUES (?, ?, ?, ?, ?, 'Pending')
            """, (int(student_id), leave_type, from_date, to_date, reason))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    @staticmethod
    def set_status(leave_id, status):
        conn = get_db_connection()
        try:
            conn.execute("UPDATE hostel_leaves SET status = ? WHERE id = ?", (status, leave_id))
            conn.commit()
            return True
        finally:
            conn.close()


class StudentRequestModel:
    @staticmethod
    def get_by_student(student_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM student_requests WHERE student_id = ? ORDER BY id DESC", (student_id,)).fetchall()
        finally:
            conn.close()

    @staticmethod
    def create(student_id, request_type, details):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO student_requests (student_id, request_type, details, status)
                VALUES (?, ?, ?, 'Submitted')
            """, (int(student_id), request_type, details))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
