"""
CampusGuard AI — Safety, Incident & SOS Models
"""

import uuid
from database.db import get_db_connection


class IncidentModel:
    @staticmethod
    def get_all(status=None):
        conn = get_db_connection()
        try:
            query = """
                SELECT i.*, s.name as student_name, s.register_number, s.phone as student_phone
                FROM incidents i
                LEFT JOIN students s ON i.student_id = s.id
                WHERE 1=1
            """
            params = []
            if status and status != 'All':
                query += " AND i.status = ?"
                params.append(status)
            query += " ORDER BY i.created_at DESC"
            return conn.execute(query, params).fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_by_incident_id(incident_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)).fetchone()
        finally:
            conn.close()

    @staticmethod
    def create_sos(student_id, location="Main Campus Quad", latitude=12.9716, longitude=77.5946, description="Emergency SOS Beacon Triggered", priority_score=95):
        conn = get_db_connection()
        try:
            inc_id = f"SOS-{uuid.uuid4().hex[:6].upper()}"
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO incidents (
                    incident_id, student_id, incident_type, location, latitude, longitude,
                    description, status, assigned_to, priority_score
                ) VALUES (?, ?, 'EMERGENCY_SOS', ?, ?, ?, ?, 'ACTIVE', 'Campus QRT Unit 1', ?)
            """, (inc_id, int(student_id), location, float(latitude) if latitude else None, float(longitude) if longitude else None, description, int(priority_score)))
            conn.commit()
            return inc_id
        finally:
            conn.close()

    @staticmethod
    def update_status(incident_id, status, assigned_to=None):
        conn = get_db_connection()
        try:
            if assigned_to:
                conn.execute("UPDATE incidents SET status = ?, assigned_to = ? WHERE incident_id = ?", (status, assigned_to, incident_id))
            else:
                conn.execute("UPDATE incidents SET status = ? WHERE incident_id = ?", (status, incident_id))
            conn.commit()
            return True
        finally:
            conn.close()


class EmergencyContactModel:
    @staticmethod
    def get_all():
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM emergency_contacts ORDER BY id ASC").fetchall()
        finally:
            conn.close()


class SafeWalkModel:
    @staticmethod
    def get_active_by_student(student_id):
        conn = get_db_connection()
        try:
            return conn.execute("""
                SELECT * FROM safe_walk_sessions 
                WHERE student_id = ? AND status = 'IN_PROGRESS' 
                ORDER BY id DESC LIMIT 1
            """, (student_id,)).fetchone()
        finally:
            conn.close()
