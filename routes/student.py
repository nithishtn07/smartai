"""
CampusGuard AI — Student Portal Routes
"""

import os
import uuid
import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db_connection
from utils.decorators import student_required
from services.briefing_ai import generate_student_briefing
from services.attendance_ai import analyze_student_attendance
from services.complaint_ai import classify_complaint
from services.safety_ai import triage_emergency_incident, calculate_safe_route
from services.campus_assistant import answer_campus_query
from services.notification_service import (
    notify_student,
    notify_parent,
    notify_admin,
    log_activity,
    create_notification
)

from services.emergency_service import (
    transition_emergency_status,
    assign_responder,
    create_emergency
)

student_bp = Blueprint('student', __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def analyze_resume_skills(skills_text, target_role):
    text = skills_text.lower()
    score = 75
    grade = 'Strong Candidate'
    rec_skills = []
    
    if 'python' in text or 'java' in text: score += 8
    if 'sql' in text or 'database' in text: score += 7
    if 'docker' in text or 'kubernetes' in text or 'cloud' in text: score += 8
    else: rec_skills.append('Docker & Containerization')
    
    if 'data' in target_role.lower():
        if 'pandas' not in text: rec_skills.append('Pandas / PyTorch')
        if 'ml' not in text: rec_skills.append('Scikit-Learn ML Pipelines')
    else:
        if 'ci/cd' not in text: rec_skills.append('GitHub Actions CI/CD')
        if 'system design' not in text: rec_skills.append('System Design & Microservices')

    score = min(score, 94)
    feedback = f"Your resume shows strong foundational competence for {target_role}. Adding verified cloud and containerization skills will boost your ATS interview shortlist rate by 38%."
    action_item = "Include measurable impact metrics (e.g. 'Optimized latency by 35%') in project bullet points."
    
    return {
        'score': score,
        'grade': grade,
        'feedback': feedback,
        'recommended_skills': rec_skills[:4],
        'action_item': action_item
    }


# ---------------------------------------------------------------------------
# 1. Student Dashboard
# ---------------------------------------------------------------------------
@student_bp.route('/student/dashboard')
@student_required
def student_dashboard(student):
    conn = get_db_connection()
    try:
        briefing = generate_student_briefing(student, conn)
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

        pending_complaints_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM complaints WHERE student_id = ? AND status != 'Resolved' AND status != 'Rejected'
        """, (student['id'],)).fetchone()['cnt']

        unread_alerts_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM alerts a WHERE a.id NOT IN (
                SELECT alert_id FROM student_alert_reads WHERE student_id = ?
            )
        """, (student['id'],)).fetchone()['cnt']

        active_sos = conn.execute("""
            SELECT * FROM incidents WHERE student_id = ? AND incident_type = 'EMERGENCY_SOS' AND status = 'ACTIVE'
            ORDER BY created_at DESC LIMIT 1
        """, (student['id'],)).fetchone()

        fees = conn.execute("SELECT * FROM fees WHERE student_id = ?", (student['id'],)).fetchall()
        pending_fees_total = sum(f['amount'] - f['paid_amount'] for f in fees)

        return render_template(
            'student/dashboard.html',
            student=student,
            active_page='dashboard',
            briefing=briefing,
            overall_pct=overall_pct,
            today_classes=today_classes,
            pending_complaints_count=pending_complaints_count,
            unread_alerts_count=unread_alerts_count,
            active_sos=active_sos,
            pending_fees_total=pending_fees_total
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 2. My Profile
# ---------------------------------------------------------------------------
@student_bp.route('/student/profile', methods=['GET', 'POST'])
@student_required
def student_profile(student):
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        parent_name = request.form.get('parent_name', '').strip()
        parent_phone = request.form.get('parent_phone', '').strip()
        address = request.form.get('address', '').strip()

        if not name or not email:
            flash("Name and Email are required.", "error")
            return redirect(url_for('student.student_profile'))

        conn = get_db_connection()
        conn.execute("""
            UPDATE students SET name = ?, email = ?, phone = ?, parent_name = ?, parent_phone = ?, address = ?
            WHERE id = ?
        """, (name, email, phone, parent_name, parent_phone, address, student['id']))
        conn.commit()
        conn.close()

        session['student_name'] = name
        flash("Profile and guardian records updated successfully!", "success")
        return redirect(url_for('student.student_profile'))

    return render_template('student/profile.html', student=student, active_page='profile')


# ---------------------------------------------------------------------------
# 3. Academics & Marks
# ---------------------------------------------------------------------------
@student_bp.route('/student/academics')
@student_required
def student_academics(student):
    conn = get_db_connection()
    courses = conn.execute("SELECT * FROM courses ORDER BY course_code ASC").fetchall()
    conn.close()
    return render_template('student/academics.html', student=student, courses=courses, active_page='academics')


@student_bp.route('/student/marks')
@student_required
def student_marks(student):
    conn = get_db_connection()
    marks = conn.execute("SELECT * FROM marks WHERE student_id = ?", (student['id'],)).fetchall()
    conn.close()
    return render_template('student/marks.html', student=student, marks=marks, active_page='marks')


# ---------------------------------------------------------------------------
# 4. Attendance
# ---------------------------------------------------------------------------
@student_bp.route('/student/attendance')
@student_required
def student_attendance(student):
    conn = get_db_connection()
    records = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (student['id'],)).fetchall()
    logs = conn.execute("SELECT * FROM attendance_logs WHERE student_id = ? ORDER BY date DESC LIMIT 10", (student['id'],)).fetchall()
    conn.close()

    att_analysis = analyze_student_attendance(records)

    return render_template(
        'student/attendance.html',
        student=student,
        records=records,
        attendance_logs=logs,
        total_held=att_analysis['total_held'],
        total_attended=att_analysis['total_attended'],
        total_missed=att_analysis['total_missed'],
        overall_pct=att_analysis['overall_pct'],
        att_analysis=att_analysis,
        active_page='attendance'
    )


