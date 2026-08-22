"""
=============================================================================
CampusGuard AI - Context-Aware AI Campus & Safety Assistant
Answers student questions using authorized database records and responds
to administrative security inquiries regarding location risk scores, peak hours,
and incident patterns.
=============================================================================
"""

import datetime
from .ai_service import sanitize_input
from .safety_intelligence import calculate_location_risk_scores, analyze_temporal_patterns, detect_emerging_risks

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
    # B. Student Personalized Queries (Attendance, Classes, Fees, SOS)
    # -----------------------------------------------------------------------
    # 1. Attendance Queries
    if 'attendance' in q or 'lowest' in q or 'absent' in q or 'bunk' in q:
        records = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (student_id,)).fetchall()
        if not records:
            return "You do not have any registered attendance records in the database."

        if 'lowest' in q:
            lowest = min(records, key=lambda x: x['attendance_pct'])
            return (
                f"⚠️ **Lowest Attendance Subject:**\n\n"
                f"• **{lowest['subject_name']} ({lowest['subject_code']})** is currently at **{lowest['attendance_pct']}%** "
                f"({lowest['classes_attended']}/{lowest['classes_held']} classes attended).\n"
                f"Regular attendance in upcoming classes is recommended to stay above 75%."
            )
        
        total_held = sum(r['classes_held'] for r in records)
        total_attended = sum(r['classes_attended'] for r in records)
        overall_pct = round((total_attended / total_held * 100), 1) if total_held > 0 else 0.0

        lines = [f"📊 **Your Overall Academic Attendance is {overall_pct}%**\n"]
        for r in records:
            status_emoji = "🟢" if r['attendance_pct'] >= 85 else ("🟡" if r['attendance_pct'] >= 75 else "🔴")
            lines.append(f"• {status_emoji} {r['subject_name']}: **{r['attendance_pct']}%** ({r['classes_attended']}/{r['classes_held']})")
        
        lines.append("\nMinimum institutional compliance is **75.0%**.")
        return "\n".join(lines)

    # 2. Timetable, Next Class & Tomorrow's Schedule
    if any(k in q for k in ['tomorrow', 'next class', 'class', 'timetable', 'where', 'lecture', 'room']):
        student = conn.execute("SELECT department, year FROM students WHERE id = ?", (student_id,)).fetchone()
        dept = student['department'] if student else 'Computer Science'
        year = student['year'] if student else 3

        if 'tomorrow' in q:
            tomorrow_date = datetime.datetime.now() + datetime.timedelta(days=1)
            tomorrow_name = tomorrow_date.strftime('%A')
            classes = conn.execute("""
                SELECT * FROM timetable WHERE department = ? AND year = ? AND day_of_week = ?
                ORDER BY start_time ASC
            """, (dept, year, tomorrow_name)).fetchall()

            if not classes:
                return f"📅 **Tomorrow ({tomorrow_name}):** You have no scheduled lectures. Use this day for project research and assignment preparation."
            
            lines = [f"📅 **Your Class Schedule for Tomorrow ({tomorrow_name}):**\n"]
            for c in classes:
                lines.append(f"• **{c['start_time']} - {c['end_time']}**: {c['subject_name']} ({c['subject_code']}) in 📍 **{c['room_number']}** ({c['faculty_name']})")
            return "\n".join(lines)

        # Next class today
        today_name = datetime.datetime.now().strftime('%A')
        classes = conn.execute("""
            SELECT * FROM timetable WHERE department = ? AND year = ? AND day_of_week = ?
            ORDER BY start_time ASC
        """, (dept, year, today_name)).fetchall()

        if not classes:
            classes = conn.execute("""
                SELECT * FROM timetable WHERE department = ? AND year = ? AND day_of_week = 'Monday'
                ORDER BY start_time ASC
            """, (dept, year)).fetchall()
            today_name = "Monday (Preview)"

        if classes:
            c = classes[0]
            return (
                f"⏰ **Next Lecture on {today_name}:**\n\n"
                f"• **Subject:** {c['subject_name']} ({c['subject_code']})\n"
                f"• **Time:** {c['start_time']} - {c['end_time']}\n"
                f"• **Lecture Hall:** 📍 **{c['room_number']}**\n"
                f"• **Faculty:** {c['faculty_name']}"
            )

    # 3. Complaints & Grievance Queries
    if any(k in q for k in ['complaint', 'grievance', 'ticket', 'status']):
        if 'how' in q or 'submit' in q:
            return (
                "📝 **How to Submit a Complaint:**\n\n"
                "1. Navigate to **Grievance Tickets** from the left sidebar.\n"
                "2. Provide a title, specific campus location, and description.\n"
                "3. CampusGuard AI will automatically triage the issue, determine its urgency, and assign it to the responsible department (*Security, Facilities, IT, or Academic Affairs*)."
            )

        complaints = conn.execute("""
            SELECT * FROM complaints WHERE student_id = ? ORDER BY created_at DESC LIMIT 5
        """, (student_id,)).fetchall()

        if not complaints:
            return "You have no active or pending complaints filed in the system."

        pending = [c for c in complaints if c['status'] not in ['Resolved', 'Rejected']]
        lines = [f"📝 **Your Grievance Tickets ({len(pending)} Awaiting Resolution):**\n"]
        for c in complaints:
            lines.append(f"• **{c['complaint_id']}**: {c['title']} — Status: **{c['status']}** (Dept: {c['ai_dept'] or c['category']})")
        return "\n".join(lines)

    # 4. Campus Safety, How to Report, Emergency Instructions
    if any(k in q for k in ['emergency', 'sos', 'safety', 'report', 'police', 'doctor', 'help', 'safe walk', 'walk']):
        if 'report' in q or 'how' in q:
            return (
                "🛡️ **Reporting a Safety Issue:**\n\n"
                "• Visit the **Campus Safety Center** from the sidebar.\n"
                "• Submit an incident report (Harassment, Hazard, Theft, Unsafe Area).\n"
                "• Reports are prioritized by AI and routed directly to Campus Security Command."
            )
        
        if 'emergency' in q or 'sos' in q or 'what should i do' in q:
            return (
                "🚨 **Emergency Protocol & Immediate Actions:**\n\n"
                "1. **Press Emergency SOS:** Tap the red SOS button at the top right of your screen to broadcast an instant GPS distress beacon to the campus Quick Response Team.\n"
                "2. **Direct Helplines:**\n"
                "   • Campus Security Command: 📞 **+91 91234 56780**\n"
                "   • Medical Pavilion & Ambulance: 📞 **+91 91234 56781**\n"
                "   • Women's Safety Liaison: 📞 **+91 91234 56782**\n"
                "3. Move to the nearest illuminated corridor or designated safe beacon pole."
            )

    # 5. Alerts & Broadcasts
    if any(k in q for k in ['alert', 'alerts', 'announcement', 'broadcast']):
        alerts = conn.execute("SELECT * FROM alerts ORDER BY created_at DESC LIMIT 3").fetchall()
        if not alerts:
            return "There are currently no active campus alerts or emergency announcements."
        
        lines = ["🔔 **Latest Campus Safety & Academic Alerts:**\n"]
        for a in alerts:
            lines.append(f"• **[{a['category'].upper()}]** {a['title']}: {a['description']}")
        return "\n".join(lines)

    # 6. CGPA, Marks, Academic Standing
    if any(k in q for k in ['cgpa', 'sgpa', 'marks', 'grade', 'gpa']):
        student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        return (
            f"📈 **Academic Performance:**\n\n"
            f"• **Current CGPA:** **{student['cgpa']} / 10.0**\n"
            f"• **Semester SGPA:** **{student['sgpa']}**\n"
            f"• **Earned Credits:** **{student['earned_credits']} / {student['total_credits']}**\n"
            f"View detailed course marks in the **Academics & Marks** section."
        )

    # 7. Fees & Finance
    if any(k in q for k in ['fee', 'fees', 'due', 'payment', 'paid']):
        fees = conn.execute("SELECT * FROM fees WHERE student_id = ?", (student_id,)).fetchall()
        total_pending = sum(f['amount'] - f['paid_amount'] for f in fees)
        lines = [f"💳 **Financial Fee Status:**\n• **Outstanding Balance:** **₹{total_pending}**\n"]
        for f in fees:
            p = f['amount'] - f['paid_amount']
            lines.append(f"• {f['fee_type']}: **₹{f['paid_amount']}/₹{f['amount']}** ({'PAID' if p == 0 else 'Due ₹' + str(p)})")
        return "\n".join(lines)

    # Default fallback prompt
    return (
        "🤖 **CampusGuard AI Assistant is ready!**\n\n"
        "I can assist you with:\n"
        "• _'What is my current attendance?'_\n"
        "• _'Which subject has my lowest attendance?'_\n"
        "• _'When is my next class?'_\n"
        "• _'What classes do I have tomorrow?'_\n"
        "• _'What complaints are still pending?'_\n"
        "• _'What are the highest-risk campus locations?'_\n"
        "• _'What are the peak risk hours?'_\n"
        "• _'What should I do during an emergency?'_"
    )


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

