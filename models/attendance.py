"""
CampusGuard AI — Attendance Models & Single Source of Truth Calculations
All aggregate calculations strictly derive from attendance_logs.
"""

import datetime
from database.db import get_db_connection


class AttendanceModel:

    @staticmethod
    def recalculate_aggregate(conn, student_id, course_code, course_name=None):
        """
        Recalculates aggregate metrics for (student_id, course_code) strictly from attendance_logs.
        """
        if not course_name:
            course = conn.execute("SELECT course_name FROM courses WHERE course_code = ?", (course_code,)).fetchone()
            course_name = course['course_name'] if course else course_code

        stats = conn.execute("""
            SELECT 
                COUNT(*) as total_held,
                SUM(CASE WHEN LOWER(status) = 'present' THEN 1 ELSE 0 END) as total_attended,
                SUM(CASE WHEN LOWER(status) = 'absent' THEN 1 ELSE 0 END) as total_missed
            FROM attendance_logs
            WHERE student_id = ? AND course_code = ?
        """, (student_id, course_code)).fetchone()

        total_held = stats['total_held'] or 0
        total_attended = stats['total_attended'] or 0
        total_missed = stats['total_missed'] or 0
        pct = round((total_attended / total_held) * 100.0, 1) if total_held > 0 else 0.0

        existing = conn.execute("""
            SELECT id FROM attendance WHERE student_id = ? AND subject_code = ?
        """, (student_id, course_code)).fetchone()

        if total_held == 0:
            if existing:
                conn.execute("DELETE FROM attendance WHERE id = ?", (existing['id'],))
        else:
            if existing:
                conn.execute("""
                    UPDATE attendance 
                    SET classes_held = ?, classes_attended = ?, classes_missed = ?, attendance_pct = ?
                    WHERE id = ?
                """, (total_held, total_attended, total_missed, pct, existing['id']))
            else:
                conn.execute("""
                    INSERT INTO attendance (student_id, subject_code, subject_name, classes_held, classes_attended, classes_missed, attendance_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (student_id, course_code, course_name, total_held, total_attended, total_missed, pct))

        return total_held, total_attended, total_missed, pct

    @staticmethod
    def record_student_attendance(conn, student_id, course_code, course_name, date_val, status, topic="", faculty_id=1):
        """
        Upserts a single attendance log record and recalculates aggregate attendance.
        Prevents duplicates by updating if record already exists for the same date.
        """
        existing_log = conn.execute("""
            SELECT id FROM attendance_logs 
            WHERE student_id = ? AND course_code = ? AND date = ?
        """, (student_id, course_code, date_val)).fetchone()

        if existing_log:
            conn.execute("""
                UPDATE attendance_logs 
                SET status = ?, topic = ?
                WHERE id = ?
            """, (status, topic, existing_log['id']))
        else:
            conn.execute("""
                INSERT INTO attendance_logs (student_id, course_code, course_name, date, status, topic)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (student_id, course_code, course_name, date_val, status, topic))

        return AttendanceModel.recalculate_aggregate(conn, student_id, course_code, course_name)

    @staticmethod
    def record_batch_attendance(conn, student_statuses, course_code, course_name, date_val, topic="", faculty_id=1):
        """
        Records attendance for multiple students in a single atomic transaction.
        student_statuses is a dict of {student_id: status_string}
        """
        present_count = 0
        absent_count = 0
        results = {}

        for stu_id, status in student_statuses.items():
            is_present = (status.lower() == 'present')
            if is_present:
                present_count += 1
            else:
                absent_count += 1

            held, att, miss, pct = AttendanceModel.record_student_attendance(
                conn, stu_id, course_code, course_name, date_val, status, topic, faculty_id
            )
            results[stu_id] = {'held': held, 'attended': att, 'missed': miss, 'pct': pct}

        return present_count, absent_count, results

    @staticmethod
    def get_by_student(student_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM attendance WHERE student_id = ? ORDER BY subject_code ASC", (student_id,)).fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_logs_by_student(student_id, limit=30):
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
    def get_low_attendance_students(threshold=75.0):
        conn = get_db_connection()
        try:
            return conn.execute("""
                SELECT a.*, s.name as student_name, s.register_number, s.department, s.phone as student_phone, s.parent_phone
                FROM attendance a
                JOIN students s ON a.student_id = s.id
                WHERE a.attendance_pct < ? AND a.classes_held > 0
                ORDER BY a.attendance_pct ASC
            """, (threshold,)).fetchall()
        finally:
            conn.close()
