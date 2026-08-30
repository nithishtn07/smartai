"""
CampusGuard AI — Examination & Marks Models
"""

from database.db import get_db_connection


class ExaminationModel:
    @staticmethod
    def get_all():
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM examinations ORDER BY exam_date ASC").fetchall()
        finally:
            conn.close()

    @staticmethod
    def create(exam_type, course_code, course_name, exam_date, exam_time, venue, room_number, seat_number="Allotted"):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO examinations (exam_type, course_code, course_name, exam_date, exam_time, venue, room_number, seat_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (exam_type, course_code, course_name, exam_date, exam_time, venue, room_number, seat_number))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()


class MarksModel:
    @staticmethod
    def get_by_student(student_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM marks WHERE student_id = ?", (student_id,)).fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_by_course(course_code):
        conn = get_db_connection()
        try:
            return conn.execute("""
                SELECT m.*, s.name as student_name, s.register_number 
                FROM marks m
                JOIN students s ON m.student_id = s.id
                WHERE m.course_code = ?
            """, (course_code,)).fetchall()
        finally:
            conn.close()

    @staticmethod
    def upsert_marks(student_id, course_code, course_name, cat1=0, cat2=0, quiz=0, assignment=0, project=0, fat=0, grade="A", grade_points=None, status=None):
        from services.academic_service import calculate_grade_point, sync_student_cgpa
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if grade_points is None:
                grade_points = calculate_grade_point(grade)
            if status is None:
                status = 'FAIL' if str(grade).upper() in ['F', 'FAIL'] else 'PASS'

            existing = cursor.execute("SELECT id FROM marks WHERE student_id = ? AND course_code = ?", (student_id, course_code)).fetchone()
            if existing:
                cursor.execute("""
                    UPDATE marks SET cat1 = ?, cat2 = ?, quiz = ?, assignment = ?, project = ?, fat = ?, grade = ?, grade_points = ?, status = ?
                    WHERE id = ?
                """, (cat1, cat2, quiz, assignment, project, fat, grade, grade_points, status, existing['id']))
            else:
                cursor.execute("""
                    INSERT INTO marks (student_id, course_code, course_name, cat1, cat2, quiz, assignment, project, fat, grade, grade_points, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (student_id, course_code, course_name, cat1, cat2, quiz, assignment, project, fat, grade, grade_points, status))
            
            sync_student_cgpa(conn, student_id)
            conn.commit()
            return True
        finally:
            conn.close()
