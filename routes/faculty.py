"""
CampusGuard AI — Faculty Portal Routes & Controller
"""

import io
import csv
import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, Response
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db_connection
from models.attendance import AttendanceModel
from utils.decorators import faculty_required
from services.academic_service import calculate_grade_point, sync_student_cgpa, calculate_student_cgpa
from services.notification_service import (
    notify_student,
    notify_parent,
    notify_faculty,
    notify_admin,
    broadcast_announcement,
    log_activity,
    get_system_setting,
    generate_smart_attendance_notification,
    generate_smart_marks_notification,
    generate_smart_cgpa_notification
)
from services.campus_assistant import answer_campus_query, answer_admin_query, answer_faculty_query
from services.ai_insight_engine import (
    evaluate_attendance_risk,
    evaluate_academic_risk,
    generate_student_insights_summary
)

faculty_bp = Blueprint('faculty', __name__)


# ---------------------------------------------------------------------------
# 1. Faculty Dashboard
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/dashboard')
@faculty_required
def faculty_dashboard(faculty):
    conn = get_db_connection()
    try:
        now = datetime.datetime.now()
        today_dow = now.strftime('%A')
        hour = now.hour
        if hour < 12:
            greeting_time = "Good Morning"
        elif hour < 17:
            greeting_time = "Good Afternoon"
        else:
            greeting_time = "Good Evening"

        today_schedule = conn.execute("""
            SELECT * FROM timetable 
            WHERE faculty_name LIKE ? AND day_of_week = ?
            ORDER BY start_time ASC
        """, (f"%{faculty['name']}%", today_dow)).fetchall()

        assigned_courses = conn.execute("""
            SELECT * FROM courses WHERE faculty_name LIKE ?
        """, (f"%{faculty['name']}%",)).fetchall()
        if not assigned_courses:
            assigned_courses = conn.execute("SELECT * FROM courses WHERE department = ?", (faculty['department'],)).fetchall()
        if not assigned_courses:
            assigned_courses = conn.execute("SELECT * FROM courses").fetchall()

        total_students_count = conn.execute("SELECT COUNT(*) as cnt FROM students WHERE department = ?", (faculty['department'],)).fetchone()['cnt']
        if total_students_count == 0:
            total_students_count = conn.execute("SELECT COUNT(*) as cnt FROM students").fetchone()['cnt']

        pending_leaves = conn.execute("""
            SELECT hl.*, s.name as student_name, s.register_number, s.department, s.phone as student_phone
            FROM hostel_leaves hl
            JOIN students s ON hl.student_id = s.id
            WHERE hl.status = 'Pending'
            ORDER BY hl.created_at DESC
        """).fetchall()
        pending_leaves_count = len(pending_leaves)

        # Assignment Submissions Pending Evaluation
        has_subs = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_submissions'").fetchone()
        if has_subs:
            pending_assignments_count = conn.execute("SELECT COUNT(*) as cnt FROM student_submissions WHERE status = 'Submitted'").fetchone()['cnt']
        else:
            pending_assignments_count = conn.execute("SELECT COUNT(*) as cnt FROM assignments WHERE status = 'Submitted'").fetchone()['cnt']

        # Course Attendance Metrics
        course_codes = [c['course_code'] for c in assigned_courses]
        if course_codes:
            placeholders = ','.join('?' for _ in course_codes)
            course_att_rows = conn.execute(f"""
                SELECT subject_code, subject_name, AVG(attendance_pct) as avg_att, COUNT(*) as stu_cnt
                FROM attendance
                WHERE subject_code IN ({placeholders})
                GROUP BY subject_code, subject_name
            """, course_codes).fetchall()
            avg_attendance = round(sum(r['avg_att'] for r in course_att_rows) / len(course_att_rows), 1) if course_att_rows else 0.0
        else:
            course_att_rows = []
            avg_attendance = 0.0

        # Students below 75% threshold in faculty courses
        if course_codes:
            placeholders = ','.join('?' for _ in course_codes)
            low_att_records = conn.execute(f"""
                SELECT a.*, s.name as student_name, s.register_number, s.department, s.phone as student_phone
                FROM attendance a
                JOIN students s ON a.student_id = s.id
                WHERE a.subject_code IN ({placeholders}) AND a.attendance_pct < 75.0
                ORDER BY a.attendance_pct ASC LIMIT 6
            """, course_codes).fetchall()
        else:
            low_att_records = conn.execute("""
                SELECT a.*, s.name as student_name, s.register_number, s.department, s.phone as student_phone
                FROM attendance a
                JOIN students s ON a.student_id = s.id
                WHERE a.attendance_pct < 75.0
                ORDER BY a.attendance_pct ASC LIMIT 6
            """).fetchall()
        low_att_count = len(low_att_records)

        # Unread Messages & Notifications
        unread_messages_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM messages 
            WHERE (receiver_role = 'Faculty' OR receiver_name LIKE ?) AND is_read = 0
        """, (f"%{faculty['name']}%",)).fetchone()['cnt']

        unread_notifications_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM notifications 
            WHERE recipient_role = 'faculty' AND recipient_id = ? AND is_read = 0
        """, (faculty['id'],)).fetchone()['cnt']

        recent_notifications = conn.execute("""
            SELECT * FROM notifications 
            WHERE recipient_role = 'faculty' AND recipient_id = ?
            ORDER BY created_at DESC LIMIT 5
        """, (faculty['id'],)).fetchall()

        announcements = conn.execute("SELECT * FROM announcements ORDER BY created_at DESC LIMIT 4").fetchall()
        today_name = now.strftime('%A')
        current_date_str = now.strftime('%A, %d %B %Y')

        # Next upcoming class
        next_class = today_schedule[0] if today_schedule else (assigned_courses[0] if assigned_courses else None)

        # Assignments Overview (Real Submissions & Evaluations Queue)
        assignments_overview = conn.execute("""
            SELECT a.*,
                   (SELECT COUNT(*) FROM student_submissions ss WHERE ss.assignment_id = a.id) as total_submissions,
                   (SELECT COUNT(*) FROM student_submissions ss WHERE ss.assignment_id = a.id AND ss.status = 'Submitted') as pending_reviews,
                   (SELECT COUNT(*) FROM student_submissions ss WHERE ss.assignment_id = a.id AND ss.status = 'Graded') as graded_count
            FROM assignments a
            WHERE a.faculty_name LIKE ? OR a.course_code IN (SELECT course_code FROM courses WHERE faculty_name LIKE ?)
            ORDER BY a.id DESC LIMIT 4
        """, (f"%{faculty['name']}%", f"%{faculty['name']}%")).fetchall()

        if not assignments_overview:
            assignments_overview = conn.execute("""
                SELECT a.*,
                       (SELECT COUNT(*) FROM student_submissions ss WHERE ss.assignment_id = a.id) as total_submissions,
                       (SELECT COUNT(*) FROM student_submissions ss WHERE ss.assignment_id = a.id AND ss.status = 'Submitted') as pending_reviews,
                       (SELECT COUNT(*) FROM student_submissions ss WHERE ss.assignment_id = a.id AND ss.status = 'Graded') as graded_count
                FROM assignments a
                ORDER BY a.id DESC LIMIT 4
            """).fetchall()

        # Teaching Overview Matrix (Per Course Metrics)
        teaching_overview = []
        for c in assigned_courses:
            c_code = c['course_code']
            att_stats = conn.execute("SELECT AVG(attendance_pct) as avg_p, SUM(classes_held) as held, SUM(classes_attended) as att FROM attendance WHERE subject_code = ?", (c_code,)).fetchone()
            stu_c = conn.execute("SELECT COUNT(DISTINCT student_id) as cnt FROM attendance WHERE subject_code = ?", (c_code,)).fetchone()['cnt']
            if not stu_c or stu_c == 0:
                dept_val = c['department'] if 'department' in tuple(c.keys()) else faculty['department']
                stu_c = conn.execute("SELECT COUNT(*) as cnt FROM students WHERE department = ?", (dept_val,)).fetchone()['cnt'] or 0
            
            c_avg_att = round(att_stats['avg_p'], 1) if att_stats and att_stats['avg_p'] else 0.0
            pending_in_c = conn.execute("""
                SELECT COUNT(*) as cnt FROM student_submissions ss
                JOIN assignments a ON ss.assignment_id = a.id
                WHERE a.course_code = ? AND ss.status = 'Submitted'
            """, (c_code,)).fetchone()['cnt'] if has_subs else 0
            
            teaching_overview.append({
                'course': c,
                'student_count': stu_c,
                'avg_attendance': c_avg_att,
                'pending_evaluations': pending_in_c,
                'is_risk': (c_avg_att > 0 and c_avg_att < 75.0)
            })

        # Dynamically Synthesized Real-Data AI Faculty Insights
        ai_insights_list = []
        if low_att_count > 0:
            ai_insights_list.append({
                'type': 'warning',
                'badge': 'Attendance Watchlist',
                'text': f"{low_att_count} student(s) in your teaching roster are below the institutional 75% attendance compliance standard."
            })
        else:
            ai_insights_list.append({
                'type': 'success',
                'badge': 'High Compliance',
                'text': f"All advisees across your {len(assigned_courses)} assigned course(s) maintain satisfactory attendance (average: {avg_attendance}%)."
            })

        if pending_assignments_count > 0:
            ai_insights_list.append({
                'type': 'info',
                'badge': 'Grading Queue',
                'text': f"{pending_assignments_count} assignment submission(s) are awaiting evaluation and grade entry."
            })

        if pending_leaves_count > 0:
            ai_insights_list.append({
                'type': 'amber',
                'badge': 'Outpass Review',
                'text': f"{pending_leaves_count} hostel outpass application(s) require advisor review and sign-off."
            })

        if teaching_overview:
            best_course = max(teaching_overview, key=lambda x: x['avg_attendance'])
            if best_course['avg_attendance'] > 0:
                ai_insights_list.append({
                    'type': 'trend',
                    'badge': 'Performance Lead',
                    'text': f"Highest student attendance engagement observed in {best_course['course']['course_code']} ({best_course['avg_attendance']}%)."
                })

        # Upcoming Examinations
        upcoming_exams = conn.execute("""
            SELECT * FROM examinations ORDER BY exam_date ASC LIMIT 3
        """).fetchall()

        # Chart Data Preparation (Course-wise Attendance & Average Marks)
        chart_labels = [c['course_code'] for c in assigned_courses[:5]]
        chart_att_data = []
        chart_marks_data = []
        for code in chart_labels:
            att_row = conn.execute("SELECT AVG(attendance_pct) as a FROM attendance WHERE subject_code = ?", (code,)).fetchone()
            chart_att_data.append(round(att_row['a'], 1) if att_row and att_row['a'] else 0.0)

            marks_row = conn.execute("SELECT AVG((cat1+cat2+quiz+assignment+project+fat)/2.0) as m FROM marks WHERE course_code = ?", (code,)).fetchone()
            chart_marks_data.append(round(marks_row['m'], 1) if marks_row and marks_row['m'] else 0.0)

        chart_data = {
            'labels': chart_labels,
            'attendance': chart_att_data,
            'marks': chart_marks_data
        }

        return render_template(
            'faculty/dashboard.html',
            faculty=faculty,
            courses=assigned_courses,
            assigned_courses=assigned_courses,
            total_students=total_students_count,
            total_students_count=total_students_count,
            avg_attendance=avg_attendance,
            pending_leaves=pending_leaves,
            pending_leaves_count=pending_leaves_count,
            pending_assignments_count=pending_assignments_count,
            low_att_students=low_att_count,
            low_att_records=low_att_records,
            greeting_time=greeting_time,
            today_name=today_name,
            current_date_str=current_date_str,
            today_classes=today_schedule,
            today_schedule=today_schedule,
            next_class=next_class,
            assignments_overview=assignments_overview,
            teaching_overview=teaching_overview,
            ai_insights_list=ai_insights_list,
            upcoming_exams=upcoming_exams,
            recent_notifications=recent_notifications,
            unread_messages_count=unread_messages_count,
            unread_notifications_count=unread_notifications_count,
            announcements=announcements,
            chart_data=chart_data,
            active_page='dashboard'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 2. Timetable
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/timetable')
@faculty_required
def faculty_timetable(faculty):
    conn = get_db_connection()
    try:
        schedule = conn.execute("""
            SELECT * FROM timetable 
            WHERE faculty_name LIKE ?
            ORDER BY CASE day_of_week 
                WHEN 'Monday' THEN 1 
                WHEN 'Tuesday' THEN 2 
                WHEN 'Wednesday' THEN 3 
                WHEN 'Thursday' THEN 4 
                WHEN 'Friday' THEN 5 
                WHEN 'Saturday' THEN 6 
                ELSE 7 END, start_time ASC
        """, (f"%{faculty['name']}%",)).fetchall()

        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        timetable_grid = {day: [s for s in schedule if s['day_of_week'] == day] for day in days}

        return render_template(
            'faculty/timetable.html',
            faculty=faculty,
            timetable_grid=timetable_grid,
            timetable_by_day=timetable_grid,
            days=days,
            active_page='timetable'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 3. Subjects & Course Catalog
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/subjects')
@faculty_required
def faculty_subjects(faculty):
    conn = get_db_connection()
    try:
        courses = conn.execute("""
            SELECT * FROM courses WHERE faculty_name LIKE ?
        """, (f"%{faculty['name']}%",)).fetchall()
        if not courses:
            courses = conn.execute("SELECT * FROM courses").fetchall()

        subjects_data = []
        for c in courses:
            subjects_data.append({
                'course': c,
                'student_count': 64,
                'avg_attendance': 92.5
            })

        return render_template(
            'faculty/subjects.html',
            faculty=faculty,
            subjects_data=subjects_data,
            subjects=courses,
            active_page='subjects'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 4. Classes & Cohorts
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/classes')
@faculty_required
def faculty_classes(faculty):
    conn = get_db_connection()
    try:
        cohorts = [
            {
                'class_id': 'CSE-3A',
                'course': 'B.Tech Computer Science & Engineering',
                'section': 'Section A',
                'year': 3,
                'semester': 5,
                'room': 'CS-201',
                'student_count': 64,
                'avg_attendance': 86.4,
                'avg_cgpa': 8.42,
                'rep_name': 'Nithish Nagaraj',
                'rep_reg': 'STU001',
                'subjects': ['CS301 (DBMS)', 'CS302 (OS)', 'CS303 (DS&ML)']
            },
            {
                'class_id': 'CSE-3B',
                'course': 'B.Tech Computer Science & Engineering',
                'section': 'Section B',
                'year': 3,
                'semester': 5,
                'room': 'CS-204',
                'student_count': 62,
                'avg_attendance': 84.1,
                'avg_cgpa': 8.28,
                'rep_name': 'Priya Sharma',
                'rep_reg': 'STU002',
                'subjects': ['CS301 (DBMS)', 'CS304 (Networks)']
            }
        ]

        students = conn.execute("""
            SELECT * FROM students WHERE department = ? ORDER BY register_number ASC
        """, (faculty['department'],)).fetchall()

        return render_template(
            'faculty/classes.html',
            faculty=faculty,
            classes=cohorts,
            students=students,
            active_page='classes'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 5. Students & 360 Degree Profile Inspector
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/students')
@faculty_required
def faculty_students(faculty):
    conn = get_db_connection()
    try:
        search_query = request.args.get('q', '').strip()
        status_filter = request.args.get('status', 'all')

        query = "SELECT * FROM students WHERE (status = 'ACTIVE' OR status IS NULL)"
        params = []

        if search_query:
            query += " AND (name LIKE ? OR register_number LIKE ? OR email LIKE ?)"
            params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

        query += " ORDER BY name ASC"
        students = conn.execute(query, params).fetchall()

        student_cards = []
        for s_row in students:
            s = dict(s_row)
            cgpa, earned_credits, _, _ = calculate_student_cgpa(conn, s['id'])
            s['cgpa'] = cgpa
            s['sgpa'] = cgpa
            if cgpa is not None:
                s['earned_credits'] = earned_credits
            att_rows = conn.execute("SELECT attendance_pct FROM attendance WHERE student_id = ?", (s['id'],)).fetchall()
            avg_att = round(sum(r['attendance_pct'] for r in att_rows) / len(att_rows), 1) if att_rows else 0.0
            student_cards.append({
                'student': s,
                'avg_attendance': avg_att,
                'is_risk': (avg_att > 0 and avg_att < 75.0)
            })

        if status_filter == 'risk':
            student_cards = [sc for sc in student_cards if sc['is_risk']]

        return render_template(
            'faculty/students.html',
            faculty=faculty,
            student_cards=student_cards,
            students=students,
            q=search_query,
            search_query=search_query,
            status_filter=status_filter,
            active_page='students'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/students/view/<int:id>')
@faculty_bp.route('/faculty/students/view/<int:student_id>', endpoint='faculty_student_view_sid')
@faculty_required
def faculty_student_view(faculty, id=None, student_id=None):
    target_id = id if id is not None else student_id
    conn = get_db_connection()
    try:
        student_row = conn.execute("SELECT * FROM students WHERE id = ?", (target_id,)).fetchone()
        if not student_row:
            flash("Student record not found.", "error")
            return redirect(url_for('faculty.faculty_students'))

        student = dict(student_row)
        cgpa, earned_credits, _, _ = calculate_student_cgpa(conn, target_id)
        student['cgpa'] = cgpa
        student['sgpa'] = cgpa
        if cgpa is not None:
            student['earned_credits'] = earned_credits

        attendance = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (target_id,)).fetchall()
        marks = conn.execute("SELECT * FROM marks WHERE student_id = ?", (target_id,)).fetchall()
        parent = conn.execute("SELECT * FROM parents WHERE student_id = ?", (target_id,)).fetchone()
        leaves = conn.execute("SELECT * FROM hostel_leaves WHERE student_id = ? ORDER BY created_at DESC LIMIT 5", (target_id,)).fetchall()
        risk_summary = generate_student_insights_summary(target_id, conn)

        return render_template(
            'faculty/student_view.html',
            faculty=faculty,
            student=student,
            attendance=attendance,
            marks=marks,
            parent=parent,
            leaves=leaves,
            risk_summary=risk_summary,
            active_page='students'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 6. Attendance Management & Date-Specific Roll-Call
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/attendance', methods=['GET', 'POST'])
@faculty_required
def faculty_attendance(faculty):
    conn = get_db_connection()
    try:
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        threshold = float(get_system_setting('attendance_threshold', '75.0'))

        if request.method == 'POST':
            course_code = request.form.get('course_code', 'CS301').strip()
            date_val = request.form.get('date', today_str).strip() or today_str
            topic = request.form.get('topic', 'Classroom Lecture').strip() or 'Classroom Lecture'
            action_type = request.form.get('action_type', '')

            # Date validation
            if date_val > today_str:
                flash("Attendance cannot be logged for future dates.", "error")
                return redirect(url_for('faculty.faculty_attendance', course=course_code, date=today_str))

            course = conn.execute("SELECT * FROM courses WHERE course_code = ?", (course_code,)).fetchone()
            course_name = course['course_name'] if course else course_code
            faculty_id = faculty['id'] if (faculty and 'id' in tuple(faculty.keys())) else 1

            try:
                if action_type == 'batch_roll_call' or not request.form.get('student_id'):
                    student_statuses = {}
                    for k, status_val in request.form.items():
                        if k.startswith('status_'):
                            try:
                                stu_id = int(k.split('_')[1])
                                student_statuses[stu_id] = status_val.strip()
                            except ValueError:
                                continue

                    if not student_statuses:
                        flash("No student records selected for attendance marking.", "error")
                        return redirect(url_for('faculty.faculty_attendance', course=course_code, date=date_val))

                    present_cnt, absent_cnt, results = AttendanceModel.record_batch_attendance(
                        conn, student_statuses, course_code, course_name, date_val, topic, faculty_id
                    )
                    conn.commit()

                    # Trigger smart attendance notifications
                    for stu_id, res in results.items():
                        if res['held'] > 0:
                            generate_smart_attendance_notification(
                                student_id=stu_id,
                                course_code=course_code,
                                course_name=course_name,
                                current_pct=res['pct'],
                                db_conn=conn
                            )

                    flash(f"✅ Class roll call for {course_name} ({course_code}) successfully saved for {date_val} ({present_cnt} Present, {absent_cnt} Absent).", "success")
                    return redirect(url_for('faculty.faculty_attendance', course=course_code, date=date_val))
                else:
                    student_id = int(request.form.get('student_id'))
                    status = request.form.get('status', 'Present').strip()
                    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()

                    held, att, miss, pct = AttendanceModel.record_student_attendance(
                        conn, student_id, course_code, course_name, date_val, status, topic, faculty_id
                    )
                    conn.commit()

                    if held > 0:
                        generate_smart_attendance_notification(
                            student_id=student_id,
                            course_code=course_code,
                            course_name=course_name,
                            current_pct=pct,
                            db_conn=conn
                        )

                    flash(f"✅ Attendance for {student['name'] if student else student_id} on {date_val} successfully recorded as {status}.", "success")
                    return redirect(url_for('faculty.faculty_attendance', course=course_code, date=date_val))
            except Exception as e:
                conn.rollback()
                flash(f"Error saving attendance: {e}", "error")
                return redirect(url_for('faculty.faculty_attendance', course=course_code, date=date_val))

        # Query all available courses and students for the single faculty
        my_courses = conn.execute("SELECT * FROM courses ORDER BY course_code ASC").fetchall()
        if not my_courses:
            my_courses = conn.execute("SELECT * FROM courses").fetchall()
            my_courses = conn.execute("SELECT * FROM courses").fetchall()

        selected_course = request.args.get('course', my_courses[0]['course_code'] if my_courses else 'CS301')
        selected_date = request.args.get('date', today_str).strip() or today_str

        # Query all registered active students across all sections
        students = conn.execute("SELECT * FROM students WHERE (status = 'ACTIVE' OR status IS NULL) ORDER BY name ASC").fetchall()

        # Date-specific logs mapping for pre-populating the roll-call table
        date_logs = conn.execute("""
            SELECT student_id, status, topic FROM attendance_logs
            WHERE course_code = ? AND date = ?
        """, (selected_course, selected_date)).fetchall()

        date_attendance_map = {row['student_id']: row['status'] for row in date_logs}
        date_topic = date_logs[0]['topic'] if date_logs and date_logs[0]['topic'] else ''

        # Overall compliance roster
        attendance_records = conn.execute("""
            SELECT a.*, s.name as student_name, s.register_number
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.subject_code = ?
            ORDER BY s.register_number ASC
        """, (selected_course,)).fetchall()

        # Recent history logs
        recent_logs = conn.execute("""
            SELECT l.*, s.name as student_name, s.register_number
            FROM attendance_logs l
            JOIN students s ON l.student_id = s.id
            WHERE l.course_code = ?
            ORDER BY l.date DESC, l.id DESC LIMIT 40
        """, (selected_course,)).fetchall()

        # Stats
        total_students = len(students)
        avg_att = round(sum(r['attendance_pct'] for r in attendance_records) / len(attendance_records), 1) if attendance_records else 0.0
        shortage_count = sum(1 for r in attendance_records if r['attendance_pct'] < 75.0)
        lectures_held = max([r['classes_held'] for r in attendance_records] + [0])

        stats = {
            'total_students': total_students,
            'avg_attendance': avg_att,
            'shortage_count': shortage_count,
            'lectures_held': lectures_held
        }

        return render_template(
            'faculty/attendance.html',
            faculty=faculty,
            courses=my_courses,
            my_courses=my_courses,
            selected_course=selected_course,
            today_date=today_str,
            selected_date=selected_date,
            students=students,
            date_attendance_map=date_attendance_map,
            date_topic=date_topic,
            attendance_records=attendance_records,
            attendance_list=attendance_records,
            recent_logs=recent_logs,
            stats=stats,
            active_page='attendance'
        )
    finally:
        conn.close()


@faculty_bp.route('/api/faculty/attendance/date-logs')
@faculty_required
def api_faculty_attendance_date_logs(faculty):
    conn = get_db_connection()
    try:
        course_code = request.args.get('course', 'CS301')
        date_val = request.args.get('date', datetime.date.today().strftime('%Y-%m-%d'))

        logs = conn.execute("""
            SELECT l.student_id, l.status, l.topic, s.name as student_name, s.register_number
            FROM attendance_logs l
            JOIN students s ON l.student_id = s.id
            WHERE l.course_code = ? AND l.date = ?
        """, (course_code, date_val)).fetchall()

        records = {str(r['student_id']): r['status'] for r in logs}
        topic = logs[0]['topic'] if logs else ''

        return jsonify({
            'status': 'success',
            'course': course_code,
            'date': date_val,
            'count': len(logs),
            'topic': topic,
            'records': records
        })
    finally:
        conn.close()


@faculty_bp.route('/faculty/attendance/send-warning/<int:student_id>', methods=['POST'])
@faculty_required
def faculty_attendance_send_warning(faculty, student_id):
    conn = get_db_connection()
    try:
        student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        course_code = request.form.get('course_code') or request.form.get('subject_code') or 'CS301'
        if student:
            notify_student(student_id, f"Formal Attendance Warning: {course_code}", f"{faculty['name']} issued a critical attendance reminder. Meet your faculty advisor immediately.", category='Attendance', priority='Critical')
            parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (student_id,)).fetchone()
            if parent:
                notify_parent(parent['id'], f"Attendance Deficit Notice: {student['name']}", f"Official warning issued by {faculty['name']} for {course_code}. Ward attendance is in critical deficit.", category='Attendance', priority='Critical')
        flash(f"Official attendance warning dispatched for {course_code}.", "success")
        return redirect(url_for('faculty.faculty_attendance'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 7. Marks & Continuous Assessment
# ---------------------------------------------------------------------------
# 7. Marks & Continuous Assessment (Individual & Bulk Editing)
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/marks', methods=['GET', 'POST'])
@faculty_required
def faculty_marks(faculty):
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            action_type = request.form.get('action_type', 'single')
            course_code = request.form.get('course_code')
            course = conn.execute("SELECT * FROM courses WHERE course_code = ?", (course_code,)).fetchone()
            course_name = course['course_name'] if course else course_code

            if action_type == 'bulk':
                # Bulk update marks for all students in the selected course
                all_active_students = conn.execute("SELECT id, name, register_number FROM students WHERE status != 'DELETED'").fetchall()
                updated_count = 0
                for s in all_active_students:
                    s_id = s['id']
                    if f"fat_{s_id}" in request.form:
                        try:
                            cat1 = float(request.form.get(f'cat1_{s_id}', 0))
                            cat2 = float(request.form.get(f'cat2_{s_id}', 0))
                            quiz = float(request.form.get(f'quiz_{s_id}', 0))
                            assignment = float(request.form.get(f'assignment_{s_id}', 0))
                            project = float(request.form.get(f'project_{s_id}', 0))
                            fat = float(request.form.get(f'fat_{s_id}', 0))

                            if (quiz + assignment + project) == 0:
                                total_score = ((cat1 + cat2 + fat) / 200.0) * 100.0
                            else:
                                total_score = (cat1 * 0.30) + (cat2 * 0.30) + quiz + assignment + (fat * 0.50)

                            req_grade = request.form.get(f'grade_{s_id}')
                            if req_grade:
                                grade = req_grade
                            elif total_score >= 90: grade = 'S'
                            elif total_score >= 80: grade = 'A'
                            elif total_score >= 70: grade = 'B'
                            elif total_score >= 60: grade = 'C'
                            elif total_score >= 50: grade = 'D'
                            else: grade = 'F'

                            grade_pts = calculate_grade_point(grade, total_score)
                            status = 'FAIL' if grade in ['F', 'FAIL'] else 'PASS'

                            existing = conn.execute("SELECT id FROM marks WHERE student_id = ? AND course_code = ?", (s_id, course_code)).fetchone()
                            if existing:
                                conn.execute("""
                                    UPDATE marks SET cat1 = ?, cat2 = ?, quiz = ?, assignment = ?, project = ?, fat = ?,
                                                     grade = ?, grade_points = ?, status = ?, is_demo = 0
                                    WHERE id = ?
                                """, (cat1, cat2, quiz, assignment, project, fat, grade, grade_pts, status, existing['id']))
                            else:
                                conn.execute("""
                                    INSERT INTO marks (student_id, course_code, course_name, cat1, cat2, quiz, assignment, project, fat, grade, grade_points, status, is_demo)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                                """, (s_id, course_code, course_name, cat1, cat2, quiz, assignment, project, fat, grade, grade_pts, status))

                            prev_cgpa = student['cgpa'] if (student and 'cgpa' in tuple(student.keys())) else None
                            sync_student_cgpa(conn, s_id)
                            new_cgpa_row = conn.execute("SELECT cgpa FROM students WHERE id = ?", (s_id,)).fetchone()
                            new_cgpa = new_cgpa_row['cgpa'] if new_cgpa_row else 0.0

                            generate_smart_marks_notification(
                                student_id=s_id,
                                course_code=course_code,
                                course_name=course_name,
                                assessment_type="Continuous Assessment",
                                marks_obtained=round(total_score, 1),
                                max_marks=100,
                                grade=grade,
                                db_conn=conn
                            )
                            generate_smart_cgpa_notification(
                                student_id=s_id,
                                new_cgpa=new_cgpa,
                                prev_cgpa=prev_cgpa,
                                db_conn=conn
                            )
                            updated_count += 1
                        except (ValueError, TypeError):
                            continue

                conn.commit()
                flash(f"✅ Marks updated successfully for {updated_count} students in {course_code}. CGPA recalculated.", "success")
                return redirect(url_for('faculty.faculty_marks', course=course_code))

            else:
                # Single student marks update
                student_id = int(request.form.get('student_id'))
                cat1 = float(request.form.get('cat1', 0))
                cat2 = float(request.form.get('cat2', 0))
                quiz = float(request.form.get('quiz', 0))
                assignment = float(request.form.get('assignment', 0))
                project = float(request.form.get('project', 0))
                fat = float(request.form.get('fat', 0))

                student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
                prev_cgpa = student['cgpa'] if student else None

                if (quiz + assignment + project) == 0:
                    total_score = ((cat1 + cat2 + fat) / 200.0) * 100.0
                else:
                    total_score = (cat1 * 0.30) + (cat2 * 0.30) + quiz + assignment + (fat * 0.50)

                req_grade = request.form.get('grade')
                if req_grade:
                    grade = req_grade
                elif total_score >= 90: grade = 'S'
                elif total_score >= 80: grade = 'A'
                elif total_score >= 70: grade = 'B'
                elif total_score >= 60: grade = 'C'
                elif total_score >= 50: grade = 'D'
                else: grade = 'F'

                grade_pts = calculate_grade_point(grade, total_score)
                status = 'FAIL' if grade in ['F', 'FAIL'] else 'PASS'

                # Upsert marks
                existing = conn.execute("SELECT id FROM marks WHERE student_id = ? AND course_code = ?", (student_id, course_code)).fetchone()
                if existing:
                    conn.execute("""
                        UPDATE marks SET cat1 = ?, cat2 = ?, quiz = ?, assignment = ?, project = ?, fat = ?,
                                         grade = ?, grade_points = ?, status = ?, is_demo = 0
                        WHERE id = ?
                    """, (cat1, cat2, quiz, assignment, project, fat, grade, grade_pts, status, existing['id']))
                else:
                    conn.execute("""
                        INSERT INTO marks (student_id, course_code, course_name, cat1, cat2, quiz, assignment, project, fat, grade, grade_points, status, is_demo)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """, (student_id, course_code, course_name, cat1, cat2, quiz, assignment, project, fat, grade, grade_pts, status))

                sync_student_cgpa(conn, student_id)
                new_cgpa_row = conn.execute("SELECT cgpa FROM students WHERE id = ?", (student_id,)).fetchone()
                new_cgpa = new_cgpa_row['cgpa'] if new_cgpa_row else 0.0
                conn.commit()

                # Cross-portal synchronization & smart notifications
                generate_smart_cgpa_notification(
                    student_id=student_id,
                    new_cgpa=new_cgpa,
                    prev_cgpa=prev_cgpa,
                    db_conn=conn
                )
                generate_smart_marks_notification(
                    student_id=student_id,
                    course_code=course_code,
                    course_name=course_name,
                    assessment_type="Continuous Assessment",
                    marks_obtained=round(total_score, 1),
                    max_marks=100,
                    grade=grade,
                    db_conn=conn
                )

                flash(f"✅ Marks updated successfully for {student['name'] if student else student_id} ({course_code}). CGPA recalculated.", "success")
                return redirect(url_for('faculty.faculty_marks', course=course_code))

        my_courses = conn.execute("SELECT * FROM courses ORDER BY course_code ASC").fetchall()
        selected_course = request.args.get('course', my_courses[0]['course_code'] if my_courses else 'CS301')

        students = conn.execute("SELECT * FROM students WHERE status != 'DELETED' ORDER BY name ASC").fetchall()

        # Build comprehensive course roster with current marks and live CGPA
        course_roster = []
        for s_row in students:
            s = dict(s_row)
            m = conn.execute("SELECT * FROM marks WHERE student_id = ? AND course_code = ?", (s['id'], selected_course)).fetchone()
            cgpa, earned_credits, _, _ = calculate_student_cgpa(conn, s['id'])
            s['cgpa'] = cgpa
            s['sgpa'] = cgpa
            course_roster.append({
                'student': s,
                'mark': dict(m) if m else None
            })

        marks_records = conn.execute("""
            SELECT m.*, s.name as student_name, s.register_number
            FROM marks m
            JOIN students s ON m.student_id = s.id
            WHERE m.course_code = ? AND s.status != 'DELETED'
            ORDER BY s.register_number ASC
        """, (selected_course,)).fetchall()

        return render_template(
            'faculty/marks.html',
            faculty=faculty,
            my_courses=my_courses,
            courses=my_courses,
            selected_course=selected_course,
            students=students,
            course_roster=course_roster,
            marks_records=marks_records,
            marks_list=marks_records,
            active_page='marks'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 8. Assignments Management
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/assignments', methods=['GET', 'POST'])
@faculty_required
def faculty_assignments(faculty):
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            course_code = request.form.get('course_code')
            title = request.form.get('title')
            description = request.form.get('description')
            due_date = request.form.get('due_date')
            max_marks = float(request.form.get('max_marks', 50))

            course = conn.execute("SELECT * FROM courses WHERE course_code = ?", (course_code,)).fetchone()
            course_name = course['course_name'] if course else course_code

            conn.execute("""
                INSERT INTO assignments (course_code, course_name, title, description, faculty_name, due_date, max_marks)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (course_code, course_name, title, description, faculty['name'], due_date, max_marks))
            conn.commit()

            broadcast_announcement(f"New Assignment: {course_code}", f"{title} has been posted. Due: {due_date}.", category='Academic', priority='Normal', target_audience='Students', author_name=faculty['name'])
            flash(f"Assignment '{title}' published successfully for {course_code}.", "success")
            return redirect(url_for('faculty.faculty_assignments'))

        assignments = conn.execute("SELECT * FROM assignments ORDER BY due_date ASC").fetchall()
        my_courses = conn.execute("SELECT * FROM courses ORDER BY course_code ASC").fetchall()

        return render_template(
            'faculty/assignments.html',
            faculty=faculty,
            assignments=assignments,
            my_courses=my_courses,
            active_page='assignments'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/assignments/submissions/<int:assignment_id>')
@faculty_required
def faculty_assignment_submissions(faculty, assignment_id):
    conn = get_db_connection()
    try:
        assignment = conn.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
        if not assignment:
            flash("Assignment not found.", "error")
            return redirect(url_for('faculty.faculty_assignments'))

        # Query all enrolled active students with their submission/grading status
        students = conn.execute("""
            SELECT st.id as student_id, st.id, st.name, st.name as student_name, st.register_number, st.department, st.year, st.section,
                   ss.id as submission_id, ss.submission_text, ss.attachment_url, ss.status as submission_status,
                   ss.submitted_at, ss.marks_obtained, ss.feedback, ss.graded_at
            FROM students st
            LEFT JOIN student_submissions ss ON st.id = ss.student_id AND ss.assignment_id = ?
            WHERE st.status = 'ACTIVE'
            ORDER BY ss.submitted_at DESC, st.name ASC
        """, (assignment_id,)).fetchall()

        submissions = [s for s in students if s['submission_status'] is not None]

        return render_template(
            'faculty/assignment_submissions.html',
            faculty=faculty,
            assignment=assignment,
            students=students,
            submissions=submissions,
            active_page='assignments'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/assignments/evaluate/<int:assignment_id>', methods=['POST'])
@faculty_required
def faculty_assignment_evaluate(faculty, assignment_id):
    student_id = int(request.form.get('student_id', 1))
    marks_obtained = float(request.form.get('marks_obtained', 0))
    feedback = request.form.get('feedback', '').strip()

    conn = get_db_connection()
    try:
        existing = conn.execute("""
            SELECT id FROM student_submissions WHERE assignment_id = ? AND student_id = ?
        """, (assignment_id, student_id)).fetchone()

        if existing:
            conn.execute("""
                UPDATE student_submissions 
                SET marks_obtained = ?, feedback = ?, status = 'Graded', graded_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (marks_obtained, feedback, existing['id']))
        else:
            conn.execute("""
                INSERT INTO student_submissions (assignment_id, student_id, submission_text, status, marks_obtained, feedback, graded_at)
                VALUES (?, ?, 'Direct Evaluation by Faculty', 'Graded', ?, ?, CURRENT_TIMESTAMP)
            """, (assignment_id, student_id, marks_obtained, feedback))

        conn.commit()

        notify_student(student_id, "Assignment Graded", f"Your assignment submission has been evaluated: {marks_obtained} marks.", category='Academics')
        flash(f"✓ Marks ({marks_obtained} pts) and feedback saved successfully.", "success")
        return redirect(url_for('faculty.faculty_assignment_submissions', assignment_id=assignment_id))
    finally:
        conn.close()


@faculty_bp.route('/faculty/assignments/delete/<int:assignment_id>', methods=['POST'])
@faculty_required
def faculty_assignment_delete(faculty, assignment_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM student_submissions WHERE assignment_id = ?", (assignment_id,))
        conn.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
        conn.commit()
        log_activity(faculty['name'], 'faculty', 'DELETE_ASSIGNMENT', f"Deleted assignment #{assignment_id}", record_id=str(assignment_id))
        flash("Assignment and associated submissions deleted successfully.", "success")
        return redirect(url_for('faculty.faculty_assignments'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 9. Study Materials Repository
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/materials', methods=['GET', 'POST'])
@faculty_required
def faculty_materials(faculty):
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            course_code = request.form.get('course_code')
            title = request.form.get('title')
            material_type = request.form.get('material_type', 'Lecture Notes (PDF)')
            upload_date = datetime.date.today().strftime('%Y-%m-%d')

            conn.execute("""
                INSERT INTO study_materials (course_code, title, material_type, uploaded_date)
                VALUES (?, ?, ?, ?)
            """, (course_code, title, material_type, upload_date))
            conn.commit()
            flash(f"Study material '{title}' successfully uploaded and published.", "success")
            return redirect(url_for('faculty.faculty_materials'))

        my_courses = conn.execute("SELECT * FROM courses WHERE faculty_name LIKE ?", (f"%{faculty['name']}%",)).fetchall()
        materials = conn.execute("SELECT * FROM study_materials ORDER BY uploaded_date DESC").fetchall()
        return render_template(
            'faculty/materials.html',
            faculty=faculty,
            my_courses=my_courses,
            materials=materials,
            active_page='materials'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/materials/upload', methods=['POST'])
@faculty_required
def faculty_materials_upload(faculty):
    course_code = request.form.get('course_code')
    title = request.form.get('title')
    material_type = request.form.get('material_type', 'Lecture Notes (PDF)')
    upload_date = datetime.date.today().strftime('%Y-%m-%d')

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO study_materials (course_code, title, material_type, uploaded_date)
            VALUES (?, ?, ?, ?)
        """, (course_code, title, material_type, upload_date))
        conn.commit()
        flash(f"Study material '{title}' successfully uploaded and published.", "success")
        return redirect(url_for('faculty.faculty_materials'))
    finally:
        conn.close()


@faculty_bp.route('/faculty/materials/delete/<int:material_id>', methods=['POST'])
@faculty_required
def faculty_materials_delete(faculty, material_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM study_materials WHERE id = ?", (material_id,))
        conn.commit()
        flash("Study material removed successfully.", "success")
        return redirect(url_for('faculty.faculty_materials'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 10. Leaves & Outpasses
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/leaves')
@faculty_required
def faculty_leaves(faculty):
    conn = get_db_connection()
    try:
        leaves = conn.execute("""
            SELECT hl.*, s.name as student_name, s.register_number, s.department, s.phone as student_phone
            FROM hostel_leaves hl
            JOIN students s ON hl.student_id = s.id
            WHERE s.department = ?
            ORDER BY hl.created_at DESC
        """, (faculty['department'],)).fetchall()

        return render_template(
            'faculty/leaves.html',
            faculty=faculty,
            leaves=leaves,
            active_page='leaves'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/leaves/decision/<int:leave_id>', methods=['POST'])
@faculty_required
def faculty_leaves_decision(faculty, leave_id):
    decision = request.form.get('decision', 'Approved')
    conn = get_db_connection()
    try:
        conn.execute("UPDATE hostel_leaves SET status = ? WHERE id = ?", (decision, leave_id))
        conn.commit()

        leave = conn.execute("SELECT * FROM hostel_leaves WHERE id = ?", (leave_id,)).fetchone()
        if leave:
            notify_student(leave['student_id'], f"Hostel Outpass {decision}", f"Your outpass application was {decision.lower()} by {faculty['name']}.", category='Leave')
            parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (leave['student_id'],)).fetchone()
            if parent:
                notify_parent(parent['id'], f"Hostel Outpass Decision: {decision}", f"Residential outpass decision {decision} by faculty advisor.", category='Leave')

        flash(f"Student outpass request has been marked as {decision}.", "success")
        return redirect(url_for('faculty.faculty_leaves'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 11. Announcements
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/announcements')
@faculty_required
def faculty_announcements(faculty):
    conn = get_db_connection()
    try:
        announcements = conn.execute("""
            SELECT * FROM announcements 
            WHERE author_name LIKE ? OR target_audience IN ('All', 'Students', 'Faculty')
            ORDER BY created_at DESC
        """, (f"%{faculty['name']}%",)).fetchall()

        my_courses = conn.execute("""
            SELECT * FROM courses WHERE faculty_name LIKE ? OR department = ?
        """, (f"%{faculty['name']}%", faculty['department'])).fetchall()

        return render_template(
            'faculty/announcements.html',
            faculty=faculty,
            announcements=announcements,
            my_courses=my_courses,
            active_page='announcements'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/announcements/create', methods=['POST'])
@faculty_required
def faculty_announcements_create(faculty):
    title = request.form.get('title', '').strip()
    description = (request.form.get('description') or request.form.get('content') or '').strip()
    category = request.form.get('category', 'Academic').strip()
    priority = request.form.get('priority', 'Normal').strip()
    target_audience = request.form.get('target_audience', 'Students').strip()

    if not title or not description:
        flash("Title and description are required for announcements.", "error")
        return redirect(url_for('faculty.faculty_announcements'))

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO announcements (title, description, category, priority, target_audience, author_name)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, description, category, priority, target_audience, faculty['name']))
        conn.commit()

        broadcast_announcement(title, description, category=category, priority=priority, target_audience=target_audience, author_name=faculty['name'])
        flash(f"Announcement '{title}' published successfully.", "success")
        return redirect(url_for('faculty.faculty_announcements'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 12. Messages
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/messages', methods=['GET', 'POST'])
@faculty_required
def faculty_messages(faculty):
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            target = request.form.get('recipient_target')
            student_id = int(request.form.get('student_id', 1)) if not target else None
            receiver_role = request.form.get('receiver_role', 'Student')
            receiver_name = request.form.get('receiver_name', 'Student')
            subject = request.form.get('subject', '').strip()
            content = request.form.get('content', '').strip()

            if target:
                if target.startswith('student_'):
                    student_id = int(target.split('_')[1])
                    receiver_role = 'Student'
                    stu = conn.execute("SELECT name FROM students WHERE id = ?", (student_id,)).fetchone()
                    receiver_name = stu['name'] if stu else 'Student'
                elif target.startswith('parent_'):
                    student_id = int(target.split('_')[1])
                    receiver_role = 'Parent'
                    par = conn.execute("SELECT name FROM parents WHERE student_id = ?", (student_id,)).fetchone()
                    receiver_name = par['name'] if par else 'Parent'
                elif target == 'admin':
                    student_id = 1
                    receiver_role = 'Admin'
                    receiver_name = 'Campus Administrator'

            student_id = student_id if student_id is not None else 1

            conn.execute("""
                INSERT INTO messages (
                    student_id, sender_id, sender_role, sender_name,
                    receiver_id, receiver_role, receiver_name,
                    subject, content, is_read
                ) VALUES (?, ?, 'Faculty', ?, ?, ?, ?, ?, ?, 0)
            """, (
                student_id, faculty['id'], faculty['name'],
                student_id, receiver_role, receiver_name, subject, content
            ))

            if receiver_role == 'Parent' and student_id:
                parent = conn.execute("SELECT * FROM parents WHERE student_id = ?", (student_id,)).fetchone()
                if parent:
                    conn.execute("""
                        INSERT INTO parent_messages (parent_id, student_id, sender_role, sender_name, receiver_name, subject, content)
                        VALUES (?, ?, 'Faculty Advisor', ?, ?, ?, ?)
                    """, (parent['id'], student_id, faculty['name'], parent['name'], subject, content))

            conn.commit()
            flash("Message successfully transmitted.", "success")
            return redirect(url_for('faculty.faculty_messages'))

        students = conn.execute("SELECT * FROM students WHERE department = ? ORDER BY name ASC", (faculty['department'],)).fetchall()
        inbox = conn.execute("""
            SELECT * FROM messages 
            WHERE (receiver_role = 'Faculty' AND (receiver_name LIKE ? OR receiver_id = ?))
               OR (sender_role = 'Faculty' AND sender_id = ?)
            ORDER BY sent_at DESC
        """, (f"%{faculty['name']}%", faculty['id'], faculty['id'])).fetchall()

        return render_template(
            'faculty/messages.html',
            faculty=faculty,
            students=students,
            messages=inbox,
            active_page='messages'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 12. Notifications & Mark Read
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/notifications')
@faculty_required
def faculty_notifications(faculty):
    conn = get_db_connection()
    try:
        notifications = conn.execute("""
            SELECT * FROM notifications 
            WHERE recipient_role = 'faculty' AND recipient_id = ?
            ORDER BY created_at DESC
        """, (faculty['id'],)).fetchall()

        unread_count = sum(1 for n in notifications if not n['is_read'])

        return render_template(
            'faculty/notifications.html',
            faculty=faculty,
            notifications=notifications,
            unread_count=unread_count,
            active_page='notifications'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/notifications/read-all', methods=['POST'])
@faculty_bp.route('/faculty/notifications/mark-all-read', methods=['POST'])
@faculty_required
def faculty_notifications_read_all(faculty):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE recipient_role = 'faculty' AND recipient_id = ?", (faculty['id'],))
        conn.commit()
        flash("All faculty notifications marked as read.", "success")
        return redirect(url_for('faculty.faculty_notifications'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 13. AI Insights & Assistant
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/insights')
@faculty_required
def faculty_insights(faculty):
    conn = get_db_connection()
    try:
        students = conn.execute("SELECT * FROM students WHERE department = ?", (faculty['department'],)).fetchall()
        return render_template(
            'faculty/insights.html',
            faculty=faculty,
            students=students,
            active_page='insights'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/api/ai-insights', methods=['POST'])
@faculty_bp.route('/api/faculty/chat', methods=['POST'])
@faculty_bp.route('/faculty/api/chat', methods=['POST'])
@faculty_required
def faculty_api_ai_insights(faculty):
    data = request.get_json() or {}
    query = (data.get('query') or data.get('message') or '').strip()
    if not query:
        return jsonify({
            'status': 'success',
            'reply': f"Hello Professor {faculty['name']}! Ask me about attendance shortages below 75%, class performance summaries, or exam scoring analytics.",
            'suggestions': ['Which students have attendance below 75%?', 'Summarize class performance', 'Which students need attention?']
        })

    conn = get_db_connection()
    try:
        from services.unified_ai_assistant import process_unified_ai_query
        result = process_unified_ai_query(
            role='faculty',
            user_id=faculty['id'],
            query=query,
            conn=conn
        )
        return jsonify({'status': 'success', 'reply': result.get('reply', ''), 'intent': result.get('intent', '')})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 14. Profile & Security
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/profile', methods=['GET', 'POST'])
@faculty_required
def faculty_profile(faculty):
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'update_info':
                phone = request.form.get('phone', '').strip()
                cabin = request.form.get('cabin', '').strip()
                designation = request.form.get('designation', '').strip()

                conn.execute("""
                    UPDATE faculties SET phone = ?, cabin = ?, designation = ? WHERE id = ?
                """, (phone, cabin, designation, faculty['id']))
                conn.commit()
                flash("Profile details updated successfully.", "success")
                return redirect(url_for('faculty.faculty_profile'))

            elif action == 'change_password':
                current_pw = request.form.get('current_password', '')
                new_pw = request.form.get('new_password', '')
                confirm_pw = request.form.get('confirm_password', '')

                if not check_password_hash(faculty['password_hash'], current_pw):
                    flash("Current password entered is incorrect.", "error")
                elif len(new_pw) < 6:
                    flash("New password must be at least 6 characters.", "error")
                elif new_pw != confirm_pw:
                    flash("New password and confirmation do not match.", "error")
                else:
                    new_hash = generate_password_hash(new_pw)
                    conn.execute("UPDATE faculties SET password_hash = ? WHERE id = ?", (new_hash, faculty['id']))
                    conn.commit()
                    flash("Password updated successfully.", "success")
                return redirect(url_for('faculty.faculty_profile'))

        current_fac = conn.execute("SELECT * FROM faculties WHERE id = ?", (faculty['id'],)).fetchone()
        assigned_courses = conn.execute("SELECT * FROM courses WHERE faculty_name LIKE ?", (f"%{faculty['name']}%",)).fetchall()

        return render_template(
            'faculty/profile.html',
            faculty=current_fac,
            assigned_courses=assigned_courses,
            active_page='profile'
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 15. Extended Modules: Analytics, Performance, Labs, Exams, Mentoring, Reports
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/attendance/analytics')
@faculty_required
def faculty_attendance_analytics(faculty):
    conn = get_db_connection()
    try:
        subject = request.args.get('subject', 'all').strip()
        student_q = request.args.get('q', '').strip()
        threshold = float(get_system_setting('attendance_threshold', '75.0'))

        courses = conn.execute("SELECT * FROM courses").fetchall()

        att_query = """
            SELECT a.*, s.name as student_name, s.register_number
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE 1=1
        """
        params = []
        if subject and subject != 'all':
            att_query += " AND a.subject_code = ?"
            params.append(subject)
        if student_q:
            att_query += " AND (s.name LIKE ? OR s.register_number LIKE ?)"
            params.extend([f"%{student_q}%", f"%{student_q}%"])

        att_records = conn.execute(att_query, params).fetchall()

        all_att = conn.execute("SELECT * FROM attendance").fetchall()
        class_avg = round(sum(r['attendance_pct'] for r in all_att) / len(all_att), 1) if all_att else 0.0
        above_90_count = sum(1 for r in all_att if r['attendance_pct'] >= 90.0)
        between_75_90_count = sum(1 for r in all_att if threshold <= r['attendance_pct'] < 90.0)
        below_threshold_count = sum(1 for r in all_att if r['attendance_pct'] < threshold)

        subject_stats = []
        for c in courses:
            c_att = [r for r in all_att if r['subject_code'] == c['course_code']]
            c_avg = round(sum(r['attendance_pct'] for r in c_att) / len(c_att), 1) if c_att else 0.0
            subject_stats.append({
                'subject_code': c['course_code'],
                'subject_name': c['course_name'],
                'student_count': len(c_att),
                'avg_pct': c_avg
            })

        return render_template(
            'faculty/attendance_analytics.html',
            faculty=faculty,
            threshold=threshold,
            class_avg=class_avg,
            above_90_count=above_90_count,
            between_75_90_count=between_75_90_count,
            below_threshold_count=below_threshold_count,
            courses=courses,
            subject_filter=subject,
            student_q=student_q,
            subject_stats=subject_stats,
            repeated_absences=[],
            att_records=att_records,
            records=att_records,
            active_page='attendance'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/marks/performance')
@faculty_required
def faculty_marks_performance(faculty):
    conn = get_db_connection()
    try:
        marks_rows = conn.execute("""
            SELECT m.*, s.name as student_name, s.register_number
            FROM marks m
            JOIN students s ON m.student_id = s.id
        """).fetchall()

        avg_cat1 = round(sum(m['cat1'] for m in marks_rows) / len(marks_rows), 1) if marks_rows else 0.0
        avg_cat2 = round(sum(m['cat2'] for m in marks_rows) / len(marks_rows), 1) if marks_rows else 0.0
        avg_fat = round(sum(m['fat'] for m in marks_rows) / len(marks_rows), 1) if marks_rows else 0.0

        grade_dist = {'S': 0, 'A+': 0, 'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        for m in marks_rows:
            g = m['grade']
            grade_dist[g] = grade_dist.get(g, 0) + 1

        top_performers = [m for m in marks_rows if m['grade'] in ('S', 'A+', 'A')]
        needs_support = [m for m in marks_rows if m['grade'] in ('D', 'F') or m['fat'] < 50]

        return render_template(
            'faculty/academic_performance.html',
            faculty=faculty,
            avg_cat1=avg_cat1,
            avg_cat2=avg_cat2,
            avg_fat=avg_fat,
            grade_dist=grade_dist,
            grade_distribution=grade_dist,
            marks_data=marks_rows,
            marks_records=marks_rows,
            top_performers=top_performers,
            needs_support=needs_support,
            active_page='marks'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/lab', methods=['GET', 'POST'])
@faculty_required
def faculty_lab(faculty):
    conn = get_db_connection()
    try:
        lab_courses = conn.execute("SELECT * FROM courses WHERE course_type LIKE '%Lab%' OR course_code LIKE '%L'").fetchall()
        if not lab_courses:
            lab_courses = conn.execute("SELECT * FROM courses WHERE department = ?", (faculty['department'],)).fetchall()
        if not lab_courses:
            lab_courses = conn.execute("SELECT * FROM courses").fetchall()

        selected_course = request.args.get('course', lab_courses[0]['course_code'] if lab_courses else '')

        if request.method == 'POST':
            exp_no = int(request.form.get('experiment_no', 1))
            course_code = request.form.get('course_code', selected_course)
            student_id = int(request.form.get('student_id', 1))
            title = request.form.get('title', 'Practical Lab Experiment').strip()
            date_conducted = request.form.get('conducted_date', datetime.date.today().strftime('%Y-%m-%d'))
            practical_marks = float(request.form.get('practical_marks', 0.0))
            viva_marks = float(request.form.get('viva_marks', 0.0))
            status = request.form.get('record_status', 'Verified')
            remarks = request.form.get('faculty_remarks', '').strip()

            conn.execute("""
                INSERT INTO lab_experiments (course_code, student_id, experiment_no, title, conducted_date, practical_marks, viva_marks, record_status, faculty_remarks)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (course_code, student_id, exp_no, title, date_conducted, practical_marks, viva_marks, status, remarks))
            conn.commit()

            flash(f"Lab experiment #{exp_no} successfully saved and verified for {course_code}.", "success")
            return redirect(url_for('faculty.faculty_lab', course=course_code))

        students = conn.execute("SELECT * FROM students WHERE department = ? ORDER BY register_number ASC", (faculty['department'],)).fetchall()
        if not students:
            students = conn.execute("SELECT * FROM students ORDER BY register_number ASC").fetchall()

        experiments = []
        if selected_course:
            experiments = conn.execute("""
                SELECT le.*, s.name as student_name, s.register_number
                FROM lab_experiments le
                JOIN students s ON le.student_id = s.id
                WHERE le.course_code = ?
                ORDER BY le.experiment_no ASC, le.conducted_date DESC
            """, (selected_course,)).fetchall()
        else:
            experiments = conn.execute("""
                SELECT le.*, s.name as student_name, s.register_number
                FROM lab_experiments le
                JOIN students s ON le.student_id = s.id
                ORDER BY le.conducted_date DESC LIMIT 50
            """).fetchall()

        return render_template(
            'faculty/lab.html',
            faculty=faculty,
            lab_courses=lab_courses,
            selected_course=selected_course,
            students=students,
            experiments=experiments,
            active_page='lab'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/exams')
@faculty_required
def faculty_exams(faculty):
    conn = get_db_connection()
    try:
        exams = conn.execute("SELECT * FROM examinations ORDER BY exam_date ASC").fetchall()
        students = conn.execute("SELECT * FROM students WHERE department = ?", (faculty['department'],)).fetchall()
        return render_template(
            'faculty/exams.html',
            faculty=faculty,
            exams=exams,
            examinations=exams,
            students=students,
            active_page='exams'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/mentoring')
@faculty_required
def faculty_mentoring(faculty):
    conn = get_db_connection()
    try:
        advisees = conn.execute("SELECT * FROM students WHERE department = ? ORDER BY cgpa DESC", (faculty['department'],)).fetchall()
        return render_template(
            'faculty/mentoring.html',
            faculty=faculty,
            advisees=advisees,
            active_page='mentoring'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/calendar')
@faculty_required
def faculty_calendar(faculty):
    conn = get_db_connection()
    try:
        events = conn.execute("SELECT * FROM academic_calendar ORDER BY start_date ASC").fetchall()
        return render_template('faculty/calendar.html', faculty=faculty, events=events, active_page='calendar')
    finally:
        conn.close()


@faculty_bp.route('/faculty/reports')
@faculty_required
def faculty_reports(faculty):
    conn = get_db_connection()
    try:
        report_type = request.args.get('type', 'attendance').strip().lower()
        records = []

        if report_type == 'marks':
            records = conn.execute("""
                SELECT m.*, s.name as student_name, s.register_number
                FROM marks m
                JOIN students s ON m.student_id = s.id
                ORDER BY s.register_number ASC, m.course_code ASC
            """).fetchall()
        elif report_type == 'lab':
            records = conn.execute("""
                SELECT le.*, s.name as student_name, s.register_number
                FROM lab_experiments le
                JOIN students s ON le.student_id = s.id
                ORDER BY le.course_code ASC, le.experiment_no ASC
            """).fetchall()
        else:
            report_type = 'attendance'
            records = conn.execute("""
                SELECT a.*, s.name as student_name, s.register_number
                FROM attendance a
                JOIN students s ON a.student_id = s.id
                ORDER BY s.register_number ASC, a.subject_code ASC
            """).fetchall()

        return render_template(
            'faculty/reports.html',
            faculty=faculty,
            report_type=report_type,
            records=records,
            active_page='reports'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/reports/export/<report_type>')
@faculty_required
def faculty_reports_export(faculty, report_type):
    conn = get_db_connection()
    try:
        si = io.StringIO()
        cw = csv.writer(si)

        if report_type == 'attendance':
            cw.writerow(['Student ID', 'Student Name', 'Subject Code', 'Classes Held', 'Classes Attended', 'Attendance %'])
            records = conn.execute("""
                SELECT a.*, s.name as student_name 
                FROM attendance a
                JOIN students s ON a.student_id = s.id
                ORDER BY s.name ASC
            """).fetchall()
            for r in records:
                cw.writerow([r['student_id'], r['student_name'], r['subject_code'], r['classes_held'], r['classes_attended'], r['attendance_pct']])
            
            output = Response(si.getvalue(), mimetype='text/csv')
            output.headers["Content-Disposition"] = "attachment; filename=faculty_attendance_report.csv"
            return output

        elif report_type == 'marks':
            cw.writerow(['Student ID', 'Student Name', 'Course Code', 'CAT 1 (50)', 'CAT 2 (50)', 'FAT (100)', 'Grade'])
            records = conn.execute("""
                SELECT m.*, s.name as student_name 
                FROM marks m
                JOIN students s ON m.student_id = s.id
                ORDER BY s.name ASC
            """).fetchall()
            for r in records:
                cw.writerow([r['student_id'], r['student_name'], r['course_code'], r['cat1'], r['cat2'], r['fat'], r['grade']])
            
            output = Response(si.getvalue(), mimetype='text/csv')
            output.headers["Content-Disposition"] = "attachment; filename=faculty_marks_report.csv"
            return output

        elif report_type == 'lab':
            cw.writerow(['Exp #', 'Student ID', 'Student Name', 'Course Code', 'Title', 'Date Conducted', 'Practical (10)', 'Viva (10)', 'Status'])
            records = conn.execute("""
                SELECT le.*, s.name as student_name 
                FROM lab_experiments le
                JOIN students s ON le.student_id = s.id
                ORDER BY le.experiment_no ASC
            """).fetchall()
            for r in records:
                cw.writerow([r['experiment_no'], r['student_id'], r['student_name'], r['course_code'], r['title'], r['conducted_date'], r['practical_marks'], r['viva_marks'], r['record_status']])
            
            output = Response(si.getvalue(), mimetype='text/csv')
            output.headers["Content-Disposition"] = "attachment; filename=faculty_lab_report.csv"
            return output

        flash("Invalid report type.", "error")
        return redirect(url_for('faculty.faculty_reports'))
    finally:
        conn.close()


@faculty_bp.route('/faculty/feedback', methods=['GET', 'POST'])
@faculty_required
def faculty_feedback(faculty):
    conn = get_db_connection()
    try:
        # Fetch complaints/issues raised by this faculty member
        tickets = conn.execute("""
            SELECT * FROM complaints 
            WHERE sender_role = 'Faculty' AND (faculty_id = ? OR sender_name LIKE ?)
            ORDER BY id DESC
        """, (faculty['id'], f"%{faculty['name']}%")).fetchall()

        total_tickets = len(tickets)
        resolved_tickets = len([t for t in tickets if t['status'] in ['Resolved', 'Closed']])
        in_progress_tickets = len([t for t in tickets if t['status'] in ['In Progress', 'Assigned', 'Under Review']])
        pending_tickets = len([t for t in tickets if t['status'] == 'Submitted'])

        return render_template(
            'faculty/feedback.html',
            faculty=faculty,
            tickets=tickets,
            total_tickets=total_tickets,
            resolved_tickets=resolved_tickets,
            in_progress_tickets=in_progress_tickets,
            pending_tickets=pending_tickets,
            active_page='feedback'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/feedback/create', methods=['POST'])
@faculty_required
def faculty_feedback_create(faculty):
    title = request.form.get('title', '').strip()
    category = request.form.get('category', 'Classroom Equipment').strip()
    description = request.form.get('description', '').strip()
    location = request.form.get('location', f"{faculty['department']} - Cabin/Classroom").strip()
    priority = request.form.get('priority', 'Normal').strip()

    if not title or not description:
        flash("Please provide both a Title and detailed Description for your issue ticket.", "error")
        return redirect(url_for('faculty.faculty_feedback'))

    conn = get_db_connection()
    try:
        complaint_id = f"FAC-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        conn.execute("""
            INSERT INTO complaints (
                complaint_id, student_id, faculty_id, sender_role, sender_name,
                category, title, description, location, priority, status
            ) VALUES (?, 0, ?, 'Faculty', ?, ?, ?, ?, ?, ?, 'Submitted')
        """, (complaint_id, faculty['id'], faculty['name'], category, title, description, location, priority))
        
        conn.execute("""
            INSERT INTO activity_logs (user_name, user_role, action, details)
            VALUES (?, 'faculty', 'FACULTY_TICKET_SUBMISSION', ?)
        """, (faculty['name'], f"[{category}] {title}: {description}"))
        conn.commit()

        notify_admin(
            f"Faculty Ticket: {title} ({category})",
            f"Raised by: {faculty['name']} ({faculty['department']}). Priority: {priority}. Location: {location}",
            category='Administrative'
        )
        flash(f"✓ Ticket #{complaint_id} successfully submitted to Central Administration Helpdesk.", "success")
        return redirect(url_for('faculty.faculty_feedback'))
    except Exception as e:
        conn.rollback()
        flash(f"Error submitting ticket: {e}", "error")
        return redirect(url_for('faculty.faculty_feedback'))
    finally:
        conn.close()


@faculty_bp.route('/faculty/safety', methods=['GET'])
@faculty_required
def faculty_safety(faculty):
    conn = get_db_connection()
    try:
        # Query live active emergencies and recent incident logs (read-only for faculty)
        active_incidents = conn.execute("""
            SELECT * FROM incidents 
            ORDER BY id DESC LIMIT 10
        """).fetchall()

        emergency_contacts = conn.execute("""
            SELECT * FROM emergency_contacts ORDER BY id ASC
        """).fetchall()

        safety_alerts = conn.execute("""
            SELECT * FROM alerts 
            ORDER BY id DESC LIMIT 5
        """).fetchall()

        return render_template(
            'faculty/safety.html',
            faculty=faculty,
            active_incidents=active_incidents,
            emergency_contacts=emergency_contacts,
            safety_alerts=safety_alerts,
            active_page='safety'
        )
    finally:
        conn.close()


