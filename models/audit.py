"""
CampusGuard AI — Audit Logs & Institutional Settings Models
"""

from database.db import get_db_connection


class AuditLogModel:
    @staticmethod
    def get_recent(limit=50):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM activity_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        finally:
            conn.close()


class SystemSettingModel:
    @staticmethod
    def get(key_name, default=None):
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT value_text FROM system_settings WHERE key_name = ?", (key_name,)).fetchone()
            return row['value_text'] if row else default
        finally:
            conn.close()

    @staticmethod
    def set(key_name, value_text, description=""):
        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO system_settings (key_name, value_text, description)
                VALUES (?, ?, ?)
                ON CONFLICT(key_name) DO UPDATE SET value_text = excluded.value_text, updated_at = CURRENT_TIMESTAMP
            """, (key_name, str(value_text), description))
            conn.commit()
            return True
        finally:
            conn.close()

    @staticmethod
    def get_all():
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM system_settings ORDER BY key_name ASC").fetchall()
        finally:
            conn.close()
