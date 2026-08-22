"""
CampusGuard AI — User & Authentication Models
"""

from database.db import get_db_connection
from utils.security import hash_password, verify_password


class StudentModel:
    @staticmethod
    def get_by_id(student_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        finally:
            conn.close()

    @staticmethod
    def get_by_register_number(register_number):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM students WHERE UPPER(register_number) = UPPER(?)", (register_number.strip(),)).fetchone()
        finally:
            conn.close()

    @staticmethod
    def get_all(search_query=None, department=None, limit=100, offset=0):
        conn = get_db_connection()
        try:
            query = "SELECT * FROM students WHERE 1=1"
            params = []
            if search_query:
                query += " AND (name LIKE ? OR register_number LIKE ? OR email LIKE ?)"
                q = f"%{search_query}%"
                params.extend([q, q, q])
            if department and department != 'All':
                query += " AND department = ?"
                params.append(department)
            query += " ORDER BY register_number ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            return conn.execute(query, params).fetchall()
        finally:
            conn.close()

    @staticmethod
    def create(name, register_number, email, password, department, year, program="B.Tech", semester=5, section="A", phone="", parent_name="", parent_phone="", address=""):
        conn = get_db_connection()
        try:
            pw_hash = hash_password(password)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO students (
                    name, register_number, email, password_hash, department, year,
                    program, semester, section, phone, parent_name, parent_phone, address
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, register_number.strip().upper(), email.strip(), pw_hash, department, int(year), program, int(semester), section, phone, parent_name, parent_phone, address))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    @staticmethod
    def update(student_id, **kwargs):
        conn = get_db_connection()
        try:
            fields = []
            params = []
            for key, val in kwargs.items():
                fields.append(f"{key} = ?")
                params.append(val)
            params.append(student_id)
            conn.execute(f"UPDATE students SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()
            return True
        finally:
            conn.close()

    @staticmethod
    def toggle_status(student_id):
        conn = get_db_connection()
        try:
            curr = conn.execute("SELECT status FROM students WHERE id = ?", (student_id,)).fetchone()
            if curr:
                new_status = 'INACTIVE' if curr['status'] == 'ACTIVE' else 'ACTIVE'
                conn.execute("UPDATE students SET status = ? WHERE id = ?", (new_status, student_id))
                conn.commit()
                return new_status
            return None
        finally:
            conn.close()


class ParentModel:
    @staticmethod
    def get_by_id(parent_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM parents WHERE id = ?", (parent_id,)).fetchone()
        finally:
            conn.close()

    @staticmethod
    def get_by_email(email):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM parents WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
        finally:
            conn.close()

    @staticmethod
    def get_all(search_query=None, limit=100, offset=0):
        conn = get_db_connection()
        try:
            query = """
                SELECT p.*, s.name as student_name, s.register_number as student_reg
                FROM parents p
                LEFT JOIN students s ON p.student_id = s.id
                WHERE 1=1
            """
            params = []
            if search_query:
                query += " AND (p.name LIKE ? OR p.email LIKE ? OR p.parent_id LIKE ? OR s.name LIKE ?)"
                q = f"%{search_query}%"
                params.extend([q, q, q, q])
            query += " ORDER BY p.id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            return conn.execute(query, params).fetchall()
        finally:
            conn.close()

    @staticmethod
    def create(parent_id, name, email, phone, password, student_id, relationship="Father", occupation="", address=""):
        conn = get_db_connection()
        try:
            pw_hash = hash_password(password)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO parents (parent_id, name, email, phone, password_hash, relationship, student_id, occupation, address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (parent_id.strip().upper(), name.strip(), email.strip().lower(), phone.strip(), pw_hash, relationship, int(student_id), occupation, address))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    @staticmethod
    def reset_password(parent_id, new_password):
        conn = get_db_connection()
        try:
            pw_hash = hash_password(new_password)
            conn.execute("UPDATE parents SET password_hash = ? WHERE id = ?", (pw_hash, parent_id))
            conn.commit()
            return True
        finally:
            conn.close()


class FacultyModel:
    @staticmethod
    def get_by_id(faculty_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM faculties WHERE id = ?", (faculty_id,)).fetchone()
        finally:
            conn.close()

    @staticmethod
    def get_by_email(email):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM faculties WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
        finally:
            conn.close()

    @staticmethod
    def get_all(department=None):
        conn = get_db_connection()
        try:
            if department and department != 'All':
                return conn.execute("SELECT * FROM faculties WHERE department = ? ORDER BY name ASC", (department,)).fetchall()
            return conn.execute("SELECT * FROM faculties ORDER BY name ASC").fetchall()
        finally:
            conn.close()

    @staticmethod
    def create(faculty_id, name, email, phone, password, department, designation="Assistant Professor", cabin="CS-101"):
        conn = get_db_connection()
        try:
            pw_hash = hash_password(password)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO faculties (faculty_id, name, email, phone, password_hash, department, designation, cabin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (faculty_id.strip().upper(), name.strip(), email.strip().lower(), phone.strip(), pw_hash, department, designation, cabin))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()


class AdminModel:
    @staticmethod
    def get_by_id(admin_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM admins WHERE id = ?", (admin_id,)).fetchone()
        finally:
            conn.close()

    @staticmethod
    def get_by_username(username):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM admins WHERE LOWER(username) = LOWER(?)", (username.strip(),)).fetchone()
        finally:
            conn.close()
