"""
=============================================================================
CampusGuard AI — Unified Multi-Role AI Assistant Service
=============================================================================
Database-First, Intent-Aware, Role-Isolated Campus Intelligence Engine.
Integrates SQLite ERP records as Single Source of Truth and Google Gemini
as the deep reasoning/advisory layer across Student, Parent, Faculty, and Admin.
=============================================================================
"""

import os
import re
import json
import datetime
from database.db import get_db_connection
from services.ai_service import sanitize_input, query_gemini_api, get_api_key
from services.academic_service import calculate_student_cgpa


# =============================================================================
# 1. System Prompt Builder
# =============================================================================

def build_system_instruction(role: str, user_name: str) -> str:
    return (
        f"You are CampusGuard AI, the official intelligent assistant for the CampusGuard Smart & Safe Campus ERP. "
        f"You are speaking with authenticated {role.upper()}: '{user_name}'.\n\n"
        f"CORE INSTRUCTIONS:\n"
        f"1. The provided Campus Context is extracted directly from the verified CampusGuard relational database and is the absolute single source of truth.\n"
        f"2. NEVER invent, assume, or hallucinate marks, CGPA, attendance %, fee amounts, student names, schedules, or incident logs.\n"
        f"3. If specific student or campus data is missing or empty in the context, explicitly state: 'That information is not available in the official CampusGuard records.'\n"
        f"4. Format your output with clear Markdown headers, bold highlights, and clean bullet points.\n"
        f"5. For safety or distress queries, emphasize campus emergency contacts and direct the user to trigger the CampusGuard SOS Beacon immediately."
    )


# =============================================================================
# 2. Database Factual Data Extractors
# =============================================================================

def get_student_attendance_data(student_id: int, conn) -> dict:
    """Computes exact attendance metrics from attendance table."""
    records = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (student_id,)).fetchall()
    if not records:
        return {'total': 0, 'present': 0, 'absent': 0, 'percentage': 0.0, 'subjects': [], 'lowest_subject': None}

    total_held = sum(r['classes_held'] for r in records)
    total_attended = sum(r['classes_attended'] for r in records)
    total_missed = sum(r['classes_missed'] for r in records)
    overall_pct = round((total_attended / total_held) * 100, 1) if total_held > 0 else 0.0

    sub_list = []
    for r in records:
        pct = float(r['attendance_pct'])
        held = r['classes_held']
        att = r['classes_attended']
        max_absences = int(att / 0.75) - held if pct >= 75.0 else 0
        classes_needed = int((0.75 * held - att) / 0.25) + 1 if pct < 75.0 else 0
        sub_list.append({
            'code': r['subject_code'],
            'subject': r['subject_name'],
            'present': att,
            'total': held,
            'percentage': pct,
            'safe_bunk': max(0, max_absences),
            'needed': max(0, classes_needed),
            'is_shortage': pct < 75.0
        })

    sub_list.sort(key=lambda x: x['percentage'])
    return {
        'total': total_held,
        'present': total_attended,
        'absent': total_missed,
        'percentage': overall_pct,
        'subjects': sub_list,
        'lowest_subject': sub_list[0] if sub_list else None
    }


def get_student_academic_data(student_id: int, conn) -> dict:
    """Computes CGPA, SGPA, and subject grade breakdown from marks & academics."""
    cgpa, earned_credits, _, _ = calculate_student_cgpa(conn, student_id)
    
    marks_rows = conn.execute("""
        SELECT * FROM marks WHERE student_id = ? ORDER BY course_code ASC
    """, (student_id,)).fetchall()

    items = []
    for r in marks_rows:
        total = (float(r['cat1'] or 0) + float(r['cat2'] or 0) + float(r['quiz'] or 0) + 
                 float(r['assignment'] or 0) + float(r['project'] or 0) + float(r['fat'] or 0))
        items.append({
            'code': r['course_code'],
            'name': r['course_name'],
            'cat1': r['cat1'],
            'cat2': r['cat2'],
            'fat': r['fat'],
            'total': round(total, 1),
            'grade': r['grade'],
            'grade_points': r['grade_points'],
            'status': r['status']
        })

    return {
        'cgpa': cgpa if cgpa is not None else 0.0,
        'earned_credits': earned_credits,
        'marks': items,
        'has_records': bool(items or cgpa is not None)
    }


