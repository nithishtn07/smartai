"""
=============================================================================
CampusGuard AI — Central AI Insight Engine
=============================================================================
Comprehensive multi-source intelligence engine analyzing academic performance,
attendance patterns, examination preparedness, fee dues, and student safety.
Provides actionable alerts and diagnostic summaries with confidence scores.
=============================================================================
"""

import datetime
from database.db import get_db_connection


def evaluate_attendance_risk(student_id: int, conn=None, threshold: float = 75.0) -> dict:
    """
    Analyzes student subject-wise attendance to calculate risk tiers and safe margins.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        records = conn.execute(
            "SELECT * FROM attendance WHERE student_id = ?", (student_id,)
        ).fetchall()

        if not records:
            return {
                'status': 'INSUFFICIENT_DATA',
                'overall_pct': 0.0,
                'at_risk_count': 0,
                'critical_subjects': [],
                'safe_subjects': [],
                'recommendation': 'No attendance records logged yet for this semester.'
            }

        total_held = sum(r['classes_held'] for r in records)
        total_att = sum(r['classes_attended'] for r in records)
        overall_pct = round((total_att / total_held * 100.0), 1) if total_held > 0 else 100.0

        critical = []
        warning = []
        safe = []

        for r in records:
            pct = r['attendance_pct']
            held = r['classes_held']
            att = r['classes_attended']

            # Calculate classes needed to reach threshold if below
            classes_needed = 0
            if pct < threshold and held > 0:
                # (att + x) / (held + x) >= threshold / 100
                # att + x >= 0.75 * held + 0.75 * x
                # 0.25 * x >= 0.75 * held - att
                target_ratio = threshold / 100.0
                if target_ratio < 1.0:
                    needed = (target_ratio * held - att) / (1.0 - target_ratio)
                    classes_needed = max(1, int(needed + 0.999))

            # Calculate safe bunks possible if above threshold
            safe_bunks = 0
            if pct > threshold and held > 0:
                # att / (held + y) >= 0.75
                # att >= 0.75 * held + 0.75 * y
                # 0.75 * y <= att - 0.75 * held
                target_ratio = threshold / 100.0
                safe_bunks = max(0, int((att - target_ratio * held) / target_ratio))

            subj_info = {
                'subject_code': r['subject_code'],
                'subject_name': r['subject_name'],
                'attendance_pct': pct,
                'classes_held': held,
                'classes_attended': att,
                'classes_missed': r['classes_missed'],
                'classes_needed': classes_needed,
                'safe_bunks': safe_bunks
            }

            if pct < threshold:
                critical.append(subj_info)
            elif pct < threshold + 5.0:
                warning.append(subj_info)
            else:
                safe.append(subj_info)

        status = 'CRITICAL' if critical else ('WARNING' if warning else 'HEALTHY')

        if critical:
            rec = f"Action Required: Attendance in {len(critical)} subject(s) is below institutional {threshold}% requirement. Mandatory makeup classes advised."
        elif warning:
            rec = f"Caution: Attendance is within 5% of the {threshold}% minimum threshold. Attend upcoming sessions to avoid debarment."
        else:
            rec = f"Optimal: Attendance is maintained at {overall_pct}%, safely above the {threshold}% institutional requirement."

        return {
            'status': status,
            'overall_pct': overall_pct,
            'total_held': total_held,
            'total_attended': total_att,
            'at_risk_count': len(critical),
            'warning_count': len(warning),
            'critical_subjects': critical,
            'warning_subjects': warning,
            'safe_subjects': safe,
            'recommendation': rec
        }
    finally:
        if close_conn:
            conn.close()


def evaluate_academic_risk(student_id: int, conn=None) -> dict:
    """
    Analyzes marks across CAT1, CAT2, Quizzes, Assignments, and FAT to detect performance trends.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        marks = conn.execute(
            "SELECT * FROM marks WHERE student_id = ?", (student_id,)
        ).fetchall()

        if not marks:
            return {
                'status': 'INSUFFICIENT_DATA',
                'weak_subjects': [],
                'strong_subjects': [],
                'average_score': 0.0,
                'trend': 'STABLE',
                'recommendation': 'No continuous assessment records available yet.'
            }

        total_cat1 = 0
        total_cat2 = 0
        cat_count = 0
        weak = []
        strong = []
        scores = []

        for m in marks:
            cat1 = m['cat1']
            cat2 = m['cat2']
            fat = m['fat']

            if cat1 > 0 and cat2 > 0:
                total_cat1 += cat1
                total_cat2 += cat2
                cat_count += 1

            # Estimate composite normalized score
            comp_score = (cat1 * 0.3) + (cat2 * 0.3) + (m['assignment'] * 0.1) + (m['quiz'] * 0.1) + (m['project'] * 0.2)
            scores.append(comp_score)

            subj_info = {
                'course_code': m['course_code'],
                'course_name': m['course_name'],
                'cat1': cat1,
                'cat2': cat2,
                'fat': fat,
                'grade': m['grade'],
                'status': m['status']
            }

            if m['grade'] in ('D', 'E', 'F') or comp_score < 50:
                weak.append(subj_info)
            elif m['grade'] in ('S', 'A+', 'A') or comp_score >= 80:
                strong.append(subj_info)

        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

        trend = 'STABLE'
        if cat_count > 0:
            if total_cat2 > total_cat1 * 1.05:
                trend = 'IMPROVING'
            elif total_cat2 < total_cat1 * 0.95:
                trend = 'DECLINING'

        status = 'HIGH_RISK' if len(weak) >= 2 else ('MODERATE_RISK' if len(weak) == 1 else 'EXCELLENT')

        if weak:
            rec = f"Targeted Mentoring Advised: Student exhibits academic strain in {', '.join([w['course_code'] for w in weak])}. Remedial tutoring recommended."
        elif trend == 'IMPROVING':
            rec = f"Positive Trajectory: Continuous assessment performance shows marked improvement (+{round((total_cat2 - total_cat1)/cat_count, 1)} pts avg)."
        else:
            rec = f"Consistent Standing: Cumulative performance is steady with an average assessment index of {avg_score}."

        return {
            'status': status,
            'average_score': avg_score,
            'trend': trend,
            'weak_subjects': weak,
            'strong_subjects': strong,
            'recommendation': rec
        }
    finally:
        if close_conn:
            conn.close()


