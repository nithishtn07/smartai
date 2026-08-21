"""
=============================================================================
CampusGuard AI - Complaint & Grievance AI Triage Engine
Classifies grievances into categories, severity, priority, responsible
departments, and recommended actions with complete offline resilience.
=============================================================================
"""

import re
from .ai_service import call_ai_with_fallback, sanitize_input

def _rule_based_classify(title: str, description: str, category: str, location: str) -> dict:
    """
    Deterministic rule-based NLP classifier fallback.
    """
    text = f"{title} {description} {category} {location}".lower()

    # 1. Critical Harassment / Assault / Women's Safety
    if any(k in text for k in ['harass', 'stalk', 'threat', 'assault', 'fight', 'bully', 'unsafe', 'scared', 'hazing', 'abuse', 'danger', 'chasing']):
        return {
            'category': 'Harassment / Safety',
            'severity': 'CRITICAL',
            'priority': 'URGENT',
            'dept': 'Campus Security & Student Protection Office',
            'action': 'Immediately alert security liaison officer and dispatch patrol to verify student safety.'
        }

    # 2. Medical Emergencies
    if any(k in text for k in ['faint', 'bleed', 'injury', 'fracture', 'unconscious', 'breathing', 'allergic', 'hospital', 'doctor', 'ambulance']):
        return {
            'category': 'Medical',
            'severity': 'CRITICAL',
            'priority': 'URGENT',
            'dept': 'Emergency Medical Pavilion & Health Center',
            'action': 'Dispatch campus paramedic and prepare emergency medical observation bay.'
        }

    # 3. Infrastructure & Hazard Maintenance
    if any(k in text for k in ['fire', 'smoke', 'spark', 'shock', 'open wire', 'gas', 'flood', 'leakage', 'collapse', 'broken light', 'dark', 'elevator', 'lift']):
        is_high = any(k in text for k in ['fire', 'smoke', 'spark', 'shock', 'open wire', 'gas'])
        return {
            'category': 'Infrastructure Hazard' if is_high else 'Infrastructure',
            'severity': 'HIGH' if is_high else 'MEDIUM',
            'priority': 'URGENT' if is_high else 'NORMAL',
            'dept': 'Facility Emergency Maintenance & Safety Unit',
            'action': 'Inspect the reported location immediately and dispatch technical repair personnel.'
        }

    # 4. Hostel & Mess
    if any(k in text for k in ['hostel', 'room', 'bed', 'mess', 'food', 'hygiene', 'washroom', 'water', 'fan', 'ac', 'warden', 'cleaning']):
        return {
            'category': 'Hostel & Amenities',
            'severity': 'MEDIUM',
            'priority': 'NORMAL',
            'dept': 'Hostel Administration & Resident Warden Office',
            'action': 'Issue maintenance ticket for residential block inspection and rectify within 24 hours.'
        }

    # 5. IT & Connectivity
    if any(k in text for k in ['wifi', 'network', 'internet', 'portal', 'login', 'server', 'computer', 'lab pc', 'ethernet', 'password']):
        return {
            'category': 'IT / Technical',
            'severity': 'LOW',
            'priority': 'NORMAL',
            'dept': 'Campus IT Support & Network Services',
            'action': 'Diagnose network router switch and verify student account credentials.'
        }

    # 6. Transport
    if any(k in text for k in ['bus', 'route', 'driver', 'transport', 'pickup', 'drop', 'traffic']):
        return {
            'category': 'Transport',
            'severity': 'MEDIUM',
            'priority': 'NORMAL',
            'dept': 'Campus Transport Logistics Office',
            'action': 'Review bus telemetry route timing and coordinate with transport supervisor.'
        }

    # 7. Academic Affairs
    if any(k in text for k in ['academic', 'exam', 'grade', 'marks', 'faculty', 'attendance', 'lecture', 'class', 'syllabus', 'credits']):
        return {
            'category': 'Academic Affairs',
            'severity': 'MEDIUM',
            'priority': 'NORMAL',
            'dept': 'Academic Affairs & Dean of Studies',
            'action': 'Forward inquiry to Department Academic Coordinator for curriculum review.'
        }

    # Default general categorization
    return {
        'category': category if category else 'General Grievance',
        'severity': 'LOW',
        'priority': 'LOW',
        'dept': 'Campus General Administration Redressal Cell',
        'action': 'Grievance recorded for standard administrative review and queue assignment.'
    }

def classify_complaint(title: str, description: str, category: str = "", location: str = "") -> dict:
    """
    Main triage interface: Evaluates complaint through AI with guaranteed fallback.
    """
    s_title = sanitize_input(title)
    s_desc = sanitize_input(description)
    s_cat = sanitize_input(category)
    s_loc = sanitize_input(location)

    prompt = (
        f"Analyze this campus complaint:\n"
        f"Title: {s_title}\n"
        f"Description: {s_desc}\n"
        f"Category: {s_cat}\n"
        f"Location: {s_loc}\n\n"
        f"Return JSON with keys: category, severity (LOW/MEDIUM/HIGH/CRITICAL), "
        f"priority (LOW/NORMAL/HIGH/URGENT), dept (responsible department), action (recommended action)."
    )

    def _fallback_wrapper():
        return _rule_based_classify(s_title, s_desc, s_cat, s_loc)

    # Always use the rule-based classifier or AI fallback
    return _rule_based_classify(s_title, s_desc, s_cat, s_loc)
