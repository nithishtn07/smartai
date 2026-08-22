"""
CampusGuard AI — Academic Catalog & Timetable Models
"""

from database.db import get_db_connection


class CourseModel:
    @staticmethod
    def get_all(department=None, semester=None):
        conn = get_db_connection()
        try:
            query = "SELECT * FROM courses WHERE 1=1"
            params = []
            if department and department != 'All':
                query += " AND department = ?"
                params.append(department)
            if semester:
                query += " AND semester = ?"
                params.append(int(semester))
            query += " ORDER BY course_code ASC"
            return conn.execute(query, params).fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_by_code(course_code):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM courses WHERE course_code = ?", (course_code,)).fetchone()
        finally:
            conn.close()

    @staticmethod
    def create(course_code, course_name, department, semester, credits, faculty_name, course_type="Core Theory", room_number="CS-201", timing=""):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO courses (course_code, course_name, department, semester, credits, faculty_name, course_type, room_number, timing)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (course_code.strip().upper(), course_name.strip(), department, int(semester), int(credits), faculty_name, course_type, room_number, timing))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()


class TimetableModel:
    @staticmethod
    def get_for_student(department, year, day=None):
        conn = get_db_connection()
        try:
            if day:
                return conn.execute("""
                    SELECT * FROM timetable 
                    WHERE department = ? AND year = ? AND day_of_week = ?
                    ORDER BY start_time ASC
                """, (department, year, day)).fetchall()
            return conn.execute("""
                SELECT * FROM timetable 
                WHERE department = ? AND year = ?
                ORDER BY CASE 
                    WHEN day_of_week = 'Monday' THEN 1
                    WHEN day_of_week = 'Tuesday' THEN 2
                    WHEN day_of_week = 'Wednesday' THEN 3
                    WHEN day_of_week = 'Thursday' THEN 4
                    WHEN day_of_week = 'Friday' THEN 5
                    WHEN day_of_week = 'Saturday' THEN 6
                    ELSE 7 END, start_time ASC
            """, (department, year)).fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_for_faculty(faculty_name):
        conn = get_db_connection()
        try:
            return conn.execute("""
                SELECT * FROM timetable 
                WHERE faculty_name LIKE ?
                ORDER BY CASE 
                    WHEN day_of_week = 'Monday' THEN 1
                    WHEN day_of_week = 'Tuesday' THEN 2
                    WHEN day_of_week = 'Wednesday' THEN 3
                    WHEN day_of_week = 'Thursday' THEN 4
                    WHEN day_of_week = 'Friday' THEN 5
                    WHEN day_of_week = 'Saturday' THEN 6
                    ELSE 7 END, start_time ASC
            """, (f"%{faculty_name}%",)).fetchall()
        finally:
            conn.close()


class StudyMaterialModel:
    @staticmethod
    def get_by_course(course_code=None):
        conn = get_db_connection()
        try:
            if course_code:
                return conn.execute("SELECT * FROM study_materials WHERE course_code = ? ORDER BY id DESC", (course_code,)).fetchall()
            return conn.execute("SELECT * FROM study_materials ORDER BY id DESC").fetchall()
        finally:
            conn.close()
