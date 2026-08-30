"""
=============================================================================
CampusGuard AI — Smart, Automated & Role-Based Notification Platform
=============================================================================
Provides unified multi-portal smart notification creation, event-driven
triggers (Attendance, Marks, CGPA, Fees, Timetable, Announcements), real-time
Socket.IO dispatching, duplicate prevention, and contextual action routing.
=============================================================================
"""

import os
import datetime
from database.db import get_db_connection

# Global socketio reference (set from app.py)
socketio_instance = None


def set_socketio(socketio):
    global socketio_instance
    socketio_instance = socketio


def ensure_notifications_schema(db_conn=None):
    """
    Ensures that the notifications table contains all required columns (e.g. action_url).
    """
    should_close = False
    if db_conn is None:
        db_conn = get_db_connection()
        should_close = True

    try:
        cursor = db_conn.cursor()
        cursor.execute("PRAGMA table_info(notifications)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'action_url' not in cols:
            try:
                cursor.execute("ALTER TABLE notifications ADD COLUMN action_url TEXT")
                db_conn.commit()
            except Exception:
                pass
    except Exception as e:
        print(f"[Notifications Schema Check] {e}")
    finally:
        if should_close:
            db_conn.close()


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


def is_duplicate_notification(recipient_id, recipient_role, title, category, hours_window=12, db_conn=None):
    """
    Duplicate Prevention:
    Checks if an identical or matching unread notification was already dispatched recently.
    """
    if db_conn is None:
        return False
    try:
        # Check if identical unread notification exists
        existing_unread = db_conn.execute("""
            SELECT id FROM notifications 
            WHERE recipient_id = ? AND recipient_role = ? AND title = ? AND category = ? AND is_read = 0
            LIMIT 1
        """, (recipient_id, recipient_role.lower(), title, category)).fetchone()
        if existing_unread:
            return True

        # Check if identical notification was created within hours_window
        time_cutoff = (datetime.datetime.now() - datetime.timedelta(hours=hours_window)).strftime('%Y-%m-%d %H:%M:%S')
        recent = db_conn.execute("""
            SELECT id FROM notifications
            WHERE recipient_id = ? AND recipient_role = ? AND title = ? AND category = ? AND created_at >= ?
            LIMIT 1
        """, (recipient_id, recipient_role.lower(), title, category, time_cutoff)).fetchone()
        if recent:
            return True

        return False
    except Exception:
        return False


def create_notification(recipient_id, recipient_role, title, message, category="Academic", 
                        priority="Normal", related_id=None, related_type=None, action_url=None, 
                        db_conn=None, allow_duplicate=False):
    """
    Inserts a notification record into the central `notifications` table
    with priority, category, action_url, and broadcasts real-time Socket.IO events.
    """
    should_close = False
    if db_conn is None:
        db_conn = get_db_connection()
        should_close = True

    try:
        ensure_notifications_schema(db_conn)

        # Normalize priority: Critical, High, Normal, Informational
        p_map = {'critical': 'Critical', 'high': 'High', 'normal': 'Normal', 'informational': 'Informational', 'info': 'Informational'}
        norm_priority = p_map.get(str(priority).lower(), 'Normal')

        # Normalize category: Academic, Attendance, Fees, Timetable, Announcements, System, Safety, Leave, Message
        c_map = {
            'academic': 'Academic', 'academics': 'Academic', 'attendance': 'Attendance',
            'fees': 'Fees', 'fee': 'Fees', 'finance': 'Fees', 'timetable': 'Timetable',
            'announcement': 'Announcements', 'announcements': 'Announcements',
            'leave': 'Leave', 'message': 'Message',
            'system': 'System', 'safety': 'Safety', 'emergency': 'Safety'
        }
        norm_category = c_map.get(str(category).lower(), category)

        # Default action_url based on role & category if not explicitly provided
        if not action_url:
            r = recipient_role.lower()
            if r == 'student':
                if norm_category == 'Attendance': action_url = '/student/attendance'
                elif norm_category == 'Academic': action_url = '/student/marks'
                elif norm_category == 'Fees': action_url = '/student/fees'
                elif norm_category == 'Timetable': action_url = '/student/timetable'
                elif norm_category in ['Announcements', 'System']: action_url = '/student/alerts'
            elif r == 'parent':
                if norm_category == 'Attendance': action_url = '/parent/attendance'
                elif norm_category == 'Academic': action_url = '/parent/academics'
                elif norm_category == 'Fees': action_url = '/parent/fees'
                elif norm_category == 'Timetable': action_url = '/parent/timetable'
                elif norm_category in ['Announcements', 'System']: action_url = '/parent/notifications'
            elif r == 'faculty':
                if norm_category == 'Attendance': action_url = '/faculty/attendance'
                elif norm_category == 'Academic': action_url = '/faculty/marks'
                elif norm_category == 'Timetable': action_url = '/faculty/timetable'
                elif norm_category in ['Announcements', 'System']: action_url = '/faculty/notifications'
            elif r == 'admin':
                if norm_category == 'Fees': action_url = '/admin/fees'
                elif norm_category == 'Attendance': action_url = '/admin/attendance'
                elif norm_category in ['Announcements', 'System']: action_url = '/admin/announcements'

        # Duplicate Prevention check
        if not allow_duplicate and is_duplicate_notification(recipient_id, recipient_role, title, norm_category, db_conn=db_conn):
            # Return existing notification ID
            row = db_conn.execute("""
                SELECT id FROM notifications 
                WHERE recipient_id = ? AND recipient_role = ? AND title = ? AND category = ?
                ORDER BY id DESC LIMIT 1
            """, (recipient_id, recipient_role.lower(), title, norm_category)).fetchone()
            return row['id'] if row else None

        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO notifications (
                recipient_id, recipient_role, title, message, category, priority, related_id, related_type, action_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (recipient_id, recipient_role.lower(), title, message, norm_category, norm_priority, related_id, related_type, action_url))
        db_conn.commit()
        notif_id = cursor.lastrowid

        payload = {
            'id': notif_id,
            'recipient_id': recipient_id,
            'recipient_role': recipient_role.lower(),
            'title': title,
            'message': message,
            'category': norm_category,
            'priority': norm_priority,
            'action_url': action_url,
            'is_read': 0,
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


# -----------------------------------------------------------------------------
# Convenience Role-Based Helpers
# -----------------------------------------------------------------------------

def notify_student(student_id, title, message, category="Academic", priority="Normal", 
                   related_id=None, related_type=None, action_url=None, db_conn=None, allow_duplicate=False):
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
        action_url=action_url,
        db_conn=db_conn,
        allow_duplicate=allow_duplicate
    )


def notify_parent(parent_id_or_student_id, title, message, category="Academic", priority="Normal", 
                  related_id=None, related_type=None, action_url=None, db_conn=None, is_student_id=False, allow_duplicate=False):
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
            action_url=action_url,
            db_conn=db_conn,
            allow_duplicate=allow_duplicate
        )
    finally:
        if should_close:
            db_conn.close()