def get_student_fee_data(student_id: int, conn) -> dict:
    """Extracts billed, paid, pending fees and transaction logs."""
    fee_rows = conn.execute("SELECT * FROM fees WHERE student_id = ? ORDER BY due_date ASC", (student_id,)).fetchall()
    tx_rows = conn.execute("SELECT * FROM payment_transactions WHERE student_id = ? ORDER BY paid_at DESC", (student_id,)).fetchall()

    total_billed = sum(float(r['amount'] or 0) for r in fee_rows)
    total_paid = sum(float(r['paid_amount'] or 0) for r in fee_rows)
    total_pending = max(0.0, total_billed - total_paid)

    now_str = datetime.date.today().strftime('%Y-%m-%d')
    overdue_items = [r for r in fee_rows if r['due_date'] < now_str and (float(r['amount'] or 0) - float(r['paid_amount'] or 0)) > 0]
    overdue_amount = sum(float(r['amount'] or 0) - float(r['paid_amount'] or 0) for r in overdue_items)

    next_due = None
    for r in fee_rows:
        if (float(r['amount'] or 0) - float(r['paid_amount'] or 0)) > 0 and r['due_date'] >= now_str:
            next_due = r['due_date']
            break

    return {
        'total_billed': total_billed,
        'total_paid': total_paid,
        'total_pending': total_pending,
        'overdue_amount': overdue_amount,
        'next_due_date': next_due,
        'fee_items': [dict(r) for r in fee_rows],
        'transactions': [dict(r) for r in tx_rows]
    }


def get_student_timetable_data(student_id: int, conn) -> dict:
    """Retrieves weekly and daily timetable schedule."""
    tt_rows = conn.execute("SELECT * FROM timetable ORDER BY day_of_week, start_time").fetchall()
    today_name = datetime.datetime.now().strftime('%A')
    tomorrow_name = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%A')

    today_classes = [dict(r) for r in tt_rows if r['day_of_week'].lower() == today_name.lower()]
    tomorrow_classes = [dict(r) for r in tt_rows if r['day_of_week'].lower() == tomorrow_name.lower()]

    return {
        'today_name': today_name,
        'tomorrow_name': tomorrow_name,
        'today_classes': today_classes,
        'tomorrow_classes': tomorrow_classes,
        'all_classes': [dict(r) for r in tt_rows]
    }


# =============================================================================
# 3. Intent Detection Classifier
# =============================================================================

def classify_query_intent(query: str) -> dict:
    """
    Analyzes student/parent/faculty/admin query to determine:
    1. domain: ATTENDANCE, ACADEMICS, FEES, TIMETABLE, SAFETY, CAMPUS_ADMIN, GENERAL
    2. is_factual: True if simple direct lookup, False if complex reasoning/advice required.
    """
    q = query.lower().strip()

    # Safety / Crisis / SOS
    if any(k in q for k in ['sos', 'emergency', 'help me', 'threat', 'stalk', 'harass', 'fire', 'ambulance', 'police', 'danger', 'attack', 'suicide', 'injury']):
        return {'domain': 'SAFETY', 'is_factual': True, 'intent': 'CRISIS_EMERGENCY'}

    # Timetable / Schedule (Check before general words)
    if any(k in q for k in ['timetable', 'schedule', 'class tomorrow', 'classes tomorrow', 'next class', 'period', 'lecture', 'timing', 'when is my class', 'classes do i have']):
        return {'domain': 'TIMETABLE', 'is_factual': True, 'intent': 'TIMETABLE_FACTUAL'}

    # Attendance
    if any(k in q for k in ['attendance', 'present', 'absent', 'bunk', 'skip', 'miss class', '75%']):
        if any(k in q for k in ['why', 'how to improve', 'advice', 'should i', 'can i miss', 'what if', 'analyze', 'recommend']):
            return {'domain': 'ATTENDANCE', 'is_factual': False, 'intent': 'ATTENDANCE_ANALYSIS'}
        return {'domain': 'ATTENDANCE', 'is_factual': True, 'intent': 'ATTENDANCE_FACTUAL'}

    # CGPA / Marks / Academics / Performance
    if any(k in q for k in ['cgpa', 'sgpa', 'marks', 'grade', 'score', 'credit', 'academic', 'transcript', 'exam', 'perform', 'child doing', 'ward doing', 'my child', 'my ward', 'my son', 'my daughter']):
        if any(k in q for k in ['how am i doing', 'how to improve', 'advice', 'weak', 'strong', 'guide', 'study plan', 'tips', 'why', 'child doing', 'ward doing']):
            return {'domain': 'ACADEMICS', 'is_factual': False, 'intent': 'ACADEMICS_ANALYSIS'}
        return {'domain': 'ACADEMICS', 'is_factual': True, 'intent': 'ACADEMICS_FACTUAL'}

    # Fees / Payment
    if any(k in q for k in ['fee', 'fees', 'tuition', 'paid', 'pending fee', 'due date', 'receipt', 'payment', 'installment', 'overdue']):
        if any(k in q for k in ['explain', 'why', 'breakdown meaning', 'assistance', 'concession']):
            return {'domain': 'FEES', 'is_factual': False, 'intent': 'FEES_ANALYSIS'}
        return {'domain': 'FEES', 'is_factual': True, 'intent': 'FEES_FACTUAL'}

    # Faculty / Admin Aggregate Inquiries
    if any(k in q for k in ['registered student', 'below 75', 'failing', 'class summary', 'total collection', 'how many student', 'incident count']):
        return {'domain': 'CAMPUS_ADMIN', 'is_factual': True, 'intent': 'CAMPUS_ADMIN_FACTUAL'}

    # General Knowledge / Educational
    return {'domain': 'GENERAL', 'is_factual': False, 'intent': 'GENERAL_KNOWLEDGE'}


