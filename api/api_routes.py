"""
CampusGuard AI — Centralized REST API Endpoints
"""

import datetime
import uuid
from flask import Blueprint, request, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash
from database.db import get_db_connection
from services.ai_insight_engine import (
    evaluate_attendance_risk,
    evaluate_academic_risk,
    evaluate_fee_alerts,
    evaluate_exam_reminders,
    evaluate_assignment_alerts,
    generate_student_insights_summary,
    generate_admin_campus_risk_overview
)
from services.notification_service import (
    notify_student,
    notify_parent,
    notify_faculty,
    notify_admin,
    create_notification,
    broadcast_announcement,
    log_activity
)

api_bp = Blueprint('api', __name__)


# ---------------------------------------------------------------------------
# 1. Auth REST API
# ---------------------------------------------------------------------------
@api_bp.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    data = request.get_json() or {}
    role = data.get('role', 'student').lower()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Username and password required'}), 400

    conn = get_db_connection()
    try:
        user = None
        if role == 'student':
            user = conn.execute("SELECT * FROM students WHERE UPPER(register_number) = UPPER(?)", (username,)).fetchone()
            if user and check_password_hash(user['password_hash'], password):
                session['student_id'] = user['id']
                session['user_role'] = 'student'
                return jsonify({'status': 'success', 'role': 'student', 'user_id': user['id'], 'name': user['name'], 'register_number': user['register_number']})

        elif role == 'parent':
            user = conn.execute("SELECT * FROM parents WHERE LOWER(email) = LOWER(?) OR UPPER(parent_id) = UPPER(?)", (username, username)).fetchone()
            if user and check_password_hash(user['password_hash'], password):
                session['parent_id'] = user['id']
                session['user_role'] = 'parent'
                return jsonify({'status': 'success', 'role': 'parent', 'user_id': user['id'], 'name': user['name'], 'student_id': user['student_id']})

        elif role == 'faculty':
            user = conn.execute("SELECT * FROM faculties WHERE LOWER(email) = LOWER(?) OR UPPER(faculty_id) = UPPER(?)", (username, username)).fetchone()
            if user and check_password_hash(user['password_hash'], password):
                session['faculty_id'] = user['id']
                session['user_role'] = 'faculty'
                return jsonify({'status': 'success', 'role': 'faculty', 'user_id': user['id'], 'name': user['name'], 'department': user['department']})

        elif role == 'admin':
            user = conn.execute("SELECT * FROM admins WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)", (username, username)).fetchone()
            if user and check_password_hash(user['password_hash'], password):
                session['admin_id'] = user['id']
                session['user_role'] = 'admin'
                return jsonify({'status': 'success', 'role': 'admin', 'user_id': user['id'], 'name': user['name'], 'admin_role': user['role']})

        return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401
    finally:
        conn.close()


@api_bp.route('/api/auth/session', methods=['GET'])
def api_auth_session():
    role = session.get('user_role')
    if not role:
        return jsonify({'authenticated': False})
    return jsonify({
        'authenticated': True,
        'role': role,
        'student_id': session.get('student_id'),
        'parent_id': session.get('parent_id'),
        'faculty_id': session.get('faculty_id'),
        'admin_id': session.get('admin_id')
    })


@api_bp.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    session.clear()
    return jsonify({'status': 'success', 'message': 'Logged out successfully'})


# ---------------------------------------------------------------------------
# 2. Students REST API
# ---------------------------------------------------------------------------
@api_bp.route('/api/students', methods=['GET'])
def api_students_list():
    user_role = session.get('user_role')
    if not user_role or user_role not in ('admin', 'faculty'):
        return jsonify({'status': 'error', 'message': 'Admin or Faculty authorization required'}), 403

    dept = request.args.get('department')
    search = request.args.get('search')
    conn = get_db_connection()
    try:
        query = "SELECT id, name, register_number, email, department, year, semester, section, cgpa, phone, status FROM students WHERE 1=1"
        params = []
        if dept and dept != 'All':
            query += " AND department = ?"
            params.append(dept)
        if search:
            query += " AND (name LIKE ? OR register_number LIKE ?)"
            q = f"%{search}%"
            params.extend([q, q])
        query += " ORDER BY register_number ASC"
        students = conn.execute(query, params).fetchall()
        return jsonify({'status': 'success', 'count': len(students), 'students': [dict(s) for s in students]})
    finally:
        conn.close()


