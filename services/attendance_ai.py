"""
=============================================================================
CampusGuard AI - Attendance Intelligence Service
Analyzes course attendance, calculates safe missed class predictions,
detects threshold risks, and generates actionable academic guidance.
=============================================================================
"""

import math

def analyze_student_attendance(records):
    """
    Analyzes list of course attendance records for a student.
    Returns structured analysis with overall metrics, risk courses,
    absence predictions, and recommendations.
    """
    if not records:
        return {
            'overall_pct': 0.0,
            'total_held': 0,
            'total_attended': 0,
            'total_missed': 0,
            'risk_level': 'UNKNOWN',
            'risk_courses': [],
            'predictions': [],
            'recommendations': ["Insufficient attendance records logged in the system."]
        }

    total_held = sum(r['classes_held'] for r in records)
    total_attended = sum(r['classes_attended'] for r in records)
    total_missed = sum(r['classes_missed'] for r in records)
    overall_pct = round((total_attended / total_held * 100), 1) if total_held > 0 else 0.0

    risk_courses = []
    predictions = []
    recommendations = []

    for r in records:
        pct = r['attendance_pct']
        held = r['classes_held']
        attended = r['classes_attended']
        code = r['subject_code']
        name = r['subject_name']

        # Safe absences arithmetic: (attended - 0.75 * held) / 0.75
        # If student misses M classes: new_pct = attended / (held + M) >= 0.75 -> attended >= 0.75 * held + 0.75 * M -> M <= (attended - 0.75*held)/0.75
        margin = attended - (0.75 * held)
        safe_misses = math.floor(margin / 0.75) if margin > 0 else 0

        # Classes needed to recover if below 75%
        # (attended + R) / (held + R) >= 0.75 -> attended + R >= 0.75*held + 0.75*R -> 0.25*R >= 0.75*held - attended -> R = ceil((0.75*held - attended) / 0.25)
        classes_needed = math.ceil((0.75 * held - attended) / 0.25) if margin < 0 else 0

        status = 'GOOD'
        if pct < 75.0:
            status = 'CRITICAL'
            risk_courses.append({
                'code': code,
                'name': name,
                'pct': pct,
                'status': 'CRITICAL',
                'warning': f"Attendance is below 75% minimum requirement.",
                'action': f"Must attend next {classes_needed} consecutive lecture{'s' if classes_needed > 1 else ''} to restore eligibility."
            })
            recommendations.append(f"Priority Alert: Attend all upcoming {name} ({code}) classes to recover from {pct}% to 75%.")
        elif pct <= 80.0:
            status = 'WARNING'
            risk_courses.append({
                'code': code,
                'name': name,
                'pct': pct,
                'status': 'WARNING',
                'warning': f"Attendance at {pct}% is approaching the 75% threshold.",
                'action': f"You can safely miss at most {safe_misses} class before reaching the warning line."
            })
            recommendations.append(f"Caution: {name} ({code}) attendance is at {pct}%. Avoid absences to prevent shortage.")
        else:
            status = 'EXCELLENT'

        predictions.append({
            'code': code,
            'name': name,
            'pct': pct,
            'safe_misses': safe_misses,
            'classes_needed': classes_needed,
            'status': status
        })

    # Overall summary assessment
    if overall_pct >= 85.0:
        risk_level = 'LOW'
        if not recommendations:
            recommendations.append("Overall academic attendance is in good standing. Maintain this consistent presence.")
    elif overall_pct >= 75.0:
        risk_level = 'MODERATE'
        recommendations.append("Overall aggregate attendance is close to the 75% requirement. Minimize future absences.")
    else:
        risk_level = 'HIGH'
        recommendations.append("Urgent: Aggregate attendance is in critical shortage. Academic advising meeting recommended.")

    return {
        'overall_pct': overall_pct,
        'total_held': total_held,
        'total_attended': total_attended,
        'total_missed': total_missed,
        'risk_level': risk_level,
        'risk_courses': risk_courses,
        'predictions': predictions,
        'recommendations': recommendations
    }
