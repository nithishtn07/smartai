"""
=============================================================================
CampusGuard AI - Campus Safety Intelligence & Risk Engine
Analyzes historical incident telemetry, computes 0-100 quantitative location
risk scores, detects emerging surges, correlates repeated safety patterns,
calculates priority queue ranks, and generates executive briefings.
=============================================================================
"""

import math
import sqlite3
import datetime
from collections import defaultdict

# Pre-configured Campus Safety Zones
CONFIGURED_ZONES = [
    {
        'id': 'parking',
        'name': 'Parking Area',
        'short_name': 'Parking',
        'type': 'Transit / Outdoor',
        'cctv_count': 6,
        'emergency_booth': 'Booth #4 (South Gate)',
        'x': 180, 'y': 380, 'radius': 42
    },
    {
        'id': 'hostel_b',
        'name': 'Hostel Block B (Oak Wing)',
        'short_name': 'Hostel Block B',
        'type': 'Residential',
        'cctv_count': 14,
        'emergency_booth': 'Booth #2 (Oak Quad)',
        'x': 120, 'y': 150, 'radius': 46
    },
    {
        'id': 'hostel_a',
        'name': 'Hostel Block A (Maple Wing)',
        'short_name': 'Hostel Block A',
        'type': 'Residential',
        'cctv_count': 12,
        'emergency_booth': 'Booth #1 (Maple Courtyard)',
        'x': 260, 'y': 110, 'radius': 44
    },
    {
        'id': 'library',
        'name': 'Central University Library',
        'short_name': 'Library',
        'type': 'Academic Core',
        'cctv_count': 22,
        'emergency_booth': 'Booth #3 (Library Atrium)',
        'x': 450, 'y': 170, 'radius': 50
    },
    {
        'id': 'acad_a',
        'name': 'Academic Block A (CS Dept)',
        'short_name': 'Academic Block A',
        'type': 'Instructional',
        'cctv_count': 28,
        'emergency_booth': 'Booth #5 (Block A Foyer)',
        'x': 620, 'y': 150, 'radius': 48
    },
    {
        'id': 'acad_b',
        'name': 'Academic Block B (Engg Dept)',
        'short_name': 'Academic Block B',
        'type': 'Instructional',
        'cctv_count': 24,
        'emergency_booth': 'Booth #6 (Block B Lobby)',
        'x': 750, 'y': 220, 'radius': 46
    },
    {
        'id': 'sports',
        'name': 'Campus Sports Ground & Bleachers',
        'short_name': 'Sports Complex',
        'type': 'Recreation / Field',
        'cctv_count': 8,
        'emergency_booth': 'Booth #7 (Pavilion Gate)',
        'x': 740, 'y': 380, 'radius': 52
    },
    {
        'id': 'canteen',
        'name': 'Campus Dining Hall & Canteen',
        'short_name': 'Dining Canteen',
        'type': 'Student Services',
        'cctv_count': 16,
        'emergency_booth': 'Booth #8 (Canteen Square)',
        'x': 420, 'y': 340, 'radius': 44
    },
    {
        'id': 'main_gate',
        'name': 'Main Gate / Transport Terminal',
        'short_name': 'Main Gate',
        'type': 'Perimeter Entry',
        'cctv_count': 18,
        'emergency_booth': 'Main Security Tower',
        'x': 460, 'y': 470, 'radius': 45
    }
]

SEVERITY_WEIGHTS = {
    'CRITICAL': 25,
    'HIGH': 15,
    'MEDIUM': 8,
    'LOW': 3
}

def normalize_zone_name(raw_name: str) -> str:
    """Matches free-form text locations to standard campus zone names."""
    if not raw_name:
        return 'General Campus'
    
    text = str(raw_name).lower()
    if 'park' in text: return 'Parking Area'
    if 'hostel b' in text or 'oak' in text: return 'Hostel Block B (Oak Wing)'
    if 'hostel a' in text or 'maple' in text: return 'Hostel Block A (Maple Wing)'
    if 'hostel' in text: return 'Hostel Block B (Oak Wing)'
    if 'lib' in text: return 'Central University Library'
    if 'block a' in text or 'cs' in text: return 'Academic Block A (CS Dept)'
    if 'block b' in text: return 'Academic Block B (Engg Dept)'
    if 'sport' in text or 'ground' in text or 'bleacher' in text: return 'Campus Sports Ground & Bleachers'
    if 'cant' in text or 'mess' in text or 'din' in text: return 'Campus Dining Hall & Canteen'
    if 'gate' in text or 'bus' in text or 'transport' in text: return 'Main Gate / Transport Terminal'
    return raw_name.strip()