@api_bp.route('/api/students/<int:id>', methods=['GET'])
def api_student_detail(id):
    user_role = session.get('user_role')
    if not user_role:
        return jsonify({'status': 'error', 'message': 'Authentication required'}), 401
    
    # IDOR protection: Students can only view themselves; Parents can only view their linked child
    if user_role == 'student' and session.get('student_id') != id:
        return jsonify({'status': 'error', 'message': 'Access forbidden: you may only view your own record'}), 403

    conn = get_db_connection()
    try:
        if user_role == 'parent':
            linked = conn.execute("SELECT student_id FROM parents WHERE id = ?", (session.get('parent_id'),)).fetchone()
            if not linked or linked['student_id'] != id:
                return jsonify({'status': 'error', 'message': 'Access forbidden: student not linked to this parent account'}), 403

        student = conn.execute("SELECT id, name, register_number, email, department, year, semester, section, cgpa, sgpa, phone, parent_name, parent_phone, address, status FROM students WHERE id = ?", (id,)).fetchone()
        if not student:
            return jsonify({'status': 'error', 'message': 'Student not found'}), 404
        return jsonify({'status': 'success', 'student': dict(student)})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 3. Attendance REST API
# ---------------------------------------------------------------------------
@api_bp.route('/api/attendance/summary/<int:student_id>', methods=['GET'])
def api_attendance_summary(student_id):
    user_role = session.get('user_role')
    if user_role == 'student' and session.get('student_id') != student_id:
        return jsonify({'status': 'error', 'message': 'Access forbidden'}), 403

    conn = get_db_connection()
    try:
        records = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (student_id,)).fetchall()
        risk = evaluate_attendance_risk(student_id, conn)
        return jsonify({
            'status': 'success',
            'student_id': student_id,
            'records': [dict(r) for r in records],
            'risk_evaluation': risk
        })
    finally:
        conn.close()