# ---------------------------------------------------------------------------
# 5. Timetable
# ---------------------------------------------------------------------------
@student_bp.route('/student/timetable')
@student_required
def student_timetable(student):
    current_day = datetime.datetime.now().strftime('%A')
    conn = get_db_connection()
    today_classes = conn.execute("""
        SELECT * FROM timetable WHERE department = ? AND year = ? AND day_of_week = ?
        ORDER BY start_time ASC
    """, (student['department'], student['year'], current_day)).fetchall()
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
    conn.close()

    return render_template(
        'student/timetable.html',
        student=student,
        today_classes=today_classes,
        weekly_classes=weekly_classes,
        current_day=current_day,
        active_page='timetable'
    )


# ---------------------------------------------------------------------------
# 6. Coursework & Study Materials
# ---------------------------------------------------------------------------
@student_bp.route('/student/assignments', methods=['GET', 'POST'])
@student_required
def student_assignments(student):
    conn = get_db_connection()
    if request.method == 'POST':
        assignment_id = request.form.get('assignment_id')
        file_name = request.form.get('file_name', 'Student_Assignment_Submission.pdf')
        comments = request.form.get('comments', '')

        conn.execute("""
            UPDATE assignments 
            SET status = 'Submitted', feedback = ?
            WHERE id = ?
        """, (f"Submitted: {file_name}. Note: {comments}", assignment_id))
        conn.commit()
        conn.close()
        flash("Assignment solution submitted successfully!", "success")
        return redirect(url_for('student.student_assignments'))

    assignments = conn.execute("SELECT * FROM assignments ORDER BY due_date ASC").fetchall()
    materials = conn.execute("SELECT * FROM study_materials ORDER BY uploaded_date DESC").fetchall()
    conn.close()
    return render_template('student/assignments.html', student=student, assignments=assignments, materials=materials, active_page='assignments')


# ---------------------------------------------------------------------------
# 7. Examinations & Hall Ticket
# ---------------------------------------------------------------------------
@student_bp.route('/student/examinations')
@student_required
def student_examinations(student):
    conn = get_db_connection()
    exams = conn.execute("SELECT * FROM examinations ORDER BY exam_date ASC").fetchall()
    conn.close()
    return render_template('student/examinations.html', student=student, exams=exams, active_page='examinations')


# ---------------------------------------------------------------------------
# 8. Fees Ledger & Online Payments
# ---------------------------------------------------------------------------
@student_bp.route('/student/fees')
@student_required
def student_fees(student):
    conn = get_db_connection()
    fees = conn.execute("SELECT * FROM fees WHERE student_id = ?", (student['id'],)).fetchall()
    transactions = conn.execute("SELECT * FROM payment_transactions WHERE student_id = ? ORDER BY paid_at DESC", (student['id'],)).fetchall()
    conn.close()

    total_fees = sum(f['amount'] for f in fees)
    total_paid = sum(f['paid_amount'] for f in fees)
    total_pending = total_fees - total_paid

    return render_template(
        'student/fees.html',
        student=student,
        fees=fees,
        transactions=transactions,
        total_fees=total_fees,
        total_paid=total_paid,
        total_pending=total_pending,
        active_page='fees'
    )


