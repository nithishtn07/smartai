"""
CampusGuard AI — Emergency Response Routes & REST API Blueprint
Enterprise emergency control, real-time dispatch, multi-role incident dossier, and analytics.
"""

import json
import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, abort
from database.db import get_db_connection
from services.emergency_service import (
    create_emergency,
    transition_emergency_status,
    assign_responder,
    add_incident_note,
    calculate_response_times,
    get_emergency_full_dossier
)
from services.ai_emergency_service import classify_emergency_text
from services.safety_intelligence import CONFIGURED_ZONES, calculate_location_risk_scores

emergency_bp = Blueprint('emergency', __name__)


# ---------------------------------------------------------------------------
# Helper: Session User Identity Extractor
# ---------------------------------------------------------------------------
def _get_current_actor():
    user_role = session.get('user_role', 'anonymous')
    user_id = session.get(f'{user_role}_id', 1)
    
    conn = get_db_connection()
    try:
        actor_name = "Campus User"
        if user_role == 'student':
            row = conn.execute("SELECT name, phone FROM students WHERE id = ?", (user_id,)).fetchone()
            if row:
                actor_name = row['name']
        elif user_role == 'faculty':
            row = conn.execute("SELECT name, phone FROM faculties WHERE id = ?", (user_id,)).fetchone()
            if row:
                actor_name = row['name']
        elif user_role == 'parent':
            row = conn.execute("SELECT name, phone, student_id FROM parents WHERE id = ?", (user_id,)).fetchone()
            if row:
                actor_name = row['name']
        elif user_role == 'admin':
            row = conn.execute("SELECT name FROM admins WHERE id = ?", (user_id,)).fetchone()
            if row:
                actor_name = row['name']
        elif user_role == 'security':
            actor_name = "Security Officer"

        return {'id': user_id, 'role': user_role, 'name': actor_name}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1. API: Create Emergency / Trigger SOS
# ---------------------------------------------------------------------------
@emergency_bp.route('/api/emergency/create', methods=['POST'])
def api_emergency_create():
    actor = _get_current_actor()
    data = request.get_json() if request.is_json else request.form

    category = data.get('category', 'Personal Safety')
    severity = data.get('severity', 'HIGH').upper()
    description = data.get('description', '')
    campus_zone = data.get('campus_zone', data.get('location', 'Main Academic Block'))
    building = data.get('building', '')
    floor = data.get('floor', '')
    room = data.get('room', '')
    
    lat = None
    lng = None
    acc = None
    try:
        if data.get('latitude'): lat = float(data.get('latitude'))
        if data.get('longitude'): lng = float(data.get('longitude'))
        if data.get('accuracy'): acc = float(data.get('accuracy'))
    except (ValueError, TypeError):
        pass

    result = create_emergency(
        reporter_id=actor['id'],
        reporter_name=actor['name'],
        reporter_role=actor['role'],
        category=category,
        severity=severity,
        description=description,
        latitude=lat,
        longitude=lng,
        location_accuracy=acc,
        campus_zone=campus_zone,
        building=building,
        floor=floor,
        room=room
    )

    if request.is_json:
        return jsonify(result)
    
    flash(f"EMERGENCY ACTIVATED ({result['emergency']['emergency_id']}): Campus Security and Response Team alerted.", "danger")
    return redirect(url_for('student.student_emergency'))


# ---------------------------------------------------------------------------
# 2. API: Get Emergency Details & Scoped Authorization
# ---------------------------------------------------------------------------
@emergency_bp.route('/api/emergency/<emergency_id>', methods=['GET'])
def api_emergency_get(emergency_id):
    actor = _get_current_actor()
    dossier = get_emergency_full_dossier(emergency_id)
    if not dossier:
        return jsonify({'status': 'error', 'message': 'Emergency not found'}), 404

    emg = dossier['emergency']

    # Security Isolation: Student can only view own emergency
    if actor['role'] == 'student' and emg['user_id'] != actor['id'] and emg['user_role'] == 'student':
        return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 403

    # Security Isolation: Parent can only view linked ward emergency
    if actor['role'] == 'parent':
        conn = get_db_connection()
        par = conn.execute("SELECT student_id FROM parents WHERE id = ?", (actor['id'],)).fetchone()
        conn.close()
        if not par or par['student_id'] != emg['user_id']:
            return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 403

    return jsonify({'status': 'success', 'dossier': dossier})


# ---------------------------------------------------------------------------
# 3. API: Get My Active Emergency
# ---------------------------------------------------------------------------
@emergency_bp.route('/api/emergency/my-active', methods=['GET'])
def api_emergency_my_active():
    actor = _get_current_actor()
    conn = get_db_connection()
    try:
        active = conn.execute("""
            SELECT * FROM emergencies 
            WHERE user_id = ? AND user_role = ? AND status != 'RESOLVED' AND status != 'CLOSED' AND status != 'CANCELLED'
            ORDER BY created_at DESC LIMIT 1
        """, (actor['id'], actor['role'])).fetchone()

        if not active:
            return jsonify({'status': 'none', 'active': None})
        
        dossier = get_emergency_full_dossier(active['emergency_id'], conn)
        return jsonify({'status': 'active', 'dossier': dossier})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 4. State Machine Transition APIs (Role Guarded)
