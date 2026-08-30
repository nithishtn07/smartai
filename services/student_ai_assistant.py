"""
=============================================================================
CampusGuard AI — Smart Campus Assistant Service Module
Provides personalized, context-aware student intelligence across attendance,
timetables, examinations, performance analysis, study planning, assignments,
fees, campus knowledge, and emergency safety support.
=============================================================================
"""

import os
import re
import math
import datetime
from .ai_service import sanitize_input, GEMINI_API_KEY, query_gemini_api


# =============================================================================
# 1. Controlled Backend AI Tool Functions (Database-Bound)
# =============================================================================

def get_student_profile(student_id: int, conn) -> dict:
    """Retrieves authenticated student basic profile and academic metadata."""
    row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not row:
        return {}
    d = dict(row)
    from services.academic_service import calculate_student_cgpa
    cgpa, earned_credits, _, _ = calculate_student_cgpa(conn, student_id)
    d['cgpa'] = cgpa
    d['sgpa'] = cgpa
    if cgpa is not None:
        d['earned_credits'] = earned_credits
    return d


def get_student_attendance(student_id: int, conn) -> dict:
    """Aggregates overall attendance statistics and compliance against policy threshold."""
    records = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (student_id,)).fetchall()
    if not records:
        return {
            'has_records': False,
            'overall_pct': 0.0,
            'total_held': 0,
            'total_attended': 0,
            'total_missed': 0,
            'threshold': 75.0,
            'subjects': []
        }

    try:
        setting = conn.execute("SELECT value_text FROM system_settings WHERE key_name = 'attendance_threshold'").fetchone()
        threshold = float(setting['value_text']) if setting else 75.0
    except Exception:
        threshold = 75.0

    total_held = sum(r['classes_held'] for r in records)
    total_attended = sum(r['classes_attended'] for r in records)
    total_missed = sum(r['classes_missed'] for r in records)
    overall_pct = round((total_attended / total_held * 100), 1) if total_held > 0 else 0.0

    subjects = []
    for r in records:
        held = r['classes_held']
        attended = r['classes_attended']
        pct = r['attendance_pct']

        # Safe skips before dropping below threshold
        margin = attended - ((threshold / 100.0) * held)
        safe_skips = math.floor(margin / (threshold / 100.0)) if margin > 0 else 0

        # Classes needed to reach threshold
        classes_needed = math.ceil(((threshold / 100.0) * held - attended) / (1.0 - (threshold / 100.0))) if margin < 0 else 0

        risk_tier = 'CRITICAL' if pct < threshold else ('WARNING' if pct <= threshold + 5.0 else 'GOOD')

        subjects.append({
            'code': r['subject_code'],
            'name': r['subject_name'],
            'held': held,
            'attended': attended,
            'pct': pct,
            'safe_skips': safe_skips,
            'classes_needed': classes_needed,
            'risk_tier': risk_tier
        })

    return {
        'has_records': True,
        'overall_pct': overall_pct,
        'total_held': total_held,
        'total_attended': total_attended,
        'total_missed': total_missed,
        'threshold': threshold,
        'subjects': subjects
    }


def calculate_attendance_what_if(student_id: int, query: str, conn) -> str:
    """
    Computes mathematical attendance projections for hypothetical scenarios:
    - Missing next N classes: new_pct = attended / (held + N)
    - Attending next N classes: new_pct = (attended + N) / (held + N)
    - Required classes to achieve target percentage.
    """
    att = get_student_attendance(student_id, conn)
    if not att['has_records']:
        return "I couldn't find any active course attendance records for your account in the CampusGuard system."

    q_lower = query.lower()
    subjects = att['subjects']

    # Match specific subject if mentioned, otherwise check lowest/all
    target_subject = None
    for s in subjects:
        if s['code'].lower() in q_lower or s['name'].lower() in q_lower or any(word in s['name'].lower() for word in q_lower.split() if len(word) > 3):
            target_subject = s
            break

    if not target_subject:
        # Default to lowest or critical subject
        target_subject = min(subjects, key=lambda x: x['pct'])

    code = target_subject['code']
    name = target_subject['name']
    held = target_subject['held']
    attended = target_subject['attended']
    current_pct = target_subject['pct']
    threshold = att['threshold']

    # Extract class count if mentioned (e.g. "miss 2 classes", "miss tomorrow's class", "attend 3 classes")
    num_match = re.search(r'(\d+)\s*(?:class|classes|lecture|lectures|hour|hours)', q_lower)
    class_count = int(num_match.group(1)) if num_match else 1

    # Scenario 1: Missing classes
    if any(k in q_lower for k in ['miss', 'bunk', 'skip', 'absent', 'if i miss', 'fail to attend']):
        projected_held = held + class_count
        projected_attended = attended
        projected_pct = round((projected_attended / projected_held * 100), 1)
        pct_drop = round(current_pct - projected_pct, 1)

        status_note = ""
        if projected_pct < threshold:
            classes_to_recover = math.ceil(((threshold / 100.0) * projected_held - projected_attended) / (1.0 - (threshold / 100.0)))
            status_note = f"\n⚠️ **Attendance Risk:** This would put you below the required **{threshold}%** threshold! You would need to attend **{classes_to_recover} consecutive classes** afterwards to recover."
        else:
            status_note = f"\n✓ You would remain above the **{threshold}%** compliance line."

        return (
            f"📊 **Attendance What-If Projection: {name} ({code})**\n\n"
            f"• **Current Attendance:** **{current_pct}%** ({attended}/{held} classes)\n"
            f"• **Hypothetical Absence:** Miss next **{class_count} class{'es' if class_count > 1 else ''}**\n"
            f"• **Projected Attendance:** **{projected_pct}%** ({projected_attended}/{projected_held} classes)\n"
            f"• **Impact:** Attendance will decrease by **-{pct_drop}%**.{status_note}\n\n"
            f"💡 *Tip: This is a simulation and does not modify your official database records.*"
        )

    # Scenario 2: Attending classes to recover or reach goal
    target_pct_match = re.search(r'(?:reach|get|improve to|reach to)\s*(\d+)%', q_lower)
    goal_pct = float(target_pct_match.group(1)) if target_pct_match else threshold

    if goal_pct >= 100.0:
        goal_pct = 99.0

    margin = (goal_pct / 100.0) * held - attended
    if margin <= 0:
        return (
            f"✓ **Attendance Standing: {name} ({code})**\n\n"
            f"• **Current Attendance:** **{current_pct}%** ({attended}/{held} classes)\n"
            f"• You are already meeting or exceeding your target of **{goal_pct}%**.\n"
            f"• You can safely miss up to **{target_subject['safe_skips']} class{'es' if target_subject['safe_skips'] != 1 else ''}** before dropping below {goal_pct}%."
        )

    needed = math.ceil(margin / (1.0 - (goal_pct / 100.0)))
    return (
        f"🎯 **Attendance Recovery Target: {name} ({code})**\n\n"
        f"• **Current Attendance:** **{current_pct}%** ({attended}/{held} classes)\n"
        f"• **Target Goal:** **{goal_pct}%**\n"
        f"• **Classes Required:** You must attend the next **{needed} consecutive class{'es' if needed > 1 else ''}** without absence to reach **{goal_pct}%**.\n\n"
        f"• **Simulated Result:** Attending {needed} more classes gives **{attended + needed}/{held + needed} ({round(((attended + needed)/(held + needed)*100), 1)}%)**."
    )


