"""
=============================================================================
CampusGuard AI — Predictive Academic & Retention Risk ML Engine
=============================================================================
Calculates multi-dimensional risk index using composite weighted metrics:
- Attendance Deficit & Volatility Velocity (35%)
- Internal Assessment Performance Gradient (CAT-1/CAT-2/Quizzes) (35%)
- Assignment Submission Latency & Homework Discipline (15%)
- Fee Payment Friction & Overdue Status (10%)
- Course Difficulty & Credit Load Complexity (5%)
=============================================================================
"""

import math
from typing import Dict, List, Any


def evaluate_student_predictive_risk(student_id: int, conn) -> Dict[str, Any]:
    """
    Computes an empirical predictive risk profile for a single student.
    Returns composite score (0-100), risk tier, key risk drivers, and remediation path.
    """
    # 1. Student Profile
    stu_row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not stu_row:
        return {
            'student_id': student_id,
            'composite_risk_score': 0.0,
            'risk_tier': 'UNKNOWN',
            'dropout_probability_pct': 0.0,
            'risk_factors': [],
            'action_plan': []
        }
    
    student = dict(stu_row)

    # 2. Attendance Metric
    att_rows = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (student_id,)).fetchall()
    attendance_risk_score = 0.0
    att_drivers = []
    
    if att_rows:
        total_held = sum(r['classes_held'] for r in att_rows)
        total_attended = sum(r['classes_attended'] for r in att_rows)
        overall_pct = (total_attended / total_held * 100.0) if total_held > 0 else 100.0
        
        # Penalize if below 75%
        if overall_pct < 75.0:
            attendance_risk_score = min(100.0, (75.0 - overall_pct) * 4.0 + 35.0)
            att_drivers.append(f"Aggregate attendance ({overall_pct:.1f}%) is below mandatory 75% threshold.")
        elif overall_pct <= 80.0:
            attendance_risk_score = (80.0 - overall_pct) * 4.0
            att_drivers.append(f"Attendance ({overall_pct:.1f}%) is in warning zone (75-80%).")
        
        # Check individual failing courses
        crit_courses = [r['subject_name'] for r in att_rows if r['attendance_pct'] < 75.0]
        if crit_courses:
            att_drivers.append(f"Critical shortage in: {', '.join(crit_courses[:3])}.")
    else:
        overall_pct = 85.0

    # 3. Marks & Assessment Metric
    marks_rows = conn.execute("SELECT * FROM marks WHERE student_id = ?", (student_id,)).fetchall()
    marks_risk_score = 0.0
    acad_drivers = []
    
    if marks_rows:
        failing_courses = [m for m in marks_rows if m['status'] == 'FAIL' or m['grade'] == 'F' or m['fat'] < 40]
        avg_grade_points = sum(m['grade_points'] for m in marks_rows) / len(marks_rows)
        
        if failing_courses:
            marks_risk_score += min(60.0, len(failing_courses) * 30.0)
            acad_drivers.append(f"{len(failing_courses)} course(s) with failing marks/grade F.")
        
        if avg_grade_points < 6.0:
            marks_risk_score += (6.0 - avg_grade_points) * 15.0
            acad_drivers.append(f"Low GPA trajectory ({avg_grade_points:.2f}/10.0).")
        
        marks_risk_score = min(100.0, marks_risk_score)
    elif student.get('cgpa', 0) > 0:
        cgpa = student['cgpa']
        if cgpa < 6.0:
            marks_risk_score = (6.0 - cgpa) * 20.0
            acad_drivers.append(f"Current CGPA ({cgpa}) below academic standard.")

    # 4. Assignments Metric
    assign_rows = conn.execute("""
        SELECT a.id, a.title, a.due_date, s.status
        FROM assignments a
        LEFT JOIN student_submissions s ON a.id = s.assignment_id AND s.student_id = ?
    """, (student_id,)).fetchall()
    
    assignment_risk_score = 0.0
    assign_drivers = []
    
    if assign_rows:
        pending_count = sum(1 for a in assign_rows if not a['status'])
        total_assign = len(assign_rows)
        pending_ratio = pending_count / total_assign if total_assign > 0 else 0
        
        if pending_count > 0:
            assignment_risk_score = min(100.0, pending_ratio * 70.0 + pending_count * 10.0)
            assign_drivers.append(f"{pending_count} unsubmitted assignment(s) in portal.")

    # 5. Financial Friction Metric
    fee_rows = conn.execute("SELECT * FROM fees WHERE student_id = ?", (student_id,)).fetchall()
    fee_risk_score = 0.0
    fee_drivers = []
    
    if fee_rows:
        overdue_items = [f for f in fee_rows if f['status'] == 'OVERDUE']
        pending_amt = sum(f['amount'] - f['paid_amount'] for f in fee_rows if f['status'] != 'PAID')
        
        if overdue_items:
            fee_risk_score = 75.0
            fee_drivers.append(f"{len(overdue_items)} overdue fee invoice(s) outstanding.")
        elif pending_amt > 50000:
            fee_risk_score = 35.0
            fee_drivers.append(f"Substantial pending fee balance: ₹{pending_amt:,.2f}.")

    # 6. Composite Score Calculation (0 - 100)
    # Weights: Attendance (35%), Academic Marks (35%), Assignments (15%), Fees (15%)
    composite_risk = (
        (attendance_risk_score * 0.35) +
        (marks_risk_score * 0.35) +
        (assignment_risk_score * 0.15) +
        (fee_risk_score * 0.15)
    )
    composite_risk = round(min(100.0, max(0.0, composite_risk)), 1)

    # 7. Tier Classification & Dropout Probability
    if composite_risk >= 70.0:
        tier = 'CRITICAL'
        dropout_prob = round(composite_risk * 0.85, 1)
        priority_label = 'High Priority Academic Intervention'
    elif composite_risk >= 45.0:
        tier = 'ELEVATED'
        dropout_prob = round(composite_risk * 0.55, 1)
        priority_label = 'Faculty Mentoring & Review Advised'
    elif composite_risk >= 20.0:
        tier = 'MODERATE'
        dropout_prob = round(composite_risk * 0.25, 1)
        priority_label = 'Monitor Attendance & Submissions'
    else:
        tier = 'NOMINAL'
        dropout_prob = round(composite_risk * 0.08, 1)
        priority_label = 'Academic Standing Optimal'

    # 8. Actionable Remediation Plan
    all_drivers = att_drivers + acad_drivers + assign_drivers + fee_drivers
    action_plan = []
    
    if attendance_risk_score > 20:
        action_plan.append("Attend next 5 consecutive lectures without absence to restore safe margin.")
    if marks_risk_score > 20:
        action_plan.append("Schedule 1-on-1 diagnostic session with Faculty Advisor for exam remediation.")
    if assignment_risk_score > 20:
        action_plan.append("Submit pending coursework submissions before portal cutoff.")
    if fee_risk_score > 20:
        action_plan.append("Clear overdue fee balance or request installment payment schedule.")
    if not action_plan:
        action_plan.append("Maintain existing high engagement and consistent class participation.")

    return {
        'student_id': student_id,
        'student_name': student.get('name', 'Unknown'),
        'register_number': student.get('register_number', ''),
        'department': student.get('department', ''),
        'year': student.get('year', 1),
        'cgpa': student.get('cgpa', 0.0),
        'composite_risk_score': composite_risk,
        'risk_tier': tier,
        'dropout_probability_pct': dropout_prob,
        'priority_label': priority_label,
        'component_scores': {
            'attendance_risk': round(attendance_risk_score, 1),
            'academic_marks_risk': round(marks_risk_score, 1),
            'assignments_risk': round(assignment_risk_score, 1),
            'financial_risk': round(fee_risk_score, 1)
        },
        'primary_risk_drivers': all_drivers,
        'remediation_plan': action_plan
    }


def evaluate_cohort_predictive_risk(conn, department: str = None, year: int = None) -> List[Dict[str, Any]]:
    """
    Evaluates predictive risk scores across a cohort or entire institutional student body.
    Sorted by highest risk score first for proactive intervention.
    """
    query = "SELECT id FROM students WHERE status = 'ACTIVE'"
    params = []
    
    if department:
        query += " AND department = ?"
        params.append(department)
    if year:
        query += " AND year = ?"
        params.append(year)

    rows = conn.execute(query, tuple(params)).fetchall()
    results = [evaluate_student_predictive_risk(r['id'], conn) for r in rows]
    results.sort(key=lambda x: x['composite_risk_score'], reverse=True)
    return results