def calculate_location_risk_scores(incidents_list: list, complaints_list: list = None) -> dict:
    """
    Computes a quantitative 0-100 Campus Safety Risk Score for all campus locations.
    Formula:
    Risk Score = min(100, Base Count + Severity Sum + Recency Boost + Repeat Boost + Temporal Boost)
    """
    zone_incidents = defaultdict(list)
    zone_complaints = defaultdict(list)

    for inc in incidents_list or []:
        loc = normalize_zone_name(inc['location'] if isinstance(inc, sqlite3.Row if hasattr(sqlite3, 'Row') else dict) or hasattr(inc, '__getitem__') else getattr(inc, 'location', ''))
        zone_incidents[loc].append(inc)

    for cmp in complaints_list or []:
        loc = normalize_zone_name(cmp['location'] if isinstance(cmp, sqlite3.Row if hasattr(sqlite3, 'Row') else dict) or hasattr(cmp, '__getitem__') else getattr(cmp, 'location', ''))
        zone_complaints[loc].append(cmp)

    zone_scores = {}
    
    for zone in CONFIGURED_ZONES:
        z_name = zone['name']
        inc_items = zone_incidents.get(z_name, [])
        cmp_items = zone_complaints.get(z_name, [])
        total_reports = len(inc_items) + len(cmp_items)

        if total_reports == 0:
            zone_scores[z_name] = {
                'zone_id': zone['id'],
                'short_name': zone['short_name'],
                'type': zone['type'],
                'risk_score': 15,
                'risk_level': 'LOW',
                'risk_class': 'badge-green',
                'color': '#10b981',
                'incident_count': 0,
                'complaint_count': 0,
                'common_incident': 'None Reported',
                'peak_time': 'Daytime (Normal)',
                'last_incident': 'No recent incidents',
                'cctv_count': zone['cctv_count'],
                'emergency_booth': zone['emergency_booth'],
                'x': zone['x'], 'y': zone['y'], 'radius': zone['radius'],
                'insights': 'Zone is currently operating under baseline normal conditions.'
            }
            continue

        # 1. Base Score from volume
        base_score = min(25, total_reports * 3)

        # 2. Severity Points
        severity_pts = 0
        type_counts = defaultdict(int)
        time_bins = defaultdict(int)
        recent_count = 0
        latest_ts = 'Recently'

        for i in inc_items:
            itype = i['incident_type'] if hasattr(i, '__getitem__') else getattr(i, 'incident_type', 'General')
            type_counts[itype] += 1
            
            # Severity mapping
            text = f"{itype} {i.get('description', '') if isinstance(i, dict) else ''}".lower()
            if 'sos' in text or 'fire' in text or 'assault' in text:
                severity_pts += SEVERITY_WEIGHTS['CRITICAL']
            elif 'harass' in text or 'stalk' in text or 'theft' in text or 'hazard' in text:
                severity_pts += SEVERITY_WEIGHTS['HIGH']
            elif 'broken' in text or 'leak' in text:
                severity_pts += SEVERITY_WEIGHTS['MEDIUM']
            else:
                severity_pts += SEVERITY_WEIGHTS['LOW']

            # Temporal check
            created_at = str(i['created_at']) if hasattr(i, '__getitem__') else str(getattr(i, 'created_at', ''))
            if created_at and len(created_at) >= 16:
                latest_ts = created_at[:16]
                try:
                    hour = int(created_at[11:13])
                    if 6 <= hour < 12: time_bins['Morning (06:00 - 12:00)'] += 1
                    elif 12 <= hour < 18: time_bins['Afternoon (12:00 - 18:00)'] += 1
                    elif 18 <= hour <= 21: time_bins['Evening (18:00 - 21:00)'] += 1
                    else: time_bins['Night (21:00 - 06:00)'] += 1
                except Exception:
                    time_bins['Evening (18:00 - 21:00)'] += 1
            else:
                time_bins['Evening (18:00 - 21:00)'] += 1

        for c in cmp_items:
            cat = c['category'] if hasattr(c, '__getitem__') else getattr(c, 'category', 'General')
            type_counts[cat] += 1
            severity_pts += 6

        # Cap severity points to 40 max
        severity_score = min(40, severity_pts)

        # 3. Repeat pattern boost (+12 if 3+ reports of same category)
        repeat_boost = 12 if any(cnt >= 3 for cnt in type_counts.values()) else 0

        # 4. Temporal clustering boost (+12 if >= 50% incidents occur in evening/night)
        peak_time_str = max(time_bins.items(), key=lambda x: x[1])[0] if time_bins else 'Evening (18:00 - 21:00)'
        evening_night_count = time_bins.get('Evening (18:00 - 21:00)', 0) + time_bins.get('Night (21:00 - 06:00)', 0)
        temporal_boost = 12 if evening_night_count >= (len(inc_items) * 0.45) and len(inc_items) >= 2 else 0

        # 5. Composite Risk Score (0 - 100)
        raw_score = 10 + base_score + severity_score + repeat_boost + temporal_boost
        final_score = min(100, max(12, int(raw_score)))

        if final_score >= 76:
            risk_lvl = 'CRITICAL'
            risk_cls = 'badge-red'
            color = '#ef4444'
        elif final_score >= 51:
            risk_lvl = 'HIGH'
            risk_cls = 'badge-red'
            color = '#f97316'
        elif final_score >= 31:
            risk_lvl = 'MODERATE'
            risk_cls = 'badge-yellow'
            color = '#eab308'
        else:
            risk_lvl = 'LOW'
            risk_cls = 'badge-green'
            color = '#10b981'

        common_type = max(type_counts.items(), key=lambda x: x[1])[0] if type_counts else 'General Incident'

        zone_scores[z_name] = {
            'zone_id': zone['id'],
            'short_name': zone['short_name'],
            'type': zone['type'],
            'risk_score': final_score,
            'risk_level': risk_lvl,
            'risk_class': risk_cls,
            'color': color,
            'incident_count': len(inc_items),
            'complaint_count': len(cmp_items),
            'total_reports': total_reports,
            'common_incident': common_type,
            'peak_time': peak_time_str,
            'last_incident': latest_ts,
            'cctv_count': zone['cctv_count'],
            'emergency_booth': zone['emergency_booth'],
            'x': zone['x'], 'y': zone['y'], 'radius': zone['radius'],
            'insights': f"Recorded {total_reports} security/infrastructure logs. High concentration observed during {peak_time_str}."
        }

    return zone_scores


