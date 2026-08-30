"""
=============================================================================
CampusGuard AI — Granular Role-Based & Attribute-Based Access Control (RBAC)
=============================================================================
Enforces least-privilege security access control across all 5 operational roles:
Admin, Faculty, Student, Parent, and Campus Security.
=============================================================================
"""

from functools import wraps
from flask import session, flash, redirect, url_for, jsonify, request


ROLE_PERMISSIONS = {
    'admin': {
        'view_admin_dashboard', 'manage_students', 'manage_faculty', 'manage_parents',
        'create_courses', 'edit_grades', 'manage_finances', 'approve_leaves',
        'override_attendance', 'dispatch_sos', 'view_audit_trail', 'modify_system_settings',
        'broadcast_announcements', 'export_reports', 'view_safety_analytics'
    },
    'faculty': {
        'view_faculty_dashboard', 'mark_attendance', 'edit_grades', 'grade_assignments',
        'post_study_materials', 'message_parents', 'review_leave_recommendations',
        'view_student_360', 'view_faculty_safety', 'export_course_reports'
    },
    'parent': {
        'view_parent_dashboard', 'view_ward_academics', 'view_ward_attendance',
        'view_ward_fees', 'pay_ward_fees', 'authorize_outpass', 'message_faculty',
        'view_emergency_directory', 'update_emergency_contacts'
    },
    'student': {
        'view_student_dashboard', 'view_own_academics', 'view_own_attendance',
        'submit_assignments', 'request_outpass', 'trigger_emergency_sos',
        'start_safe_walk', 'file_grievance', 'pay_student_fees', 'view_hall_ticket'
    },
    'security': {
        'view_security_dashboard', 'manage_live_sos', 'dispatch_patrol',
        'view_cctv_telemetry', 'resolve_emergency_incidents', 'trigger_lockdown'
    }
}


def has_permission(role: str, permission: str) -> bool:
    """Checks if a given role possesses a specific permission."""
    if not role or not permission:
        return False
    
    role_key = role.lower()
    if role_key in ['superadmin', 'admin']:
        return True

    perms = ROLE_PERMISSIONS.get(role_key, set())
    return permission in perms


def permission_required(permission: str, json_response: bool = False):
    """
    Decorator for Flask routes ensuring authenticated user possesses the specific permission.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_role = session.get('user_role', '')
            
            # Allow admin session
            if session.get('admin_logged_in') or user_role == 'admin':
                return f(*args, **kwargs)

            if not has_permission(user_role, permission):
                if json_response or request.is_json:
                    return jsonify({
                        'status': 'error',
                        'error': 'Forbidden',
                        'message': f"Access Denied: Missing required permission '{permission}'."
                    }), 403
                else:
                    flash(f"Unauthorized: You do not possess the required permission.", "danger")
                    return redirect(url_for('landing'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator
