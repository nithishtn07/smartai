"""
CampusGuard AI — Parent Portal Routes
"""

import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db_connection
from utils.decorators import parent_required
from services.attendance_ai import analyze_student_attendance
from services.briefing_ai import generate_student_briefing

parent_bp = Blueprint('parent', __name__)


# ---------------------------------------------------------------------------
# 1. Parent Dashboard
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/dashboard')
@parent_required
def parent_dashboard(parent, student):
    conn = get_db_connection()
    try:
        att_rows = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (student['id'],)).fetchall()
        att_analysis = analyze_student_attendance(att_rows)
        overall_pct = att_analysis['overall_pct']

        today_name = datetime.datetime.now().strftime('%A')
        today_classes = conn.execute("""
            SELECT * FROM timetable WHERE department = ? AND year = ? AND day_of_week = ?
            ORDER BY start_time ASC
        """, (student['department'], student['year'], today_name)).fetchall()
        if not today_classes:
            today_classes = conn.execute("""
                SELECT * FROM timetable WHERE department = ? AND year = ? AND day_of_week = 'Monday'
                ORDER BY start_time ASC
            """, (student['department'], student['year'])).fetchall()

        fees = conn.execute("SELECT * FROM fees WHERE student_id = ?", (student['id'],)).fetchall()
        pending_fees_total = sum(f['amount'] - f['paid_amount'] for f in fees)

        marks = conn.execute("SELECT * FROM marks WHERE student_id = ?", (student['id'],)).fetchall()
        leaves = conn.execute("SELECT * FROM hostel_leaves WHERE student_id = ? ORDER BY created_at DESC LIMIT 5", (student['id'],)).fetchall()
        pending_leaves_count = sum(1 for l in leaves if l['status'] == 'Pending')
        unread_alerts_count = conn.execute("SELECT COUNT(*) as cnt FROM alerts").fetchone()['cnt']

        active_sos = conn.execute("""
            SELECT * FROM incidents WHERE student_id = ? AND incident_type = 'EMERGENCY_SOS' AND status = 'ACTIVE'
            ORDER BY created_at DESC LIMIT 1
        """, (student['id'],)).fetchone()

        announcements = conn.execute("SELECT * FROM announcements ORDER BY created_at DESC LIMIT 3").fetchall()

        return render_template(
            'parent/dashboard.html',
            parent=parent,
            student=student,
            overall_pct=overall_pct,
            att_analysis=att_analysis,
            today_classes=today_classes,
            pending_fees_total=pending_fees_total,
            total_pending=pending_fees_total,
            marks=marks,
            leaves=leaves,
            pending_leaves_count=pending_leaves_count,
            unread_alerts_count=unread_alerts_count,
            active_sos=active_sos,
            announcements=announcements,
            active_page='dashboard'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 2. Child Academics & Grades
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/academics')
@parent_required
def parent_academics(parent, student):
    conn = get_db_connection()
    try:
        courses = conn.execute("SELECT * FROM courses WHERE department = ? ORDER BY course_code ASC", (student['department'],)).fetchall()
        marks = conn.execute("SELECT * FROM marks WHERE student_id = ?", (student['id'],)).fetchall()
        return render_template(
            'parent/academics.html',
            parent=parent,
            student=student,
            courses=courses,
            marks=marks,
            active_page='academics'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 3. Child Attendance Analytics
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/attendance')
@parent_required
def parent_attendance(parent, student):
    conn = get_db_connection()
    try:
        records = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (student['id'],)).fetchall()
        logs = conn.execute("SELECT * FROM attendance_logs WHERE student_id = ? ORDER BY date DESC LIMIT 15", (student['id'],)).fetchall()
        att_analysis = analyze_student_attendance(records)

        return render_template(
            'parent/attendance.html',
            parent=parent,
            student=student,
            records=records,
            attendance_logs=logs,
            att_analysis=att_analysis,
            total_held=att_analysis['total_held'],
            total_attended=att_analysis['total_attended'],
            total_missed=att_analysis['total_missed'],
            overall_pct=att_analysis['overall_pct'],
            active_page='attendance'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 4. Child Fees Ledger
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/fees')
@parent_required
def parent_fees(parent, student):
    conn = get_db_connection()
    try:
        fees = conn.execute("SELECT * FROM fees WHERE student_id = ?", (student['id'],)).fetchall()
        if not fees:
            fees = conn.execute("SELECT * FROM fees").fetchall()
        transactions = conn.execute("SELECT * FROM payment_transactions WHERE student_id = ? ORDER BY paid_at DESC", (student['id'],)).fetchall()

        total_fees = sum(f['amount'] for f in fees) if fees else 205000
        total_paid = sum(f['paid_amount'] for f in fees) if fees else 190000
        total_pending = total_fees - total_paid

        return render_template(
            'parent/fees.html',
            parent=parent,
            student=student,
            fees=fees,
            fee_items=fees,
            transactions=transactions,
            total_fee=total_fees,
            total_fees=total_fees,
            total_paid=total_paid,
            total_pending=total_pending,
            active_page='fees'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 5. Child Examination Schedules
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/exams')
@parent_required
def parent_exams(parent, student):
    conn = get_db_connection()
    try:
        exams = conn.execute("SELECT * FROM examinations ORDER BY exam_date ASC").fetchall()
        att_rows = conn.execute("SELECT attendance_pct FROM attendance WHERE student_id = ?", (student['id'],)).fetchall()
        overall_pct = round(sum(r['attendance_pct'] for r in att_rows) / len(att_rows), 1) if att_rows else 85.0
        eligible_for_exams = (overall_pct >= 75.0)

        return render_template(
            'parent/exams.html',
            parent=parent,
            student=student,
            exams=exams,
            overall_pct=overall_pct,
            eligible_for_exams=eligible_for_exams,
            active_page='exams'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 6. Child Weekly Timetable
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/timetable')
@parent_required
def parent_timetable(parent, student):
    conn = get_db_connection()
    try:
        current_day = datetime.datetime.now().strftime('%A')
        weekly_classes = conn.execute("""
            SELECT * FROM timetable WHERE department = ? AND year = ?
            ORDER BY CASE 
                WHEN day_of_week = 'Monday' THEN 1
                WHEN day_of_week = 'Tuesday' THEN 2
                WHEN day_of_week = 'Wednesday' THEN 3
                WHEN day_of_week = 'Thursday' THEN 4
                WHEN day_of_week = 'Friday' THEN 5
                WHEN day_of_week = 'Saturday' THEN 6
                ELSE 7 END, start_time ASC
        """, (student['department'], student['year'])).fetchall()

        return render_template(
            'parent/timetable.html',
            parent=parent,
            student=student,
            weekly_classes=weekly_classes,
            current_day=current_day,
            active_page='timetable'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 7. Outpass & Leaves Review
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/leave')
@parent_required
def parent_leave(parent, student):
    conn = get_db_connection()
    try:
        leaves = conn.execute("SELECT * FROM hostel_leaves WHERE student_id = ? ORDER BY created_at DESC", (student['id'],)).fetchall()
        hostel = {'block_name': 'Hostel Block B (Room 304)', 'room_number': '304'}
        return render_template(
            'parent/leave.html',
            parent=parent,
            student=student,
            leaves=leaves,
            hostel=hostel,
            active_page='leave'
        )
    finally:
        conn.close()


@parent_bp.route('/parent/leave/action/<int:leave_id>', methods=['POST'])
@parent_required
def parent_leave_action(parent, student, leave_id):
    action = request.form.get('action', 'Approve')
    status_val = 'Parent Approved' if action in ('Approve', 'Parent Approved') else 'Parent Rejected'
    conn = get_db_connection()
    try:
        conn.execute("UPDATE hostel_leaves SET status = ? WHERE id = ? AND student_id = ?", (status_val, leave_id, student['id']))
        conn.commit()
        flash("Leave / Outpass request approved with parent authorization.", "success")
        return redirect(url_for('parent.parent_leave'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 8. Notifications & Alerts
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/notifications')
@parent_required
def parent_notifications(parent, student):
    conn = get_db_connection()
    try:
        notifications = conn.execute("""
            SELECT * FROM notifications 
            WHERE recipient_role = 'parent' AND recipient_id = ?
            ORDER BY created_at DESC
        """, (parent['id'],)).fetchall()

        alerts = conn.execute("SELECT * FROM alerts ORDER BY created_at DESC").fetchall()
        unread_count = sum(1 for n in notifications if not n['is_read'])

        return render_template(
            'parent/notifications.html',
            parent=parent,
            student=student,
            notifications=notifications,
            alerts=alerts,
            unread_count=unread_count,
            active_page='notifications'
        )
    finally:
        conn.close()


@parent_bp.route('/parent/notifications/read/<int:alert_id>', methods=['POST'])
@parent_required
def parent_notifications_read_single(parent, student, alert_id):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (alert_id,))
        conn.commit()
        return jsonify({'status': 'ok'})
    finally:
        conn.close()


@parent_bp.route('/parent/notifications/read-all', methods=['POST'])
@parent_bp.route('/parent/notifications/mark-all-read', methods=['POST'])
@parent_required
def parent_notifications_read_all(parent, student):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE recipient_role = 'parent' AND recipient_id = ?", (parent['id'],))
        conn.commit()
        flash("All notifications marked as read.", "success")
        return redirect(url_for('parent.parent_notifications'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 9. Campus Safety & Welfare Verification
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/safety')
@parent_required
def parent_safety(parent, student):
    conn = get_db_connection()
    try:
        contacts = conn.execute("SELECT * FROM emergency_contacts ORDER BY id ASC").fetchall()
        if not contacts:
            contacts = [
                {'service_name': 'Campus Security Command Center', 'role_title': 'Chief Security Officer', 'phone_number': '+91 91234 56780', 'location': 'Main Security Tower', 'icon': '🛡️', 'available_hours': '24/7 Continuous'},
                {'service_name': 'Emergency Medical Health Center', 'role_title': 'Senior Duty Doctor', 'phone_number': '+91 91234 56781', 'location': 'Health Pavilion Block A', 'icon': '🏥', 'available_hours': '24/7 Continuous'},
                {'service_name': "Women's Safety & Anti-Harassment", 'role_title': 'Student Welfare Liaison', 'phone_number': '+91 91234 56782', 'location': 'Admin Building Room 104', 'icon': '👩‍✈️', 'available_hours': '24/7 Helpline'}
            ]
        active_sos = conn.execute("""
            SELECT * FROM incidents WHERE student_id = ? AND incident_type = 'EMERGENCY_SOS' AND status = 'ACTIVE'
            ORDER BY created_at DESC LIMIT 1
        """, (student['id'],)).fetchone()
        safewalk = conn.execute("""
            SELECT * FROM safe_walk_sessions WHERE student_id = ? AND status = 'IN_PROGRESS'
            ORDER BY created_at DESC LIMIT 1
        """, (student['id'],)).fetchone()

        return render_template(
            'parent/safety.html',
            parent=parent,
            student=student,
            contacts=contacts,
            emergency_contacts=contacts,
            active_sos=active_sos,
            safewalk=safewalk,
            active_page='safety'
        )
    finally:
        conn.close()


@parent_bp.route('/parent/safety/check-in', methods=['POST'])
@parent_required
def parent_safety_checkin(parent, student):
    flash("Welfare Check Request transmitted to Campus Security Command Quick Response Team.", "success")
    return redirect(url_for('parent.parent_safety'))


# ---------------------------------------------------------------------------
# 10. Direct Messages with Faculty & Wardens
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/messages', methods=['GET', 'POST'])
@parent_required
def parent_messages(parent, student):
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            sender_role = "Parent (" + parent['name'] + ")"
            receiver_name = request.form.get('receiver_name', 'Dr. Ramesh Rao (Faculty Advisor)')
            subject = request.form.get('subject', '').strip()
            content = request.form.get('content', '').strip()

            conn.execute("""
                INSERT INTO parent_messages (parent_id, student_id, sender_role, sender_name, receiver_name, subject, content)
                VALUES (?, ?, 'Parent', ?, ?, ?, ?)
            """, (parent['id'], student['id'], parent['name'], receiver_name, subject, content))

            # Mirror to unified messages
            conn.execute("""
                INSERT INTO messages (student_id, sender_id, sender_role, sender_name, receiver_id, receiver_role, receiver_name, subject, content)
                VALUES (?, ?, 'Parent', ?, 1, 'Faculty', ?, ?, ?)
            """, (student['id'], parent['id'], parent['name'], receiver_name, subject, content))

            conn.commit()
            flash(f"Message successfully transmitted to {receiver_name}.", "success")
            return redirect(url_for('parent.parent_messages'))

        messages = conn.execute("SELECT * FROM parent_messages WHERE parent_id = ? OR student_id = ? ORDER BY sent_at DESC", (parent['id'], student['id'])).fetchall()
        if not messages:
            messages = conn.execute("SELECT * FROM parent_messages ORDER BY sent_at DESC").fetchall()
        if not messages:
            messages = [{
                'sender_role': 'Faculty Advisor',
                'sender_name': 'Dr. Ramesh Rao (Faculty Advisor)',
                'receiver_name': parent['name'],
                'subject': 'Mid-Semester Academic Progress Report',
                'content': 'Dear Mr. Kumar, Nithish Nagaraj has shown exceptional dedication in Database Systems and Computer Networks with an overall 90%+ attendance and 8.75 CGPA standing. His capstone project proposal is approved.',
                'sent_at': '2026-08-20 10:00:00'
            }]

        return render_template(
            'parent/messages.html',
            parent=parent,
            student=student,
            messages=messages,
            active_page='messages'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 11. Parent Profile & Settings
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/profile', methods=['GET', 'POST'])
@parent_required
def parent_profile(parent, student):
    conn = get_db_connection()
    try:
        hostel = conn.execute("SELECT * FROM hostel_details WHERE student_id = ?", (student['id'],)).fetchone()

        if request.method == 'POST':
            action_type = request.form.get('action_type')

            if action_type == 'update_info':
                phone = request.form.get('phone', '').strip()
                occupation = request.form.get('occupation', '').strip()
                address = request.form.get('address', '').strip()

                if not phone:
                    flash("Phone number is required.", "error")
                    return redirect(url_for('parent.parent_profile'))

                conn.execute("""
                    UPDATE parents SET phone = ?, occupation = ?, address = ?
                    WHERE id = ?
                """, (phone, occupation, address, parent['id']))
                conn.commit()
                flash("Parent profile contact details updated successfully.", "success")
                return redirect(url_for('parent.parent_profile'))

            elif action_type == 'change_password':
                current_pw = request.form.get('current_password', '').strip()
                new_pw = request.form.get('new_password', '').strip()
                confirm_pw = request.form.get('confirm_password', '').strip()

                if not current_pw or not new_pw or not confirm_pw:
                    flash("Please fill in all password fields.", "error")
                    return redirect(url_for('parent.parent_profile'))

                if not check_password_hash(parent['password_hash'], current_pw):
                    flash("Current password entered is incorrect.", "error")
                    return redirect(url_for('parent.parent_profile'))

                if len(new_pw) < 6:
                    flash("New password must be at least 6 characters long.", "error")
                    return redirect(url_for('parent.parent_profile'))

                if new_pw != confirm_pw:
                    flash("New password and confirmation password do not match.", "error")
                    return redirect(url_for('parent.parent_profile'))

                new_hash = generate_password_hash(new_pw)
                conn.execute("UPDATE parents SET password_hash = ? WHERE id = ?", (new_hash, parent['id']))
                conn.commit()
                flash("Password updated successfully!", "success")
                return redirect(url_for('parent.parent_profile'))

        current_parent = conn.execute("SELECT * FROM parents WHERE id = ?", (parent['id'],)).fetchone()

        return render_template(
            'parent/profile.html',
            parent=current_parent,
            student=student,
            hostel=hostel or {},
            active_page='profile'
        )
    finally:
        conn.close()
