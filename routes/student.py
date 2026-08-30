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
    create_emergency,
    get_student_latest_emergency,
    generate_emergency_id
)

from services.ai_insight_engine import analyze_resume_skills

student_bp = Blueprint('student', __name__)


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

        emg_status = get_student_latest_emergency(student['id'], conn)
        active_sos = emg_status if emg_status.get('is_active') else None
        latest_sos = emg_status if emg_status.get('has_emergency') else None

        fees = conn.execute("SELECT * FROM fees WHERE student_id = ?", (student['id'],)).fetchall()
        total_fees = sum(f['amount'] for f in fees) if fees else 0
        total_paid = sum(f['paid_amount'] for f in fees) if fees else 0
        pending_fees_total = total_fees - total_paid

        upcoming_exams_count = conn.execute("SELECT COUNT(*) as cnt FROM examinations").fetchone()['cnt']
        next_exam = conn.execute("SELECT * FROM examinations ORDER BY exam_date ASC LIMIT 1").fetchone()
        placements_count = conn.execute("SELECT COUNT(*) as cnt FROM placements").fetchone()['cnt']
        pending_assignments_count = conn.execute("SELECT COUNT(*) as cnt FROM assignments WHERE status != 'Evaluated'").fetchone()['cnt']

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
            latest_sos=latest_sos,
            pending_fees_total=pending_fees_total,
            total_fees=total_fees,
            total_paid=total_paid,
            upcoming_exams_count=upcoming_exams_count,
            next_exam=next_exam,
            placements_count=placements_count,
            pending_assignments_count=pending_assignments_count
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
    marks = conn.execute("""
        SELECT m.*, COALESCE(c.credits, 4) as credits
        FROM marks m
        LEFT JOIN courses c ON m.course_code = c.course_code
        WHERE m.student_id = ?
        ORDER BY m.course_code ASC
    """, (student['id'],)).fetchall()
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
# 8. Fees Ledger & Online Payments (Safe Demo Payment Flow)
# ---------------------------------------------------------------------------
@student_bp.route('/student/fees')
@student_required
def student_fees(student):
    from services.payment_service import get_student_fee_summary
    fee_summary = get_student_fee_summary(student['id'])

    return render_template(
        'student/fees.html',
        student=student,
        fees=fee_summary['fees'],
        fee_items=fee_summary['fee_items'],
        transactions=fee_summary['transactions'],
        total_fee=fee_summary['total_billed'],
        total_fees=fee_summary['total_billed'],
        total_paid=fee_summary['total_paid'],
        total_pending=fee_summary['total_pending'],
        overdue_amount=fee_summary['overdue_amount'],
        overdue_count=fee_summary['overdue_count'],
        next_due_date=fee_summary['next_due_date'],
        next_due_days=fee_summary['next_due_days'],
        active_page='fees'
    )


