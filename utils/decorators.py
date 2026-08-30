"""
CampusGuard AI — Role-Based Authorization Decorators
"""

from functools import wraps
from flask import session, redirect, url_for, flash, g, request, jsonify
from database.db import get_db_connection
from services.academic_service import calculate_student_cgpa


def student_required(f):
    """
    Decorator protecting student routes:
    - Enforces valid student session.
    - Loads student row from central database.
    - Dynamically evaluates real CGPA from database academic records.
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
        student_row = conn.execute(
            "SELECT * FROM students WHERE id = ?",
            (session['student_id'],)
        ).fetchone()

        if not student_row:
            conn.close()
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized', 'message': 'Session expired'}), 401
            flash("Session expired. Please log in again.", "info")
            return redirect(url_for('auth.student_login'))
        
        student = dict(student_row)
        cgpa, earned_credits, _, _ = calculate_student_cgpa(conn, student['id'])
        student['cgpa'] = cgpa
        student['sgpa'] = cgpa
        if cgpa is not None:
            student['earned_credits'] = earned_credits
        conn.close()

        g.student = student
        return f(student=student, *args, **kwargs)
    return decorated_function


def parent_required(f):
    """
    Decorator protecting parent routes:
    - Enforces valid parent session.
    - Loads parent row and all authorized linked student rows from central database.
    - Dynamically evaluates real CGPA for linked students from database academic records.
    - Strictly scopes active student access to verified parent-student relationships.
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

        # Fetch all authorized linked students for this parent
        linked_rows = conn.execute("""
            SELECT DISTINCT s.*, COALESCE(ps.relationship, p.relationship, 'Guardian') as relationship,
                   COALESCE(ps.is_primary, 1) as is_primary
            FROM students s
            LEFT JOIN parent_student ps ON (s.id = ps.student_id AND ps.parent_id = ?)
            LEFT JOIN parents p ON p.id = ?
            WHERE (ps.parent_id = ? OR p.student_id = s.id) AND s.status != 'DELETED'
            ORDER BY is_primary DESC, s.id ASC
        """, (parent['id'], parent['id'], parent['id'])).fetchall()

        if not linked_rows:
            conn.close()
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Forbidden', 'message': 'No linked student found'}), 403
            flash("No linked student record found for this account. Please contact campus admin.", "error")
            return redirect(url_for('auth.parent_login'))

        linked_students = []
        for row in linked_rows:
            s_dict = dict(row)
            cgpa, earned_credits, _, _ = calculate_student_cgpa(conn, s_dict['id'])
            s_dict['cgpa'] = cgpa
            s_dict['sgpa'] = cgpa
            if cgpa is not None:
                s_dict['earned_credits'] = earned_credits
            linked_students.append(s_dict)

        # Resolve active selected student
        active_student_id = session.get('parent_active_student_id')
        active_student = None
        if active_student_id:
            for s in linked_students:
                if s['id'] == active_student_id:
                    active_student = s
                    break
        
        if not active_student:
            active_student = linked_students[0]
            session['parent_active_student_id'] = active_student['id']

        conn.close()

        g.parent = parent
        g.student = active_student
        g.linked_students = linked_students
        return f(parent=parent, student=active_student, *args, **kwargs)
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
