-- =============================================================================
-- CampusGuard AI — Enterprise Relational Schema Definition
-- =============================================================================

-- 1. Students Table
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
    status TEXT DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_students_reg ON students (register_number);
CREATE INDEX IF NOT EXISTS idx_students_dept_yr ON students (department, year);

-- 2. Parents Table
CREATE TABLE IF NOT EXISTS parents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    relationship TEXT DEFAULT 'Father',
    student_id INTEGER NOT NULL,
    occupation TEXT DEFAULT 'Civil Engineer',
    address TEXT DEFAULT '#42, Green Avenue, Tech City, Karnataka 560001',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students (id)
);

CREATE INDEX IF NOT EXISTS idx_parents_email ON parents (email);
CREATE INDEX IF NOT EXISTS idx_parents_student_id ON parents (student_id);

-- 3. Faculties Table
CREATE TABLE IF NOT EXISTS faculties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    department TEXT NOT NULL,
    designation TEXT DEFAULT 'Associate Professor & Faculty Advisor',
    cabin TEXT DEFAULT 'CS-201 (Cabin 4)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_faculties_email ON faculties (email);
CREATE INDEX IF NOT EXISTS idx_faculties_dept ON faculties (department);

-- 4. Admins Table
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'SuperAdmin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_admins_username ON admins (username);

-- 5. Courses Catalog
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

CREATE INDEX IF NOT EXISTS idx_courses_code ON courses (course_code);
CREATE INDEX IF NOT EXISTS idx_courses_dept_sem ON courses (department, semester);

-- 6. Marks & Assessments
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

CREATE INDEX IF NOT EXISTS idx_marks_student_course ON marks (student_id, course_code);

-- 7. Attendance Aggregate
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

CREATE INDEX IF NOT EXISTS idx_attendance_student_subject ON attendance (student_id, subject_code);

-- 8. Date-wise Attendance Logs
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

CREATE INDEX IF NOT EXISTS idx_att_logs_student_date ON attendance_logs (student_id, date);

-- 9. Timetable
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

CREATE INDEX IF NOT EXISTS idx_timetable_dept_yr_day ON timetable (department, year, day_of_week);

-- 10. Assignments
CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT NOT NULL,
    course_name TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    faculty_name TEXT NOT NULL,
    due_date TEXT NOT NULL,
    max_marks INTEGER DEFAULT 50,
    status TEXT DEFAULT 'Pending',
    marks_obtained INTEGER,
    feedback TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_assignments_course ON assignments (course_code);

-- 10b. Student Submissions
CREATE TABLE IF NOT EXISTS student_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER,
    student_id INTEGER,
    submission_file TEXT,
    comments TEXT,
    marks_obtained REAL,
    feedback TEXT,
    status TEXT DEFAULT 'Submitted',
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assignment_id) REFERENCES assignments(id),
    FOREIGN KEY (student_id) REFERENCES students(id)
);

-- 11. Study Materials
CREATE TABLE IF NOT EXISTS study_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT NOT NULL,
    title TEXT NOT NULL,
    material_type TEXT NOT NULL,
    uploaded_date TEXT NOT NULL
);

-- 12. Examinations
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

-- 13. Fees Ledger
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

CREATE INDEX IF NOT EXISTS idx_fees_student ON fees (student_id);

-- 14. Payment Transactions
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

CREATE INDEX IF NOT EXISTS idx_payments_student ON payment_transactions (student_id);

-- 15. Unified Multi-Role Messages Table
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    sender_id INTEGER DEFAULT 1,
    sender_role TEXT DEFAULT 'Student',
    sender_name TEXT NOT NULL,
    receiver_id INTEGER DEFAULT 1,
    receiver_role TEXT DEFAULT 'Faculty',
    receiver_name TEXT NOT NULL,
    subject TEXT NOT NULL,
    content TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_student ON messages (student_id);
CREATE INDEX IF NOT EXISTS idx_messages_receiver ON messages (receiver_role, receiver_id);

-- 16. Parent-Specific Messages
CREATE TABLE IF NOT EXISTS parent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    sender_role TEXT NOT NULL,
    sender_name TEXT NOT NULL,
    receiver_name TEXT NOT NULL,
    subject TEXT NOT NULL,
    content TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES parents (id),
    FOREIGN KEY (student_id) REFERENCES students (id)
);

CREATE INDEX IF NOT EXISTS idx_parent_messages_parent ON parent_messages (parent_id);

-- 17. Central Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id INTEGER NOT NULL,
    recipient_role TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    related_id INTEGER,
    related_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications (recipient_role, recipient_id, is_read);

-- 18. Hostel Details & Leaves
CREATE TABLE IF NOT EXISTS hostel_details (
    student_id INTEGER PRIMARY KEY,
    block_name TEXT NOT NULL,
    room_no TEXT NOT NULL,
    bed_no TEXT NOT NULL,
    warden_name TEXT NOT NULL,
    warden_phone TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students (id)
);

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

CREATE INDEX IF NOT EXISTS idx_hostel_leaves_student ON hostel_leaves (student_id);

-- 19. Placements
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

-- 20. Student Requests
CREATE TABLE IF NOT EXISTS student_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    request_type TEXT NOT NULL,
    details TEXT NOT NULL,
    status TEXT DEFAULT 'Submitted',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students (id)
);

-- 21. Lost & Found
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

-- 22. Wellbeing Appointments
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

-- 23. Safe Walk Sessions
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