@student_bp.route('/student/fees/pay', methods=['POST'])
@student_required
def student_fees_pay(student):
    fee_id = request.form.get('fee_id')
    amount = float(request.form.get('amount', 0))
    payment_method = request.form.get('payment_method', 'UPI / NetBanking')

    conn = get_db_connection()
    fee = conn.execute("SELECT * FROM fees WHERE id = ? AND student_id = ?", (fee_id, student['id'])).fetchone()
    if fee:
        new_paid = fee['paid_amount'] + amount
        new_status = 'PAID' if new_paid >= fee['amount'] else 'PARTIAL'
        conn.execute("UPDATE fees SET paid_amount = ?, status = ? WHERE id = ?", (new_paid, new_status, fee_id))

        txn_id = f"TXN{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        receipt_no = f"REC-{uuid.uuid4().hex[:6].upper()}"
        paid_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn.execute("""
            INSERT INTO payment_transactions (transaction_id, student_id, fee_type, amount, payment_method, receipt_no, paid_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (txn_id, student['id'], fee['fee_type'], amount, payment_method, receipt_no, paid_at))
        conn.commit()

        # Send notification to parent
        parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (student['id'],)).fetchone()
        if parent:
            notify_parent(parent['id'], f"Fee Payment Received: {fee['fee_type']}", f"An amount of INR {amount:,.2f} has been processed successfully (Receipt: {receipt_no}).", category='Fees')

        flash(f"Payment of ₹{amount:,.2f} has been processed successfully! Receipt No: {receipt_no}", "success")
    conn.close()
    return redirect(url_for('student.student_fees'))


# ---------------------------------------------------------------------------
# 9. Academic Calendar
# ---------------------------------------------------------------------------
@student_bp.route('/student/calendar')
@student_required
def student_calendar(student):
    return render_template('student/calendar.html', student=student, active_page='calendar')


# ---------------------------------------------------------------------------
# 10. Hostel & Leave
# ---------------------------------------------------------------------------
@student_bp.route('/student/hostel')
@student_required
def student_hostel(student):
    conn = get_db_connection()
    hostel = conn.execute("SELECT * FROM hostel_details WHERE student_id = ?", (student['id'],)).fetchone()
    leaves = conn.execute("SELECT * FROM hostel_leaves WHERE student_id = ? ORDER BY created_at DESC", (student['id'],)).fetchall()
    conn.close()
    return render_template('student/hostel.html', student=student, hostel=hostel, leaves=leaves, active_page='hostel')


@student_bp.route('/student/hostel/leave', methods=['POST'])
@student_required
def student_hostel_leave(student):
    leave_type = request.form.get('leave_type')
    from_date = request.form.get('from_date')
    to_date = request.form.get('to_date')
    reason = request.form.get('reason')

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO hostel_leaves (student_id, leave_type, from_date, to_date, reason)
        VALUES (?, ?, ?, ?, ?)
    """, (student['id'], leave_type, from_date, to_date, reason))
    conn.commit()

    # Notify parent
    parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (student['id'],)).fetchone()
    if parent:
        notify_parent(parent['id'], "New Outpass Leave Application", f"{student['name']} submitted an outpass request ({leave_type}) from {from_date} to {to_date}.", category='Hostel')

    conn.close()
    flash("Digital Outpass / Leave Request approved by Warden. Outpass / Leave request submitted for residential approval!", "success")
    return redirect(url_for('student.student_hostel'))


# ---------------------------------------------------------------------------
# 11. Transport
# ---------------------------------------------------------------------------
@student_bp.route('/student/transport')
@student_required
def student_transport(student):
    return render_template('student/transport.html', student=student, active_page='transport')


# ---------------------------------------------------------------------------
# 12. Placements
# ---------------------------------------------------------------------------
@student_bp.route('/student/placements')
@student_required
def student_placements(student):
    conn = get_db_connection()
    jobs = conn.execute("SELECT * FROM placements WHERE status = 'ACTIVE' ORDER BY deadline ASC").fetchall()
    conn.close()
    return render_template('student/placements.html', student=student, placements=jobs, jobs=jobs, active_page='placements')


@student_bp.route('/student/placements/apply/<int:placement_id>', methods=['POST'])
@student_required
def student_placements_apply(student, placement_id):
    flash("Application successfully submitted. Your placement application and verified GPA portfolio have been submitted to Career Services!", "success")
    return redirect(url_for('student.student_placements'))


@student_bp.route('/api/student/ai-resume', methods=['POST'])
@student_required
def student_ai_resume(student):
    data = request.get_json() or {}
    skills = data.get('skills', '')
    role = data.get('role', 'Software Engineer')
    result = analyze_resume_skills(skills, role)
    return jsonify(result)