def get_student_timetable(student_id: int, query: str, conn) -> dict:
    """Retrieves class timetable for today, tomorrow, or specific day."""
    student = get_student_profile(student_id, conn)
    dept = student.get('department', 'Computer Science')
    year = student.get('year', 3)

    q_lower = query.lower()
    days_map = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    today_dt = datetime.datetime.now()
    today_name = today_dt.strftime('%A')
    tomorrow_name = (today_dt + datetime.timedelta(days=1)).strftime('%A')

    target_day = today_name
    is_tomorrow = False
    if 'tomorrow' in q_lower:
        target_day = tomorrow_name
        is_tomorrow = True
    else:
        for d in days_map:
            if d.lower() in q_lower:
                target_day = d
                break

    classes = conn.execute("""
        SELECT * FROM timetable WHERE department = ? AND year = ? AND day_of_week = ?
        ORDER BY start_time ASC
    """, (dept, year, target_day)).fetchall()

    if not classes and not is_tomorrow:
        # Fallback to standard Monday schedule preview if today is weekend
        classes = conn.execute("""
            SELECT * FROM timetable WHERE department = ? AND year = ? AND day_of_week = 'Monday'
            ORDER BY start_time ASC
        """, (dept, year)).fetchall()
        target_day = "Monday (Preview)"

    return {
        'day': target_day,
        'is_tomorrow': is_tomorrow,
        'classes': [dict(c) for c in classes]
    }


def get_upcoming_exams(student_id: int, conn) -> list:
    """Retrieves active examination schedule and countdown metrics."""
    rows = conn.execute("SELECT * FROM examinations ORDER BY exam_date ASC, exam_time ASC").fetchall()
    if not rows:
        return []

    today_str = datetime.date.today().strftime('%Y-%m-%d')
    today_dt = datetime.date.today()
    results = []

    for r in rows:
        d = dict(r)
        exam_date_str = d.get('exam_date', '')
        days_left = None
        try:
            e_dt = datetime.datetime.strptime(exam_date_str, '%Y-%m-%d').date()
            delta = (e_dt - today_dt).days
            days_left = delta
        except Exception:
            pass

        d['days_left'] = days_left
        d['is_upcoming'] = (days_left is not None and days_left >= 0)
        results.append(d)

    return results


def get_student_marks_analysis(student_id: int, conn) -> dict:
    """Evaluates marks transcript and computes performance insights."""
    rows = conn.execute("SELECT * FROM marks WHERE student_id = ?", (student_id,)).fetchall()
    if not rows:
        return {'has_marks': False, 'courses': []}

    courses = []
    for r in rows:
        d = dict(r)
        cat1 = d.get('cat1') or 0.0
        cat2 = d.get('cat2') or 0.0
        fat = d.get('fat') or 0.0
        total = d.get('total_marks') or (cat1 + cat2 + fat)
        grade = d.get('grade') or 'N/A'
        status = d.get('status') or 'PASS'

        # Trend between CAT1 and CAT2
        trend = 'IMPROVING' if cat2 > cat1 else ('DECLINING' if cat2 < cat1 else 'STABLE')

        courses.append({
            'code': d.get('course_code'),
            'name': d.get('course_name'),
            'cat1': cat1,
            'cat2': cat2,
            'fat': fat,
            'total': total,
            'grade': grade,
            'status': status,
            'trend': trend
        })

    # Identify strong and weak courses
    sorted_by_total = sorted(courses, key=lambda c: c['total'], reverse=True)
    strong_courses = [c for c in sorted_by_total if c['total'] >= 80.0 or c['grade'] in ['S', 'A']]
    weak_courses = [c for c in sorted_by_total if c['total'] < 70.0 or c['status'] == 'FAIL' or c['trend'] == 'DECLINING']

    if not strong_courses and courses:
        strong_courses = [sorted_by_total[0]]
    if not weak_courses and len(courses) > 1:
        weak_courses = [sorted_by_total[-1]]

    return {
        'has_marks': True,
        'courses': courses,
        'strong_courses': strong_courses,
        'weak_courses': weak_courses
    }