def notify_faculty(faculty_id, title, message, category="Academic", priority="Normal", 
                   related_id=None, related_type=None, action_url=None, db_conn=None, allow_duplicate=False):
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
        action_url=action_url,
        db_conn=db_conn,
        allow_duplicate=allow_duplicate
    )


def notify_admin(title, message, category="System", priority="Critical", 
                 related_id=None, related_type=None, action_url=None, db_conn=None, allow_duplicate=False):
    """
    Convenience helper to notify all campus administrators.
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
                action_url=action_url,
                db_conn=db_conn,
                allow_duplicate=allow_duplicate
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


# -----------------------------------------------------------------------------
# Smart Event Triggers
# -----------------------------------------------------------------------------

def generate_smart_attendance_notification(student_id, course_code, course_name, current_pct, prev_pct=None, db_conn=None):
    """
    Smart Attendance Notification Trigger:
    Evaluates verified database attendance against institutional thresholds:
    - 85%+ -> Normal
    - 80-84.9% -> Informational
    - 75-79.9% -> High Warning
    - Below 75% -> Critical Alert
    - Improved -> Attendance Improved notification
    Dispatches to Student and linked Parent.
    """
    should_close = False
    if db_conn is None:
        db_conn = get_db_connection()
        should_close = True

    try:
        student = db_conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if not student:
            return None

        pct = round(float(current_pct), 1)
        student_name = student['name']

        # Determine Priority & Message
        if prev_pct is not None and prev_pct < 75.0 and pct >= 75.0:
            # Improvement across threshold
            s_title = f"🟢 Attendance Improved: {course_code}"
            s_msg = f"Your {course_name} ({course_code}) attendance has improved to {pct}%, reaching safe standing."
            priority = "Normal"
            p_title = f"🟢 Attendance Improved: {student_name}"
            p_msg = f"{student_name}'s {course_name} ({course_code}) attendance has improved to {pct}%, reaching safe standing."
        elif pct < 75.0:
            s_title = f"🔴 Low Attendance Alert: {course_code} ({pct}%)"
            s_msg = f"Your {course_name} ({course_code}) attendance is {pct}%, which is below the required 75% threshold."
            priority = "Critical"
            p_title = f"⚠️ Low Attendance Alert: {student_name} ({pct}%)"
            p_msg = f"{student_name}'s {course_name} ({course_code}) attendance is currently {pct}%, below the required 75% threshold."
        elif pct < 80.0:
            s_title = f"🟠 Low Attendance Warning: {course_code} ({pct}%)"
            s_msg = f"Your {course_name} ({course_code}) attendance is {pct}%. You are approaching the minimum required 75% attendance threshold."
            priority = "High"
            p_title = f"🟠 Low Attendance Warning: {student_name} ({pct}%)"
            p_msg = f"{student_name}'s {course_name} ({course_code}) attendance is {pct}%, approaching the 75% threshold."
        elif pct < 85.0:
            s_title = f"⚪ Attendance Update: {course_code} ({pct}%)"
            s_msg = f"Your {course_name} ({course_code}) attendance is recorded at {pct}%."
            priority = "Informational"
            p_title = f"⚪ Attendance Update: {student_name}"
            p_msg = f"{student_name}'s {course_name} ({course_code}) attendance is recorded at {pct}%."
        else:
            s_title = f"🔵 Attendance Logged: {course_code} ({pct}%)"
            s_msg = f"Your attendance for {course_name} is in good standing at {pct}%."
            priority = "Normal"
            p_title = None
            p_msg = None

        # Student Notification
        notify_student(
            student_id=student_id,
            title=s_title,
            message=s_msg,
            category='Attendance',
            priority=priority,
            action_url='/student/attendance',
            db_conn=db_conn
        )

        # Parent Notification (for warnings, alerts, and threshold improvements)
        if p_title and p_msg:
            parent = db_conn.execute("SELECT id FROM parents WHERE student_id = ?", (student_id,)).fetchone()
            if parent:
                notify_parent(
                    parent_id_or_student_id=parent['id'],
                    title=p_title,
                    message=p_msg,
                    category='Attendance',
                    priority=priority,
                    action_url='/parent/attendance',
                    db_conn=db_conn
                )

        return True
    except Exception as e:
        print(f"[Smart Attendance Notification Error] {e}")
        return False
    finally:
        if should_close:
            db_conn.close()


def generate_smart_marks_notification(student_id, course_code, course_name, assessment_type="Continuous Assessment",
                                      marks_obtained=None, max_marks=100, grade=None, db_conn=None):
    """
    Smart Marks Notification Trigger:
    When faculty enters or updates marks, dispatches notifications to Student and linked Parent.
    """
    should_close = False
    if db_conn is None:
        db_conn = get_db_connection()
        should_close = True

    try:
        student = db_conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if not student:
            return None

        student_name = student['name']
        grade_str = f", Grade: {grade}" if grade else ""
        marks_str = f" ({marks_obtained}/{max_marks})" if marks_obtained is not None else ""

        # Student Notification
        notify_student(
            student_id=student_id,
            title=f"📊 Marks Updated: {course_code}",
            message=f"Your {assessment_type} marks for {course_name} ({course_code}) have been updated{marks_str}{grade_str}.",
            category='Academic',
            priority='Normal',
            action_url='/student/marks',
            db_conn=db_conn,
            allow_duplicate=True
        )

        # Parent Notification
        parent = db_conn.execute("SELECT id FROM parents WHERE student_id = ?", (student_id,)).fetchone()
        if parent:
            notify_parent(
                parent_id_or_student_id=parent['id'],
                title=f"📊 Academic Update: {student_name}",
                message=f"{student_name}'s {assessment_type} marks for {course_name} ({course_code}) have been published{marks_str}{grade_str}.",
                category='Academic',
                priority='Normal',
                action_url='/parent/academics',
                db_conn=db_conn,
                allow_duplicate=True
            )

        return True
    except Exception as e:
        print(f"[Smart Marks Notification Error] {e}")
        return False
    finally:
        if should_close:
            db_conn.close()


def generate_smart_cgpa_notification(student_id, new_cgpa, prev_cgpa=None, db_conn=None):
    """
    Smart CGPA Recalculation Notification Trigger:
    When marks/grades trigger CGPA recalculation, notifies student and parent.
    """
    should_close = False
    if db_conn is None:
        db_conn = get_db_connection()
        should_close = True

    try:
        student = db_conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if not student:
            return None

        student_name = student['name']
        cgpa_val = round(float(new_cgpa), 2)
        if prev_cgpa is not None and round(float(prev_cgpa), 2) == cgpa_val:
            return None
        prev_str = f" (Previous: {round(float(prev_cgpa), 2)})" if (prev_cgpa is not None and prev_cgpa > 0) else ""

        # Student Notification
        notify_student(
            student_id=student_id,
            title="📈 Academic Update: CGPA Recalculated",
            message=f"Your academic record has been updated and your cumulative CGPA is {cgpa_val} / 10.0{prev_str}.",
            category='Academic',
            priority='Normal',
            action_url='/student/marks',
            db_conn=db_conn
        )

        # Parent Notification
        parent = db_conn.execute("SELECT id FROM parents WHERE student_id = ?", (student_id,)).fetchone()
        if parent:
            notify_parent(
                parent_id_or_student_id=parent['id'],
                title=f"📈 Academic Update: {student_name}'s CGPA",
                message=f"{student_name}'s academic record has been updated with a recalculated CGPA of {cgpa_val} / 10.0{prev_str}.",
                category='Academic',
                priority='Normal',
                action_url='/parent/academics',
                db_conn=db_conn
            )

        return True
    except Exception as e:
        print(f"[Smart CGPA Notification Error] {e}")
        return False
    finally:
        if should_close:
            db_conn.close()


def generate_smart_payment_notification(parent_id, student_id, amount, fee_type, receipt_no, txn_id=None, is_demo=True, db_conn=None):
    """
    Smart Payment Settlement Notification Trigger:
    Dispatches verified payment confirmations across Parent, Student, and Admin portals.
    """
    should_close = False
    if db_conn is None:
        db_conn = get_db_connection()
        should_close = True

    try:
        student = db_conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        parent = db_conn.execute("SELECT * FROM parents WHERE id = ?", (parent_id,)).fetchone()

        student_name = student['name'] if student else f"Student #{student_id}"
        parent_name = parent['name'] if parent else "Parent/Guardian"
        amt_str = f"{float(amount):,.2f}"
        demo_tag = " (Demo Payment)" if is_demo else ""

        # 1. Parent Notification
        notify_parent(
            parent_id_or_student_id=parent_id,
            title=f"✅ Payment Successful: #{receipt_no}",
            message=f"Your payment{demo_tag} of ₹{amt_str} for {fee_type} was recorded successfully. Official Receipt: #{receipt_no}.",
            category='Fees',
            priority='Informational',
            action_url=f"/parent/fees/receipt/{receipt_no}",
            db_conn=db_conn,
            allow_duplicate=True
        )

        # 2. Student Notification
        notify_student(
            student_id=student_id,
            title=f"💳 Fee Payment Recorded: ₹{amt_str}",
            message=f"A fee payment{demo_tag} of ₹{amt_str} for {fee_type} was recorded on your account. Receipt: #{receipt_no}.",
            category='Fees',
            priority='Informational',
            action_url='/student/fees',
            db_conn=db_conn,
            allow_duplicate=True
        )

        # 3. Admin Notification
        notify_admin(
            title=f"💰 Fee Collection: ₹{amt_str}",
            message=f"Payment{demo_tag} of ₹{amt_str} received from {parent_name} for student {student_name} ({fee_type}). Receipt: #{receipt_no}.",
            category='Fees',
            priority='Informational',
            action_url='/admin/fees',
            db_conn=db_conn,
            allow_duplicate=True
        )

        return True
    except Exception as e:
        print(f"[Smart Payment Notification Error] {e}")
        return False
    finally:
        if should_close:
            db_conn.close()


def generate_smart_timetable_notification(department, year, course_code, day_of_week, start_time, room_no="TBD", change_type="Updated", db_conn=None):
    """
    Smart Timetable Change Notification Trigger:
    Notifies all affected students in the specified department and academic year.
    """
    should_close = False
    if db_conn is None:
        db_conn = get_db_connection()
        should_close = True

    try:
        students = db_conn.execute("""
            SELECT id, name FROM students 
            WHERE department = ? AND year = ? AND status != 'DELETED'
        """, (department, year)).fetchall()

        priority = "High" if change_type.lower() in ['rescheduled', 'cancelled', 'room change'] else "Normal"
        title = f"📅 Timetable {change_type}: {course_code}"
        message = f"Schedule for {course_code} on {day_of_week} has been {change_type.lower()} ({start_time}, Room: {room_no})."

        for s in students:
            notify_student(
                student_id=s['id'],
                title=title,
                message=message,
                category='Timetable',
                priority=priority,
                action_url='/student/timetable',
                db_conn=db_conn
            )

        return len(students)
    except Exception as e:
        print(f"[Smart Timetable Notification Error] {e}")
        return 0
    finally:
        if should_close:
            db_conn.close()


def broadcast_announcement(title, description, target_audience="All", category="General", priority="Normal", author_name="Admin", db_conn=None):
    """
    Stores an announcement and fans out notifications to matching targeted audiences
    (All, Students, Parents, Faculty, or Specific Target).
    """
    should_close = False
    if db_conn is None:
        db_conn = get_db_connection()
        should_close = True

    try:
        ann_row = db_conn.execute("SELECT id FROM announcements WHERE title = ? AND description = ? ORDER BY id DESC LIMIT 1", (title, description)).fetchone()
        if ann_row:
            ann_id = ann_row['id']
        else:
            cursor = db_conn.cursor()
            cursor.execute("""
                INSERT INTO announcements (title, description, category, priority, target_audience, author_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, description, category, priority, target_audience, author_name))
            db_conn.commit()
            ann_id = cursor.lastrowid

        aud = (target_audience or "All").strip().lower()

        # Batch fan-out to Students
        if aud in ['all', 'students', 'students only', 'all students']:
            db_conn.execute("""
                INSERT INTO notifications (recipient_id, recipient_role, title, message, category, priority, related_id, related_type, action_url)
                SELECT id, 'student', ?, ?, ?, ?, ?, 'announcement', '/student/alerts' FROM students WHERE status != 'DELETED'
            """, (f"📢 {title}", description, category, priority, ann_id))

        # Batch fan-out to Parents
        if aud in ['all', 'parents', 'parents only', 'all parents']:
            db_conn.execute("""
                INSERT INTO notifications (recipient_id, recipient_role, title, message, category, priority, related_id, related_type, action_url)
                SELECT id, 'parent', ?, ?, ?, ?, ?, 'announcement', '/parent/notifications' FROM parents
            """, (f"📢 {title}", description, category, priority, ann_id))

        # Batch fan-out to Faculty
        if aud in ['all', 'faculty', 'faculty only', 'all faculty']:
            db_conn.execute("""
                INSERT INTO notifications (recipient_id, recipient_role, title, message, category, priority, related_id, related_type, action_url)
                SELECT id, 'faculty', ?, ?, ?, ?, ?, 'announcement', '/faculty/notifications' FROM faculties
            """, (f"📢 {title}", description, category, priority, ann_id))

        db_conn.commit()

        # Broadcast Socket.IO event to all connected users
        if socketio_instance is not None:
            try:
                payload = {
                    'id': ann_id,
                    'title': f"📢 {title}",
                    'message': description,
                    'category': category,
                    'priority': priority,
                    'target_audience': target_audience,
                    'author_name': author_name,
                    'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'related_id': ann_id,
                    'related_type': 'announcement'
                }
                socketio_instance.emit('announcement_published', payload, room='all_users')
                socketio_instance.emit('new_notification', payload, room='all_users')
                if aud in ['all', 'students', 'students only', 'all students']:
                    socketio_instance.emit('new_notification', payload, room='role_student')
                if aud in ['all', 'parents', 'parents only', 'all parents']:
                    socketio_instance.emit('new_notification', payload, room='role_parent')
                if aud in ['all', 'faculty', 'faculty only', 'all faculty']:
                    socketio_instance.emit('new_notification', payload, room='role_faculty')
            except Exception as se:
                print(f"[SocketIO Announcement Error] {se}")

        return ann_id
    except Exception as e:
        print(f"[Broadcast Announcement Error] {e}")
        return None
    finally:
        if should_close:
            db_conn.close()


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
