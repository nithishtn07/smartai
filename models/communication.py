"""
CampusGuard AI — Communication, Announcements & Notifications Models
"""

from database.db import get_db_connection


class AnnouncementModel:
    @staticmethod
    def get_all(target_audience=None):
        conn = get_db_connection()
        try:
            if target_audience and target_audience != 'All':
                return conn.execute("""
                    SELECT * FROM announcements 
                    WHERE target_audience = ? OR target_audience = 'All' 
                    ORDER BY id DESC
                """, (target_audience,)).fetchall()
            return conn.execute("SELECT * FROM announcements ORDER BY id DESC").fetchall()
        finally:
            conn.close()

    @staticmethod
    def create(title, description, category="General", priority="Normal", target_audience="All", author_name="Admin"):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO announcements (title, description, category, priority, target_audience, author_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, description, category, priority, target_audience, author_name))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()


class MessageModel:
    @staticmethod
    def get_for_student(student_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM messages WHERE student_id = ? ORDER BY id DESC", (student_id,)).fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_for_parent(parent_id):
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM parent_messages WHERE parent_id = ? ORDER BY id DESC", (parent_id,)).fetchall()
        finally:
            conn.close()

    @staticmethod
    def send(student_id, sender_name, receiver_name, subject, content, sender_role="Student", sender_id=1, receiver_role="Faculty", receiver_id=1):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (student_id, sender_name, receiver_name, subject, content, sender_role, sender_id, receiver_role, receiver_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (student_id, sender_name, receiver_name, subject, content, sender_role, sender_id, receiver_role, receiver_id))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()


class NotificationModel:
    @staticmethod
    def get_by_recipient(role, recipient_id, unread_only=False, limit=20):
        conn = get_db_connection()
        try:
            query = "SELECT * FROM notifications WHERE recipient_role = ? AND recipient_id = ?"
            params = [role, recipient_id]
            if unread_only:
                query += " AND is_read = 0"
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            return conn.execute(query, params).fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_unread_count(role, recipient_id):
        conn = get_db_connection()
        try:
            row = conn.execute("""
                SELECT COUNT(*) as cnt FROM notifications 
                WHERE recipient_role = ? AND recipient_id = ? AND is_read = 0
            """, (role, recipient_id)).fetchone()
            return row['cnt'] if row else 0
        finally:
            conn.close()

    @staticmethod
    def mark_as_read(notif_id):
        conn = get_db_connection()
        try:
            conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    @staticmethod
    def mark_all_as_read(role, recipient_id):
        conn = get_db_connection()
        try:
            conn.execute("UPDATE notifications SET is_read = 1 WHERE recipient_role = ? AND recipient_id = ?", (role, recipient_id))
            conn.commit()
            return True
        finally:
            conn.close()


class AlertModel:
    @staticmethod
    def get_all():
        conn = get_db_connection()
        try:
            return conn.execute("SELECT * FROM alerts ORDER BY id DESC").fetchall()
        finally:
            conn.close()