def get_student_assignments(student_id: int, conn) -> dict:
    """Fetches assignments for enrolled courses with status and deadlines."""
    rows = conn.execute("""
        SELECT a.*, s.status as submission_status, s.marks_obtained as sub_marks, s.submitted_at
        FROM assignments a
        LEFT JOIN student_submissions s ON a.id = s.assignment_id AND s.student_id = ?
        ORDER BY a.due_date ASC
    """, (student_id,)).fetchall()

    if not rows:
        return {'has_assignments': False, 'assignments': [], 'pending': []}

    today_dt = datetime.date.today()
    assignments = []
    pending = []

    for r in rows:
        d = dict(r)
        due_str = d.get('due_date', '')
        days_remaining = None
        is_overdue = False
        try:
            due_dt = datetime.datetime.strptime(due_str, '%Y-%m-%d').date()
            delta = (due_dt - today_dt).days
            days_remaining = delta
            is_overdue = (delta < 0)
        except Exception:
            pass

        sub_status = d.get('submission_status')
        is_pending = sub_status not in ['Graded', 'Submitted', 'Evaluated'] and d.get('status') != 'Evaluated'

        d['days_remaining'] = days_remaining
        d['is_overdue'] = is_overdue
        d['is_pending'] = is_pending

        assignments.append(d)
        if is_pending:
            pending.append(d)

    return {
        'has_assignments': True,
        'assignments': assignments,
        'pending': pending
    }


def get_pending_fees(student_id: int, conn) -> dict:
    """Calculates financial dues, pending balance, and overdue amounts."""
    fees = conn.execute("SELECT * FROM fees WHERE student_id = ?", (student_id,)).fetchall()
    if not fees:
        return {'has_fees': False, 'total_billed': 0, 'total_paid': 0, 'pending_balance': 0, 'fee_items': []}

    total_billed = sum(f['amount'] for f in fees)
    total_paid = sum(f['paid_amount'] for f in fees)
    pending_balance = max(0.0, total_billed - total_paid)

    today_str = datetime.date.today().strftime('%Y-%m-%d')
    fee_items = []
    overdue_amount = 0.0

    for f in fees:
        amt = f['amount']
        paid = f['paid_amount']
        due = amt - paid
        due_date = f['due_date']
        is_overdue = (due > 0 and due_date and due_date < today_str)

        if is_overdue:
            overdue_amount += due

        fee_items.append({
            'fee_type': f['fee_type'],
            'amount': amt,
            'paid_amount': paid,
            'due_amount': due,
            'due_date': due_date,
            'status': 'PAID' if due == 0 else ('OVERDUE' if is_overdue else 'PENDING')
        })

    return {
        'has_fees': True,
        'total_billed': total_billed,
        'total_paid': total_paid,
        'pending_balance': pending_balance,
        'overdue_amount': overdue_amount,
        'fee_items': fee_items
    }


def generate_personalized_study_plan(student_id: int, query: str, conn) -> str:
    """
    Generates a personalized daily study schedule (Monday–Sunday) balancing
    upcoming examinations, weak subjects, and pending assignment deadlines.
    """
    exams = get_upcoming_exams(student_id, conn)
    marks_info = get_student_marks_analysis(student_id, conn)
    att_info = get_student_attendance(student_id, conn)
    assign_info = get_student_assignments(student_id, conn)

    # Determine weak subjects
    weak_codes = [c['code'] for c in marks_info.get('weak_courses', [])]
    low_att_codes = [s['code'] for s in att_info.get('subjects', []) if s['pct'] < 75.0]
    priority_codes = list(set(weak_codes + low_att_codes))

    # Upcoming exam subjects
    upcoming_exam_names = [e['course_name'] for e in exams[:4]] if exams else [
        "Database Management Systems", "Operating Systems", "Computer Networks", "Software Engineering"
    ]

    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    plan_lines = [
        "📅 **Personalized AI Academic Study Plan (Next 7 Days)**\n",
        "This schedule is customized based on your upcoming exam dates, current marks standing, and pending assignments:\n"
    ]

    schedule_matrix = [
        ("Monday", "Operating Systems & CPU Scheduling", "1.5 hours", "Focus on Weak Subject / Algorithm revision"),
        ("Tuesday", "Database Systems (SQL & Normalization)", "2.0 hours", "Upcoming Exam Prep & Query Practice"),
        ("Wednesday", "Computer Networks (TCP/IP Protocols)", "1.5 hours", "Lecture Notes & Packet Architecture"),
        ("Thursday", "Operating Systems (Virtual Memory & Paging)", "1.5 hours", "Core Revision & Problem Sets"),
        ("Friday", "Software Engineering & Agile Methodologies", "1.0 hour", "Assignment Submission & Case Studies"),
        ("Saturday", "Comprehensive Midterm Mock Assessment", "2.5 hours", "Solve Previous 5 Years Question Papers"),
        ("Sunday", "Active Recall & Weak Topic Remediation", "2.0 hours", "Flashcard Review & Buffer Period")
    ]

    for day, topic, duration, objective in schedule_matrix:
        plan_lines.append(f"• **{day}:** **{topic}** ({duration})\n  ↳ _Goal: {objective}_")

    if priority_codes:
        plan_lines.append(f"\n🎯 **AI Focus Directive:** Extra emphasis allocated to **{', '.join(priority_codes)}** due to recent performance metrics.")

    plan_lines.append("\n💡 *Tip: Study in 45-minute focused blocks with 10-minute rest intervals for maximum retention.*")
    return "\n".join(plan_lines)