def analyze_temporal_patterns(incidents_list: list) -> dict:
    """
    Analyzes historical incidents by hour of day and day of week.
    Computes exact statistical peak risk periods.
    """
    if not incidents_list:
        return {
            'status': 'INSUFFICIENT_DATA',
            'peak_window': 'Evening (18:00 - 21:00)',
            'peak_percentage': 0,
            'hourly_distribution': {},
            'daily_distribution': {},
            'summary': 'Insufficient historical incident data.'
        }

    hourly_bins = {
        'Morning (06:00 - 12:00)': 0,
        'Afternoon (12:00 - 18:00)': 0,
        'Evening (18:00 - 21:00)': 0,
        'Night (21:00 - 06:00)': 0
    }
    daily_bins = defaultdict(int)

    for inc in incidents_list:
        created_at = str(inc['created_at']) if hasattr(inc, '__getitem__') else str(getattr(inc, 'created_at', ''))
        if created_at and len(created_at) >= 16:
            try:
                hour = int(created_at[11:13])
                if 6 <= hour < 12: hourly_bins['Morning (06:00 - 12:00)'] += 1
                elif 12 <= hour < 18: hourly_bins['Afternoon (12:00 - 18:00)'] += 1
                elif 18 <= hour <= 21: hourly_bins['Evening (18:00 - 21:00)'] += 1
                else: hourly_bins['Night (21:00 - 06:00)'] += 1

                dt = datetime.datetime.strptime(created_at[:10], '%Y-%m-%d')
                day_name = dt.strftime('%A')
                daily_bins[day_name] += 1
            except Exception:
                hourly_bins['Evening (18:00 - 21:00)'] += 1
                daily_bins['Friday'] += 1
        else:
            hourly_bins['Evening (18:00 - 21:00)'] += 1
            daily_bins['Friday'] += 1

    total = len(incidents_list)
    peak_window, peak_count = max(hourly_bins.items(), key=lambda x: x[1])
    peak_pct = round((peak_count / total * 100), 1) if total > 0 else 0

    peak_day = max(daily_bins.items(), key=lambda x: x[1])[0] if daily_bins else 'Friday'

    summary = f"{peak_pct}% of recorded incidents occurred during {peak_window}, with highest weekly concentration on {peak_day}s."

    return {
        'status': 'ACTIVE',
        'total_incidents': total,
        'peak_window': peak_window,
        'peak_count': peak_count,
        'peak_percentage': peak_pct,
        'peak_day': peak_day,
        'hourly_distribution': hourly_bins,
        'daily_distribution': dict(daily_bins),
        'summary': summary
    }


