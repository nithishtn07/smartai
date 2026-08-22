from flask import Flask, Blueprint, url_for

app = Flask(__name__)
bp = Blueprint('student', __name__)

@bp.route('/student/dashboard')
def student_dashboard():
    return "Dashboard"

app.register_blueprint(bp)

def url_build_error_handler(error, endpoint, values):
    """Fallback handler to map legacy unprefixed endpoint names to registered blueprint endpoints."""
    for ep in app.view_functions:
        if ep.endswith('.' + endpoint) or ep == endpoint:
            return url_for(ep, **values)
    raise error

app.url_build_error_handlers.append(url_build_error_handler)

with app.test_request_context():
    print("Direct endpoint:", url_for('student_dashboard'))
    print("Blueprint qualified:", url_for('student.student_dashboard'))