def evaluate_fee_alerts(student_id: int, conn=None) -> dict:
    """
    Checks for outstanding fee dues and calculates urgency.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        fees = conn.execute("SELECT * FROM fees WHERE student_id = ?", (student_id,)).fetchall()
        if not fees:
            return {'has_pending': False, 'total_pending': 0, 'alerts': []}

        pending_items = []
        total_pending = 0.0

        for f in fees:
            due = f['amount'] - f['paid_amount']
            if due > 0 or f['status'].upper() != 'PAID':
                total_pending += due
                pending_items.append({
                    'fee_type': f['fee_type'],
                    'due_amount': due,
                    'due_date': f['due_date'],
                    'status': f['status']
                })

        return {
            'has_pending': total_pending > 0,
            'total_pending': total_pending,
            'pending_count': len(pending_items),
            'items': pending_items
        }
    finally:
        if close_conn:
            conn.close()


def evaluate_exam_reminders(conn=None, days_ahead: int = 14) -> list:
    """
    Identifies upcoming examinations within the given timeframe.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        today = datetime.date.today().strftime('%Y-%m-%d')
        future = (datetime.date.today() + datetime.timedelta(days=days_ahead)).strftime('%Y-%m-%d')
        
        exams = conn.execute("""
            SELECT * FROM examinations 
            WHERE exam_date >= ? AND exam_date <= ?
            ORDER BY exam_date ASC
        """, (today, future)).fetchall()

        return [dict(e) for e in exams]
    finally:
        if close_conn:
            conn.close()


def evaluate_assignment_alerts(conn=None, days_ahead: int = 7) -> list:
    """
    Identifies pending assignments due within the given timeframe.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        today = datetime.date.today().strftime('%Y-%m-%d')
        future = (datetime.date.today() + datetime.timedelta(days=days_ahead)).strftime('%Y-%m-%d')

        assignments = conn.execute("""
            SELECT * FROM assignments 
            WHERE due_date >= ? AND due_date <= ? AND status != 'Evaluated'
            ORDER BY due_date ASC
        """, (today, future)).fetchall()

        return [dict(a) for a in assignments]
    finally:
        if close_conn:
            conn.close()


def generate_student_insights_summary(student_id: int, conn=None) -> dict:
    """
    Synthesizes multi-domain analytics into a unified diagnostic report for students and parents.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        att = evaluate_attendance_risk(student_id, conn)
        acad = evaluate_academic_risk(student_id, conn)
        fees = evaluate_fee_alerts(student_id, conn)
        exams = evaluate_exam_reminders(conn, days_ahead=14)
        assigns = evaluate_assignment_alerts(conn, days_ahead=7)

        # Composite Risk Index (0 - 100, lower is better)
        risk_score = 0
        if att['status'] == 'CRITICAL':
            risk_score += 40
        elif att['status'] == 'WARNING':
            risk_score += 20

        if acad['status'] == 'HIGH_RISK':
            risk_score += 35
        elif acad['status'] == 'MODERATE_RISK':
            risk_score += 15

        if fees['has_pending']:
            risk_score += 15

        risk_score = min(100, risk_score)

        return {
            'student_id': student_id,
            'composite_risk_score': risk_score,
            'risk_tier': 'High Risk' if risk_score >= 50 else ('Moderate Risk' if risk_score >= 25 else 'Low Risk / Healthy'),
            'attendance_summary': att,
            'academic_summary': acad,
            'fee_summary': fees,
            'upcoming_exams_count': len(exams),
            'upcoming_assignments_count': len(assigns),
            'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    finally:
        if close_conn:
            conn.close()


def generate_admin_campus_risk_overview(conn=None) -> dict:
    """
    Provides central administration with high-level institutional risk metrics.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        total_students = conn.execute("SELECT COUNT(*) as cnt FROM students").fetchone()['cnt']
        low_att_students = conn.execute("""
            SELECT COUNT(DISTINCT student_id) as cnt FROM attendance WHERE attendance_pct < 75.0
        """).fetchone()['cnt']

        pending_fees_total = conn.execute("""
            SELECT SUM(amount - paid_amount) as total FROM fees WHERE status != 'PAID'
        """).fetchone()['total'] or 0.0

        active_sos_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM incidents WHERE incident_type = 'EMERGENCY_SOS' AND status = 'ACTIVE'
        """).fetchone()['cnt']

        active_complaints = conn.execute("""
            SELECT COUNT(*) as cnt FROM complaints WHERE status NOT IN ('Resolved', 'Rejected')
        """).fetchone()['cnt']

        return {
            'total_students': total_students,
            'low_attendance_students': low_att_students,
            'attendance_compliance_pct': round(((total_students - low_att_students) / total_students * 100.0), 1) if total_students > 0 else 100.0,
            'pending_fees_total': pending_fees_total,
            'active_sos_count': active_sos_count,
            'active_complaints_count': active_complaints
        }
    finally:
        if close_conn:
            conn.close()
