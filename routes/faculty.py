"""
CampusGuard AI — Faculty Portal Routes & Controller
"""

import io
import csv
import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, Response
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db_connection
from utils.decorators import faculty_required
from services.notification_service import (
    notify_student,
    notify_parent,
    notify_faculty,
    notify_admin,
    broadcast_announcement,
    log_activity,
    get_system_setting
)
from services.campus_assistant import answer_campus_query, answer_admin_query
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
        today_dow = datetime.datetime.now().strftime('%A')
        today_schedule = conn.execute("""
            SELECT * FROM timetable 
            WHERE faculty_name LIKE ? AND day_of_week = ?
            ORDER BY start_time ASC
        """, (f"%{faculty['name']}%", today_dow)).fetchall()

        assigned_courses = conn.execute("""
            SELECT * FROM courses WHERE faculty_name LIKE ?
        """, (f"%{faculty['name']}%",)).fetchall()
        if not assigned_courses:
            assigned_courses = conn.execute("SELECT * FROM courses").fetchall()

        total_students_count = conn.execute("SELECT COUNT(*) as cnt FROM students WHERE department = ?", (faculty['department'],)).fetchone()['cnt']
        pending_leaves = conn.execute("""
            SELECT hl.*, s.name as student_name, s.register_number 
            FROM hostel_leaves hl
            JOIN students s ON hl.student_id = s.id
            WHERE hl.status = 'Pending'
            ORDER BY hl.created_at DESC
        """).fetchall()
        pending_leaves_count = len(pending_leaves)
        pending_assignments_count = conn.execute("SELECT COUNT(*) as cnt FROM assignments WHERE status = 'Submitted'").fetchone()['cnt']

        low_att_records = conn.execute("""
            SELECT a.*, s.name as student_name, s.register_number, s.department
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.attendance_pct < 75.0
            ORDER BY a.attendance_pct ASC LIMIT 5
        """).fetchall()
        low_att_count = len(low_att_records)

        unread_notifications_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM notifications 
            WHERE recipient_role = 'faculty' AND recipient_id = ? AND is_read = 0
        """, (faculty['id'],)).fetchone()['cnt']

        announcements = conn.execute("SELECT * FROM announcements ORDER BY created_at DESC LIMIT 3").fetchall()
        today_name = datetime.datetime.now().strftime('%A')

        return render_template(
            'faculty/dashboard.html',
            faculty=faculty,
            courses=assigned_courses,
            assigned_courses=assigned_courses,
            total_students=total_students_count,
            total_students_count=total_students_count,
            pending_leaves=pending_leaves,
            pending_leaves_count=pending_leaves_count,
            pending_assignments_count=pending_assignments_count,
            low_att_students=low_att_count,
            low_att_records=low_att_records,
            today_name=today_name,
            today_classes=today_schedule,
            today_schedule=today_schedule,
            unread_notifications_count=unread_notifications_count,
            announcements=announcements,
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

        query = "SELECT * FROM students WHERE department = ?"
        params = [faculty['department']]

        if search_query:
            query += " AND (name LIKE ? OR register_number LIKE ?)"
            params.extend([f"%{search_query}%", f"%{search_query}%"])

        students = conn.execute(query, params).fetchall()

        student_cards = []
        for s in students:
            att_rows = conn.execute("SELECT attendance_pct FROM attendance WHERE student_id = ?", (s['id'],)).fetchall()
            avg_att = round(sum(r['attendance_pct'] for r in att_rows) / len(att_rows), 1) if att_rows else 85.0
            student_cards.append({
                'student': s,
                'avg_attendance': avg_att,
                'is_risk': (avg_att < 75.0)
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
        student = conn.execute("SELECT * FROM students WHERE id = ?", (target_id,)).fetchone()
        if not student:
            flash("Student record not found.", "error")
            return redirect(url_for('faculty.faculty_students'))

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
# 6. Attendance Management & Low Warning Trigger
# ---------------------------------------------------------------------------
@faculty_bp.route('/faculty/attendance', methods=['GET', 'POST'])
@faculty_required
def faculty_attendance(faculty):
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            course_code = request.form.get('course_code', 'CS301')
            date_val = request.form.get('date', datetime.date.today().strftime('%Y-%m-%d'))
            topic = request.form.get('topic', 'Classroom Lecture')
            action_type = request.form.get('action_type', '')

            course = conn.execute("SELECT * FROM courses WHERE course_code = ?", (course_code,)).fetchone()
            course_name = course['course_name'] if course else course_code

            if action_type == 'batch_roll_call' or not request.form.get('student_id'):
                # Process multiple students
                for k, status_val in request.form.items():
                    if k.startswith('status_'):
                        try:
                            stu_id = int(k.split('_')[1])
                            conn.execute("""
                                INSERT INTO attendance_logs (student_id, course_code, course_name, date, status, topic)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (stu_id, course_code, course_name, date_val, status_val, topic))

                            existing = conn.execute("""
                                SELECT * FROM attendance WHERE student_id = ? AND subject_code = ?
                            """, (stu_id, course_code)).fetchone()

                            is_present = (status_val.lower() == 'present')
                            if existing:
                                held = existing['classes_held'] + 1
                                att = existing['classes_attended'] + (1 if is_present else 0)
                                miss = existing['classes_missed'] + (0 if is_present else 1)
                                pct = round((att / held) * 100.0, 1)
                                conn.execute("""
                                    UPDATE attendance 
                                    SET classes_held = ?, classes_attended = ?, classes_missed = ?, attendance_pct = ?
                                    WHERE id = ?
                                """, (held, att, miss, pct, existing['id']))
                            else:
                                held = 1
                                att = 1 if is_present else 0
                                miss = 0 if is_present else 1
                                pct = 100.0 if is_present else 0.0
                                conn.execute("""
                                    INSERT INTO attendance (student_id, subject_code, subject_name, classes_held, classes_attended, classes_missed, attendance_pct)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (stu_id, course_code, course_name, held, att, miss, pct))
                        except Exception as ex:
                            print(f"[ERROR] Batch attendance error: {ex}")
                conn.commit()
                flash(f"Class roll call for {course_code} successfully saved.", "success")
                return redirect(url_for('faculty.faculty_attendance', course=course_code))
            else:
                student_id = int(request.form.get('student_id'))
                status = request.form.get('status', 'Present')
                student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()

                # Record single attendance log
                conn.execute("""
                    INSERT INTO attendance_logs (student_id, course_code, course_name, date, status, topic)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (student_id, course_code, course_name, date_val, status, topic))

                existing = conn.execute("""
                    SELECT * FROM attendance WHERE student_id = ? AND subject_code = ?
                """, (student_id, course_code)).fetchone()

                is_present = (status.lower() == 'present')
                if existing:
                    held = existing['classes_held'] + 1
                    att = existing['classes_attended'] + (1 if is_present else 0)
                    miss = existing['classes_missed'] + (0 if is_present else 1)
                    pct = round((att / held) * 100.0, 1)
                    conn.execute("""
                        UPDATE attendance 
                        SET classes_held = ?, classes_attended = ?, classes_missed = ?, attendance_pct = ?
                        WHERE id = ?
                    """, (held, att, miss, pct, existing['id']))
                else:
                    held = 1
                    att = 1 if is_present else 0
                    miss = 0 if is_present else 1
                    pct = 100.0 if is_present else 0.0
                    conn.execute("""
                        INSERT INTO attendance (student_id, subject_code, subject_name, classes_held, classes_attended, classes_missed, attendance_pct)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (student_id, course_code, course_name, held, att, miss, pct))

                # Low attendance warning trigger (< 75%)
                if pct < 75.0 and student:
                    notify_student(student_id, f"Low Attendance Alert: {course_code} ({pct}%)", f"Your attendance in {course_name} has fallen to {pct}%, below the 75% requirement.", category='Attendance', priority='Critical', db_conn=conn)
                    parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (student_id,)).fetchone()
                    if parent:
                        notify_parent(parent['id'], f"Low Attendance Alert: {student['name']}", f"Your ward {student['name']} attendance in {course_name} has dropped to {pct}%.", category='Attendance', priority='Critical', db_conn=conn)

                conn.commit()
                flash(f"Attendance recorded for {student['name'] if student else student_id}.", "success")
                return redirect(url_for('faculty.faculty_attendance', course=course_code))

        my_courses = conn.execute("SELECT * FROM courses WHERE faculty_name LIKE ?", (f"%{faculty['name']}%",)).fetchall()
        selected_course = request.args.get('course', my_courses[0]['course_code'] if my_courses else 'CS301')

        students = conn.execute("SELECT * FROM students WHERE department = ? ORDER BY register_number ASC", (faculty['department'],)).fetchall()
        attendance_records = conn.execute("""
            SELECT a.*, s.name as student_name, s.register_number
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.subject_code = ?
            ORDER BY s.register_number ASC
        """, (selected_course,)).fetchall()

        recent_logs = conn.execute("""
            SELECT l.*, s.name as student_name, s.register_number
            FROM attendance_logs l
            JOIN students s ON l.student_id = s.id
            WHERE l.course_code = ?
            ORDER BY l.id DESC LIMIT 25
        """, (selected_course,)).fetchall()

        return render_template(
            'faculty/attendance.html',
            faculty=faculty,
            my_courses=my_courses,
            selected_course=selected_course,
            students=students,
            attendance_records=attendance_records,
            recent_logs=recent_logs,
            active_page='attendance'
        )
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
@faculty_bp.route('/faculty/marks', methods=['GET', 'POST'])
@faculty_required
def faculty_marks(faculty):
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            course_code = request.form.get('course_code')
            student_id = int(request.form.get('student_id'))
            cat1 = float(request.form.get('cat1', 0))
            cat2 = float(request.form.get('cat2', 0))
            quiz = float(request.form.get('quiz', 0))
            assignment = float(request.form.get('assignment', 0))
            project = float(request.form.get('project', 0))
            fat = float(request.form.get('fat', 0))

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

            course = conn.execute("SELECT * FROM courses WHERE course_code = ?", (course_code,)).fetchone()
            course_name = course['course_name'] if course else course_code
            student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()

            # Upsert marks
            existing = conn.execute("SELECT id FROM marks WHERE student_id = ? AND course_code = ?", (student_id, course_code)).fetchone()
            if existing:
                conn.execute("""
                    UPDATE marks SET cat1 = ?, cat2 = ?, quiz = ?, assignment = ?, project = ?, fat = ?, grade = ?, status = 'PASS'
                    WHERE id = ?
                """, (cat1, cat2, quiz, assignment, project, fat, grade, existing['id']))
            else:
                conn.execute("""
                    INSERT INTO marks (student_id, course_code, course_name, cat1, cat2, quiz, assignment, project, fat, grade, grade_points, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 8.0, 'PASS')
                """, (student_id, course_code, course_name, cat1, cat2, quiz, assignment, project, fat, grade))

            conn.commit()

            # Cross-portal synchronization & notifications
            if student:
                notify_student(student_id, f"Marks Published: {course_code}", f"Your assessment marks for {course_name} have been updated. Grade awarded: {grade}.", category='Academic')
                parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (student_id,)).fetchone()
                if parent:
                    notify_parent(parent['id'], f"Academic Assessment Update: {student['name']}", f"Continuous assessment grades published for {course_name} ({course_code}): Grade {grade}.", category='Academic')

            flash(f"Assessment scores for {course_code} saved. Grade: {grade}", "success")
            return redirect(url_for('faculty.faculty_marks'))

        my_courses = conn.execute("SELECT * FROM courses WHERE faculty_name LIKE ?", (f"%{faculty['name']}%",)).fetchall()
        selected_course = request.args.get('course', my_courses[0]['course_code'] if my_courses else 'CS301')

        students = conn.execute("SELECT * FROM students WHERE department = ? ORDER BY register_number ASC", (faculty['department'],)).fetchall()
        marks_records = conn.execute("""
            SELECT m.*, s.name as student_name, s.register_number
            FROM marks m
            JOIN students s ON m.student_id = s.id
            WHERE m.course_code = ?
            ORDER BY s.register_number ASC
        """, (selected_course,)).fetchall()

        return render_template(
            'faculty/marks.html',
            faculty=faculty,
            my_courses=my_courses,
            selected_course=selected_course,
            students=students,
            marks_records=marks_records,
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
        my_courses = conn.execute("SELECT * FROM courses WHERE faculty_name LIKE ?", (f"%{faculty['name']}%",)).fetchall()

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
        submissions = conn.execute("""
            SELECT s.*, st.name as student_name, st.register_number, st.department
            FROM student_submissions s
            JOIN students st ON s.student_id = st.id
            WHERE s.assignment_id = ?
            ORDER BY s.submitted_at DESC
        """, (assignment_id,)).fetchall()

        return render_template(
            'faculty/assignment_submissions.html',
            faculty=faculty,
            assignment=assignment,
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
    feedback = request.form.get('feedback', '')

    conn = get_db_connection()
    try:
        conn.execute("""
            UPDATE student_submissions 
            SET marks_obtained = ?, feedback = ?, status = 'Graded'
            WHERE assignment_id = ? AND student_id = ?
        """, (marks_obtained, feedback, assignment_id, student_id))
        conn.commit()

        notify_student(student_id, "Assignment Graded", f"Your assignment submission has been evaluated: {marks_obtained} marks.", category='Academics')
        flash("Assignment evaluation and marks successfully submitted.", "success")
        return redirect(url_for('faculty.faculty_assignment_submissions', assignment_id=assignment_id))
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
            notify_student(leave['student_id'], f"Hostel Outpass {decision}", f"Your outpass application was {decision.lower()} by {faculty['name']}.", category='Hostel')
            parent = conn.execute("SELECT id FROM parents WHERE student_id = ?", (leave['student_id'],)).fetchone()
            if parent:
                notify_parent(parent['id'], f"Hostel Outpass Decision: {decision}", f"Residential outpass decision {decision} by faculty advisor.", category='Hostel')

        flash(f"Student outpass request has been marked as {decision}.", "success")
        return redirect(url_for('faculty.faculty_leaves'))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 11. Messages
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
@faculty_required
def faculty_api_ai_insights(faculty):
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    conn = get_db_connection()
    try:
        reply = answer_admin_query(query, conn)
        return jsonify({'status': 'success', 'reply': reply})
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
        class_avg = round(sum(r['attendance_pct'] for r in all_att) / len(all_att), 1) if all_att else 85.0
        above_90_count = sum(1 for r in all_att if r['attendance_pct'] >= 90.0)
        between_75_90_count = sum(1 for r in all_att if threshold <= r['attendance_pct'] < 90.0)
        below_threshold_count = sum(1 for r in all_att if r['attendance_pct'] < threshold)

        subject_stats = []
        for c in courses:
            c_att = [r for r in all_att if r['subject_code'] == c['course_code']]
            c_avg = round(sum(r['attendance_pct'] for r in c_att) / len(c_att), 1) if c_att else 90.0
            subject_stats.append({
                'subject_code': c['course_code'],
                'subject_name': c['course_name'],
                'student_count': len(c_att) or 64,
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

        avg_cat1 = round(sum(m['cat1'] for m in marks_rows) / len(marks_rows), 1) if marks_rows else 45.0
        avg_cat2 = round(sum(m['cat2'] for m in marks_rows) / len(marks_rows), 1) if marks_rows else 46.0
        avg_fat = round(sum(m['fat'] for m in marks_rows) / len(marks_rows), 1) if marks_rows else 88.0

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
        if request.method == 'POST':
            exp_no = request.form.get('experiment_no', '1')
            course_code = request.form.get('course_code', 'CS301L')
            flash(f"Lab experiment #{exp_no} successfully saved and verified for {course_code}.", "success")
            return redirect(url_for('faculty.faculty_lab', course=course_code))

        lab_courses = conn.execute("SELECT * FROM courses WHERE course_type LIKE '%Lab%'").fetchall()
        return render_template(
            'faculty/lab.html',
            faculty=faculty,
            lab_courses=lab_courses,
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


@faculty_bp.route('/faculty/announcements')
@faculty_required
def faculty_announcements(faculty):
    conn = get_db_connection()
    try:
        announcements = conn.execute("SELECT * FROM announcements ORDER BY created_at DESC").fetchall()
        return render_template(
            'faculty/announcements.html',
            faculty=faculty,
            announcements=announcements,
            active_page='announcements'
        )
    finally:
        conn.close()


@faculty_bp.route('/faculty/announcements/create', methods=['POST'])
@faculty_required
def faculty_announcements_create(faculty):
    title = request.form.get('title')
    description = request.form.get('description')
    category = request.form.get('category', 'Academic')
    priority = request.form.get('priority', 'Normal')
    target = request.form.get('target_audience', 'Students')

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO announcements (title, description, category, priority, target_audience, author_name)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, description, category, priority, target, faculty['name']))
        conn.commit()

        broadcast_announcement(title, description, category=category, priority=priority, target_audience=target, author_name=faculty['name'])
        flash("Course announcement broadcasted successfully across selected portals.", "success")
        return redirect(url_for('faculty.faculty_announcements'))
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
    return render_template('faculty/reports.html', faculty=faculty, active_page='reports')


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
            """).fetchall()
            for r in records:
                cw.writerow([r['student_id'], r['student_name'], r['course_code'], r['cat1'], r['cat2'], r['fat'], r['grade']])
            
            output = Response(si.getvalue(), mimetype='text/csv')
            output.headers["Content-Disposition"] = "attachment; filename=faculty_marks_report.csv"
            return output

        flash("Invalid report type.", "error")
        return redirect(url_for('faculty.faculty_reports'))
    finally:
        conn.close()


@faculty_bp.route('/faculty/feedback', methods=['GET', 'POST'])
@faculty_required
def faculty_feedback(faculty):
    return render_template('faculty/feedback.html', faculty=faculty, active_page='feedback')


@faculty_bp.route('/faculty/feedback/create', methods=['POST'])
@faculty_required
def faculty_feedback_create(faculty):
    title = request.form.get('title')
    category = request.form.get('category', 'Administrative')
    description = request.form.get('description')
    priority = request.form.get('priority', 'Normal')

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO activity_logs (user_name, user_role, action, details)
            VALUES (?, 'faculty', 'FEEDBACK_SUBMISSION', ?)
        """, (faculty['name'], f"[{category}] {title}: {description}"))
        conn.commit()

        notify_admin(f"Faculty Administrative Request: {title}", f"From: {faculty['name']} ({faculty['department']}). Priority: {priority}", category='Administrative')
        flash("Your administrative request has been submitted to the Central Administration helpdesk.", "success")
        return redirect(url_for('faculty.faculty_feedback'))
    finally:
        conn.close()


@faculty_bp.route('/faculty/safety', methods=['GET'])
@faculty_required
def faculty_safety(faculty):
    return render_template('faculty/safety.html', faculty=faculty, active_page='safety')

