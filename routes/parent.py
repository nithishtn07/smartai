import os
import re
import uuid
import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database.db import get_db_connection
from utils.decorators import parent_required
from services.attendance_ai import analyze_student_attendance
from services.briefing_ai import generate_student_briefing
from services.emergency_service import get_student_latest_emergency, get_parent_ward_emergency
from services.payment_service import (
    create_fee_order,
    verify_and_record_payment,
    get_student_fee_summary,
    get_payment_receipt,
    RAZORPAY_KEY_ID
)
from services.notification_service import (
    notify_parent,
    notify_student,
    notify_admin,
    log_activity
)

parent_bp = Blueprint('parent', __name__)


@parent_bp.app_context_processor
def inject_parent_context():
    from flask import g
    return {
        'linked_students': getattr(g, 'linked_students', []),
        'active_ward': getattr(g, 'student', None)
    }


# ---------------------------------------------------------------------------
# 0. Switch Active Student (Multi-Child Ward Navigation)
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/switch-student/<int:student_id>', methods=['GET', 'POST'])
@parent_required
def parent_switch_student(parent, student, student_id):
    conn = get_db_connection()
    try:
        # Check authorization strictly from database
        is_linked = conn.execute("""
            SELECT 1 FROM parent_student WHERE parent_id = ? AND student_id = ?
            UNION
            SELECT 1 FROM parents WHERE id = ? AND student_id = ?
        """, (parent['id'], student_id, parent['id'], student_id)).fetchone()

        if not is_linked:
            flash("Unauthorized access: Student is not linked to your parent account.", "error")
            return redirect(url_for('parent.parent_dashboard'))

        target_student = conn.execute("SELECT name FROM students WHERE id = ? AND status != 'DELETED'", (student_id,)).fetchone()
        if not target_student:
            flash("Selected student record is inactive or unavailable.", "error")
            return redirect(url_for('parent.parent_dashboard'))

        session['parent_active_student_id'] = student_id
        flash(f"✓ Switched view to {target_student['name']}.", "success")
        return redirect(request.referrer or url_for('parent.parent_dashboard'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1. Parent Dashboard
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/dashboard')
@parent_required
def parent_dashboard(parent, student):
    conn = get_db_connection()
    try:
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

        fee_summary = get_student_fee_summary(student['id'])
        total_fees = fee_summary['total_billed']
        total_paid = fee_summary['total_paid']
        pending_fees_total = fee_summary['total_pending']

        marks = conn.execute("SELECT * FROM marks WHERE student_id = ?", (student['id'],)).fetchall()
        leaves = conn.execute("SELECT * FROM hostel_leaves WHERE student_id = ? ORDER BY created_at DESC LIMIT 5", (student['id'],)).fetchall()
        pending_leaves_count = sum(1 for l in leaves if l['status'] == 'Pending')
        unread_alerts_count = conn.execute("SELECT COUNT(*) as cnt FROM alerts").fetchone()['cnt']
        recent_alerts = conn.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 3").fetchall()

        upcoming_exams_count = conn.execute("SELECT COUNT(*) as cnt FROM examinations").fetchone()['cnt']
        next_exam = conn.execute("SELECT * FROM examinations ORDER BY exam_date ASC LIMIT 1").fetchone()
        pending_assignments_count = conn.execute("SELECT COUNT(*) as cnt FROM assignments WHERE status != 'Evaluated'").fetchone()['cnt']

        emg_status = get_student_latest_emergency(student['id'], conn)
        active_sos = emg_status if emg_status.get('is_active') else None
        latest_resolved_sos = emg_status if (emg_status.get('has_emergency') and not emg_status.get('is_active')) else None

        active_safewalk = conn.execute("""
            SELECT * FROM safe_walk_sessions WHERE student_id = ? AND status = 'IN_PROGRESS'
            ORDER BY created_at DESC LIMIT 1
        """, (student['id'],)).fetchone()

        announcements = conn.execute("SELECT * FROM announcements ORDER BY created_at DESC LIMIT 3").fetchall()

        return render_template(
            'parent/dashboard.html',
            parent=parent,
            student=student,
            overall_pct=overall_pct,
            att_analysis=att_analysis,
            today_classes=today_classes,
            pending_fees_total=pending_fees_total,
            total_pending=pending_fees_total,
            total_paid=total_paid,
            marks=marks,
            leaves=leaves,
            pending_leaves_count=pending_leaves_count,
            unread_alerts_count=unread_alerts_count,
            recent_alerts=recent_alerts,
            upcoming_exams_count=upcoming_exams_count,
            next_exam=next_exam,
            pending_assignments_count=pending_assignments_count,
            active_sos=active_sos,
            latest_resolved_sos=latest_resolved_sos,
            latest_sos=emg_status,
            active_safewalk=active_safewalk,
            announcements=announcements,
            active_page='dashboard'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 2. Child Academics & Grades
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/academics')
@parent_required
def parent_academics(parent, student):
    conn = get_db_connection()
    try:
        courses = conn.execute("SELECT * FROM courses ORDER BY course_code ASC").fetchall()
        marks = conn.execute("""
            SELECT m.*, COALESCE(c.credits, 4) as credits
            FROM marks m
            LEFT JOIN courses c ON m.course_code = c.course_code
            WHERE m.student_id = ?
            ORDER BY m.course_code ASC
        """, (student['id'],)).fetchall()
        s_grades = sum(1 for m in marks if m['grade'] in ['S', 'O'])
        a_plus_grades = sum(1 for m in marks if m['grade'] in ['A+', 'A'])
        return render_template(
            'parent/academics.html',
            parent=parent,
            student=student,
            courses=courses,
            marks=marks,
            s_grades=s_grades,
            a_plus_grades=a_plus_grades,
            active_page='academics'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 3. Child Attendance Analytics
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/attendance')
@parent_required
def parent_attendance(parent, student):
    conn = get_db_connection()
    try:
        records = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (student['id'],)).fetchall()
        logs = conn.execute("SELECT * FROM attendance_logs WHERE student_id = ? ORDER BY date DESC LIMIT 15", (student['id'],)).fetchall()
        att_analysis = analyze_student_attendance(records)

        return render_template(
            'parent/attendance.html',
            parent=parent,
            student=student,
            records=records,
            attendance_logs=logs,
            att_analysis=att_analysis,
            total_held=att_analysis['total_held'],
            total_attended=att_analysis['total_attended'],
            total_missed=att_analysis['total_missed'],
            overall_pct=att_analysis['overall_pct'],
            active_page='attendance'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 4. Child College Fee Center & Online Payment Portal
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/fees')
@parent_required
def parent_fees(parent, student):
    conn = get_db_connection()
    try:
        # Fetch all linked students for this parent account (Multi-child support)
        linked_students = conn.execute("""
            SELECT s.*, p.relationship, p.id as parent_record_id
            FROM parents p
            JOIN students s ON p.student_id = s.id
            WHERE LOWER(p.email) = LOWER(?) OR p.id = ?
        """, (parent['email'], parent['id'])).fetchall()
        linked_students = [dict(ls) for ls in linked_students]
    finally:
        conn.close()

    # Active student selection from query parameter ?student_id=X
    active_student = dict(student)
    req_stu_id = request.args.get('student_id')
    if req_stu_id and req_stu_id.isdigit():
        selected_id = int(req_stu_id)
        for ls in linked_students:
            if ls['id'] == selected_id:
                active_student = ls
                break

    fee_summary = get_student_fee_summary(active_student['id'])

    return render_template(
        'parent/fees.html',
        parent=parent,
        student=active_student,
        linked_students=linked_students,
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
        razorpay_key_id=RAZORPAY_KEY_ID,
        active_page='fees'
    )


@parent_bp.route('/api/parent/fees/demo-pay', methods=['POST'])
@parent_required
def api_parent_fees_demo_pay(parent, student):
    data = request.get_json() or {}
    fee_id = data.get('fee_id')
    fee_ids = data.get('fee_ids')
    req_stu_id = data.get('student_id')
    amount = data.get('amount')
    payment_method = data.get('payment_method', 'Demo UPI (Google Pay)')
    simulate_failure = bool(data.get('simulate_failure', False))

    if simulate_failure:
        return jsonify({
            'success': False,
            'error': 'Simulated Payment Failure: The demo banking gateway declined the transaction for testing.'
        }), 400

    target_student_id = student['id']
    if req_stu_id and str(req_stu_id).isdigit():
        target_student_id = int(req_stu_id)

    conn = get_db_connection()
    try:
        # Authorization check
        authorized = conn.execute("""
            SELECT 1 FROM parents 
            WHERE (id = ? OR LOWER(email) = LOWER(?)) AND student_id = ?
        """, (parent['id'], parent['email'], target_student_id)).fetchone()
        if not authorized:
            return jsonify({'success': False, 'error': 'Unauthorized access: Parent is not linked to this student record.'}), 403

        target_fee_ids = []
        if fee_ids:
            if isinstance(fee_ids, list):
                target_fee_ids = [int(fid) for fid in fee_ids if str(fid).strip().isdigit()]
            elif isinstance(fee_ids, str):
                target_fee_ids = [int(fid.strip()) for fid in fee_ids.split(',') if fid.strip().isdigit()]
        elif fee_id:
            target_fee_ids = [int(fee_id)]

        if not target_fee_ids:
            return jsonify({'success': False, 'error': 'At least one valid fee ID is required for demo payment.'}), 400

        placeholders = ','.join(['?'] * len(target_fee_ids))
        fee_records = conn.execute(
            f"SELECT * FROM fees WHERE id IN ({placeholders}) AND student_id = ?",
            target_fee_ids + [target_student_id]
        ).fetchall()

        if not fee_records or len(fee_records) != len(target_fee_ids):
            return jsonify({'success': False, 'error': 'One or more fee records could not be found.'}), 400

        total_due = sum(max(0.0, f['amount'] - f['paid_amount']) for f in fee_records)
        if total_due <= 0:
            return jsonify({'success': False, 'error': 'This fee has already been fully paid.'}), 400

        try:
            pay_amt = min(float(amount), total_due) if (amount is not None and float(amount) > 0) else total_due
        except (ValueError, TypeError):
            pay_amt = total_due

        remaining_dist = pay_amt
        fee_names = []
        overall_status = 'PAID'

        for f in fee_records:
            fee_names.append(f['fee_type'])
            item_due = max(0.0, f['amount'] - f['paid_amount'])
            if remaining_dist <= 0:
                if item_due > 0:
                    overall_status = 'PARTIAL'
                continue

            this_pay = min(remaining_dist, item_due)
            new_paid = f['paid_amount'] + this_pay
            new_status = 'PAID' if new_paid >= f['amount'] else 'PARTIAL'

            conn.execute("UPDATE fees SET paid_amount = ?, status = ? WHERE id = ?", (new_paid, new_status, f['id']))
            remaining_dist -= this_pay
            if new_status != 'PAID':
                overall_status = 'PARTIAL'

        now_dt = datetime.datetime.now()
        txn_id = f"DEMO-TXN-{now_dt.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        receipt_no = f"REC-DEMO-{now_dt.strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
        paid_at = now_dt.strftime('%Y-%m-%d %H:%M:%S')
        fee_title = ", ".join(fee_names)

        conn.execute("""
            INSERT INTO payment_transactions (
                transaction_id, student_id, fee_type, amount, payment_method,
                receipt_no, paid_at, status, parent_id, fee_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'SUCCESS', ?, ?)
        """, (txn_id, target_student_id, fee_title, pay_amt, payment_method, receipt_no, paid_at, parent['id'], target_fee_ids[0]))
        conn.commit()

        notify_parent(parent['id'], f"Demo Payment Received: {fee_title}", f"Simulated payment of INR {pay_amt:,.2f} towards {fee_title} was successful (Receipt #{receipt_no}).", category='Fees')
        notify_student(target_student_id, f"Demo Fee Settled: INR {pay_amt:,.2f}", f"Your parent {parent['name']} paid INR {pay_amt:,.2f} towards {fee_title} (Receipt #{receipt_no}).", category='Fees')
        notify_admin(f"Demo Fee Collection: INR {pay_amt:,.2f}", f"Parent {parent['name']} settled INR {pay_amt:,.2f} for Student {student['name']} (Receipt #{receipt_no}).", category='Finance')

        log_activity(parent['name'], 'parent', 'DEMO_FEE_PAYMENT', f"Simulated fee payment of INR {pay_amt} for {fee_title} (Receipt #{receipt_no})", record_id=receipt_no)

        updated_selected = conn.execute(f"SELECT amount, paid_amount FROM fees WHERE id IN ({placeholders})", target_fee_ids).fetchall()
        rem_balance = sum(max(0.0, f['amount'] - f['paid_amount']) for f in updated_selected)

        return jsonify({
            'success': True,
            'message': 'Demo payment processed successfully.',
            'transaction_id': txn_id,
            'receipt_no': receipt_no,
            'fee_type': fee_title,
            'amount_paid': pay_amt,
            'remaining_balance': rem_balance,
            'status': overall_status,
            'payment_method': payment_method,
            'paid_at': paid_at,
            'student_name': student['name'],
            'receipt_url': url_for('parent.parent_fees_receipt', receipt_no=receipt_no)
        })
    finally:
        conn.close()


@parent_bp.route('/api/parent/fees/create-order', methods=['POST'])
@parent_required
def api_parent_fees_create_order(parent, student):
    data = request.get_json() or {}
    fee_id = data.get('fee_id')
    fee_ids = data.get('fee_ids')
    amount = data.get('amount')
    req_stu_id = data.get('student_id')

    # Resolve target student (ensure parent authorization)
    target_student_id = student['id']
    if req_stu_id and str(req_stu_id).isdigit():
        target_student_id = int(req_stu_id)

    if not fee_id and not fee_ids:
        return jsonify({'success': False, 'error': 'At least one fee item ID is required for checkout.'}), 400

    try:
        pay_amt = float(amount) if amount is not None else None
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid payment amount format.'}), 400

    order_result = create_fee_order(
        parent_id=parent['id'],
        student_id=target_student_id,
        fee_id=fee_id,
        fee_ids=fee_ids,
        payment_amount=pay_amt
    )

    if not order_result.get('success'):
        return jsonify(order_result), 400

    return jsonify(order_result)


@parent_bp.route('/api/parent/fees/verify-payment', methods=['POST'])
@parent_required
def api_parent_fees_verify_payment(parent, student):
    data = request.get_json() or {}
    fee_id = data.get('fee_id')
    fee_ids = data.get('fee_ids')
    order_id = data.get('order_id')
    payment_id = data.get('payment_id') or data.get('razorpay_payment_id')
    signature = data.get('signature') or data.get('razorpay_signature', '')
    payment_method = data.get('payment_method', 'Razorpay Online (UPI/Cards/NetBanking)')
    amount = data.get('amount')
    req_stu_id = data.get('student_id')

    target_student_id = student['id']
    if req_stu_id and str(req_stu_id).isdigit():
        target_student_id = int(req_stu_id)

    if not order_id or not payment_id:
        return jsonify({'success': False, 'error': 'Missing required payment verification tokens.'}), 400

    if not fee_id and not fee_ids:
        return jsonify({'success': False, 'error': 'Fee item reference is required.'}), 400

    try:
        pay_amt = float(amount) if amount is not None else None
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid fee amount format.'}), 400

    verify_result = verify_and_record_payment(
        parent_id=parent['id'],
        student_id=target_student_id,
        fee_id=fee_id,
        fee_ids=fee_ids,
        order_id=order_id,
        payment_id=payment_id,
        signature=signature,
        payment_method=payment_method,
        payment_amount=pay_amt
    )

    if not verify_result.get('success'):
        return jsonify(verify_result), 400

    return jsonify(verify_result)


@parent_bp.route('/api/parent/fees/history', methods=['GET'])
@parent_required
def api_parent_fees_history(parent, student):
    req_stu_id = request.args.get('student_id')
    target_student_id = student['id']
    if req_stu_id and req_stu_id.isdigit():
        target_student_id = int(req_stu_id)

    search_term = request.args.get('search')
    fee_type = request.args.get('fee_type')
    status = request.args.get('status')
    method = request.args.get('method')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    from services.payment_service import get_filtered_payment_transactions
    transactions = get_filtered_payment_transactions(
        student_id=target_student_id,
        search_term=search_term,
        fee_type=fee_type,
        status=status,
        payment_method=method,
        date_from=date_from,
        date_to=date_to
    )
    return jsonify({'success': True, 'transactions': transactions, 'count': len(transactions)})


@parent_bp.route('/parent/fees/checkout/<int:fee_id>')
@parent_bp.route('/parent/fees/pay/<int:fee_id>')
@parent_required
def parent_fee_checkout(parent, student, fee_id):
    conn = get_db_connection()
    try:
        fee = conn.execute("SELECT * FROM fees WHERE id = ? AND student_id = ?", (fee_id, student['id'])).fetchone()
        if not fee:
            flash("Fee invoice not found or unauthorized.", "error")
            return redirect(url_for('parent.parent_fees'))

        pending_amount = max(0.0, float(fee['amount']) - float(fee['paid_amount']))
        if pending_amount <= 0:
            flash("This fee invoice has already been fully settled.", "info")
            return redirect(url_for('parent.parent_fees'))

        return render_template(
            'parent/fee_checkout.html',
            parent=parent,
            student=student,
            fee=fee,
            pending_amount=pending_amount,
            active_page='fees'
        )
    finally:
        conn.close()


@parent_bp.route('/parent/fees/pay', methods=['POST'])
@parent_required
def parent_fees_pay(parent, student):
    fee_id = request.form.get('fee_id')
    fee_ids = request.form.getlist('fee_ids') or request.form.get('fee_ids')
    payment_mode = request.form.get('payment_mode', 'full')
    custom_amt = request.form.get('custom_amount')
    amount_str = custom_amt if payment_mode == 'custom' and custom_amt else request.form.get('amount')
    payment_method = request.form.get('payment_method', 'Demo UPI (Google Pay)')

    if not fee_id and not fee_ids:
        flash("Please select at least one fee item to pay.", "error")
        return redirect(url_for('parent.parent_fees'))

    try:
        pay_amt = float(amount_str) if amount_str else None
    except (ValueError, TypeError):
        flash("Invalid payment amount entered.", "error")
        return redirect(url_for('parent.parent_fees'))

    # Generate verified payment record
    order_res = create_fee_order(parent['id'], student['id'], fee_id=fee_id, fee_ids=fee_ids, payment_amount=pay_amt)
    if not order_res.get('success'):
        flash(order_res.get('error', 'Unable to initiate fee checkout.'), "error")
        return redirect(url_for('parent.parent_fees'))

    order_id = order_res['order_id']
    payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    signature = "test_sandbox_signature"

    verify_res = verify_and_record_payment(
        parent_id=parent['id'],
        student_id=student['id'],
        fee_id=fee_id,
        fee_ids=fee_ids,
        order_id=order_id,
        payment_id=payment_id,
        signature=signature,
        payment_method=payment_method,
        payment_amount=order_res['amount_inr']
    )

    if verify_res.get('success'):
        flash(f"✅ Demo Payment of ₹{verify_res['amount_paid']:,.2f} completed! Official Receipt: #{verify_res['receipt_no']}", "success")
        return redirect(url_for('parent.parent_fees_receipt', receipt_no=verify_res['receipt_no']))
    else:
        flash(verify_res.get('error', 'Payment transaction failed verification.'), "error")
        return redirect(url_for('parent.parent_fees'))


@parent_bp.route('/parent/fees/receipt/<receipt_no>')
@parent_required
def parent_fees_receipt(parent, student, receipt_no):
    receipt = get_payment_receipt(receipt_no, parent_id=parent['id'], student_id=student['id'])
    if not receipt:
        flash("Official payment receipt not found or access unauthorized.", "error")
        return redirect(url_for('parent.parent_fees'))

    return render_template('parent/receipt_view.html', parent=parent, student=student, receipt=receipt, active_page='fees')


@parent_bp.route('/api/parent/fees/webhook', methods=['POST'])
@parent_bp.route('/api/payment/razorpay/webhook', methods=['POST'])
def razorpay_webhook():
    webhook_signature = request.headers.get('X-Razorpay-Signature', '')
    raw_body = request.get_data()

    from services.payment_service import process_razorpay_webhook
    result = process_razorpay_webhook(raw_body, webhook_signature)
    if result.get('success'):
        return jsonify(result), 200
    return jsonify(result), 400


# ---------------------------------------------------------------------------
# 5. Child Examination Schedules
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/exams')
@parent_required
def parent_exams(parent, student):
    conn = get_db_connection()
    try:
        exams = conn.execute("SELECT * FROM examinations ORDER BY exam_date ASC").fetchall()
        att_rows = conn.execute("SELECT attendance_pct FROM attendance WHERE student_id = ?", (student['id'],)).fetchall()
        overall_pct = round(sum(r['attendance_pct'] for r in att_rows) / len(att_rows), 1) if att_rows else 0.0
        eligible_for_exams = (overall_pct >= 75.0)

        return render_template(
            'parent/exams.html',
            parent=parent,
            student=student,
            exams=exams,
            overall_pct=overall_pct,
            eligible_for_exams=eligible_for_exams,
            active_page='exams'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 6. Child Weekly Timetable
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/timetable')
@parent_required
def parent_timetable(parent, student):
    conn = get_db_connection()
    try:
        current_day = datetime.datetime.now().strftime('%A')
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

        return render_template(
            'parent/timetable.html',
            parent=parent,
            student=student,
            weekly_classes=weekly_classes,
            current_day=current_day,
            active_page='timetable'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 7. Outpass & Leaves Review
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/leave')
@parent_required
def parent_leave(parent, student):
    conn = get_db_connection()
    try:
        leaves = conn.execute("SELECT * FROM hostel_leaves WHERE student_id = ? ORDER BY created_at DESC", (student['id'],)).fetchall()
        hostel = {'block_name': 'Hostel Block B (Room 304)', 'room_number': '304'}
        return render_template(
            'parent/leave.html',
            parent=parent,
            student=student,
            leaves=leaves,
            hostel=hostel,
            active_page='leave'
        )
    finally:
        conn.close()


@parent_bp.route('/parent/leave/action/<int:leave_id>', methods=['POST'])
@parent_required
def parent_leave_action(parent, student, leave_id):
    action = request.form.get('action', 'Approve')
    status_val = 'Parent Approved' if action in ('Approve', 'Parent Approved') else 'Parent Rejected'
    conn = get_db_connection()
    try:
        conn.execute("UPDATE hostel_leaves SET status = ? WHERE id = ? AND student_id = ?", (status_val, leave_id, student['id']))
        conn.commit()
        flash("Leave / Outpass request approved with parent authorization.", "success")
        return redirect(url_for('parent.parent_leave'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 8. Notifications & Alerts Center
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/notifications')
@parent_required
def parent_notifications(parent, student):
    conn = get_db_connection()
    try:
        category_filter = request.args.get('category', 'all').strip()
        status_filter = request.args.get('status', 'all').strip()

        query = "SELECT * FROM notifications WHERE recipient_role = 'parent' AND recipient_id = ?"
        params = [parent['id']]

        if category_filter.lower() != 'all':
            query += " AND LOWER(category) = LOWER(?)"
            params.append(category_filter)

        if status_filter == 'unread':
            query += " AND is_read = 0"

        query += " ORDER BY created_at DESC, id DESC"
        notifications_list = conn.execute(query, params).fetchall()

        all_notifs = conn.execute("SELECT * FROM notifications WHERE recipient_role = 'parent' AND recipient_id = ?", (parent['id'],)).fetchall()
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
            'parent/notifications.html',
            parent=parent,
            student=student,
            notifications=notifications_list,
            alerts=notifications_list,
            unread_count=unread_count,
            category_counts=category_counts,
            category_filter=category_filter,
            status_filter=status_filter,
            active_page='notifications'
        )
    finally:
        conn.close()


@parent_bp.route('/parent/notifications/read/<int:alert_id>', methods=['POST'])
@parent_required
def parent_notifications_read_single(parent, student, alert_id):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND recipient_role = 'parent' AND recipient_id = ?", (alert_id, parent['id']))
        conn.commit()
        return jsonify({'status': 'ok', 'message': 'Notification marked as read.'})
    finally:
        conn.close()


@parent_bp.route('/parent/notifications/read-all', methods=['POST'])
@parent_bp.route('/parent/notifications/mark-all-read', methods=['POST'])
@parent_required
def parent_notifications_read_all(parent, student):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE recipient_role = 'parent' AND recipient_id = ?", (parent['id'],))
        conn.commit()
        flash("All parent notifications marked as read.", "success")
        return redirect(url_for('parent.parent_notifications'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 9. Campus Safety & Welfare Verification
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/safety')
@parent_required
def parent_safety(parent, student):
    conn = get_db_connection()
    try:
        contacts = conn.execute("SELECT * FROM emergency_contacts ORDER BY id ASC").fetchall()
        if not contacts:
            contacts = [
                {'service_name': 'Campus Security Command Center', 'role_title': 'Chief Security Officer', 'phone_number': '+91 91234 56780', 'location': 'Main Security Tower', 'icon': '🛡️', 'available_hours': '24/7 Continuous'},
                {'service_name': 'Emergency Medical Health Center', 'role_title': 'Senior Duty Doctor', 'phone_number': '+91 91234 56781', 'location': 'Health Pavilion Block A', 'icon': '🏥', 'available_hours': '24/7 Continuous'},
                {'service_name': "Women's Safety & Anti-Harassment", 'role_title': 'Student Welfare Liaison', 'phone_number': '+91 91234 56782', 'location': 'Admin Building Room 104', 'icon': '👩‍✈️', 'available_hours': '24/7 Helpline'}
            ]
        emg_status = get_student_latest_emergency(student['id'], conn)
        active_sos = emg_status if emg_status.get('is_active') else None
        latest_resolved_sos = emg_status if (emg_status.get('has_emergency') and not emg_status.get('is_active')) else None

        safewalk = conn.execute("""
            SELECT * FROM safe_walk_sessions WHERE student_id = ? AND status = 'IN_PROGRESS'
            ORDER BY created_at DESC LIMIT 1
        """, (student['id'],)).fetchone()

        return render_template(
            'parent/safety.html',
            parent=parent,
            student=student,
            contacts=contacts,
            emergency_contacts=contacts,
            active_sos=active_sos,
            latest_resolved_sos=latest_resolved_sos,
            latest_sos=emg_status,
            safewalk=safewalk,
            active_page='safety'
        )
    finally:
        conn.close()


@parent_bp.route('/parent/safety/check-in', methods=['POST'])
@parent_required
def parent_safety_checkin(parent, student):
    flash("Welfare Check Request transmitted to Campus Security Command Quick Response Team.", "success")
    return redirect(url_for('parent.parent_safety'))


# ---------------------------------------------------------------------------
# 10. Direct Messages with Faculty & Wardens
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/messages', methods=['GET', 'POST'])
@parent_required
def parent_messages(parent, student):
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            sender_role = "Parent (" + parent['name'] + ")"
            receiver_name = request.form.get('receiver_name', 'Dr. Ramesh Rao (Faculty Advisor)')
            subject = request.form.get('subject', '').strip()
            content = request.form.get('content', '').strip()

            conn.execute("""
                INSERT INTO parent_messages (parent_id, student_id, sender_role, sender_name, receiver_name, subject, content)
                VALUES (?, ?, 'Parent', ?, ?, ?, ?)
            """, (parent['id'], student['id'], parent['name'], receiver_name, subject, content))

            # Mirror to unified messages
            conn.execute("""
                INSERT INTO messages (student_id, sender_id, sender_role, sender_name, receiver_id, receiver_role, receiver_name, subject, content)
                VALUES (?, ?, 'Parent', ?, 1, 'Faculty', ?, ?, ?)
            """, (student['id'], parent['id'], parent['name'], receiver_name, subject, content))

            conn.commit()
            flash(f"Message successfully transmitted to {receiver_name}.", "success")
            return redirect(url_for('parent.parent_messages'))

        messages = conn.execute("""
            SELECT * FROM parent_messages 
            WHERE parent_id = ? OR student_id = ? 
            ORDER BY sent_at DESC
        """, (parent['id'], student['id'])).fetchall()

        return render_template(
            'parent/messages.html',
            parent=parent,
            student=student,
            messages=messages,
            active_page='messages'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 11. Parent Profile Management & Account Security
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/profile', methods=['GET', 'POST'])
@parent_required
def parent_profile(parent, student):
    conn = get_db_connection()
    try:
        hostel = conn.execute("SELECT * FROM hostel_details WHERE student_id = ?", (student['id'],)).fetchone()

        if request.method == 'POST':
            action_type = request.form.get('action_type', 'update_profile')

            # 1. Update Profile Personal & Contact Information
            if action_type in ('update_profile', 'update_info'):
                name = (request.form.get('name') or parent['name'] or '').strip()
                email = (request.form.get('email') or parent['email'] or '').strip()
                phone = (request.form.get('phone') or parent['phone'] or '').strip()
                alt_phone = request.form.get('alt_phone', parent['alt_phone'] if 'alt_phone' in parent.keys() else '').strip()
                relationship = (request.form.get('relationship') or parent['relationship'] or 'Father').strip()
                occupation = request.form.get('occupation', parent['occupation'] or '').strip()
                address = request.form.get('address', parent['address'] or '').strip()
                city = request.form.get('city', parent['city'] if 'city' in parent.keys() else '').strip()
                state = request.form.get('state', parent['state'] if 'state' in parent.keys() else '').strip()
                country = request.form.get('country', parent['country'] if 'country' in parent.keys() else 'India').strip()
                postal_code = request.form.get('postal_code', parent['postal_code'] if 'postal_code' in parent.keys() else '').strip()

                # Server-Side Validations
                if not name or len(name) < 2:
                    flash("Please enter a valid full name (minimum 2 characters).", "error")
                    return redirect(url_for('parent.parent_profile'))

                if not email or not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
                    flash("Please enter a valid email address.", "error")
                    return redirect(url_for('parent.parent_profile'))

                # Check for duplicate email across other parent accounts
                dup_parent = conn.execute(
                    "SELECT id FROM parents WHERE LOWER(email) = LOWER(?) AND id != ?",
                    (email, parent['id'])
                ).fetchone()
                if dup_parent:
                    flash("This email address is already registered to another parent account.", "error")
                    return redirect(url_for('parent.parent_profile'))

                # Phone validation (allow digits, plus, hyphens, spaces; min 7 digits)
                digits_only = re.sub(r'\D', '', phone)
                if not phone or len(digits_only) < 7 or len(digits_only) > 15:
                    flash("Please enter a valid primary phone number (7 to 15 digits).", "error")
                    return redirect(url_for('parent.parent_profile'))

                if alt_phone:
                    alt_digits = re.sub(r'\D', '', alt_phone)
                    if len(alt_digits) < 7 or len(alt_digits) > 15:
                        flash("Please enter a valid alternate phone number.", "error")
                        return redirect(url_for('parent.parent_profile'))

                if len(address) > 300:
                    flash("Address cannot exceed 300 characters.", "error")
                    return redirect(url_for('parent.parent_profile'))

                # Update database record
                conn.execute("""
                    UPDATE parents 
                    SET name = ?, email = ?, phone = ?, alt_phone = ?, relationship = ?,
                        occupation = ?, address = ?, city = ?, state = ?, country = ?, postal_code = ?
                    WHERE id = ?
                """, (name, email, phone, alt_phone, relationship, occupation, address, city, state, country, postal_code, parent['id']))

                # Keep student emergency parent contact synced
                conn.execute("""
                    UPDATE students SET parent_name = ?, parent_phone = ? WHERE id = ?
                """, (name, phone, student['id']))

                conn.commit()
                if action_type == 'update_info':
                    flash("Parent profile contact details updated successfully.", "success")
                else:
                    flash("✓ Parent profile information updated successfully.", "success")
                return redirect(url_for('parent.parent_profile'))

            # 2. Upload / Change Profile Photo
            elif action_type == 'upload_photo':
                file = request.files.get('profile_photo') or request.files.get('profile_image')
                if not file or file.filename == '':
                    flash("Please select an image file to upload.", "error")
                    return redirect(url_for('parent.parent_profile'))

                allowed_exts = {'jpg', 'jpeg', 'png', 'webp'}
                ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
                if ext not in allowed_exts:
                    flash("Invalid file type. Allowed formats: JPG, JPEG, PNG, WEBP.", "error")
                    return redirect(url_for('parent.parent_profile'))

                # Verify file size (max 2MB)
                file.seek(0, os.SEEK_END)
                size_bytes = file.tell()
                file.seek(0)
                if size_bytes > 2 * 1024 * 1024:
                    flash("File size exceeds maximum allowed limit (2MB).", "error")
                    return redirect(url_for('parent.parent_profile'))

                # Ensure upload folder exists
                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profile')
                os.makedirs(upload_dir, exist_ok=True)

                safe_name = f"parent_{parent['id']}_{uuid.uuid4().hex[:8]}.{ext}"
                save_path = os.path.join(upload_dir, safe_name)
                file.save(save_path)

                web_path = f"/static/uploads/profile/{safe_name}"
                conn.execute("UPDATE parents SET profile_image = ? WHERE id = ?", (web_path, parent['id']))
                conn.commit()

                flash("✓ Profile photo uploaded and updated successfully.", "success")
                return redirect(url_for('parent.parent_profile'))

            # 3. Remove Profile Photo
            elif action_type == 'remove_photo':
                conn.execute("UPDATE parents SET profile_image = '' WHERE id = ?", (parent['id'],))
                conn.commit()
                flash("✓ Profile photo removed. Default initials avatar active.", "success")
                return redirect(url_for('parent.parent_profile'))

            # 4. Change Account Password
            elif action_type == 'change_password':
                current_pw = request.form.get('current_password', '').strip()
                new_pw = request.form.get('new_password', '').strip()
                confirm_pw = request.form.get('confirm_password', '').strip()

                if not current_pw or not new_pw or not confirm_pw:
                    flash("Please fill in all password fields.", "error")
                    return redirect(url_for('parent.parent_profile'))

                if not check_password_hash(parent['password_hash'], current_pw):
                    flash("Current password entered is incorrect.", "error")
                    return redirect(url_for('parent.parent_profile'))

                if len(new_pw) < 6:
                    flash("New password must be at least 6 characters long.", "error")
                    return redirect(url_for('parent.parent_profile'))

                if new_pw != confirm_pw:
                    flash("New password and confirmation password do not match.", "error")
                    return redirect(url_for('parent.parent_profile'))

                new_hash = generate_password_hash(new_pw)
                conn.execute("UPDATE parents SET password_hash = ? WHERE id = ?", (new_hash, parent['id']))
                conn.commit()
                flash("✓ Account password updated successfully!", "success")
                return redirect(url_for('parent.parent_profile'))

        current_parent = conn.execute("SELECT * FROM parents WHERE id = ?", (parent['id'],)).fetchone()

        return render_template(
            'parent/profile.html',
            parent=current_parent,
            student=student,
            hostel=hostel or {},
            active_page='profile'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 11. Parent AI Campus Assistant
# ---------------------------------------------------------------------------
@parent_bp.route('/parent/assistant')
@parent_required
def parent_assistant(parent, student):
    return render_template(
        'parent/assistant.html',
        parent=parent,
        student=student,
        active_page='assistant'
    )


@parent_bp.route('/api/parent/chat', methods=['POST'])
@parent_bp.route('/parent/api/chat', methods=['POST'])
@parent_required
def parent_chat_api(parent, student):
    data = request.get_json() or {}
    query = (data.get('query') or data.get('message') or '').strip()

    if not query:
        return jsonify({
            'reply': f"Hello {parent['name']}! How can I help you regarding your ward {student['name']} today?",
            'intent': 'GREETING',
            'status': 'success',
            'suggestions': [
                f"📊 {student['name']}'s Performance",
                f"🟢 {student['name']}'s Attendance",
                f"💰 {student['name']}'s Pending Fees",
                f"📅 {student['name']}'s Timetable"
            ]
        })

    history = session.get('parent_chat_history', [])
    if not isinstance(history, list):
        history = []

    conn = get_db_connection()
    try:
        from services.unified_ai_assistant import process_unified_ai_query
        result = process_unified_ai_query(
            role='parent',
            user_id=parent['id'],
            student_id=student['id'],
            query=query,
            session_history=history[-6:],
            conn=conn
        )

        history.append({'role': 'user', 'content': query})
        history.append({'role': 'assistant', 'content': result.get('reply', '')})
        session['parent_chat_history'] = history[-8:]

        return jsonify(result)
    finally:
        conn.close()


