"""
CampusGuard AI — Central Emergency Response Management Service
Enterprise state machine, responder assignment, response timers, scoped alerts, and audit trail.
"""

import uuid
import datetime
import sqlite3
from typing import Dict, Any, List, Optional
from database.db import get_db_connection
from services.notification_service import notify_parent, notify_student, notify_faculty, notify_admin, emit_event
from services.ai_emergency_service import classify_emergency_text, generate_ai_incident_summary


# ---------------------------------------------------------------------------
# Emergency Valid Status Workflow
# ---------------------------------------------------------------------------
VALID_STATUSES = [
    'TRIGGERED',
    'ACKNOWLEDGED',
    'ASSIGNED',
    'RESPONDER_ASSIGNED',
    'EN_ROUTE',
    'ON_SCENE',
    'RESOLVED',
    'CLOSED',
    'STAND_DOWN',
    'CANCELLED'
]


# Active vs Completed status categories
ACTIVE_EMERGENCY_STATUSES = [
    'TRIGGERED',
    'ACKNOWLEDGED',
    'ASSIGNED',
    'RESPONDER_ASSIGNED',
    'EN_ROUTE',
    'ON_SCENE',
    'ACTIVE',
    'RESPONDING'
]

COMPLETED_EMERGENCY_STATUSES = [
    'RESOLVED',
    'CLOSED',
    'STAND_DOWN',
    'CANCELLED'
]


def generate_emergency_id() -> str:
    """
    Generates a human-readable, unique emergency identifier: EMG-YYYY-XXXXXX.
    """
    now = datetime.datetime.now()
    unique_suffix = uuid.uuid4().hex[:6].upper()
    return f"EMG-{now.year}-{unique_suffix}"