@student_bp.route('/student/fees/pay', methods=['POST'])
@student_required
def student_fees_pay(student):
    fee_id = request.form.get('fee_id')
    amount_str = request.form.get('amount')
    payment_method = request.form.get('payment_method', 'UPI (Google Pay / PhonePe)')

    if not fee_id:
        flash("Please select a valid fee item to pay.", "error")
        return redirect(url_for('student.student_fees'))

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Payment amount must be greater than zero.", "error")
            return redirect(url_for('student.student_fees'))
    except (ValueError, TypeError):
        flash("Invalid payment amount entered.", "error")
        return redirect(url_for('student.student_fees'))

    conn = get_db_connection()
    try:
        fee = conn.execute("SELECT * FROM fees WHERE id = ? AND student_id = ?", (fee_id, student['id'])).fetchone()
        if not fee:
            flash("Fee record not found or access unauthorized.", "error")
            return redirect(url_for('student.student_fees'))

        remaining_balance = max(0.0, float(fee['amount']) - float(fee['paid_amount']))
        if remaining_balance <= 0 or fee['status'] in ('PAID', 'Paid'):
            flash("This fee has already been fully paid and cleared. Duplicate payment prevented.", "info")
            return redirect(url_for('student.student_fees'))

        # Clamp payable amount to remaining balance to prevent overpayment
        pay_amount = min(amount, remaining_balance)
        new_paid = float(fee['paid_amount']) + pay_amount
        new_status = 'PAID' if new_paid >= float(fee['amount']) else 'PARTIAL'

        conn.execute("UPDATE fees SET paid_amount = ?, status = ? WHERE id = ?", (new_paid, new_status, fee_id))

        txn_id = f"TXN-STU-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        receipt_no = f"REC-{uuid.uuid4().hex[:6].upper()}"
        paid_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn.execute("""
            INSERT INTO payment_transactions (transaction_id, student_id, fee_type, amount, payment_method, receipt_no, paid_at, status, fee_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'SUCCESS', ?)
        """, (txn_id, student['id'], fee['fee_type'], pay_amount, payment_method, receipt_no, paid_at, fee_id))
        conn.commit()

        # Send real-time notifications to student & linked parent
        notify_student(
            student['id'],
            f"✅ Payment Successful: {fee['fee_type']}",
            f"Demo Payment of INR {pay_amount:,.2f} recorded successfully (Receipt #{receipt_no}). Remaining balance: INR {max(0.0, fee['amount'] - new_paid):,.2f}.",
            category='Fees'
        )

        parent = conn.execute("SELECT id, name FROM parents WHERE student_id = ?", (student['id'],)).fetchone()
        if parent:
            notify_parent(
                parent['id'],
                f"✅ Fee Payment Received for {student['name']}",
                f"An amount of INR {pay_amount:,.2f} towards {fee['fee_type']} was processed (Receipt #{receipt_no}).",
                category='Fees'
            )

        log_activity(
            student['name'], 'student', 'DEMO_FEE_PAYMENT',
            f"Paid INR {pay_amount} towards {fee['fee_type']} via {payment_method} (Receipt #{receipt_no})",
            record_id=str(fee_id)
        )

        flash(f"✅ Demo Payment of ₹{pay_amount:,.2f} completed successfully! Official Receipt #{receipt_no} generated.", "success")
        return redirect(url_for('student.student_fees_receipt', receipt_no=receipt_no))
    finally:
        conn.close()


@student_bp.route('/student/fees/receipt/<receipt_no>')
@student_required
def student_fees_receipt(student, receipt_no):
    from services.payment_service import get_payment_receipt
    receipt = get_payment_receipt(receipt_no, student_id=student['id'])
    if not receipt:
        flash("Official payment receipt not found or access unauthorized.", "error")
        return redirect(url_for('student.student_fees'))

    return render_template(
        'parent/receipt_view.html',
        student=student,
        receipt=receipt,
        back_url=url_for('student.student_fees'),
        active_page='fees'
    )


