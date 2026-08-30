"""
CampusGuard AI - Modular AI & Intelligence Services Package
"""

from .ai_service import call_ai_with_fallback, query_gemini_api
from .attendance_ai import analyze_student_attendance
from .complaint_ai import classify_complaint
from .safety_ai import triage_emergency_incident, calculate_safe_route
from .safety_intelligence import (
    CONFIGURED_ZONES,
    calculate_location_risk_scores,
    analyze_temporal_patterns,
    detect_emerging_risks,
    detect_repeated_patterns,
    calculate_incident_priority,
    generate_executive_safety_briefing,
    normalize_zone_name
)
from .incident_analyzer import extract_incident_intelligence, correlate_safety_context
from .campus_assistant import answer_campus_query, answer_admin_query
from .briefing_ai import generate_student_briefing
from .notification_service import (
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
from .ai_insight_engine import (
    evaluate_attendance_risk,
    evaluate_academic_risk,
    evaluate_fee_alerts,
    evaluate_exam_reminders,
    evaluate_assignment_alerts,
    generate_student_insights_summary,
    generate_admin_campus_risk_overview
)
from .academic_service import (
    calculate_grade_point,
    calculate_student_cgpa,
    sync_student_cgpa,
    get_student_academic_profile
)
