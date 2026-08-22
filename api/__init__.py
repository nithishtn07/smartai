"""
CampusGuard AI — Central API Package
"""

from .api_routes import api_bp

def register_api(app):
    """
    Registers the REST API blueprint onto the Flask application.
    """
    app.register_blueprint(api_bp)