# =============================================================================
# 4. Role Handlers
# =============================================================================

def handle_student_ai(student_id: int, query: str, history: list, conn) -> dict:
    """Handles query for authenticated Student."""
    stu = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not stu:
        return {'reply': "⚠️ Student profile not found in database.", 'intent': 'ERROR', 'status': 'error'}

    user_name = stu['name']
    intent_info = classify_query_intent(query)
    domain = intent_info['domain']

    # --- A. Safety & Emergency ---
    if domain == 'SAFETY':
        return {
            'reply': (
                "🚨 **EMERGENCY ASSISTANCE INITIATED**\n\n"
                "If you or someone around you is in immediate danger:\n"
                "• 🔴 **[Activate Emergency SOS](/student/safety)** immediately from your Campus Safety portal.\n"
                "• 📞 **Campus Security Helpline:** `+91 98765 43210` / Intercom `2222`\n"
                "• 🏥 **Campus Health Centre:** `+91 98765 43211` / Intercom `108`\n"
                "• 👮 **Women's Safety & Anti-Harassment Cell:** Room 104, Admin Block\n\n"
                "Campus security guards and fast-response officers are automatically dispatched when you press the SOS Beacon."
            ),
            'intent': 'SAFETY_SOS',
            'status': 'success',
            'suggestions': ['🚨 Open Emergency SOS', '📞 Call Security', '🚶‍♀️ Start Safe Walk']
        }

    system_inst = build_system_instruction('student', user_name)

    # --- B. Attendance ---
    if domain == 'ATTENDANCE':
        att = get_student_attendance_data(student_id, conn)
        
        # Build offline fallback
        if att['total'] == 0:
            fallback_reply = f"📋 **Attendance Records for {user_name}:**\nNo attendance logs recorded in the central database yet."
        else:
            lines = [f"📊 **Attendance Overview for {user_name}:** **{att['percentage']}%** ({att['present']}/{att['total']} sessions)\n"]
            for s in att['subjects']:
                status_icon = "🟢" if not s['is_shortage'] else "🔴"
                margin_text = f"Can safely miss {s['safe_bunk']} classes" if not s['is_shortage'] else f"Need to attend {s['needed']} consecutive classes to reach 75%"
                lines.append(f"• {status_icon} **{s['subject']}**: **{s['percentage']}%** ({s['present']}/{s['total']}) — *{margin_text}*")
            if att['lowest_subject']:
                lines.append(f"\n⚠️ **Lowest Subject:** **{att['lowest_subject']['subject']}** at **{att['lowest_subject']['percentage']}%**.")
            fallback_reply = "\n".join(lines)

        context = (
            f"Student Name: {user_name}\n"
            f"Register Number: {stu['register_number']}\n"
            f"Department: {stu['department']}\n"
            f"Overall Attendance: {att['percentage']}% ({att['present']}/{att['total']} sessions attended, {att['absent']} missed)\n"
            f"Attendance Threshold: 75.0%\n"
            f"Subject Attendance Breakdown: {json.dumps(att['subjects'])}\n"
            f"Lowest Attendance Subject: {json.dumps(att['lowest_subject']) if att['lowest_subject'] else 'None'}"
        )
        
        try:
            ai_resp = query_gemini_api(f"Campus Context (Verified Database Records):\n{context}\n\nStudent Question:\n{query}", system_instruction=system_inst)
            if ai_resp:
                return {'reply': ai_resp, 'intent': 'ATTENDANCE_AI', 'status': 'success', 'suggestions': ['Which subject is lowest?', 'What is my CGPA?', 'When is my next class?']}
        except Exception:
            pass

        return {
            'reply': fallback_reply,
            'intent': 'ATTENDANCE_FALLBACK',
            'status': 'success',
            'suggestions': ['Which subject is lowest?', 'What is my CGPA?', 'When is my next class?']
        }

    # --- C. Academics / CGPA / Performance ---
    if domain == 'ACADEMICS':
        acad = get_student_academic_data(student_id, conn)
        att = get_student_attendance_data(student_id, conn)
        
        # Build offline fallback
        if not acad['has_records']:
            fallback_reply = f"🎓 **Academic Record for {user_name}:**\nNo examination grades or marks found in the registrar database."
        else:
            lines = [f"🎓 **Academic Standing for {user_name}:**\n• **Cumulative CGPA:** **{acad['cgpa']}** / 10.0\n• **Earned Credits:** **{acad['earned_credits']}** Credits\n"]
            if acad['marks']:
                lines.append("**Subject Score Breakdown:**")
                for m in acad['marks']:
                    lines.append(f"• **[{m['code']}] {m['name']}**: **{m['total']}/100** (Grade: **{m['grade']}**)")
            fallback_reply = "\n".join(lines)

        context = (
            f"Student Name: {user_name}\n"
            f"Register Number: {stu['register_number']}\n"
            f"Department: {stu['department']}\n"
            f"Cumulative CGPA: {acad['cgpa']} / 10.0\n"
            f"Earned Credits: {acad['earned_credits']}\n"
            f"Overall Attendance: {att['percentage']}%\n"
            f"Course Marks & Assessment Breakdown: {json.dumps(acad['marks'])}"
        )

        try:
            ai_resp = query_gemini_api(f"Campus Context (Verified Database Records):\n{context}\n\nStudent Question:\n{query}", system_instruction=system_inst)
            if ai_resp:
                return {'reply': ai_resp, 'intent': 'ACADEMICS_AI', 'status': 'success', 'suggestions': ['How can I improve my CGPA?', 'What is my attendance?', 'Do I have pending fees?']}
        except Exception:
            pass

        return {
            'reply': fallback_reply,
            'intent': 'ACADEMICS_FALLBACK',
            'status': 'success',
            'suggestions': ['How can I improve my CGPA?', 'What is my attendance?', 'Do I have pending fees?']
        }

    # --- D. Fees & Payments ---
    if domain == 'FEES':
        fees = get_student_fee_data(student_id, conn)
        lines = [
            f"💰 **Fee & Financial Status for {user_name}:**\n",
            f"• **Total Billed:** ₹{fees['total_billed']:,.2f}",
            f"• **Total Paid:** ₹{fees['total_paid']:,.2f}",
            f"• **Pending Balance:** **₹{fees['total_pending']:,.2f}**"
        ]
        if fees['overdue_amount'] > 0:
            lines.append(f"• 🔴 **Overdue Amount:** ₹{fees['overdue_amount']:,.2f}")
        if fees['next_due_date']:
            lines.append(f"• 📅 **Next Due Date:** {fees['next_due_date']}")

        if fees['fee_items']:
            lines.append("\n**Invoiced Fee Heads:**")
            for f in fees['fee_items']:
                st = "✓ PAID" if f['status'] in ('PAID', 'Paid') else f"Pending ₹{(f['amount'] - f['paid_amount']):,.2f}"
                lines.append(f"• **{f['fee_type']}**: ₹{f['amount']:,.2f} ({st})")
        fallback_reply = "\n".join(lines)

        context = (
            f"Student Name: {user_name}\n"
            f"Total Invoiced Fees: ₹{fees['total_billed']:,.2f}\n"
            f"Total Paid Amount: ₹{fees['total_paid']:,.2f}\n"
            f"Pending Balance: ₹{fees['total_pending']:,.2f}\n"
            f"Overdue Amount: ₹{fees['overdue_amount']:,.2f}\n"
            f"Next Due Date: {fees['next_due_date']}\n"
            f"Fee Invoices: {json.dumps(fees['fee_items'])}\n"
            f"Recent Transactions: {json.dumps(fees['transactions'])}"
        )

        try:
            ai_resp = query_gemini_api(f"Campus Context (Verified Database Records):\n{context}\n\nStudent Question:\n{query}", system_instruction=system_inst)
            if ai_resp:
                return {'reply': ai_resp, 'intent': 'FEES_AI', 'status': 'success', 'suggestions': ['💳 Go to Fee Payment Portal', 'What is my attendance?', 'What is my CGPA?']}
        except Exception:
            pass

        return {
            'reply': fallback_reply,
            'intent': 'FEES_FALLBACK',
            'status': 'success',
            'suggestions': ['💳 Go to Fee Payment Portal', 'What is my attendance?', 'What is my CGPA?']
        }

    # --- E. Timetable ---
    if domain == 'TIMETABLE':
        tt = get_student_timetable_data(student_id, conn)
        is_tomorrow = 'tomorrow' in query.lower()
        target_day = tt['tomorrow_name'] if is_tomorrow else tt['today_name']
        classes = tt['tomorrow_classes'] if is_tomorrow else tt['today_classes']

        if not classes:
            fallback_reply = f"📅 **Timetable for {target_day}:**\nNo lecture sessions scheduled for {target_day}. Enjoy your day off!"
        else:
            lines = [f"📅 **Schedule for {target_day} ({user_name}):**\n"]
            for c in classes:
                lines.append(f"• ⏰ **{c['start_time']} - {c['end_time']}**: **{c['subject']}**\n  ↳ Room: `{c['room_number']}` • Faculty: {c['faculty_name']}")
            fallback_reply = "\n".join(lines)

        context = (
            f"Student Name: {user_name}\n"
            f"Today's Day: {tt['today_name']}\n"
            f"Today's Classes: {json.dumps(tt['today_classes'])}\n"
            f"Tomorrow's Day: {tt['tomorrow_name']}\n"
            f"Tomorrow's Classes: {json.dumps(tt['tomorrow_classes'])}\n"
            f"Full Weekly Timetable: {json.dumps(tt['all_classes'])}"
        )

        try:
            ai_resp = query_gemini_api(f"Campus Context (Verified Database Records):\n{context}\n\nStudent Question:\n{query}", system_instruction=system_inst)
            if ai_resp:
                return {'reply': ai_resp, 'intent': 'TIMETABLE_AI', 'status': 'success', 'suggestions': ['What classes do I have tomorrow?', 'What is my attendance?', 'What is my CGPA?']}
        except Exception:
            pass

        return {
            'reply': fallback_reply,
            'intent': 'TIMETABLE_FALLBACK',
            'status': 'success',
            'suggestions': ['What classes do I have tomorrow?', 'What is my attendance?', 'What is my CGPA?']
        }

    # --- F. General Knowledge / Gemini Synthesis ---
    try:
        ai_resp = query_gemini_api(query, system_instruction=system_inst)
        if ai_resp:
            return {'reply': ai_resp, 'intent': 'GENERAL_AI', 'status': 'success'}
    except Exception:
        pass

    return {
        'reply': f"👋 Hello {user_name}! I am your **CampusGuard AI Assistant**. Ask me about your **attendance**, **CGPA/marks**, **pending fees**, **class timetable**, or **safety help**.",
        'intent': 'GENERAL_FALLBACK',
        'status': 'success'
    }