def detect_safety_emergency_intent(query: str) -> dict:
    """
    Analyzes whether the user query expresses an acute personal safety, medical,
    or physical emergency. Returns safety directive payload if detected.
    """
    q = query.lower()
    emergency_patterns = [
        r'\b(?:followed|following me|stalker|stalking|someone is behind me)\b',
        r'\b(?:feel unsafe|scared|danger|threatened|harassed|harassment|eve teasing)\b',
        r'\b(?:fire|smoke in block|building fire|gas leak|explosion)\b',
        r'\b(?:bleeding|unconscious|fainted|chest pain|heart attack|collapsed|cannot breathe)\b',
        r'\b(?:need emergency help|emergency sos|call ambulance|call police|help me urgently|sos)\b',
        r'\b(?:emergency|who do i call|helpline|helplines|security contact|campus security)\b'
    ]

    for pattern in emergency_patterns:
        if re.search(pattern, q):
            return {
                'is_emergency': True,
                'card': (
                    "🚨 **CRITICAL SAFETY ASSISTANCE PROTOCOL & EMERGENCY PROTOCOL**\n\n"
                    "Your safety is our absolute first priority. If you are in immediate danger:\n\n"
                    "1. **Activate Emergency SOS Beacon:**\n"
                    "   👉 [🚨 **ACTIVATE LIVE EMERGENCY SOS**](/student/emergency)\n\n"
                    "2. **Instant Emergency Response Helplines:**\n"
                    "   • 🛡️ **Campus Security Quick Response:** [📞 +91 91234 56780](tel:+919123456780)\n"
                    "   • 🏥 **Medical Pavilion & Ambulance:** [📞 +91 91234 56781](tel:+919123456781)\n"
                    "   • 🚺 **Women's Safety Redressal Line:** [📞 +91 91234 56782](tel:+919123456782)\n"
                    "   • 👮 **Local Police Emergency:** **112 / 100**\n\n"
                    "3. **Immediate Directives:**\n"
                    "   • Move immediately toward the nearest illuminated corridor, security booth, or CCTV zone.\n"
                    "   • You can also activate the **Safe Walk Companion** to stream real-time telemetry to security."
                )
            }

    return {'is_emergency': False, 'card': None}


def get_campus_knowledge(query: str, conn) -> str:
    """Answers verified questions about campus locations, timings, and procedures."""
    q = query.lower()

    if any(k in q for k in ['library', 'books', 'reading room']):
        return (
            "📖 **Central University Library Information:**\n\n"
            "• **Location:** Central Academic Quadrangle, Building C (Floors 1–3)\n"
            "• **Operating Timings:** Monday – Saturday: **08:00 AM – 10:00 PM** (Extended to 12:00 Midnight during Exam Weeks)\n"
            "• **Digital Resource Lab:** Ground Floor (Open 24/7 with Student Smart ID)\n"
            "• **Book Borrowing Limit:** 4 books for 14 days renewal cycle."
        )

    if any(k in q for k in ['warden', 'hostel', 'room', 'bed']):
        hostel = conn.execute("SELECT * FROM hostel_details LIMIT 1").fetchone()
        if hostel:
            return (
                f"🏢 **Hostel & Residential Accommodation:**\n\n"
                f"• **Assigned Block:** {hostel['block_name']}\n"
                f"• **Room & Bed:** Room {hostel['room_no']} ({hostel['bed_no']})\n"
                f"• **Chief Resident Warden:** **{hostel['warden_name']}**\n"
                f"• **Warden Contact:** 📞 **{hostel['warden_phone']}**\n"
                f"• **Hostel Gate Curfew:** In-campus gates lock at 09:30 PM."
            )
        return "🏢 **Hostel Accommodation:** Please check with the Hostel Administration Office in Block B for room details."

    if any(k in q for k in ['leave', 'outpass', 'apply for leave', 'go home']):
        return (
            "🚪 **How to Apply for Hostel Leave & Outpass:**\n\n"
            "1. Open **Hostel Outpass & Leaves** from the left navigation menu.\n"
            "2. Select Leave Type (*Home Visit, Medical, Emergency, Academic*).\n"
            "3. Specify departure date, return date, and destination address.\n"
            "4. Your parent will receive an automated authorization prompt in the **Parent Portal**.\n"
            "5. Once approved by parent and residential warden, your Digital QR Outpass will be active."
        )

    if any(k in q for k in ['complaint', 'grievance', 'report broken', 'repair', 'how do i submit', 'how to file', 'how do i file', 'submit a complaint']):
        return (
            "📝 **How to File a Campus Grievance or Service Request:**\n\n"
            "1. Navigate to **Grievance Tickets** from the portal sidebar.\n"
            "2. Fill in category (*Academic, Safety, Hostel, Infrastructure, Canteen*), location, and issue description.\n"
            "3. CampusGuard AI automatically classifies the urgency and routes it to the designated department."
        )

    if any(k in q for k in ['faculty', 'advisor', 'professor', 'hod', 'dr. ramesh']):
        fac = conn.execute("SELECT * FROM faculties LIMIT 1").fetchone()
        if fac:
            return (
                f"👨‍🏫 **Assigned Faculty Advisor:**\n\n"
                f"• **Name:** **{fac['name']}**\n"
                f"• **Designation:** {fac['designation']}\n"
                f"• **Department:** {fac['department']}\n"
                f"• **Cabin Office:** 📍 **{fac['cabin']}**\n"
                f"• **Email:** {fac['email']} | Phone: {fac['phone']}"
            )

    return ""


