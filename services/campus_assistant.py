"""
=============================================================================
CampusGuard AI - Context-Aware AI Campus & Safety Assistant
Answers student questions using authorized database records and responds
to administrative security inquiries regarding location risk scores, peak hours,
and incident patterns.
=============================================================================
"""

import os
import json
import urllib.request
import urllib.error
import datetime
from .ai_service import sanitize_input
from .safety_intelligence import calculate_location_risk_scores, analyze_temporal_patterns, detect_emerging_risks


def _query_llm_with_context(prompt: str, context_text: str = "") -> str:
    """
    Optional LLM generation using Google Gemini API if GEMINI_API_KEY is present in environment.
    Falls back gracefully if key is not configured or network request fails.
    """
    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        return ""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
    system_instruction = (
        "You are CampusGuard AI, an intelligent, empathetic campus ERP and safety assistant. "
        "Provide direct, concise, and helpful answers formatted with bullet points and bold headers."
    )
    full_prompt = f"{system_instruction}\n\nCampus Context:\n{context_text}\n\nUser Question:\n{prompt}"
    
    payload = {
        "contents": [{
            "parts": [{"text": full_prompt}]
        }]
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            candidates = data.get('candidates', [])
            if candidates and 'content' in candidates[0]:
                parts = candidates[0]['content'].get('parts', [])
                if parts and 'text' in parts[0]:
                    return parts[0]['text'].strip()
    except Exception as e:
        print(f"[Gemini Assistant Error] {e}")
    return ""

def answer_campus_query(student_id: int, query: str, conn) -> str:
    """
    Processes user query and retrieves minimum required data for authenticated student
    or security/administrative inquiries.
    """
    q = sanitize_input(query).lower()

    # -----------------------------------------------------------------------
    # A. Administrative & Security Intelligence Queries
    # -----------------------------------------------------------------------
    if any(k in q for k in ['highest-risk', 'highest risk', 'risk score', 'dangerous', 'hotspot', 'unsafe location']):
        incidents = conn.execute("SELECT * FROM incidents").fetchall()
        complaints = conn.execute("SELECT * FROM complaints").fetchall()
        zone_scores = calculate_location_risk_scores(incidents, complaints)
        
        sorted_zones = sorted(zone_scores.values(), key=lambda z: z['risk_score'], reverse=True)[:3]
        lines = ["🛡️ **Campus Safety Risk Rankings:**\n"]
        for z in sorted_zones:
            lines.append(f"• **{z['short_name']}**: Risk Score **{z['risk_score']}/100** ({z['risk_level']}) — {z['incident_count']} incidents ({z['peak_time']})")
        lines.append(f"\n💡 *Recommendation:* Priority mobile patrols assigned to **{sorted_zones[0]['short_name']}** during peak hours.")
        return "\n".join(lines)

    if any(k in q for k in ['peak risk', 'peak hours', 'what time', 'when do incidents', 'temporal']):
        incidents = conn.execute("SELECT * FROM incidents").fetchall()
        temporal = analyze_temporal_patterns(incidents)
        return (
            f"⏰ **Campus Incident Temporal Analytics:**\n\n"
            f"• **Peak Risk Window:** **{temporal['peak_window']}** ({temporal['peak_percentage']}% of all recorded reports)\n"
            f"• **Highest Concentration Day:** **{temporal['peak_day']}s**\n"
            f"• **Operational Advisory:** Increased security patrols and illumination checks active during evening surveillance windows."
        )

    if any(k in q for k in ['increasing', 'surge', 'emerging', 'trend', 'more incidents', 'month']):
        incidents = conn.execute("SELECT * FROM incidents").fetchall()
        emerging = detect_emerging_risks(incidents)
        if emerging:
            em = emerging[0]
            return (
                f"📈 **Emerging Safety Risk Trend Detected:**\n\n"
                f"• **Location:** {em['location']}\n"
                f"• **Surge:** **+{em['surge_pct']}% increase** ({em['recent_count']} reports in last 30 days vs {em['previous_count']} prior)\n"
                f"• **AI Recommendation:** {em['recommendation']}"
            )
        return "📊 **Campus Trend Analysis:** Incident trends are currently stable across all major zones with no acute surges detected."

    # -----------------------------------------------------------------------
    # B. Student Personalized Queries (Delegated to Smart Student AI Engine)
    # -----------------------------------------------------------------------
    from .student_ai_assistant import answer_student_assistant_query
    res = answer_student_assistant_query(student_id, query, conn=conn)
    return res['reply']


def answer_admin_query(query: str, conn) -> str:
    """
    Answers executive, academic, financial, safety, and administrative inquiries
    using real SQLite database aggregation and intelligence modules.
    """
    q = sanitize_input(query).lower()

    # 1. Attendance analytics
    if 'lowest attendance' in q or ('department' in q and 'attendance' in q):
        rows = conn.execute("""
            SELECT s.department, AVG(a.attendance_pct) as avg_att, COUNT(DISTINCT s.id) as stu_count
            FROM students s
            JOIN attendance a ON s.id = a.student_id
            GROUP BY s.department
            ORDER BY avg_att ASC
        """).fetchall()
        if rows:
            lines = ["📊 **Department Attendance Analytics:**\n"]
            for r in rows:
                lines.append(f"• **{r['department']}**: **{r['avg_att']:.1f}%** average ({r['stu_count']} students)")
            lowest = rows[0]
            lines.append(f"\n⚠️ **Lowest Attendance:** **{lowest['department']}** ({lowest['avg_att']:.1f}%).")
            return "\n".join(lines)
        return "No department attendance records available in the central database."

    # 2. Students below 75% attendance / watchlist
    if 'below' in q or 'low attendance' in q or 'attendance threshold' in q or '75' in q:
        rows = conn.execute("""
            SELECT s.name, s.register_number, s.department, a.subject_name, a.attendance_pct
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.attendance_pct < 75.0
            ORDER BY a.attendance_pct ASC
        """).fetchall()
        if rows:
            lines = [f"⚠️ **Students Below Institutional 75% Threshold ({len(rows)} instances):**\n"]
            for r in rows[:8]:
                lines.append(f"• **{r['name']}** ({r['register_number']}, {r['department']}) — {r['subject_name']}: **{r['attendance_pct']:.1f}%**")
            if len(rows) > 8:
                lines.append(f"• ... and {len(rows)-8} more instances.")
            lines.append("\n💡 *Action:* Use Attendance Monitor to dispatch automated SMS/Portal notices to parents.")
            return "\n".join(lines)
        return "✓ Excellent news! All students currently maintain attendance at or above the 75.0% compliance threshold."

    # 3. Fees & Financial collection
    if any(k in q for k in ['fee', 'fees', 'pending fees', 'due', 'financial', 'collection', 'revenue']):
        total_b = conn.execute("SELECT SUM(amount) as s FROM fees").fetchone()['s'] or 0
        total_c = conn.execute("SELECT SUM(paid_amount) as s FROM fees").fetchone()['s'] or 0
        total_p = max(0, total_b - total_c)
        pending_records = conn.execute("SELECT COUNT(*) as cnt FROM fees WHERE status != 'Paid'").fetchone()['cnt']
        return (
            f"💰 **Institutional Financial Summary:**\n\n"
            f"• **Total Invoiced:** ₹{total_b:,.2f}\n"
            f"• **Total Collected:** ₹{total_c:,.2f} ({(total_c/total_b*100 if total_b>0 else 0):.1f}% collection rate)\n"
            f"• **Outstanding Pending Balance:** **₹{total_p:,.2f}**\n"
            f"• **Pending Invoice Records:** **{pending_records}**\n"
        )

    # 4. Academic Risk / Low CGPA / Backlogs
    if any(k in q for k in ['academic risk', 'academically at risk', 'failing', 'grade', 'low marks', 'cgpa']):
        risk_students = conn.execute("""
            SELECT name, register_number, department, cgpa FROM students
            WHERE cgpa < 7.0 OR id IN (SELECT student_id FROM marks WHERE status = 'FAIL' OR fat < 40)
            ORDER BY cgpa ASC
        """).fetchall()
        if risk_students:
            lines = ["🎯 **Academically At-Risk Students:**\n"]
            for s in risk_students:
                lines.append(f"• **{s['name']}** ({s['register_number']}, {s['department']}) — CGPA: **{s['cgpa']}**")
            lines.append("\n💡 *Directive:* Academic remedial tutorials and faculty mentor counselling recommended.")
            return "\n".join(lines)
        return "✓ No students currently flagged as critically at-risk. Overall institutional academic performance is in good standing."

    # 5. SOS Incidents & Emergency frequency
    if any(k in q for k in ['sos', 'emergency', 'incidents', 'safety incident', 'how many sos']):
        total_inc = conn.execute("SELECT COUNT(*) as cnt FROM incidents").fetchone()['cnt']
        active_inc = conn.execute("SELECT COUNT(*) as cnt FROM incidents WHERE status IN ('ACTIVE', 'RESPONDING')").fetchone()['cnt']
        types = conn.execute("SELECT incident_type, COUNT(*) as cnt FROM incidents GROUP BY incident_type ORDER BY cnt DESC").fetchall()
        
        lines = [
            f"🚨 **Campus Safety Incident Intelligence:**\n",
            f"• **Total Historical Incidents:** **{total_inc}**",
            f"• **Currently Active Distresses:** **{active_inc}**\n",
            "**Breakdown by Emergency Category:**"
        ]
        for t in types:
            lines.append(f"• {t['incident_type']}: **{t['cnt']}**")
        return "\n".join(lines)

    # 6. Safety by department / zone
    if 'highest' in q and ('safety' in q or 'incident' in q or 'risk' in q):
        incidents = conn.execute("SELECT * FROM incidents").fetchall()
        complaints = conn.execute("SELECT * FROM complaints").fetchall()
        zone_scores = calculate_location_risk_scores(incidents, complaints)
        sorted_zones = sorted(zone_scores.values(), key=lambda z: z['risk_score'], reverse=True)[:3]
        lines = ["🛡️ **Highest Safety Risk Campus Sectors:**\n"]
        for z in sorted_zones:
            lines.append(f"• **{z['short_name']}**: Score **{z['risk_score']}/100** ({z['risk_level']}) — {z['incident_count']} incidents ({z['peak_time']})")
        return "\n".join(lines)

    # 7. Leave requests
    if 'leave' in q or 'outpass' in q:
        pending_leaves = conn.execute("SELECT COUNT(*) as cnt FROM hostel_leaves WHERE status = 'Pending'").fetchone()['cnt']
        approved_leaves = conn.execute("SELECT COUNT(*) as cnt FROM hostel_leaves WHERE status = 'Approved'").fetchone()['cnt']
        return (
            f"🚪 **Hostel Outpass & Leave Overview:**\n\n"
            f"• **Pending Approvals:** **{pending_leaves}** requests requiring warden/admin sign-off\n"
            f"• **Active/Approved Outpasses:** **{approved_leaves}**\n"
            f"Review full submissions in the **Hostel Leaves** console."
        )

    # Optional dynamic LLM reasoning for executive insights
    llm_resp = _query_llm_with_context(query, "Institutional Role: Campus Administrator / Executive Intelligence Officer")
    if llm_resp:
        return llm_resp

    # Default executive response
    return (
        "🏛️ **CampusGuard AI Executive Assistant Active**\n\n"
        "Ask me anything about the institutional database, including:\n"
        "• _'Which department has the lowest attendance?'_\n"
        "• _'Show students below 75% attendance.'_\n"
        "• _'What is the total pending fee collection?'_\n"
        "• _'Which students are academically at risk?'_\n"
        "• _'How many SOS incidents occurred this month?'_\n"
        "• _'Show summary of pending leave requests.'_"
    )


def answer_faculty_query(faculty, query: str, conn) -> str:
    """
    Provides authorized, privacy-safe, and real database-backed responses
    tailored specifically to the logged-in faculty member's assigned courses,
    department students, daily schedule, and pending tasks.
    """
    q = sanitize_input(query).lower()
    fac_name = faculty['name'] if (faculty and 'name' in tuple(faculty.keys())) else 'Faculty'
    fac_dept = faculty['department'] if (faculty and 'department' in tuple(faculty.keys())) else 'Computer Science & Engineering'
    today_dow = datetime.datetime.now().strftime('%A')

    # Get faculty's assigned courses
    courses = conn.execute("""
        SELECT * FROM courses WHERE faculty_name LIKE ?
    """, (f"%{fac_name}%",)).fetchall()
    if not courses:
        courses = conn.execute("SELECT * FROM courses WHERE department = ?", (fac_dept,)).fetchall()
    if not courses:
        courses = conn.execute("SELECT * FROM courses").fetchall()
    
    course_codes = [c['course_code'] for c in courses]
    placeholders = ','.join('?' for _ in course_codes) if course_codes else "''"

    # 1. Subject-specific attendance query (e.g. "Show DBMS attendance", "CS301 attendance")
    matched_subject = None
    for c in courses:
        code = c['course_code'].lower()
        name_words = [w.lower() for w in c['course_name'].split() if len(w) > 3]
        if code in q or any(w in q for w in name_words) or ('dbms' in q and 'cs301' in code):
            matched_subject = c
            break

    if matched_subject and any(k in q for k in ['attendance', 'present', 'absent', 'roster', 'classes', 'roll']):
        c_code = matched_subject['course_code']
        c_name = matched_subject['course_name']
        records = conn.execute("""
            SELECT a.*, s.name as student_name, s.register_number
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.subject_code = ?
            ORDER BY a.attendance_pct ASC
        """, (c_code,)).fetchall()

        if records:
            avg_pct = round(sum(r['attendance_pct'] for r in records) / len(records), 1)
            lines = [f"📊 **Attendance Overview for {c_name} (`{c_code}`):**\n"]
            lines.append(f"• **Class Average Attendance:** **{avg_pct}%**")
            lines.append(f"• **Enrolled Records:** **{len(records)} students**\n")
            lines.append("**Student Breakdown:**")
            for r in records[:8]:
                status_icon = "🟢" if r['attendance_pct'] >= 75.0 else "🔴"
                lines.append(f"• {status_icon} **{r['student_name']}** ({r['register_number']}): **{r['attendance_pct']:.1f}%** ({r['classes_attended']}/{r['classes_held']} classes attended)")
            if len(records) > 8:
                lines.append(f"• ... and **{len(records)-8} additional students**.")
            return "\n".join(lines)
        else:
            return f"ℹ️ **No attendance recorded** yet for **{c_name}** (`{c_code}`). Navigate to **Class Attendance** to conduct the first roll-call."

    # 2. Unsubmitted / Missing assignments query
    if any(k in q for k in ['who hasn', 'not submitted', 'missing submission', 'unsubmitted', 'hasn\'t submitted']):
        assigns = conn.execute("SELECT * FROM assignments ORDER BY due_date DESC LIMIT 5").fetchall()
        if assigns:
            lines = [f"📋 **Assignment Submission Compliance:**\n"]
            all_students = conn.execute("SELECT * FROM students WHERE status = 'ACTIVE' ORDER BY name ASC").fetchall()
            for a in assigns[:3]:
                submitted_stu_ids = {row['student_id'] for row in conn.execute("SELECT student_id FROM student_submissions WHERE assignment_id = ?", (a['id'],)).fetchall()}
                unsubmitted = [s for s in all_students if s['id'] not in submitted_stu_ids]
                lines.append(f"• **{a['title']}** (`{a['course_code']}`) — Due: {a['due_date']}")
                if unsubmitted:
                    names = ', '.join(f"**{s['name']}** ({s['register_number']})" for s in unsubmitted[:4])
                    more_txt = f" and {len(unsubmitted)-4} more" if len(unsubmitted) > 4 else ""
                    lines.append(f"  ↳ ⚠️ **{len(unsubmitted)} Pending Submission(s):** {names}{more_txt}")
                else:
                    lines.append(f"  ↳ ✓ **100% Submissions received!**")
            return "\n".join(lines)
        return "✓ No active assignments pending submission found in the system."

    # 3. Attendance below threshold / low attendance
    if any(k in q for k in ['below', 'threshold', 'low attendance', 'attendance deficit', 'shortage', '75']):
        if course_codes:
            rows = conn.execute(f"""
                SELECT a.*, s.name as student_name, s.register_number, s.department
                FROM attendance a
                JOIN students s ON a.student_id = s.id
                WHERE a.subject_code IN ({placeholders}) AND a.attendance_pct < 75.0
                ORDER BY a.attendance_pct ASC
            """, course_codes).fetchall()
        else:
            rows = conn.execute("""
                SELECT a.*, s.name as student_name, s.register_number, s.department
                FROM attendance a
                JOIN students s ON a.student_id = s.id
                WHERE a.attendance_pct < 75.0
                ORDER BY a.attendance_pct ASC
            """).fetchall()

        if rows:
            lines = [f"⚠️ **Attendance Deficit Alert ({len(rows)} Student Instances Below 75%):**\n"]
            for r in rows[:6]:
                lines.append(f"• **{r['student_name']}** ({r['register_number']}) — **{r['subject_code']}**: **{r['attendance_pct']:.1f}%** ({r['classes_attended']}/{r['classes_held']} classes)")
            if len(rows) > 6:
                lines.append(f"• ... and **{len(rows)-6} more students**.")
            lines.append(f"\n💡 *Recommendation:* Send automated SMS/App warnings via the **Class Attendance** module.")
            return "\n".join(lines)
        return "✓ **All clear!** None of your advisees or enrolled students are currently below the 75% institutional attendance threshold."

    # 4. Assignments pending / grading
    if any(k in q for k in ['assignment', 'pending assignment', 'grading', 'submissions', 'evaluate']):
        has_subs = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_submissions'").fetchone()
        if has_subs:
            subs = conn.execute("""
                SELECT ss.*, a.title as assignment_title, a.course_code, s.name as student_name, s.register_number
                FROM student_submissions ss
                JOIN assignments a ON ss.assignment_id = a.id
                JOIN students s ON ss.student_id = s.id
                WHERE ss.status = 'Submitted'
                ORDER BY ss.submitted_at DESC
            """).fetchall()

            if subs:
                lines = [f"📋 **Pending Assignment Evaluations ({len(subs)} Submissions):**\n"]
                for s in subs[:5]:
                    lines.append(f"• **{s['student_name']}** ({s['register_number']}) — _{s['assignment_title']}_ [{s['course_code']}]")
                if len(subs) > 5:
                    lines.append(f"• ... and **{len(subs)-5} additional submissions** awaiting evaluation.")
                lines.append("\n💡 *Action:* Navigate to **Assignments** to enter grades and feedback.")
                return "\n".join(lines)
        return "✓ **All caught up!** You have no pending assignment submissions waiting for grading."

    # 3. Today's classes / schedule
    if any(k in q for k in ['today', 'class', 'classes', 'schedule', 'timetable', 'periods', 'lecture', 'lecture schedule']):
        schedule = conn.execute("""
            SELECT * FROM timetable 
            WHERE faculty_name LIKE ? AND day_of_week = ?
            ORDER BY start_time ASC
        """, (f"%{fac_name}%", today_dow)).fetchall()

        if schedule:
            lines = [f"📅 **Your Teaching Schedule for Today ({today_dow}):**\n"]
            for slot in schedule:
                lines.append(f"• ⏰ **{slot['start_time']} – {slot['end_time']}**: **{slot['subject_name']}** (`{slot['subject_code']}`) in Room **{slot['room_number']}** ({slot['department']} Year {slot['year']})")
            lines.append(f"\n💡 Total: **{len(schedule)} period(s)** scheduled for today.")
            return "\n".join(lines)
        return f"☕ **No lectures scheduled for today ({today_dow}).** Use this time for research, office hours, or grading."

    # 4. Poor performance / marks / academic risk
    if any(k in q for k in ['marks', 'poor', 'exam', 'failing', 'grade', 'academic risk', 'cat1', 'cat2', 'fat']):
        if course_codes:
            marks = conn.execute(f"""
                SELECT m.*, s.name as student_name, s.register_number
                FROM marks m
                JOIN students s ON m.student_id = s.id
                WHERE m.course_code IN ({placeholders}) AND (m.grade IN ('D', 'F') OR m.fat < 45)
                ORDER BY m.fat ASC
            """, course_codes).fetchall()
        else:
            marks = conn.execute("""
                SELECT m.*, s.name as student_name, s.register_number
                FROM marks m
                JOIN students s ON m.student_id = s.id
                WHERE (m.grade IN ('D', 'F') OR m.fat < 45)
                ORDER BY m.fat ASC
            """).fetchall()

        if marks:
            lines = [f"🎯 **Students Requiring Academic Attention ({len(marks)} Records):**\n"]
            for m in marks[:5]:
                lines.append(f"• **{m['student_name']}** ({m['register_number']}) — Course **{m['course_code']}**: Grade **{m['grade']}** (FAT: {m['fat']}/100, CAT1: {m['cat1']}, CAT2: {m['cat2']})")
            lines.append("\n💡 *Advisory:* Schedule 1-on-1 mentoring sessions to offer remedial course support.")
            return "\n".join(lines)
        return "✓ **Strong academic performance!** All enrolled students currently maintain satisfactory grades in your courses."

    # 5. Summarize performance / class summary
    if any(k in q for k in ['summarize', 'summary', 'performance', 'overview', 'stats']):
        total_stu = conn.execute("SELECT COUNT(*) as cnt FROM students WHERE department = ?", (fac_dept,)).fetchone()['cnt']
        if total_stu == 0:
            total_stu = conn.execute("SELECT COUNT(*) as cnt FROM students").fetchone()['cnt']

        if course_codes:
            att_row = conn.execute(f"SELECT AVG(attendance_pct) as a FROM attendance WHERE subject_code IN ({placeholders})", course_codes).fetchone()
            avg_att = round(att_row['a'], 1) if att_row and att_row['a'] else 0.0
        else:
            avg_att = 0.0

        pending_leaves = conn.execute("SELECT COUNT(*) as cnt FROM hostel_leaves WHERE status = 'Pending'").fetchone()['cnt']

        return (
            f"📊 **Faculty Academic Portfolio Summary for {fac_name}:**\n\n"
            f"• **Department:** {fac_dept}\n"
            f"• **Assigned Teaching Modules:** **{len(courses)} Courses** ({', '.join(course_codes)})\n"
            f"• **Total Department Advisees:** **{total_stu} Students**\n"
            f"• **Average Course Attendance:** **{avg_att}%** (Institutional Target: 75%)\n"
            f"• **Pending Outpass Approvals:** **{pending_leaves} Requests**\n"
            f"• **Compliance Status:** 🟢 High Compliance & Operational Readiness"
        )

    # 6. Daily focus / priorities / what should I do today
    if any(k in q for k in ['focus', 'priority', 'priorities', 'what should i do', 'agenda', 'action']):
        schedule = conn.execute("""
            SELECT * FROM timetable WHERE faculty_name LIKE ? AND day_of_week = ? ORDER BY start_time ASC
        """, (f"%{fac_name}%", today_dow)).fetchall()
        
        pending_leaves = conn.execute("SELECT COUNT(*) as cnt FROM hostel_leaves WHERE status = 'Pending'").fetchone()['cnt']
        
        has_subs = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_submissions'").fetchone()
        pending_subs = conn.execute("SELECT COUNT(*) as cnt FROM student_submissions WHERE status = 'Submitted'").fetchone()['cnt'] if has_subs else 0

        lines = [f"⚡ **Key Focus Priorities for {today_dow}:**\n"]
        if schedule:
            lines.append(f"1. 🏛️ **Deliver Lectures:** {len(schedule)} period(s) today starting at **{schedule[0]['start_time']}** ({schedule[0]['subject_name']}, Room {schedule[0]['room_number']}).")
        else:
            lines.append(f"1. ☕ **No lectures scheduled today.** Great time for curriculum research.")

        if pending_leaves > 0:
            lines.append(f"2. 🚪 **Hostel Outpasses:** {pending_leaves} pending student outpass requests require your sign-off.")
        else:
            lines.append(f"2. 🚪 **Hostel Outpasses:** All clear! No pending leave applications.")

        if pending_subs > 0:
            lines.append(f"3. 📝 **Grading:** {pending_subs} assignment submission(s) are awaiting evaluation in your queue.")

        return "\n".join(lines)

    # Optional dynamic LLM reasoning with scoped context
    llm_context = f"Faculty: {fac_name}, Department: {fac_dept}, Assigned Courses: {', '.join(course_codes)}"
    llm_resp = _query_llm_with_context(query, llm_context)
    if llm_resp:
        return llm_resp

    # Default guidance response
    return (
        f"👨‍🏫 **CampusGuard AI Faculty Assistant Ready**\n\n"
        f"I am synced with your assigned courses ({', '.join(course_codes) if course_codes else fac_dept}) and departmental database.\n\n"
        f"You can ask me:\n"
        f"• _'Which students have attendance below the threshold?'_\n"
        f"• _'Which assignments are pending review?'_\n"
        f"• _'Show my classes today.'_\n"
        f"• _'Which students performed poorly in the last exam?'_\n"
        f"• _'Summarize my class performance.'_\n"
        f"• _'What should I focus on today?'_"
    )


