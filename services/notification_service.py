"""
=============================================================================
CampusGuard AI — Central Notification, Messaging & Event Service
=============================================================================
Provides unified multi-portal notification creation, real-time Socket.IO
dispatching, targeted announcement distribution, and audit activity logging.
=============================================================================
"""

import datetime
from database.db import get_db_connection

# Global socketio reference (set from app.py)
socketio_instance = None

def set_socketio(socketio):
    global socketio_instance
    socketio_instance = socketio


def emit_event(event_name, data, room=None):
    """
    Broadcasts a real-time event via Socket.IO if connected.
    """
    if socketio_instance is not None:
        try:
            if room:
                socketio_instance.emit(event_name, data, room=room)
            else:
                socketio_instance.emit(event_name, data)
        except Exception as e:
            print(f"[SocketIO Emit Error] {e}")


def log_activity(user_name, user_role, action, details="", record_id="", ip_address="127.0.0.1", db_conn=None):
    """
    Records an entry in the activity_logs table for audit trail.
    """
    should_close = False
    if db_conn is None:
        db_conn = get_db_connection()
        should_close = True

    try:
        db_conn.execute("""
            INSERT INTO activity_logs (user_name, user_role, action, details, record_id, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_name, user_role, action, details, str(record_id), ip_address))
        db_conn.commit()
    except Exception as e:
        print(f"[ActivityLog Error] {e}")
    finally:
        if should_close:
            db_conn.close()


def create_notification(recipient_id, recipient_role, title, message, category="Academic", 
                        priority="Normal", related_id=None, related_type=None, db_conn=None):
    """
    Inserts a notification record into the central `notifications` table
    and broadcasts a real-time `new_notification` event via Socket.IO if connected.
    """
    should_close = False
    if db_conn is None:
        db_conn = get_db_connection()
        should_close = True

    try:
        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO notifications (
                recipient_id, recipient_role, title, message, category, priority, related_id, related_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (recipient_id, recipient_role.lower(), title, message, category, priority, related_id, related_type))
        db_conn.commit()
        notif_id = cursor.lastrowid

        payload = {
            'id': notif_id,
            'recipient_id': recipient_id,
            'recipient_role': recipient_role.lower(),
            'title': title,
            'message': message,
            'category': category,
            'priority': priority,
            'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'related_id': related_id,
            'related_type': related_type
        }

        # Emit to user personal room and role room
        if socketio_instance is not None:
            user_room = f"user_{recipient_role.lower()}_{recipient_id}"
            role_room = f"role_{recipient_role.lower()}"
            try:
                socketio_instance.emit('new_notification', payload, room=user_room)
                socketio_instance.emit('new_notification', payload, room=role_room)
            except Exception as se:
                print(f"[SocketIO Error] {se}")

        return notif_id
    except Exception as e:
        print(f"[Notification Service Error] {e}")
        return None
    finally:
        if should_close:
            db_conn.close()


def notify_student(student_id, title, message, category="Academic", priority="Normal", 
                   related_id=None, related_type=None, db_conn=None):
    """Convenience helper to notify a student"""
    return create_notification(
        recipient_id=student_id,
        recipient_role="student",
        title=title,
        message=message,
        category=category,
        priority=priority,
        related_id=related_id,
        related_type=related_type,
        db_conn=db_conn
    )


def notify_parent(parent_id_or_student_id, title, message, category="Academic", priority="Normal", 
                  related_id=None, related_type=None, db_conn=None, is_student_id=False):
    """
    Convenience helper to notify a parent.
    If is_student_id=True, resolves the parent ID from student_id.
    """
    should_close = False
    if db_conn is None:
        db_conn = get_db_connection()
        should_close = True

    try:
        parent_id = parent_id_or_student_id
        if is_student_id:
            parent_row = db_conn.execute(
                "SELECT id FROM parents WHERE student_id = ?", 
                (parent_id_or_student_id,)
            ).fetchone()
            if parent_row:
                parent_id = parent_row['id']
            else:
                return None

        return create_notification(
            recipient_id=parent_id,
            recipient_role="parent",
            title=title,
            message=message,
            category=category,
            priority=priority,
            related_id=related_id,
            related_type=related_type,
            db_conn=db_conn
        )
    finally:
        if should_close:
            db_conn.close()


def notify_faculty(faculty_id, title, message, category="Academic", priority="Normal", 
                   related_id=None, related_type=None, db_conn=None):
    """Convenience helper to notify a faculty member"""
    return create_notification(
        recipient_id=faculty_id,
        recipient_role="faculty",
        title=title,
        message=message,
        category=category,
        priority=priority,
        related_id=related_id,
        related_type=related_type,
        db_conn=db_conn
    )


def notify_admin(title, message, category="Safety", priority="Critical", 
                 related_id=None, related_type=None, db_conn=None):
    """
    Convenience helper to notify all campus administrators and security officials.
    """
    should_close = False
    if db_conn is None:
        db_conn = get_db_connection()
        should_close = True

    try:
        admins = db_conn.execute("SELECT id FROM admins").fetchall()
        notif_ids = []
        for adm in admins:
            nid = create_notification(
                recipient_id=adm['id'],
                recipient_role="admin",
                title=title,
                message=message,
                category=category,
                priority=priority,
                related_id=related_id,
                related_type=related_type,
                db_conn=db_conn
            )
            if nid:
                notif_ids.append(nid)
        return notif_ids
    except Exception as e:
        print(f"[Notify Admin Error] {e}")
        return None
    finally:
        if should_close:
            db_conn.close()


def broadcast_announcement(title, description, target_audience="All", category="General", priority="Normal", author_name="Admin", db_conn=None):
    """
    Stores an announcement and fans out notifications to matching audiences
    (All, Students, Parents, Faculty, or Specific Department).
    """
    if db_conn is None:
        return None

    try:
        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO announcements (title, description, category, priority, target_audience, author_name)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, description, category, priority, target_audience, author_name))
        db_conn.commit()
        ann_id = cursor.lastrowid

        aud = (target_audience or "All").strip().lower()

        # Fan-out to Students
        if aud in ['all', 'students', 'students only', 'all students']:
            students = db_conn.execute("SELECT id FROM students").fetchall()
            for s in students:
                notify_student(s['id'], f"📢 {title}", description, category=category, priority=priority, related_id=ann_id, related_type="announcement", db_conn=db_conn)

        # Fan-out to Parents
        if aud in ['all', 'parents', 'parents only', 'all parents']:
            parents = db_conn.execute("SELECT id FROM parents").fetchall()
            for p in parents:
                notify_parent(p['id'], f"📢 {title}", description, category=category, priority=priority, related_id=ann_id, related_type="announcement", db_conn=db_conn)

        # Fan-out to Faculty
        if aud in ['all', 'faculty', 'faculty only', 'all faculty']:
            faculties = db_conn.execute("SELECT id FROM faculties").fetchall()
            for f in faculties:
                notify_faculty(f['id'], f"📢 {title}", description, category=category, priority=priority, related_id=ann_id, related_type="announcement", db_conn=db_conn)

        # Broadcast Socket.IO event to all connected users
        if socketio_instance is not None:
            try:
                socketio_instance.emit('announcement_published', {
                    'id': ann_id,
                    'title': title,
                    'description': description,
                    'category': category,
                    'priority': priority,
                    'target_audience': target_audience,
                    'author_name': author_name,
                    'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }, room='all_users')
            except Exception as se:
                print(f"[SocketIO Announcement Error] {se}")

        return ann_id
    except Exception as e:
        print(f"[Broadcast Announcement Error] {e}")
        return None


def get_system_setting(key_name, default_value="", db_conn=None):
    """
    Retrieves an institutional configuration parameter from system_settings table.
    """
    if db_conn is None:
        return default_value
    try:
        row = db_conn.execute("SELECT value_text FROM system_settings WHERE key_name = ?", (key_name,)).fetchone()
        if row and row['value_text'] is not None:
            return row['value_text']
        return default_value
    except Exception as e:
        print(f"[get_system_setting Error] {e}")
        return default_value


def set_system_setting(key_name, value_text, description="", db_conn=None):
    """
    Updates or inserts an institutional configuration parameter in system_settings table.
    """
    if db_conn is None:
        return False
    try:
        db_conn.execute("""
            INSERT INTO system_settings (key_name, value_text, description, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key_name) DO UPDATE SET
                value_text = excluded.value_text,
                updated_at = CURRENT_TIMESTAMP
        """, (key_name, str(value_text), description))
        db_conn.commit()
        return True
    except Exception as e:
        print(f"[set_system_setting Error] {e}")
        return False