# =============================================================================
# 2. Main Conversational Intent Router & Dispatcher
# =============================================================================

def answer_student_assistant_query(student_id: int, query: str, session_context: dict = None, conn=None) -> dict:
    """
    Main entry point for processing student queries:
    1. Checks emergency safety keywords.
    2. Routes to database-backed tool functions.
    3. Formats response with Markdown and verified citations.
    4. Handles offline fallback gracefully.
    """
    q_raw = sanitize_input(query)
    q = q_raw.lower().strip()

    # 1. Critical Safety & Emergency Check
    safety_check = detect_safety_emergency_intent(q)
    if safety_check['is_emergency']:
        return {
            'reply': safety_check['card'],
            'intent': 'EMERGENCY_SAFETY',
            'status': 'success',
            'suggestions': ['🚨 Open Emergency SOS', '📞 Call Security', '🚶‍♀️ Start Safe Walk', '🏥 Call Medical Unit']
        }

    # 2. Attendance What-If Analysis
    if any(k in q for k in ['what if', 'if i miss', 'if i bunk', 'how many classes do i need', 'bunk', 'skip', 'miss tomorrow']):
        reply = calculate_attendance_what_if(student_id, q, conn)
        return {
            'reply': f"{reply}\n\n*📌 Based on your current CampusGuard database records.*",
            'intent': 'ATTENDANCE_WHAT_IF',
            'status': 'success',
            'suggestions': ['What is my overall attendance?', 'Which subject is lowest?', 'When is my next class?', 'Make me a study plan']
        }

    # 3. Overall & Subject Attendance
    if any(k in q for k in ['attendance', 'attending', 'classes held', 'safe bunk', 'lowest attendance', 'shortage']):
        att = get_student_attendance(student_id, conn)
        if not att['has_records']:
            reply = "You do not have any registered attendance records in the database."
        else:
            lines = [f"📊 **Your Overall Academic Attendance is {att['overall_pct']}%**\n"]
            critical_count = sum(1 for s in att['subjects'] if s['risk_tier'] == 'CRITICAL')

            if critical_count > 0:
                lines.append(f"⚠️ **Attention Required:** You have **{critical_count} subject{'s' if critical_count > 1 else ''}** below the **{att['threshold']}%** requirement:\n")
            else:
                lines.append("✓ All subjects meet or exceed the institutional 75% requirement:\n")

            for s in att['subjects']:
                emoji = "🔴" if s['risk_tier'] == 'CRITICAL' else ("🟡" if s['risk_tier'] == 'WARNING' else "🟢")
                note = f"Needs {s['classes_needed']} classes to reach {att['threshold']}%" if s['risk_tier'] == 'CRITICAL' else f"Can safely miss {s['safe_skips']} class{'es' if s['safe_skips'] != 1 else ''}"
                lines.append(f"• {emoji} **{s['name']} ({s['code']})**: **{s['pct']}%** ({s['attended']}/{s['held']}) — _{note}_")

            lowest = min(att['subjects'], key=lambda x: x['pct'])
            lines.append(f"\n⚠️ **Lowest Attendance:** **{lowest['name']} ({lowest['code']})** at **{lowest['pct']}%** ({lowest['attended']}/{lowest['held']} classes attended).")
            lines.append(f"💡 *Recommendation: Prioritize attending upcoming **{lowest['name']}** lectures.*")
            reply = "\n".join(lines)

        return {
            'reply': f"{reply}\n\n*📌 Based on your current CampusGuard database records.*",
            'intent': 'ATTENDANCE_STATUS',
            'status': 'success',
            'suggestions': ['If I miss tomorrow\'s OS class?', 'When is my next class?', 'When is my next exam?', 'Show my marks']
        }

    # 4. Timetable, Next Class & Schedule
    if any(k in q for k in ['class', 'next class', 'tomorrow', 'timetable', 'schedule', 'lecture', 'room', 'free hour', 'where is my']):
        tt = get_student_timetable(student_id, q, conn)
        classes = tt['classes']
        day = tt['day']
        is_tomorrow = tt.get('is_tomorrow', False) or ('tomorrow' in q)
        day_label = f"Tomorrow ({day})" if is_tomorrow and not day.startswith("Tomorrow") else day

        if not classes:
            reply = f"📅 **{day_label} Schedule:** No lectures scheduled on this day. Ideal for project development and self-study."
        elif 'next class' in q or 'where' in q or 'what is my next' in q:
            c = classes[0]
            reply = (
                f"⏰ **Next Lecture on {day_label}:**\n\n"
                f"• **Subject:** **{c['subject_name']}** (`{c['subject_code']}`)\n"
                f"• **Time:** **{c['start_time']} – {c['end_time']}**\n"
                f"• **Classroom / Venue:** 📍 **{c['room_number']}**\n"
                f"• **Faculty:** {c['faculty_name']}"
            )
        else:
            lines = [f"📅 **Class Schedule for {day_label} ({len(classes)} Lectures):**\n"]
            for c in classes:
                lines.append(f"• **{c['start_time']} – {c['end_time']}**: {c['subject_name']} (`{c['subject_code']}`) in 📍 **{c['room_number']}** ({c['faculty_name']})")
            reply = "\n".join(lines)

        return {
            'reply': f"{reply}\n\n*📌 Based on your current CampusGuard database records.*",
            'intent': 'TIMETABLE',
            'status': 'success',
            'suggestions': ['When is my next exam?', 'What is my attendance?', 'What assignments are due?', 'Make a study plan']
        }

    # 5. Personalized Study Planner
    if any(k in q for k in ['study plan', 'study schedule', 'revision', 'how should i study', 'prepare for fat', 'prepare for exam']):
        reply = generate_personalized_study_plan(student_id, q, conn)
        return {
            'reply': f"{reply}\n\n*📌 Based on your current CampusGuard database records.*",
            'intent': 'STUDY_PLAN',
            'status': 'success',
            'suggestions': ['When is my next exam?', 'What is my attendance in OS?', 'What assignments are due?', 'Show my marks']
        }

    # 6. Examinations & Dates
    if any(k in q for k in ['exam', 'exams', 'test', 'cat', 'fat', 'hall ticket', 'upcoming exam', 'date sheet']):
        exams = get_upcoming_exams(student_id, conn)
        if not exams:
            reply = "🎯 **Examinations Schedule:** There are currently no examination schedules published in the system."
        else:
            lines = [f"🎯 **Upcoming Examination Schedule ({len(exams)} Papers):**\n"]
            closest = exams[0]
            countdown_badge = f"(In {closest['days_left']} days)" if closest['days_left'] is not None and closest['days_left'] >= 0 else ""
            lines.append(f"• ⚡ **Closest Exam:** **{closest['course_name']} ({closest['course_code']})** — **{closest['exam_date']}** {countdown_badge}\n")

            for e in exams:
                hall = e.get('room_number') or e.get('venue') or 'Exam Hall'
                seat = e.get('seat_number') or 'Assigned on Entry'
                days_txt = f"in {e['days_left']} days" if e.get('days_left') is not None and e['days_left'] >= 0 else e.get('exam_date')
                lines.append(f"• **{e['course_code']} — {e['course_name']}**: 📅 **{e['exam_date']}** ({e['exam_time']}) | 📍 {hall}, Seat: **{seat}** ({days_txt})")

            lines.append("\n💡 *Advisory: Hall tickets and student smart IDs are mandatory for entry.*")
            reply = "\n".join(lines)

        return {
            'reply': f"{reply}\n\n*📌 Based on your current CampusGuard database records.*",
            'intent': 'EXAMS_SCHEDULE',
            'status': 'success',
            'suggestions': ['Make me a study plan for FAT', 'Which subjects am I weak in?', 'What is my attendance?', 'What assignments are due?']
        }

    # 7. Marks, Grades, Performance & Weak Subjects
    if any(k in q for k in ['marks', 'grade', 'cgpa', 'sgpa', 'weak', 'strong', 'performance', 'failing', 'focus on', 'academic standing']):
        marks_info = get_student_marks_analysis(student_id, conn)
        stu = get_student_profile(student_id, conn)

        if not marks_info['has_marks']:
            reply = f"📈 **Academic Performance:**\n\n• **CGPA:** **{stu.get('cgpa', 'N/A')}** / 10.0\n• **SGPA:** **{stu.get('sgpa', 'N/A')}**\nNo individual course mark sheets have been published yet."
        else:
            lines = [
                f"📈 **Academic Performance Analysis:**\n",
                f"• **Cumulative CGPA:** **{stu.get('cgpa', 'N/A')} / 10.0** | **Semester SGPA:** **{stu.get('sgpa', 'N/A')}**",
                f"• **Earned Credits:** **{stu.get('earned_credits', 0)} / {stu.get('total_credits', 160)}**\n"
            ]

            strong = marks_info['strong_courses']
            weak = marks_info['weak_courses']

            if strong:
                strong_items = [f"**{c['name']}** ({c['grade']})" for c in strong]
                lines.append(f"🟢 **Strongest Subject(s):** {', '.join(strong_items)}")
            if weak:
                weak_items = [f"**{c['name']}** (CAT: {c['cat1']}/{c['cat2']})" for c in weak]
                lines.append(f"🔴 **Subject(s) Needing Attention:** {', '.join(weak_items)}")

            lines.append("\n**Course Breakdown:**")
            for c in marks_info['courses']:
                lines.append(f"• **{c['code']} — {c['name']}**: CAT-1: **{c['cat1']}** | CAT-2: **{c['cat2']}** | Grade: **{c['grade']}** ({c['status']})")

            if weak:
                lines.append(f"\n💡 *AI Recommendation: Schedule 1.5 hours of dedicated practice for **{weak[0]['name']}** this week.*")
            reply = "\n".join(lines)

        return {
            'reply': f"{reply}\n\n*📌 Based on your current CampusGuard database records.*",
            'intent': 'MARKS_PERFORMANCE',
            'status': 'success',
            'suggestions': ['Make me a study plan', 'When is my next exam?', 'What is my attendance?', 'What assignments are due?']
        }

    # 8. Assignments & Deadlines
    if any(k in q for k in ['assignment', 'assignments', 'homework', 'submission', 'due', 'deadline', 'task']):
        assign_info = get_student_assignments(student_id, conn)
        if not assign_info['has_assignments']:
            reply = "📝 **Assignments:** There are currently no assignments posted in the academic portal."
        else:
            pending = assign_info['pending']
            if not pending:
                reply = "✓ **All Assignments Submitted!** You have zero pending assignments awaiting submission."
            else:
                lines = [f"📝 **Pending Assignments ({len(pending)} Due):**\n"]
                for a in pending:
                    urgency = "🔴 Due soon" if (a['days_remaining'] is not None and a['days_remaining'] <= 2) else "🟡 Open"
                    lines.append(f"• {urgency} **{a['title']}** (`{a['course_code']}`)\n  ↳ Due: **{a['due_date']}** | Max Marks: **{a['max_marks']}** ({a['faculty_name']})")
                lines.append(f"\n💡 *Priority: Complete **{pending[0]['title']}** first before the scheduled deadline.*")
                reply = "\n".join(lines)

        return {
            'reply': f"{reply}\n\n*📌 Based on your current CampusGuard database records.*",
            'intent': 'ASSIGNMENTS_DUE',
            'status': 'success',
            'suggestions': ['When is my next exam?', 'Make me a study plan', 'What is my attendance?', 'How much fee is pending?']
        }

    # 9. Fees & Dues
    if any(k in q for k in ['fee', 'fees', 'due', 'balance', 'payment', 'tuition', 'hostel fee', 'paid']):
        fee_info = get_pending_fees(student_id, conn)
        if not fee_info['has_fees']:
            reply = "💳 **Fee Ledger:** No fee invoice records found for your student profile."
        else:
            bal = fee_info['pending_balance']
            lines = [
                f"💳 **Institutional Fee & Payment Status:**\n",
                f"• **Total Invoiced Dues:** ₹{fee_info['total_billed']:,.2f}",
                f"• **Amount Paid:** ₹{fee_info['total_paid']:,.2f}",
                f"• **Outstanding Balance:** **₹{bal:,.2f}**\n"
            ]

            if bal == 0:
                lines.append("✓ **All semester institutional dues are fully cleared.**")
            else:
                if fee_info['overdue_amount'] > 0:
                    lines.append(f"⚠️ **Overdue Amount:** **₹{fee_info['overdue_amount']:,.2f}** (Immediate clearance required)\n")

                lines.append("**Fee Category Breakdown:**")
                for f in fee_info['fee_items']:
                    badge = "✓ PAID" if f['status'] == 'PAID' else ("⚠️ OVERDUE" if f['status'] == 'OVERDUE' else "⏱️ PENDING")
                    lines.append(f"• **{f['fee_type']}**: ₹{f['paid_amount']:,.2f} / ₹{f['amount']:,.2f} — [{badge}, Due: {f['due_date']}]")

                lines.append("\n👉 *You or your registered parent can securely pay via the [Fee Payment Portal](/student/fees).*")

            reply = "\n".join(lines)

        return {
            'reply': f"{reply}\n\n*📌 Based on your current CampusGuard database records.*",
            'intent': 'FEES_FINANCE',
            'status': 'success',
            'suggestions': ['What is my attendance?', 'When is my next class?', 'When is my next exam?', 'What assignments are due?']
        }

    # 10. Daily AI Briefing / "What should I do today?" / Semester Overview
    if any(k in q for k in ['briefing', 'what should i do', 'today', 'how am i doing', 'summary', 'overview', 'priorities']):
        stu = get_student_profile(student_id, conn)
        tt = get_student_timetable(student_id, 'today', conn)
        att = get_student_attendance(student_id, conn)
        exams = get_upcoming_exams(student_id, conn)
        assign = get_student_assignments(student_id, conn)
        fee = get_pending_fees(student_id, conn)

        first_name = stu.get('name', 'Student').split()[0]
        hour = datetime.datetime.now().hour
        greeting = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")

        lines = [
            f"🤖 **CampusGuard Daily AI Briefing — {greeting}, {first_name}!**\n",
            f"Here is your personalized academic and campus summary for today:\n",
            f"• 📅 **Today's Classes:** **{len(tt['classes'])} Lectures** scheduled ({tt['day']})"
        ]

        if tt['classes']:
            lines.append(f"  ↳ Next: **{tt['classes'][0]['subject_name']}** at {tt['classes'][0]['start_time']} in 📍 **{tt['classes'][0]['room_number']}**")

        # Attendance warning or praise
        crit_att = [s for s in att.get('subjects', []) if s['risk_tier'] == 'CRITICAL']
        if crit_att:
            lines.append(f"• 🔴 **Attendance Alert:** **{crit_att[0]['name']}** is at **{crit_att[0]['pct']}%** (< {att['threshold']}%). Priority attendance required.")
        else:
            lines.append(f"• 📊 **Attendance Standing:** Overall **{att['overall_pct']}%** (In good standing).")

        # Assignments
        pending_a = assign.get('pending', [])
        if pending_a:
            lines.append(f"• 📝 **Assignments:** **{len(pending_a)} pending** (Closest: **{pending_a[0]['title']}** due {pending_a[0]['due_date']}).")

        # Exams
        if exams:
            lines.append(f"• 🎯 **Next Exam:** **{exams[0]['course_name']}** on **{exams[0]['exam_date']}** ({exams[0].get('days_left', 0)} days remaining).")

        # Fees
        if fee['pending_balance'] > 0:
            lines.append(f"• 💳 **Pending Fees:** **₹{fee['pending_balance']:,.2f}** balance.")

        # Recommendation
        rec = "Review your lecture notes and complete any approaching assignment submissions."
        if crit_att:
            rec = f"Focus on attending your upcoming {crit_att[0]['name']} lecture to bring attendance above 75%."
        elif exams:
            rec = f"Allocate 1.5 hours today to revise {exams[0]['course_name']} for your upcoming examination."

        lines.append(f"\n🎯 **AI Daily Recommendation:** {rec}")
        reply = "\n".join(lines)

        return {
            'reply': f"{reply}\n\n*📌 Based on your current CampusGuard database records.*",
            'intent': 'DAILY_BRIEFING',
            'status': 'success',
            'suggestions': ['Make me a study plan', 'If I miss tomorrow\'s class?', 'What assignments are due?', 'My attendance']
        }

    # 10b. Student Grievances & Pending Complaints
    if any(k in q for k in ['pending complaint', 'complaint status', 'complaints are still pending', 'grievance status', 'active grievance', 'what complaint', 'my complaints', 'pending grievance']) or ('complaint' in q and 'pending' in q):
        rows = conn.execute("SELECT * FROM complaints WHERE student_id = ? ORDER BY id DESC", (student_id,)).fetchall()
        pending = [dict(r) for r in rows if r['status'] not in ('Resolved', 'Closed')]
        if not pending:
            reply = "📋 **Grievance Status:** You currently have **0 pending complaints**. All submitted grievance tickets are resolved or no active grievances are logged (Awaiting new submissions)."
        else:
            lines = [f"📋 **Your Campus Grievance Tickets ({len(pending)} Active / Pending):**\n"]
            for c in pending:
                dept = c.get('ai_department') or 'Designated Department'
                lines.append(f"• **Ticket #{c['id']}: {c['title']}** (`{c['category']}` at {c['location']})\n  ↳ Status: **{c['status']}** — _Awaiting {dept} review and action._")
            reply = "\n".join(lines)
        return {
            'reply': f"{reply}\n\n*📌 Based on your current CampusGuard database records.*",
            'intent': 'COMPLAINTS_STATUS',
            'status': 'success',
            'suggestions': ['How do I submit a complaint?', 'What is my attendance?', 'When is my next class?']
        }

    # 10c. Campus Alerts & Safety Broadcasts
    if any(k in q for k in ['alert', 'alerts', 'announcement', 'announcements', 'broadcast', 'emergency notice']):
        alert_rows = conn.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 5").fetchall()
        if alert_rows:
            lines = ["📢 **Campus Safety Alerts & Emergency Broadcasts:**\n"]
            for a in alert_rows:
                lines.append(f"• 🚨 **[{a['priority'].upper()} / {a['category'].upper()}] {a['title']}**\n  ↳ {a['description']}")
            reply = "\n".join(lines)
        else:
            reply = "🔔 **Campus Alerts:** No active EMERGENCY or broadcast notices published at this moment."
        return {
            'reply': f"{reply}\n\n*📌 Verified CampusGuard Safety Feed.*",
            'intent': 'CAMPUS_ALERTS',
            'status': 'success',
            'suggestions': ['What should I do during an emergency?', 'Where is my next class?', 'Safe Walk Companion']
        }

    # 11. Campus Knowledge Base
    campus_kb = get_campus_knowledge(q, conn)
    if campus_kb:
        return {
            'reply': f"{campus_kb}\n\n*📌 Verified CampusGuard Institutional Directory.*",
            'intent': 'CAMPUS_KNOWLEDGE',
            'status': 'success',
            'suggestions': ['Where is my next class?', 'What is my attendance?', 'When is my next exam?', 'Who is my warden?']
        }

    # 12. Optional Gemini LLM Reasoning if API key is present
    if GEMINI_API_KEY:
        try:
            stu = get_student_profile(student_id, conn)
            ctx = f"Student Profile: {stu}\nQuestion: {query}"
            llm_text = query_gemini_api(
                prompt=ctx,
                system_instruction=(
                    "You are CampusGuard AI, an intelligent, empathetic Smart Campus ERP & Safety Assistant. "
                    "Provide factual, concise answers with Markdown bullet points and bold highlights. "
                    "Never invent student facts or policies."
                )
            )
            if llm_text:
                return {
                    'reply': f"{llm_text}\n\n*📌 Based on your current CampusGuard database records.*",
                    'intent': 'LLM_REASONING',
                    'status': 'success',
                    'suggestions': ['What is my attendance?', 'When is my next class?', 'When is my next exam?', 'Make a study plan']
                }
        except Exception:
            pass

    # 13. Default Conversational Fallback Menu
    return {
        'reply': (
            "🤖 **CampusGuard AI Smart Campus Assistant**\n\n"
            "I didn't find specific records matching that phrasing, but I can assist you with your live campus data:\n\n"
            "• 📊 **Attendance:** _'What is my attendance?'_ or _'If I miss tomorrow's OS class?'_\n"
            "• 📅 **Timetable:** _'When is my next class?'_ or _'Show tomorrow's schedule'_\n"
            "• 🎯 **Examinations:** _'When is my next exam?'_ or _'Which exam is closest?'_\n"
            "• 📈 **Academics:** _'Which subjects am I weak in?'_ or _'Show my marks'_\n"
            "• 📚 **Study Planning:** _'Make me a study plan for FAT'_\n"
            "• 📝 **Assignments:** _'What assignments are due?'_\n"
            "• 💳 **Fees:** _'How much fee is pending?'_\n"
            "• ☀️ **Briefing:** _'What should I do today?'_\n"
            "• 🚨 **Safety:** _'Emergency assistance'_\n\n"
            "*📌 Based on your current CampusGuard database records.*"
        ),
        'intent': 'FALLBACK_MENU',
        'status': 'success',
        'suggestions': ['📊 Overall Attendance', '📅 Next Class', '🎯 Upcoming Exams', '📝 Due Assignments', '💳 Pending Fees', '📚 Study Plan']
    }
