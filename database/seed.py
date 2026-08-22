"""
CampusGuard AI — Enterprise Initial Seed & Demo Data Module
"""

import datetime
from werkzeug.security import generate_password_hash


def seed_database(conn):
    """
    Populates the database with initial enterprise demo data:
    - Demo Student: STU001 (Nithish Nagaraj / Student@123)
    - Demo Parent: PAR001 (R. S. Kumar / Parent@123, linked to STU001)
    - Demo Faculty: FAC001 (Dr. Ramesh Rao / Faculty@123)
    - Demo Admin: admin (Campus Administrator / Admin@123)
    - Complete academic, fee, safety, and operational records.
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

    # 2. Demo Student Account: STU001
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
            'Nithish Nagaraj', 'STU001', 'student@example.com', demo_password_hash,
            'Computer Science', 3, 'B.Tech', 5, 'A', '+91 98765 43210',
            '2004-05-14', '#42, Green Avenue, Tech City, Karnataka 560001',
            'R. S. Kumar', '+91 94440 12345', '2023-08-01', 8.75, 8.90, 112, 160
        ))
        student_id = cursor.lastrowid
    else:
        student_id = demo_student['id']
        demo_password_hash = generate_password_hash('Student@123')
        cursor.execute("""
            UPDATE students SET name = 'Nithish Nagaraj', email = 'student@example.com', password_hash = ?
            WHERE id = ?
        """, (demo_password_hash, student_id))

    # 3. Courses Catalog
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

    # 4. Marks Records
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

    # 5. Attendance Records & Logs
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

    # 6. Timetable
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

    # 7. Safety Incidents
    cursor.execute("SELECT COUNT(*) as cnt FROM incidents")
    if cursor.fetchone()['cnt'] == 0:
        historical_incidents = [
            ('INC-101', student_id, 'Poor Lighting', 'Parking Area', 12.9712, 77.5941, 'Broken halogen lamp near vehicle bay with pitch dark walking alley', 'RESOLVED', 'Officer R. Singh', 65, '2026-08-10 19:15:00'),
            ('INC-102', student_id, 'Suspicious Activity', 'Parking Area', 12.9714, 77.5943, 'Unidentified persons hanging around two-wheeler parking after sunset', 'RESOLVED', 'Officer R. Singh', 75, '2026-08-11 19:45:00'),
            ('INC-103', student_id, 'Harassment', 'Parking Area', 12.9715, 77.5944, 'Catcalling reported near parking exit ramp between 8 PM and 8:30 PM', 'RESOLVED', 'Inspector V. Nair', 88, '2026-08-12 20:10:00'),
            ('INC-104', student_id, 'Vehicle Scratch', 'Parking Area', 12.9713, 77.5942, 'Vehicle scratched near rear row under non-functioning CCTV camera', 'RESOLVED', 'Officer M. Khan', 55, '2026-08-14 18:30:00'),
            ('INC-105', student_id, 'Theft Attempt', 'Parking Area', 12.9711, 77.5940, 'Helmet and accessories taken from bike rack', 'RESOLVED', 'Officer M. Khan', 70, '2026-08-16 20:00:00'),
            ('INC-109', student_id, 'Stalking Concern', 'Parking Area', 12.9716, 77.5945, 'Student followed from parking bay to library corridor', 'RESOLVED', 'Inspector V. Nair', 85, '2026-08-19 20:20:00'),
            ('INC-106', student_id, 'Water Leakage', 'Hostel Block B (Oak Wing)', 12.9720, 77.5950, 'Pipe burst and puddle hazard near Block B gate entrance', 'RESOLVED', 'Warden Prabhakar', 45, '2026-08-15 14:00:00'),
            ('INC-107', student_id, 'Broken Lamp', 'Hostel Block B (Oak Wing)', 12.9721, 77.5951, 'Flickering street lamp causing blind spot on pathway', 'RESOLVED', 'Maint. Team #3', 55, '2026-08-17 21:30:00'),
            ('INC-110', student_id, 'Suspicious Person', 'Hostel Block B (Oak Wing)', 12.9722, 77.5952, 'Trespassing individual spotted near ground floor window', 'RESOLVED', 'Officer R. Singh', 80, '2026-08-18 22:15:00'),
            ('INC-111', student_id, 'Harassment Near Gate', 'Hostel Block B (Oak Wing)', 12.9723, 77.5953, 'Verbal harassment shouted from road perimeter', 'RESOLVED', 'Inspector V. Nair', 85, '2026-08-20 20:45:00'),
            ('INC-108', student_id, 'Broken Bench', 'Central University Library', 12.9730, 77.5960, 'Damaged chair on reading floor with protruding metal screw', 'RESOLVED', 'Library Staff', 25, '2026-08-18 11:00:00'),
            ('INC-112', student_id, 'Open Electrical Wire', 'Academic Block A (CS Dept)', 12.9740, 77.5970, 'Exposed terminal box near Room 204 during renovation', 'RESOLVED', 'Electrician Desk', 78, '2026-08-17 10:30:00'),
            ('INC-113', student_id, 'Slippery Spill Hazard', 'Campus Dining Hall & Canteen', 12.9725, 77.5955, 'Oil spill near tray return counter causing slip risk', 'RESOLVED', 'Canteen Supervisor', 35, '2026-08-19 13:15:00')
        ]
        cursor.executemany("""
            INSERT INTO incidents (
                incident_id, student_id, incident_type, location, latitude, longitude, description, status, assigned_to, priority_score, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, historical_incidents)

    # 8. Assignments, Materials, Exams, Fees, Placements, Contacts, Alerts
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

    cursor.execute("SELECT COUNT(*) as cnt FROM student_submissions")
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute("""
            INSERT INTO student_submissions (assignment_id, student_id, submission_file, comments, marks_obtained, feedback, status)
            VALUES (1, 1, 'Nithish_STU001_Assignment2.pdf', 'Distributed 2PC consensus protocol implementation.', 48.5, 'Exceptional execution of distributed 2PC recovery protocol.', 'Graded')
        """)

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

    # 9. Demo Parent Account: PAR001 (linked to STU001)
    cursor.execute("SELECT id, password_hash, student_id FROM parents WHERE email = ?", ('parent@example.com',))
    demo_parent = cursor.fetchone()
    if not demo_parent:
        demo_parent_pw = generate_password_hash('Parent@123')
        cursor.execute("""
            INSERT INTO parents (
                parent_id, name, email, phone, password_hash, relationship, student_id, occupation, address
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'PAR001', 'R. S. Kumar', 'parent@example.com', '+91 94440 12345',
            demo_parent_pw, 'Father', student_id, 'Chief Structural Engineer',
            '#42, Green Avenue, Tech City, Karnataka 560001'
        ))
        parent_db_id = cursor.lastrowid
    else:
        parent_db_id = demo_parent['id']
        demo_parent_pw = generate_password_hash('Parent@123')
        cursor.execute("UPDATE parents SET student_id = ?, password_hash = ? WHERE id = ?", (student_id, demo_parent_pw, parent_db_id))

    cursor.execute("SELECT COUNT(*) as cnt FROM parent_messages WHERE parent_id = ?", (parent_db_id,))
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute("""
            INSERT INTO parent_messages (parent_id, student_id, sender_role, sender_name, receiver_name, subject, content)
            VALUES (?, ?, 'Faculty Advisor', 'Dr. Ramesh Rao (Faculty Advisor)', 'R. S. Kumar',
                    'Mid-Semester Academic Progress Report',
                    'Dear Mr. Kumar, Nithish Nagaraj has shown exceptional dedication in Database Systems and Computer Networks with an overall 90%+ attendance and 8.75 CGPA standing. His capstone project proposal is approved.')
        """, (parent_db_id, student_id))

    # 10. Demo Faculty Account: FAC001
    cursor.execute("SELECT id FROM faculties WHERE email = ?", ('faculty@example.com',))
    demo_faculty = cursor.fetchone()
    fac_pw = generate_password_hash('Faculty@123')
    if not demo_faculty:
        cursor.execute("""
            INSERT INTO faculties (faculty_id, name, email, phone, password_hash, department, designation, cabin)
            VALUES ('FAC001', 'Dr. Ramesh Rao', 'faculty@example.com', '+91 98888 11223', ?, 'Computer Science', 'Associate Professor & Faculty Advisor', 'CS-201 (Cabin 4)')
        """, (fac_pw,))
        faculty_db_id = cursor.lastrowid
    else:
        faculty_db_id = demo_faculty['id']
        cursor.execute("UPDATE faculties SET password_hash = ? WHERE id = ?", (fac_pw, faculty_db_id))

    # 11. Demo Admin Account: admin
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

    # 12. Announcements
    cursor.execute("SELECT COUNT(*) as cnt FROM announcements")
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute("""
            INSERT INTO announcements (title, description, category, priority, target_audience, author_name)
            VALUES ('Semester 5 Final Assessment (FAT) Schedule Released', 'Official timetable for Fall 2026 FAT Examinations is now live on Student and Parent Portals.', 'Academic', 'High', 'All', 'Office of the Controller of Examinations')
        """)
        cursor.execute("""
            INSERT INTO announcements (title, description, category, priority, target_audience, author_name)
            VALUES ('Campus Security Alert: Perimeter Lighting Upgrade', 'Perimeter LED lighting modernization in progress near Parking Bay.', 'Safety', 'Normal', 'All', 'Campus Security Command')
        """)

    # 13. Notifications
    cursor.execute("SELECT COUNT(*) as cnt FROM notifications WHERE recipient_role = 'student' AND recipient_id = ?", (student_id,))
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute("""
            INSERT INTO notifications (recipient_id, recipient_role, title, message, category, priority)
            VALUES (?, 'student', 'Welcome to CampusGuard AI', 'Your smart student ERP portal is active and verified.', 'System', 'Normal')
        """, (student_id,))
        cursor.execute("""
            INSERT INTO notifications (recipient_id, recipient_role, title, message, category, priority)
            VALUES (?, 'student', 'DBMS Assignment 2 Published', 'Dr. Ramesh Rao posted Assignment 2 due on 2026-08-28.', 'Academic', 'Normal')
        """, (student_id,))

    cursor.execute("SELECT COUNT(*) as cnt FROM notifications WHERE recipient_role = 'parent' AND recipient_id = ?", (parent_db_id,))
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute("""
            INSERT INTO notifications (recipient_id, recipient_role, title, message, category, priority)
            VALUES (?, 'parent', 'Parent-Ward Link Verified', 'Your parent monitoring account is linked to Nithish Nagaraj (STU001).', 'System', 'Normal')
        """, (parent_db_id,))

    cursor.execute("SELECT COUNT(*) as cnt FROM notifications WHERE recipient_role = 'faculty' AND recipient_id = ?", (faculty_db_id,))
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute("""
            INSERT INTO notifications (recipient_id, recipient_role, title, message, category, priority)
            VALUES (?, 'faculty', 'Faculty Advisor Portal Operational', 'Welcome Dr. Ramesh Rao. Advisee records for CSE Year 3 are synced.', 'System', 'Normal')
        """, (faculty_db_id,))

    # 14. Activity Log
    cursor.execute("SELECT COUNT(*) as cnt FROM activity_logs")
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute("""
            INSERT INTO activity_logs (user_name, user_role, action, details, ip_address)
            VALUES ('System Master', 'system', 'SYSTEM_INITIALIZATION', 'CampusGuard AI multi-portal ERP initialization completed.', '127.0.0.1')
        """)

    # 15. Academic Calendar
    cursor.execute("SELECT COUNT(*) as cnt FROM academic_calendar")
    if cursor.fetchone()['cnt'] == 0:
        cal_records = [
            ('Commencement of Fall 2026 Semester', 'Official beginning of instruction for 3rd and 4th year undergraduate programs.', '2026-07-20', '2026-07-20', 'Academic', 'Semester 5'),
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

    # 16. Placements & Career Drives
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

    # 17. Seed Comprehensive Emergencies
    cursor.execute("SELECT COUNT(*) as cnt FROM emergencies")
    if cursor.fetchone()['cnt'] == 0:
        demo_emergencies = [
            (
                'EMG-2026-000101', 1, 'student', 'Nithish Nagaraj', '+91 98765 43210',
                'Medical Emergency', 'Medical Emergency', 'HIGH',
                'Student felt dizzy and collapsed in Computer Lab 2 after prolonged project session.',
                12.9716, 77.5946, 5.0, 'Main Academic Block', 'Main Academic Block', '2nd Floor', 'Lab 2',
                'RESOLVED', 85, 'Officer Ravi (QRT Unit 1)', 'Medical Responder',
                '{"category": "Medical Emergency", "severity": "HIGH", "priority": "IMMEDIATE", "dept": "Campus Medical Center"}',
                'First Aid administered by campus nurse; vitals stabilized and student escorted to health clinic.',
                '2026-08-20 10:14:00', '2026-08-20 10:15:10', '2026-08-20 10:16:00', '2026-08-20 10:17:30', '2026-08-20 10:21:00', '2026-08-20 10:35:00', '2026-08-20 10:40:00'
            ),
            (
                'EMG-2026-000102', 1, 'student', 'Nithish Nagaraj', '+91 98765 43210',
                'Personal Safety', 'Personal Safety', 'MEDIUM',
                'Suspicious non-campus individual loitering near East Quadrangle bike parking lot.',
                12.9722, 77.5950, 10.0, 'Parking Area East', 'East Quadrangle', 'Ground Level', 'Bike Lot B',
                'RESOLVED', 60, 'Officer Suresh (Security Patrol)', 'Security Officer',
                '{"category": "Personal Safety", "severity": "MEDIUM", "priority": "URGENT", "dept": "Campus Security Command"}',
                'Security patrol inspected zone, verified visitor credential, and escorted unauthorized visitor off-campus.',
                '2026-08-21 19:40:00', '2026-08-21 19:41:00', '2026-08-21 19:42:15', '2026-08-21 19:43:00', '2026-08-21 19:46:00', '2026-08-21 19:58:00', '2026-08-21 20:00:00'
            ),
            (
                'EMG-2026-000103', 2, 'student', 'Sneha Patel', '+91 98765 11223',
                'Campus Infrastructure', 'Campus Infrastructure', 'HIGH',
                'Elevator stopped between 2nd and 3rd floor in Central Library with 2 students inside.',
                12.9730, 77.5935, 3.0, 'Central Library', 'Central Library', 'Between 2nd & 3rd Floor', 'Elevator #2',
                'RESOLVED', 75, 'Engr. Rajesh (Facilities & Maintenance)', 'Facility Engineer',
                '{"category": "Campus Infrastructure", "severity": "HIGH", "priority": "URGENT", "dept": "Engineering & Estate Services"}',
                'Manual mechanical release engaged safely; all occupants exited without injury. Technicians resetting motor controller.',
                '2026-08-22 09:10:00', '2026-08-22 09:10:45', '2026-08-22 09:11:30', '2026-08-22 09:12:00', '2026-08-22 09:16:30', '2026-08-22 09:28:00', '2026-08-22 09:30:00'
            )
        ]
        cursor.executemany("""
            INSERT INTO emergencies (
                emergency_id, user_id, user_role, reporter_name, reporter_phone,
                emergency_type, category, severity, description,
                latitude, longitude, location_accuracy, campus_zone, building, floor, room,
                status, priority_score, assigned_responder, assigned_responder_type,
                ai_classification, resolution_summary,
                created_at, acknowledged_at, assigned_at, response_started_at, arrived_at, resolved_at, closed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, demo_emergencies)

        # Seed Notes
        cursor.execute("""
            INSERT INTO emergency_notes (emergency_id, author_id, author_name, author_role, note_text, created_at)
            VALUES 
            ('EMG-2026-000101', 1, 'Officer Ravi', 'Security', 'Dispatched with medical kit. Nurse Priya accompanying.', '2026-08-20 10:18:00'),
            ('EMG-2026-000101', 1, 'Officer Ravi', 'Security', 'Arrived at Lab 2. Student is conscious, blood pressure 110/70.', '2026-08-20 10:22:00'),
            ('EMG-2026-000102', 1, 'Officer Suresh', 'Security', 'Patrol unit on bike located individual near Gate 3.', '2026-08-21 19:47:00'),
            ('EMG-2026-000103', 1, 'Engr. Rajesh', 'Maintenance', 'Keys retrieved, elevator door safety latch opened manually.', '2026-08-22 09:17:00')
        """)

        # Seed Audit Logs
        cursor.execute("""
            INSERT INTO emergency_audit_logs (emergency_id, user_name, user_role, action, old_value, new_value, timestamp)
            VALUES
            ('EMG-2026-000101', 'Nithish Nagaraj', 'student', 'SOS_TRIGGERED', NULL, 'TRIGGERED', '2026-08-20 10:14:00'),
            ('EMG-2026-000101', 'Security Dispatch', 'security', 'ACKNOWLEDGED', 'TRIGGERED', 'ACKNOWLEDGED', '2026-08-20 10:15:10'),
            ('EMG-2026-000101', 'Security Dispatch', 'security', 'ASSIGN_RESPONDER', 'Unassigned', 'Officer Ravi (QRT Unit 1)', '2026-08-20 10:16:00'),
            ('EMG-2026-000101', 'Officer Ravi', 'security', 'EN_ROUTE', 'RESPONDER_ASSIGNED', 'EN_ROUTE', '2026-08-20 10:17:30'),
            ('EMG-2026-000101', 'Officer Ravi', 'security', 'ON_SCENE', 'EN_ROUTE', 'ON_SCENE', '2026-08-20 10:21:00'),
            ('EMG-2026-000101', 'Security Dispatch', 'security', 'RESOLVED', 'ON_SCENE', 'RESOLVED', '2026-08-20 10:35:00'),
            ('EMG-2026-000101', 'Admin Command', 'admin', 'CLOSED', 'RESOLVED', 'CLOSED', '2026-08-20 10:40:00')
        """)

    conn.commit()
