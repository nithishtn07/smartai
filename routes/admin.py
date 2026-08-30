"""
CampusGuard AI — Admin Master Control Center Routes
"""

import datetime
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash
from database.db import get_db_connection
from models.attendance import AttendanceModel
from utils.decorators import admin_required
from services.academic_service import calculate_student_cgpa, sync_student_cgpa
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
        avg_attendance = round(sum(r['attendance_pct'] for r in att_rows) / len(att_rows), 1) if att_rows else 0.0
        low_att_count = sum(1 for r in att_rows if r['attendance_pct'] < 75.0)

        # Financial Metrics
        fees_rows = conn.execute("SELECT amount, paid_amount FROM fees").fetchall()
        total_fees_expected = sum(r['amount'] for r in fees_rows)
        total_fees_collected = sum(r['paid_amount'] for r in fees_rows)
        pending_fees_total = total_fees_expected - total_fees_collected

        # Safety & Grievances (Unified Single Source of Truth)
        active_sos_alerts = conn.execute("""
            SELECT e.*, e.emergency_id as incident_id, e.reporter_name as student_name,
                   COALESCE(s.register_number, '') as register_number,
                   COALESCE(s.phone, e.reporter_phone, '') as student_phone,
                   e.campus_zone as location
            FROM emergencies e
            LEFT JOIN students s ON (e.user_id = s.id AND e.user_role = 'student')
            WHERE e.status IN ('TRIGGERED', 'ACKNOWLEDGED', 'ASSIGNED', 'RESPONDER_ASSIGNED', 'EN_ROUTE', 'ON_SCENE', 'ACTIVE', 'RESPONDING')
            ORDER BY e.priority_score DESC, e.created_at DESC
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

        # Incident metrics for safety chart
        resolved_incidents_count = conn.execute("SELECT COUNT(*) as cnt FROM incidents WHERE status IN ('RESOLVED', 'CLOSED', 'Resolved', 'Closed')").fetchone()['cnt']
        active_incidents_count = conn.execute("SELECT COUNT(*) as cnt FROM incidents WHERE status IN ('ACTIVE', 'TRIGGERED', 'DISPATCHED', 'ON_SCENE', 'Active')").fetchone()['cnt']
        monitoring_incidents_count = conn.execute("SELECT COUNT(*) as cnt FROM incidents WHERE status NOT IN ('RESOLVED', 'CLOSED', 'Resolved', 'Closed', 'ACTIVE', 'TRIGGERED', 'DISPATCHED', 'ON_SCENE', 'Active')").fetchone()['cnt']
        pending_leaves_count = conn.execute("SELECT COUNT(*) as cnt FROM hostel_leaves WHERE status = 'Pending'").fetchone()['cnt']
        active_sos_count = len(active_sos_alerts)

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
            active_sos_count=active_sos_count,
            active_complaints=active_complaints,
            recent_logs=recent_logs,
            announcements=announcements,
            subject_stats=subject_stats,
            resolved_incidents_count=resolved_incidents_count,
            active_incidents_count=active_incidents_count,
            monitoring_incidents_count=monitoring_incidents_count,
            pending_leaves_count=pending_leaves_count,
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
        search_query = request.args.get('search', '').strip() or request.args.get('q', '').strip()
        dept_filter = request.args.get('department', '') or request.args.get('dept', '')
        status_filter = request.args.get('status', '').strip()

        query = """
            SELECT s.*, 
                   COALESCE(p.name, s.parent_name, 'Not Assigned') as parent_name,
                   COALESCE(p.email, '') as parent_email,
                   COALESCE(p.phone, s.parent_phone, '') as parent_phone,
                   COALESCE(p.parent_id, '') as parent_account_id,
                   COALESCE(ps.relationship, p.relationship, 'Guardian') as relationship,
                   CASE WHEN p.id IS NOT NULL THEN 'Created & Linked' ELSE 'Not Linked' END as parent_account_status
            FROM students s
            LEFT JOIN parent_student ps ON s.id = ps.student_id
            LEFT JOIN parents p ON (ps.parent_id = p.id OR (ps.parent_id IS NULL AND p.student_id = s.id))
            WHERE s.status != 'DELETED'
        """
        params = []
        if dept_filter and dept_filter != 'All':
            query += " AND s.department = ?"
            params.append(dept_filter)
        if status_filter and status_filter != 'All':
            query += " AND s.status = ?"
            params.append(status_filter)
        if search_query:
            query += " AND (s.name LIKE ? OR s.register_number LIKE ? OR s.email LIKE ? OR s.phone LIKE ? OR p.name LIKE ? OR p.email LIKE ? OR p.phone LIKE ?)"
            q = f"%{search_query}%"
            params.extend([q, q, q, q, q, q, q])

        query += " GROUP BY s.id ORDER BY s.register_number ASC"
        students = conn.execute(query, params).fetchall()
        departments = conn.execute("SELECT DISTINCT department FROM students WHERE status != 'DELETED'").fetchall()

        return render_template(
            'admin/students.html',
            admin=admin,
            students=students,
            departments=departments,
            current_dept=dept_filter,
            dept=dept_filter,
            current_status=status_filter,
            search_query=search_query,
            query=search_query,
            active_page='students'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/students/create', methods=['POST'])
@admin_required
def admin_student_create(admin):
    is_json = request.is_json or request.headers.get('Accept') == 'application/json'
    data = request.get_json() if request.is_json else request.form

    name = data.get('name', '').strip()
    reg_num = data.get('register_number', '').strip().upper()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    department = data.get('department', '').strip()
    year_raw = data.get('year', '')
    semester_raw = data.get('semester', '')
    program = data.get('program', 'B.Tech').strip()
    dob = data.get('dob', '').strip()
    address = data.get('address', '').strip()
    student_pw = data.get('password') or 'Student@123'

    # Parent / Guardian fields
    parent_name = (data.get('parent_name') or data.get('guardian_name') or '').strip()
    parent_email = (data.get('parent_email') or data.get('guardian_email') or '').strip().lower()
    parent_phone = (data.get('parent_phone') or data.get('guardian_phone') or '').strip()
    parent_relationship = (data.get('parent_relationship') or data.get('relationship') or '').strip()
    parent_address = (data.get('parent_address') or address or '').strip()
    parent_occupation = (data.get('parent_occupation') or '').strip()
    parent_pw = data.get('parent_password') or 'Parent@123'

    # Fallback parent info if omitted
    if not parent_name: parent_name = f"{name} Guardian"
    if not parent_email: parent_email = f"parent.{email}" if email else "parent@example.com"
    if not parent_phone: parent_phone = phone if phone else "+91 98765 00000"
    if not parent_relationship: parent_relationship = "Guardian"

    missing_fields = []
    if not name: missing_fields.append("Student Name")
    if not reg_num: missing_fields.append("Register Number")
    if not email: missing_fields.append("Campus Email")
    if not department: missing_fields.append("Department")

    if missing_fields:
        msg = f"Required fields missing: {', '.join(missing_fields)}"
        if is_json:
            return jsonify({'success': False, 'error': msg}), 400
        flash(msg, "error")
        return redirect(url_for('admin.admin_students'))

    try:
        year = int(year_raw)
        semester = int(semester_raw)
    except (ValueError, TypeError):
        msg = "Year and Semester must be valid numbers."
        if is_json:
            return jsonify({'success': False, 'error': msg}), 400
        flash(msg, "error")
        return redirect(url_for('admin.admin_students'))

    conn = get_db_connection()
    try:
        # Check student duplicate
        existing_student = conn.execute(
            "SELECT id FROM students WHERE (UPPER(register_number) = ? OR LOWER(email) = ?) AND status != 'DELETED'",
            (reg_num, email)
        ).fetchone()
        if existing_student:
            msg = f"Student with Register Number {reg_num} or Email {email} already exists."
            if is_json:
                return jsonify({'success': False, 'error': msg}), 409
            flash(msg, "error")
            return redirect(url_for('admin.admin_students'))

        # Check existing parent (by email or phone)
        existing_parent = conn.execute(
            "SELECT id, parent_id, name, email FROM parents WHERE LOWER(email) = ? OR (phone != '' AND phone = ?)",
            (parent_email, parent_phone)
        ).fetchone()

        student_pw_hash = generate_password_hash(student_pw)
        parent_pw_hash = generate_password_hash(parent_pw)

        # 1. Insert Student record
        cursor = conn.execute("""
            INSERT INTO students (
                name, register_number, email, password_hash, department, year,
                semester, program, phone, dob, address, parent_name, parent_phone
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, reg_num, email, student_pw_hash, department, year,
            semester, program, phone, dob, address, parent_name, parent_phone
        ))
        new_student_id = cursor.lastrowid

        parent_created = False
        if existing_parent:
            parent_pk = existing_parent['id']
            parent_code = existing_parent['parent_id']
            # Link existing parent to the new student
            conn.execute("""
                INSERT OR IGNORE INTO parent_student (parent_id, student_id, relationship, is_primary)
                VALUES (?, ?, ?, 0)
            """, (parent_pk, new_student_id, parent_relationship))
        else:
            parent_code = f"PAR{uuid.uuid4().hex[:5].upper()}"
            while conn.execute("SELECT id FROM parents WHERE parent_id = ?", (parent_code,)).fetchone():
                parent_code = f"PAR{uuid.uuid4().hex[:5].upper()}"

            cursor_p = conn.execute("""
                INSERT INTO parents (
                    parent_id, name, email, phone, password_hash, relationship,
                    student_id, occupation, address
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                parent_code, parent_name, parent_email, parent_phone,
                parent_pw_hash, parent_relationship, new_student_id,
                parent_occupation, parent_address
            ))
            parent_pk = cursor_p.lastrowid
            parent_created = True

            # Insert into parent_student mapping
            conn.execute("""
                INSERT OR IGNORE INTO parent_student (parent_id, student_id, relationship, is_primary)
                VALUES (?, ?, ?, 1)
            """, (parent_pk, new_student_id, parent_relationship))

        # Commit single atomic transaction
        conn.commit()

        log_activity(
            admin['name'], 'admin', 'CREATE_STUDENT_WITH_PARENT',
            f"Created student {name} ({reg_num}) and linked parent {parent_name} ({parent_code})",
            record_id=reg_num
        )

        msg = f"Student {name} ({reg_num}) created successfully! Parent account {parent_code} ({parent_name}) automatically linked."
        if is_json:
            return jsonify({
                'success': True,
                'student_created': True,
                'parent_created': parent_created,
                'linked': True,
                'student_id': new_student_id,
                'register_number': reg_num,
                'parent_id': parent_code,
                'message': msg
            }), 201

        flash(f"✓ {msg} (Default Passwords: Student@123 / Parent@123)", "success")
        return redirect(url_for('admin.admin_students'))

    except Exception as e:
        conn.rollback()
        msg = f"Error creating student: {e}"
        if is_json:
            return jsonify({'success': False, 'error': msg}), 500
        flash(msg, "error")
        return redirect(url_for('admin.admin_students'))
    finally:
        conn.close()


@admin_bp.route('/admin/students/api/<int:id>', methods=['GET'])
@admin_required
def admin_student_api(admin, id):
    conn = get_db_connection()
    try:
        student = conn.execute("SELECT * FROM students WHERE id = ?", (id,)).fetchone()
        if not student:
            return jsonify({'success': False, 'error': 'Student not found'}), 404

        parent = conn.execute("""
            SELECT p.*, ps.relationship as link_relationship
            FROM parents p
            LEFT JOIN parent_student ps ON p.id = ps.parent_id
            WHERE ps.student_id = ? OR p.student_id = ?
            LIMIT 1
        """, (id, id)).fetchone()

        s_dict = dict(student)
        s_dict.pop('password_hash', None)  # Never expose password hash

        p_dict = dict(parent) if parent else None
        if p_dict:
            p_dict.pop('password_hash', None)

        return jsonify({
            'success': True,
            'student': s_dict,
            'parent': p_dict
        })
    finally:
        conn.close()


@admin_bp.route('/admin/students/edit/<int:id>', methods=['POST'])
@admin_required
def admin_student_edit(admin, id):
    is_json = request.is_json or request.headers.get('Accept') == 'application/json'
    data = request.get_json() if request.is_json else request.form

    name = data.get('name', '').strip()
    reg_num = data.get('register_number', '').strip().upper()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    department = data.get('department', '').strip()
    program = data.get('program', 'B.Tech').strip()
    year_raw = data.get('year', 1)
    semester_raw = data.get('semester', 1)
    section = data.get('section', 'A').strip()
    dob = data.get('dob', '').strip()
    address = data.get('address', '').strip()
    status = data.get('status', 'ACTIVE').strip()

    parent_name = data.get('parent_name', '').strip()
    parent_phone = data.get('parent_phone', '').strip()
    parent_relationship = data.get('parent_relationship', 'Guardian').strip()

    if not name:
        msg = "Student name cannot be empty."
        if is_json: return jsonify({'success': False, 'error': msg}), 400
        flash(msg, "error")
        return redirect(url_for('admin.admin_students'))

    try:
        year = int(year_raw)
        semester = int(semester_raw)
    except (ValueError, TypeError):
        year, semester = 1, 1

    conn = get_db_connection()
    try:
        # Check student exists
        student = conn.execute("SELECT id, register_number, email FROM students WHERE id = ?", (id,)).fetchone()
        if not student:
            msg = "Student record not found."
            if is_json: return jsonify({'success': False, 'error': msg}), 404
            flash(msg, "error")
            return redirect(url_for('admin.admin_students'))

        # Check duplicate register_number or email if modified
        if reg_num or email:
            duplicate = conn.execute("""
                SELECT id FROM students 
                WHERE id != ? AND status != 'DELETED' AND (
                    (UPPER(register_number) = ? AND ? != '') OR 
                    (LOWER(email) = ? AND ? != '')
                )
            """, (id, reg_num, reg_num, email, email)).fetchone()
            if duplicate:
                msg = f"Another student already has register number '{reg_num}' or email '{email}'."
                if is_json: return jsonify({'success': False, 'error': msg}), 409
                flash(msg, "error")
                return redirect(url_for('admin.admin_students'))

        # Build update statement for student
        current_reg = reg_num if reg_num else student['register_number']
        current_email = email if email else student['email']

        conn.execute("""
            UPDATE students 
            SET name = ?, register_number = ?, email = ?, phone = ?, department = ?, program = ?,
                year = ?, semester = ?, section = ?, dob = ?, address = ?, status = ?,
                parent_name = ?, parent_phone = ?
            WHERE id = ?
        """, (name, current_reg, current_email, phone, department, program,
              year, semester, section, dob, address, status,
              parent_name, parent_phone, id))

        # Update linked parent details if provided
        if parent_name or parent_phone:
            ps = conn.execute("SELECT parent_id FROM parent_student WHERE student_id = ?", (id,)).fetchone()
            if ps:
                conn.execute("""
                    UPDATE parents 
                    SET name = COALESCE(NULLIF(?, ''), name),
                        phone = COALESCE(NULLIF(?, ''), phone),
                        relationship = ?
                    WHERE id = ?
                """, (parent_name, parent_phone, parent_relationship, ps['parent_id']))
                conn.execute("""
                    UPDATE parent_student SET relationship = ? WHERE parent_id = ? AND student_id = ?
                """, (parent_relationship, ps['parent_id'], id))
            else:
                p = conn.execute("SELECT id FROM parents WHERE student_id = ?", (id,)).fetchone()
                if p:
                    conn.execute("""
                        UPDATE parents 
                        SET name = COALESCE(NULLIF(?, ''), name),
                            phone = COALESCE(NULLIF(?, ''), phone),
                            relationship = ?
                        WHERE id = ?
                    """, (parent_name, parent_phone, parent_relationship, p['id']))

        conn.commit()
        log_activity(admin['name'], 'admin', 'EDIT_STUDENT', f"Updated details for student {name} ({current_reg})", record_id=str(id))
        
        msg = f"✓ Student '{name}' ({current_reg}) updated successfully."
        if is_json:
            return jsonify({'success': True, 'message': msg})
        flash(msg, "success")
        return redirect(url_for('admin.admin_students'))
    except Exception as e:
        conn.rollback()
        msg = f"Error updating student: {e}"
        if is_json: return jsonify({'success': False, 'error': msg}), 500
        flash(msg, "error")
        return redirect(url_for('admin.admin_students'))
    finally:
        conn.close()


@admin_bp.route('/admin/students/delete/<int:id>', methods=['POST', 'DELETE'])
@admin_required
def admin_student_delete(admin, id):
    is_json = request.is_json or request.headers.get('Accept') == 'application/json'
    conn = get_db_connection()
    try:
        student = conn.execute("SELECT name, register_number FROM students WHERE id = ?", (id,)).fetchone()
        if not student:
            msg = "Student not found."
            if is_json: return jsonify({'success': False, 'error': msg}), 404
            flash(msg, "error")
            return redirect(url_for('admin.admin_students'))

        # Find linked parents before unlinking
        parent_links = conn.execute("SELECT parent_id FROM parent_student WHERE student_id = ?", (id,)).fetchall()
        
        # Safely soft delete student record
        conn.execute("UPDATE students SET status = 'DELETED' WHERE id = ?", (id,))
        # Remove parent_student mapping
        conn.execute("DELETE FROM parent_student WHERE student_id = ?", (id,))

        # For each linked parent, update remaining active children pointer
        for pl in parent_links:
            parent_id = pl['parent_id']
            remaining = conn.execute("""
                SELECT s.id FROM students s
                JOIN parent_student ps ON s.id = ps.student_id
                WHERE ps.parent_id = ? AND s.status != 'DELETED'
            """, (parent_id,)).fetchall()

            if remaining:
                conn.execute("UPDATE parents SET student_id = ? WHERE id = ?", (remaining[0]['id'], parent_id))
            else:
                conn.execute("UPDATE parents SET student_id = 0 WHERE id = ?", (parent_id,))

        conn.commit()
        log_activity(admin['name'], 'admin', 'DELETE_STUDENT', f"Deleted student {student['name']} ({student['register_number']})", record_id=str(id))
        
        msg = f"✓ Student '{student['name']}' ({student['register_number']}) has been successfully deleted."
        if is_json:
            return jsonify({'success': True, 'message': msg})
        flash(msg, "success")
        return redirect(url_for('admin.admin_students'))
    except Exception as e:
        conn.rollback()
        msg = f"Error removing student: {e}"
        if is_json: return jsonify({'success': False, 'error': msg}), 500
        flash(msg, "error")
        return redirect(url_for('admin.admin_students'))
    finally:
        conn.close()


@admin_bp.route('/admin/students/view/<int:id>')
@admin_required
def admin_student_view(admin, id):
    conn = get_db_connection()
    try:
        student_row = conn.execute("SELECT * FROM students WHERE id = ?", (id,)).fetchone()
        if not student_row:
            flash("Student record not found.", "error")
            return redirect(url_for('admin.admin_students'))

        student = dict(student_row)
        cgpa, earned_credits, _, _ = calculate_student_cgpa(conn, id)
        student['cgpa'] = cgpa
        student['sgpa'] = cgpa
        if cgpa is not None:
            student['earned_credits'] = earned_credits

        parent = conn.execute("""
            SELECT p.*, ps.relationship as link_relationship
            FROM parents p
            LEFT JOIN parent_student ps ON p.id = ps.parent_id
            WHERE ps.student_id = ? OR p.student_id = ?
            LIMIT 1
        """, (id, id)).fetchone()
        attendance = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (id,)).fetchall()
        marks = conn.execute("""
            SELECT m.*, COALESCE(c.credits, 4) as credits
            FROM marks m
            LEFT JOIN courses c ON m.course_code = c.course_code
            WHERE m.student_id = ?
            ORDER BY m.course_code ASC
        """, (id,)).fetchall()
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
    is_json = request.is_json or request.headers.get('Accept') == 'application/json'
    conn = get_db_connection()
    try:
        curr = conn.execute("SELECT status, name, register_number FROM students WHERE id = ?", (id,)).fetchone()
        if curr:
            new_status = 'DISABLED' if (curr['status'] or 'ACTIVE') == 'ACTIVE' else 'ACTIVE'
            conn.execute("UPDATE students SET status = ? WHERE id = ?", (new_status, id))
            conn.commit()
            log_activity(admin['name'], 'admin', 'TOGGLE_STUDENT_STATUS', f"Changed status of {curr['name']} to {new_status}", record_id=str(id))
            msg = f"Student '{curr['name']}' status set to {new_status}."
            if is_json:
                return jsonify({'success': True, 'new_status': new_status, 'message': msg})
            flash(msg, "success")
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
        search_query = request.args.get('search', '').strip() or request.args.get('q', '').strip()

        # Query all parents with multi-child aggregation
        query = """
            SELECT p.*,
                   GROUP_CONCAT(DISTINCT s.name || ' (' || s.register_number || ')') as linked_students_display,
                   GROUP_CONCAT(DISTINCT s.id) as linked_student_ids,
                   COUNT(DISTINCT s.id) as linked_children_count,
                   MAX(s.name) as student_name,
                   MAX(s.register_number) as student_reg
            FROM parents p
            LEFT JOIN parent_student ps ON p.id = ps.parent_id
            LEFT JOIN students s ON (ps.student_id = s.id OR (ps.parent_id IS NULL AND p.student_id = s.id)) AND s.status != 'DELETED'
            WHERE 1=1
        """
        params = []
        if search_query:
            query += """
                AND (
                    p.name LIKE ? OR 
                    p.email LIKE ? OR 
                    p.parent_id LIKE ? OR 
                    p.phone LIKE ? OR 
                    p.occupation LIKE ? OR
                    s.name LIKE ? OR 
                    s.register_number LIKE ?
                )
            """
            q = f"%{search_query}%"
            params.extend([q, q, q, q, q, q, q])

        query += " GROUP BY p.id ORDER BY p.id DESC"
        parents_rows = conn.execute(query, params).fetchall()

        # Enrich parents with actual child objects for rich UI
        parents = []
        for pr in parents_rows:
            p_dict = dict(pr)
            # Fetch all linked children details
            children = conn.execute("""
                SELECT s.id, s.name, s.register_number, s.department, s.year, s.semester,
                       COALESCE(ps.relationship, 'Guardian') as link_relationship
                FROM students s
                JOIN parent_student ps ON s.id = ps.student_id
                WHERE ps.parent_id = ? AND s.status != 'DELETED'
            """, (pr['id'],)).fetchall()

            # If no parent_student mapping, fallback to pr['student_id']
            if not children and pr['student_id'] and pr['student_id'] > 0:
                c = conn.execute("SELECT id, name, register_number, department, year, semester FROM students WHERE id = ? AND status != 'DELETED'", (pr['student_id'],)).fetchone()
                if c:
                    children = [dict(c)]

            p_dict['children'] = [dict(c) for c in children]
            p_dict.pop('password_hash', None)
            parents.append(p_dict)

        all_students = conn.execute("SELECT id, name, register_number, department FROM students WHERE status != 'DELETED' ORDER BY name ASC").fetchall()

        return render_template(
            'admin/parents.html',
            admin=admin,
            parents=parents,
            students=all_students,
            all_students=all_students,
            search_query=search_query,
            query=search_query,
            active_page='parents'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/parents/api/<int:id>', methods=['GET'])
@admin_required
def admin_parent_api(admin, id):
    conn = get_db_connection()
    try:
        parent = conn.execute("SELECT * FROM parents WHERE id = ?", (id,)).fetchone()
        if not parent:
            return jsonify({'success': False, 'error': 'Parent not found'}), 404

        children = conn.execute("""
            SELECT s.id, s.name, s.register_number, s.department, s.year, s.semester, s.phone,
                   COALESCE(ps.relationship, p.relationship, 'Guardian') as link_relationship
            FROM students s
            JOIN parent_student ps ON s.id = ps.student_id
            JOIN parents p ON ps.parent_id = p.id
            WHERE ps.parent_id = ? AND s.status != 'DELETED'
        """, (id,)).fetchall()

        if not children and parent['student_id'] and parent['student_id'] > 0:
            c = conn.execute("SELECT id, name, register_number, department, year, semester, phone FROM students WHERE id = ? AND status != 'DELETED'", (parent['student_id'],)).fetchone()
            if c:
                children = [dict(c)]

        p_dict = dict(parent)
        p_dict.pop('password_hash', None)
        p_dict['children'] = [dict(c) for c in children]

        return jsonify({
            'success': True,
            'parent': p_dict
        })
    finally:
        conn.close()


@admin_bp.route('/admin/parents/create', methods=['POST'])
@admin_required
def admin_parent_create(admin):
    is_json = request.is_json or request.headers.get('Accept') == 'application/json'
    data = request.get_json() if request.is_json else request.form

    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    relationship = data.get('relationship', 'Father').strip()
    student_id_raw = data.get('student_id')
    occupation = data.get('occupation', '').strip()
    address = data.get('address', '').strip()
    password = data.get('password') or 'Parent@123'

    parent_id = data.get('parent_id') or f"PAR{uuid.uuid4().hex[:5].upper()}"

    if not name or not email or not phone:
        msg = "Parent Name, Email, and Phone Number are required."
        if is_json: return jsonify({'success': False, 'error': msg}), 400
        flash(msg, "error")
        return redirect(url_for('admin.admin_parents'))

    student_id = int(student_id_raw) if student_id_raw else 0

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
            p_id = existing['id']
        else:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO parents (parent_id, name, email, phone, password_hash, relationship, student_id, occupation, address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (parent_id, name, email, phone, pw_hash, relationship, student_id, occupation, address))
            p_id = cursor.lastrowid

        # Maintain parent_student mapping
        if student_id > 0:
            conn.execute("""
                INSERT OR REPLACE INTO parent_student (parent_id, student_id, relationship, is_primary)
                VALUES (?, ?, ?, 1)
            """, (p_id, student_id, relationship))
            # Sync parent name to student
            conn.execute("UPDATE students SET parent_name = ?, parent_phone = ? WHERE id = ?", (name, phone, student_id))

        conn.commit()

        log_activity(admin['name'], 'admin', 'CREATE_PARENT', f"Linked parent {name} ({parent_id})", record_id=str(p_id))
        msg = f"✓ Parent account {parent_id} registered successfully (Default Password: {password})."
        if is_json:
            return jsonify({'success': True, 'message': msg, 'parent_id': parent_id})
        flash(msg, "success")
        return redirect(url_for('admin.admin_parents'))
    except Exception as e:
        conn.rollback()
        msg = f"Error creating parent record: {e}"
        if is_json: return jsonify({'success': False, 'error': msg}), 500
        flash(msg, "error")
        return redirect(url_for('admin.admin_parents'))
    finally:
        conn.close()


@admin_bp.route('/admin/parents/edit/<int:id>', methods=['POST'])
@admin_required
def admin_parent_edit(admin, id):
    is_json = request.is_json or request.headers.get('Accept') == 'application/json'
    data = request.get_json() if request.is_json else request.form

    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    relationship = data.get('relationship', 'Guardian').strip()
    occupation = data.get('occupation', '').strip()
    address = data.get('address', '').strip()
    parent_id = data.get('parent_id', '').strip().upper()
    student_id_raw = data.get('student_id')

    if not name or not email or not phone:
        msg = "Guardian Name, Email, and Phone Number are required."
        if is_json: return jsonify({'success': False, 'error': msg}), 400
        flash(msg, "error")
        return redirect(url_for('admin.admin_parents'))

    conn = get_db_connection()
    try:
        parent = conn.execute("SELECT * FROM parents WHERE id = ?", (id,)).fetchone()
        if not parent:
            msg = "Parent record not found."
            if is_json: return jsonify({'success': False, 'error': msg}), 404
            flash(msg, "error")
            return redirect(url_for('admin.admin_parents'))

        # Check duplicate email or parent_id
        duplicate = conn.execute("""
            SELECT id FROM parents WHERE id != ? AND (LOWER(email) = ? OR UPPER(parent_id) = ?)
        """, (id, email, parent_id)).fetchone()
        if duplicate:
            msg = f"Another parent account with email '{email}' or ID '{parent_id}' already exists."
            if is_json: return jsonify({'success': False, 'error': msg}), 409
            flash(msg, "error")
            return redirect(url_for('admin.admin_parents'))

        p_code = parent_id if parent_id else parent['parent_id']
        student_id = int(student_id_raw) if student_id_raw else parent['student_id']

        # Update parent record
        conn.execute("""
            UPDATE parents 
            SET name = ?, email = ?, phone = ?, relationship = ?, occupation = ?, address = ?, parent_id = ?, student_id = ?
            WHERE id = ?
        """, (name, email, phone, relationship, occupation, address, p_code, student_id, id))

        # Update or link student in parent_student
        if student_id and student_id > 0:
            conn.execute("""
                INSERT OR REPLACE INTO parent_student (parent_id, student_id, relationship, is_primary)
                VALUES (?, ?, ?, 1)
            """, (id, student_id, relationship))
            # Sync parent name to student
            conn.execute("UPDATE students SET parent_name = ?, parent_phone = ? WHERE id = ?", (name, phone, student_id))

        conn.commit()
        log_activity(admin['name'], 'admin', 'EDIT_PARENT', f"Updated parent {name} ({p_code})", record_id=str(id))

        msg = f"✓ Parent '{name}' ({p_code}) records updated successfully."
        if is_json:
            return jsonify({'success': True, 'message': msg})
        flash(msg, "success")
        return redirect(url_for('admin.admin_parents'))
    except Exception as e:
        conn.rollback()
        msg = f"Error updating parent: {e}"
        if is_json: return jsonify({'success': False, 'error': msg}), 500
        flash(msg, "error")
        return redirect(url_for('admin.admin_parents'))
    finally:
        conn.close()


@admin_bp.route('/admin/parents/delete/<int:id>', methods=['POST', 'DELETE'])
@admin_required
def admin_parent_delete(admin, id):
    is_json = request.is_json or request.headers.get('Accept') == 'application/json'
    conn = get_db_connection()
    try:
        parent = conn.execute("SELECT name, parent_id FROM parents WHERE id = ?", (id,)).fetchone()
        if not parent:
            msg = "Parent record not found."
            if is_json: return jsonify({'success': False, 'error': msg}), 404
            flash(msg, "error")
            return redirect(url_for('admin.admin_parents'))

        # Safe removal of mappings and dependent items
        conn.execute("DELETE FROM parent_student WHERE parent_id = ?", (id,))
        conn.execute("DELETE FROM parent_messages WHERE parent_id = ?", (id,))
        conn.execute("DELETE FROM parent_alert_reads WHERE parent_id = ?", (id,))
        conn.execute("DELETE FROM parents WHERE id = ?", (id,))

        conn.commit()
        log_activity(admin['name'], 'admin', 'DELETE_PARENT', f"Deleted parent {parent['name']} ({parent['parent_id']})", record_id=str(id))

        msg = f"✓ Parent account '{parent['name']}' ({parent['parent_id']}) has been safely deleted."
        if is_json:
            return jsonify({'success': True, 'message': msg})
        flash(msg, "success")
        return redirect(url_for('admin.admin_parents'))
    except Exception as e:
        conn.rollback()
        msg = f"Error removing parent: {e}"
        if is_json: return jsonify({'success': False, 'error': msg}), 500
        flash(msg, "error")
        return redirect(url_for('admin.admin_parents'))
    finally:
        conn.close()


@admin_bp.route('/admin/parents/reset-password/<int:id>', methods=['POST'])
@admin_required
def admin_parent_reset_password(admin, id):
    is_json = request.is_json or request.headers.get('Accept') == 'application/json'
    conn = get_db_connection()
    try:
        new_pw = "Parent@123"
        pw_hash = generate_password_hash(new_pw)
        conn.execute("UPDATE parents SET password_hash = ? WHERE id = ?", (pw_hash, id))
        conn.commit()
        log_activity(admin['name'], 'admin', 'RESET_PARENT_PASSWORD', f"Reset password for parent ID {id}", record_id=str(id))
        msg = f"Parent credentials successfully reset to default ('{new_pw}')."
        if is_json:
            return jsonify({'success': True, 'message': msg})
        flash(msg, "success")
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
# ---------------------------------------------------------------------------
# 8. Fees & Finance Management
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/fees', methods=['GET'])
@admin_required
def admin_fees(admin):
    conn = get_db_connection()
    try:
        search_query = request.args.get('search', '').strip()
        status_filter = request.args.get('status', 'ALL').strip()
        fee_type_filter = request.args.get('fee_type', 'ALL').strip()

        today_str = datetime.date.today().strftime('%Y-%m-%d')

        # Base query for all fees to compute global financial KPIs
        all_fees_raw = conn.execute("SELECT * FROM fees").fetchall()
        total_billed = sum(float(f['amount'] or 0) for f in all_fees_raw) if all_fees_raw else 0.0
        total_collected = sum(float(f['paid_amount'] or 0) for f in all_fees_raw) if all_fees_raw else 0.0
        total_pending = max(0.0, total_billed - total_collected)
        
        overdue_amount = 0.0
        overdue_count = 0
        for f in all_fees_raw:
            amt = float(f['amount'] or 0)
            paid = float(f['paid_amount'] or 0)
            bal = max(0.0, amt - paid)
            due = str(f['due_date'] or '')[:10]
            if due and due < today_str and bal > 0:
                overdue_amount += bal
                overdue_count += 1

        # Payments Today KPI
        today_stats = conn.execute("""
            SELECT COALESCE(SUM(amount), 0) as tot, COUNT(*) as cnt 
            FROM payment_transactions 
            WHERE DATE(paid_at) = DATE('now')
        """).fetchone()
        today_collected = float(today_stats['tot'] or 0)
        payments_today_count = int(today_stats['cnt'] or 0)
        failed_payments_count = 0

        # Filtered query for the fees table view
        query = """
            SELECT f.*, s.name as student_name, s.register_number, s.department
            FROM fees f
            JOIN students s ON f.student_id = s.id
            WHERE s.status != 'DELETED'
        """
        params = []
        if search_query:
            query += " AND (s.name LIKE ? OR s.register_number LIKE ? OR f.fee_type LIKE ?)"
            q = f"%{search_query}%"
            params.extend([q, q, q])

        if fee_type_filter and fee_type_filter != 'ALL':
            query += " AND f.fee_type LIKE ?"
            params.append(f"%{fee_type_filter}%")

        query += " ORDER BY f.id DESC"
        filtered_fees_raw = conn.execute(query, tuple(params)).fetchall()

        # Process filtered list with calculated status and overdue flags
        fees = []
        for f_row in filtered_fees_raw:
            item = dict(f_row)
            amt = float(item['amount'] or 0)
            paid = float(item['paid_amount'] or 0)
            pending = max(0.0, amt - paid)
            due = str(item.get('due_date') or '')[:10]
            is_overdue = (due < today_str and pending > 0) if due else False

            if pending <= 0 or item.get('status') in ('PAID', 'Paid'):
                calc_status = 'PAID'
            elif is_overdue:
                calc_status = 'OVERDUE'
            elif paid > 0:
                calc_status = 'PARTIAL'
            else:
                calc_status = 'PENDING'

            item['is_overdue'] = is_overdue
            item['pending_amount'] = pending
            item['calculated_status'] = calc_status

            if status_filter == 'ALL' or status_filter == calc_status:
                fees.append(item)

        students = conn.execute("SELECT id, name, register_number, department FROM students WHERE status != 'DELETED' ORDER BY name ASC").fetchall()
        departments = conn.execute("SELECT DISTINCT department FROM students WHERE status != 'DELETED'").fetchall()

        # Payment transactions query with search
        tx_query = """
            SELECT pt.*, s.name as student_name, s.register_number
            FROM payment_transactions pt
            JOIN students s ON pt.student_id = s.id
            WHERE 1=1
        """
        tx_params = []
        if search_query:
            tx_query += " AND (pt.transaction_id LIKE ? OR pt.receipt_no LIKE ? OR s.name LIKE ? OR s.register_number LIKE ?)"
            q = f"%{search_query}%"
            tx_params.extend([q, q, q, q])

        tx_query += " ORDER BY pt.paid_at DESC, pt.id DESC LIMIT 50"
        transactions = conn.execute(tx_query, tuple(tx_params)).fetchall()

        return render_template(
            'admin/fees.html',
            admin=admin,
            fees=fees,
            students=students,
            departments=departments,
            transactions=transactions,
            total_billed=total_billed,
            total_collected=total_collected,
            total_pending=total_pending,
            overdue_amount=overdue_amount,
            overdue_count=overdue_count,
            today_collected=today_collected,
            payments_today_count=payments_today_count,
            failed_payments_count=failed_payments_count,
            search_query=search_query,
            status_filter=status_filter,
            fee_type_filter=fee_type_filter,
            active_page='fees'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/fees/create', methods=['POST'])
@admin_required
def admin_fees_create(admin):
    target_selection = request.form.get('student_id')
    fee_type = request.form.get('fee_type', 'Tuition Fee').strip()
    amount = float(request.form.get('amount', 10000))
    due_date = request.form.get('due_date', '2026-09-30').strip()
    academic_year = request.form.get('academic_year', '2026-2027').strip()
    semester = int(request.form.get('semester', 5))

    conn = get_db_connection()
    try:
        target_student_ids = []
        if target_selection == 'ALL':
            stu_rows = conn.execute("SELECT id FROM students WHERE status != 'DELETED'").fetchall()
            target_student_ids = [r['id'] for r in stu_rows]
        elif target_selection and target_selection.startswith('DEPT_'):
            dept_name = target_selection.replace('DEPT_', '')
            stu_rows = conn.execute("SELECT id FROM students WHERE department = ? AND status != 'DELETED'", (dept_name,)).fetchall()
            target_student_ids = [r['id'] for r in stu_rows]
        elif target_selection and target_selection.isdigit():
            target_student_ids = [int(target_selection)]

        if not target_student_ids:
            flash("Please select a valid student or recipient group.", "error")
            return redirect(url_for('admin.admin_fees'))

        created_count = 0
        for s_id in target_student_ids:
            conn.execute("""
                INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status, academic_year, semester)
                VALUES (?, ?, ?, 0, ?, 'PENDING', ?, ?)
            """, (s_id, fee_type, amount, due_date, academic_year, semester))

            notify_student(s_id, f"Fee Invoice Issued: {fee_type}", f"An invoice of INR {amount:,.2f} is due on {due_date}.", category='Fees')
            parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (s_id,)).fetchone()
            if parent:
                notify_parent(parent['id'], f"Fee Due Notification: {fee_type}", f"Fee invoice of INR {amount:,.2f} due on {due_date}.", category='Fees')
            created_count += 1

        conn.commit()
        log_activity(admin['name'], 'admin', 'CREATE_FEE', f"Issued {fee_type} of INR {amount} to {created_count} students", record_id=str(target_selection))
        flash(f"✅ Fee invoice '{fee_type}' issued to {created_count} students successfully.", "success")
        return redirect(url_for('admin.admin_fees'))
    finally:
        conn.close()


@admin_bp.route('/admin/fees/edit/<int:fee_id>', methods=['POST'])
@admin_required
def admin_fees_edit(admin, fee_id):
    fee_type = request.form.get('fee_type').strip()
    amount = float(request.form.get('amount', 0))
    due_date = request.form.get('due_date').strip()
    academic_year = request.form.get('academic_year', '2026-2027').strip()
    semester = int(request.form.get('semester', 5))

    conn = get_db_connection()
    try:
        fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee_id,)).fetchone()
        if not fee:
            flash("Fee invoice record not found.", "error")
            return redirect(url_for('admin.admin_fees'))

        paid_amount = float(fee['paid_amount'] or 0)
        new_status = 'PAID' if paid_amount >= amount else ('PARTIAL' if paid_amount > 0 else 'PENDING')

        conn.execute("""
            UPDATE fees 
            SET fee_type = ?, amount = ?, due_date = ?, academic_year = ?, semester = ?, status = ?
            WHERE id = ?
        """, (fee_type, amount, due_date, academic_year, semester, new_status, fee_id))
        conn.commit()

        log_activity(admin['name'], 'admin', 'EDIT_FEE', f"Updated fee #{fee_id} to INR {amount} ({fee_type})", record_id=str(fee_id))
        flash(f"✅ Fee invoice #{fee_id} updated successfully.", "success")
        return redirect(url_for('admin.admin_fees'))
    finally:
        conn.close()


@admin_bp.route('/admin/fees/cancel/<int:fee_id>', methods=['POST'])
@admin_required
def admin_fees_cancel(admin, fee_id):
    conn = get_db_connection()
    try:
        fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee_id,)).fetchone()
        if not fee:
            flash("Fee invoice not found.", "error")
            return redirect(url_for('admin.admin_fees'))

        if float(fee['paid_amount'] or 0) > 0:
            flash("Cannot delete a fee invoice that has payments recorded against it.", "error")
            return redirect(url_for('admin.admin_fees'))

        conn.execute("DELETE FROM fees WHERE id = ?", (fee_id,))
        conn.commit()

        log_activity(admin['name'], 'admin', 'CANCEL_FEE', f"Cancelled fee invoice #{fee_id} ({fee['fee_type']})", record_id=str(fee_id))
        flash(f"✓ Fee invoice #{fee_id} cancelled successfully.", "success")
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
            remaining = max(0.0, float(fee['amount']) - float(fee['paid_amount']))
            if remaining <= 0:
                flash("This fee is already completely cleared.", "info")
                return redirect(url_for('admin.admin_fees'))

            conn.execute("UPDATE fees SET paid_amount = amount, status = 'PAID' WHERE id = ?", (fee_id,))
            txn_id = f"TXN-ADM-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
            rcp_no = f"REC-{uuid.uuid4().hex[:6].upper()}"
            paid_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            conn.execute("""
                INSERT INTO payment_transactions (transaction_id, student_id, fee_type, amount, payment_method, receipt_no, paid_at, status, fee_id)
                VALUES (?, ?, ?, ?, 'Admin Cash / Cheque Entry', ?, ?, 'SUCCESS', ?)
            """, (txn_id, fee['student_id'], fee['fee_type'], remaining, rcp_no, paid_at, fee_id))
            conn.commit()

            notify_student(fee['student_id'], f"Fee Payment Recorded: {fee['fee_type']}", f"An amount of INR {remaining:,.2f} has been cleared by Administration (Receipt #{rcp_no}).", category='Fees')
            parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (fee['student_id'],)).fetchone()
            if parent:
                notify_parent(parent['id'], f"Fee Payment Recorded: {fee['fee_type']}", f"Admin payment of INR {remaining:,.2f} recorded (Receipt #{rcp_no}).", category='Fees')

            log_activity(admin['name'], 'admin', 'MARK_FEE_PAID', f"Marked fee ID {fee_id} as PAID (Receipt: {rcp_no})", record_id=str(fee_id))
            flash(f"✅ Fee invoice marked as Paid. Official Receipt #{rcp_no} generated.", "success")
        return redirect(url_for('admin.admin_fees'))
    finally:
        conn.close()


@admin_bp.route('/admin/fees/receipt/<receipt_no>')
@admin_required
def admin_fees_receipt(admin, receipt_no):
    from services.payment_service import get_payment_receipt
    receipt = get_payment_receipt(receipt_no)
    if not receipt:
        flash("Official payment receipt not found.", "error")
        return redirect(url_for('admin.admin_fees'))

    return render_template(
        'parent/receipt_view.html',
        receipt=receipt,
        student={'name': receipt['student_name'], 'register_number': receipt['register_number']},
        back_url=url_for('admin.admin_fees'),
        active_page='fees'
    )


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
        # 1. Active Emergencies (Single Source of Truth)
        active_emergencies = conn.execute("""
            SELECT e.*, e.emergency_id as incident_id, e.reporter_name as student_name,
                   COALESCE(s.register_number, '') as register_number,
                   COALESCE(s.phone, e.reporter_phone, '') as student_phone,
                   e.campus_zone as location
            FROM emergencies e
            LEFT JOIN students s ON (e.user_id = s.id AND e.user_role = 'student')
            WHERE e.status IN ('TRIGGERED', 'ACKNOWLEDGED', 'ASSIGNED', 'RESPONDER_ASSIGNED', 'EN_ROUTE', 'ON_SCENE', 'ACTIVE', 'RESPONDING')
            ORDER BY e.priority_score DESC, e.created_at DESC, e.id DESC
        """).fetchall()

        # 2. SOS History (Resolved / Closed / Cancelled past records)
        sos_history = conn.execute("""
            SELECT e.*, e.emergency_id as incident_id, e.reporter_name as student_name,
                   COALESCE(s.register_number, '') as register_number,
                   COALESCE(s.phone, e.reporter_phone, '') as student_phone,
                   e.campus_zone as location
            FROM emergencies e
            LEFT JOIN students s ON (e.user_id = s.id AND e.user_role = 'student')
            WHERE e.status IN ('RESOLVED', 'CLOSED', 'STAND_DOWN', 'CANCELLED')
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT 100
        """).fetchall()

        active_sos_count = len(active_emergencies)
        contacts = conn.execute("SELECT * FROM emergency_contacts ORDER BY id ASC").fetchall()
        
        safe_walks = []
        has_sw = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='safe_walks'").fetchone()
        if has_sw:
            safe_walks = conn.execute("SELECT * FROM safe_walks WHERE status IN ('ACTIVE', 'EN_ROUTE') ORDER BY created_at DESC").fetchall()

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
            active_sos_count=active_sos_count,
            sos_history=sos_history,
            all_incidents=active_emergencies,
            emergency_contacts=contacts,
            safe_walks=safe_walks,
            risk_scores=risk_scores,
            temporal_analysis=temporal_analysis,
            emerging_risks=emerging_risks,
            active_page='safety'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/api/ai-assistant', methods=['POST'])
@admin_bp.route('/api/admin/chat', methods=['POST'])
@admin_bp.route('/admin/api/chat', methods=['POST'])
@admin_required
def admin_api_ai_assistant(admin):
    data = request.get_json() or {}
    query = (data.get('query') or data.get('message') or '').strip()
    if not query:
        return jsonify({
            'status': 'success',
            'reply': "Hello Administrator! Ask me about registered student statistics, fee collections vs pending balances, or safety SOS metrics.",
            'suggestions': ['How many students are registered?', 'How much fee has been collected?', 'How many SOS incidents occurred?']
        })

    conn = get_db_connection()
    try:
        from services.unified_ai_assistant import process_unified_ai_query
        result = process_unified_ai_query(
            role='admin',
            user_id=admin['id'],
            query=query,
            conn=conn
        )
        return jsonify({'status': 'success', 'reply': result.get('reply', ''), 'intent': result.get('intent', '')})
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
        student_count = conn.execute("SELECT COUNT(*) as cnt FROM students").fetchone()['cnt']
        faculty_count = conn.execute("SELECT COUNT(*) as cnt FROM faculties").fetchone()['cnt']
        courses_count = conn.execute("SELECT COUNT(*) as cnt FROM courses").fetchone()['cnt']
        incidents_count = conn.execute("SELECT COUNT(*) as cnt FROM incidents").fetchone()['cnt']
        complaints_count = conn.execute("SELECT COUNT(*) as cnt FROM complaints").fetchone()['cnt']

        fees = conn.execute("SELECT amount, paid_amount FROM fees").fetchall()
        total_billed = sum(f['amount'] for f in fees) if fees else 0
        total_collected = sum(f['paid_amount'] for f in fees) if fees else 0
        pending_fees_total = max(0, total_billed - total_collected)

        att_rows = conn.execute("SELECT attendance_pct FROM attendance").fetchall()
        avg_attendance = (sum(r['attendance_pct'] for r in att_rows) / len(att_rows)) if att_rows else 0.0

        stats = {
            'students_count': student_count,
            'faculty_count': faculty_count,
            'courses_count': courses_count,
            'incidents_count': incidents_count,
            'complaints_count': complaints_count,
            'pending_fees_total': pending_fees_total,
            'avg_attendance': avg_attendance
        }
        return render_template(
            'admin/reports.html',
            admin=admin,
            stats=stats,
            student_count=student_count,
            incidents_count=incidents_count,
            pending_fees_total=pending_fees_total,
            avg_attendance=avg_attendance,
            active_page='reports'
        )
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


# ---------------------------------------------------------------------------
# 18. Faculty Directory & Management
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/faculties')
@admin_bp.route('/admin/faculty')
@admin_required
def admin_faculties(admin):
    conn = get_db_connection()
    try:
        faculties = conn.execute("SELECT * FROM faculties ORDER BY name ASC").fetchall()
        courses = conn.execute("SELECT * FROM courses ORDER BY course_code ASC").fetchall()
        return render_template(
            'admin/faculty.html',
            admin=admin,
            faculties=faculties,
            courses=courses,
            active_page='faculty'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/faculty/edit/<int:id>', methods=['POST'])
@admin_required
def admin_faculty_edit(admin, id):
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    department = request.form.get('department')
    designation = request.form.get('designation')
    cabin = request.form.get('cabin')

    conn = get_db_connection()
    try:
        conn.execute("""
            UPDATE faculties 
            SET name = ?, email = ?, phone = ?, department = ?, designation = ?, cabin = ?
            WHERE id = ?
        """, (name, email, phone, department, designation, cabin, id))
        conn.commit()
        log_activity(admin['name'], 'admin', 'EDIT_FACULTY', f"Updated faculty {name} (ID: {id})", record_id=str(id))
        flash(f"Faculty details for {name} updated successfully.", "success")
        return redirect(url_for('admin.admin_faculties'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 19. Central Attendance Monitoring & Governance
# ---------------------------------------------------------------------------
@admin_bp.route('/admin/attendance')
@admin_required
def admin_attendance(admin):
    conn = get_db_connection()
    try:
        threshold = float(get_system_setting('attendance_threshold', '75.0'))
        search_query = request.args.get('q', '').strip()
        selected_course = request.args.get('course', '').strip()
        status_filter = request.args.get('status', 'all').strip()

        # Query master attendance records
        query = """
            SELECT a.*, s.name as student_name, s.register_number, s.department, s.year, s.section,
                   c.faculty_name
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            LEFT JOIN courses c ON a.subject_code = c.course_code
            WHERE 1=1
        """
        params = []

        if search_query:
            query += " AND (s.name LIKE ? OR s.register_number LIKE ? OR s.email LIKE ?)"
            params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

        if selected_course:
            query += " AND a.subject_code = ?"
            params.append(selected_course)

        if status_filter == 'risk':
            query += " AND a.attendance_pct < ? AND a.classes_held > 0"
            params.append(threshold)
        elif status_filter == 'good':
            query += " AND a.attendance_pct >= ?"
            params.append(threshold)

        query += " ORDER BY a.attendance_pct ASC, s.name ASC"
        all_attendance = conn.execute(query, params).fetchall()

        # At-risk low attendance records
        low_att_records = conn.execute("""
            SELECT a.*, s.name as student_name, s.register_number, s.department, s.phone as student_phone,
                   p.id as parent_id, p.name as parent_name, p.phone as parent_phone
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            LEFT JOIN parents p ON p.student_id = s.id
            WHERE a.attendance_pct < ? AND a.classes_held > 0
            ORDER BY a.attendance_pct ASC
        """, (threshold,)).fetchall()

        # Recent history logs
        recent_logs = conn.execute("""
            SELECT l.*, s.name as student_name, s.register_number
            FROM attendance_logs l
            JOIN students s ON l.student_id = s.id
            ORDER BY l.date DESC, l.id DESC LIMIT 30
        """).fetchall()

        # Courses for filtering
        courses = conn.execute("SELECT * FROM courses ORDER BY course_code ASC").fetchall()

        # Statistics
        total_students = conn.execute("SELECT COUNT(*) as cnt FROM students WHERE (status = 'ACTIVE' OR status IS NULL)").fetchone()['cnt']
        avg_att_row = conn.execute("SELECT AVG(attendance_pct) as a FROM attendance WHERE classes_held > 0").fetchone()
        avg_att = round(avg_att_row['a'], 1) if avg_att_row and avg_att_row['a'] else 0.0

        return render_template(
            'admin/attendance.html',
            admin=admin,
            all_attendance=all_attendance,
            low_att_records=low_att_records,
            recent_logs=recent_logs,
            courses=courses,
            threshold=threshold,
            avg_att=avg_att,
            total_students=total_students,
            search_query=search_query,
            selected_course=selected_course,
            status_filter=status_filter,
            active_page='attendance'
        )
    finally:
        conn.close()


@admin_bp.route('/admin/attendance/send-warning/<int:student_id>', methods=['POST'])
@admin_required
def admin_attendance_send_warning(admin, student_id):
    conn = get_db_connection()
    try:
        threshold = float(get_system_setting('attendance_threshold', '75.0'))
        student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if not student:
            flash("Student not found.", "error")
            return redirect(url_for('admin.admin_attendance'))

        low_courses = conn.execute("""
            SELECT * FROM attendance WHERE student_id = ? AND attendance_pct < ? AND classes_held > 0
        """, (student_id, threshold)).fetchall()

        course_names = ", ".join(f"{c['subject_name']} ({c['attendance_pct']}%)" for c in low_courses) or "General"

        notify_student(
            student_id,
            "Official Attendance Warning Notice",
            f"Institutional warning: Your attendance in {course_names} is below the {threshold}% minimum threshold. Please meet your faculty advisor immediately.",
            category='Attendance', priority='Critical', db_conn=conn
        )

        parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (student_id,)).fetchone()
        if parent:
            notify_parent(
                parent['id'],
                f"Official Attendance Notice: {student['name']}",
                f"Urgent advisory: Your ward {student['name']}'s attendance in {course_names} is below the required {threshold}% threshold.",
                category='Attendance', priority='Critical', db_conn=conn
            )

        log_activity(admin['name'], 'admin', 'DISPATCH_ATTENDANCE_WARNING', f"Dispatched official low attendance warning to {student['name']} ({student['register_number']})", record_id=str(student_id))
        flash(f"Official attendance warning dispatched to {student['name']} and guardian.", "success")
        return redirect(url_for('admin.admin_attendance'))
    finally:
        conn.close()


@admin_bp.route('/admin/attendance/correct', methods=['POST'])
@admin_required
def admin_attendance_correct(admin):
    student_id = int(request.form.get('student_id'))
    course_code = request.form.get('course_code')
    date_val = request.form.get('date')
    new_status = request.form.get('status', 'Present').strip()

    conn = get_db_connection()
    try:
        course = conn.execute("SELECT course_name FROM courses WHERE course_code = ?", (course_code,)).fetchone()
        course_name = course['course_name'] if course else course_code
        student = conn.execute("SELECT name, register_number FROM students WHERE id = ?", (student_id,)).fetchone()

        held, att, miss, pct = AttendanceModel.record_student_attendance(
            conn, student_id, course_code, course_name, date_val, new_status, topic='Admin Attendance Correction', faculty_id=1
        )
        conn.commit()

        log_activity(admin['name'], 'admin', 'CORRECT_ATTENDANCE', f"Corrected attendance for {student['name']} ({course_code} on {date_val}) to {new_status}. New %: {pct}%", record_id=str(student_id))
        flash(f"Attendance for {student['name']} on {date_val} ({course_code}) corrected to {new_status}. New attendance: {pct}%.", "success")
        return redirect(url_for('admin.admin_attendance'))
    except Exception as e:
        conn.rollback()
        flash(f"Error correcting attendance: {e}", "error")
        return redirect(url_for('admin.admin_attendance'))
    finally:
        conn.close()

