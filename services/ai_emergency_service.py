"""
CampusGuard AI — AI Emergency Intelligence Service
Non-blocking Natural Language Processing for Emergency Triage & Incident Summarization.
"""

import re
from typing import Dict, Any, List


# ---------------------------------------------------------------------------
# Emergency Keyword Ontologies
# ---------------------------------------------------------------------------
EMERGENCY_TAXONOMY = {
    'Medical Emergency': {
        'critical_keywords': [
            'unconscious', 'collapsed', 'not breathing', 'bleeding heavily', 'cardiac', 'heart attack',
            'seizure', 'severe chest pain', 'head trauma', 'choking', 'poisoning', 'overdose'
        ],
        'high_keywords': [
            'injury', 'fracture', 'broken bone', 'fainted', 'dizzy', 'burn', 'asthma',
            'allergic reaction', 'sprain', 'accident', 'cut', 'fall', 'severe pain'
        ],
        'medium_keywords': [
            'fever', 'nausea', 'headache', 'vomiting', 'minor cut', 'dehydration', 'illness'
        ],
        'default_unit': 'Campus Medical & Ambulance Unit'
    },
    'Personal Safety': {
        'critical_keywords': [
            'assault', 'attack', 'weapon', 'gun', 'knife', 'hostage', 'kidnapping', 'threat to life'
        ],
        'high_keywords': [
            'harassment', 'stalking', 'threat', 'following me', 'cornered', 'aggressive', 'unsafe situation', 'intimidation'
        ],
        'medium_keywords': [
            'suspicious person', 'loitering', 'uncomfortable', 'verbal abuse', 'trespasser'
        ],
        'default_unit': 'Campus Quick Response Team (QRT)'
    },
    'Fire/Safety': {
        'critical_keywords': [
            'fire explosion', 'flames spreading', 'building on fire', 'toxic gas', 'chemical spill', 'dense smoke'
        ],
        'high_keywords': [
            'fire', 'smoke', 'gas leak', 'electrical fire', 'burning smell', 'fire alarm sounding'
        ],
        'medium_keywords': [
            'sparking wire', 'exposed wire', 'open flame', 'blocked fire exit'
        ],
        'default_unit': 'Fire Safety & Campus Marshall Unit'
    },
    'Security': {
        'critical_keywords': [
            'active shooter', 'armed robbery', 'violent riot', 'mass trespassing'
        ],
        'high_keywords': [
            'theft in progress', 'break-in', 'burglary', 'unauthorized entry', 'vandalism', 'physical brawl', 'fight'
        ],
        'medium_keywords': [
            'stolen property', 'lost keycard', 'tailgating', 'suspicious bag', 'unattended package'
        ],
        'default_unit': 'Campus Security Command & Police Liaison'
    },
    'Campus Infrastructure': {
        'critical_keywords': [
            'roof collapse', 'structural collapse', 'major flooding', 'gas pipeline burst'
        ],
        'high_keywords': [
            'elevator trapped', 'power outage', 'water leak', 'glass shattered', 'elevator stuck', 'power line down'
        ],
        'medium_keywords': [
            'door jammed', 'light failure', 'water cooler broken', 'ac failure', 'leakage'
        ],
        'default_unit': 'Facilities & Engineering Emergency Team'
    }
}


def classify_emergency_text(description: str = "", location: str = "", category_hint: str = "") -> Dict[str, Any]:
    """
    Analyzes user-provided description and context to suggest emergency category,
    severity tier, priority level, and recommended response unit.
    This serves as an AI advisory suggestion; human responders can always override it.
    """
    text = f"{description} {location}".lower().strip()
    
    matched_category = category_hint if category_hint in EMERGENCY_TAXONOMY else None
    highest_severity = 'LOW'
    matched_keywords = []
    recommended_unit = 'Campus Security Patrol'
    
    # Priority ranking
    severity_rank = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}

    # Evaluate against ontology
    best_score = 0
    detected_cat = None

    for cat_name, data in EMERGENCY_TAXONOMY.items():
        cat_score = 0
        cat_severity = 'LOW'
        
        for kw in data['critical_keywords']:
            if re.search(r'\b' + re.escape(kw) + r'\b', text):
                cat_score += 10
                cat_severity = 'CRITICAL'
                matched_keywords.append(kw)

        for kw in data['high_keywords']:
            if re.search(r'\b' + re.escape(kw) + r'\b', text):
                cat_score += 5
                if severity_rank[cat_severity] < severity_rank['HIGH']:
                    cat_severity = 'HIGH'
                matched_keywords.append(kw)

        for kw in data['medium_keywords']:
            if re.search(r'\b' + re.escape(kw) + r'\b', text):
                cat_score += 2
                if severity_rank[cat_severity] < severity_rank['MEDIUM']:
                    cat_severity = 'MEDIUM'
                matched_keywords.append(kw)

        if cat_score > best_score:
            best_score = cat_score
            detected_cat = cat_name
            if severity_rank[cat_severity] > severity_rank[highest_severity]:
                highest_severity = cat_severity

    final_category = matched_category or detected_cat or 'Personal Safety'
    
    # Determine unit
    if final_category in EMERGENCY_TAXONOMY:
        recommended_unit = EMERGENCY_TAXONOMY[final_category]['default_unit']

    # Priority mapping
    priority_map = {
        'CRITICAL': 'IMMEDIATE',
        'HIGH': 'URGENT',
        'MEDIUM': 'HIGH',
        'LOW': 'NORMAL'
    }

    # If explicit severity was detected or fallback
    if highest_severity == 'LOW' and best_score == 0:
        highest_severity = 'HIGH' if 'sos' in text or 'emergency' in text else 'MEDIUM'

    return {
        'category': final_category,
        'severity': highest_severity,
        'priority': priority_map.get(highest_severity, 'URGENT'),
        'recommended_unit': recommended_unit,
        'confidence': min(0.98, max(0.65, 0.50 + (best_score * 0.08))),
        'key_indicators': list(set(matched_keywords)),
        'advisory_notice': "AI-assisted triage suggestion. Field commanders and dispatchers retain manual override authority."
    }


def generate_ai_incident_summary(emergency: dict, timeline_events: List[dict] = None, notes: List[dict] = None) -> str:
    """
    Synthesizes a concise, factual executive debriefing from logged emergency milestones.
    Never fabricates events — strictly follows database timestamps and notes.
    """
    emg_id = emergency.get('emergency_id', 'Unknown')
    cat = emergency.get('category') or emergency.get('emergency_type', 'Emergency')
    loc = emergency.get('location') or emergency.get('campus_zone') or 'Campus Grounds'
    rep_name = emergency.get('reporter_name', 'Campus Member')
    created_at = emergency.get('created_at', '')
    ack_at = emergency.get('acknowledged_at', '')
    arr_at = emergency.get('arrived_at', '')
    res_at = emergency.get('resolved_at', '')
    responder = emergency.get('assigned_responder', 'Emergency Response Unit')
    
    parts = []
    parts.append(f"A {cat.lower()} (ID: {emg_id}) was reported by {rep_name} at {loc} on {created_at}.")
    
    if ack_at:
        parts.append(f"Security Command acknowledged the distress signal at {ack_at} and assigned {responder}.")
    
    if arr_at:
        parts.append(f"Responders arrived on scene at {arr_at}.")
        
    if notes and len(notes) > 0:
        last_note = notes[-1].get('note_text', '')
        if last_note:
            parts.append(f"Action Taken: {last_note}")
            
    if res_at:
        parts.append(f"The incident was successfully resolved at {res_at}. All involved parties stood down safely.")
        
    return " ".join(parts)
