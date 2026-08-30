"""
CampusGuard AI — Academic Intelligence & Real CGPA Calculation Service
Calculates student CGPA using exact weighted grade points and course credits:
CGPA = Σ(Grade Point × Credit) / Σ(Credits)
Handles missing academic records gracefully by returning None / 'Not available'.
"""

from database.db import get_db_connection

GRADE_POINTS_MAP = {
    'O': 10.0,
    'S': 10.0,
    'A+': 9.0,
    'A': 8.0,
    'B+': 7.0,
    'B': 6.0,
    'C': 5.0,
    'D': 4.0,
    'P': 4.0,
    'F': 0.0,
    'FAIL': 0.0,
    'AB': 0.0,
    'ABSENT': 0.0
}


def calculate_grade_point(grade, total_score=None):
    """
    Returns numerical grade points (0.0 - 10.0) from letter grade or total composite score.
    """
    if isinstance(grade, str) and grade.strip().upper() in GRADE_POINTS_MAP:
        return GRADE_POINTS_MAP[grade.strip().upper()]
    
    if total_score is not None:
        try:
            score = float(total_score)
            if score >= 90: return 10.0
            if score >= 80: return 8.0
            if score >= 70: return 7.0
            if score >= 60: return 6.0
            if score >= 50: return 5.0
            if score >= 40: return 4.0
            return 0.0
        except (ValueError, TypeError):
            pass
            
    return 0.0


def calculate_student_cgpa(conn, student_id):
    """
    Calculates exact CGPA and earned credits directly from the student's real marks
    joined with courses credits catalog.
    
    Formula: CGPA = Σ(Grade Point × Credits) / Σ(Credits)
    
    Returns: (cgpa, earned_credits, total_registered_credits, marks_count)
    - If no academic marks exist: returns (None, 0, 0, 0)
    """
    rows = conn.execute("""
        SELECT m.grade, m.grade_points, m.course_code, m.cat1, m.cat2, m.quiz, m.assignment, m.project, m.fat,
               COALESCE(c.credits, 4) as credits
        FROM marks m
        LEFT JOIN courses c ON m.course_code = c.course_code
        WHERE m.student_id = ?
    """, (student_id,)).fetchall()

    if not rows:
        return None, 0, 0, 0

    weighted_points = 0.0
    total_credits = 0
    earned_credits = 0

    for r in rows:
        credits = int(r['credits']) if r['credits'] else 4
        # Determine grade point
        gp = None
        if r['grade_points'] is not None and r['grade_points'] > 0 and r['grade_points'] <= 10.0:
            gp = float(r['grade_points'])
        else:
            gp = calculate_grade_point(r['grade'])

        weighted_points += (gp * credits)
        total_credits += credits

        grade_upper = str(r['grade']).strip().upper()
        if grade_upper not in ['F', 'FAIL', 'AB', 'ABSENT'] and gp > 0:
            earned_credits += credits

    if total_credits > 0:
        cgpa = round(weighted_points / total_credits, 2)
    else:
        cgpa = None

    return cgpa, earned_credits, total_credits, len(rows)


def sync_student_cgpa(conn, student_id):
    """
    Calculates and updates student's cgpa, sgpa, and earned_credits in the database.
    """
    cgpa, earned_credits, total_credits, count = calculate_student_cgpa(conn, student_id)
    if cgpa is not None:
        conn.execute("""
            UPDATE students 
            SET cgpa = ?, sgpa = ?, earned_credits = ?
            WHERE id = ?
        """, (cgpa, cgpa, earned_credits, student_id))
    else:
        conn.execute("""
            UPDATE students 
            SET cgpa = NULL, sgpa = NULL, earned_credits = 0
            WHERE id = ?
        """, (student_id,))
    return cgpa, earned_credits, count


def get_student_academic_profile(conn, student_id):
    """
    Returns an enriched student academic dictionary with accurate real CGPA.
    """
    cgpa, earned_credits, total_credits, marks_count = calculate_student_cgpa(conn, student_id)
    return {
        'cgpa': cgpa,
        'cgpa_display': f"{cgpa:.2f}" if cgpa is not None else "Not available",
        'sgpa': cgpa,
        'sgpa_display': f"{cgpa:.2f}" if cgpa is not None else "Not available",
        'earned_credits': earned_credits,
        'total_credits': 160,
        'has_records': (cgpa is not None),
        'marks_count': marks_count
    }
