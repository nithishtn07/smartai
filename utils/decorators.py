"""
CampusGuard AI — Role-Based Authorization Decorators
"""

from functools import wraps
from flask import session, redirect, url_for, flash, g, request, jsonify
from database.db import get_db_connection


def student_required(f):
    """
    Decorator protecting student routes:
    - Enforces valid student session.
    - Loads student row from central database.
    - Redirects to /student/login if unauthenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'student_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized', 'message': 'Student authentication required'}), 401
            flash("Please log in to access the Student Portal.", "info")
            return redirect(url_for('auth.student_login'))
        
        conn = get_db_connection()
        student = conn.execute(
            "SELECT * FROM students WHERE id = ?",
            (session['student_id'],)
        ).fetchone()
        conn.close()

        if not student:
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized', 'message': 'Session expired'}), 401
            flash("Session expired. Please log in again.", "info")
            return redirect(url_for('auth.student_login'))
        
        g.student = student
        return f(student=student, *args, **kwargs)
    return decorated_function


def parent_required(f):
    """
    Decorator protecting parent routes:
    - Enforces valid parent session.
    - Loads parent row and linked student row from central database.
    - Strictly scopes student access to parent.student_id.
    - Redirects to /parent/login if unauthenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'parent_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized', 'message': 'Parent authentication required'}), 401
            flash("Please sign in to access the Parent Portal.", "info")
            return redirect(url_for('auth.parent_login'))
        
        conn = get_db_connection()
        parent = conn.execute(
            "SELECT * FROM parents WHERE id = ?",
            (session['parent_id'],)
        ).fetchone()

        if not parent:
            conn.close()
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized', 'message': 'Session expired'}), 401
            flash("Session expired. Please sign in again.", "info")
            return redirect(url_for('auth.parent_login'))

        student = conn.execute(
            "SELECT * FROM students WHERE id = ?",
            (parent['student_id'],)
        ).fetchone()
        conn.close()

        if not student:
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Forbidden', 'message': 'No linked student found'}), 403
            flash("No linked student record found for this account. Please contact campus admin.", "error")
            return redirect(url_for('auth.parent_login'))
        
        g.parent = parent
        g.student = student
        return f(parent=parent, student=student, *args, **kwargs)
    return decorated_function


def faculty_required(f):
    """
    Decorator protecting faculty routes:
    - Enforces valid faculty session.
    - Loads faculty row from central database.
    - Redirects to /faculty/login if unauthenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'faculty_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized', 'message': 'Faculty authentication required'}), 401
            flash("Please sign in to access the Faculty Portal.", "info")
            return redirect(url_for('auth.faculty_login'))
        
        conn = get_db_connection()
        faculty = conn.execute(
            "SELECT * FROM faculties WHERE id = ?",
            (session['faculty_id'],)
        ).fetchone()
        conn.close()

        if not faculty:
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized', 'message': 'Session expired'}), 401
            flash("Session expired. Please sign in again.", "info")
            return redirect(url_for('auth.faculty_login'))
        
        g.faculty = faculty
        return f(faculty=faculty, *args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator protecting admin routes:
    - Enforces valid admin session.
    - Loads admin row from central database.
    - Redirects to /admin/login if unauthenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized', 'message': 'Admin authentication required'}), 401
            flash("Please sign in to access the Admin Console.", "info")
            return redirect(url_for('auth.admin_login'))
        
        conn = get_db_connection()
        admin = conn.execute(
            "SELECT * FROM admins WHERE id = ?",
            (session['admin_id'],)
        ).fetchone()
        conn.close()

        if not admin:
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized', 'message': 'Session expired'}), 401
            flash("Session expired. Please sign in again.", "info")
            return redirect(url_for('auth.admin_login'))
        
        g.admin = admin
        return f(admin=admin, *args, **kwargs)
    return decorated_function


def login_required_role(*allowed_roles):
    """
    Universal role requirement decorator for multi-role API endpoints.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_role = session.get('user_role')
            if not user_role or user_role not in allowed_roles:
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Forbidden', 'message': f'Access restricted to {allowed_roles}'}), 403
                flash("You do not have permission to access this resource.", "error")
                return redirect(url_for('auth.home'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