-- 24. Login Attempts
CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    register_number TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_reg ON login_attempts (register_number, attempt_time);

-- 25. Complaints
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

CREATE INDEX IF NOT EXISTS idx_complaints_student ON complaints (student_id);
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints (status);

-- 26. Alerts
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_alert_reads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    alert_id INTEGER NOT NULL,
    read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, alert_id),
    FOREIGN KEY (student_id) REFERENCES students (id),
    FOREIGN KEY (alert_id) REFERENCES alerts (id)
);

CREATE TABLE IF NOT EXISTS parent_alert_reads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER NOT NULL,
    alert_id INTEGER NOT NULL,
    read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(parent_id, alert_id),
    FOREIGN KEY (parent_id) REFERENCES parents (id),
    FOREIGN KEY (alert_id) REFERENCES alerts (id)
);

-- 27. Safety Incidents & SOS Events
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

CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status);
CREATE INDEX IF NOT EXISTS idx_incidents_student ON incidents (student_id);

-- 28. Emergency Contacts Directory
CREATE TABLE IF NOT EXISTS emergency_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL,
    role_title TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    location TEXT NOT NULL,
    icon TEXT NOT NULL,
    available_hours TEXT NOT NULL
);

-- 29. Student Settings
CREATE TABLE IF NOT EXISTS student_settings (
    student_id INTEGER PRIMARY KEY,
    email_alerts INTEGER DEFAULT 1,
    sms_alerts INTEGER DEFAULT 1,
    emergency_broadcasts INTEGER DEFAULT 1,
    theme TEXT DEFAULT 'dark',
    FOREIGN KEY (student_id) REFERENCES students (id)
);

-- 30. Announcements
CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    target_audience TEXT NOT NULL,
    author_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 31. Audit & Activity Logs
CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT NOT NULL,
    user_role TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    record_id TEXT,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_activity_logs_created ON activity_logs (created_at DESC);

-- 32. Institutional System Settings
CREATE TABLE IF NOT EXISTS system_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_name TEXT UNIQUE NOT NULL,
    value_text TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 33. Academic Calendar
CREATE TABLE IF NOT EXISTS academic_calendar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    event_type TEXT DEFAULT 'Academic',
    semester TEXT DEFAULT 'Semester 5'
);

-- 34. Placements & Career Drives
CREATE TABLE IF NOT EXISTS placements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    job_role TEXT NOT NULL,
    ctc_package TEXT NOT NULL,
    eligibility_cgpa REAL DEFAULT 7.5,
    eligible_departments TEXT DEFAULT 'CSE, ECE, IT',
    location TEXT DEFAULT 'Bengaluru / Hyderabad',
    deadline DATE NOT NULL,
    drive_date DATE NOT NULL,
    status TEXT DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 35. Comprehensive Campus Emergencies
CREATE TABLE IF NOT EXISTS emergencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emergency_id TEXT UNIQUE NOT NULL,
    user_id INTEGER,
    user_role TEXT DEFAULT 'student',
    reporter_name TEXT NOT NULL,
    reporter_phone TEXT,
    emergency_type TEXT NOT NULL DEFAULT 'Other',
    category TEXT NOT NULL DEFAULT 'Personal Safety',
    severity TEXT NOT NULL DEFAULT 'HIGH',
    description TEXT,
    latitude REAL,
    longitude REAL,
    location_accuracy REAL,
    campus_zone TEXT,
    building TEXT,
    floor TEXT,
    room TEXT,
    status TEXT NOT NULL DEFAULT 'TRIGGERED',
    priority_score INTEGER DEFAULT 80,
    assigned_responder TEXT,
    assigned_responder_type TEXT,
    ai_classification TEXT,
    resolution_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP,
    assigned_at TIMESTAMP,
    response_started_at TIMESTAMP,
    arrived_at TIMESTAMP,
    resolved_at TIMESTAMP,
    closed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_emergencies_status ON emergencies (status);
CREATE INDEX IF NOT EXISTS idx_emergencies_user ON emergencies (user_role, user_id);
CREATE INDEX IF NOT EXISTS idx_emergencies_created ON emergencies (created_at DESC);

-- 36. Emergency Responders
CREATE TABLE IF NOT EXISTS emergency_responders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emergency_id TEXT NOT NULL,
    responder_id TEXT,
    responder_name TEXT NOT NULL,
    responder_role TEXT NOT NULL DEFAULT 'Security Officer',
    phone TEXT,
    status TEXT NOT NULL DEFAULT 'ASSIGNED',
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMP,
    arrived_at TIMESTAMP
);

-- 37. Emergency Notes
CREATE TABLE IF NOT EXISTS emergency_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emergency_id TEXT NOT NULL,
    author_id INTEGER,
    author_name TEXT NOT NULL,
    author_role TEXT NOT NULL DEFAULT 'Security',
    note_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 38. Emergency Notifications
CREATE TABLE IF NOT EXISTS emergency_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emergency_id TEXT NOT NULL,
    recipient_role TEXT NOT NULL,
    recipient_id INTEGER,
    recipient_name TEXT,
    notification_type TEXT NOT NULL DEFAULT 'IN_APP',
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'SENT',
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP
);

-- 39. Emergency Audit Logs
CREATE TABLE IF NOT EXISTS emergency_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emergency_id TEXT NOT NULL,
    user_name TEXT NOT NULL,
    user_role TEXT NOT NULL,
    action TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_emergency_audit ON emergency_audit_logs (emergency_id, timestamp);

