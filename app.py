"""
=============================================================================
CampusGuard AI - AI-Powered Smart College ERP & Campus Safety Platform
Main Application Server (Flask)
=============================================================================
Comprehensive Academic Management, Fee Payments, Examinations, Timetable,
Hostel & Transport, Placements with AI Resume Analysis, Service Requests,
Campus Safety with Live SOS Dispatch, Safe Route Navigation, Safe Walk,
and Enterprise AI Safety Intelligence Engine.
=============================================================================
"""

import os
import json
import sqlite3
import datetime
from datetime import timedelta
from functools import wraps
from flask import (
    Flask,
    render_template,
    render_template_string,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    g
)
from werkzeug.security import generate_password_hash, check_password_hash

# Modular AI Services
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
from services.campus_assistant import answer_campus_query
from services.briefing_ai import generate_student_briefing

# ---------------------------------------------------------------------------
# Flask App Configuration
# ---------------------------------------------------------------------------
app = Flask(__name__)

# Secret key used to cryptographically sign session cookies
app.secret_key = os.environ.get(
    'CAMPUSGUARD_SECRET_KEY', 
    'campusguard-ai-secure-secret-key-2026-smart-safe-campus'
)

# Session lifetime configuration (7 days persistence when "Remember Me" is checked)
app.permanent_session_lifetime = timedelta(days=7)

# SQLite database file path
DATABASE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')


