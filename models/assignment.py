"""
CampusGuard AI — Assignment & Submission Models
"""

from database.db import get_db_connection


class AssignmentModel:
    @staticmethod
    def get_all(course_code=None):
        conn = get_db_connection()
        try:
            if course_code:
                return conn.execute("SELECT * FROM assignments WHERE course_code = ? ORDER BY id DESC", (course_code,)).fetchall()
            return conn.execute("SELECT * FROM assignments ORDER BY id DESC").fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_by_id(assignment_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
        finally:
            conn.close()

    @staticmethod
    def create(course_code, title, description, faculty_name, due_date, max_marks=50):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO assignments (course_code, title, description, faculty_name, due_date, max_marks, status)
                VALUES (?, ?, ?, ?, ?, ?, 'Pending')
            """, (course_code, title, description, faculty_name, due_date, max_marks))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    @staticmethod
    def evaluate(assignment_id, marks_obtained, feedback=""):
        conn = get_db_connection()
        try:
            conn.execute("""
                UPDATE assignments SET marks_obtained = ?, feedback = ?, status = 'Evaluated'
                WHERE id = ?
            """, (marks_obtained, feedback, assignment_id))
            conn.commit()
            return True
        finally:
            conn.close()

    @staticmethod
    def delete(assignment_id):
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
            conn.commit()
            return True
        finally:
            conn.close()