def handle_parent_ai(parent_id: int, student_id: int, query: str, history: list, conn) -> dict:
    """Handles query for authenticated Parent regarding linked child only."""
    parent = conn.execute("SELECT * FROM parents WHERE id = ?", (parent_id,)).fetchone()
    if not parent:
        return {'reply': "⚠️ Parent authentication session expired.", 'intent': 'ERROR', 'status': 'error'}

    # Verify authorization: Parent must be linked to student_id
    if parent['student_id'] != student_id:
        return {
            'reply': "🔒 **Access Denied:** You are only authorized to query academic and fee data for your verified linked ward.",
            'intent': 'UNAUTHORIZED',
            'status': 'error'
        }

    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        return {'reply': "⚠️ Linked student profile not found in database.", 'intent': 'ERROR', 'status': 'error'}

    child_name = student['name']
    parent_name = parent['name']
    intent_info = classify_query_intent(query)
    domain = intent_info['domain']
    system_inst = build_system_instruction('parent', parent_name)

    # --- A. Attendance ---
    if domain == 'ATTENDANCE':
        att = get_student_attendance_data(student_id, conn)
        
        # Build offline fallback
        lines = [
            f"📊 **Attendance Report for your ward {child_name}:**\n",
            f"• **Overall Attendance:** **{att['percentage']}%** ({att['present']}/{att['total']} sessions)",
            f"• **Compliance Status:** {'🟢 In Compliance (Above 75%)' if att['percentage'] >= 75.0 else '🔴 Attendance Warning (Below 75%)'}\n",
            "**Subject Summary:**"
        ]
        for s in att['subjects']:
            lines.append(f"• **{s['subject']}**: {s['percentage']}% ({s['present']}/{s['total']})")
        fallback_reply = "\n".join(lines)

        context = (
            f"Parent Name: {parent_name}\n"
            f"Linked Ward/Student: {child_name} (Register No: {student['register_number']}, Department: {student['department']})\n"
            f"Overall Attendance: {att['percentage']}% ({att['present']}/{att['total']} sessions attended, {att['absent']} missed)\n"
            f"Institutional Minimum Requirement: 75.0%\n"
            f"Compliance Status: {'Satisfactory (Above 75%)' if att['percentage'] >= 75.0 else 'Warning: Below 75% Threshold'}\n"
            f"Subject Attendance Details: {json.dumps(att['subjects'])}\n"
            f"Lowest Subject: {json.dumps(att['lowest_subject']) if att['lowest_subject'] else 'None'}"
        )

        try:
            ai_resp = query_gemini_api(f"Campus Context (Verified Database Records):\n{context}\n\nParent Question:\n{query}", system_instruction=system_inst)
            if ai_resp:
                return {'reply': ai_resp, 'intent': 'PARENT_ATTENDANCE_AI', 'status': 'success', 'suggestions': [f"What is {child_name}'s CGPA?", f"Does {child_name} have pending fees?", f"How is {child_name} performing overall?"]}
        except Exception:
            pass

        return {
            'reply': fallback_reply,
            'intent': 'PARENT_ATTENDANCE_FALLBACK',
            'status': 'success',
            'suggestions': [f"What is {child_name}'s CGPA?", f"Does {child_name} have pending fees?", f"How is {child_name} performing overall?"]
        }

    # --- B. Academics / CGPA / "How is my child doing?" ---
    if domain == 'ACADEMICS':
        acad = get_student_academic_data(student_id, conn)
        att = get_student_attendance_data(student_id, conn)

        # Build offline fallback
        lines = [
            f"🎓 **Academic Standing for your ward {child_name}:**\n",
            f"• **Cumulative CGPA:** **{acad['cgpa']}** / 10.0",
            f"• **Credits Cleared:** {acad['earned_credits']} Credits\n"
        ]
        if acad['marks']:
            lines.append("**Subject Marks:**")
            for m in acad['marks']:
                lines.append(f"• **{m['name']}**: **{m['total']}/100** (Grade: {m['grade']})")
        fallback_reply = "\n".join(lines)

        context = (
            f"Parent Name: {parent_name}\n"
            f"Linked Ward/Student: {child_name} (Register No: {student['register_number']}, Department: {student['department']})\n"
            f"Cumulative CGPA: {acad['cgpa']} / 10.0\n"
            f"Earned Credits: {acad['earned_credits']}\n"
            f"Overall Attendance: {att['percentage']}%\n"
            f"Subject Assessments & Grades: {json.dumps(acad['marks'])}\n"
            f"Subject Attendance: {json.dumps(att['subjects'])}"
        )

        try:
            ai_resp = query_gemini_api(f"Campus Context (Verified Database Records):\n{context}\n\nParent Question:\n{query}", system_instruction=system_inst)
            if ai_resp:
                return {'reply': ai_resp, 'intent': 'PARENT_ACADEMICS_AI', 'status': 'success', 'suggestions': [f"How is {child_name} performing overall?", f"What is {child_name}'s attendance?", "What fees are pending?"]}
        except Exception:
            pass

        return {
            'reply': fallback_reply,
            'intent': 'PARENT_ACADEMICS_FALLBACK',
            'status': 'success',
            'suggestions': [f"How is {child_name} performing overall?", f"What is {child_name}'s attendance?", "What fees are pending?"]
        }

    # --- C. Fees ---
    if domain == 'FEES':
        fees = get_student_fee_data(student_id, conn)
        lines = [
            f"💰 **Fee & Settlement Summary for {child_name}:**\n",
            f"• **Total Billed Amount:** ₹{fees['total_billed']:,.2f}",
            f"• **Total Cleared Amount:** ₹{fees['total_paid']:,.2f}",
            f"• **Outstanding Balance:** **₹{fees['total_pending']:,.2f}**"
        ]
        if fees['overdue_amount'] > 0:
            lines.append(f"• 🔴 **Overdue Amount:** ₹{fees['overdue_amount']:,.2f}")
        if fees['next_due_date']:
            lines.append(f"• 📅 **Next Due Date:** {fees['next_due_date']}")
        fallback_reply = "\n".join(lines)

        context = (
            f"Parent Name: {parent_name}\n"
            f"Linked Ward/Student: {child_name}\n"
            f"Total Billed: ₹{fees['total_billed']:,.2f}\n"
            f"Total Paid: ₹{fees['total_paid']:,.2f}\n"
            f"Outstanding Balance: ₹{fees['total_pending']:,.2f}\n"
            f"Overdue Amount: ₹{fees['overdue_amount']:,.2f}\n"
            f"Next Due Date: {fees['next_due_date']}\n"
            f"Invoices Breakdown: {json.dumps(fees['fee_items'])}\n"
            f"Recent Transactions: {json.dumps(fees['transactions'])}"
        )

        try:
            ai_resp = query_gemini_api(f"Campus Context (Verified Database Records):\n{context}\n\nParent Question:\n{query}", system_instruction=system_inst)
            if ai_resp:
                return {'reply': ai_resp, 'intent': 'PARENT_FEES_AI', 'status': 'success', 'suggestions': ['💳 Settle Fees Online', f"What is {child_name}'s attendance?"]}
        except Exception:
            pass

        return {
            'reply': fallback_reply,
            'intent': 'PARENT_FEES_FALLBACK',
            'status': 'success',
            'suggestions': ['💳 Settle Fees Online', f"What is {child_name}'s attendance?"]
        }

    # --- D. Timetable ---
    if domain == 'TIMETABLE':
        tt = get_student_timetable_data(student_id, conn)
        is_tomorrow = 'tomorrow' in query.lower()
        target_day = tt['tomorrow_name'] if is_tomorrow else tt['today_name']
        classes = tt['tomorrow_classes'] if is_tomorrow else tt['today_classes']

        if not classes:
            fallback_reply = f"📅 **Timetable for {target_day}:**\nNo lecture sessions scheduled for your ward on {target_day}."
        else:
            lines = [f"📅 **Schedule for {target_day} ({child_name}):**\n"]
            for c in classes:
                lines.append(f"• ⏰ **{c['start_time']} - {c['end_time']}**: **{c['subject']}** (Room: `{c['room_number']}`)")
            fallback_reply = "\n".join(lines)

        context = (
            f"Parent Name: {parent_name}\n"
            f"Linked Ward/Student: {child_name}\n"
            f"Today ({tt['today_name']}) Classes: {json.dumps(tt['today_classes'])}\n"
            f"Tomorrow ({tt['tomorrow_name']}) Classes: {json.dumps(tt['tomorrow_classes'])}\n"
            f"Weekly Schedule: {json.dumps(tt['all_classes'])}"
        )

        try:
            ai_resp = query_gemini_api(f"Campus Context (Verified Database Records):\n{context}\n\nParent Question:\n{query}", system_instruction=system_inst)
            if ai_resp:
                return {'reply': ai_resp, 'intent': 'PARENT_TIMETABLE_AI', 'status': 'success', 'suggestions': [f"What is {child_name}'s CGPA?", f"What is {child_name}'s attendance?"]}
        except Exception:
            pass

        return {
            'reply': fallback_reply,
            'intent': 'PARENT_TIMETABLE_FALLBACK',
            'status': 'success',
            'suggestions': [f"What is {child_name}'s CGPA?", f"What is {child_name}'s attendance?"]
        }

    # --- E. General Gemini ---
    try:
        ai_resp = query_gemini_api(query, system_instruction=system_inst)
        if ai_resp:
            return {'reply': ai_resp, 'intent': 'PARENT_GENERAL_AI', 'status': 'success'}
    except Exception:
        pass

    return {
        'reply': f"👋 Hello {parent_name}! I am your **Parent AI Assistant**. Ask me about your ward {child_name}'s **attendance**, **grades/CGPA**, **fee payments**, or **class schedule**.",
        'intent': 'PARENT_FALLBACK',
        'status': 'success'
    }


