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
        if not skip_idempotency:
            recent = conn.execute("""
                SELECT * FROM emergencies 
                WHERE user_id = ? AND user_role = ? AND status = 'TRIGGERED'
                AND created_at >= datetime('now', '-8 seconds')
            """, (reporter_id, reporter_role)).fetchone()

            if recent:
                return {'status': 'success', 'emergency': dict(recent), 'is_duplicate': True}

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
            priority='Critical'
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
                    priority='Critical'
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
            priority='High'
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

        conn.commit()

        # Emit realtime update
        emit_event('emergency_status_update', {
            'emergency_id': emergency_id,
            'old_status': old_status,
            'new_status': new_status,
            'updated_by': actor_name,
            'timestamp': now_str
        })

        updated = conn.execute("SELECT * FROM emergencies WHERE emergency_id = ?", (emergency_id,)).fetchone()
        return {'status': 'success', 'emergency': dict(updated), 'old_status': old_status, 'new_status': new_status}

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
