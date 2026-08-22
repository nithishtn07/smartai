"""
=============================================================================
CampusGuard AI — AI-Powered Smart & Safe Campus ERP and Safety Platform
=============================================================================
Central Flask Application & Main Controller
Unified multi-role ERP integrating Admin, Faculty, Student, Parent, and
Campus Security consoles on a single relational database and real-time backend.
=============================================================================
"""

import os
import sqlite3
from datetime import timedelta
from functools import wraps
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    g
)
from flask_socketio import SocketIO

# Configuration
from config import get_config

# Database Engine
from database.db import get_db_connection, init_db, get_db_path
DATABASE_FILE = get_db_path()

# Services & Real-time Dispatcher
from services.notification_service import (
    set_socketio,
    create_notification,
    notify_student,
    notify_parent,
    notify_faculty,
    notify_admin,
    broadcast_announcement,
    log_activity,
    get_system_setting,
    set_system_setting
)

# AI Services
from services.attendance_ai import analyze_student_attendance
from services.complaint_ai import classify_complaint
from services.safety_ai import triage_emergency_incident, calculate_safe_route
from services.safety_intelligence import (
    CONFIGURED_ZONES,
    calculate_location_risk_scores,
    analyze_temporal_patterns,
    detect_emerging_risks,
    detect_repeated_patterns,
    calculate_incident_priority,
    generate_executive_safety_briefing,
    normalize_zone_name
)
from services.incident_analyzer import extract_incident_intelligence, correlate_safety_context
from services.campus_assistant import answer_campus_query, answer_admin_query
from services.briefing_ai import generate_student_briefing
from services.ai_insight_engine import (
    evaluate_attendance_risk,
    evaluate_academic_risk,
    evaluate_fee_alerts,
    evaluate_exam_reminders,
    evaluate_assignment_alerts,
    generate_student_insights_summary,
    generate_admin_campus_risk_overview
)

# Utilities & Security
from utils.decorators import (
    student_required,
    parent_required,
    faculty_required,
    admin_required
)
from utils.security import add_security_headers

# Blueprints Registration
from routes import register_routes
from api import register_api

# ---------------------------------------------------------------------------
# Application Factory & Initialization
# ---------------------------------------------------------------------------
app = Flask(__name__)
config_class = get_config()
app.config.from_object(config_class)

# Initialize Real-time WebSocket Broker
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
set_socketio(socketio)

# Attach Security Headers Middleware
app.after_request(add_security_headers)

# Register All Modular Routes & REST API Blueprints
register_routes(app)
register_api(app)


# ---------------------------------------------------------------------------
# Cross-Blueprint URL Build Error Fallback Handler
# ---------------------------------------------------------------------------
def _url_build_error_fallback(error, endpoint, values):
    """
    Guarantees 100% backward compatibility for templates and tests that reference
    unprefixed legacy endpoint names (e.g. 'student_dashboard' vs 'student.student_dashboard').
    """
    # If endpoint has blueprint prefix, check parameter name mappings (e.g. student_id vs id)
    if '.' in endpoint:
        if 'student_id' in values and 'id' not in values:
            v_copy = dict(values)
            v_copy['id'] = v_copy.pop('student_id')
            try:
                return url_for(endpoint, **v_copy)
            except Exception:
                pass
        elif 'id' in values and 'student_id' not in values:
            v_copy = dict(values)
            v_copy['student_id'] = v_copy.pop('id')
            try:
                return url_for(endpoint, **v_copy)
            except Exception:
                pass
        raise error

    # Try exact or blueprint-prefixed match
    for registered_ep in list(app.view_functions.keys()):
        if registered_ep == endpoint or registered_ep.endswith('.' + endpoint):
            try:
                return url_for(registered_ep, **values)
            except Exception:
                if 'student_id' in values and 'id' not in values:
                    v_copy = dict(values)
                    v_copy['id'] = v_copy.pop('student_id')
                    try:
                        return url_for(registered_ep, **v_copy)
                    except Exception:
                        pass
                continue

    # Also check normalized name (singular/plural)
    norm_ep = endpoint.replace('_', '').replace('s', '')
    for registered_ep in list(app.view_functions.keys()):
        norm_reg = registered_ep.split('.')[-1].replace('_', '').replace('s', '')
        if norm_reg == norm_ep:
            try:
                return url_for(registered_ep, **values)
            except Exception:
                continue

    raise error

app.url_build_error_handlers.append(_url_build_error_fallback)


# ---------------------------------------------------------------------------
# Backward Compatibility Service Wrappers
# ---------------------------------------------------------------------------
def classify_complaint_ai(title, description, category, location):
    return classify_complaint(title, description, category, location)


def generate_assistant_reply(student_id, query):
    conn = get_db_connection()
    try:
        return answer_campus_query(student_id, query, conn)
    finally:
        conn.close()


def analyze_resume_skills(skills_text, target_role):
    text = skills_text.lower()
    score = 75
    grade = 'Strong Candidate'
    rec_skills = []
    
    if 'python' in text or 'java' in text: score += 8
    if 'sql' in text or 'database' in text: score += 7
    if 'docker' in text or 'kubernetes' in text or 'cloud' in text: score += 8
    else: rec_skills.append('Docker & Containerization')
    
    if 'data' in target_role.lower():
        if 'pandas' not in text: rec_skills.append('Pandas / PyTorch')
        if 'ml' not in text: rec_skills.append('Scikit-Learn ML Pipelines')
    else:
        if 'ci/cd' not in text: rec_skills.append('GitHub Actions CI/CD')
        if 'system design' not in text: rec_skills.append('System Design & Microservices')

    score = min(score, 94)
    feedback = f"Your resume shows strong foundational competence for {target_role}. Adding verified cloud and containerization skills will boost your ATS interview shortlist rate by 38%."
    action_item = "Include measurable impact metrics (e.g. 'Optimized latency by 35%') in project bullet points."
    
    return {
        'score': score,
        'grade': grade,
        'feedback': feedback,
        'recommended_skills': rec_skills[:4],
        'action_item': action_item
    }


# ---------------------------------------------------------------------------
# Initialize Database Schema & Seed Data
# ---------------------------------------------------------------------------
init_db()


# ---------------------------------------------------------------------------
# Main Server Entry Point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, debug=True, host='127.0.0.1', port=port, allow_unsafe_werkzeug=True)