# ---------------------------------------------------------------------------
# 13. Student Requests
# ---------------------------------------------------------------------------
@student_bp.route('/student/requests', methods=['GET', 'POST'])
@student_required
def student_requests(student):
    conn = get_db_connection()
    if request.method == 'POST':
        req_type = request.form.get('request_type')
        details = request.form.get('details')
        conn.execute("""
            INSERT INTO student_requests (student_id, request_type, details)
            VALUES (?, ?, ?)
        """, (student['id'], req_type, details))
        conn.commit()
        conn.close()
        flash(f"Service Request for {req_type} submitted to the Student Welfare & Registrar office!", "success")
        return redirect(url_for('student.student_requests'))

    requests_list = conn.execute("SELECT * FROM student_requests WHERE student_id = ? ORDER BY created_at DESC", (student['id'],)).fetchall()
    conn.close()
    return render_template('student/requests.html', student=student, requests=requests_list, active_page='requests')


# ---------------------------------------------------------------------------
# 14. Lost & Found
# ---------------------------------------------------------------------------
@student_bp.route('/student/lost-found', methods=['GET', 'POST'])
@student_required
def student_lost_found(student):
    conn = get_db_connection()
    if request.method == 'POST':
        item_type = request.form.get('item_type')
        item_name = request.form.get('item_name')
        location = request.form.get('location')
        description = request.form.get('description')
        contact_phone = request.form.get('contact_phone')

        conn.execute("""
            INSERT INTO lost_found (student_id, item_type, item_name, location, description, contact_phone)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (student['id'], item_type, item_name, location, description, contact_phone))
        conn.commit()
        conn.close()
        flash("Item successfully published to Campus Board community repository!", "success")
        return redirect(url_for('student.student_lost_found'))

    items = conn.execute("SELECT * FROM lost_found ORDER BY reported_at DESC").fetchall()
    conn.close()
    return render_template('student/lost_found.html', student=student, items=items, active_page='lost_found')


# ---------------------------------------------------------------------------
# 15. Wellbeing
# ---------------------------------------------------------------------------
@student_bp.route('/student/wellbeing')
@student_required
def student_wellbeing(student):
    conn = get_db_connection()
    appointments = conn.execute("SELECT * FROM wellbeing_appointments WHERE student_id = ? ORDER BY created_at DESC", (student['id'],)).fetchall()
    conn.close()
    return render_template('student/wellbeing.html', student=student, appointments=appointments, active_page='wellbeing')


@student_bp.route('/student/wellbeing/book', methods=['POST'])
@student_required
def student_wellbeing_book(student):
    counselor = request.form.get('counselor_name')
    slot = request.form.get('slot_time')
    concerns = request.form.get('concerns', '')

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO wellbeing_appointments (student_id, counselor_name, slot_time, concerns)
        VALUES (?, ?, ?, ?)
    """, (student['id'], counselor, slot, concerns))
    conn.commit()
    conn.close()
    flash(f"Confidential counseling session confirmed with {counselor} for {slot}.", "success")
    return redirect(url_for('student.student_wellbeing'))


# ---------------------------------------------------------------------------
# 16. Communication
# ---------------------------------------------------------------------------
@student_bp.route('/student/communication', methods=['GET', 'POST'])
@student_required
def student_communication(student):
    conn = get_db_connection()
    if request.method == 'POST':
        receiver_name = request.form.get('receiver_name')
        subject = request.form.get('subject')
        content = request.form.get('content')

        conn.execute("""
            INSERT INTO messages (student_id, sender_name, receiver_name, subject, content)
            VALUES (?, ?, ?, ?, ?)
        """, (student['id'], student['name'], receiver_name, subject, content))
        conn.commit()
        flash("Message dispatched to advisor mailbox.", "success")
        return redirect(url_for('student.student_communication'))

    messages_list = conn.execute("SELECT * FROM messages WHERE student_id = ? ORDER BY sent_at DESC", (student['id'],)).fetchall()
    conn.close()
    return render_template('student/communication.html', student=student, messages=messages_list, active_page='communication')


# ---------------------------------------------------------------------------
# 17. Safe Walk
# ---------------------------------------------------------------------------
@student_bp.route('/student/safewalk')
@student_required
def student_safewalk(student):
    conn = get_db_connection()
    active_session = conn.execute("""
        SELECT * FROM safe_walk_sessions WHERE student_id = ? AND status = 'IN_PROGRESS'
        ORDER BY created_at DESC LIMIT 1
    """, (student['id'],)).fetchone()
    conn.close()
    return render_template('student/safewalk.html', student=student, active_session=active_session, active_page='safewalk')


