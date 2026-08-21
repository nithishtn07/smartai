"""
=============================================================================
CampusGuard AI - Personalized AI Campus Briefing Service
Generates dynamic contextual briefing on student login and dashboard.
=============================================================================
"""

import datetime
from .attendance_ai import analyze_student_attendance

def generate_student_briefing(student, conn) -> dict:
    """
    Synthesizes real-time personalized briefing using student database records.
    """
    student_id = student['id']
    first_name = student['name'].split()[0] if ('name' in student.keys() and student['name']) else 'Student'

    # Time-based greeting
    hour = datetime.datetime.now().hour
    if hour < 12:
        greeting = f"Good morning, {first_name} 👋"
    elif hour < 17:
        greeting = f"Good afternoon, {first_name} 👋"
    else:
        greeting = f"Good evening, {first_name} 👋"

    # 1. Attendance synthesis
    att_rows = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (student_id,)).fetchall()
    att_analysis = analyze_student_attendance(att_rows)

    # 2. Next class synthesis
    today_name = datetime.datetime.now().strftime('%A')
    classes = conn.execute("""
        SELECT * FROM timetable WHERE department = ? AND year = ? AND day_of_week = ?
        ORDER BY start_time ASC
    """, (student['department'], student['year'], today_name)).fetchall()

    if not classes:
        classes = conn.execute("""
            SELECT * FROM timetable WHERE department = ? AND year = ? AND day_of_week = 'Monday'
            ORDER BY start_time ASC
        """, (student['department'], student['year'])).fetchall()
        next_class_str = f"{classes[0]['subject_name']} ({classes[0]['start_time']}) in {classes[0]['room_number']} [Monday Preview]" if classes else "No classes scheduled"
    else:
        c = classes[0]
        next_class_str = f"{c['subject_name']} at {c['start_time']} in {c['room_number']}"

    # 3. Pending complaints
    pending_complaints = conn.execute("""
        SELECT COUNT(*) as cnt FROM complaints WHERE student_id = ? AND status NOT IN ('Resolved', 'Rejected')
    """, (student_id,)).fetchone()['cnt']

    # 4. Unread alerts
    unread_alerts = conn.execute("""
        SELECT COUNT(*) as cnt FROM alerts a WHERE a.id NOT IN (
            SELECT alert_id FROM student_alert_reads WHERE student_id = ?
        )
    """, (student_id,)).fetchone()['cnt']

    # 5. Active SOS
    active_sos = conn.execute("""
        SELECT * FROM incidents WHERE student_id = ? AND incident_type = 'EMERGENCY_SOS' AND status = 'ACTIVE'
        ORDER BY created_at DESC LIMIT 1
    """, (student_id,)).fetchone()

    # 6. Synthesized briefing cards
    briefing_items = []

    # Next Class Card
    briefing_items.append({
        'icon': '📚',
        'title': 'Next Class',
        'text': next_class_str,
        'badge': 'Scheduled'
    })

    # Attendance Risk or Good Standing Card
    if att_analysis['risk_courses']:
        rc = att_analysis['risk_courses'][0]
        briefing_items.append({
            'icon': '⚠️',
            'title': 'Attendance Warning',
            'text': f"{rc['name']} is at {rc['pct']}%. {rc['action']}",
            'badge': 'Action Required',
            'badge_class': 'badge-yellow'
        })
    else:
        briefing_items.append({
            'icon': '📊',
            'title': 'Attendance Standing',
            'text': f"Overall attendance is strong at {att_analysis['overall_pct']}%.",
            'badge': 'Compliant',
            'badge_class': 'badge-green'
        })

    # Grievance / Alerts Status
    if pending_complaints > 0:
        briefing_items.append({
            'icon': '📝',
            'title': 'Grievances',
            'text': f"{pending_complaints} complaint{'s' if pending_complaints > 1 else ''} currently being reviewed by administrative departments.",
            'badge': 'In Progress',
            'badge_class': 'badge-cyan'
        })
    
    # Campus Safety Status
    if active_sos:
        briefing_items.append({
            'icon': '🚨',
            'title': 'Emergency SOS Active',
            'text': f"Distress beacon {active_sos['incident_id']} is actively receiving security response.",
            'badge': 'SOS Active',
            'badge_class': 'badge-red'
        })
    else:
        briefing_items.append({
            'icon': '🛡️',
            'title': 'Campus Safety Status',
            'text': f"{unread_alerts} unread alert{'s' if unread_alerts != 1 else ''}. Perimeter CCTV monitoring active.",
            'badge': 'Secure',
            'badge_class': 'badge-green'
        })

    return {
        'greeting': greeting,
        'overall_pct': att_analysis['overall_pct'],
        'next_class': next_class_str,
        'pending_complaints': pending_complaints,
        'unread_alerts': unread_alerts,
        'active_sos': active_sos,
        'briefing_items': briefing_items,
        'recommendations': att_analysis['recommendations']
    }
