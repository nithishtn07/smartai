"""
=============================================================================
CampusGuard AI - Incident NLP Understanding & Historical Context Correlator
Extracts structured intelligence from natural-language incident reports and
correlates them against historical incidents for spatial-temporal patterns.
=============================================================================
"""

import datetime
from .safety_intelligence import normalize_zone_name

def extract_incident_intelligence(text: str, location_hint: str = "") -> dict:
    """
    Parses natural language incident descriptions to extract type, severity,
    priority, risk indicators, keywords, and responsible response units.
    """
    raw = f"{text} {location_hint}".lower()
    indicators = []
    keywords = []

    # 1. Fire / Electrical Hazards
    if any(k in raw for k in ['smoke', 'fire', 'spark', 'flame', 'burning', 'gas', 'explosion', 'blast']):
        indicators.extend(['Smoke/Fire Hazard', 'Electrical Grid Risk'])
        if 'trapped' in raw or 'inside' in raw or 'student' in raw:
            indicators.append('Occupied Area Vulnerability')
        keywords.extend(['smoke', 'fire', 'emergency'])
        return {
            'incident_type': 'Fire / Electrical Hazard',
            'severity': 'CRITICAL',
            'priority': 'IMMEDIATE',
            'location': normalize_zone_name(location_hint),
            'risk_indicators': indicators or ['Thermal Hazard'],
            'keywords': keywords or ['fire', 'electrical'],
            'department': 'Campus Security Quick Response + Emergency Fire Safety Unit',
            'recommended_action': 'Immediately deploy on-duty fire warden team with extinguisher units and initiate localized hall evacuation.'
        }

    # 2. Assault / Stalking / Harassment
    if any(k in raw for k in ['harass', 'stalk', 'follow', 'catcall', 'threat', 'assault', 'fight', 'weapon', 'scared', 'unsafe']):
        indicators.extend(['Personal Safety Threat', 'Nighttime Vulnerability'])
        if 'weapon' in raw or 'physical' in raw or 'hit' in raw:
            indicators.append('Immediate Violence Risk')
        keywords.extend(['harassment', 'threat', 'perimeter'])
        return {
            'incident_type': 'Harassment / Security Threat',
            'severity': 'CRITICAL' if 'weapon' in raw or 'assault' in raw else 'HIGH',
            'priority': 'IMMEDIATE' if 'weapon' in raw or 'assault' in raw else 'URGENT',
            'location': normalize_zone_name(location_hint),
            'risk_indicators': indicators or ['Personal Threat'],
            'keywords': keywords or ['harassment', 'security'],
            'department': 'Campus Security Command & Student Safety Liaison Desk',
            'recommended_action': 'Dispatch mobile patrol to intercept reported location, verify CCTV feed, and ensure student is escorted to safety.'
        }

    # 3. Medical Emergency
    if any(k in raw for k in ['faint', 'bleed', 'unconscious', 'fracture', 'injury', 'medical', 'breathing', 'heart', 'seizure']):
        indicators.extend(['Acute Medical Trauma', 'Urgent First Aid Required'])
        keywords.extend(['medical', 'paramedic', 'ambulance'])
        return {
            'incident_type': 'Medical Emergency',
            'severity': 'CRITICAL',
            'priority': 'IMMEDIATE',
            'location': normalize_zone_name(location_hint),
            'risk_indicators': indicators or ['Medical Alert'],
            'keywords': keywords or ['medical', 'health'],
            'department': 'Emergency Medical Pavilion & Health Center Ambulance',
            'recommended_action': 'Deploy medical responder with emergency resuscitation kit and prepare health center triage bed.'
        }

    # 4. Theft & Property Damage
    if any(k in raw for k in ['theft', 'stolen', 'laptop', 'bag', 'phone', 'wallet', 'scratch', 'break-in', 'vandalism']):
        indicators.extend(['Property Theft', 'Asset Security Breach'])
        keywords.extend(['theft', 'cctv_review', 'property'])
        return {
            'incident_type': 'Theft / Property Loss',
            'severity': 'MEDIUM',
            'priority': 'NORMAL',
            'location': normalize_zone_name(location_hint),
            'risk_indicators': indicators or ['Property Concern'],
            'keywords': keywords or ['theft', 'loss'],
            'department': 'Campus Security Surveillance & Lost Asset Recovery Cell',
            'recommended_action': 'Review timestamped surveillance camera recordings and log property serial numbers in security registry.'
        }

    # 5. Infrastructure & Environmental Hazards
    if any(k in raw for k in ['broken', 'light', 'dark', 'water', 'leak', 'glass', 'slippery', 'elevator', 'lift']):
        indicators.extend(['Physical Hazard', 'Infrastructure Deficit'])
        keywords.extend(['maintenance', 'lighting', 'hazard'])
        return {
            'incident_type': 'Infrastructure / Hazard Report',
            'severity': 'MEDIUM',
            'priority': 'NORMAL',
            'location': normalize_zone_name(location_hint),
            'risk_indicators': indicators or ['Facility Deficit'],
            'keywords': keywords or ['infrastructure', 'maintenance'],
            'department': 'Campus Facility Engineering & Maintenance Unit',
            'recommended_action': 'Issue maintenance ticket for technical personnel repair and cordon off hazard perimeter.'
        }

    # Default fallback
    return {
        'incident_type': 'General Campus Safety Report',
        'severity': 'LOW',
        'priority': 'LOW',
        'location': normalize_zone_name(location_hint),
        'risk_indicators': ['General Observation'],
        'keywords': ['campus', 'general'],
        'department': 'Campus General Security Administration',
        'recommended_action': 'Log report for routine patrol officer briefing and surveillance verification.'
    }


def correlate_safety_context(new_incident: dict, historical_incidents: list) -> dict:
    """
    Correlates a newly reported incident against historical database records
    to identify matching spatial-temporal patterns.
    """
    loc = normalize_zone_name(new_incident.get('location', ''))
    itype = str(new_incident.get('incident_type', '')).lower()

    matches = []
    for inc in historical_incidents or []:
        h_loc = normalize_zone_name(inc['location'] if hasattr(inc, '__getitem__') else getattr(inc, 'location', ''))
        h_type = str(inc['incident_type'] if hasattr(inc, '__getitem__') else getattr(inc, 'incident_type', '')).lower()

        if h_loc == loc:
            matches.append(inc)

    match_count = len(matches)
    if match_count >= 3:
        summary = (
            f"⚠️ Similar historical pattern detected: {match_count} incidents have been recorded "
            f"in {loc} during past surveillance periods."
        )
        recommendations = [
            f"Escalate security patrol presence in {loc}.",
            f"Audit CCTV camera operational angles covering {loc}.",
            f"Coordinate with facility maintenance for illumination verification."
        ]
        return {
            'has_pattern': True,
            'match_count': match_count,
            'pattern_summary': summary,
            'recommended_actions': recommendations
        }

    return {
        'has_pattern': False,
        'match_count': match_count,
        'pattern_summary': f"Isolated report. Recorded {match_count} prior event{'s' if match_count != 1 else ''} in {loc}.",
        'recommended_actions': [f"Standard operational logging and patrol verification for {loc}."]
    }
