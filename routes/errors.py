"""
CampusGuard AI — Custom HTTP Error Handlers
"""

from flask import Blueprint, render_template, request, jsonify

errors_bp = Blueprint('errors', __name__)


@errors_bp.app_errorhandler(403)
def forbidden_error(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Forbidden', 'message': 'You do not have authorization for this resource.', 'status_code': 403}), 403
    return render_template('errors/403.html'), 403


@errors_bp.app_errorhandler(404)
def not_found_error(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not Found', 'message': 'Requested API endpoint does not exist.', 'status_code': 404}), 404
    return render_template('errors/404.html'), 404


@errors_bp.app_errorhandler(500)
def internal_error(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal Server Error', 'message': 'An unexpected error occurred.', 'status_code': 500}), 500
    return render_template('errors/500.html'), 500