# ---------------------------------------------------------------------------
# Database Helper Functions & Full Schema Initialization
# ---------------------------------------------------------------------------
def get_db_connection():
    """
    Establishes and returns a connection to the SQLite database.
    Row factory is set to sqlite3.Row so columns can be accessed by name.
    """
    conn = sqlite3.connect(DATABASE_FILE, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Initializes the complete enterprise SQLite database schema and seeds sample
    academic, life, and safety data for demo student STU001.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Students Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            register_number TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            department TEXT NOT NULL,
            year INTEGER NOT NULL,
            program TEXT DEFAULT 'B.Tech',
            semester INTEGER DEFAULT 5,
            section TEXT DEFAULT 'A',
            phone TEXT DEFAULT '+91 98765 43210',
            dob TEXT DEFAULT '2004-05-14',
            address TEXT DEFAULT '#42, Green Avenue, Tech City, Karnataka 560001',
            parent_name TEXT DEFAULT 'R. S. Kumar',
            parent_phone TEXT DEFAULT '+91 94440 12345',
            join_date TEXT DEFAULT '2023-08-01',
            cgpa REAL DEFAULT 8.75,
            sgpa REAL DEFAULT 8.90,
            earned_credits INTEGER DEFAULT 112,
            total_credits INTEGER DEFAULT 160,
            profile_image TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Column migrations for existing tables
    existing_cols = set()
    for row in cursor.execute("PRAGMA table_info(students)").fetchall():
        try:
            existing_cols.add(row['name'])
        except Exception:
            existing_cols.add(row[1])

    cols_to_add = {
        'program': "TEXT DEFAULT 'B.Tech'",
        'semester': "INTEGER DEFAULT 5",
        'section': "TEXT DEFAULT 'A'",
        'phone': "TEXT DEFAULT '+91 98765 43210'",
        'dob': "TEXT DEFAULT '2004-05-14'",
        'address': "TEXT DEFAULT '#42, Green Avenue, Tech City, Karnataka 560001'",
        'parent_name': "TEXT DEFAULT 'R. S. Kumar'",
        'parent_phone': "TEXT DEFAULT '+91 94440 12345'",
        'join_date': "TEXT DEFAULT '2023-08-01'",
        'cgpa': "REAL DEFAULT 8.75",
        'sgpa': "REAL DEFAULT 8.90",
        'earned_credits': "INTEGER DEFAULT 112",
        'total_credits': "INTEGER DEFAULT 160"
    }
    for col, definition in cols_to_add.items():
        if col not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE students ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass

    # 2. Courses Catalog Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT UNIQUE NOT NULL,
            course_name TEXT NOT NULL,
            department TEXT NOT NULL,
            semester INTEGER NOT NULL,
            credits INTEGER NOT NULL,
            faculty_name TEXT NOT NULL,
            course_type TEXT NOT NULL,
            room_number TEXT NOT NULL,
            timing TEXT NOT NULL
        );
    """)

    # 3. Marks & Assessment Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_code TEXT NOT NULL,
            course_name TEXT NOT NULL,
            cat1 REAL NOT NULL,
            cat2 REAL NOT NULL,
            quiz REAL NOT NULL,
            assignment REAL NOT NULL,
            project REAL NOT NULL,
            fat REAL NOT NULL,
            grade TEXT NOT NULL,
            grade_points REAL NOT NULL,
            status TEXT DEFAULT 'PASS',
            FOREIGN KEY (student_id) REFERENCES students (id)
        );
    """)

    # 4. Attendance Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_code TEXT NOT NULL,
            subject_name TEXT NOT NULL,
            classes_held INTEGER NOT NULL,
            classes_attended INTEGER NOT NULL,
            classes_missed INTEGER NOT NULL,
            attendance_pct REAL NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (id)
        );
    """)

    # 5. Date-wise Attendance Logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_code TEXT NOT NULL,
            course_name TEXT NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL,
            topic TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (id)
        );
    """)

    # 6. Timetable Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT NOT NULL,
            year INTEGER NOT NULL,
            day_of_week TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            subject_code TEXT NOT NULL,
            subject_name TEXT NOT NULL,
            faculty_name TEXT NOT NULL,
            room_number TEXT NOT NULL
        );
    """)

    # 7. Assignments & Coursework Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            faculty_name TEXT NOT NULL,
            due_date TEXT NOT NULL,
            max_marks INTEGER DEFAULT 50,
            status TEXT DEFAULT 'Pending',
            marks_obtained INTEGER,
            feedback TEXT DEFAULT ''
        );
    """)

    # 8. Study Materials Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT NOT NULL,
            title TEXT NOT NULL,
            material_type TEXT NOT NULL,
            uploaded_date TEXT NOT NULL
        );
    """)

    # 9. Examinations Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS examinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_type TEXT NOT NULL,
            course_code TEXT NOT NULL,
            course_name TEXT NOT NULL,
            exam_date TEXT NOT NULL,
            exam_time TEXT NOT NULL,
            venue TEXT NOT NULL,
            room_number TEXT NOT NULL,
            seat_number TEXT NOT NULL
        );
    """)

    # 10. Fees Ledger Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            fee_type TEXT NOT NULL,
            amount REAL NOT NULL,
            paid_amount REAL NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (id)
        );
    """)

    # 11. Payment Transactions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT UNIQUE NOT NULL,
            student_id INTEGER NOT NULL,
            fee_type TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            receipt_no TEXT NOT NULL,
            paid_at TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (id)
        );
    """)

    # 12. Messages Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            sender_name TEXT NOT NULL,
            receiver_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            content TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id)
        );
    """)

    # 13. Hostel Details & Leave Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hostel_details (
            student_id INTEGER PRIMARY KEY,
            block_name TEXT NOT NULL,
            room_no TEXT NOT NULL,
            bed_no TEXT NOT NULL,
            warden_name TEXT NOT NULL,
            warden_phone TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hostel_leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            leave_type TEXT NOT NULL,
            from_date TEXT NOT NULL,
            to_date TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id)
        );
    """)

    # 14. Placements Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS placements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            role_title TEXT NOT NULL,
            package_lpa REAL NOT NULL,
            min_cgpa REAL NOT NULL,
            job_type TEXT NOT NULL,
            deadline TEXT NOT NULL,
            location TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE'
        );
    """)

    # 15. Student Requests Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            request_type TEXT NOT NULL,
            details TEXT NOT NULL,
            status TEXT DEFAULT 'Submitted',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id)
        );
    """)

    # 16. Lost & Found Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lost_found (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            item_type TEXT NOT NULL,
            item_name TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            contact_phone TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE',
            reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id)
        );
    """)

    # 17. Wellbeing Appointments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wellbeing_appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            counselor_name TEXT NOT NULL,
            slot_time TEXT NOT NULL,
            concerns TEXT DEFAULT '',
            status TEXT DEFAULT 'CONFIRMED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id)
        );
    """)

    # 18. Safe Walk Sessions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS safe_walk_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            start_location TEXT NOT NULL,
            destination TEXT NOT NULL,
            expected_arrival TEXT NOT NULL,
            status TEXT DEFAULT 'IN_PROGRESS',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id)
        );
    """)

    # 19. Login Attempts Security Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            register_number TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 0
        );
    """)

    # 20. Complaints Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT UNIQUE NOT NULL,
            student_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Submitted',
            ai_category TEXT,
            ai_severity TEXT,
            ai_priority TEXT,
            ai_dept TEXT,
            ai_action TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id)
        );
    """)

    # 21. Alerts Table & Reads
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_alert_reads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            alert_id INTEGER NOT NULL,
            read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, alert_id),
            FOREIGN KEY (student_id) REFERENCES students (id),
            FOREIGN KEY (alert_id) REFERENCES alerts (id)
        );
    """)

    # 22. Incidents Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT UNIQUE NOT NULL,
            student_id INTEGER NOT NULL,
            incident_type TEXT NOT NULL,
            location TEXT,
            latitude REAL,
            longitude REAL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            assigned_to TEXT DEFAULT 'Unassigned',
            priority_score INTEGER DEFAULT 50,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id)
        );
    """)

    # Column migrations for incidents table
    existing_inc_cols = set()
    for row in cursor.execute("PRAGMA table_info(incidents)").fetchall():
        try:
            existing_inc_cols.add(row['name'])
        except Exception:
            existing_inc_cols.add(row[1])

    inc_cols_to_add = {
        'assigned_to': "TEXT DEFAULT 'Unassigned'",
        'priority_score': "INTEGER DEFAULT 50"
    }
    for col, definition in inc_cols_to_add.items():
        if col not in existing_inc_cols:
            try:
                cursor.execute(f"ALTER TABLE incidents ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass

    # 23. Emergency Contacts Directory
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            role_title TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            location TEXT NOT NULL,
            icon TEXT NOT NULL,
            available_hours TEXT NOT NULL
        );
    """)

    # 24. Student Settings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_settings (
            student_id INTEGER PRIMARY KEY,
            email_alerts INTEGER DEFAULT 1,
            sms_alerts INTEGER DEFAULT 1,
            emergency_broadcasts INTEGER DEFAULT 1,
            theme TEXT DEFAULT 'dark',
            FOREIGN KEY (student_id) REFERENCES students (id)
        );
    """)

    # -----------------------------------------------------------------------
    # Seed DEMO Student Account: STU001
    # -----------------------------------------------------------------------
    cursor.execute("SELECT id FROM students WHERE register_number = ?", ('STU001',))
    demo_student = cursor.fetchone()

    if not demo_student:
        demo_password_hash = generate_password_hash('Student@123')
        cursor.execute("""
            INSERT INTO students (
                name, register_number, email, password_hash, department, year,
                program, semester, section, phone, dob, address, parent_name,
                parent_phone, join_date, cgpa, sgpa, earned_credits, total_credits
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'Nithish Kumar', 'STU001', 'student@example.com', demo_password_hash,
            'Computer Science', 3, 'B.Tech', 5, 'A', '+91 98765 43210',
            '2004-05-14', '#42, Green Avenue, Tech City, Karnataka 560001',
            'R. S. Kumar', '+91 94440 12345', '2023-08-01', 8.75, 8.90, 112, 160
        ))
        student_id = cursor.lastrowid
        print("[Database] Seeded DEMO student account: STU001 (Password: Student@123)")
    else:
        student_id = demo_student['id']
        cursor.execute("""
            UPDATE students SET name = 'Nithish Kumar', email = 'student@example.com'
            WHERE id = ?
        """, (student_id,))

    # -----------------------------------------------------------------------
    # Seed Courses
    # -----------------------------------------------------------------------
    cursor.execute("SELECT COUNT(*) as cnt FROM courses")
    if cursor.fetchone()['cnt'] == 0:
        course_records = [
            ('CS301', 'Database Management Systems', 'Computer Science', 5, 4, 'Dr. Ramesh Rao', 'Core Theory', 'CS-201', 'Mon, Wed 09:00 AM'),
            ('CS302', 'Operating Systems & Architecture', 'Computer Science', 5, 4, 'Prof. Kavita Nair', 'Core Theory', 'CS-302', 'Mon, Thu 11:00 AM'),
            ('CS303', 'Data Science & Machine Learning', 'Computer Science', 5, 4, 'Dr. Alan Turing', 'Core Theory + Lab', 'CS-Lab 3', 'Mon, Wed 02:00 PM'),
            ('CS304', 'Computer Networks & Cyber Security', 'Computer Science', 5, 4, 'Prof. David John', 'Core Theory', 'CS-201', 'Tue, Thu 09:00 AM'),
            ('CS305', 'Software Engineering & Agile ERP', 'Computer Science', 5, 4, 'Dr. Priya Sen', 'Core Theory', 'CS-204', 'Tue, Fri 11:00 AM'),
            ('CS306', 'Campus Cyber Safety & Ethics', 'Computer Science', 5, 2, 'Dean Office', 'Institutional Mandatory', 'Seminar Hall 1', 'Fri 11:00 AM'),
            ('CS301L', 'DBMS Laboratory Work', 'Computer Science', 5, 2, 'Dr. Ramesh Rao', 'Practical Lab', 'CS-Lab 1', 'Wed 09:00 AM')
        ]
        cursor.executemany("""
            INSERT INTO courses (
                course_code, course_name, department, semester, credits, faculty_name, course_type, room_number, timing
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, course_records)

    # -----------------------------------------------------------------------
    # Seed Marks
    # -----------------------------------------------------------------------
    cursor.execute("SELECT COUNT(*) as cnt FROM marks WHERE student_id = ?", (student_id,))
    if cursor.fetchone()['cnt'] == 0:
        marks_records = [
            (student_id, 'CS301', 'Database Management Systems', 46.5, 48.0, 9.5, 9.5, 19.0, 92.0, 'S', 10.0, 'PASS'),
            (student_id, 'CS302', 'Operating Systems & Architecture', 42.0, 44.5, 9.0, 9.0, 18.0, 86.0, 'A+', 9.0, 'PASS'),
            (student_id, 'CS303', 'Data Science & Machine Learning', 38.0, 39.5, 8.5, 8.0, 16.5, 78.0, 'A', 8.0, 'PASS'),
            (student_id, 'CS304', 'Computer Networks & Cyber Security', 48.0, 49.0, 10.0, 9.5, 19.5, 95.0, 'S', 10.0, 'PASS'),
            (student_id, 'CS305', 'Software Engineering & Agile ERP', 45.0, 46.5, 9.0, 9.0, 18.5, 89.0, 'A+', 9.0, 'PASS')
        ]
        cursor.executemany("""
            INSERT INTO marks (
                student_id, course_code, course_name, cat1, cat2, quiz, assignment, project, fat, grade, grade_points, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, marks_records)

    # -----------------------------------------------------------------------
    # Seed Attendance & Logs
    # -----------------------------------------------------------------------
    cursor.execute("SELECT COUNT(*) as cnt FROM attendance WHERE student_id = ?", (student_id,))
    if cursor.fetchone()['cnt'] == 0:
        attendance_records = [
            (student_id, 'CS301', 'Database Management Systems', 40, 37, 3, 92.5),
            (student_id, 'CS302', 'Operating Systems & Architecture', 38, 32, 6, 84.2),
            (student_id, 'CS303', 'Data Science & Machine Learning', 35, 27, 8, 77.1),
            (student_id, 'CS304', 'Computer Networks & Cyber Security', 42, 40, 2, 95.2),
            (student_id, 'CS305', 'Software Engineering & Agile ERP', 36, 33, 3, 91.7)
        ]
        cursor.executemany("""
            INSERT INTO attendance (
                student_id, subject_code, subject_name, classes_held, classes_attended, classes_missed, attendance_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, attendance_records)

    cursor.execute("SELECT COUNT(*) as cnt FROM attendance_logs WHERE student_id = ?", (student_id,))
    if cursor.fetchone()['cnt'] == 0:
        logs = [
            (student_id, 'CS301', 'Database Management Systems', '2026-08-20', 'Present', 'B+ Tree Indexing & Query Optimization'),
            (student_id, 'CS302', 'Operating Systems & Architecture', '2026-08-20', 'Present', 'Deadlock Detection & Bankers Algorithm'),
            (student_id, 'CS303', 'Data Science & Machine Learning', '2026-08-19', 'Absent', 'Convolutional Neural Networks & Backprop'),
            (student_id, 'CS304', 'Computer Networks & Cyber Security', '2026-08-19', 'Present', 'TLS 1.3 Handshake & Asymmetric RSA'),
            (student_id, 'CS305', 'Software Engineering & Agile ERP', '2026-08-18', 'Present', 'Sprint Retrospectives & CI/CD Pipelines'),
            (student_id, 'CS301', 'Database Management Systems', '2026-08-18', 'Present', 'ACID Transactions & 2-Phase Locking')
        ]
        cursor.executemany("""
            INSERT INTO attendance_logs (student_id, course_code, course_name, date, status, topic)
            VALUES (?, ?, ?, ?, ?, ?)
        """, logs)

    # -----------------------------------------------------------------------
    # Seed Timetable
    # -----------------------------------------------------------------------
    cursor.execute("SELECT COUNT(*) as cnt FROM timetable WHERE department = 'Computer Science' AND year = 3")
    if cursor.fetchone()['cnt'] == 0:
        timetable_records = [
            ('Computer Science', 3, 'Monday', '09:00 AM', '10:30 AM', 'CS301', 'Database Management Systems', 'Dr. Ramesh Rao', 'CS-201'),
            ('Computer Science', 3, 'Monday', '11:00 AM', '12:30 PM', 'CS302', 'Operating Systems', 'Prof. Kavita Nair', 'CS-302'),
            ('Computer Science', 3, 'Monday', '02:00 PM', '03:30 PM', 'CS303', 'Data Science & Machine Learning', 'Dr. Alan Turing', 'CS-Lab 3'),
            ('Computer Science', 3, 'Tuesday', '09:00 AM', '10:30 AM', 'CS304', 'Computer Networks & Security', 'Prof. David John', 'CS-201'),
            ('Computer Science', 3, 'Tuesday', '11:00 AM', '12:30 PM', 'CS305', 'Software Engineering', 'Dr. Priya Sen', 'CS-204'),
            ('Computer Science', 3, 'Wednesday', '09:00 AM', '11:00 AM', 'CS301L', 'DBMS Laboratory', 'Dr. Ramesh Rao', 'CS-Lab 1'),
            ('Computer Science', 3, 'Wednesday', '11:30 AM', '01:00 PM', 'CS303', 'Data Science', 'Dr. Alan Turing', 'CS-302'),
            ('Computer Science', 3, 'Thursday', '10:00 AM', '11:30 AM', 'CS302', 'Operating Systems', 'Prof. Kavita Nair', 'CS-302'),
            ('Computer Science', 3, 'Thursday', '01:30 PM', '03:00 PM', 'CS304', 'Computer Networks', 'Prof. David John', 'CS-201'),
            ('Computer Science', 3, 'Friday', '09:00 AM', '10:30 AM', 'CS305', 'Software Engineering', 'Dr. Priya Sen', 'CS-204'),
            ('Computer Science', 3, 'Friday', '11:00 AM', '12:30 PM', 'CS306', 'Campus Cyber Safety & Ethics', 'Dean Office', 'Seminar Hall 1'),
            ('Computer Science', 3, 'Saturday', '09:30 AM', '11:00 AM', 'CS308', 'AI Research Colloquium', 'Dr. Alan Turing', 'Seminar Hall 2')
        ]
        cursor.executemany("""
            INSERT INTO timetable (
                department, year, day_of_week, start_time, end_time, subject_code, subject_name, faculty_name, room_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, timetable_records)

    # -----------------------------------------------------------------------
    # Seed Comprehensive Realistic Historical Incidents (Multi-Zone & Temporal)
    # -----------------------------------------------------------------------
    cursor.execute("SELECT COUNT(*) as cnt FROM incidents")
    if cursor.fetchone()['cnt'] == 0:
        historical_incidents = [
            # Parking Area Hotspot (Concentrated Evening Reports)
            ('INC-101', student_id, 'Poor Lighting', 'Parking Area', 12.9712, 77.5941, 'Broken halogen lamp near vehicle bay with pitch dark walking alley', 'RESOLVED', 'Officer R. Singh', 65, '2026-08-10 19:15:00'),
            ('INC-102', student_id, 'Suspicious Activity', 'Parking Area', 12.9714, 77.5943, 'Unidentified persons hanging around two-wheeler parking after sunset', 'RESOLVED', 'Officer R. Singh', 75, '2026-08-11 19:45:00'),
            ('INC-103', student_id, 'Harassment', 'Parking Area', 12.9715, 77.5944, 'Catcalling reported near parking exit ramp between 8 PM and 8:30 PM', 'RESOLVED', 'Inspector V. Nair', 88, '2026-08-12 20:10:00'),
            ('INC-104', student_id, 'Vehicle Scratch', 'Parking Area', 12.9713, 77.5942, 'Vehicle scratched near rear row under non-functioning CCTV camera', 'RESOLVED', 'Officer M. Khan', 55, '2026-08-14 18:30:00'),
            ('INC-105', student_id, 'Theft Attempt', 'Parking Area', 12.9711, 77.5940, 'Helmet and accessories taken from bike rack', 'RESOLVED', 'Officer M. Khan', 70, '2026-08-16 20:00:00'),
            ('INC-109', student_id, 'Stalking Concern', 'Parking Area', 12.9716, 77.5945, 'Student followed from parking bay to library corridor', 'RESOLVED', 'Inspector V. Nair', 85, '2026-08-19 20:20:00'),

            # Hostel Block B (Surging Reports & Lighting Pattern)
            ('INC-106', student_id, 'Water Leakage', 'Hostel Block B (Oak Wing)', 12.9720, 77.5950, 'Pipe burst and puddle hazard near Block B gate entrance', 'RESOLVED', 'Warden Prabhakar', 45, '2026-08-15 14:00:00'),
            ('INC-107', student_id, 'Broken Lamp', 'Hostel Block B (Oak Wing)', 12.9721, 77.5951, 'Flickering street lamp causing blind spot on pathway', 'RESOLVED', 'Maint. Team #3', 55, '2026-08-17 21:30:00'),
            ('INC-110', student_id, 'Suspicious Person', 'Hostel Block B (Oak Wing)', 12.9722, 77.5952, 'Trespassing individual spotted near ground floor window', 'RESOLVED', 'Officer R. Singh', 80, '2026-08-18 22:15:00'),
            ('INC-111', student_id, 'Harassment Near Gate', 'Hostel Block B (Oak Wing)', 12.9723, 77.5953, 'Verbal harassment shouted from road perimeter', 'RESOLVED', 'Inspector V. Nair', 85, '2026-08-20 20:45:00'),

            # Other Campus Zones
            ('INC-108', student_id, 'Broken Bench', 'Central University Library', 12.9730, 77.5960, 'Damaged chair on reading floor with protruding metal screw', 'RESOLVED', 'Library Staff', 25, '2026-08-18 11:00:00'),
            ('INC-112', student_id, 'Open Electrical Wire', 'Academic Block A (CS Dept)', 12.9740, 77.5970, 'Exposed terminal box near Room 204 during renovation', 'RESOLVED', 'Electrician Desk', 78, '2026-08-17 10:30:00'),
            ('INC-113', student_id, 'Slippery Spill Hazard', 'Campus Dining Hall & Canteen', 12.9725, 77.5955, 'Oil spill near tray return counter causing slip risk', 'RESOLVED', 'Canteen Supervisor', 35, '2026-08-19 13:15:00')
        ]
        cursor.executemany("""
            INSERT INTO incidents (
                incident_id, student_id, incident_type, location, latitude, longitude, description, status, assigned_to, priority_score, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, historical_incidents)

    # -----------------------------------------------------------------------
    # Seed Assignments, Materials, Exams, Fees, Contacts, Alerts
    # -----------------------------------------------------------------------
    cursor.execute("SELECT COUNT(*) as cnt FROM assignments")
    if cursor.fetchone()['cnt'] == 0:
        assign_records = [
            ('CS301', 'Assignment 2: Complex SQL & Relational Algebra', 'Implement nested queries with joins and subqueries on enterprise schema.', 'Dr. Ramesh Rao', '2026-08-28', 50, 'Pending', None, ''),
            ('CS302', 'Mini Project: CPU Scheduling Simulator in C++', 'Simulate Round Robin, FCFS and SJF scheduling algorithms with turnaround graphs.', 'Prof. Kavita Nair', '2026-08-30', 50, 'Pending', None, ''),
            ('CS304', 'Lab Assignment 1: Wireshark Packet Sniffing Analysis', 'Analyze TCP 3-way handshake and SSL certificate inspection logs.', 'Prof. David John', '2026-08-15', 50, 'Evaluated', 48, 'Excellent packet timing dissection.')
        ]
        cursor.executemany("""
            INSERT INTO assignments (
                course_code, title, description, faculty_name, due_date, max_marks, status, marks_obtained, feedback
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, assign_records)

    cursor.execute("SELECT COUNT(*) as cnt FROM study_materials")
    if cursor.fetchone()['cnt'] == 0:
        mat_records = [
            ('CS301', 'Unit 3: Normalization & Functional Dependencies (PDF)', 'Lecture Notes PDF', '2026-08-10'),
            ('CS302', 'Unit 4: Virtual Memory Management & Paging Slides (PPT)', 'Slide Deck', '2026-08-12'),
            ('CS303', 'Deep Learning & Neural Network Foundations Workbook', 'Lab Notebook', '2026-08-15'),
            ('CS304', 'Previous 5 Years Solved Mid-Term Question Papers', 'Exam Archive', '2026-08-01')
        ]
        cursor.executemany("""
            INSERT INTO study_materials (course_code, title, material_type, uploaded_date)
            VALUES (?, ?, ?, ?)
        """, mat_records)

    cursor.execute("SELECT COUNT(*) as cnt FROM examinations")
    if cursor.fetchone()['cnt'] == 0:
        exam_records = [
            ('FAT Semester 5', 'CS301', 'Database Management Systems', '2026-09-10', '09:30 AM - 12:30 PM', 'Academic Block A', 'Exam Hall 3', 'C-14'),
            ('FAT Semester 5', 'CS302', 'Operating Systems & Architecture', '2026-09-12', '09:30 AM - 12:30 PM', 'Academic Block A', 'Exam Hall 3', 'C-14'),
            ('FAT Semester 5', 'CS303', 'Data Science & Machine Learning', '2026-09-15', '09:30 AM - 12:30 PM', 'Academic Block A', 'Exam Hall 3', 'C-14'),
            ('FAT Semester 5', 'CS304', 'Computer Networks & Cyber Security', '2026-09-17', '09:30 AM - 12:30 PM', 'Academic Block A', 'Exam Hall 3', 'C-14'),
            ('FAT Semester 5', 'CS305', 'Software Engineering & Agile ERP', '2026-09-19', '09:30 AM - 12:30 PM', 'Academic Block A', 'Exam Hall 3', 'C-14')
        ]
        cursor.executemany("""
            INSERT INTO examinations (
                exam_type, course_code, course_name, exam_date, exam_time, venue, room_number, seat_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, exam_records)

    cursor.execute("SELECT COUNT(*) as cnt FROM fees WHERE student_id = ?", (student_id,))
    if cursor.fetchone()['cnt'] == 0:
        fee_records = [
            (student_id, 'Tuition & Academic Semester Fee', 125000, 125000, '2026-07-30', 'PAID'),
            (student_id, 'Hostel & Residential Mess Charges', 65000, 65000, '2026-07-30', 'PAID'),
            (student_id, 'Semester 5 Assessment & Examination Fee', 15000, 0, '2026-09-02', 'PENDING')
        ]
        cursor.executemany("""
            INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, fee_records)

    cursor.execute("SELECT student_id FROM hostel_details WHERE student_id = ?", (student_id,))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO hostel_details (student_id, block_name, room_no, bed_no, warden_name, warden_phone)
            VALUES (?, 'Block B (Oak Wing)', '304', 'Bed A', 'Mr. R. Prabhakar', '+91 91234 56784')
        """, (student_id,))

    cursor.execute("SELECT COUNT(*) as cnt FROM placements")
    if cursor.fetchone()['cnt'] == 0:
        placement_records = [
            ('Microsoft India', 'Software Engineering Trainee (SDE-1)', 24.5, 8.0, 'Full-Time Internship + FTE', '2026-09-05', 'Bangalore / Hyderabad', 'ACTIVE'),
            ('Amazon Web Services', 'Cloud Support Associate & DevOps', 18.0, 7.5, 'Full-Time FTE', '2026-09-12', 'Hyderabad', 'ACTIVE'),
            ('Google Cloud', 'Technical Solutions Associate', 22.0, 8.5, 'Full-Time FTE', '2026-09-20', 'Bangalore', 'ACTIVE'),
            ('Cisco Systems', 'Network Security Engineer', 16.5, 7.0, 'Full-Time FTE', '2026-09-25', 'Bangalore', 'ACTIVE')
        ]
        cursor.executemany("""
            INSERT INTO placements (
                company_name, role_title, package_lpa, min_cgpa, job_type, deadline, location, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, placement_records)

    cursor.execute("SELECT COUNT(*) as cnt FROM emergency_contacts")
    if cursor.fetchone()['cnt'] == 0:
        contacts_records = [
            ('Campus Security Command Center', 'Chief Security Officer', '+91 91234 56780', 'Main Security Tower', '🛡️', '24/7 Continuous'),
            ('Emergency Medical Health Center', 'Senior Duty Doctor', '+91 91234 56781', 'Health Pavilion Block A', '🏥', '24/7 Continuous'),
            ("Women's Safety & Anti-Harassment", 'Student Welfare Liaison', '+91 91234 56782', 'Admin Building Room 104', '👩‍✈️', '24/7 Helpline'),
            ('Campus Quick Response Team', 'Patrol Dispatch Lead', '+91 91234 56783', 'Central Gate Station', '🚨', '24/7 Mobile Patrol'),
            ('Hostel Chief Warden', 'Residential Support', '+91 91234 56784', 'Warden Quarters Block B', '🏢', '24/7 On-Campus')
        ]
        cursor.executemany("""
            INSERT INTO emergency_contacts (
                service_name, role_title, phone_number, location, icon, available_hours
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, contacts_records)

    cursor.execute("SELECT COUNT(*) as cnt FROM alerts")
    if cursor.fetchone()['cnt'] == 0:
        alert_records = [
            ('Emergency Notice: Block C Ground Corridor Maintenance', 
             'Avoid Academic Block C ground floor corridor due to scheduled emergency power grid maintenance.', 
             'Emergency', 'Critical'),
            ('Mid-Term Examination Schedule Released', 
             'The official Semester 5 mid-term examination timetable has been published. Check your dates in the academic calendar.', 
             'Announcement', 'High'),
            ('Hostel Block B Facility Maintenance Tonight', 
             'Hostel Block B water pump replacement is scheduled tonight from 11:00 PM to 02:00 AM.', 
             'Maintenance', 'Normal')
        ]
        cursor.executemany("""
            INSERT INTO alerts (title, description, category, priority)
            VALUES (?, ?, ?, ?)
        """, alert_records)

    cursor.execute("SELECT COUNT(*) as cnt FROM messages WHERE student_id = ?", (student_id,))
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute("""
            INSERT INTO messages (student_id, sender_name, receiver_name, subject, content)
            VALUES (?, 'Dr. Ramesh Rao (Faculty Advisor)', 'Nithish Kumar', 
                    'DBMS Capstone Project Review Schedule', 
                    'Hello Nithish, your proposed database architecture design looks solid. Please schedule your Phase 1 demo on Wednesday after lab session.')
        """, (student_id,))

    cursor.execute("SELECT COUNT(*) as cnt FROM student_requests WHERE student_id = ?", (student_id,))
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute("""
            INSERT INTO student_requests (student_id, request_type, details, status)
            VALUES (?, 'Bonafide Certificate', 'Official bonafide verification for Education Loan renewal.', 'Completed')
        """, (student_id,))

    conn.commit()
    conn.close()


# Run initialization on startup
init_db()


# ---------------------------------------------------------------------------
# Cache-Control Header Middleware
# ---------------------------------------------------------------------------
@app.after_request
def add_security_headers(response):
    """
    Prevents browsers from caching protected authentication & dashboard pages.
    """
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# ---------------------------------------------------------------------------
# Reusable Authentication Decorator
# ---------------------------------------------------------------------------
def student_required(f):
    """
    Decorator protecting student routes:
    - Enforces valid student session.
    - Loads student row from SQLite.
    - Redirects to /student/login if unauthenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'student_id' not in session:
            flash("Please log in to access the Student Portal.", "info")
            return redirect(url_for('student_login'))
        
        conn = get_db_connection()
        student = conn.execute(
            "SELECT * FROM students WHERE id = ?",
            (session['student_id'],)
        ).fetchone()
        conn.close()

        if not student:
            session.clear()
            flash("Session expired. Please log in again.", "info")
            return redirect(url_for('student_login'))
        
        g.student = student
        return f(student=student, *args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------------
# Backward Compatibility Wrappers
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
# Public Landing & Auth Routes with Login Security & Anomaly Detection
# ---------------------------------------------------------------------------
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if 'student_id' in session:
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        register_number = request.form.get('register_number', '').strip()
        password = request.form.get('password', '').strip()
        remember_me = bool(request.form.get('remember'))
        ip_addr = request.remote_addr or '127.0.0.1'

        if not register_number or not password:
            return render_template(
                'student/login.html',
                error="Please enter both Register Number and Password.",
                register_number=register_number
            )

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for multiple recent failed attempts (within 15 minutes)
        failed_count = cursor.execute("""
            SELECT COUNT(*) as cnt FROM login_attempts 
            WHERE register_number = ? AND success = 0 AND attempt_time >= datetime('now', '-15 minutes')
        """, (register_number.upper(),)).fetchone()['cnt']

        if failed_count >= 5:
            conn.close()
            return render_template(
                'student/login.html',
                error="⚠️ Multiple failed login attempts detected. Your account has been temporarily protected. Please try again in 15 minutes.",
                register_number=register_number
            )

        try:
            cursor.execute(
                "SELECT * FROM students WHERE UPPER(register_number) = UPPER(?)",
                (register_number,)
            )
            student = cursor.fetchone()

            if student and check_password_hash(student['password_hash'], password):
                # Log successful login
                cursor.execute("""
                    INSERT INTO login_attempts (register_number, ip_address, success)
                    VALUES (?, ?, 1)
                """, (register_number.upper(), ip_addr))
                conn.commit()
                conn.close()

                session.clear()
                session['student_id'] = student['id']
                session['student_register_number'] = student['register_number']
                session['student_name'] = student['name']
                session.permanent = remember_me
                return redirect(url_for('student_dashboard'))
            else:
                # Log failed login attempt
                cursor.execute("""
                    INSERT INTO login_attempts (register_number, ip_address, success)
                    VALUES (?, ?, 0)
                """, (register_number.upper(), ip_addr))
                conn.commit()
                conn.close()

                return render_template(
                    'student/login.html',
                    error="Invalid register number or password.",
                    register_number=register_number
                )
        except Exception as e:
            print(f"[ERROR] Database error during login: {e}")
            if conn: conn.close()
            return render_template(
                'student/login.html',
                error="Something went wrong. Please try again.",
                register_number=register_number
            )

    return render_template('student/login.html')


@app.route('/student/logout')
def student_logout():
    session.clear()
    flash("You have been signed out successfully.", "success")
    return redirect(url_for('student_login'))


# ---------------------------------------------------------------------------
# 1. Student Dashboard (with Dynamic AI Briefing)
# ---------------------------------------------------------------------------
@app.route('/student/dashboard')
@student_required
def student_dashboard(student):
    conn = get_db_connection()
    try:
        briefing = generate_student_briefing(student, conn)
        att_rows = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (student['id'],)).fetchall()
        att_analysis = analyze_student_attendance(att_rows)
        overall_pct = att_analysis['overall_pct']

        today_name = datetime.datetime.now().strftime('%A')
        today_classes = conn.execute("""
            SELECT * FROM timetable WHERE department = ? AND year = ? AND day_of_week = ?
            ORDER BY start_time ASC
        """, (student['department'], student['year'], today_name)).fetchall()
        if not today_classes:
            today_classes = conn.execute("""
                SELECT * FROM timetable WHERE department = ? AND year = ? AND day_of_week = 'Monday'
                ORDER BY start_time ASC
            """, (student['department'], student['year'])).fetchall()

        pending_complaints_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM complaints WHERE student_id = ? AND status != 'Resolved' AND status != 'Rejected'
        """, (student['id'],)).fetchone()['cnt']

        unread_alerts_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM alerts a WHERE a.id NOT IN (
                SELECT alert_id FROM student_alert_reads WHERE student_id = ?
            )
        """, (student['id'],)).fetchone()['cnt']

        active_sos = conn.execute("""
            SELECT * FROM incidents WHERE student_id = ? AND incident_type = 'EMERGENCY_SOS' AND status = 'ACTIVE'
            ORDER BY created_at DESC LIMIT 1
        """, (student['id'],)).fetchone()

        fees = conn.execute("SELECT * FROM fees WHERE student_id = ?", (student['id'],)).fetchall()
        pending_fees_total = sum(f['amount'] - f['paid_amount'] for f in fees)

        return render_template(
            'student/dashboard.html',
            student=student,
            active_page='dashboard',
            briefing=briefing,
            overall_pct=overall_pct,
            today_classes=today_classes,
            pending_complaints_count=pending_complaints_count,
            unread_alerts_count=unread_alerts_count,
            active_sos=active_sos,
            pending_fees_total=pending_fees_total
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 2. My Profile
# ---------------------------------------------------------------------------
@app.route('/student/profile', methods=['GET', 'POST'])
@student_required
def student_profile(student):
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        parent_name = request.form.get('parent_name', '').strip()
        parent_phone = request.form.get('parent_phone', '').strip()
        address = request.form.get('address', '').strip()

        if not name or not email:
            flash("Name and Email are required.", "error")
            return redirect(url_for('student_profile'))

        conn = get_db_connection()
        conn.execute("""
            UPDATE students SET name = ?, email = ?, phone = ?, parent_name = ?, parent_phone = ?, address = ?
            WHERE id = ?
        """, (name, email, phone, parent_name, parent_phone, address, student['id']))
        conn.commit()
        conn.close()

        session['student_name'] = name
        flash("Profile and guardian records updated successfully!", "success")
        return redirect(url_for('student_profile'))

    return render_template('student/profile.html', student=student, active_page='profile')


# ---------------------------------------------------------------------------
# 3. Academics & Marks
# ---------------------------------------------------------------------------
@app.route('/student/academics')
@student_required
def student_academics(student):
    conn = get_db_connection()
    courses = conn.execute("SELECT * FROM courses ORDER BY course_code ASC").fetchall()
    conn.close()
    return render_template('student/academics.html', student=student, courses=courses, active_page='academics')


@app.route('/student/marks')
@student_required
def student_marks(student):
    conn = get_db_connection()
    marks = conn.execute("SELECT * FROM marks WHERE student_id = ?", (student['id'],)).fetchall()
    conn.close()
    return render_template('student/marks.html', student=student, marks=marks, active_page='marks')


# ---------------------------------------------------------------------------
# 4. Attendance (AI Intelligence)
# ---------------------------------------------------------------------------
@app.route('/student/attendance')
@student_required
def student_attendance(student):
    conn = get_db_connection()
    records = conn.execute("SELECT * FROM attendance WHERE student_id = ?", (student['id'],)).fetchall()
    logs = conn.execute("SELECT * FROM attendance_logs WHERE student_id = ? ORDER BY date DESC LIMIT 10", (student['id'],)).fetchall()
    conn.close()

    att_analysis = analyze_student_attendance(records)

    return render_template(
        'student/attendance.html',
        student=student,
        records=records,
        attendance_logs=logs,
        total_held=att_analysis['total_held'],
        total_attended=att_analysis['total_attended'],
        total_missed=att_analysis['total_missed'],
        overall_pct=att_analysis['overall_pct'],
        att_analysis=att_analysis,
        active_page='attendance'
    )


# ---------------------------------------------------------------------------
# 5. Timetable
# ---------------------------------------------------------------------------
@app.route('/student/timetable')
@student_required
def student_timetable(student):
    current_day = datetime.datetime.now().strftime('%A')
    conn = get_db_connection()
    today_classes = conn.execute("""
        SELECT * FROM timetable WHERE department = ? AND year = ? AND day_of_week = ?
        ORDER BY start_time ASC
    """, (student['department'], student['year'], current_day)).fetchall()
    weekly_classes = conn.execute("""
        SELECT * FROM timetable WHERE department = ? AND year = ?
        ORDER BY CASE 
            WHEN day_of_week = 'Monday' THEN 1
            WHEN day_of_week = 'Tuesday' THEN 2
            WHEN day_of_week = 'Wednesday' THEN 3
            WHEN day_of_week = 'Thursday' THEN 4
            WHEN day_of_week = 'Friday' THEN 5
            WHEN day_of_week = 'Saturday' THEN 6
            ELSE 7 END, start_time ASC
    """, (student['department'], student['year'])).fetchall()
    conn.close()

    return render_template(
        'student/timetable.html',
        student=student,
        current_day=current_day,
        today_classes=today_classes,
        weekly_classes=weekly_classes,
        active_page='timetable'
    )


# ---------------------------------------------------------------------------
# 6. Assignments & Materials
# ---------------------------------------------------------------------------
@app.route('/student/assignments', methods=['GET', 'POST'])
@student_required
def student_assignments(student):
    conn = get_db_connection()
    if request.method == 'POST':
        assignment_id = request.form.get('assignment_id')
        file_name = request.form.get('file_name', 'Assignment_Solution.pdf')
        conn.execute("""
            UPDATE assignments 
            SET status = 'Submitted', feedback = 'File received: ' || ?
            WHERE id = ?
        """, (file_name, assignment_id))
        conn.commit()
        flash("Assignment solution submitted successfully!", "success")
        return redirect(url_for('student_assignments'))

    assignments = conn.execute("SELECT * FROM assignments ORDER BY id ASC").fetchall()
    materials = conn.execute("SELECT * FROM study_materials ORDER BY id ASC").fetchall()
    conn.close()
    return render_template('student/assignments.html', student=student, assignments=assignments, study_materials=materials, active_page='assignments')


# ---------------------------------------------------------------------------
# 7. Examinations & Hall Ticket
# ---------------------------------------------------------------------------
@app.route('/student/examinations')
@student_required
def student_examinations(student):
    conn = get_db_connection()
    exams = conn.execute("SELECT * FROM examinations ORDER BY exam_date ASC").fetchall()
    conn.close()
    return render_template('student/examinations.html', student=student, exams=exams, active_page='examinations')


# ---------------------------------------------------------------------------
# 8. Fees & Finance
# ---------------------------------------------------------------------------
@app.route('/student/fees')
@student_required
def student_fees(student):
    conn = get_db_connection()
    fee_items = conn.execute("SELECT * FROM fees WHERE student_id = ?", (student['id'],)).fetchall()
    transactions = conn.execute("SELECT * FROM payment_transactions WHERE student_id = ? ORDER BY id DESC", (student['id'],)).fetchall()
    conn.close()

    total_fee = sum(f['amount'] for f in fee_items)
    total_paid = sum(f['paid_amount'] for f in fee_items)
    total_pending = total_fee - total_paid

    return render_template(
        'student/fees.html',
        student=student,
        fee_items=fee_items,
        transactions=transactions,
        total_fee=total_fee,
        total_paid=total_paid,
        total_pending=total_pending,
        active_page='fees'
    )


@app.route('/student/fees/pay', methods=['POST'])
@student_required
def student_fees_pay(student):
    fee_id = request.form.get('fee_id')
    amount = float(request.form.get('amount', 0))
    payment_method = request.form.get('payment_method', 'UPI')

    conn = get_db_connection()
    fee = conn.execute("SELECT * FROM fees WHERE id = ? AND student_id = ?", (fee_id, student['id'])).fetchone()

    if fee:
        new_paid = fee['paid_amount'] + amount
        new_status = 'PAID' if new_paid >= fee['amount'] else 'PARTIAL'
        conn.execute("UPDATE fees SET paid_amount = ?, status = ? WHERE id = ?", (new_paid, new_status, fee_id))

        tx_id = f"TXN-{int(datetime.datetime.now().timestamp()) % 1000000}"
        rec_no = f"REC-{int(datetime.datetime.now().timestamp()) % 10000}"
        paid_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

        conn.execute("""
            INSERT INTO payment_transactions (transaction_id, student_id, fee_type, amount, payment_method, receipt_no, paid_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tx_id, student['id'], fee['fee_type'], amount, payment_method, rec_no, paid_at))
        conn.commit()

    conn.close()
    flash(f"Payment of ₹{amount} processed successfully. Receipt: #{rec_no}", "success")
    return redirect(url_for('student_fees'))


# ---------------------------------------------------------------------------
# 9. Calendar
# ---------------------------------------------------------------------------
@app.route('/student/calendar')
@student_required
def student_calendar(student):
    events = [
        {'month': 'AUG', 'day': '28', 'title': 'DBMS Assignment 2 Submission', 'category': 'Assignment', 'time': '11:59 PM', 'venue': 'Online Portal', 'description': 'Relational Algebra & SQL Query tasks.'},
        {'month': 'AUG', 'day': '30', 'title': 'OS Mini Project Milestone', 'category': 'Assignment', 'time': '05:00 PM', 'venue': 'CS Lab 3', 'description': 'CPU Scheduling simulation code.'},
        {'month': 'SEP', 'day': '02', 'title': 'Assessment Fee Clearance Deadline', 'category': 'Fee', 'time': '05:00 PM', 'venue': 'Finance Counter / Portal', 'description': 'Semester 5 FAT Examination fee.'},
        {'month': 'SEP', 'day': '10', 'title': 'FAT Exam: Database Systems', 'category': 'Exam', 'time': '09:30 AM', 'venue': 'Exam Hall 3', 'description': 'Final theory comprehensive test.'},
        {'month': 'SEP', 'day': '12', 'title': 'FAT Exam: Operating Systems', 'category': 'Exam', 'time': '09:30 AM', 'venue': 'Exam Hall 3', 'description': 'OS Architecture assessment.'},
        {'month': 'SEP', 'day': '25', 'title': 'Annual Campus Technical Fest', 'category': 'Event', 'time': '09:00 AM', 'venue': 'University Auditorium', 'description': 'Hackathon, Robotics & Paper presentations.'}
    ]
    return render_template('student/calendar.html', student=student, events=events, active_page='calendar')


# ---------------------------------------------------------------------------
# 10. Hostel & Mess
# ---------------------------------------------------------------------------
@app.route('/student/hostel')
@student_required
def student_hostel(student):
    conn = get_db_connection()
    hostel = conn.execute("SELECT * FROM hostel_details WHERE student_id = ?", (student['id'],)).fetchone()
    leaves = conn.execute("SELECT * FROM hostel_leaves WHERE student_id = ? ORDER BY id DESC", (student['id'],)).fetchall()
    conn.close()
    return render_template('student/hostel.html', student=student, hostel=hostel or {}, leaves=leaves, active_page='hostel')


@app.route('/student/hostel/leave', methods=['POST'])
@student_required
def student_hostel_leave(student):
    leave_type = request.form.get('leave_type')
    from_date = request.form.get('from_date')
    to_date = request.form.get('to_date')
    reason = request.form.get('reason')

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO hostel_leaves (student_id, leave_type, from_date, to_date, reason, status)
        VALUES (?, ?, ?, ?, ?, 'Approved')
    """, (student['id'], leave_type, from_date, to_date, reason))
    conn.commit()
    conn.close()

    flash("Digital Outpass / Leave Request approved by Warden.", "success")
    return redirect(url_for('student_hostel'))


# ---------------------------------------------------------------------------
# 11. Transport
# ---------------------------------------------------------------------------
@app.route('/student/transport')
@student_required
def student_transport(student):
    return render_template('student/transport.html', student=student, active_page='transport')


# ---------------------------------------------------------------------------
# 12. Placements & AI Resume
# ---------------------------------------------------------------------------
@app.route('/student/placements')
@student_required
def student_placements(student):
    conn = get_db_connection()
    placements = conn.execute("SELECT * FROM placements WHERE status = 'ACTIVE'").fetchall()
    conn.close()
    return render_template('student/placements.html', student=student, placements=placements, active_page='placements')


@app.route('/student/placements/apply/<int:placement_id>', methods=['POST'])
@student_required
def student_placements_apply(student, placement_id):
    conn = get_db_connection()
    job = conn.execute("SELECT * FROM placements WHERE id = ?", (placement_id,)).fetchone()
    conn.close()
    flash(f"Application successfully submitted to {job['company_name']} for {job['role_title']}!", "success")
    return redirect(url_for('student_placements'))


@app.route('/api/student/ai-resume', methods=['POST'])
def api_student_ai_resume():
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    skills = data.get('skills', '')
    role = data.get('role', 'Software Engineer')
    result = analyze_resume_skills(skills, role)
    return jsonify(result)


# ---------------------------------------------------------------------------
# 13. Requests & Services
# ---------------------------------------------------------------------------
@app.route('/student/requests', methods=['GET', 'POST'])
@student_required
def student_requests(student):
    conn = get_db_connection()
    if request.method == 'POST':
        req_type = request.form.get('request_type')
        details = request.form.get('details')
        conn.execute("""
            INSERT INTO student_requests (student_id, request_type, details, status)
            VALUES (?, ?, ?, 'Under Review')
        """, (student['id'], req_type, details))
        conn.commit()
        flash(f"Service Request for {req_type} submitted to Administrative Office.", "success")
        return redirect(url_for('student_requests'))

    requests_list = conn.execute("SELECT * FROM student_requests WHERE student_id = ? ORDER BY id DESC", (student['id'],)).fetchall()
    conn.close()
    return render_template('student/requests.html', student=student, requests=requests_list, active_page='requests')


# ---------------------------------------------------------------------------
# 14. Lost & Found
# ---------------------------------------------------------------------------
@app.route('/student/lost-found', methods=['GET', 'POST'])
@student_required
def student_lost_found(student):
    conn = get_db_connection()
    if request.method == 'POST':
        item_type = request.form.get('item_type')
        item_name = request.form.get('item_name')
        location = request.form.get('location')
        description = request.form.get('description')
        contact_phone = request.form.get('contact_phone')

        conn.execute("""
            INSERT INTO lost_found (student_id, item_type, item_name, location, description, contact_phone, status)
            VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
        """, (student['id'], item_type, item_name, location, description, contact_phone))
        conn.commit()
        flash(f"{item_type} listing for '{item_name}' published to Campus Board.", "success")
        return redirect(url_for('student_lost_found'))

    items = conn.execute("SELECT * FROM lost_found ORDER BY id DESC").fetchall()
    conn.close()
    return render_template('student/lost_found.html', student=student, items=items, active_page='lost_found')


# ---------------------------------------------------------------------------
# 15. Student Wellbeing
# ---------------------------------------------------------------------------
@app.route('/student/wellbeing')
@student_required
def student_wellbeing(student):
    conn = get_db_connection()
    appts = conn.execute("SELECT * FROM wellbeing_appointments WHERE student_id = ?", (student['id'],)).fetchall()
    conn.close()
    return render_template('student/wellbeing.html', student=student, appointments=appts, active_page='wellbeing')


@app.route('/student/wellbeing/book', methods=['POST'])
@student_required
def student_wellbeing_book(student):
    counselor_name = request.form.get('counselor_name')
    slot_time = request.form.get('slot_time')
    concerns = request.form.get('concerns', '')

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO wellbeing_appointments (student_id, counselor_name, slot_time, concerns, status)
        VALUES (?, ?, ?, ?, 'CONFIRMED')
    """, (student['id'], counselor_name, slot_time, concerns))
    conn.commit()
    conn.close()

    flash(f"Confidential counseling session confirmed with {counselor_name} ({slot_time}).", "success")
    return redirect(url_for('student_wellbeing'))


# ---------------------------------------------------------------------------
# 16. Communication & Faculty Messages
# ---------------------------------------------------------------------------
@app.route('/student/communication', methods=['GET', 'POST'])
@student_required
def student_communication(student):
    conn = get_db_connection()
    if request.method == 'POST':
        receiver = request.form.get('receiver_name')
        subject = request.form.get('subject')
        content = request.form.get('content')

        conn.execute("""
            INSERT INTO messages (student_id, sender_name, receiver_name, subject, content)
            VALUES (?, ?, ?, ?, ?)
        """, (student['id'], student['name'], receiver, subject, content))
        conn.commit()
        flash(f"Message transmitted to {receiver}.", "success")
        return redirect(url_for('student_communication'))

    msgs = conn.execute("SELECT * FROM messages WHERE student_id = ? ORDER BY id DESC", (student['id'],)).fetchall()
    conn.close()
    return render_template('student/communication.html', student=student, messages=msgs, active_page='communication')


# ---------------------------------------------------------------------------
# 17. Safe Walk Companion
# ---------------------------------------------------------------------------
@app.route('/student/safewalk')
@student_required
def student_safewalk(student):
    conn = get_db_connection()
    active_session = conn.execute("""
        SELECT * FROM safe_walk_sessions WHERE student_id = ? AND status = 'IN_PROGRESS'
        ORDER BY created_at DESC LIMIT 1
    """, (student['id'],)).fetchone()

    past_sessions = conn.execute("""
        SELECT * FROM safe_walk_sessions WHERE student_id = ? AND status != 'IN_PROGRESS'
        ORDER BY created_at DESC LIMIT 5
    """, (student['id'],)).fetchall()
    conn.close()

    return render_template(
        'student/safewalk.html',
        student=student,
        active_session=active_session,
        past_sessions=past_sessions,
        active_page='safewalk'
    )


@app.route('/student/safewalk/start', methods=['POST'])
@student_required
def student_safewalk_start(student):
    start_loc = request.form.get('start_location', 'Hostel Block B')
    dest_loc = request.form.get('destination', 'Central Library')
    duration_mins = int(request.form.get('duration_minutes', 15))

    arrival_dt = datetime.datetime.now() + datetime.timedelta(minutes=duration_mins)
    expected_arrival_str = arrival_dt.strftime('%I:%M %p')

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO safe_walk_sessions (student_id, start_location, destination, expected_arrival, status)
        VALUES (?, ?, ?, ?, 'IN_PROGRESS')
    """, (student['id'], start_loc, dest_loc, expected_arrival_str))
    conn.commit()
    conn.close()

    flash(f"Safe Walk session started. Estimated arrival at {dest_loc} by {expected_arrival_str}.", "success")
    return redirect(url_for('student_safewalk'))


@app.route('/student/safewalk/safe/<int:session_id>', methods=['POST'])
@student_required
def student_safewalk_safe(student, session_id):
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db_connection()
    conn.execute("""
        UPDATE safe_walk_sessions SET status = 'COMPLETED', completed_at = ?
        WHERE id = ? AND student_id = ?
    """, (now_str, session_id, student['id']))
    conn.commit()
    conn.close()

    flash("Safe Walk completed! You have checked in safely.", "success")
    return redirect(url_for('student_safewalk'))


@app.route('/student/safewalk/sos/<int:session_id>', methods=['POST'])
@student_required
def student_safewalk_sos(student, session_id):
    conn = get_db_connection()
    sess_row = conn.execute("SELECT * FROM safe_walk_sessions WHERE id = ?", (session_id,)).fetchone()
    loc = f"Safe Walk Corridor ({sess_row['start_location']} to {sess_row['destination']})" if sess_row else "Safe Walk Corridor"

    sos_id = f"EMG-{int(datetime.datetime.now().timestamp()) % 100000}"
    conn.execute("""
        INSERT INTO incidents (incident_id, student_id, incident_type, location, description, status, priority_score)
        VALUES (?, ?, 'EMERGENCY_SOS', ?, 'Safe Walk Distress Triggered', 'ACTIVE', 95)
    """, (sos_id, student['id'], loc))

    conn.execute("UPDATE safe_walk_sessions SET status = 'HELP_REQUESTED' WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

    flash(f"Distress Beacon {sos_id} broadcasted from Safe Walk route!", "error")
    return redirect(url_for('student_emergency'))


# ---------------------------------------------------------------------------
# 18. Campus Safety Map & AI Safe Route
# ---------------------------------------------------------------------------
@app.route('/student/campus-map')
@student_required
def student_campus_map(student):
    conn = get_db_connection()
    incidents = conn.execute("SELECT * FROM incidents").fetchall()
    complaints = conn.execute("SELECT * FROM complaints").fetchall()
    conn.close()

    zone_scores = calculate_location_risk_scores(incidents, complaints)
    return render_template('student/campus_map.html', student=student, zone_scores=zone_scores, zones=CONFIGURED_ZONES, active_page='map')


@app.route('/api/student/safe-route', methods=['POST'])
def api_student_safe_route():
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    from_loc = data.get('from', 'Hostel Block B')
    to_loc = data.get('to', 'Central Library')
    result = calculate_safe_route(from_loc, to_loc)
    return jsonify(result)


# ---------------------------------------------------------------------------
# 19. Campus Safety Center & Complaints (with AI Intelligence)
# ---------------------------------------------------------------------------
@app.route('/student/safety', methods=['GET', 'POST'])
@student_required
def student_safety(student):
    conn = get_db_connection()
    if request.method == 'POST':
        incident_type = request.form.get('incident_type', '').strip()
        location = request.form.get('location', '').strip()
        description = request.form.get('description', '').strip()

        if not incident_type or not location or not description:
            flash("Please fill in all incident report details.", "error")
            return redirect(url_for('student_safety'))

        intel = extract_incident_intelligence(description, location)
        historical = conn.execute("SELECT * FROM incidents").fetchall()
        context_corr = correlate_safety_context({'incident_type': incident_type, 'location': location}, historical)

        incident_id = f"INC-{int(datetime.datetime.now().timestamp()) % 100000}"
        p_score = 75 if intel['severity'] in ['CRITICAL', 'HIGH'] else 45

        conn.execute("""
            INSERT INTO incidents (incident_id, student_id, incident_type, location, description, status, priority_score)
            VALUES (?, ?, ?, ?, ?, 'RECORDED', ?)
        """, (incident_id, student['id'], intel['incident_type'], normalize_zone_name(location), description, p_score))
        conn.commit()
        conn.close()

        flash_msg = f"Safety incident {incident_id} logged ({intel['department']})."
        if context_corr['has_pattern']:
            flash_msg += f" [AI Context: {context_corr['pattern_summary']}]"

        flash(flash_msg, "success")
        return redirect(url_for('student_safety'))

    contacts = conn.execute("SELECT * FROM emergency_contacts").fetchall()
    recent_incidents = conn.execute("""
        SELECT * FROM incidents WHERE student_id = ? AND incident_type != 'EMERGENCY_SOS'
        ORDER BY created_at DESC LIMIT 10
    """, (student['id'],)).fetchall()
    conn.close()

    return render_template('student/safety.html', student=student, contacts=contacts, recent_incidents=recent_incidents, active_page='safety')


@app.route('/student/complaints', methods=['GET', 'POST'])
@student_required
def student_complaints(student):
    conn = get_db_connection()
    if request.method == 'POST':
        category = request.form.get('category', '').strip()
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        priority = request.form.get('priority', 'Medium').strip()

        if not title or not description or not location:
            flash("Please provide a title, location, and description.", "error")
            return redirect(url_for('student_complaints'))

        ai_result = classify_complaint(title, description, category, location)
        complaint_id = f"CMP-{int(datetime.datetime.now().timestamp()) % 100000}"

        conn.execute("""
            INSERT INTO complaints (
                complaint_id, student_id, category, title, description, location, priority,
                status, ai_category, ai_severity, ai_priority, ai_dept, ai_action
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Submitted', ?, ?, ?, ?, ?)
        """, (
            complaint_id, student['id'], category, title, description, normalize_zone_name(location), priority,
            ai_result['category'], ai_result['severity'], ai_result['priority'], ai_result['dept'], ai_result['action']
        ))
        conn.commit()
        conn.close()

        flash(f"Grievance Ticket {complaint_id} filed. AI triaged to {ai_result['dept']}.", "success")
        return redirect(url_for('student_complaints'))

    complaints = conn.execute("SELECT * FROM complaints WHERE student_id = ? ORDER BY created_at DESC", (student['id'],)).fetchall()
    conn.close()
    return render_template('student/complaints.html', student=student, complaints=complaints, active_page='complaints')


# ---------------------------------------------------------------------------
# 20. Emergency SOS
# ---------------------------------------------------------------------------
@app.route('/student/emergency', methods=['GET', 'POST'])
@student_required
def student_emergency(student):
    conn = get_db_connection()
    if request.method == 'POST':
        location = request.form.get('location', 'Campus Perimeter Beacon').strip()
        latitude = request.form.get('latitude') or None
        longitude = request.form.get('longitude') or None
        sos_id = f"EMG-{int(datetime.datetime.now().timestamp()) % 100000}"

        conn.execute("""
            INSERT INTO incidents (
                incident_id, student_id, incident_type, location, latitude, longitude, description, status, priority_score
            ) VALUES (?, ?, 'EMERGENCY_SOS', ?, ?, ?, 'Immediate Student Distress Beacon Activated', 'ACTIVE', 100)
        """, (sos_id, student['id'], normalize_zone_name(location), latitude, longitude))
        conn.commit()
        conn.close()

        flash(f"Distress Beacon {sos_id} broadcasted! QRT Patrol units alerted.", "error")
        return redirect(url_for('student_emergency'))

    active_sos = conn.execute("""
        SELECT * FROM incidents WHERE student_id = ? AND incident_type = 'EMERGENCY_SOS' AND status = 'ACTIVE'
        ORDER BY created_at DESC LIMIT 1
    """, (student['id'],)).fetchone()
    conn.close()
    return render_template('student/emergency.html', student=student, active_sos=active_sos, active_page='emergency')


@app.route('/student/emergency/cancel/<incident_id>', methods=['POST'])
@student_required
def student_emergency_cancel(student, incident_id):
    conn = get_db_connection()
    conn.execute("UPDATE incidents SET status = 'RESOLVED' WHERE incident_id = ? AND student_id = ?", (incident_id, student['id']))
    conn.commit()
    conn.close()
    flash(f"Emergency beacon {incident_id} stood down. Marked safe.", "success")
    return redirect(url_for('student_emergency'))


# ---------------------------------------------------------------------------
# 21. Alerts
# ---------------------------------------------------------------------------
@app.route('/student/alerts')
@student_required
def student_alerts(student):
    conn = get_db_connection()
    alerts = conn.execute("""
        SELECT a.*, CASE WHEN r.id IS NOT NULL THEN 1 ELSE 0 END as is_read
        FROM alerts a
        LEFT JOIN student_alert_reads r ON a.id = r.alert_id AND r.student_id = ?
        ORDER BY a.created_at DESC
    """, (student['id'],)).fetchall()
    unread_count = sum(1 for a in alerts if not a['is_read'])
    conn.close()
    return render_template('student/alerts.html', student=student, alerts=alerts, unread_count=unread_count, active_page='alerts')


@app.route('/student/alerts/read/<int:alert_id>', methods=['POST'])
@student_required
def student_alerts_read_single(student, alert_id):
    conn = get_db_connection()
    conn.execute("INSERT OR IGNORE INTO student_alert_reads (student_id, alert_id) VALUES (?, ?)", (student['id'], alert_id))
    conn.commit()
    conn.close()
    return redirect(url_for('student_alerts'))


@app.route('/student/alerts/read-all', methods=['POST'])
@student_required
def student_alerts_read_all(student):
    conn = get_db_connection()
    conn.execute("INSERT OR IGNORE INTO student_alert_reads (student_id, alert_id) SELECT ?, id FROM alerts", (student['id'],))
    conn.commit()
    conn.close()
    flash("All alerts marked as read.", "success")
    return redirect(url_for('student_alerts'))


# ---------------------------------------------------------------------------
# 22. AI Assistant & Chat API
# ---------------------------------------------------------------------------
@app.route('/student/assistant')
@student_required
def student_assistant(student):
    return render_template('student/assistant.html', student=student, active_page='assistant')


@app.route('/api/student/chat', methods=['POST'])
def api_student_chat():
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'reply': 'Please type a question about your attendance, marks, fees, timetable, or campus safety.'})
    
    conn = get_db_connection()
    try:
        reply = answer_campus_query(session['student_id'], message, conn)
        return jsonify({'reply': reply})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 23. Settings
# ---------------------------------------------------------------------------
@app.route('/student/settings', methods=['GET', 'POST'])
@student_required
def student_settings(student):
    conn = get_db_connection()
    if request.method == 'POST':
        action_type = request.form.get('action_type')

        if action_type == 'preferences':
            email_alerts = 1 if request.form.get('email_alerts') else 0
            emergency_broadcasts = 1 if request.form.get('emergency_broadcasts') else 0
            conn.execute("""
                INSERT INTO student_settings (student_id, email_alerts, emergency_broadcasts)
                VALUES (?, ?, ?)
                ON CONFLICT(student_id) DO UPDATE SET
                    email_alerts = excluded.email_alerts,
                    emergency_broadcasts = excluded.emergency_broadcasts
            """, (student['id'], email_alerts, emergency_broadcasts))
            conn.commit()
            conn.close()
            flash("Notification preferences updated successfully.", "success")
            return redirect(url_for('student_settings'))

        elif action_type == 'password':
            current_pw = request.form.get('current_password', '').strip()
            new_pw = request.form.get('new_password', '').strip()
            confirm_pw = request.form.get('confirm_password', '').strip()

            if not current_pw or not new_pw or not confirm_pw:
                flash("Please fill in all password fields.", "error")
                conn.close()
                return redirect(url_for('student_settings'))

            if not check_password_hash(student['password_hash'], current_pw):
                flash("Current password entered is incorrect.", "error")
                conn.close()
                return redirect(url_for('student_settings'))

            if len(new_pw) < 6:
                flash("New password must be at least 6 characters long.", "error")
                conn.close()
                return redirect(url_for('student_settings'))

            if new_pw != confirm_pw:
                flash("New password and confirmation do not match.", "error")
                conn.close()
                return redirect(url_for('student_settings'))

            new_hash = generate_password_hash(new_pw)
            conn.execute("UPDATE students SET password_hash = ? WHERE id = ?", (new_hash, student['id']))
            conn.commit()
            conn.close()
            flash("Password updated successfully!", "success")
            return redirect(url_for('student_settings'))

    settings = conn.execute("SELECT * FROM student_settings WHERE student_id = ?", (student['id'],)).fetchone()
    conn.close()
    return render_template('student/settings.html', student=student, settings=settings or {'email_alerts': 1, 'emergency_broadcasts': 1}, active_page='settings')


# ---------------------------------------------------------------------------
# Multi-Role: Security Command Console & Zone Intelligence API
# ---------------------------------------------------------------------------
@app.route('/security/dashboard')
def security_dashboard():
    conn = get_db_connection()
    incidents = conn.execute("SELECT * FROM incidents ORDER BY created_at DESC").fetchall()
    complaints = conn.execute("SELECT * FROM complaints ORDER BY created_at DESC").fetchall()

    active_sos_list = conn.execute("""
        SELECT i.*, s.name as student_name, s.register_number, s.phone as student_phone
        FROM incidents i
        JOIN students s ON i.student_id = s.id
        WHERE i.incident_type = 'EMERGENCY_SOS' AND i.status = 'ACTIVE'
        ORDER BY i.created_at DESC
    """).fetchall()

    all_incidents = conn.execute("""
        SELECT i.*, s.name as student_name, s.register_number
        FROM incidents i
        JOIN students s ON i.student_id = s.id
        ORDER BY i.created_at DESC LIMIT 30
    """).fetchall()
    conn.close()

    zone_scores = calculate_location_risk_scores(incidents, complaints)
    briefing = generate_executive_safety_briefing(incidents, complaints, zone_scores)

    # Calculate real priority scores for queue
    ranked_incidents = []
    for inc in all_incidents:
        loc_name = normalize_zone_name(inc['location'])
        z_score = zone_scores.get(loc_name, {}).get('risk_score', 50)
        p_rank = calculate_incident_priority(inc, z_score)
        ranked_incidents.append({
            'item': inc,
            'priority_rank': p_rank,
            'location_risk': z_score,
            'zone_name': loc_name
        })

    # Sort queue: higher priority rank first, then active status
    ranked_incidents.sort(key=lambda x: (x['item']['status'] == 'ACTIVE', x['priority_rank']), reverse=True)

    return render_template(
        'security/dashboard.html',
        active_sos_list=active_sos_list,
        ranked_incidents=ranked_incidents,
        zone_scores=zone_scores,
        zones=CONFIGURED_ZONES,
        briefing=briefing
    )


@app.route('/api/security/zone-intel/<zone_id>')
def api_security_zone_intel(zone_id):
    conn = get_db_connection()
    incidents = conn.execute("SELECT * FROM incidents").fetchall()
    complaints = conn.execute("SELECT * FROM complaints").fetchall()
    conn.close()

    zone_scores = calculate_location_risk_scores(incidents, complaints)
    for name, data in zone_scores.items():
        if data['zone_id'] == zone_id:
            return jsonify(data)
    
    return jsonify({'error': 'Zone not found'}), 404


@app.route('/security/incident/<incident_id>/status', methods=['POST'])
def security_update_incident_status(incident_id):
    new_status = request.form.get('new_status', 'RESOLVED')
    assigned_to = request.form.get('assigned_to', 'QRT Officer On-Duty')

    conn = get_db_connection()
    conn.execute("""
        UPDATE incidents SET status = ?, assigned_to = ?
        WHERE incident_id = ?
    """, (new_status, assigned_to, incident_id))
    conn.commit()
    conn.close()

    flash(f"Incident {incident_id} updated: Status = {new_status}, Assignee = {assigned_to}.", "success")
    return redirect(url_for('security_dashboard'))


# ---------------------------------------------------------------------------
# Multi-Role: Executive Admin AI Analytics Dashboard
# ---------------------------------------------------------------------------
@app.route('/admin/analytics')
def admin_analytics():
    conn = get_db_connection()
    incidents = conn.execute("SELECT * FROM incidents ORDER BY created_at DESC").fetchall()
    complaints = conn.execute("SELECT * FROM complaints ORDER BY created_at DESC").fetchall()
    conn.close()

    zone_scores = calculate_location_risk_scores(incidents, complaints)
    temporal = analyze_temporal_patterns(incidents)
    emerging = detect_emerging_risks(incidents)
    patterns = detect_repeated_patterns(incidents, complaints)
    briefing = generate_executive_safety_briefing(incidents, complaints, zone_scores)

    return render_template(
        'admin/analytics.html',
        zone_scores=zone_scores,
        temporal=temporal,
        emerging=emerging,
        patterns=patterns,
        briefing=briefing
    )


# ---------------------------------------------------------------------------
# Preserved Landing Routes for Faculty and Parents
# ---------------------------------------------------------------------------
@app.route('/faculty/login')
def faculty_login():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Faculty Portal Login | CampusGuard AI</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
        <style>
            body { margin: 0; padding: 0; background: #06080e; color: #fff; font-family: 'Plus Jakarta Sans', sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; text-align: center; }
            .card { background: rgba(14, 19, 32, 0.85); border: 1px solid rgba(52, 211, 153, 0.3); padding: 48px 36px; border-radius: 24px; max-width: 440px; backdrop-filter: blur(20px); box-shadow: 0 20px 50px rgba(52, 211, 153, 0.15); }
            h1 { color: #34d399; margin: 12px 0 8px; font-size: 1.8rem; }
            .badge { display: inline-block; padding: 4px 12px; background: rgba(52,211,153,0.1); border: 1px solid rgba(52,211,153,0.3); border-radius: 99px; color: #34d399; font-size: 0.75rem; font-weight: 700; }
            p { color: #94a3b8; line-height: 1.6; font-size: 0.95rem; margin: 16px 0; }
            a { display: inline-flex; align-items: center; gap: 8px; margin-top: 16px; padding: 12px 24px; background: linear-gradient(135deg, #059669, #047857); color: white; text-decoration: none; border-radius: 12px; font-weight: 700; font-size: 0.95rem; }
        </style>
    </head>
    <body>
        <div class="card">
            <div style="font-size: 3.5rem; margin-bottom: 8px;">👨‍🏫</div>
            <span class="badge">FACULTY ACCESS</span>
            <h1>Faculty Portal</h1>
            <p>Faculty ERP &amp; Class Management will be expanded in the subsequent phase.</p>
            <a href="/">← Back to Home Landing Page</a>
        </div>
    </body>
    </html>
    """)


@app.route('/parent/login')
def parent_login():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Parent Portal Login | CampusGuard AI</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
        <style>
            body { margin: 0; padding: 0; background: #06080e; color: #fff; font-family: 'Plus Jakarta Sans', sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; text-align: center; }
            .card { background: rgba(14, 19, 32, 0.85); border: 1px solid rgba(192, 132, 252, 0.3); padding: 48px 36px; border-radius: 24px; max-width: 440px; backdrop-filter: blur(20px); box-shadow: 0 20px 50px rgba(192, 132, 252, 0.15); }
            h1 { color: #c084fc; margin: 12px 0 8px; font-size: 1.8rem; }
            .badge { display: inline-block; padding: 4px 12px; background: rgba(192,132,252,0.1); border: 1px solid rgba(192,132,252,0.3); border-radius: 99px; color: #c084fc; font-size: 0.75rem; font-weight: 700; }
            p { color: #94a3b8; line-height: 1.6; font-size: 0.95rem; margin: 16px 0; }
            a { display: inline-flex; align-items: center; gap: 8px; margin-top: 16px; padding: 12px 24px; background: linear-gradient(135deg, #7c3aed, #6d28d9); color: white; text-decoration: none; border-radius: 12px; font-weight: 700; font-size: 0.95rem; }
        </style>
    </head>
    <body>
        <div class="card">
            <div style="font-size: 3.5rem; margin-bottom: 8px;">👨‍👩‍👧</div>
            <span class="badge">PARENT ACCESS</span>
            <h1>Parent Portal</h1>
            <p>Ward Tracking &amp; Parent Notifications will be expanded in the subsequent phase.</p>
            <a href="/">← Back to Home Landing Page</a>
        </div>
    </body>
    </html>
    """)


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
