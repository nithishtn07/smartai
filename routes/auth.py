"""
CampusGuard AI — Public Landing & Authentication Routes
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import check_password_hash
from database.db import get_db_connection
from utils.security import is_brute_force_locked, record_login_attempt

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def home():
    """Public campus landing page."""
    return render_template('index.html')


# ---------------------------------------------------------------------------
# Student Authentication
# ---------------------------------------------------------------------------
@auth_bp.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if 'student_id' in session:
        return redirect(url_for('student.student_dashboard'))

    if request.method == 'POST':
        register_number = (
            request.form.get('register_number') or 
            request.form.get('identifier') or 
            request.form.get('email') or ''
        ).strip()
        password = request.form.get('password', '').strip()
        remember_me = bool(request.form.get('remember'))
        ip_addr = request.remote_addr or '127.0.0.1'

        if not register_number or not password:
            return render_template(
                'student/login.html',
                error="Please enter both Register Number and Password.",
                register_number=register_number
            )

        if is_brute_force_locked(register_number):
            return render_template(
                'student/login.html',
                error="⚠️ Multiple failed login attempts detected. Your account has been temporarily protected. Please try again in 15 minutes.",
                register_number=register_number
            )

        conn = get_db_connection()
        try:
            student = conn.execute(
                "SELECT * FROM students WHERE UPPER(register_number) = UPPER(?) OR LOWER(email) = LOWER(?)",
                (register_number, register_number)
            ).fetchone()

            if student and check_password_hash(student['password_hash'], password):
                record_login_attempt(register_number, ip_addr, success=True)
                session.clear()
                session['student_id'] = student['id']
                session['student_register_number'] = student['register_number']
                session['student_name'] = student['name']
                session['user_role'] = 'student'
                session['student_logged_in'] = True
                session.permanent = remember_me
                return redirect(url_for('student.student_dashboard'))
            else:
                record_login_attempt(register_number, ip_addr, success=False)
                return render_template(
                    'student/login.html',
                    error="Invalid register number or password.",
                    register_number=register_number
                )
        except Exception as e:
            print(f"[ERROR] Database error during student login: {e}")
            return render_template(
                'student/login.html',
                error="Something went wrong. Please try again.",
                register_number=register_number
            )
        finally:
            conn.close()

    return render_template('student/login.html')


@auth_bp.route('/student/logout')
def student_logout():
    session.clear()
    flash("You have been signed out successfully.", "success")
    return redirect(url_for('auth.student_login'))


# ---------------------------------------------------------------------------
# Faculty Authentication
# ---------------------------------------------------------------------------
@auth_bp.route('/faculty/login', methods=['GET', 'POST'])
def faculty_login():
    if 'faculty_id' in session:
        return redirect(url_for('faculty.faculty_dashboard'))

    if request.method == 'POST':
        identifier = (
            request.form.get('identifier') or 
            request.form.get('email') or 
            request.form.get('faculty_id') or ''
        ).strip()
        password = request.form.get('password', '').strip()
        remember_me = bool(request.form.get('remember'))
        ip_addr = request.remote_addr or '127.0.0.1'

        if not identifier or not password:
            return render_template('faculty/login.html', error="Please enter email and password.", email=identifier)

        if is_brute_force_locked(identifier):
            return render_template('faculty/login.html', error="⚠️ Multiple failed login attempts. Please try again in 15 minutes.", email=identifier)

        conn = get_db_connection()
        try:
            faculty = conn.execute(
                "SELECT * FROM faculties WHERE LOWER(email) = LOWER(?) OR UPPER(faculty_id) = UPPER(?)",
                (identifier, identifier)
            ).fetchone()

            if faculty and check_password_hash(faculty['password_hash'], password):
                record_login_attempt(identifier, ip_addr, success=True)
                session.clear()
                session['faculty_id'] = faculty['id']
                session['faculty_name'] = faculty['name']
                session['faculty_email'] = faculty['email']
                session['faculty_dept'] = faculty['department']
                session['user_role'] = 'faculty'
                session['faculty_logged_in'] = True
                session.permanent = remember_me
                return redirect(url_for('faculty.faculty_dashboard'))
            else:
                record_login_attempt(identifier, ip_addr, success=False)
                return render_template('faculty/login.html', error="Invalid faculty credentials.", email=identifier)
        finally:
            conn.close()

    return render_template('faculty/login.html')


@auth_bp.route('/faculty/logout')
def faculty_logout():
    session.clear()
    flash("Faculty session signed out securely.", "success")
    return redirect(url_for('auth.faculty_login'))


# ---------------------------------------------------------------------------
# Admin Authentication
# ---------------------------------------------------------------------------
@auth_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if 'admin_id' in session:
        return redirect(url_for('admin.admin_dashboard'))

    if request.method == 'POST':
        username = (
            request.form.get('username') or 
            request.form.get('identifier') or 
            request.form.get('email') or ''
        ).strip()
        password = request.form.get('password', '').strip()
        ip_addr = request.remote_addr or '127.0.0.1'

        if not username or not password:
            return render_template('admin/login.html', error="Please enter both username and password.", username=username)

        if is_brute_force_locked(username):
            return render_template('admin/login.html', error="⚠️ Multiple failed attempts. Console locked for 15 minutes.", username=username)

        conn = get_db_connection()
        try:
            clean_id = username.strip().upper()
            if clean_id in ('ADMIN001', 'ADMIN', 'ADM001'):
                admin = conn.execute("SELECT * FROM admins WHERE LOWER(username) = 'admin' OR id = 1").fetchone()
            else:
                admin = conn.execute(
                    "SELECT * FROM admins WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
                    (username, username)
                ).fetchone()

            if admin and check_password_hash(admin['password_hash'], password):
                record_login_attempt(username, ip_addr, success=True)
                session.clear()
                session['admin_id'] = admin['id']
                session['admin_name'] = admin['name']
                session['admin_role'] = admin['role']
                session['user_role'] = 'admin'
                session['admin_logged_in'] = True
                return redirect(url_for('admin.admin_dashboard'))
            else:
                record_login_attempt(username, ip_addr, success=False)
                return render_template('admin/login.html', error="Invalid Admin ID or password.", username=username)
        finally:
            conn.close()

    return render_template('admin/login.html')


@auth_bp.route('/admin/logout')
def admin_logout():
    session.clear()
    flash("Admin command session terminated.", "success")
    return redirect(url_for('auth.admin_login'))


# ---------------------------------------------------------------------------
# Parent Authentication
# ---------------------------------------------------------------------------
@auth_bp.route('/parent/login', methods=['GET', 'POST'])
def parent_login():
    if 'parent_id' in session:
        return redirect(url_for('parent.parent_dashboard'))

    if request.method == 'POST':
        identifier = (
            request.form.get('identifier') or 
            request.form.get('email') or 
            request.form.get('parent_id') or ''
        ).strip()
        password = request.form.get('password', '').strip()
        remember_me = bool(request.form.get('remember'))
        ip_addr = request.remote_addr or '127.0.0.1'

        if not identifier or not password:
            return render_template('parent/login.html', error="Please enter parent email/ID and password.", email=identifier)

        if is_brute_force_locked(identifier):
            return render_template('parent/login.html', error="⚠️ Multiple failed login attempts. Please try again in 15 minutes.", email=identifier)

        conn = get_db_connection()
        try:
            clean_id = identifier.strip().upper()
            if clean_id in ('P1001', 'PAR001'):
                parent = conn.execute("SELECT * FROM parents WHERE UPPER(parent_id) = 'PAR001' OR LOWER(email) = 'parent@example.com'").fetchone()
            else:
                parent = conn.execute(
                    "SELECT * FROM parents WHERE LOWER(email) = LOWER(?) OR UPPER(parent_id) = UPPER(?)",
                    (identifier, identifier)
                ).fetchone()

            if parent and check_password_hash(parent['password_hash'], password):
                record_login_attempt(identifier, ip_addr, success=True)
                session.clear()
                session['parent_id'] = parent['id']
                session['parent_name'] = parent['name']
                session['parent_email'] = parent['email']
                session['student_id'] = parent['student_id']
                session['user_role'] = 'parent'
                session['parent_logged_in'] = True
                session.permanent = remember_me
                return redirect(url_for('parent.parent_dashboard'))
            else:
                record_login_attempt(identifier, ip_addr, success=False)
                return render_template('parent/login.html', error="Invalid Parent ID / Email or Password.", email=identifier)
        finally:
            conn.close()

    return render_template('parent/login.html')


@auth_bp.route('/parent/logout')
def parent_logout():
    session.clear()
    flash("Parent monitoring session ended safely.", "success")
    return redirect(url_for('auth.parent_login'))