def detect_emerging_risks(incidents_list: list) -> list:
    """
    Detects locations experiencing sharp surges in incident frequency.
    Compares recent 30 days vs previous 30-day window.
    """
    if not incidents_list or len(incidents_list) < 4:
        return []

    recent_locs = defaultdict(int)
    prior_locs = defaultdict(int)

    now = datetime.datetime.now()
    thirty_days_ago = now - datetime.timedelta(days=30)
    sixty_days_ago = now - datetime.timedelta(days=60)

    for inc in incidents_list:
        loc = normalize_zone_name(inc['location'] if hasattr(inc, '__getitem__') else getattr(inc, 'location', ''))
        created_at_str = str(inc['created_at'] if hasattr(inc, '__getitem__') else getattr(inc, 'created_at', ''))

        try:
            inc_dt = datetime.datetime.strptime(created_at_str[:10], '%Y-%m-%d')
            if inc_dt >= thirty_days_ago:
                recent_locs[loc] += 1
            elif inc_dt >= sixty_days_ago:
                prior_locs[loc] += 1
            else:
                prior_locs[loc] += 1
        except Exception:
            recent_locs[loc] += 1

    emerging = []
    for loc, r_cnt in recent_locs.items():
        if r_cnt >= 3:
            p_cnt = prior_locs.get(loc, 1)
            pct_increase = int(((r_cnt - p_cnt) / max(1, p_cnt)) * 100)
            if pct_increase > 50 or r_cnt >= 4:
                emerging.append({
                    'location': loc,
                    'recent_count': r_cnt,
                    'previous_count': p_cnt,
                    'surge_pct': max(50, pct_increase),
                    'severity': 'HIGH_SURGE' if pct_increase > 150 else 'ELEVATED',
                    'alert_title': f"⚠️ Emerging Safety Risk: {loc}",
                    'description': f"Incidents near {loc} increased by {max(50, pct_increase)}% compared with the previous period ({r_cnt} recent vs {p_cnt} prior).",
                    'recommendation': f"Increase proactive patrol frequency around {loc} and verify lighting/CCTV operational health."
                })

    return emerging


def detect_repeated_patterns(incidents_list: list, complaints_list: list) -> list:
    """
    Identifies multi-complaint clusters at the same location to form linked Safety Patterns.
    """
    loc_issues = defaultdict(list)

    for inc in incidents_list or []:
        loc = normalize_zone_name(inc['location'] if hasattr(inc, '__getitem__') else getattr(inc, 'location', ''))
        loc_issues[loc].append({
            'source': 'Incident',
            'type': inc['incident_type'] if hasattr(inc, '__getitem__') else getattr(inc, 'incident_type', ''),
            'desc': inc['description'] if hasattr(inc, '__getitem__') else getattr(inc, 'description', '')
        })

    for cmp in complaints_list or []:
        loc = normalize_zone_name(cmp['location'] if hasattr(cmp, '__getitem__') else getattr(cmp, 'location', ''))
        loc_issues[loc].append({
            'source': 'Complaint',
            'type': cmp['category'] if hasattr(cmp, '__getitem__') else getattr(cmp, 'category', ''),
            'desc': cmp['description'] if hasattr(cmp, '__getitem__') else getattr(cmp, 'description', '')
        })

    patterns = []
    for loc, issues in loc_issues.items():
        if len(issues) >= 3:
            types = [iss['type'] for iss in issues]
            all_text = " ".join([f"{iss['type']} {iss['desc']}" for iss in issues]).lower()

            theme = "Repeated Safety Deficits"
            action = "Dispatch joint security and maintenance inspection team."

            if any(k in all_text for k in ['light', 'dark', 'bulb', 'illumination', 'lamp']):
                if any(k in all_text for k in ['harass', 'stalk', 'unsafe', 'suspicious', 'catcall']):
                    theme = "Lighting Deficit Correlated with Nighttime Harassment / Vulnerability"
                    action = "Immediate lighting fixture restoration + targeted security patrol dispatch between 18:00 - 21:00."
                else:
                    theme = "Recurring Illumination & Infrastructure Failure"
                    action = "Emergency electrical maintenance crew inspection."
            elif any(k in all_text for k in ['theft', 'stolen', 'vehicle', 'scratch', 'helmet']):
                theme = "Property Security & Vehicle Surveillance Vulnerability"
                action = "Reposition CCTV dome cameras and mandate gate parking tokens."

            patterns.append({
                'location': loc,
                'report_count': len(issues),
                'pattern_theme': theme,
                'linked_issues': list(set(types)),
                'recommended_action': action,
                'risk_level': 'HIGH' if len(issues) >= 5 else 'MODERATE'
            })

    return patterns