def handle_faculty_ai(faculty_id: int, query: str, history: list, conn) -> dict:
    """Handles query for authenticated Faculty."""
    fac = conn.execute("SELECT * FROM faculties WHERE id = ?", (faculty_id,)).fetchone()
    fac_name = fac['name'] if fac else "Professor"

    q = query.lower()

    # 1. At-risk attendance
    if any(k in q for k in ['below 75', 'shortage', 'low attendance', 'attendance shortage', 'at risk']):
        students = conn.execute("SELECT id, register_number, name FROM students WHERE status != 'DELETED'").fetchall()
        at_risk = []
        for s in students:
            att = get_student_attendance_data(s['id'], conn)
            if att['total'] > 0 and att['percentage'] < 75.0:
                at_risk.append(f"• **{s['name']}** ({s['register_number']}): **{att['percentage']}%** ({att['present']}/{att['total']} sessions)")

        if not at_risk:
            reply = "🟢 **Attendance Compliance:** All students are currently maintaining attendance above the institutional 75% threshold."
        else:
            reply = f"⚠️ **Students with Attendance Below 75% ({len(at_risk)} Students):**\n" + "\n".join(at_risk)

        return {'reply': reply, 'intent': 'FACULTY_AT_RISK_ATTENDANCE', 'status': 'success'}

    # 2. Class performance summary
    if any(k in q for k in ['performance', 'summary', 'class average', 'failing', 'marks summary']):
        marks = conn.execute("SELECT m.*, s.name as student_name FROM marks m JOIN students s ON m.student_id = s.id").fetchall()
        if not marks:
            reply = "📋 No student examination marks uploaded yet for this term."
        else:
            scores = [(float(r['cat1'] or 0) + float(r['cat2'] or 0) + float(r['quiz'] or 0) + 
                       float(r['assignment'] or 0) + float(r['project'] or 0) + float(r['fat'] or 0)) for r in marks]
            avg_score = round(sum(scores) / len(scores), 1) if scores else 0
            below_50 = sum(1 for s in scores if s < 50)
            above_80 = sum(1 for s in scores if s >= 80)
            reply = (
                f"📊 **Class Academic Performance Summary:**\n\n"
                f"• **Evaluated Submissions:** {len(scores)} exams\n"
                f"• **Class Average Score:** **{avg_score}/100**\n"
                f"• **High Performers (>=80%):** {above_80} students\n"
                f"• **Students Needing Support (<50%):** {below_50} students"
            )
        return {'reply': reply, 'intent': 'FACULTY_PERFORMANCE_SUMMARY', 'status': 'success'}

    # 3. Gemini Faculty Assistance
    system_inst = build_system_instruction('faculty', fac_name)
    try:
        ai_resp = query_gemini_api(query, system_instruction=system_inst)
        if ai_resp:
            return {'reply': ai_resp, 'intent': 'FACULTY_AI', 'status': 'success'}
    except Exception:
        pass

    return {
        'reply': f"🤖 Hello Professor {fac_name}! Ask me about **attendance shortages below 75%**, **class performance summaries**, or **exam scoring analytics**.",
        'intent': 'FACULTY_HELP',
        'status': 'success'
    }


