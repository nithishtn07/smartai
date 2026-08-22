"""
CampusGuard AI — Routes & Blueprints Package
"""

from .auth import auth_bp
from .student import student_bp
from .faculty import faculty_bp
from .parent import parent_bp
from .admin import admin_bp
from .security import security_bp
from .emergency_routes import emergency_bp
from .errors import errors_bp

def register_routes(app):
    """
    Registers all portal and system blueprints onto the Flask application.
    """
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(faculty_bp)
    app.register_blueprint(parent_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(emergency_bp)
    app.register_blueprint(errors_bp)