@api_bp.route('/api/attendance/mark', methods=['POST'])
def api_attendance_mark():
    user_role = session.get('user_role')
    if user_role and user_role not in ('faculty', 'admin'):
        return jsonify({'status': 'error', 'message': 'Faculty or Admin authorization required to mark attendance'}), 403

    data = request.get_json() or {}
    student_id = data.get('student_id')
    course_code = data.get('course_code')
    status = data.get('status', 'Present')
    date_val = data.get('date', datetime.date.today().strftime('%Y-%m-%d'))
    topic = data.get('topic', 'API Attendance Sync')

    if not student_id or not course_code:
        return jsonify({'status': 'error', 'message': 'student_id and course_code required'}), 400

    conn = get_db_connection()
    try:
        course = conn.execute("SELECT * FROM courses WHERE course_code = ?", (course_code,)).fetchone()
        course_name = course['course_name'] if course else course_code

        # Log entry
        conn.execute("""
            INSERT INTO attendance_logs (student_id, course_code, course_name, date, status, topic)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (student_id, course_code, course_name, date_val, status, topic))

        # Aggregate update
        existing = conn.execute("SELECT * FROM attendance WHERE student_id = ? AND subject_code = ?", (student_id, course_code)).fetchone()
        is_present = (status.lower() == 'present')

        if existing:
            held = existing['classes_held'] + 1
            att = existing['classes_attended'] + (1 if is_present else 0)
            miss = existing['classes_missed'] + (0 if is_present else 1)
            pct = round((att / held) * 100.0, 1)
            conn.execute("""
                UPDATE attendance SET classes_held = ?, classes_attended = ?, classes_missed = ?, attendance_pct = ?
                WHERE id = ?
            """, (held, att, miss, pct, existing['id']))
        else:
            held = 1
            att = 1 if is_present else 0
            miss = 0 if is_present else 1
            pct = 100.0 if is_present else 0.0
            conn.execute("""
                INSERT INTO attendance (student_id, subject_code, subject_name, classes_held, classes_attended, classes_missed, attendance_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (student_id, course_code, course_name, held, att, miss, pct))

        conn.commit()
        return jsonify({'status': 'success', 'message': 'Attendance marked successfully', 'new_percentage': pct})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 4. Marks REST API
# ---------------------------------------------------------------------------
@api_bp.route('/api/marks/student/<int:student_id>', methods=['GET'])
def api_marks_student(student_id):
    conn = get_db_connection()
    try:
        marks = conn.execute("SELECT * FROM marks WHERE student_id = ?", (student_id,)).fetchall()
        acad_risk = evaluate_academic_risk(student_id, conn)
        return jsonify({
            'status': 'success',
            'student_id': student_id,
            'marks': [dict(m) for m in marks],
            'academic_risk': acad_risk
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 5. Fees REST API
# ---------------------------------------------------------------------------
@api_bp.route('/api/fees/student/<int:student_id>', methods=['GET'])
def api_fees_student(student_id):
    conn = get_db_connection()
    try:
        fees = conn.execute("SELECT * FROM fees WHERE student_id = ?", (student_id,)).fetchall()
        fee_eval = evaluate_fee_alerts(student_id, conn)
        return jsonify({
            'status': 'success',
            'student_id': student_id,
            'fees': [dict(f) for f in fees],
            'fee_evaluation': fee_eval
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 6. Safety & SOS REST API
# ---------------------------------------------------------------------------
@api_bp.route('/api/sos/trigger', methods=['POST'])
def api_sos_trigger():
    data = request.get_json() or {}
    student_id = data.get('student_id') or session.get('student_id', 1)
    location = data.get('location', 'Campus Quad (API Dispatch)')
    lat = data.get('latitude', 12.9716)
    lon = data.get('longitude', 77.5946)
    note = data.get('note', 'Emergency SOS beacon triggered via REST API')

    inc_id = f"SOS{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO incidents (incident_id, student_id, incident_type, location, latitude, longitude, description, status)
            VALUES (?, ?, 'EMERGENCY_SOS', ?, ?, ?, ?, 'ACTIVE')
        """, (inc_id, student_id, location, float(lat), float(lon), note))
        conn.commit()

        notify_admin(f"CRITICAL: SOS Distress from Student {student_id}", f"Location: {location}", category='Safety', priority='Critical')
        return jsonify({'status': 'success', 'incident_id': inc_id, 'message': 'Distress beacon activated and campus QRT notified.'})
    finally:
        conn.close()


@api_bp.route('/api/sos/status', methods=['GET'])
def api_sos_status():
    conn = get_db_connection()
    try:
        active = conn.execute("""
            SELECT i.*, s.name as student_name, s.phone as student_phone
            FROM incidents i
            LEFT JOIN students s ON i.student_id = s.id
            WHERE i.incident_type = 'EMERGENCY_SOS' AND i.status != 'RESOLVED' AND i.status != 'CANCELLED'
            ORDER BY i.created_at DESC
        """).fetchall()
        return jsonify({'status': 'success', 'active_count': len(active), 'active_emergencies': [dict(a) for a in active]})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 7. AI Insight Engine REST API
# ---------------------------------------------------------------------------
@api_bp.route('/api/ai/insights/<int:student_id>', methods=['GET'])
def api_ai_student_insights(student_id):
    conn = get_db_connection()
    try:
        summary = generate_student_insights_summary(student_id, conn)
        return jsonify({'status': 'success', 'insights': summary})
    finally:
        conn.close()


@api_bp.route('/api/ai/campus-risk', methods=['GET'])
def api_ai_campus_risk():
    conn = get_db_connection()
    try:
        overview = generate_admin_campus_risk_overview(conn)
        return jsonify({'status': 'success', 'campus_risk_overview': overview})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 8. Notifications & Global Search API (Preserved Endpoints)
# ---------------------------------------------------------------------------
@api_bp.route('/api/notifications/unread-count')
def api_notifications_unread_count():
    conn = get_db_connection()
    try:
        user_role = session.get('user_role')
        if not user_role:
            if 'student_id' in session: user_role = 'student'
            elif 'parent_id' in session: user_role = 'parent'
            elif 'faculty_id' in session: user_role = 'faculty'
            elif 'admin_id' in session: user_role = 'admin'
            else: user_role = 'student'

        user_id = session.get(f'{user_role}_id') or session.get('user_id', 1)

        count = conn.execute("""
            SELECT COUNT(*) as cnt FROM notifications 
            WHERE recipient_role = ? AND recipient_id = ? AND is_read = 0
        """, (user_role, user_id)).fetchone()['cnt']

        return jsonify({'unread_count': count, 'count': count, 'role': user_role})
    finally:
        conn.close()


@api_bp.route('/api/notifications/recent')
def api_notifications_recent():
    conn = get_db_connection()
    try:
        user_role = session.get('user_role')
        if not user_role:
            if 'student_id' in session: user_role = 'student'
            elif 'parent_id' in session: user_role = 'parent'
            elif 'faculty_id' in session: user_role = 'faculty'
            elif 'admin_id' in session: user_role = 'admin'
            else: user_role = 'student'

        user_id = session.get(f'{user_role}_id') or session.get('user_id', 1)

        notifs = conn.execute("""
            SELECT * FROM notifications 
            WHERE recipient_role = ? AND recipient_id = ?
            ORDER BY created_at DESC, id DESC LIMIT 8
        """, (user_role, user_id)).fetchall()

        return jsonify({'notifications': [dict(n) for n in notifs]})
    finally:
        conn.close()


@api_bp.route('/api/notifications/mark-read/<int:notif_id>', methods=['POST'])
def api_notifications_mark_read(notif_id):
    conn = get_db_connection()
    try:
        user_role = session.get('user_role')
        if not user_role:
            if 'student_id' in session: user_role = 'student'
            elif 'parent_id' in session: user_role = 'parent'
            elif 'faculty_id' in session: user_role = 'faculty'
            elif 'admin_id' in session: user_role = 'admin'
            else: user_role = 'student'

        user_id = session.get(f'{user_role}_id') or session.get('user_id', 1)

        conn.execute("""
            UPDATE notifications SET is_read = 1 
            WHERE id = ? AND recipient_role = ? AND recipient_id = ?
        """, (notif_id, user_role, user_id))
        conn.commit()
        return jsonify({'status': 'ok', 'message': 'Marked as read'})
    finally:
        conn.close()


@api_bp.route('/api/notifications/mark-all-read', methods=['POST'])
def api_notifications_mark_all_read():
    conn = get_db_connection()
    try:
        user_role = session.get('user_role')
        if not user_role:
            if 'student_id' in session: user_role = 'student'
            elif 'parent_id' in session: user_role = 'parent'
            elif 'faculty_id' in session: user_role = 'faculty'
            elif 'admin_id' in session: user_role = 'admin'
            else: user_role = 'student'

        user_id = session.get(f'{user_role}_id') or session.get('user_id', 1)
        conn.execute("UPDATE notifications SET is_read = 1 WHERE recipient_role = ? AND recipient_id = ?", (user_role, user_id))
        conn.commit()
        return jsonify({'status': 'ok', 'message': 'All notifications marked as read'})
    finally:
        conn.close()


@api_bp.route('/api/global-search')
def api_global_search():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'results': []})

    conn = get_db_connection()
    try:
        results = []
        students = conn.execute("SELECT id, name, register_number FROM students WHERE name LIKE ? OR register_number LIKE ? LIMIT 5", (f"%{q}%", f"%{q}%")).fetchall()
        for s in students:
            results.append({'type': 'Student', 'title': s['name'], 'subtitle': s['register_number'], 'url': f"/admin/students/view/{s['id']}"})

        courses = conn.execute("SELECT course_code, course_name FROM courses WHERE course_code LIKE ? OR course_name LIKE ? LIMIT 5", (f"%{q}%", f"%{q}%")).fetchall()
        for c in courses:
            results.append({'type': 'Course', 'title': c['course_name'], 'subtitle': c['course_code'], 'url': '/faculty/subjects'})

        return jsonify({'results': results})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 9. Admin Stats API
# ---------------------------------------------------------------------------
@api_bp.route('/api/admin/stats', methods=['GET'])
def api_admin_stats():
    conn = get_db_connection()
    try:
        total_students = conn.execute("SELECT COUNT(*) as cnt FROM students").fetchone()['cnt']
        total_faculty = conn.execute("SELECT COUNT(*) as cnt FROM faculties").fetchone()['cnt']
        total_parents = conn.execute("SELECT COUNT(*) as cnt FROM parents").fetchone()['cnt']
        total_courses = conn.execute("SELECT COUNT(*) as cnt FROM courses").fetchone()['cnt']
        active_sos_emg = conn.execute("SELECT COUNT(*) as cnt FROM emergencies WHERE status IN ('TRIGGERED', 'ACKNOWLEDGED', 'ASSIGNED', 'RESPONDER_ASSIGNED', 'EN_ROUTE', 'ON_SCENE', 'ACTIVE', 'RESPONDING')").fetchone()['cnt']
        active_sos_inc = conn.execute("SELECT COUNT(*) as cnt FROM incidents WHERE incident_type = 'EMERGENCY_SOS' AND status = 'ACTIVE'").fetchone()['cnt']
        active_sos = max(active_sos_emg, active_sos_inc)

        return jsonify({
            'status': 'success',
            'stats': {
                'total_students': total_students,
                'total_faculty': total_faculty,
                'total_parents': total_parents,
                'total_courses': total_courses,
                'active_sos_count': active_sos
            }
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 10. Swagger Documentation & Enterprise REST API v1
# ---------------------------------------------------------------------------
from flask import render_template
from .swagger_spec import get_openapi_spec
from services.predictive_ml_engine import evaluate_student_predictive_risk, evaluate_cohort_predictive_risk
from services.qr_attendance_service import verify_student_qr_scan, generate_qr_attendance_token
from services.rag_knowledge_engine import search_campus_knowledge
from services.cctv_vision_service import get_all_campus_cctv_telemetry
from utils.rate_limiter import rate_limit


@api_bp.route('/api/docs')
def api_docs_page():
    """Renders interactive Swagger UI documentation explorer."""
    return render_template('api_docs.html')


@api_bp.route('/api/swagger.json')
def api_swagger_json():
    """Returns OpenAPI 3.0.0 JSON specification."""
    return jsonify(get_openapi_spec())


@api_bp.route('/api/v1/predictive-risk', methods=['GET'])
@rate_limit(max_requests=30, window_seconds=60)
def api_predictive_risk():
    """Computes academic & retention risk index for authenticated student or cohort."""
    student_id = session.get('student_id') or request.args.get('student_id', type=int)
    conn = get_db_connection()
    try:
        if student_id:
            result = evaluate_student_predictive_risk(student_id, conn)
            return jsonify({'status': 'success', 'data': result})
        
        # Admin / Faculty cohort query
        dept = request.args.get('department')
        year = request.args.get('year', type=int)
        cohort_results = evaluate_cohort_predictive_risk(conn, department=dept, year=year)
        return jsonify({'status': 'success', 'cohort_count': len(cohort_results), 'data': cohort_results})
    finally:
        conn.close()


@api_bp.route('/api/v1/qr-attendance', methods=['POST'])
@rate_limit(max_requests=20, window_seconds=60)
def api_qr_attendance_verify():
    """Validates student scan of dynamic 15-second rotating QR attendance token."""
    data = request.get_json() or {}
    token = data.get('token', '').strip()
    student_id = session.get('student_id') or data.get('student_id', 1)
    lat = data.get('latitude', type=float)
    lon = data.get('longitude', type=float)

    if not token:
        return jsonify({'status': 'error', 'message': 'Attendance token is required'}), 400

    result = verify_student_qr_scan(token, student_id=student_id, student_lat=lat, student_lon=lon)
    status_code = 200 if result.get('success') else 400
    return jsonify(result), status_code


@api_bp.route('/api/v1/knowledge-search', methods=['GET'])
@rate_limit(max_requests=30, window_seconds=60)
def api_knowledge_search():
    """Performs semantic RAG search across institutional policies."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'status': 'error', 'message': 'Search query parameter (q) required'}), 400

    docs = search_campus_knowledge(query, top_k=3)
    return jsonify({
        'status': 'success',
        'query': query,
        'matched_count': len(docs),
        'results': docs
    })


@api_bp.route('/api/v1/cctv-telemetry', methods=['GET'])
def api_cctv_telemetry():
    """Returns synthesized optical CCTV camera telemetry for security dashboard."""
    telemetry = get_all_campus_cctv_telemetry()
    return jsonify({
        'status': 'success',
        'active_cameras_count': len(telemetry),
        'telemetry': telemetry
    })