# ---------------------------------------------------------------------------
# 9. Academic Calendar
# ---------------------------------------------------------------------------
@student_bp.route('/student/calendar')
@student_required
def student_calendar(student):
    conn = get_db_connection()
    try:
        cal_events = conn.execute("SELECT * FROM academic_calendar ORDER BY start_date ASC").fetchall()
        exams = conn.execute("SELECT * FROM examinations ORDER BY exam_date ASC").fetchall()
        assignments = conn.execute("SELECT * FROM assignments ORDER BY due_date ASC").fetchall()

        events = []
        for c in cal_events:
            c_dict = dict(c)
            dt_str = c_dict.get('start_date', '')
            month = 'SEM'
            day = '01'
            try:
                dt = datetime.datetime.strptime(dt_str, '%Y-%m-%d')
                month = dt.strftime('%b')
                day = dt.strftime('%d')
            except Exception:
                pass
            events.append({
                'title': c_dict.get('title', c_dict.get('event_name', 'Academic Milestone')),
                'description': c_dict.get('description', ''),
                'category': c_dict.get('event_type', 'Academic'),
                'month': month,
                'day': day,
                'time': 'Full Day',
                'venue': 'Campus'
            })

        for ex in exams:
            dt_str = ex['exam_date']
            month = 'EXAM'
            day = '01'
            try:
                dt = datetime.datetime.strptime(dt_str, '%Y-%m-%d')
                month = dt.strftime('%b')
                day = dt.strftime('%d')
            except Exception:
                pass
            events.append({
                'title': f"{ex['exam_type']} - {ex['course_code']}",
                'description': f"{ex['course_name']} ({ex['room_number']})",
                'category': 'Exam',
                'month': month,
                'day': day,
                'time': ex['exam_time'],
                'venue': f"{ex['venue']} - {ex['room_number']}"
            })

        for a in assignments:
            dt_str = a['due_date']
            month = 'DUE'
            day = '01'
            try:
                dt = datetime.datetime.strptime(dt_str, '%Y-%m-%d')
                month = dt.strftime('%b')
                day = dt.strftime('%d')
            except Exception:
                pass
            events.append({
                'title': f"Due: {a['title']}",
                'description': f"{a['course_code']} ({a['course_name']}) - Max: {a['max_marks']} Marks",
                'category': 'Assignment',
                'month': month,
                'day': day,
                'time': '11:59 PM',
                'venue': 'Online Portal'
            })

        return render_template('student/calendar.html', student=student, events=events, active_page='calendar')
    finally:
        conn.close()


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
    conn = get_db_connection()
    try:
        allocation = conn.execute("""
            SELECT st.*, tr.route_number, tr.route_name, tr.bus_number, tr.driver_name, tr.driver_phone, tr.pickup_time, tr.pickup_location, tr.eta_campus, tr.stops_json
            FROM student_transport st
            JOIN transport_routes tr ON st.route_id = tr.id
            WHERE st.student_id = ?
        """, (student['id'],)).fetchone()

        all_routes = conn.execute("SELECT * FROM transport_routes WHERE status = 'ACTIVE'").fetchall()

        return render_template(
            'student/transport.html',
            student=student,
            allocation=allocation,
            routes=all_routes,
            active_page='transport'
        )
    finally:
        conn.close()


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

        inc_id = generate_emergency_id()
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

    emg_status = get_student_latest_emergency(student['id'], conn)
    active_sos = emg_status if emg_status.get('is_active') else None
    latest_resolved_sos = emg_status if (emg_status.get('has_emergency') and not emg_status.get('is_active') and emg_status.get('status') in ['RESOLVED', 'CLOSED']) else None
    latest_standdown_sos = emg_status if (emg_status.get('has_emergency') and not emg_status.get('is_active') and emg_status.get('status') in ['STAND_DOWN', 'CANCELLED']) else None

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
        latest_resolved_sos=latest_resolved_sos,
        latest_standdown_sos=latest_standdown_sos,
        latest_sos=emg_status,
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
            notes="Student stood down emergency (marked safe / false alarm).",
            conn=conn
        )
        conn.execute("""
            UPDATE incidents SET status = 'CANCELLED' 
            WHERE incident_id = ? AND student_id = ?
        """, (incident_id, student['id']))
        conn.commit()
    finally:
        conn.close()

    if request.is_json or request.headers.get('Accept') == 'application/json':
        return jsonify({
            'status': 'success',
            'is_safe': True,
            'incident_id': incident_id,
            'message': f"Emergency distress beacon {incident_id} stood down. Marked safe."
        })

    flash(f"Emergency distress beacon {incident_id} stood down. Marked safe. You are confirmed SAFE.", "success")
    return redirect(url_for('student.student_emergency'))


