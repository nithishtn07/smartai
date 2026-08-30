"""
CampusGuard AI — Enterprise Initial Seed & Master Configuration Module
Initializes system settings, course catalogs, academic calendar, faculty, and admin accounts.
NO fake, demo, sample, or dummy student/parent records are generated.
Students and linked parents are created exclusively via Admin Portal -> Add Student.
"""

import datetime
from werkzeug.security import generate_password_hash


def seed_database(conn):
    """
    Populates the database with essential enterprise master configuration:
    - Master Admin Account: admin (Campus Administrator / Admin@123)
    - Faculty Account: FAC001 (Dr. Ramesh Rao / Faculty@123)
    - System Settings, Courses Catalog, Academic Calendar, Emergency Contacts,
      Placement Drives, Announcements, and Alerts.
    - Zero fake/demo student or parent records are created.
    """
    cursor = conn.cursor()
    cursor.execute("DELETE FROM login_attempts")

    # 1. System Settings
    cursor.execute("SELECT COUNT(*) as cnt FROM system_settings")
    if cursor.fetchone()['cnt'] == 0:
        default_settings = [
            ('attendance_threshold', '75.0', 'Minimum attendance percentage required for examination eligibility.'),
            ('academic_year', '2026-2027', 'Current academic operating year.'),
            ('active_semester', 'Fall 2026 (Semester 5)', 'Active semester term across all departments.'),
            ('institution_name', 'CampusGuard Institute of Science & Technology', 'Official institutional branding title.'),
            ('emergency_broadcast_active', '1', 'Global toggle for real-time emergency broadcasts.')
        ]
        for key_name, value_text, description in default_settings:
            cursor.execute("""
                INSERT OR IGNORE INTO system_settings (key_name, value_text, description)
                VALUES (?, ?, ?)
            """, (key_name, value_text, description))

    # 2. Courses Catalog
    cursor.execute("SELECT COUNT(*) as cnt FROM courses")
    if cursor.fetchone()['cnt'] == 0:
        course_records = [
            ('CS301', 'Database Management Systems', 'Computer Science & Engineering', 5, 4, 'Dr. Ramesh Rao', 'Core Theory', 'CS-201', 'Mon, Wed 09:00 AM'),
            ('CS302', 'Operating Systems & Architecture', 'Computer Science & Engineering', 5, 4, 'Dr. Ramesh Rao', 'Core Theory', 'CS-302', 'Mon, Thu 11:00 AM'),
            ('CS303', 'Data Science & Machine Learning', 'Computer Science & Engineering', 5, 4, 'Dr. Ramesh Rao', 'Core Theory + Lab', 'CS-Lab 3', 'Mon, Wed 02:00 PM'),
            ('CS304', 'Computer Networks & Cyber Security', 'Computer Science & Engineering', 5, 4, 'Dr. Ramesh Rao', 'Core Theory', 'CS-201', 'Tue, Thu 09:00 AM'),
            ('CS305', 'Software Engineering & Agile ERP', 'Computer Science & Engineering', 5, 4, 'Dr. Ramesh Rao', 'Core Theory', 'CS-204', 'Tue, Fri 11:00 AM'),
            ('CS306', 'Campus Cyber Safety & Ethics', 'Computer Science & Engineering', 5, 2, 'Dr. Ramesh Rao', 'Institutional Mandatory', 'Seminar Hall 1', 'Fri 11:00 AM'),
            ('CS301L', 'DBMS Laboratory Work', 'Computer Science & Engineering', 5, 2, 'Dr. Ramesh Rao', 'Practical Lab', 'CS-Lab 1', 'Wed 09:00 AM')
        ]
        cursor.executemany("""
            INSERT INTO courses (
                course_code, course_name, department, semester, credits, faculty_name, course_type, room_number, timing
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, course_records)
    else:
        cursor.execute("UPDATE courses SET faculty_name = 'Dr. Ramesh Rao'")

    # 3. Timetable Structure
    cursor.execute("SELECT COUNT(*) as cnt FROM timetable WHERE department = 'Computer Science & Engineering' AND year = 3")
    if cursor.fetchone()['cnt'] == 0:
        timetable_records = [
            ('Computer Science & Engineering', 3, 'Monday', '09:00 AM', '10:30 AM', 'CS301', 'Database Management Systems', 'Dr. Ramesh Rao', 'CS-201'),
            ('Computer Science & Engineering', 3, 'Monday', '11:00 AM', '12:30 PM', 'CS302', 'Operating Systems', 'Dr. Ramesh Rao', 'CS-302'),
            ('Computer Science & Engineering', 3, 'Monday', '02:00 PM', '03:30 PM', 'CS303', 'Data Science & Machine Learning', 'Dr. Ramesh Rao', 'CS-Lab 3'),
            ('Computer Science & Engineering', 3, 'Tuesday', '09:00 AM', '10:30 AM', 'CS304', 'Computer Networks & Security', 'Dr. Ramesh Rao', 'CS-201'),
            ('Computer Science & Engineering', 3, 'Tuesday', '11:00 AM', '12:30 PM', 'CS305', 'Software Engineering', 'Dr. Ramesh Rao', 'CS-204'),
            ('Computer Science & Engineering', 3, 'Wednesday', '09:00 AM', '11:00 AM', 'CS301L', 'DBMS Laboratory', 'Dr. Ramesh Rao', 'CS-Lab 1'),
            ('Computer Science & Engineering', 3, 'Wednesday', '11:30 AM', '01:00 PM', 'CS303', 'Data Science', 'Dr. Ramesh Rao', 'CS-302'),
            ('Computer Science & Engineering', 3, 'Thursday', '10:00 AM', '11:30 AM', 'CS302', 'Operating Systems', 'Dr. Ramesh Rao', 'CS-302'),
            ('Computer Science & Engineering', 3, 'Thursday', '01:30 PM', '03:00 PM', 'CS304', 'Computer Networks', 'Dr. Ramesh Rao', 'CS-201'),
            ('Computer Science & Engineering', 3, 'Friday', '09:00 AM', '10:30 AM', 'CS305', 'Software Engineering', 'Dr. Ramesh Rao', 'CS-204'),
            ('Computer Science & Engineering', 3, 'Friday', '11:00 AM', '12:30 PM', 'CS306', 'Campus Cyber Safety & Ethics', 'Dr. Ramesh Rao', 'Seminar Hall 1'),
            ('Computer Science & Engineering', 3, 'Saturday', '09:30 AM', '11:00 AM', 'CS308', 'AI Research Colloquium', 'Dr. Ramesh Rao', 'Seminar Hall 2')
        ]
        cursor.executemany("""
            INSERT INTO timetable (
                department, year, day_of_week, start_time, end_time, subject_code, subject_name, faculty_name, room_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, timetable_records)
    else:
        cursor.execute("UPDATE timetable SET faculty_name = 'Dr. Ramesh Rao'")


    # 5. Study Materials & Curriculum Guidelines
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

    # 6. Examination Schedules
    cursor.execute("SELECT COUNT(*) as cnt FROM examinations")
    if cursor.fetchone()['cnt'] == 0:
        exam_records = [
            ('FAT Semester 5', 'CS301', 'Database Management Systems', '2026-09-10', '09:30 AM - 12:30 PM', 'Academic Block A', 'Exam Hall 3', 'Allocated on Admit Card'),
            ('FAT Semester 5', 'CS302', 'Operating Systems & Architecture', '2026-09-12', '09:30 AM - 12:30 PM', 'Academic Block A', 'Exam Hall 3', 'Allocated on Admit Card'),
            ('FAT Semester 5', 'CS303', 'Data Science & Machine Learning', '2026-09-15', '09:30 AM - 12:30 PM', 'Academic Block A', 'Exam Hall 3', 'Allocated on Admit Card'),
            ('FAT Semester 5', 'CS304', 'Computer Networks & Cyber Security', '2026-09-17', '09:30 AM - 12:30 PM', 'Academic Block A', 'Exam Hall 3', 'Allocated on Admit Card'),
            ('FAT Semester 5', 'CS305', 'Software Engineering & Agile ERP', '2026-09-19', '09:30 AM - 12:30 PM', 'Academic Block A', 'Exam Hall 3', 'Allocated on Admit Card')
        ]
        cursor.executemany("""
            INSERT INTO examinations (
                exam_type, course_code, course_name, exam_date, exam_time, venue, room_number, seat_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, exam_records)

    # 7. Emergency Contacts Directory
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

    # 8. Campus Alerts & Safety Notices
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

    # 9. Faculty Account: FAC001 (Dr. Ramesh Rao) - Single faculty for all subjects
    cursor.execute("DELETE FROM faculties WHERE email != ?", ('faculty@example.com',))
    cursor.execute("SELECT id FROM faculties WHERE email = ?", ('faculty@example.com',))
    demo_faculty = cursor.fetchone()
    fac_pw = generate_password_hash('Faculty@123')
    if not demo_faculty:
        cursor.execute("""
            INSERT INTO faculties (faculty_id, name, email, phone, password_hash, department, designation, cabin)
            VALUES ('FAC001', 'Dr. Ramesh Rao', 'faculty@example.com', '+91 98888 11223', ?, 'Computer Science & Engineering', 'Professor & Faculty Advisor', 'CS-201 (Cabin 4)')
        """, (fac_pw,))
        faculty_db_id = cursor.lastrowid
    else:
        faculty_db_id = demo_faculty['id']
        cursor.execute("""
            UPDATE faculties 
            SET name = 'Dr. Ramesh Rao', faculty_id = 'FAC001', department = 'Computer Science & Engineering',
                designation = 'Professor & Faculty Advisor', cabin = 'CS-201 (Cabin 4)', password_hash = ?
            WHERE id = ?
        """, (fac_pw, faculty_db_id))

    # 10. Admin Account: admin (Campus Administrator)
    cursor.execute("SELECT id FROM admins WHERE username = ?", ('admin',))
    demo_admin = cursor.fetchone()
    admin_pw = generate_password_hash('Admin@123')
    if not demo_admin:
        cursor.execute("""
            INSERT INTO admins (username, name, email, password_hash, role)
            VALUES ('admin', 'Campus Administrator', 'admin@example.com', ?, 'SuperAdmin')
        """, (admin_pw,))
    else:
        cursor.execute("UPDATE admins SET password_hash = ? WHERE id = ?", (admin_pw, demo_admin['id']))

    # 11. Announcements
    cursor.execute("SELECT COUNT(*) as cnt FROM announcements")
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute("""
            INSERT INTO announcements (title, description, category, priority, target_audience, author_name)
            VALUES ('Semester 5 Final Assessment (FAT) Schedule Released', 'Official timetable for Fall 2026 FAT Examinations is now live.', 'Academic', 'High', 'All', 'Office of the Controller of Examinations')
        """)
        cursor.execute("""
            INSERT INTO announcements (title, description, category, priority, target_audience, author_name)
            VALUES ('Campus Security Alert: Perimeter Lighting Upgrade', 'Perimeter LED lighting modernization in progress near Parking Bay.', 'Safety', 'Normal', 'All', 'Campus Security Command')
        """)

    # 12. Faculty System Notification
    cursor.execute("SELECT COUNT(*) as cnt FROM notifications WHERE recipient_role = 'faculty' AND recipient_id = ?", (faculty_db_id,))
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute("""
            INSERT INTO notifications (recipient_id, recipient_role, title, message, category, priority)
            VALUES (?, 'faculty', 'Faculty Advisor Portal Operational', 'Welcome Dr. Ramesh Rao. Department records are ready.', 'System', 'Normal')
        """, (faculty_db_id,))

    # 13. System Activity Log
    cursor.execute("SELECT COUNT(*) as cnt FROM activity_logs")
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute("""
            INSERT INTO activity_logs (user_name, user_role, action, details, ip_address)
            VALUES ('System Master', 'system', 'SYSTEM_INITIALIZATION', 'CampusGuard AI enterprise ERP initialization completed.', '127.0.0.1')
        """)

    # 14. Academic Calendar
    cursor.execute("SELECT COUNT(*) as cnt FROM academic_calendar")
    if cursor.fetchone()['cnt'] == 0:
        cal_records = [
            ('Commencement of Fall 2026 Semester', 'Official beginning of instruction for undergraduate programs.', '2026-07-20', '2026-07-20', 'Academic', 'Semester 5'),
            ('Continuous Assessment Test 1 (CAT-1)', 'First mid-semester continuous assessment examinations.', '2026-08-25', '2026-08-30', 'Exam', 'Semester 5'),
            ('Technical Symposium & Hackathon (TechFest 2026)', 'Annual inter-collegiate technical fest, project expo, and competitive coding.', '2026-09-18', '2026-09-20', 'Event', 'All'),
            ('National Holiday — Gandhi Jayanti', 'Institutional holiday.', '2026-10-02', '2026-10-02', 'Holiday', 'All'),
            ('Continuous Assessment Test 2 (CAT-2)', 'Second continuous assessment examination series.', '2026-10-15', '2026-10-20', 'Exam', 'Semester 5'),
            ('Fall Semester Final Assessment Tests (FAT)', 'Comprehensive term-end theory and practical laboratory examinations.', '2026-11-10', '2026-11-28', 'Exam', 'Semester 5')
        ]
        cursor.executemany("""
            INSERT INTO academic_calendar (title, description, start_date, end_date, event_type, semester)
            VALUES (?, ?, ?, ?, ?, ?)
        """, cal_records)

    # 15. Placements & Career Drives
    cursor.execute("CREATE TABLE IF NOT EXISTS placements (id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT NOT NULL, job_role TEXT NOT NULL, ctc_package TEXT NOT NULL, eligibility_cgpa REAL DEFAULT 7.5, eligible_departments TEXT DEFAULT 'CSE, ECE, IT', location TEXT DEFAULT 'Bengaluru / Hyderabad', deadline DATE NOT NULL, drive_date DATE NOT NULL, status TEXT DEFAULT 'ACTIVE', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cursor.execute("SELECT COUNT(*) as cnt FROM placements")
    if cursor.fetchone()['cnt'] == 0:
        placements_data = [
            ('Microsoft India', 'Software Development Engineer - I', '₹44.5 LPA', 8.0, 'CSE, IT', 'Bengaluru, Karnataka', '2026-09-15', '2026-09-25', 'ACTIVE'),
            ('Google India', 'Associate Cloud Engineer', '₹38.0 LPA', 8.5, 'CSE, IT, ECE', 'Hyderabad, Telangana', '2026-09-20', '2026-10-02', 'ACTIVE'),
            ('Amazon AWS', 'Solutions Architect Associate', '₹32.0 LPA', 7.5, 'CSE, ECE', 'Chennai, Tamil Nadu', '2026-09-30', '2026-10-10', 'ACTIVE'),
            ('Cisco Systems', 'Network & Security Engineer', '₹24.0 LPA', 7.0, 'CSE, ECE, IT', 'Bengaluru, Karnataka', '2026-10-05', '2026-10-15', 'ACTIVE')
        ]
        cursor.executemany("""
            INSERT INTO placements (company_name, job_role, ctc_package, eligibility_cgpa, eligible_departments, location, deadline, drive_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, placements_data)

    # 16. Baseline Transport Routes
    has_transport = cursor.execute("SELECT COUNT(*) FROM transport_routes").fetchone()[0]
    if has_transport == 0:
        cursor.execute("""
            INSERT INTO transport_routes (route_number, route_name, bus_number, driver_name, driver_phone, pickup_time, pickup_location, eta_campus)
            VALUES 
            ('Route 14', 'Metro Line Express', 'KA-05-CG-4820', 'Sundaram K', '+91 98765 43299', '07:45 AM', 'Main Metro Station Gate 2', '08:25 AM'),
            ('Route 08', 'South Ring Corridor', 'KA-05-CG-4821', 'Rajendra V', '+91 98765 43298', '07:30 AM', 'South City Junction', '08:20 AM'),
            ('Route 22', 'North Tech Corridor', 'KA-05-CG-4822', 'Manjunath B', '+91 98765 43297', '07:15 AM', 'North Tech Gateway', '08:15 AM')
        """)

    # 17. Seed Demo Academic Records for Existing Students (Tagged is_demo=1)
    seed_demo_academic_marks(conn)

    # 18. Seed Persistent Demo Fees & Transactions for Existing Students
    seed_demo_fees_and_payments(conn)

    conn.commit()


def seed_demo_academic_marks(conn):
    """
    Populates varied, persistent database-backed demo marks for existing active students
    who do not yet have continuous assessment records.
    Records are tagged with is_demo = 1 for clear internal identification.
    CGPA is dynamically calculated directly from course credits.
    """
    from services.academic_service import calculate_grade_point, sync_student_cgpa

    cursor = conn.cursor()
    students = cursor.execute("SELECT id, register_number, name FROM students WHERE status != 'DELETED' ORDER BY id ASC").fetchall()
    courses = cursor.execute("SELECT course_code, course_name, credits FROM courses ORDER BY course_code ASC").fetchall()

    if not students or not courses:
        return

    # Varied score profiles for realistic CGPA distribution across students
    base_profiles = [
        # Profile 0: Distinction (9.0+ CGPA)
        {
            'CS301': (46.0, 48.0, 9.5, 9.5, 19.0, 94.0, 'S'),
            'CS302': (45.0, 46.0, 9.0, 9.5, 18.5, 91.0, 'S'),
            'CS303': (47.0, 49.0, 10.0, 10.0, 19.5, 96.0, 'S'),
            'CS304': (43.0, 45.0, 9.0, 9.0, 18.0, 88.0, 'A'),
            'CS305': (44.0, 46.0, 9.5, 9.5, 18.5, 90.0, 'S'),
            'CS306': (47.0, 48.0, 9.5, 9.5, 19.0, 93.0, 'S'),
            'CS301L': (48.0, 50.0, 10.0, 10.0, 20.0, 97.0, 'S'),
        },
        # Profile 1: Excellent (8.5 - 8.9 CGPA)
        {
            'CS301': (43.0, 44.0, 9.0, 9.0, 17.5, 87.0, 'A'),
            'CS302': (44.0, 45.0, 9.0, 9.0, 18.0, 89.0, 'S'),
            'CS303': (41.0, 43.0, 8.5, 8.5, 17.0, 84.0, 'A'),
            'CS304': (45.0, 46.0, 9.5, 9.5, 18.5, 91.0, 'S'),
            'CS305': (42.0, 43.0, 8.5, 9.0, 17.0, 85.0, 'A'),
            'CS306': (46.0, 47.0, 9.5, 9.5, 19.0, 92.0, 'S'),
            'CS301L': (47.0, 48.0, 9.5, 10.0, 19.0, 95.0, 'S'),
        },
        # Profile 2: Very Good (8.0 - 8.4 CGPA)
        {
            'CS301': (40.0, 41.0, 8.0, 8.5, 16.0, 81.0, 'A'),
            'CS302': (38.0, 40.0, 8.0, 8.0, 15.5, 78.0, 'B'),
            'CS303': (42.0, 44.0, 8.5, 9.0, 17.0, 85.0, 'A'),
            'CS304': (39.0, 41.0, 8.0, 8.0, 16.0, 79.0, 'B'),
            'CS305': (41.0, 42.0, 8.5, 8.5, 16.5, 83.0, 'A'),
            'CS306': (44.0, 45.0, 9.0, 9.0, 18.0, 89.0, 'S'),
            'CS301L': (45.0, 46.0, 9.0, 9.5, 18.0, 91.0, 'S'),
        },
        # Profile 3: Good (7.2 - 7.8 CGPA)
        {
            'CS301': (36.0, 38.0, 7.5, 7.5, 14.5, 74.0, 'B'),
            'CS302': (35.0, 36.0, 7.0, 7.5, 14.0, 72.0, 'B'),
            'CS303': (38.0, 39.0, 8.0, 8.0, 15.0, 77.0, 'B'),
            'CS304': (34.0, 36.0, 7.0, 7.0, 14.0, 70.0, 'B'),
            'CS305': (37.0, 38.0, 7.5, 8.0, 15.0, 75.0, 'B'),
            'CS306': (42.0, 43.0, 8.5, 8.5, 17.0, 85.0, 'A'),
            'CS301L': (44.0, 45.0, 9.0, 9.0, 18.0, 88.0, 'A'),
        }
    ]

    for idx, s in enumerate(students):
        stu_id = s['id']
        profile = base_profiles[idx % len(base_profiles)]
        for c in courses:
            code = c['course_code']
            name = c['course_name']
            if code in profile:
                cat1, cat2, quiz, assignment, project, fat, grade = profile[code]
            else:
                cat1, cat2, quiz, assignment, project, fat, grade = (42.0, 44.0, 8.5, 8.5, 17.0, 85.0, 'A')

            grade_pts = calculate_grade_point(grade)
            cursor.execute("""
                INSERT OR IGNORE INTO marks (
                    student_id, course_code, course_name, cat1, cat2, quiz,
                    assignment, project, fat, grade, grade_points, status, is_demo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PASS', 1)
            """, (stu_id, code, name, cat1, cat2, quiz, assignment, project, fat, grade, grade_pts))

        sync_student_cgpa(conn, stu_id)


def seed_demo_fees_and_payments(conn):
    """
    Seeds realistic, persistent fee ledger and transaction records for existing active students
    who do not yet have fee records.
    Does NOT create new students. Seeded once and preserved across reloads.
    """
    cursor = conn.cursor()
    students = cursor.execute("SELECT id, register_number, name, semester FROM students WHERE status != 'DELETED'").fetchall()
    if not students:
        return

    for s in students:
        stu_id = s['id']
        existing_cnt = cursor.execute("SELECT COUNT(*) FROM fees WHERE student_id = ?", (stu_id,)).fetchone()[0]
        if existing_cnt > 0:
            continue

        sample_fees = [
            ("Semester Tuition Fee", 45000.0, "2026-09-30", "PAID", 45000.0),
            ("Hostel & Mess Fee", 25000.0, "2026-09-30", "PENDING", 0.0),
            ("Examination Fee", 2000.0, "2026-08-15", "OVERDUE", 0.0),
            ("Library & Digital Tech Fee", 3000.0, "2026-10-15", "PENDING", 0.0)
        ]

        for fee_type, amount, due_date, status_hint, paid_amount in sample_fees:
            status = 'PAID' if paid_amount >= amount else ('PARTIAL' if paid_amount > 0 else 'PENDING')
            cursor.execute("""
                INSERT INTO fees (student_id, fee_type, amount, paid_amount, due_date, status, academic_year, semester)
                VALUES (?, ?, ?, ?, ?, ?, '2026-2027', ?)
            """, (stu_id, fee_type, amount, paid_amount, due_date, status, s['semester'] or 5))
            fee_id = cursor.lastrowid

            if paid_amount > 0:
                txn_id = f"TXN-DEMO-{stu_id}-{fee_id}-20260810"
                rcp_no = f"REC-DEMO-{stu_id:02d}{fee_id:02d}"
                paid_at = "2026-08-10 14:30:00"
                cursor.execute("""
                    INSERT INTO payment_transactions (
                        transaction_id, student_id, fee_type, amount, payment_method,
                        receipt_no, paid_at, status, fee_id
                    ) VALUES (?, ?, ?, ?, 'Razorpay UPI (Verified)', ?, ?, 'SUCCESS', ?)
                """, (txn_id, stu_id, fee_type, paid_amount, rcp_no, paid_at, fee_id))

    conn.commit()

