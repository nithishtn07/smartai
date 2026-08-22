"""
CampusGuard AI — Attendance Models & Calculations
"""

from database.db import get_db_connection


class AttendanceModel:
    @staticmethod
    def get_by_student(student_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM attendance WHERE student_id = ?", (student_id,)).fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_logs_by_student(student_id, limit=20):
        conn = get_db_connection()
        try:
            return conn.execute("""
                SELECT * FROM attendance_logs 
                WHERE student_id = ? 
                ORDER BY date DESC, id DESC 
                LIMIT ?
            """, (student_id, limit)).fetchall()
        finally:
            conn.close()

    @staticmethod
    def record_attendance(student_id, course_code, course_name, status, date, topic=""):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # 1. Insert into logs
            cursor.execute("""
                INSERT INTO attendance_logs (student_id, course_code, course_name, date, status, topic)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (student_id, course_code, course_name, date, status, topic))

            # 2. Update aggregate attendance row
            existing = cursor.execute("""
                SELECT * FROM attendance WHERE student_id = ? AND subject_code = ?
            """, (student_id, course_code)).fetchone()

            is_present = (status.lower() == 'present')
            if existing:
                held = existing['classes_held'] + 1
                att = existing['classes_attended'] + (1 if is_present else 0)
                miss = existing['classes_missed'] + (0 if is_present else 1)
                pct = round((att / held) * 100.0, 1)
                cursor.execute("""
                    UPDATE attendance 
                    SET classes_held = ?, classes_attended = ?, classes_missed = ?, attendance_pct = ?
                    WHERE id = ?
                """, (held, att, miss, pct, existing['id']))
            else:
                held = 1
                att = 1 if is_present else 0
                miss = 0 if is_present else 1
                pct = 100.0 if is_present else 0.0
                cursor.execute("""
                    INSERT INTO attendance (student_id, subject_code, subject_name, classes_held, classes_attended, classes_missed, attendance_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (student_id, course_code, course_name, held, att, miss, pct))

            conn.commit()
            return True
        finally:
            conn.close()

    @staticmethod
    def get_low_attendance_students(threshold=75.0):
        conn = get_db_connection()
        try:
            return conn.execute("""
                SELECT a.*, s.name as student_name, s.register_number, s.department, s.phone as student_phone, s.parent_phone
                FROM attendance a
                JOIN students s ON a.student_id = s.id
                WHERE a.attendance_pct < ?
                ORDER BY a.attendance_pct ASC
            """, (threshold,)).fetchall()
        finally:
            conn.close()
