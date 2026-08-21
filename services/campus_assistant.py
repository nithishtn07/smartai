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
