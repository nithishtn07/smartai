"""
CampusGuard AI — Admin Master Control Center Routes
"""

import datetime
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash
from database.db import get_db_connection
from utils.decorators import admin_required
from services.notification_service import (
    notify_student,
    notify_parent,
    notify_faculty,
    notify_admin,
    broadcast_announcement,
    log_activity,
    get_system_setting,
    set_system_setting
)
from services.campus_assistant import answer_admin_query
from services.emergency_service import transition_emergency_status, assign_responder
from services.safety_intelligence import (
    calculate_location_risk_scores,
    analyze_temporal_patterns,
    detect_emerging_risks,
    detect_repeated_patterns,
    generate_executive_safety_briefing
)

admin_bp = Blueprint('admin', __name__)


# ---------------------------------------------------------------------------
# 1. Admin Master Dashboard
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/dashboard')
@admin_required
def admin_dashboard(admin):
    conn = get_db_connection()
    try:
        total_students = conn.execute("SELECT COUNT(*) as cnt FROM students").fetchone()['cnt']
        total_faculty = conn.execute("SELECT COUNT(*) as cnt FROM faculties").fetchone()['cnt']
        total_parents = conn.execute("SELECT COUNT(*) as cnt FROM parents").fetchone()['cnt']
        total_courses = conn.execute("SELECT COUNT(*) as cnt FROM courses").fetchone()['cnt']

        # Attendance Metrics
        att_rows = conn.execute("SELECT attendance_pct FROM attendance").fetchall()
        avg_attendance = round(sum(r['attendance_pct'] for r in att_rows) / len(att_rows), 1) if att_rows else 85.0
        low_att_count = sum(1 for r in att_rows if r['attendance_pct'] < 75.0)

        # Financial Metrics
        fees_rows = conn.execute("SELECT amount, paid_amount FROM fees").fetchall()
        total_fees_expected = sum(r['amount'] for r in fees_rows)
        total_fees_collected = sum(r['paid_amount'] for r in fees_rows)
        pending_fees_total = total_fees_expected - total_fees_collected

        # Safety & Grievances
        active_sos_alerts = conn.execute("""
            SELECT i.*, s.name as student_name, s.register_number, s.phone as student_phone
            FROM incidents i
            LEFT JOIN students s ON i.student_id = s.id
            WHERE i.incident_type = 'EMERGENCY_SOS' AND i.status = 'ACTIVE'
            ORDER BY i.created_at DESC
        """).fetchall()

        active_complaints = conn.execute("""
            SELECT c.*, s.name as student_name, s.register_number 
            FROM complaints c
            JOIN students s ON c.student_id = s.id
            WHERE c.status NOT IN ('Resolved', 'Rejected')
            ORDER BY c.created_at DESC LIMIT 5
        """).fetchall()

        recent_logs = conn.execute("SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT 6").fetchall()
        announcements = conn.execute("SELECT * FROM announcements ORDER BY created_at DESC LIMIT 3").fetchall()

        # Subject Compliance Breakdown
        subject_stats = conn.execute("""
            SELECT subject_code, subject_name, AVG(attendance_pct) as avg_att, COUNT(*) as total_students
            FROM attendance
            GROUP BY subject_code, subject_name
        """).fetchall()

        return render_template(
            'admin/dashboard.html',
            admin=admin,
            total_students=total_students,
            total_faculty=total_faculty,
            total_parents=total_parents,
            total_courses=total_courses,
            avg_attendance=avg_attendance,
            low_att_count=low_att_count,
            pending_fees_total=pending_fees_total,
            total_fees_collected=total_fees_collected,
            active_sos_alerts=active_sos_alerts,
            active_complaints=active_complaints,
            recent_logs=recent_logs,
            announcements=announcements,
            subject_stats=subject_stats,
            active_page='dashboard'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 2. Student Management CRUD & 360 View
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/students', methods=['GET'])
@admin_required
def admin_students(admin):
    conn = get_db_connection()
    try:
        search_query = request.args.get('search', '').strip()
        dept_filter = request.args.get('department', 'All')

        query = "SELECT * FROM students WHERE 1=1"
        params = []
        if dept_filter != 'All':
            query += " AND department = ?"
            params.append(dept_filter)
        if search_query:
            query += " AND (name LIKE ? OR register_number LIKE ? OR email LIKE ?)"
            q = f"%{search_query}%"
            params.extend([q, q, q])

        query += " ORDER BY register_number ASC"
        students = conn.execute(query, params).fetchall()
        departments = conn.execute("SELECT DISTINCT department FROM students").fetchall()

        return render_template(
            'admin/students.html',
            admin=admin,
            students=students,
            departments=departments,
            current_dept=dept_filter,
            search_query=search_query,
            active_page='students'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/students/create', methods=['POST'])
@admin_required
def admin_student_create(admin):
    name = request.form.get('name', '').strip()
    reg_num = request.form.get('register_number', '').strip().upper()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    department = request.form.get('department', 'Computer Science')
    year = int(request.form.get('year', 1))
    semester = int(request.form.get('semester', 1))
    program = request.form.get('program', 'B.Tech')
    password = request.form.get('password', 'Student@123')

    if not name or not reg_num or not email:
        flash("Name, Register Number, and Email are required.", "error")
        return redirect(url_for('admin.admin_students'))

    conn = get_db_connection()
    try:
        pw_hash = generate_password_hash(password)
        conn.execute("""
            INSERT INTO students (name, register_number, email, password_hash, department, year, semester, program, phone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, reg_num, email, pw_hash, department, year, semester, program, phone))
        conn.commit()

        log_activity(admin['name'], 'admin', 'CREATE_STUDENT', f"Registered new student {name} ({reg_num})", record_id=reg_num)
        flash(f"Student account {reg_num} created successfully (Default Password: {password}).", "success")
        return redirect(url_for('admin.admin_students'))
    except Exception as e:
        flash(f"Error creating student: {e}", "error")
        return redirect(url_for('admin.admin_students'))
    finally:
        conn.close()


@admin_bp.route('/admin/students/view/<int:id>')
@admin_required
def admin_student_view(admin, id):
    conn = get_db_connection()
    try:
        student = conn.execute("SELECT * FROM students WHERE id = ?", (id,)).fetchone()
        if not student:
            flash("Student record not found.", "error")
            return redirect(url_for('admin.admin_students'))

        parent = conn.execute("SELECT * FROM parents WHERE student_id = ?", (id,)).fetchone()
        attendance = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (id,)).fetchall()
        marks = conn.execute("SELECT * FROM marks WHERE student_id = ?", (id,)).fetchall()
        fees = conn.execute("SELECT * FROM fees WHERE student_id = ?", (id,)).fetchall()
        leaves = conn.execute("SELECT * FROM hostel_leaves WHERE student_id = ? ORDER BY created_at DESC", (id,)).fetchall()
        incidents = conn.execute("SELECT * FROM incidents WHERE student_id = ? ORDER BY created_at DESC", (id,)).fetchall()

        return render_template(
            'admin/student_view.html',
            admin=admin,
            student=student,
            parent=parent,
            attendance=attendance,
            marks=marks,
            fees=fees,
            leaves=leaves,
            incidents=incidents,
            active_page='students'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/students/toggle-status/<int:id>', methods=['POST'])
@admin_required
def admin_student_toggle_status(admin, id):
    conn = get_db_connection()
    try:
        curr = conn.execute("SELECT status, name, register_number FROM students WHERE id = ?", (id,)).fetchone()
        if curr:
            new_status = 'DISABLED' if (curr['status'] or 'ACTIVE') == 'ACTIVE' else 'ACTIVE'
            conn.execute("UPDATE students SET status = ? WHERE id = ?", (new_status, id))
            conn.commit()
            log_activity(admin['name'], 'admin', 'TOGGLE_STUDENT_STATUS', f"Changed status of {curr['name']} to {new_status}", record_id=str(id))
            flash(f"Student {curr['name']} status set to {new_status}.", "success")
        return redirect(url_for('admin.admin_students'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 3. Parent Management CRUD & Linking
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/parents', methods=['GET'])
@admin_required
def admin_parents(admin):
    conn = get_db_connection()
    try:
        parents = conn.execute("""
            SELECT p.*, s.name as student_name, s.register_number as student_reg
            FROM parents p
            LEFT JOIN students s ON p.student_id = s.id
            ORDER BY p.id DESC
        """).fetchall()

        students = conn.execute("SELECT id, name, register_number FROM students ORDER BY name ASC").fetchall()

        return render_template(
            'admin/parents.html',
            admin=admin,
            parents=parents,
            students=students,
            active_page='parents'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/parents/create', methods=['POST'])
@admin_required
def admin_parent_create(admin):
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    relationship = request.form.get('relationship', 'Father')
    student_id = int(request.form.get('student_id'))
    occupation = request.form.get('occupation', '').strip()
    address = request.form.get('address', '').strip()
    password = request.form.get('password', 'Parent@123')

    parent_id = request.form.get('parent_id') or f"PAR{uuid.uuid4().hex[:5].upper()}"

    conn = get_db_connection()
    try:
        pw_hash = generate_password_hash(password)
        existing = conn.execute("SELECT id FROM parents WHERE email = ? OR parent_id = ?", (email, parent_id)).fetchone()
        if existing:
            conn.execute("""
                UPDATE parents 
                SET name = ?, phone = ?, relationship = ?, student_id = ?, occupation = ?, address = ?, parent_id = ?
                WHERE id = ?
            """, (name, phone, relationship, student_id, occupation, address, parent_id, existing['id']))
        else:
            conn.execute("""
                INSERT INTO parents (parent_id, name, email, phone, password_hash, relationship, student_id, occupation, address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (parent_id, name, email, phone, pw_hash, relationship, student_id, occupation, address))
        conn.commit()

        log_activity(admin['name'], 'admin', 'CREATE_PARENT', f"Linked parent {name} to student ID {student_id}", record_id=parent_id)
        flash(f"Parent account {parent_id} linked successfully (Default Password: {password}).", "success")
        return redirect(url_for('admin.admin_parents'))
    except Exception as e:
        flash(f"Error creating parent record: {e}", "error")
        return redirect(url_for('admin.admin_parents'))
    finally:
        conn.close()


@admin_bp.route('/admin/parents/reset-password/<int:id>', methods=['POST'])
@admin_required
def admin_parent_reset_password(admin, id):
    conn = get_db_connection()
    try:
        new_pw = "Parent@123"
        pw_hash = generate_password_hash(new_pw)
        conn.execute("UPDATE parents SET password_hash = ? WHERE id = ?", (pw_hash, id))
        conn.commit()
        log_activity(admin['name'], 'admin', 'RESET_PARENT_PASSWORD', f"Reset password for parent ID {id}", record_id=str(id))
        flash(f"Parent credentials successfully reset to default ('{new_pw}').", "success")
        return redirect(url_for('admin.admin_parents'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 4. Faculty Management CRUD
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/faculty', methods=['GET'])
@admin_required
def admin_faculty(admin):
    conn = get_db_connection()
    try:
        faculties = conn.execute("SELECT * FROM faculties ORDER BY name ASC").fetchall()
        departments = conn.execute("SELECT DISTINCT department FROM faculties").fetchall()
        return render_template(
            'admin/faculty.html',
            admin=admin,
            faculties=faculties,
            departments=departments,
            active_page='faculty'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/faculty/create', methods=['POST'])
@admin_required
def admin_faculty_create(admin):
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    department = request.form.get('department', 'Computer Science')
    designation = request.form.get('designation', 'Associate Professor')
    cabin = request.form.get('cabin', 'CS-201')
    password = request.form.get('password', 'Faculty@123')

    fac_id = f"FAC{uuid.uuid4().hex[:4].upper()}"

    conn = get_db_connection()
    try:
        pw_hash = generate_password_hash(password)
        conn.execute("""
            INSERT INTO faculties (faculty_id, name, email, phone, password_hash, department, designation, cabin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (fac_id, name, email, phone, pw_hash, department, designation, cabin))
        conn.commit()

        log_activity(admin['name'], 'admin', 'CREATE_FACULTY', f"Registered faculty {name} ({fac_id})", record_id=fac_id)
        flash(f"Faculty account {fac_id} created successfully (Password: {password}).", "success")
        return redirect(url_for('admin.admin_faculty'))
    except Exception as e:
        flash(f"Error creating faculty: {e}", "error")
        return redirect(url_for('admin.admin_faculty'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 5. Academics & Course Catalog
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/academics', methods=['GET'])
@admin_required
def admin_academics(admin):
    conn = get_db_connection()
    try:
        courses = conn.execute("SELECT * FROM courses ORDER BY course_code ASC").fetchall()
        faculties = conn.execute("SELECT name FROM faculties ORDER BY name ASC").fetchall()
        return render_template(
            'admin/academics.html',
            admin=admin,
            courses=courses,
            faculties=faculties,
            active_page='academics'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/academics/create', methods=['POST'])
@admin_required
def admin_academics_create(admin):
    code = (request.form.get('code') or request.form.get('course_code') or '').strip().upper()
    name = (request.form.get('name') or request.form.get('course_name') or '').strip()
    department = request.form.get('department', 'Computer Science & Engineering')
    semester = int(request.form.get('semester', 5))
    credits = int(request.form.get('credits', 4))
    faculty_name = request.form.get('faculty_name', 'Dr. Ramesh Rao')
    course_type = request.form.get('course_type', 'Core Theory')
    room = request.form.get('room_number', 'CS-201')
    timing = request.form.get('timing', 'Mon, Wed 09:00 AM')

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO courses (course_code, course_name, department, semester, credits, faculty_name, course_type, room_number, timing)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (code, name, department, semester, credits, faculty_name, course_type, room, timing))
        conn.commit()

        log_activity(admin['name'], 'admin', 'CREATE_COURSE', f"Created course {code} ({name})", record_id=code)
        flash(f"Course {code} added to academic registry.", "success")
        return redirect(url_for('admin.admin_academics'))
    except Exception as e:
        flash(f"Error creating course: {e}", "error")
        return redirect(url_for('admin.admin_academics'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 6. Attendance Monitoring
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/attendance', methods=['GET'])
@admin_required
def admin_attendance(admin):
    conn = get_db_connection()
    try:
        records = conn.execute("""
            SELECT a.*, s.name as student_name, s.register_number, s.department, s.phone as student_phone
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            ORDER BY a.attendance_pct ASC
        """).fetchall()

        low_att_students = [r for r in records if r['attendance_pct'] < 75.0]

        return render_template(
            'admin/attendance.html',
            admin=admin,
            records=records,
            low_att_students=low_att_students,
            active_page='attendance'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/attendance/send-warning/<int:student_id>', methods=['POST'])
@admin_required
def admin_attendance_send_warning(admin, student_id):
    conn = get_db_connection()
    try:
        student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if student:
            notify_student(student_id, "Institutional Attendance Deficiency Notice", "Your attendance has breached minimum university criteria (<75%). Submit an explanation to Dean Office.", category='Attendance', priority='Critical')
            parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (student_id,)).fetchone()
            if parent:
                notify_parent(parent['id'], f"Attendance Warning: {student['name']}", f"Official university notification: Ward {student['name']} attendance is below 75%.", category='Attendance', priority='Critical')
            flash(f"Official attendance warning notice successfully dispatched to {student['name']}.", "success")
        return redirect(url_for('admin.admin_attendance'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 7. Marks & Grades Audit
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/marks', methods=['GET'])
@admin_required
def admin_marks(admin):
    conn = get_db_connection()
    try:
        marks = conn.execute("""
            SELECT m.*, s.name as student_name, s.register_number, s.department,
                   m.cat1 as cat1_marks, m.cat2 as cat2_marks, m.fat as fat_marks
            FROM marks m
            JOIN students s ON m.student_id = s.id
            ORDER BY s.register_number ASC
        """).fetchall()

        return render_template(
            'admin/marks.html',
            admin=admin,
            marks=marks,
            all_marks=marks,
            active_page='marks'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 8. Fees & Finance
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/fees', methods=['GET'])
@admin_required
def admin_fees(admin):
    conn = get_db_connection()
    try:
        fees = conn.execute("""
            SELECT f.*, s.name as student_name, s.register_number, s.department
            FROM fees f
            JOIN students s ON f.student_id = s.id
            ORDER BY f.id DESC
        """).fetchall()

        students = conn.execute("SELECT id, name, register_number FROM students ORDER BY name ASC").fetchall()
        transactions = conn.execute("""
            SELECT pt.*, s.name as student_name, s.register_number
            FROM payment_transactions pt
            JOIN students s ON pt.student_id = s.id
            ORDER BY pt.paid_at DESC LIMIT 20
        """).fetchall()

        return render_template(
            'admin/fees.html',
            admin=admin,
            fees=fees,
            students=students,
            transactions=transactions,
            active_page='fees'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/fees/create', methods=['POST'])
@admin_required
def admin_fees_create(admin):
    student_id = int(request.form.get('student_id'))
    fee_type = request.form.get('fee_type', 'Semester Tuition Fee')
    amount = float(request.form.get('amount', 10000))
    due_date = request.form.get('due_date', '2026-09-30')

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status)
            VALUES (?, ?, ?, 0, ?, 'PENDING')
        """, (student_id, fee_type, amount, due_date))
        conn.commit()

        notify_student(student_id, f"Fee Invoice Issued: {fee_type}", f"An amount of INR {amount:,.2f} is due on {due_date}.", category='Fees')
        parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (student_id,)).fetchone()
        if parent:
            notify_parent(parent['id'], f"Fee Due Notification: {fee_type}", f"Fee invoice of INR {amount:,.2f} due on {due_date}.", category='Fees')

        log_activity(admin['name'], 'admin', 'CREATE_FEE', f"Issued fee invoice {fee_type} of INR {amount} for student ID {student_id}", record_id=str(student_id))
        flash("Fee invoice created and dispatched to student and guardian portals.", "success")
        return redirect(url_for('admin.admin_fees'))
    finally:
        conn.close()


@admin_bp.route('/admin/fees/mark-paid/<int:fee_id>', methods=['POST'])
@admin_required
def admin_fees_mark_paid(admin, fee_id):
    conn = get_db_connection()
    try:
        fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee_id,)).fetchone()
        if fee:
            conn.execute("UPDATE fees SET paid_amount = amount, status = 'PAID' WHERE id = ?", (fee_id,))
            txn_id = f"TXN-ADM-{uuid.uuid4().hex[:6].upper()}"
            rcp_no = f"REC-{uuid.uuid4().hex[:6].upper()}"
            paid_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            conn.execute("""
                INSERT INTO payment_transactions (transaction_id, student_id, fee_type, amount, payment_method, receipt_no, paid_at)
                VALUES (?, ?, ?, ?, 'Admin Manual Entry', ?, ?)
            """, (txn_id, fee['student_id'], fee['fee_type'], fee['amount'], rcp_no, paid_at))
            conn.commit()

            log_activity(admin['name'], 'admin', 'MARK_FEE_PAID', f"Marked fee ID {fee_id} as PAID (Receipt: {rcp_no})", record_id=str(fee_id))
            flash("Fee invoice marked as Paid.", "success")
        return redirect(url_for('admin.admin_fees'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 9. Examinations
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/exams', methods=['GET'])
@admin_required
def admin_exams(admin):
    conn = get_db_connection()
    try:
        exams = conn.execute("SELECT * FROM examinations ORDER BY exam_date ASC").fetchall()
        courses = conn.execute("SELECT course_code, course_name FROM courses ORDER BY course_code ASC").fetchall()
        return render_template(
            'admin/exams.html',
            admin=admin,
            exams=exams,
            courses=courses,
            active_page='exams'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/exams/create', methods=['POST'])
@admin_required
def admin_exams_create(admin):
    exam_type = request.form.get('exam_type', 'FAT Semester 5')
    course_code = request.form.get('course_code')
    course_name = request.form.get('course_name') or 'Database Systems'
    exam_date = request.form.get('exam_date')
    start_time = request.form.get('start_time', '09:30 AM')
    end_time = request.form.get('end_time', '12:30 PM')
    exam_time = request.form.get('exam_time') or f"{start_time} - {end_time}"
    venue = request.form.get('venue', 'Academic Block A')
    room = request.form.get('room_number', 'Exam Hall 3')
    seat = request.form.get('seat_number', 'Allotted')

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO examinations (exam_type, course_code, course_name, exam_date, exam_time, venue, room_number, seat_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (exam_type, course_code, course_name, exam_date, exam_time, venue, room, seat))
        conn.commit()

        broadcast_announcement(f"Examination Scheduled: {course_code}", f"{exam_type} for {course_name} is set on {exam_date} ({exam_time}) at {venue} - {room}.", category='Academic', priority='High', target_audience='All', author_name=admin['name'])
        log_activity(admin['name'], 'admin', 'SCHEDULE_EXAM', f"Scheduled exam {exam_type} for {course_code} on {exam_date}", record_id=course_code)

        flash(f"Examination scheduled and broadcasted for {course_code}.", "success")
        return redirect(url_for('admin.admin_exams'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 10. Leaves & Outpasses
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/leaves', methods=['GET'])
@admin_required
def admin_leaves(admin):
    conn = get_db_connection()
    try:
        leaves = conn.execute("""
            SELECT hl.*, s.name as student_name, s.register_number, s.department, s.phone as student_phone
            FROM hostel_leaves hl
            JOIN students s ON hl.student_id = s.id
            ORDER BY hl.created_at DESC
        """).fetchall()

        return render_template(
            'admin/leaves.html',
            admin=admin,
            leaves=leaves,
            active_page='leaves'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/leaves/action/<int:leave_id>', methods=['POST'])
@admin_required
def admin_leaves_action(admin, leave_id):
    decision = request.form.get('decision', 'Approved')
    conn = get_db_connection()
    try:
        conn.execute("UPDATE hostel_leaves SET status = ? WHERE id = ?", (decision, leave_id))
        conn.commit()

        leave = conn.execute("SELECT * FROM hostel_leaves WHERE id = ?", (leave_id,)).fetchone()
        if leave:
            notify_student(leave['student_id'], f"Hostel Outpass {decision}", f"Your outpass application was {decision.lower()} by Admin.", category='Hostel')
            parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (leave['student_id'],)).fetchone()
            if parent:
                notify_parent(parent['id'], f"Hostel Outpass {decision}", f"Residential outpass for your ward was {decision.lower()} by Campus Admin.", category='Hostel')

        log_activity(admin['name'], 'admin', 'LEAVE_DECISION', f"Leave ID {leave_id} marked as {decision}", record_id=str(leave_id))
        flash(f"Leave request marked as {decision}.", "success")
        return redirect(url_for('admin.admin_leaves'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 11. Safety & SOS Command Center
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/safety', methods=['GET'])
@admin_required
def admin_safety(admin):
    conn = get_db_connection()
    try:
        active_emergencies = conn.execute("""
            SELECT i.*, s.name as student_name, s.register_number, s.phone as student_phone
            FROM incidents i
            LEFT JOIN students s ON i.student_id = s.id
            WHERE i.incident_type = 'EMERGENCY_SOS' AND i.status != 'RESOLVED' AND i.status != 'CANCELLED'
            ORDER BY i.created_at DESC
        """).fetchall()

        all_incidents = conn.execute("""
            SELECT i.*, s.name as student_name, s.register_number
            FROM incidents i
            LEFT JOIN students s ON i.student_id = s.id
            ORDER BY i.created_at DESC LIMIT 30
        """).fetchall()

        contacts = conn.execute("SELECT * FROM emergency_contacts ORDER BY id ASC").fetchall()

        incidents_list = conn.execute("SELECT * FROM incidents").fetchall()
        complaints_list = conn.execute("SELECT * FROM complaints").fetchall()

        # Risk Intelligence Synthesis
        risk_scores = calculate_location_risk_scores(incidents_list, complaints_list)
        temporal_analysis = analyze_temporal_patterns(incidents_list)
        emerging_risks = detect_emerging_risks(incidents_list)

        return render_template(
            'admin/safety.html',
            admin=admin,
            active_emergencies=active_emergencies,
            all_incidents=all_incidents,
            emergency_contacts=contacts,
            risk_scores=risk_scores,
            temporal_analysis=temporal_analysis,
            emerging_risks=emerging_risks,
            active_page='safety'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/api/ai-assistant', methods=['POST'])
@admin_required
def admin_api_ai_assistant(admin):
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    conn = get_db_connection()
    try:
        reply = answer_admin_query(query, conn)
        return jsonify({'status': 'success', 'reply': reply})
    finally:
        conn.close()


@admin_bp.route('/admin/sos/status-update', methods=['POST'])
@admin_required
def admin_sos_status_update(admin):
    incident_id = request.form.get('incident_id')
    new_status = request.form.get('new_status') or request.form.get('status') or 'RESOLVED'
    assigned_to = request.form.get('assigned_to', 'QRT Command')

    conn = get_db_connection()
    try:
        if assigned_to and assigned_to != 'Unassigned':
            assign_responder(incident_id, assigned_to, 'Quick Response Team', actor_name=admin['name'], actor_role='admin', conn=conn)

        transition_emergency_status(incident_id, new_status, admin['name'], 'admin', notes=f"Status set to {new_status} by Admin", conn=conn)

        conn.execute("""
            UPDATE incidents SET status = ?, assigned_to = ? WHERE incident_id = ?
        """, (new_status, assigned_to, incident_id))
        
        conn.commit()

        log_activity(admin['name'], 'admin', 'SOS_STATUS_UPDATE', f"Emergency {incident_id} transitioned to {new_status} (Unit: {assigned_to})", record_id=incident_id)
        flash(f"Emergency beacon {incident_id} updated to {new_status}.", "success")
        return redirect(url_for('admin.admin_safety'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 12. Announcements & Multi-Role Broadcasts
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/announcements', methods=['GET', 'POST'])
@admin_required
def admin_announcements(admin):
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            title = request.form.get('title')
            description = request.form.get('description')
            category = request.form.get('category', 'General')
            priority = request.form.get('priority', 'Normal')
            target = request.form.get('target_audience', 'All')

            conn.execute("""
                INSERT INTO announcements (title, description, category, priority, target_audience, author_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, description, category, priority, target, admin['name']))
            conn.commit()

            broadcast_announcement(title, description, category=category, priority=priority, target_audience=target, author_name=admin['name'])
            log_activity(admin['name'], 'admin', 'BROADCAST_ANNOUNCEMENT', f"Dispatched announcement '{title}' to {target}", record_id=title)

            flash("Institutional announcement published across selected portals.", "success")
            return redirect(url_for('admin.admin_announcements'))

        announcements = conn.execute("SELECT * FROM announcements ORDER BY created_at DESC").fetchall()
        return render_template(
            'admin/announcements.html',
            admin=admin,
            announcements=announcements,
            active_page='announcements'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 13. Direct Messages
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/messages', methods=['GET', 'POST'])
@admin_required
def admin_messages(admin):
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            receiver_role = request.form.get('receiver_role', 'Faculty')
            receiver_name = request.form.get('receiver_name', 'Faculty Advisor')
            subject = request.form.get('subject', '').strip()
            content = request.form.get('content', '').strip()

            conn.execute("""
                INSERT INTO messages (
                    student_id, sender_id, sender_role, sender_name,
                    receiver_id, receiver_role, receiver_name,
                    subject, content, is_read
                ) VALUES (1, 1, 'Admin', ?, 1, ?, ?, ?, ?, 0)
            """, (admin['name'], receiver_role, receiver_name, subject, content))
            conn.commit()
            flash(f"Administrative message sent to {receiver_name}.", "success")
            return redirect(url_for('admin.admin_messages'))

        messages = conn.execute("SELECT * FROM messages ORDER BY sent_at DESC LIMIT 50").fetchall()
        return render_template(
            'admin/messages.html',
            admin=admin,
            messages=messages,
            active_page='messages'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 14. Institutional Reports
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/reports', methods=['GET'])
@admin_required
def admin_reports(admin):
    conn = get_db_connection()
    try:
        stats = {
            'students_count': conn.execute("SELECT COUNT(*) as cnt FROM students").fetchone()['cnt'],
            'faculty_count': conn.execute("SELECT COUNT(*) as cnt FROM faculties").fetchone()['cnt'],
            'courses_count': conn.execute("SELECT COUNT(*) as cnt FROM courses").fetchone()['cnt'],
            'incidents_count': conn.execute("SELECT COUNT(*) as cnt FROM incidents").fetchone()['cnt'],
            'complaints_count': conn.execute("SELECT COUNT(*) as cnt FROM complaints").fetchone()['cnt']
        }
        return render_template('admin/reports.html', admin=admin, stats=stats, active_page='reports')
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 15. Audit Logs
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/audit-logs')
@admin_required
def admin_audit_logs(admin):
    conn = get_db_connection()
    try:
        logs = conn.execute("SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT 100").fetchall()
        return render_template('admin/audit_logs.html', admin=admin, logs=logs, active_page='audit_logs')
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 16. System Settings
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings(admin):
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            threshold = request.form.get('attendance_threshold', '75.0')
            academic_year = request.form.get('academic_year', '2026-2027')
            active_sem = request.form.get('active_semester', 'Fall 2026')
            inst_name = request.form.get('institution_name', 'CampusGuard Institute')

            set_system_setting('attendance_threshold', threshold, 'Minimum attendance percentage')
            set_system_setting('academic_year', academic_year, 'Academic Operating Year')
            set_system_setting('active_semester', active_sem, 'Active Academic Term')
            set_system_setting('institution_name', inst_name, 'Institutional Branding Title')

            log_activity(admin['name'], 'admin', 'UPDATE_SETTINGS', "Updated institutional operating parameters")
            flash("System settings successfully updated.", "success")
            return redirect(url_for('admin.admin_settings'))

        settings_rows = conn.execute("SELECT * FROM system_settings").fetchall()
        settings_dict = {s['key_name']: s['value_text'] for s in settings_rows}
        return render_template('admin/settings.html', admin=admin, settings=settings_dict, settings_rows=settings_rows, active_page='settings')
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 17. Admin Analytics
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/analytics')
@admin_required
def admin_analytics(admin):
    conn = get_db_connection()
    try:
        incidents_list = conn.execute("SELECT * FROM incidents").fetchall()
        complaints_list = conn.execute("SELECT * FROM complaints").fetchall()

        risk_scores = calculate_location_risk_scores(incidents_list, complaints_list)
        temporal_analysis = analyze_temporal_patterns(incidents_list)
        emerging_risks = detect_emerging_risks(incidents_list)
        repeated_patterns = detect_repeated_patterns(incidents_list, complaints_list)
        executive_briefing = generate_executive_safety_briefing(incidents_list, complaints_list, risk_scores)

        return render_template(
            'admin/analytics.html',
            admin=admin,
            briefing=executive_briefing,
            risk_scores=risk_scores,
            zone_scores=risk_scores,
            temporal=temporal_analysis,
            emerging=emerging_risks,
            emerging_risks=emerging_risks,
            patterns=repeated_patterns,
            repeated_patterns=repeated_patterns,
            active_page='analytics'
        )
    finally:
        conn.close()