def handle_admin_ai(admin_id: int, query: str, history: list, conn) -> dict:
    """Handles query for authenticated Admin."""
    q = query.lower()

    # 1. Total Registered Students
    if any(k in q for k in ['registered student', 'total student', 'student count', 'how many student']):
        count = conn.execute("SELECT COUNT(*) FROM students WHERE status != 'DELETED'").fetchone()[0]
        return {
            'reply': f"👥 **Campus Registrar Statistics:** Total registered active students: **{count}**.",
            'intent': 'ADMIN_STUDENTS_COUNT',
            'status': 'success'
        }

    # 2. Fee Collection Statistics
    if any(k in q for k in ['fee', 'collection', 'revenue', 'pending fee', 'total fee']):
        billed = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM fees").fetchone()[0]
        paid = conn.execute("SELECT COALESCE(SUM(paid_amount), 0) FROM fees").fetchone()[0]
        pending = max(0.0, billed - paid)
        tx_count = conn.execute("SELECT COUNT(*) FROM payment_transactions WHERE status = 'SUCCESS'").fetchone()[0]
        return {
            'reply': (
                f"💰 **Institutional Fee & Treasury Metrics:**\n\n"
                f"• **Total Invoiced:** ₹{billed:,.2f}\n"
                f"• **Total Collected:** **₹{paid:,.2f}**\n"
                f"• **Total Outstanding Balance:** ₹{pending:,.2f}\n"
                f"• **Settled Transactions:** {tx_count} payments"
            ),
            'intent': 'ADMIN_FEES_METRICS',
            'status': 'success'
        }

    # 3. Safety and SOS Metrics
    if any(k in q for k in ['sos', 'incident', 'safety count', 'emergency count', 'complaint']):
        inc_total = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        inc_active = conn.execute("SELECT COUNT(*) FROM incidents WHERE status IN ('OPEN', 'Open', 'ACTIVE', 'Active')").fetchone()[0]
        comp_total = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
        return {
            'reply': (
                f"🚨 **Campus Security & Incident Analytics:**\n\n"
                f"• **Total Logged SOS / Incidents:** {inc_total}\n"
                f"• **Currently Active Incidents:** **{inc_active}**\n"
                f"• **Total Grievances / Complaints:** {comp_total}"
            ),
            'intent': 'ADMIN_SAFETY_METRICS',
            'status': 'success'
        }

    # 4. General Gemini Admin Query
    system_inst = build_system_instruction('admin', 'Administrator')
    try:
        ai_resp = query_gemini_api(query, system_instruction=system_inst)
        if ai_resp:
            return {'reply': ai_resp, 'intent': 'ADMIN_AI', 'status': 'success'}
    except Exception:
        pass

    return {
        'reply': "🤖 **CampusGuard Admin Intelligence Console:** Ask me for **total student count**, **fee collections vs pending balances**, or **campus SOS incident metrics**.",
        'intent': 'ADMIN_HELP',
        'status': 'success'
    }


# =============================================================================
# 5. Master Central Dispatcher
# =============================================================================

def process_unified_ai_query(role: str, user_id: int, query: str, session_history: list = None, student_id: int = None, conn = None) -> dict:
    """
    Main entry point for all 4 roles:
    Enforces role isolation, database-first evaluation, and Gemini AI synthesis.
    """
    q_clean = sanitize_input(query)
    if not q_clean:
        return {'reply': "Please ask a question about campus records, academics, or safety.", 'intent': 'EMPTY', 'status': 'error'}

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        r = role.lower().strip()
        if r == 'student':
            return handle_student_ai(user_id, q_clean, session_history or [], conn)
        elif r == 'parent':
            # student_id must be provided for parent
            target_student = student_id or user_id
            return handle_parent_ai(user_id, target_student, q_clean, session_history or [], conn)
        elif r == 'faculty':
            return handle_faculty_ai(user_id, q_clean, session_history or [], conn)
        elif r in ('admin', 'security'):
            return handle_admin_ai(user_id, q_clean, session_history or [], conn)
        else:
            return {'reply': "⚠️ Unauthorized or unrecognized role.", 'intent': 'UNAUTHORIZED', 'status': 'error'}
    finally:
        if should_close:
            conn.close()
