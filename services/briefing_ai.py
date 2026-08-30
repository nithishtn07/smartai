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

    # 5. Active SOS (Single Source of Truth)
    active_sos_row = conn.execute("""
        SELECT * FROM emergencies 
        WHERE user_id = ? AND user_role = 'student' AND status IN ('TRIGGERED', 'ACKNOWLEDGED', 'ASSIGNED', 'RESPONDER_ASSIGNED', 'EN_ROUTE', 'ON_SCENE', 'ACTIVE', 'RESPONDING')
        ORDER BY created_at DESC LIMIT 1
    """, (student_id,)).fetchone()
    if not active_sos_row:
        active_sos_row = conn.execute("""
            SELECT * FROM incidents WHERE student_id = ? AND incident_type = 'EMERGENCY_SOS' AND status = 'ACTIVE'
            ORDER BY created_at DESC LIMIT 1
        """, (student_id,)).fetchone()
    active_sos = dict(active_sos_row) if active_sos_row else None

    # 6. Upcoming Exams
    next_exam = conn.execute("SELECT * FROM examinations ORDER BY exam_date ASC, exam_time ASC LIMIT 1").fetchone()
    exam_days_left = None
    if next_exam and next_exam['exam_date']:
        try:
            e_dt = datetime.datetime.strptime(next_exam['exam_date'], '%Y-%m-%d').date()
            exam_days_left = (e_dt - datetime.date.today()).days
        except Exception:
            pass

    # 7. Pending Assignments
    pending_assignments = conn.execute("""
        SELECT * FROM assignments WHERE status != 'Evaluated' ORDER BY due_date ASC LIMIT 2
    """).fetchall()

    # 8. Pending Fees
    fees = conn.execute("SELECT * FROM fees WHERE student_id = ?", (student_id,)).fetchall()
    total_fee = sum(f['amount'] for f in fees) if fees else 0
    total_paid = sum(f['paid_amount'] for f in fees) if fees else 0
    pending_fee = max(0, total_fee - total_paid)

    # 9. Synthesized briefing cards
    briefing_items = []

    # Next Class Card
    briefing_items.append({
        'icon': '📚',
        'title': 'Next Class',
        'text': next_class_str,
        'badge': 'Scheduled',
        'badge_class': 'badge-cyan'
    })

    # Attendance Risk or Good Standing Card
    if not att_rows:
        briefing_items.append({
            'icon': '📊',
            'title': 'Attendance Standing',
            'text': "No attendance records logged yet for this semester.",
            'badge': 'No Records',
            'badge_class': 'badge-cyan'
        })
    elif att_analysis['risk_courses']:
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
            'text': f"Overall attendance is maintained at {att_analysis['overall_pct']}%.",
            'badge': 'Compliant',
            'badge_class': 'badge-green'
        })

    # Assignment Card
    if pending_assignments:
        pa = pending_assignments[0]
        briefing_items.append({
            'icon': '📝',
            'title': 'Assignment Deadline',
            'text': f"{pa['title']} ({pa['course_code']}) is due on {pa['due_date']}.",
            'badge': 'Due Soon',
            'badge_class': 'badge-purple'
        })

    # Upcoming Exam Card
    if next_exam:
        countdown_str = f"in {exam_days_left} days" if exam_days_left is not None and exam_days_left >= 0 else next_exam['exam_date']
        briefing_items.append({
            'icon': '🎯',
            'title': 'Upcoming Exam',
            'text': f"{next_exam['course_name']} ({next_exam['course_code']}) scheduled for {next_exam['exam_date']} ({countdown_str}).",
            'badge': 'Exam Prep',
            'badge_class': 'badge-indigo'
        })

    # Fee Card (if pending)
    if pending_fee > 0:
        briefing_items.append({
            'icon': '💳',
            'title': 'Fee Balance',
            'text': f"Outstanding balance of ₹{pending_fee:,.2f} pending semester clearance.",
            'badge': 'Payment Due',
            'badge_class': 'badge-yellow'
        })

    # Campus Safety Status
    if active_sos:
        beacon_id = active_sos.get('emergency_id') or active_sos.get('incident_id') or 'EMG-ACTIVE'
        briefing_items.append({
            'icon': '🚨',
            'title': 'Emergency SOS Active',
            'text': f"Distress beacon {beacon_id} is actively receiving security response.",
            'badge': 'SOS Active',
            'badge_class': 'badge-red'
        })

    # AI Recommendation
    recommendation = "Review lecture notes for upcoming classes and maintain active participation."
    if att_analysis['risk_courses']:
        recommendation = f"Focus on attending your upcoming {att_analysis['risk_courses'][0]['name']} classes to bring attendance above 75%."
    elif next_exam and exam_days_left is not None and exam_days_left <= 7:
        recommendation = f"Dedicate 1.5 hours today to revise {next_exam['course_name']} for your upcoming examination."
    elif pending_assignments:
        recommendation = f"Complete your {pending_assignments[0]['title']} assignment ahead of the {pending_assignments[0]['due_date']} deadline."

    return {
        'greeting': greeting,
        'overall_pct': att_analysis['overall_pct'],
        'next_class': next_class_str,
        'pending_complaints': pending_complaints,
        'unread_alerts': unread_alerts,
        'active_sos': active_sos,
        'briefing_items': briefing_items,
        'recommendations': [recommendation],
        'primary_recommendation': recommendation
    }