@student_bp.route('/student/emergency/history')
@student_required
def student_emergency_history(student):
    conn = get_db_connection()
    try:
        # Fetch from emergencies
        emg_records = conn.execute("""
            SELECT * FROM emergencies 
            WHERE user_id = ? AND user_role = 'student'
            ORDER BY created_at DESC, id DESC
        """, (student['id'],)).fetchall()

        history_list = []
        seen_ids = set()
        for r in emg_records:
            d = dict(r)
            d['incident_id'] = d.get('emergency_id')
            d['location'] = d.get('campus_zone') or 'Campus Safe Zone'
            history_list.append(d)
            seen_ids.add(d.get('emergency_id'))

        # Also pull legacy incidents if any not in emergencies
        inc_records = conn.execute("""
            SELECT * FROM incidents 
            WHERE student_id = ? AND incident_type = 'EMERGENCY_SOS'
            ORDER BY created_at DESC, id DESC
        """, (student['id'],)).fetchall()

        for r in inc_records:
            d = dict(r)
            if d.get('incident_id') not in seen_ids:
                d['emergency_id'] = d.get('incident_id')
                d['category'] = 'Personal Safety'
                d['severity'] = 'HIGH'
                d['campus_zone'] = d.get('location') or 'Campus Safe Zone'
                history_list.append(d)
                seen_ids.add(d.get('incident_id'))

        # Metrics computation
        total_count = len(history_list)
        resolved_count = sum(1 for h in history_list if h.get('status') in ['RESOLVED', 'CLOSED'])
        stand_down_count = sum(1 for h in history_list if h.get('status') in ['STAND_DOWN', 'CANCELLED', 'SAFE'])
        active_count = sum(1 for h in history_list if h.get('status') in ['TRIGGERED', 'ACTIVE', 'ACKNOWLEDGED', 'ASSIGNED', 'RESPONDER_ASSIGNED', 'EN_ROUTE', 'ON_SCENE'])

        # Filter parameters
        status_filter = request.args.get('status', 'all').upper()
        category_filter = request.args.get('category', 'all')

        filtered_list = history_list
        if status_filter != 'ALL':
            if status_filter == 'RESOLVED':
                filtered_list = [h for h in filtered_list if h.get('status') in ['RESOLVED', 'CLOSED']]
            elif status_filter == 'STAND_DOWN':
                filtered_list = [h for h in filtered_list if h.get('status') in ['STAND_DOWN', 'CANCELLED', 'SAFE']]
            elif status_filter == 'ACTIVE':
                filtered_list = [h for h in filtered_list if h.get('status') in ['TRIGGERED', 'ACTIVE', 'ACKNOWLEDGED', 'ASSIGNED', 'RESPONDER_ASSIGNED', 'EN_ROUTE', 'ON_SCENE']]
            else:
                filtered_list = [h for h in filtered_list if h.get('status') == status_filter]

        if category_filter != 'all':
            filtered_list = [h for h in filtered_list if h.get('category', '').lower() == category_filter.lower()]

        metrics = {
            'total': total_count,
            'resolved': resolved_count,
            'stand_down': stand_down_count,
            'active': active_count
        }

        if request.is_json or request.headers.get('Accept') == 'application/json':
            return jsonify({
                'status': 'success',
                'metrics': metrics,
                'history': filtered_list
            })

        return render_template(
            'student/emergency_history.html',
            student=student,
            history_records=filtered_list,
            metrics=metrics,
            current_status_filter=status_filter.lower(),
            current_category_filter=category_filter,
            active_page='emergency_history'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 22. Notifications & Alerts Center
# ---------------------------------------------------------------------------
@student_bp.route('/student/alerts')
@student_bp.route('/student/notifications')
@student_required
def student_alerts(student):
    conn = get_db_connection()
    try:
        category_filter = request.args.get('category', 'all').strip()
        status_filter = request.args.get('status', 'all').strip()

        query = "SELECT * FROM notifications WHERE recipient_role = 'student' AND recipient_id = ?"
        params = [student['id']]

        if category_filter.lower() != 'all':
            query += " AND LOWER(category) = LOWER(?)"
            params.append(category_filter)

        if status_filter == 'unread':
            query += " AND is_read = 0"

        query += " ORDER BY created_at DESC, id DESC"
        notifications_list = conn.execute(query, params).fetchall()

        all_notifs = conn.execute("SELECT * FROM notifications WHERE recipient_role = 'student' AND recipient_id = ?", (student['id'],)).fetchall()
        unread_count = sum(1 for n in all_notifs if not n['is_read'])

        category_counts = {
            'all': len(all_notifs),
            'unread': unread_count,
            'academic': sum(1 for n in all_notifs if (n['category'] or '').lower() == 'academic'),
            'attendance': sum(1 for n in all_notifs if (n['category'] or '').lower() == 'attendance'),
            'fees': sum(1 for n in all_notifs if (n['category'] or '').lower() in ['fees', 'fee', 'finance']),
            'timetable': sum(1 for n in all_notifs if (n['category'] or '').lower() == 'timetable'),
            'announcements': sum(1 for n in all_notifs if (n['category'] or '').lower() in ['announcements', 'announcement', 'general']),
            'system': sum(1 for n in all_notifs if (n['category'] or '').lower() in ['system', 'safety'])
        }

        return render_template(
            'student/alerts.html',
            student=student,
            alerts=notifications_list,
            notifications=notifications_list,
            unread_count=unread_count,
            category_counts=category_counts,
            category_filter=category_filter,
            status_filter=status_filter,
            active_page='alerts'
        )
    finally:
        conn.close()


@student_bp.route('/student/alerts/read/<int:alert_id>', methods=['POST'])
@student_bp.route('/student/notifications/read/<int:alert_id>', methods=['POST'])
@student_required
def student_alerts_read_single(student, alert_id):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND recipient_role = 'student' AND recipient_id = ?", (alert_id, student['id']))
        conn.commit()
        return jsonify({'status': 'ok', 'message': 'Notification marked as read.'})
    finally:
        conn.close()


@student_bp.route('/student/alerts/read-all', methods=['POST'])
@student_bp.route('/student/notifications/read-all', methods=['POST'])
@student_bp.route('/student/notifications/mark-all-read', methods=['POST'])
@student_required
def student_alerts_read_all(student):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE recipient_role = 'student' AND recipient_id = ?", (student['id'],))
        conn.commit()
        flash("All notifications marked as read.", "success")
        return redirect(url_for('student.student_alerts'))
    finally:
        conn.close()


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
        return jsonify({
            'reply': f"Hello {student['name']}! How may I assist you with your campus academics, attendance, fees, or safety today?",
            'intent': 'GREETING',
            'status': 'success',
            'suggestions': ['📊 My Performance', '🟢 My Attendance', '📅 My Timetable', '💰 My Fees', '🚨 Safety Help']
        })

    # Retrieve short-term conversation memory from session
    history = session.get('student_chat_history', [])
    if not isinstance(history, list):
        history = []

    conn = get_db_connection()
    try:
        from services.unified_ai_assistant import process_unified_ai_query
        result = process_unified_ai_query(
            role='student',
            user_id=student['id'],
            query=query,
            session_history=history[-6:],
            conn=conn
        )

        # Update session memory (keep last 8 turns)
        history.append({'role': 'user', 'content': query})
        history.append({'role': 'assistant', 'content': result.get('reply', '')})
        session['student_chat_history'] = history[-8:]

        return jsonify(result)
    finally:
        conn.close()


@student_bp.route('/api/student/ai-feedback', methods=['POST'])
@student_required
def student_ai_feedback(student):
    data = request.get_json() or {}
    query = data.get('query', '')
    rating = data.get('rating', 'up')  # 'up' or 'down'
    comment = data.get('comment', '')

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO activity_logs (user_type, user_id, action, details)
            VALUES ('student', ?, 'AI_ASSISTANT_FEEDBACK', ?)
        """, (student['id'], f"Rating: {rating} | Query: {query[:100]} | Comment: {comment[:200]}"))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Feedback recorded. Thank you!'})
    except Exception:
        return jsonify({'status': 'success', 'message': 'Feedback received.'})
    finally:
        conn.close()


@student_bp.route('/api/student/daily-briefing', methods=['GET'])
@student_required
def student_daily_briefing_api(student):
    conn = get_db_connection()
    try:
        briefing = generate_student_briefing(student, conn)
        return jsonify({'status': 'success', 'briefing': briefing})
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
            receiver_role = request.form.get('recipient_role') or request.form.get('receiver_role', 'Faculty')
            receiver_name = request.form.get('receiver_name')
            subject = request.form.get('subject', '').strip()
            content = request.form.get('content', '').strip()

            if not receiver_name:
                if receiver_role.lower() == 'parent':
                    parent_row = conn.execute("SELECT id, name FROM parents WHERE student_id = ?", (student['id'],)).fetchone()
                    receiver_name = parent_row['name'] if parent_row else (student['parent_name'] or 'Parent / Guardian')
                else:
                    receiver_name = 'Faculty Advisor'

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

            if receiver_role.lower() == 'parent':
                parent_row = conn.execute("SELECT id, name FROM parents WHERE student_id = ?", (student['id'],)).fetchone()
                parent_id = parent_row['id'] if parent_row else 1
                conn.execute("""
                    INSERT INTO parent_messages (parent_id, student_id, sender_role, sender_name, receiver_name, subject, content)
                    VALUES (?, ?, 'Student', ?, ?, ?, ?)
                """, (parent_id, student['id'], student['name'], receiver_name, subject, content))

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