# ---------------------------------------------------------------------------
@emergency_bp.route('/api/emergency/<emergency_id>/acknowledge', methods=['POST'])
def api_emergency_acknowledge(emergency_id):
    actor = _get_current_actor()
    if actor['role'] not in ['admin', 'security', 'faculty']:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.get_json() if request.is_json else request.form
    notes = data.get('notes', 'Incident acknowledged by Command Center.')
    res = transition_emergency_status(emergency_id, 'ACKNOWLEDGED', actor['name'], actor['role'], notes)
    return jsonify(res)


@emergency_bp.route('/api/emergency/<emergency_id>/assign', methods=['POST'])
def api_emergency_assign(emergency_id):
    actor = _get_current_actor()
    if actor['role'] not in ['admin', 'security']:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.get_json() if request.is_json else request.form
    responder_name = data.get('responder_name', 'Quick Response Team')
    responder_role = data.get('responder_role', 'Security Officer')
    phone = data.get('phone', '+91 98765 00001')

    res = assign_responder(emergency_id, responder_name, responder_role, phone, actor['name'], actor['role'])
    return jsonify(res)


@emergency_bp.route('/api/emergency/<emergency_id>/en-route', methods=['POST'])
def api_emergency_en_route(emergency_id):
    actor = _get_current_actor()
    if actor['role'] not in ['admin', 'security']:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.get_json() if request.is_json else request.form
    notes = data.get('notes', 'Responder is en route to incident coordinates.')
    res = transition_emergency_status(emergency_id, 'EN_ROUTE', actor['name'], actor['role'], notes)
    return jsonify(res)


@emergency_bp.route('/api/emergency/<emergency_id>/arrived', methods=['POST'])
def api_emergency_arrived(emergency_id):
    actor = _get_current_actor()
    if actor['role'] not in ['admin', 'security']:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.get_json() if request.is_json else request.form
    notes = data.get('notes', 'Responder has arrived on scene.')
    res = transition_emergency_status(emergency_id, 'ON_SCENE', actor['name'], actor['role'], notes)
    return jsonify(res)


@emergency_bp.route('/api/emergency/<emergency_id>/resolve', methods=['POST'])
def api_emergency_resolve(emergency_id):
    actor = _get_current_actor()
    if actor['role'] not in ['admin', 'security']:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.get_json() if request.is_json else request.form
    notes = data.get('notes', 'Emergency condition neutralized. Safety confirmed.')
    res = transition_emergency_status(emergency_id, 'RESOLVED', actor['name'], actor['role'], notes)
    return jsonify(res)


@emergency_bp.route('/api/emergency/<emergency_id>/close', methods=['POST'])
def api_emergency_close(emergency_id):
    actor = _get_current_actor()
    if actor['role'] not in ['admin', 'security']:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.get_json() if request.is_json else request.form
    notes = data.get('notes', 'Incident formally closed and archived to audit repository.')
    res = transition_emergency_status(emergency_id, 'CLOSED', actor['name'], actor['role'], notes)
    return jsonify(res)


@emergency_bp.route('/api/emergency/<emergency_id>/notes', methods=['POST'])
def api_emergency_notes(emergency_id):
    actor = _get_current_actor()
    data = request.get_json() if request.is_json else request.form
    note_text = data.get('note_text', data.get('note', '')).strip()
    if not note_text:
        return jsonify({'status': 'error', 'message': 'Note cannot be empty'}), 400

    res = add_incident_note(emergency_id, actor['id'], actor['name'], actor['role'], note_text)
    return jsonify(res)


# ---------------------------------------------------------------------------
# 5. API: Active Emergencies Stream for Command Center
# ---------------------------------------------------------------------------
@emergency_bp.route('/api/emergency/active', methods=['GET'])
def api_emergency_active():
    conn = get_db_connection()
    try:
        actives = conn.execute("""
            SELECT e.*, s.register_number 
            FROM emergencies e
            LEFT JOIN students s ON (e.user_id = s.id AND e.user_role = 'student')
            WHERE e.status != 'RESOLVED' AND e.status != 'CLOSED' AND e.status != 'CANCELLED'
            ORDER BY e.priority_score DESC, e.created_at DESC
        """).fetchall()

        results = []
        for a in actives:
            d = dict(a)
            d['metrics'] = calculate_response_times(d)
            results.append(d)

        return jsonify({'status': 'success', 'count': len(results), 'emergencies': results})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 6. API: Real-time AI NLP Classification Suggestion
# ---------------------------------------------------------------------------
@emergency_bp.route('/api/emergency/classify', methods=['POST'])
def api_emergency_classify():
    data = request.get_json() or {}
    text = data.get('description', '')
    location = data.get('location', '')
    category_hint = data.get('category', '')
    res = classify_emergency_text(text, location, category_hint)
    return jsonify(res)