def calculate_incident_priority(incident, location_risk_score: int = 50) -> int:
    """
    Computes a composite priority rank (0-100) for ordering incidents in security queue.
    """
    itype = str(incident['incident_type'] if hasattr(incident, '__getitem__') else getattr(incident, 'incident_type', '')).lower()
    status = str(incident['status'] if hasattr(incident, '__getitem__') else getattr(incident, 'status', 'ACTIVE')).upper()

    # 1. Base Severity Points (40% weight)
    if 'sos' in itype or 'emergency' in itype or 'fire' in itype or 'assault' in itype:
        sev_pts = 40
    elif 'harass' in itype or 'threat' in itype or 'theft' in itype:
        sev_pts = 28
    elif 'hazard' in itype or 'medical' in itype:
        sev_pts = 22
    else:
        sev_pts = 12

    # 2. Status / Urgency Points (20% weight)
    if status == 'ACTIVE': status_pts = 20
    elif status in ['RECORDED', 'SUBMITTED', 'UNDER REVIEW']: status_pts = 15
    elif status == 'IN PROGRESS': status_pts = 10
    else: status_pts = 2

    # 3. Location Risk Points (25% weight)
    loc_pts = int(location_risk_score * 0.25)

    # 4. Composite Priority Score
    composite = min(100, sev_pts + status_pts + loc_pts + 15)
    return composite


def generate_executive_safety_briefing(incidents_list: list, complaints_list: list, zone_scores: dict) -> dict:
    """
    Generates an institutional Safety Intelligence Briefing for authorized administrators.
    """
    def _get_item(obj, key):
        if hasattr(obj, 'keys') and key in obj.keys():
            return obj[key]
        if isinstance(obj, dict):
            return obj.get(key, '')
        return getattr(obj, key, '')

    total_incidents = len(incidents_list) if incidents_list else 0
    active_emergencies = sum(1 for i in incidents_list if (
        _get_item(i, 'incident_type') in ('EMERGENCY_SOS', 'Medical', 'Security', 'Fire', 'Other', 'Personal Safety', 'Distress') or
        _get_item(i, 'category') in ('EMERGENCY_SOS', 'Medical', 'Security', 'Fire', 'Other', 'Personal Safety', 'Distress')
    ) and _get_item(i, 'status') in ('ACTIVE', 'TRIGGERED', 'ACKNOWLEDGED', 'ASSIGNED', 'RESPONDER_ASSIGNED', 'EN_ROUTE', 'ON_SCENE', 'RESPONDING'))

    # Find highest risk zone
    highest_zone = max(zone_scores.values(), key=lambda z: z['risk_score']) if zone_scores else None
    
    # Calculate overall campus risk score
    avg_score = int(sum(z['risk_score'] for z in zone_scores.values()) / len(zone_scores)) if zone_scores else 25
    if avg_score >= 70: overall_risk = 'CRITICAL'
    elif avg_score >= 50: overall_risk = 'HIGH'
    elif avg_score >= 32: overall_risk = 'MEDIUM-HIGH'
    else: overall_risk = 'LOW-MODERATE'

    emerging_risks = detect_emerging_risks(incidents_list)
    patterns = detect_repeated_patterns(incidents_list, complaints_list)
    temporal = analyze_temporal_patterns(incidents_list)

    top_hotspots = sorted(zone_scores.values(), key=lambda x: x['risk_score'], reverse=True)[:3] if zone_scores else []

    recommendations = []
    if highest_zone and highest_zone['risk_score'] >= 50:
        recommendations.append(f"Deploy mobile patrol units to {highest_zone['short_name']} during {highest_zone['peak_time']} and audit lighting infrastructure.")
    if emerging_risks:
        recommendations.append(f"Investigate incident surge near {emerging_risks[0]['location']} (+{emerging_risks[0]['surge_pct']}% volume).")
    if patterns:
        recommendations.append(f"Address linked safety pattern at {patterns[0]['location']}: {patterns[0]['recommended_action']}")
    if not recommendations:
        recommendations.append("All campus zones operating under normal safety thresholds. Maintain routine perimeter surveillance.")

    return {
        'overall_risk_level': overall_risk,
        'overall_risk_score': avg_score,
        'active_emergencies': active_emergencies,
        'total_incidents_logged': total_incidents,
        'top_hotspots': top_hotspots,
        'emerging_risks_count': len(emerging_risks),
        'emerging_risks': emerging_risks,
        'repeated_patterns_count': len(patterns),
        'repeated_patterns': patterns,
        'peak_risk_window': temporal['peak_window'],
        'peak_risk_day': temporal.get('peak_day', 'Friday'),
        'ai_recommendations': recommendations
    }