def create_emergency(
    reporter_id: int,
    reporter_name: str,
    reporter_role: str = 'student',
    reporter_phone: str = '',
    category: str = 'Personal Safety',
    emergency_type: str = 'Emergency SOS',
    severity: str = 'HIGH',
    description: str = '',
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    location_accuracy: Optional[float] = None,
    campus_zone: str = 'Main Academic Block',
    building: str = '',
    floor: str = '',
    room: str = '',
    skip_idempotency: bool = False,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Creates a new high-priority emergency incident with idempotency protection,
    records full telemetry, performs non-blocking AI classification suggestion,
    and broadcasts scoped alerts to Security, Admin, linked Parents, and Faculty.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        now_dt = datetime.datetime.now()
        now_str = now_dt.strftime('%Y-%m-%d %H:%M:%S')

        # Idempotency / Duplicate click prevention (same reporter within 8 seconds)
        if not skip_idempotency and reporter_id and reporter_role:
            recent = conn.execute("""
                SELECT * FROM emergencies 
                WHERE user_id = ? AND user_role = ? AND status = 'TRIGGERED'
                ORDER BY created_at DESC LIMIT 1
            """, (reporter_id, reporter_role)).fetchone()

            if recent and recent['created_at']:
                try:
                    rec_time = datetime.datetime.strptime(recent['created_at'][:19], '%Y-%m-%d %H:%M:%S')
                    if (now - rec_time).total_seconds() < 8:
                        return {'status': 'success', 'emergency': dict(recent), 'is_duplicate': True}
                except Exception:
                    pass

        emg_id = generate_emergency_id()

        # Non-blocking AI classification advisory
        loc_str = f"{building} {floor} {room} {campus_zone}".strip()
        ai_meta = classify_emergency_text(description, loc_str, category)
        ai_json = str(ai_meta).replace("'", '"')

        # Composite priority score
        severity_weight = {'CRITICAL': 100, 'HIGH': 80, 'MEDIUM': 50, 'LOW': 30}
        priority_score = severity_weight.get(severity.upper(), 75)

        # 1. Insert into emergencies table
        conn.execute("""
            INSERT INTO emergencies (
                emergency_id, user_id, user_role, reporter_name, reporter_phone,
                emergency_type, category, severity, description,
                latitude, longitude, location_accuracy, campus_zone, building, floor, room,
                status, priority_score, ai_classification, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'TRIGGERED', ?, ?, ?)
        """, (
            emg_id, reporter_id, reporter_role, reporter_name, reporter_phone,
            emergency_type, category, severity, description,
            latitude, longitude, location_accuracy, campus_zone, building, floor, room,
            priority_score, ai_json, now_str
        ))

        # 2. Synchronize legacy incidents table for backwards compatibility
        conn.execute("""
            INSERT INTO incidents (
                incident_id, student_id, incident_type, location, latitude, longitude,
                description, status, priority_score, created_at
            ) VALUES (?, ?, 'EMERGENCY_SOS', ?, ?, ?, ?, 'ACTIVE', ?, ?)
        """, (
            emg_id, reporter_id if reporter_role == 'student' else 1,
            loc_str or campus_zone, latitude or 12.9716, longitude or 77.5946,
            description or f"Emergency SOS ({category} - {severity})", priority_score, now_str
        ))

        # 3. Log initial audit entry
        conn.execute("""
            INSERT INTO emergency_audit_logs (emergency_id, user_name, user_role, action, old_value, new_value, timestamp)
            VALUES (?, ?, ?, 'SOS_TRIGGERED', NULL, 'TRIGGERED', ?)
        """, (emg_id, reporter_name, reporter_role, now_str))

        conn.commit()

        # 4. Multi-portal Scoped Alert Broadcast
        # A. Security & Admin Command Broadcast
        notify_admin(
            title=f"🚨 {severity} EMERGENCY: {category} ({emg_id})",
            message=f"Reported by {reporter_name} ({reporter_role.upper()}) at {loc_str or campus_zone}. Distress Beacon active.",
            category='Safety',
            priority='Critical',
            db_conn=conn
        )

        # B. Linked Parent Alert (if reporter is a student)
        if reporter_role == 'student':
            parent = conn.execute("SELECT * FROM parents WHERE student_id = ?", (reporter_id,)).fetchone()
            if parent:
                parent_msg = (
                    f"CampusGuard Alert: Your ward {reporter_name} activated an emergency alert "
                    f"({category}) at {loc_str or campus_zone}. Campus Rapid Response Team has been notified."
                )
                notify_parent(
                    parent['id'],
                    f"🚨 Emergency Alert for {reporter_name}",
                    parent_msg,
                    category='Emergency',
                    priority='Critical',
                    db_conn=conn
                )
                conn.execute("""
                    INSERT INTO emergency_notifications (
                        emergency_id, recipient_role, recipient_id, recipient_name, notification_type, title, message, status, sent_at
                    ) VALUES (?, 'parent', ?, ?, 'IN_APP', ?, ?, 'SENT', ?)
                """, (emg_id, parent['id'], parent['name'], f"Emergency Alert for {reporter_name}", parent_msg, now_str))
                conn.commit()

        # C. Faculty Advisory Alert (if department/building applicable)
        notify_faculty(
            faculty_id=1,
            title=f"Campus Safety Notice: Incident reported at {campus_zone}",
            message=f"A {category} response is underway near {loc_str or campus_zone}. Security personnel are actively responding.",
            category='Safety',
            priority='High',
            db_conn=conn
        )

        # D. Real-time WebSocket emission
        emit_event('emergency_new', {
            'emergency_id': emg_id,
            'category': category,
            'severity': severity,
            'location': loc_str or campus_zone,
            'reporter_name': reporter_name,
            'created_at': now_str
        })

        emergency_record = conn.execute("SELECT * FROM emergencies WHERE emergency_id = ?", (emg_id,)).fetchone()
        return {'status': 'success', 'emergency': dict(emergency_record), 'is_duplicate': False}

    finally:
        if should_close:
            conn.close()


def transition_emergency_status(
    emergency_id: str,
    new_status: str,
    actor_name: str,
    actor_role: str,
    notes: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Transitions emergency to a new state in the state machine, records timestamp milestones,
    logs audit entries, and dispatches real-time update events.
    """
    if new_status not in VALID_STATUSES:
        return {'status': 'error', 'message': f"Invalid status: '{new_status}'"}

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        emg = conn.execute("SELECT * FROM emergencies WHERE emergency_id = ?", (emergency_id,)).fetchone()
        if not emg:
            return {'status': 'error', 'message': f"Emergency '{emergency_id}' not found."}

        old_status = emg['status']
        now_dt = datetime.datetime.now()
        now_str = now_dt.strftime('%Y-%m-%d %H:%M:%S')

        # Build column update mapping
        updates = ["status = ?"]
        params = [new_status]

        if new_status == 'ACKNOWLEDGED' and not emg['acknowledged_at']:
            updates.append("acknowledged_at = ?")
            params.append(now_str)
        elif new_status in ['ASSIGNED', 'RESPONDER_ASSIGNED'] and not emg['assigned_at']:
            updates.append("assigned_at = ?")
            params.append(now_str)
        elif new_status == 'EN_ROUTE' and not emg['response_started_at']:
            updates.append("response_started_at = ?")
            params.append(now_str)
        elif new_status == 'ON_SCENE' and not emg['arrived_at']:
            updates.append("arrived_at = ?")
            params.append(now_str)
        elif new_status == 'RESOLVED' and not emg['resolved_at']:
            updates.append("resolved_at = ?")
            params.append(now_str)
            # Generate AI resolution summary
            notes_rows = conn.execute("SELECT * FROM emergency_notes WHERE emergency_id = ?", (emergency_id,)).fetchall()
            ai_summary = generate_ai_incident_summary(dict(emg), notes=[dict(n) for n in notes_rows])
            updates.append("resolution_summary = ?")
            params.append(ai_summary)
        elif new_status in ['CLOSED', 'STAND_DOWN', 'CANCELLED'] and not emg['closed_at']:
            updates.append("closed_at = ?")
            params.append(now_str)

        params.append(emergency_id)
        update_query = f"UPDATE emergencies SET {', '.join(updates)} WHERE emergency_id = ?"
        conn.execute(update_query, tuple(params))

        # Synchronize legacy incidents table
        legacy_status_map = {
            'TRIGGERED': 'ACTIVE',
            'ACKNOWLEDGED': 'ACKNOWLEDGED',
            'ASSIGNED': 'RESPONDING',
            'RESPONDER_ASSIGNED': 'RESPONDING',
            'EN_ROUTE': 'RESPONDING',
            'ON_SCENE': 'RESPONDING',
            'RESOLVED': 'RESOLVED',
            'CLOSED': 'RESOLVED',
            'STAND_DOWN': 'CANCELLED',
            'CANCELLED': 'CANCELLED'
        }
        conn.execute("UPDATE incidents SET status = ? WHERE incident_id = ?", (legacy_status_map.get(new_status, 'ACTIVE'), emergency_id))

        # Log audit entry
        conn.execute("""
            INSERT INTO emergency_audit_logs (emergency_id, user_name, user_role, action, old_value, new_value, timestamp)
            VALUES (?, ?, ?, 'STATUS_CHANGE', ?, ?, ?)
        """, (emergency_id, actor_name, actor_role, old_status, new_status, now_str))

        # Add note if provided
        if notes:
            conn.execute("""
                INSERT INTO emergency_notes (emergency_id, author_id, author_name, author_role, note_text, created_at)
                VALUES (?, 1, ?, ?, ?, ?)
            """, (emergency_id, actor_name, actor_role, notes, now_str))

        # Multi-Channel Notifications for Student & Linked Parent
        if emg['user_role'] == 'student' and emg['user_id']:
            student_id = emg['user_id']
            reporter_name = emg['reporter_name'] or 'Student'
            loc_str = emg['campus_zone'] or 'Campus Safe Zone'
            assigned_unit = emg['assigned_responder'] or 'Quick Response Team'

            if new_status == 'ACKNOWLEDGED':
                notify_student(student_id, "🛡️ Emergency Acknowledged", f"Campus Security Command has acknowledged your SOS ({emergency_id}). Response units mobilized.", category="Emergency", priority="High", db_conn=conn)
            elif new_status in ['ASSIGNED', 'RESPONDER_ASSIGNED']:
                notify_student(student_id, "⚡ Response Unit Assigned", f"{assigned_unit} has been dispatched to your coordinates.", category="Emergency", priority="High", db_conn=conn)
            elif new_status == 'EN_ROUTE':
                notify_student(student_id, "🚑 Responder En Route", f"Your assigned responder ({assigned_unit}) is en route to your location. ETA ~4m.", category="Emergency", priority="Critical", db_conn=conn)
            elif new_status == 'ON_SCENE':
                notify_student(student_id, "📍 Responder On Scene", f"{assigned_unit} has arrived at your reported location ({loc_str}).", category="Emergency", priority="Critical", db_conn=conn)
            elif new_status == 'RESOLVED':
                notify_student(student_id, "✓ Emergency Resolved", f"Your emergency ({emergency_id}) has been safely handled and marked as resolved.", category="Emergency", priority="Normal", db_conn=conn)
            elif new_status in ['STAND_DOWN', 'CANCELLED']:
                notify_student(student_id, "🛡️ Stand Down Confirmed (Safe)", f"Emergency distress beacon ({emergency_id}) stood down as false alarm. You are marked SAFE.", category="Emergency", priority="Normal", db_conn=conn)
            elif new_status == 'CLOSED':
                notify_student(student_id, "✓ Emergency Closed", f"Emergency incident ({emergency_id}) has been closed.", category="Emergency", priority="Normal", db_conn=conn)

            # Linked Parent Notifications
            parent = conn.execute("SELECT id, name FROM parents WHERE student_id = ?", (student_id,)).fetchone()
            if parent:
                if new_status == 'ACKNOWLEDGED':
                    notify_parent(parent['id'], f"Emergency Acknowledged ({emergency_id})", f"Campus Security Command has acknowledged the emergency alert for your ward {reporter_name}.", category="Emergency", priority="High", db_conn=conn)
                elif new_status in ['ASSIGNED', 'RESPONDER_ASSIGNED']:
                    notify_parent(parent['id'], f"Responder Assigned ({emergency_id})", f"{assigned_unit} assigned to ward {reporter_name}'s emergency.", category="Emergency", priority="High", db_conn=conn)
                elif new_status == 'EN_ROUTE':
                    notify_parent(parent['id'], f"Responder En Route ({emergency_id})", f"Emergency unit {assigned_unit} is en route to your ward's location.", category="Emergency", priority="Critical", db_conn=conn)
                elif new_status == 'ON_SCENE':
                    notify_parent(parent['id'], f"Responder On Scene ({emergency_id})", f"Response unit {assigned_unit} has arrived on scene with your ward {reporter_name}.", category="Emergency", priority="Critical", db_conn=conn)
                elif new_status == 'RESOLVED':
                    notify_parent(parent['id'], f"✓ Emergency Resolved ({emergency_id})", f"The emergency alert for your ward {reporter_name} has been successfully resolved. Safety confirmed.", category="Emergency", priority="Normal", db_conn=conn)
                elif new_status in ['STAND_DOWN', 'CANCELLED']:
                    notify_parent(parent['id'], f"🛡️ Emergency Stood Down — Ward Safe ({emergency_id})", f"Distress beacon for your ward {reporter_name} stood down as false alarm. Ward confirmed SAFE.", category="Emergency", priority="Normal", db_conn=conn)
                elif new_status == 'CLOSED':
                    notify_parent(parent['id'], f"Emergency Closed ({emergency_id})", f"The emergency incident for your ward {reporter_name} is formally closed.", category="Emergency", priority="Normal", db_conn=conn)

        conn.commit()

        # Emit enriched realtime update to all portals
        is_active = new_status in ACTIVE_EMERGENCY_STATUSES
        emit_event('emergency_status_update', {
            'emergency_id': emergency_id,
            'incident_id': emergency_id,
            'student_id': emg['user_id'] if emg['user_role'] == 'student' else None,
            'old_status': old_status,
            'new_status': new_status,
            'status': new_status,
            'is_active': is_active,
            'is_safe': not is_active,
            'assigned_responder': emg['assigned_responder'],
            'location': emg['campus_zone'],
            'category': emg['category'],
            'severity': emg['severity'],
            'resolved_at': emg['resolved_at'] or (now_str if new_status == 'RESOLVED' else None),
            'updated_by': actor_name,
            'timestamp': now_str
        })

        updated = conn.execute("SELECT * FROM emergencies WHERE emergency_id = ?", (emergency_id,)).fetchone()
        return {'status': 'success', 'emergency': dict(updated), 'old_status': old_status, 'new_status': new_status, 'is_active': is_active, 'is_safe': not is_active}

    finally:
        if should_close:
            conn.close()


def assign_responder(
    emergency_id: str,
    responder_name: str,
    responder_role: str = 'Security Officer',
    phone: str = '+91 98765 00001',
    actor_name: str = 'Admin Command',
    actor_role: str = 'admin',
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Assigns an emergency responder or Quick Response Team to the incident.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        emg = conn.execute("SELECT * FROM emergencies WHERE emergency_id = ?", (emergency_id,)).fetchone()
        if not emg:
            return {'status': 'error', 'message': f"Emergency '{emergency_id}' not found."}

        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert responder record
        conn.execute("""
            INSERT INTO emergency_responders (emergency_id, responder_name, responder_role, phone, status, assigned_at)
            VALUES (?, ?, ?, ?, 'ASSIGNED', ?)
        """, (emergency_id, responder_name, responder_role, phone, now_str))

        # Update emergency record
        conn.execute("""
            UPDATE emergencies 
            SET assigned_responder = ?, assigned_responder_type = ?, assigned_at = COALESCE(assigned_at, ?),
                status = CASE WHEN status = 'TRIGGERED' OR status = 'ACKNOWLEDGED' THEN 'RESPONDER_ASSIGNED' ELSE status END
            WHERE emergency_id = ?
        """, (responder_name, responder_role, now_str, emergency_id))

        # Legacy update
        conn.execute("UPDATE incidents SET assigned_to = ? WHERE incident_id = ?", (responder_name, emergency_id))

        # Audit log
        conn.execute("""
            INSERT INTO emergency_audit_logs (emergency_id, user_name, user_role, action, old_value, new_value, timestamp)
            VALUES (?, ?, ?, 'ASSIGN_RESPONDER', ?, ?, ?)
        """, (emergency_id, actor_name, actor_role, emg['assigned_responder'] or 'Unassigned', responder_name, now_str))

        # Append system note
        conn.execute("""
            INSERT INTO emergency_notes (emergency_id, author_id, author_name, author_role, note_text, created_at)
            VALUES (?, 1, ?, ?, ?, ?)
        """, (emergency_id, actor_name, actor_role, f"Assigned {responder_name} ({responder_role}) to incident.", now_str))

        conn.commit()

        emit_event('emergency_responder_assigned', {
            'emergency_id': emergency_id,
            'responder_name': responder_name,
            'responder_role': responder_role,
            'timestamp': now_str
        })

        updated = conn.execute("SELECT * FROM emergencies WHERE emergency_id = ?", (emergency_id,)).fetchone()
        return {'status': 'success', 'emergency': dict(updated)}

    finally:
        if should_close:
            conn.close()


def add_incident_note(
    emergency_id: str,
    author_id: int,
    author_name: str,
    author_role: str,
    note_text: str,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Appends a collaborative incident log note.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute("""
            INSERT INTO emergency_notes (emergency_id, author_id, author_name, author_role, note_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (emergency_id, author_id, author_name, author_role, note_text, now_str))

        conn.execute("""
            INSERT INTO emergency_audit_logs (emergency_id, user_name, user_role, action, old_value, new_value, timestamp)
            VALUES (?, ?, ?, 'ADD_NOTE', NULL, ?, ?)
        """, (emergency_id, author_name, author_role, note_text[:80], now_str))

        conn.commit()
        return {'status': 'success', 'note': {'emergency_id': emergency_id, 'author_name': author_name, 'note_text': note_text, 'created_at': now_str}}
    finally:
        if should_close:
            conn.close()


def calculate_response_times(emergency: dict) -> Dict[str, Any]:
    """
    Computes exact response interval metrics:
    - Time to acknowledge (T_ack)
    - Time to assign responder (T_assign)
    - Time to respond (T_resp)
    - Time to arrive on scene (T_arrive)
    - Total resolution duration (T_total)
    """
    fmt = '%Y-%m-%d %H:%M:%S'
    
    def parse_t(k):
        v = emergency.get(k)
        if not v:
            return None
        try:
            return datetime.datetime.strptime(str(v)[:19], fmt)
        except Exception:
            return None

    t_create = parse_t('created_at')
    t_ack = parse_t('acknowledged_at')
    t_assign = parse_t('assigned_at')
    t_start = parse_t('response_started_at')
    t_arrive = parse_t('arrived_at')
    t_resolve = parse_t('resolved_at')

    def diff_secs(t1, t2):
        if t1 and t2:
            s = max(0, int((t2 - t1).total_seconds()))
            mins = s // 60
            secs = s % 60
            return f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        return "N/A"

    def diff_num(t1, t2):
        if t1 and t2:
            return max(0, int((t2 - t1).total_seconds()))
        return 0

    return {
        'time_to_acknowledge': diff_secs(t_create, t_ack),
        'time_to_assign': diff_secs(t_ack or t_create, t_assign),
        'time_to_respond': diff_secs(t_assign or t_create, t_start),
        'time_to_arrive': diff_secs(t_start or t_assign or t_create, t_arrive),
        'total_resolution_time': diff_secs(t_create, t_resolve),
        'total_seconds': diff_num(t_create, t_resolve)
    }


def get_emergency_full_dossier(emergency_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieves full emergency dossier including timeline events, notes, responders, and metrics.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        emg = conn.execute("SELECT * FROM emergencies WHERE emergency_id = ?", (emergency_id,)).fetchone()
        if not emg:
            return None

        emg_dict = dict(emg)
        responders = [dict(r) for r in conn.execute("SELECT * FROM emergency_responders WHERE emergency_id = ? ORDER BY assigned_at ASC", (emergency_id,)).fetchall()]
        notes = [dict(n) for n in conn.execute("SELECT * FROM emergency_notes WHERE emergency_id = ? ORDER BY created_at ASC", (emergency_id,)).fetchall()]
        audit_logs = [dict(a) for a in conn.execute("SELECT * FROM emergency_audit_logs WHERE emergency_id = ? ORDER BY timestamp ASC", (emergency_id,)).fetchall()]
        notifications = [dict(n) for n in conn.execute("SELECT * FROM emergency_notifications WHERE emergency_id = ? ORDER BY sent_at ASC", (emergency_id,)).fetchall()]

        # Metrics
        metrics = calculate_response_times(emg_dict)

        return {
            'emergency': emg_dict,
            'responders': responders,
            'notes': notes,
            'audit_logs': audit_logs,
            'notifications': notifications,
            'metrics': metrics
        }
    finally:
        if should_close:
            conn.close()


def get_student_latest_emergency(student_id: int, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """
    Retrieves the authoritative latest emergency for a student:
    1. Active emergency (TRIGGERED, ACKNOWLEDGED, ASSIGNED, EN_ROUTE, ON_SCENE) takes precedence.
    2. If no active emergency, retrieves the most recent resolved or closed emergency.
    3. Handles legacy incidents table synchronization for complete backward compatibility.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        # 1. Search for active emergency
        active_row = conn.execute("""
            SELECT * FROM emergencies 
            WHERE user_id = ? AND user_role = 'student' 
              AND status IN ('TRIGGERED', 'ACKNOWLEDGED', 'ASSIGNED', 'RESPONDER_ASSIGNED', 'EN_ROUTE', 'ON_SCENE')
            ORDER BY created_at DESC, id DESC LIMIT 1
        """, (student_id,)).fetchone()

        if active_row:
            emg = dict(active_row)
            return {
                'success': True,
                'has_emergency': True,
                'is_active': True,
                'is_safe': False,
                'is_stood_down': False,
                'incident_id': emg.get('emergency_id'),
                'emergency_id': emg.get('emergency_id'),
                'status': emg.get('status'),
                'category': emg.get('category') or emg.get('emergency_type') or 'Personal Safety',
                'emergency_type': emg.get('emergency_type') or emg.get('category') or 'Emergency SOS',
                'severity': emg.get('severity') or 'HIGH',
                'location': emg.get('campus_zone') or 'Campus Safe Zone',
                'campus_zone': emg.get('campus_zone') or 'Campus Safe Zone',
                'assigned_responder': emg.get('assigned_responder') or 'Awaiting assignment',
                'assigned_to': emg.get('assigned_responder') or 'Awaiting assignment',
                'latitude': emg.get('latitude'),
                'longitude': emg.get('longitude'),
                'created_at': emg.get('created_at'),
                'updated_at': emg.get('updated_at') or emg.get('created_at'),
                'acknowledged_at': emg.get('acknowledged_at'),
                'assigned_at': emg.get('assigned_at'),
                'response_started_at': emg.get('response_started_at'),
                'arrived_at': emg.get('arrived_at'),
                'resolved_at': emg.get('resolved_at'),
                'closed_at': emg.get('closed_at'),
                'message': f"Emergency {emg.get('status')}: Response team is active."
            }

        # 2. Check legacy incidents table for active records
        legacy_active = conn.execute("""
            SELECT * FROM incidents 
            WHERE student_id = ? AND incident_type = 'EMERGENCY_SOS' AND status IN ('ACTIVE', 'RESPONDING', 'ACKNOWLEDGED')
            ORDER BY created_at DESC, id DESC LIMIT 1
        """, (student_id,)).fetchone()

        if legacy_active:
            inc = dict(legacy_active)
            return {
                'success': True,
                'has_emergency': True,
                'is_active': True,
                'is_safe': False,
                'is_stood_down': False,
                'incident_id': inc.get('incident_id'),
                'emergency_id': inc.get('incident_id'),
                'status': inc.get('status') if inc.get('status') != 'ACTIVE' else 'TRIGGERED',
                'category': 'Personal Safety',
                'emergency_type': 'Emergency SOS',
                'severity': 'HIGH',
                'location': inc.get('location') or 'Campus Safe Zone',
                'campus_zone': inc.get('location') or 'Campus Safe Zone',
                'assigned_responder': inc.get('assigned_to') or 'Quick Response Team',
                'assigned_to': inc.get('assigned_to') or 'Quick Response Team',
                'latitude': inc.get('latitude'),
                'longitude': inc.get('longitude'),
                'created_at': inc.get('created_at'),
                'updated_at': inc.get('created_at'),
                'acknowledged_at': None,
                'assigned_at': None,
                'response_started_at': None,
                'arrived_at': None,
                'resolved_at': None,
                'closed_at': None,
                'message': "Emergency active: Response units mobilized."
            }

        # 3. If no active emergency, fetch most recent resolved/closed emergency
        recent_row = conn.execute("""
            SELECT * FROM emergencies 
            WHERE user_id = ? AND user_role = 'student'
            ORDER BY created_at DESC, id DESC LIMIT 1
        """, (student_id,)).fetchone()

        if recent_row:
            emg = dict(recent_row)
            is_active = emg.get('status') in ACTIVE_EMERGENCY_STATUSES
            is_stood_down = emg.get('status') in ['STAND_DOWN', 'CANCELLED']
            return {
                'success': True,
                'has_emergency': True,
                'is_active': is_active,
                'is_safe': not is_active,
                'is_stood_down': is_stood_down,
                'incident_id': emg.get('emergency_id'),
                'emergency_id': emg.get('emergency_id'),
                'status': emg.get('status'),
                'category': emg.get('category') or emg.get('emergency_type') or 'Personal Safety',
                'emergency_type': emg.get('emergency_type') or emg.get('category') or 'Emergency SOS',
                'severity': emg.get('severity') or 'HIGH',
                'location': emg.get('campus_zone') or 'Campus Safe Zone',
                'campus_zone': emg.get('campus_zone') or 'Campus Safe Zone',
                'assigned_responder': emg.get('assigned_responder') or 'Quick Response Team',
                'assigned_to': emg.get('assigned_responder') or 'Quick Response Team',
                'latitude': emg.get('latitude'),
                'longitude': emg.get('longitude'),
                'created_at': emg.get('created_at'),
                'updated_at': emg.get('updated_at') or emg.get('created_at'),
                'acknowledged_at': emg.get('acknowledged_at'),
                'assigned_at': emg.get('assigned_at'),
                'response_started_at': emg.get('response_started_at'),
                'arrived_at': emg.get('arrived_at'),
                'resolved_at': emg.get('resolved_at'),
                'closed_at': emg.get('closed_at'),
                'message': "Emergency stood down (Marked Safe)." if is_stood_down else f"Emergency {emg.get('status')}."
            }

        # 4. Check legacy recent
        legacy_recent = conn.execute("""
            SELECT * FROM incidents 
            WHERE student_id = ? AND incident_type = 'EMERGENCY_SOS'
            ORDER BY created_at DESC, id DESC LIMIT 1
        """, (student_id,)).fetchone()

        if legacy_recent:
            inc = dict(legacy_recent)
            is_active = inc['status'] in ['ACTIVE', 'RESPONDING', 'ACKNOWLEDGED']
            is_stood_down = inc['status'] in ['CANCELLED', 'STAND_DOWN']
            return {
                'success': True,
                'has_emergency': True,
                'is_active': is_active,
                'is_safe': not is_active,
                'is_stood_down': is_stood_down,
                'incident_id': inc['incident_id'],
                'emergency_id': inc['incident_id'],
                'status': inc['status'],
                'category': 'Personal Safety',
                'emergency_type': 'Emergency SOS',
                'severity': 'HIGH',
                'location': inc['location'] or 'Campus Safe Zone',
                'campus_zone': inc['location'] or 'Campus Safe Zone',
                'assigned_responder': inc['assigned_to'] or 'Quick Response Team',
                'assigned_to': inc['assigned_to'] or 'Quick Response Team',
                'latitude': inc['latitude'],
                'longitude': inc['longitude'],
                'created_at': inc['created_at'],
                'updated_at': inc['created_at'],
                'acknowledged_at': None,
                'assigned_at': None,
                'response_started_at': None,
                'arrived_at': None,
                'resolved_at': None,
                'closed_at': None,
                'message': "Emergency stood down (Marked Safe)." if is_stood_down else f"Emergency {inc['status']}."
            }

        return {
            'success': True,
            'has_emergency': False,
            'is_active': False,
            'is_safe': True,
            'is_stood_down': False,
            'incident_id': None,
            'emergency_id': None,
            'status': 'READY',
            'category': 'None',
            'emergency_type': 'None',
            'severity': 'LOW',
            'location': 'Campus Safe Zone',
            'campus_zone': 'Campus Safe Zone',
            'assigned_responder': None,
            'assigned_to': None,
            'created_at': None,
            'updated_at': None,
            'resolved_at': None,
            'closed_at': None,
            'message': 'No active emergency. System is Ready.'
        }
    finally:
        if should_close:
            conn.close()


def get_parent_ward_emergency(parent_id: int, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """
    Retrieves the authoritative latest emergency for the parent's linked student ward.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        parent = conn.execute("SELECT student_id, name FROM parents WHERE id = ?", (parent_id,)).fetchone()
        if not parent or not parent['student_id']:
            return {
                'success': False,
                'has_emergency': False,
                'is_active': False,
                'incident_id': None,
                'status': 'READY',
                'message': 'No linked student ward found for this parent.'
            }

        res = get_student_latest_emergency(parent['student_id'], conn)
        res['student_id'] = parent['student_id']
        return res
    finally:
        if should_close:
            conn.close()