# ---------------------------------------------------------------------------
# 7. Dedicated Web View: Comprehensive Incident Dossier
# ---------------------------------------------------------------------------
@emergency_bp.route('/emergency/incident/<emergency_id>', methods=['GET'])
def emergency_incident_dossier(emergency_id):
    actor = _get_current_actor()
    dossier = get_emergency_full_dossier(emergency_id)
    if not dossier:
        flash(f"Emergency dossier '{emergency_id}' not found.", "error")
        return redirect(url_for('admin.admin_safety'))

    emg = dossier['emergency']

    # Security check
    if actor['role'] == 'student' and emg['user_id'] != actor['id'] and emg['user_role'] == 'student':
        abort(403)
    if actor['role'] == 'parent':
        conn = get_db_connection()
        par = conn.execute("SELECT student_id FROM parents WHERE id = ?", (actor['id'],)).fetchone()
        conn.close()
        if not par or par['student_id'] != emg['user_id']:
            abort(403)

    return render_template(
        'emergency/incident_details.html',
        dossier=dossier,
        emergency=emg,
        responders=dossier['responders'],
        notes=dossier['notes'],
        audit_logs=dossier['audit_logs'],
        metrics=dossier['metrics'],
        actor=actor,
        configured_zones=CONFIGURED_ZONES
    )


# ---------------------------------------------------------------------------
# 8. Dedicated Web View: Emergency Incident Archive & Search
# ---------------------------------------------------------------------------
@emergency_bp.route('/emergency/history', methods=['GET'])
def emergency_history():
    actor = _get_current_actor()
    q_category = request.args.get('category', '')
    q_severity = request.args.get('severity', '')
    q_status = request.args.get('status', '')
    q_search = request.args.get('q', '').strip()

    conn = get_db_connection()
    try:
        query = "SELECT * FROM emergencies WHERE 1=1"
        params = []

        if actor['role'] == 'student':
            query += " AND user_id = ? AND user_role = 'student'"
            params.append(actor['id'])
        elif actor['role'] == 'parent':
            par = conn.execute("SELECT student_id FROM parents WHERE id = ?", (actor['id'],)).fetchone()
            stu_id = par['student_id'] if par else -1
            query += " AND user_id = ? AND user_role = 'student'"
            params.append(stu_id)

        if q_category:
            query += " AND category = ?"
            params.append(q_category)
        if q_severity:
            query += " AND severity = ?"
            params.append(q_severity)
        if q_status:
            query += " AND status = ?"
            params.append(q_status)
        if q_search:
            query += " AND (emergency_id LIKE ? OR reporter_name LIKE ? OR description LIKE ? OR campus_zone LIKE ?)"
            params.extend([f"%{q_search}%"] * 4)

        query += " ORDER BY created_at DESC LIMIT 100"
        emergencies = conn.execute(query, tuple(params)).fetchall()

        return render_template(
            'emergency/history.html',
            emergencies=emergencies,
            actor=actor,
            q_category=q_category,
            q_severity=q_severity,
            q_status=q_status,
            q_search=q_search,
            configured_zones=CONFIGURED_ZONES
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 9. Dedicated Web View: Safety Analytics & Heatmap
# ---------------------------------------------------------------------------
@emergency_bp.route('/emergency/analytics', methods=['GET'])
def emergency_analytics():
    actor = _get_current_actor()
    conn = get_db_connection()
    try:
        all_emgs = conn.execute("SELECT * FROM emergencies ORDER BY created_at DESC").fetchall()
        complaints = conn.execute("SELECT * FROM complaints").fetchall()
        incidents = conn.execute("SELECT * FROM incidents").fetchall()

        zone_scores = calculate_location_risk_scores(incidents, complaints)

        total_count = len(all_emgs)
        critical_count = sum(1 for e in all_emgs if e['severity'] == 'CRITICAL')
        resolved_count = sum(1 for e in all_emgs if e['status'] in ['RESOLVED', 'CLOSED'])
        resolution_rate = round((resolved_count / total_count * 100), 1) if total_count > 0 else 100.0

        # Category breakdown
        cat_counts = {}
        for e in all_emgs:
            c = e['category'] or 'Other'
            cat_counts[c] = cat_counts.get(c, 0) + 1

        # Zone frequency breakdown
        zone_counts = {}
        for e in all_emgs:
            z = e['campus_zone'] or 'Campus Grounds'
            zone_counts[z] = zone_counts.get(z, 0) + 1

        return render_template(
            'emergency/analytics.html',
            actor=actor,
            total_count=total_count,
            critical_count=critical_count,
            resolved_count=resolved_count,
            resolution_rate=resolution_rate,
            cat_counts=cat_counts,
            zone_counts=zone_counts,
            zone_scores=zone_scores,
            configured_zones=CONFIGURED_ZONES
        )
    finally:
        conn.close()