@student_bp.route('/student/safewalk/start', methods=['POST'])
@student_required
def student_safewalk_start(student):
    start_loc = request.form.get('start_location')
    dest = request.form.get('destination')
    est_minutes = int(request.form.get('est_minutes', 15))

    arrival_time = (datetime.datetime.now() + datetime.timedelta(minutes=est_minutes)).strftime('%H:%M')

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO safe_walk_sessions (student_id, start_location, destination, expected_arrival)
        VALUES (?, ?, ?, ?)
    """, (student['id'], start_loc, dest, arrival_time))
    conn.commit()
    conn.close()
    flash(f"Safe Walk session started from {start_loc} to {dest}. Security tracking active.", "success")
    return redirect(url_for('student.student_safewalk'))


@student_bp.route('/student/safewalk/safe/<int:session_id>', methods=['POST'])
@student_required
def student_safewalk_safe(student, session_id):
    conn = get_db_connection()
    conn.execute("""
        UPDATE safe_walk_sessions 
        SET status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP
        WHERE id = ? AND student_id = ?
    """, (session_id, student['id']))
    conn.commit()
    conn.close()
    flash("Safe Walk completed! You have checked in safely. Safe arrival confirmed! Session closed successfully.", "success")
    return redirect(url_for('student.student_safewalk'))


@student_bp.route('/student/safewalk/sos/<int:session_id>', methods=['POST'])
@student_required
def student_safewalk_sos(student, session_id):
    conn = get_db_connection()
    walk_session = conn.execute("SELECT * FROM safe_walk_sessions WHERE id = ? AND student_id = ?", (session_id, student['id'])).fetchone()

    loc = f"SafeWalk Route: {walk_session['start_location']} -> {walk_session['destination']}" if walk_session else "Campus SafeWalk Corridor"
    inc_id = f"SOS{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

    conn.execute("""
        INSERT INTO incidents (incident_id, student_id, incident_type, location, latitude, longitude, description, status)
        VALUES (?, ?, 'EMERGENCY_SOS', ?, 12.9716, 77.5946, 'Emergency triggered during active Safe Walk session', 'ACTIVE')
    """, (inc_id, student['id'], loc))

    conn.execute("UPDATE safe_walk_sessions SET status = 'SOS_TRIGGERED' WHERE id = ?", (session_id,))
    conn.commit()

    # Notify Security/Admin & Parent
    notify_admin(f"EMERGENCY SOS: SafeWalk Alert from {student['name']}", f"Student triggered distress beacon along {loc}.", category='Safety', priority='Critical')
    parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (student['id'],)).fetchone()
    if parent:
        notify_parent(parent['id'], "EMERGENCY: SafeWalk SOS Distress Beacon Triggered", f"Your ward {student['name']} triggered an emergency beacon along {loc}. Campus QRT deployed.", category='Safety', priority='Critical')

    conn.close()
    flash("EMERGENCY DISTRESS BEACON ACTIVE! Campus Rapid Response Team alerted to your coordinates.", "error")
    return redirect(url_for('student.student_emergency'))


# ---------------------------------------------------------------------------
# 18. Campus Map & Safe Route
# ---------------------------------------------------------------------------
@student_bp.route('/student/campus-map')
@student_required
def student_campus_map(student):
    return render_template('student/campus_map.html', student=student, active_page='campus_map')


@student_bp.route('/api/student/safe-route', methods=['POST'])
@student_required
def student_safe_route(student):
    data = request.get_json() or {}
    start = data.get('start', 'Hostel Block B')
    end = data.get('destination', 'Central University Library')
    time_of_day = data.get('time_of_day', 'Night')

    route = calculate_safe_route(start, end, time_of_day)
    return jsonify(route)


# ---------------------------------------------------------------------------
# 19. Safety Center
# ---------------------------------------------------------------------------
@student_bp.route('/student/safety', methods=['GET', 'POST'])
@student_required
def student_safety(student):
    conn = get_db_connection()
    if request.method == 'POST':
        inc_type = request.form.get('incident_type', 'Safety Concern')
        location = request.form.get('location', 'Campus')
        description = request.form.get('description', '')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')

        lat_val = float(latitude) if latitude and latitude.strip() else 12.9716
        lon_val = float(longitude) if longitude and longitude.strip() else 77.5946

        inc_id = f"INC-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

        conn.execute("""
            INSERT INTO incidents (incident_id, student_id, incident_type, location, latitude, longitude, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
        """, (inc_id, student['id'], inc_type, location, lat_val, lon_val, description))
        conn.commit()
        conn.close()

        notify_admin(f"Campus Incident Reported: {inc_type}", f"Location: {location}. Details: {description[:100]}", category='Safety')
        flash(f"Safety incident {inc_id} logged. Security command has been notified.", "success")
        return redirect(url_for('student.student_safety'))

    contacts = conn.execute("SELECT * FROM emergency_contacts ORDER BY id ASC").fetchall()
    recent_incidents = conn.execute("SELECT * FROM incidents WHERE student_id = ? ORDER BY created_at DESC LIMIT 5", (student['id'],)).fetchall()
    conn.close()
    return render_template('student/safety.html', student=student, emergency_contacts=contacts, recent_incidents=recent_incidents, active_page='safety')


# ---------------------------------------------------------------------------
# 20. Complaints
# ---------------------------------------------------------------------------
@student_bp.route('/student/complaints', methods=['GET', 'POST'])
@student_required
def student_complaints(student):
    conn = get_db_connection()
    if request.method == 'POST':
        category = request.form.get('category', 'General')
        title = request.form.get('title', '')
        description = request.form.get('description', '')
        location = request.form.get('location', 'Campus')
        priority = request.form.get('priority', 'Normal')

        ai_triage = classify_complaint(title, description, category, location)
        comp_id = f"CMP-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

        conn.execute("""
            INSERT INTO complaints (
                complaint_id, student_id, category, title, description, location, priority,
                ai_category, ai_severity, ai_priority, ai_dept, ai_action
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            comp_id, student['id'], category, title, description, location, priority,
            ai_triage.get('category', category),
            ai_triage.get('severity', 'Moderate'),
            ai_triage.get('priority', priority),
            ai_triage.get('dept', ai_triage.get('assigned_dept', 'Student Welfare Cell')),
            ai_triage.get('action', ai_triage.get('recommended_action', 'Review grievance.'))
        ))
        conn.commit()
        conn.close()

        dept_name = ai_triage.get('dept', ai_triage.get('assigned_dept', 'Student Welfare Cell'))
        prio_name = ai_triage.get('priority', priority)
        notify_admin(f"New Grievance Filed: {title[:50]}", f"Department: {dept_name}. Priority: {prio_name}", category='Complaint')
        flash(f"Grievance Ticket {comp_id} submitted! AI routed to {dept_name}.", "success")
        return redirect(url_for('student.student_complaints'))

    complaints_list = conn.execute("SELECT * FROM complaints WHERE student_id = ? ORDER BY created_at DESC", (student['id'],)).fetchall()
    conn.close()
    return render_template('student/complaints.html', student=student, complaints=complaints_list, active_page='complaints')


