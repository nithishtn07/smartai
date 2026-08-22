"""
CampusGuard AI — Campus Security Console Routes
"""

import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from database.db import get_db_connection
from services.safety_intelligence import (
    CONFIGURED_ZONES,
    calculate_location_risk_scores,
    analyze_temporal_patterns,
    detect_emerging_risks,
    detect_repeated_patterns,
    calculate_incident_priority,
    generate_executive_safety_briefing,
    normalize_zone_name
)
from services.incident_analyzer import correlate_safety_context

security_bp = Blueprint('security', __name__)


@security_bp.route('/security/dashboard')
def security_dashboard():
    """
    Dedicated Campus Security Command Console:
    Interactive live telemetry, active SOS distress queue, multi-zone risk matrices,
    and spatial-temporal incident patterns.
    """
    conn = get_db_connection()
    try:
        active_incidents = conn.execute("""
            SELECT i.*, s.name as student_name, s.register_number, s.phone as student_phone
            FROM incidents i
            LEFT JOIN students s ON i.student_id = s.id
            WHERE i.status != 'RESOLVED' AND i.status != 'CANCELLED'
            ORDER BY i.created_at DESC
        """).fetchall()

        all_incidents = conn.execute("""
            SELECT i.*, s.name as student_name, s.register_number 
            FROM incidents i
            LEFT JOIN students s ON i.student_id = s.id
            ORDER BY i.created_at DESC LIMIT 50
        """).fetchall()

        active_walks = conn.execute("""
            SELECT w.*, s.name as student_name, s.phone as student_phone
            FROM safe_walk_sessions w
            JOIN students s ON w.student_id = s.id
            WHERE w.status = 'IN_PROGRESS'
            ORDER BY w.created_at DESC
        """).fetchall()

        incidents_list = conn.execute("SELECT * FROM incidents").fetchall()
        complaints_list = conn.execute("SELECT * FROM complaints").fetchall()

        # Generate Real-Time Intelligence Telemetry
        risk_scores = calculate_location_risk_scores(incidents_list, complaints_list)
        temporal_analysis = analyze_temporal_patterns(incidents_list)
        emerging_risks = detect_emerging_risks(incidents_list)
        repeated_patterns = detect_repeated_patterns(incidents_list, complaints_list)
        executive_briefing = generate_executive_safety_briefing(incidents_list, complaints_list, risk_scores)

        # Compute priority ranking for each incident
        ranked_incidents = []
        for inc in all_incidents:
            norm_loc = normalize_zone_name(inc['location'] or '')
            loc_risk = risk_scores.get(norm_loc, {}).get('risk_score', 50)
            p_rank = calculate_incident_priority(inc, loc_risk)
            ranked_incidents.append({
                'item': inc,
                'priority_rank': p_rank,
                'zone_name': norm_loc,
                'location_risk': loc_risk
            })
        ranked_incidents.sort(key=lambda x: x['priority_rank'], reverse=True)

        return render_template(
            'security/dashboard.html',
            active_incidents=active_incidents,
            all_incidents=all_incidents,
            active_walks=active_walks,
            ranked_incidents=ranked_incidents,
            risk_scores=risk_scores,
            zone_scores=risk_scores,
            temporal_analysis=temporal_analysis,
            emerging_risks=emerging_risks,
            repeated_patterns=repeated_patterns,
            briefing=executive_briefing,
            executive_briefing=executive_briefing,
            configured_zones=CONFIGURED_ZONES,
            active_page='security'
        )
    finally:
        conn.close()


@security_bp.route('/api/security/zone-intel/<zone_id>')
def api_security_zone_intel(zone_id):
    """
    Returns rich spatial telemetry and context for an interactive campus zone.
    """
    conn = get_db_connection()
    try:
        incidents = conn.execute("SELECT * FROM incidents").fetchall()
        complaints = conn.execute("SELECT * FROM complaints").fetchall()
        zone_scores = calculate_location_risk_scores(incidents, complaints)
        
        for z in zone_scores.values():
            if z.get('zone_id') == zone_id:
                return jsonify(z)
        
        # Fallback default
        return jsonify(list(zone_scores.values())[0] if zone_scores else {
            'zone_id': zone_id,
            'short_name': 'Parking Area',
            'risk_score': 75,
            'cctv_count': 6
        })
    finally:
        conn.close()


from services.emergency_service import transition_emergency_status, assign_responder


@security_bp.route('/security/incident/<incident_id>/status', methods=['POST'])
def security_incident_status(incident_id):
    """
    Security officer action endpoint to transition emergency incident states.
    """
    new_status = request.form.get('status', 'RESOLVED')
    assigned_to = request.form.get('assigned_to', 'Security Dispatch Unit')

    conn = get_db_connection()
    try:
        if assigned_to and assigned_to != 'Unassigned':
            assign_responder(incident_id, assigned_to, 'Campus Security', actor_name='Security Officer', actor_role='security', conn=conn)

        transition_emergency_status(incident_id, new_status, 'Security Officer', 'security', notes=f"Status set to {new_status} by Security Command", conn=conn)

        conn.execute("""
            UPDATE incidents 
            SET status = ?, assigned_to = ?
            WHERE incident_id = ?
        """, (new_status, assigned_to, incident_id))
        
        conn.commit()

        flash(f"Incident {incident_id} transitioned to '{new_status}' (Assigned: {assigned_to}).", "success")
        return redirect(url_for('security.security_dashboard'))
    finally:
        conn.close()
