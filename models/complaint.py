"""
CampusGuard AI — Complaint & Grievance Models
"""

import uuid
from database.db import get_db_connection


class ComplaintModel:
    @staticmethod
    def get_by_student(student_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM complaints WHERE student_id = ? ORDER BY id DESC", (student_id,)).fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_all_with_students(status=None):
        conn = get_db_connection()
        try:
            query = """
                SELECT c.*, s.name as student_name, s.register_number, s.department
                FROM complaints c
                JOIN students s ON c.student_id = s.id
                WHERE 1=1
            """
            params = []
            if status and status != 'All':
                query += " AND c.status = ?"
                params.append(status)
            query += " ORDER BY c.id DESC"
            return conn.execute(query, params).fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_by_complaint_id(complaint_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM complaints WHERE complaint_id = ?", (complaint_id,)).fetchone()
        finally:
            conn.close()

    @staticmethod
    def create(student_id, category, title, description, location, priority="Normal", ai_data=None):
        conn = get_db_connection()
        try:
            cid = f"CMP-{uuid.uuid4().hex[:6].upper()}"
            ai_data = ai_data or {}
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO complaints (
                    complaint_id, student_id, category, title, description, location, priority,
                    status, ai_category, ai_severity, ai_priority, ai_dept, ai_action
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Submitted', ?, ?, ?, ?, ?)
            """, (
                cid, int(student_id), category, title, description, location, priority,
                ai_data.get('category', category),
                ai_data.get('severity', 'Moderate'),
                ai_data.get('priority', priority),
                ai_data.get('assigned_dept', 'Student Welfare Cell'),
                ai_data.get('recommended_action', 'Review grievance and assign to supervisor.')
            ))
            conn.commit()
            return cid
        finally:
            conn.close()

    @staticmethod
    def update_status(complaint_id, status, assigned_dept=None):
        conn = get_db_connection()
        try:
            if assigned_dept:
                conn.execute("UPDATE complaints SET status = ?, ai_dept = ? WHERE complaint_id = ?", (status, assigned_dept, complaint_id))
            else:
                conn.execute("UPDATE complaints SET status = ? WHERE complaint_id = ?", (status, complaint_id))
            conn.commit()
            return True
        finally:
            conn.close()