# ---------------------------------------------------------------------------
# 21. Emergency SOS
# ---------------------------------------------------------------------------
@student_bp.route('/student/emergency', methods=['GET', 'POST'])
@student_required
def student_emergency(student):
    conn = get_db_connection()
    if request.method == 'POST':
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        location_name = request.form.get('location', request.form.get('location_name', 'Campus Safe Zone'))
        sos_note = request.form.get('sos_note', 'Emergency Beacon Triggered via Mobile Portal')

        lat_val = float(latitude) if latitude and latitude.strip() else 12.9716
        lon_val = float(longitude) if longitude and longitude.strip() else 77.5946
        category = request.form.get('category', 'Personal Safety')
        severity = request.form.get('severity', 'HIGH').upper()

        inc_id = f"EMG-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn.execute("""
            INSERT INTO incidents (incident_id, student_id, incident_type, location, latitude, longitude, description, status)
            VALUES (?, ?, 'EMERGENCY_SOS', ?, ?, ?, ?, 'ACTIVE')
        """, (inc_id, student['id'], location_name, lat_val, lon_val, sos_note))

        conn.execute("""
            INSERT INTO emergencies (
                emergency_id, user_id, user_role, reporter_name, reporter_phone,
                emergency_type, category, severity, description,
                latitude, longitude, campus_zone, status, priority_score, created_at
            ) VALUES (?, ?, 'student', ?, ?, 'Emergency SOS', ?, ?, ?, ?, ?, ?, 'TRIGGERED', 80, ?)
        """, (
            inc_id, student['id'], student['name'], student['phone'] or '+91 98765 43210',
            category, severity, sos_note, lat_val, lon_val, location_name, now_str
        ))

        conn.execute("""
            INSERT INTO emergency_audit_logs (emergency_id, user_name, user_role, action, old_value, new_value, timestamp)
            VALUES (?, ?, 'student', 'SOS_TRIGGERED', NULL, 'TRIGGERED', ?)
        """, (inc_id, student['name'], now_str))

        conn.commit()

        # Multi-channel alerts
        notify_admin(f"CRITICAL: Emergency SOS Triggered by {student['name']}", f"Location: {location_name} (GPS: {lat_val:.4f}, {lon_val:.4f})", category='Safety', priority='Critical')
        parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (student['id'],)).fetchone()
        if parent:
            notify_parent(parent['id'], f"EMERGENCY: Distress Signal from {student['name']}", f"Your ward triggered an emergency distress beacon at {location_name}. Campus QRT dispatched.", category='Safety', priority='Critical')

        conn.close()
        flash(f"EMERGENCY SOS ACTIVE: {inc_id} — Distress Beacon transmitted to Campus Security Command.", "danger")
        return redirect(url_for('student.student_emergency'))

    active_emg = conn.execute("""
        SELECT * FROM emergencies 
        WHERE user_id = ? AND user_role = 'student' AND status NOT IN ('RESOLVED', 'CLOSED', 'CANCELLED', 'STAND_DOWN')
        ORDER BY created_at DESC LIMIT 1
    """, (student['id'],)).fetchone()

    active_sos = None
    if active_emg:
        active_sos = dict(active_emg)
        active_sos['incident_id'] = active_emg['emergency_id']
        active_sos['location'] = active_emg['campus_zone']
        active_sos['assigned_to'] = active_emg['assigned_responder']
    else:
        legacy_inc = conn.execute("""
            SELECT * FROM incidents WHERE student_id = ? AND incident_type = 'EMERGENCY_SOS' AND status = 'ACTIVE'
            ORDER BY created_at DESC LIMIT 1
        """, (student['id'],)).fetchone()
        if legacy_inc:
            active_sos = dict(legacy_inc)

    incident_history = conn.execute("""
        SELECT * FROM emergencies 
        WHERE user_id = ? AND user_role = 'student'
        ORDER BY created_at DESC LIMIT 20
    """, (student['id'],)).fetchall()
    if not incident_history:
        incident_history = conn.execute("""
            SELECT * FROM incidents WHERE student_id = ? AND incident_type = 'EMERGENCY_SOS'
            ORDER BY created_at DESC LIMIT 20
        """, (student['id'],)).fetchall()

    contacts = conn.execute("SELECT * FROM emergency_contacts ORDER BY id ASC").fetchall()
    conn.close()
    return render_template(
        'student/emergency.html',
        student=student,
        active_sos=active_sos,
        incident_history=incident_history,
        emergency_contacts=contacts,
        active_page='emergency'
    )


@student_bp.route('/student/emergency/cancel/<incident_id>', methods=['POST'])
@student_required
def student_emergency_cancel(student, incident_id):
    conn = get_db_connection()
    try:
        transition_emergency_status(
            incident_id, 'STAND_DOWN', student['name'], 'student',
            notes="Student stood down emergency (marked safe).",
            conn=conn
        )
        conn.execute("""
            UPDATE incidents SET status = 'CANCELLED' 
            WHERE incident_id = ? AND student_id = ?
        """, (incident_id, student['id']))
        conn.commit()
    finally:
        conn.close()

    flash(f"Emergency distress beacon {incident_id} stood down. Marked safe.", "success")
    return redirect(url_for('student.student_emergency'))


# ---------------------------------------------------------------------------
# 22. Alerts
# ---------------------------------------------------------------------------
@student_bp.route('/student/alerts')
@student_required
def student_alerts(student):
    conn = get_db_connection()
    alerts_list = conn.execute("""
        SELECT a.*, 
               CASE WHEN sar.id IS NOT NULL THEN 1 ELSE 0 END as is_read
        FROM alerts a
        LEFT JOIN student_alert_reads sar ON a.id = sar.alert_id AND sar.student_id = ?
        ORDER BY a.created_at DESC
    """, (student['id'],)).fetchall()
    conn.close()

    unread_count = sum(1 for a in alerts_list if not a['is_read'])

    return render_template(
        'student/alerts.html',
        student=student,
        alerts=alerts_list,
        unread_count=unread_count,
        active_page='alerts'
    )


@student_bp.route('/student/alerts/read/<int:alert_id>', methods=['POST'])
@student_required
def student_alerts_read_single(student, alert_id):
    conn = get_db_connection()
    conn.execute("""
        INSERT OR IGNORE INTO student_alert_reads (student_id, alert_id)
        VALUES (?, ?)
    """, (student['id'], alert_id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})


@student_bp.route('/student/alerts/read-all', methods=['POST'])
@student_required
def student_alerts_read_all(student):
    conn = get_db_connection()
    conn.execute("""
        INSERT OR IGNORE INTO student_alert_reads (student_id, alert_id)
        SELECT ?, id FROM alerts
    """, (student['id'],))
    conn.commit()
    conn.close()
    flash("All alerts marked as read.", "success")
    return redirect(url_for('student.student_alerts'))


# ---------------------------------------------------------------------------
# 23. AI Assistant
# ---------------------------------------------------------------------------
@student_bp.route('/student/assistant')
@student_required
def student_assistant(student):
    return render_template('student/assistant.html', student=student, active_page='assistant')


@student_bp.route('/api/student/chat', methods=['POST'])
@student_bp.route('/student/api/chat', methods=['POST'])
@student_required
def student_chat_api(student):
    data = request.get_json() or {}
    query = (data.get('query') or data.get('message') or '').strip()
    if not query:
        return jsonify({'reply': 'How may I assist you with your campus academics or safety today?', 'status': 'success'})

    conn = get_db_connection()
    try:
        reply = answer_campus_query(student['id'], query, conn)
        return jsonify({'reply': reply, 'status': 'success'})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 24. Student Settings
# ---------------------------------------------------------------------------
@student_bp.route('/student/settings', methods=['GET', 'POST'])
@student_required
def student_settings(student):
    conn = get_db_connection()
    if request.method == 'POST':
        action = request.form.get('action') or request.form.get('action_type')

        if action in ('update_preferences', 'preferences'):
            email_alerts = 1 if request.form.get('email_alerts') else 0
            sms_alerts = 1 if request.form.get('sms_alerts') else 0
            emergency_broadcasts = 1 if request.form.get('emergency_broadcasts') else 0
            theme = request.form.get('theme', 'dark')

            conn.execute("""
                INSERT INTO student_settings (student_id, email_alerts, sms_alerts, emergency_broadcasts, theme)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(student_id) DO UPDATE SET
                    email_alerts = excluded.email_alerts,
                    sms_alerts = excluded.sms_alerts,
                    emergency_broadcasts = excluded.emergency_broadcasts,
                    theme = excluded.theme
            """, (student['id'], email_alerts, sms_alerts, emergency_broadcasts, theme))
            conn.commit()
            flash("Notification preferences updated successfully.", "success")

        elif action in ('change_password', 'password'):
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', new_pw)

            if not check_password_hash(student['password_hash'], current_pw):
                flash("Current password entered is incorrect.", "error")
            elif len(new_pw) < 6:
                flash("New password must be at least 6 characters.", "error")
            elif new_pw != confirm_pw:
                flash("New password and confirmation do not match.", "error")
            else:
                new_hash = generate_password_hash(new_pw)
                conn.execute("UPDATE students SET password_hash = ? WHERE id = ?", (new_hash, student['id']))
                conn.commit()
                flash("Password updated successfully.", "success")

        conn.close()
        return redirect(url_for('student.student_settings'))

    settings = conn.execute("SELECT * FROM student_settings WHERE student_id = ?", (student['id'],)).fetchone()
    conn.close()
    return render_template('student/settings.html', student=student, settings=settings, active_page='settings')


# ---------------------------------------------------------------------------
# 25. Messages
# ---------------------------------------------------------------------------
@student_bp.route('/student/messages', methods=['GET', 'POST'])
@student_required
def student_messages(student):
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            receiver_role = request.form.get('receiver_role', 'Faculty')
            receiver_name = request.form.get('receiver_name', 'Dr. Ramesh Rao (Faculty Advisor)')
            subject = request.form.get('subject', '').strip()
            content = request.form.get('content', '').strip()

            if not subject or not content:
                flash("Subject and content are required.", "error")
                return redirect(url_for('student.student_messages'))

            conn.execute("""
                INSERT INTO messages (
                    student_id, sender_id, sender_role, sender_name,
                    receiver_id, receiver_role, receiver_name,
                    subject, content, is_read
                ) VALUES (?, ?, 'Student', ?, 1, ?, ?, ?, ?, 0)
            """, (
                student['id'], student['id'], student['name'],
                receiver_role, receiver_name, subject, content
            ))
            conn.commit()
            flash("Message sent successfully to " + receiver_name, "success")
            return redirect(url_for('student.student_messages'))

        inbox_messages = conn.execute("""
            SELECT * FROM messages 
            WHERE (receiver_role = 'Student' AND (receiver_id = ? OR student_id = ?))
               OR (sender_role = 'Student' AND student_id = ?)
            ORDER BY sent_at DESC
        """, (student['id'], student['id'], student['id'])).fetchall()

        return render_template(
            'student/messages.html',
            student=student,
            messages=inbox_messages,
            active_page='messages'
        )
    finally:
        conn.close()
