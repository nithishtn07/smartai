"""
CampusGuard AI — Audit & Activity Logger
"""

from database.db import get_db_connection


def log_activity(user_name: str, user_role: str, action: str, details: str = "", record_id: str = "", ip_address: str = "127.0.0.1"):
    """
    Records an immutable audit trail entry in the database.
    """
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO activity_logs (user_name, user_role, action, details, record_id, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_name, user_role, action, details, str(record_id), ip_address or '127.0.0.1'))
        conn.commit()
    except Exception as e:
        print(f"[AuditLog] Failed to record activity log: {e}")
    finally:
        conn.close()
