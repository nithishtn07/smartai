"""
CampusGuard AI — Central Database Connection & Initialization Manager
"""

import os
import sqlite3
from .seed import seed_database

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATABASE_FILE = os.path.join(BASE_DIR, 'database.db')


def get_db_path():
    return DATABASE_FILE


def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
    except Exception:
        pass
    return conn


try:
    from flask import g, has_app_context
except ImportError:
    g = None
    has_app_context = lambda: False


def get_db():
    """
    Returns the request-scoped database connection stored in Flask `g`.
    Reuses the open connection throughout the current request lifecycle.
    """
    if has_app_context() and g is not None:
        if 'db' not in g:
            g.db = get_db_connection()
        return g.db
    return get_db_connection()


def close_db(e=None):
    """
    Closes the request-scoped database connection during appcontext teardown.
    """
    if has_app_context() and g is not None:
        db = g.pop('db', None)
        if db is not None:
            db.close()


def init_db():
    """
    Initializes the complete enterprise database schema, applies non-destructive
    column migrations, creates performance indexes, and seeds the baseline demo data.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Read and execute DDL from schema.sql
        schema_file = os.path.join(os.path.dirname(__file__), 'schema.sql')
        if os.path.exists(schema_file):
            with open(schema_file, 'r', encoding='utf-8') as f:
                cursor.executescript(f.read())
        
        # Run dynamic column migrations for existing tables to guarantee zero-breakage
        _apply_column_migrations(cursor)
        conn.commit()

        # Seed baseline demo data
        seed_database(conn)
    except Exception as e:
        print(f"[Database Init Warning] {e}")
    finally:
        conn.close()


def _apply_column_migrations(cursor):
    """
    Ensures newly added columns are present in tables created in prior versions.
    """
    # 1. Students table migrations
    existing_stu_cols = {row[1] for row in cursor.execute("PRAGMA table_info(students)").fetchall()}
    stu_cols = {
        'program': "TEXT DEFAULT 'B.Tech'",
        'semester': "INTEGER DEFAULT 1",
        'section': "TEXT DEFAULT 'A'",
        'phone': "TEXT DEFAULT ''",
        'dob': "TEXT DEFAULT ''",
        'address': "TEXT DEFAULT ''",
        'parent_name': "TEXT DEFAULT ''",
        'parent_phone': "TEXT DEFAULT ''",
        'join_date': "TEXT DEFAULT ''",
        'cgpa': "REAL DEFAULT 0.0",
        'sgpa': "REAL DEFAULT 0.0",
        'earned_credits': "INTEGER DEFAULT 0",
        'total_credits': "INTEGER DEFAULT 160",
        'profile_image': "TEXT DEFAULT ''",
        'status': "TEXT DEFAULT 'ACTIVE'"
    }
    for col, defn in stu_cols.items():
        if col not in existing_stu_cols:
            try:
                cursor.execute(f"ALTER TABLE students ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass

    # 2. Incidents table migrations
    existing_inc_cols = {row[1] for row in cursor.execute("PRAGMA table_info(incidents)").fetchall()}
    inc_cols = {
        'assigned_to': "TEXT DEFAULT 'Unassigned'",
        'priority_score': "INTEGER DEFAULT 50"
    }
    for col, defn in inc_cols.items():
        if col not in existing_inc_cols:
            try:
                cursor.execute(f"ALTER TABLE incidents ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass

    # 3. Messages table migrations
    existing_msg_cols = {row[1] for row in cursor.execute("PRAGMA table_info(messages)").fetchall()}
    msg_cols = {
        'sender_id': "INTEGER DEFAULT 1",
        'sender_role': "TEXT DEFAULT 'Student'",
        'receiver_id': "INTEGER DEFAULT 1",
        'receiver_role': "TEXT DEFAULT 'Faculty'",
        'is_read': "INTEGER DEFAULT 0",
        'sent_at': "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        'timestamp': "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    }
    for col, defn in msg_cols.items():
        if col not in existing_msg_cols:
            try:
                cursor.execute(f"ALTER TABLE messages ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass

    # 4. Assignments table migrations
    existing_assign_cols = {row[1] for row in cursor.execute("PRAGMA table_info(assignments)").fetchall()}
    assign_cols = {
        'course_name': "TEXT",
        'created_at': "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    }
    for col, defn in assign_cols.items():
        if col not in existing_assign_cols:
            try:
                cursor.execute(f"ALTER TABLE assignments ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass

    # 5. Parents table migrations (Profile management fields)
    existing_parent_cols = {row[1] for row in cursor.execute("PRAGMA table_info(parents)").fetchall()}
    parent_cols = {
        'alt_phone': "TEXT DEFAULT ''",
        'city': "TEXT DEFAULT ''",
        'state': "TEXT DEFAULT ''",
        'country': "TEXT DEFAULT 'India'",
        'postal_code': "TEXT DEFAULT ''",
        'profile_image': "TEXT DEFAULT ''"
    }
    for col, defn in parent_cols.items():
        if col not in existing_parent_cols:
            try:
                cursor.execute(f"ALTER TABLE parents ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass

    # 6. Fees table migrations
    existing_fee_cols = {row[1] for row in cursor.execute("PRAGMA table_info(fees)").fetchall()}
    fee_cols = {
        'academic_year': "TEXT DEFAULT '2026-2027'",
        'semester': "INTEGER DEFAULT 5"
    }
    for col, defn in fee_cols.items():
        if col not in existing_fee_cols:
            try:
                cursor.execute(f"ALTER TABLE fees ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass

    # 7. Complaints table migrations
    existing_comp_cols = {row[1] for row in cursor.execute("PRAGMA table_info(complaints)").fetchall()}
    comp_cols = {
        'faculty_id': "INTEGER DEFAULT NULL",
        'sender_role': "TEXT DEFAULT 'Student'",
        'sender_name': "TEXT DEFAULT ''",
        'resolution_notes': "TEXT DEFAULT ''"
    }
    for col, defn in comp_cols.items():
        if col not in existing_comp_cols:
            try:
                cursor.execute(f"ALTER TABLE complaints ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass

    # 8. Payment Transactions table migrations (Payment Gateway fields)
    existing_txn_cols = {row[1] for row in cursor.execute("PRAGMA table_info(payment_transactions)").fetchall()}
    txn_cols = {
        'order_id': "TEXT DEFAULT ''",
        'gateway_payment_id': "TEXT DEFAULT ''",
        'gateway_signature': "TEXT DEFAULT ''",
        'status': "TEXT DEFAULT 'SUCCESS'",
        'parent_id': "INTEGER DEFAULT NULL",
        'fee_id': "INTEGER DEFAULT NULL"
    }
    for col, defn in txn_cols.items():
        if col not in existing_txn_cols:
            try:
                cursor.execute(f"ALTER TABLE payment_transactions ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass

    # 9. Student Submissions table migrations
    existing_sub_cols = {row[1] for row in cursor.execute("PRAGMA table_info(student_submissions)").fetchall()}
    sub_cols = {
        'submission_text': "TEXT DEFAULT ''",
        'attachment_url': "TEXT DEFAULT ''",
        'graded_at': "TIMESTAMP DEFAULT NULL"
    }
    for col, defn in sub_cols.items():
        if col not in existing_sub_cols:
            try:
                cursor.execute(f"ALTER TABLE student_submissions ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass

    # 10. Attendance Logs table migrations
    existing_att_log_cols = {row[1] for row in cursor.execute("PRAGMA table_info(attendance_logs)").fetchall()}
    att_log_cols = {
        'faculty_id': "INTEGER DEFAULT 1",
        'created_at': "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        'updated_at': "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    }
    for col, defn in att_log_cols.items():
        if col not in existing_att_log_cols:
            try:
                cursor.execute(f"ALTER TABLE attendance_logs ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass

    # 10.5. Marks table migrations
    existing_marks_cols = {row[1] for row in cursor.execute("PRAGMA table_info(marks)").fetchall()}
    marks_cols = {
        'is_demo': "INTEGER DEFAULT 0",
        'created_at': "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        'updated_at': "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    }
    for col, defn in marks_cols.items():
        if col not in existing_marks_cols:
            try:
                cursor.execute(f"ALTER TABLE marks ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_att_logs_unique ON attendance_logs (student_id, course_code, date)
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_att_unique ON attendance (student_id, subject_code)
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_marks_unique ON marks (student_id, course_code)
    """)

    # 11. Dynamic creation of extended enterprise tables if missing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lab_experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT NOT NULL,
            student_id INTEGER NOT NULL,
            experiment_no INTEGER NOT NULL,
            title TEXT NOT NULL,
            conducted_date TEXT NOT NULL,
            practical_marks REAL DEFAULT 0.0,
            viva_marks REAL DEFAULT 0.0,
            record_status TEXT DEFAULT 'Verified',
            faculty_remarks TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transport_routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_number TEXT UNIQUE NOT NULL,
            route_name TEXT NOT NULL,
            bus_number TEXT NOT NULL,
            driver_name TEXT NOT NULL,
            driver_phone TEXT NOT NULL,
            pickup_time TEXT NOT NULL,
            pickup_location TEXT NOT NULL,
            eta_campus TEXT NOT NULL,
            stops_json TEXT DEFAULT '[]',
            status TEXT DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_transport (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER UNIQUE NOT NULL,
            route_id INTEGER NOT NULL,
            boarding_stop TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE',
            allocated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id),
            FOREIGN KEY (route_id) REFERENCES transport_routes (id)
        )
    """)

    # 10. Parent-Student Mapping Table (Multi-Child / Relational Mapping)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parent_student (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            relationship TEXT DEFAULT 'Guardian',
            is_primary INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(parent_id, student_id),
            FOREIGN KEY (parent_id) REFERENCES parents (id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_parent_student_parent ON parent_student (parent_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_parent_student_student ON parent_student (student_id)")

    # Backfill legacy parents.student_id into parent_student if any exist without mapping
    cursor.execute("""
        INSERT OR IGNORE INTO parent_student (parent_id, student_id, relationship, is_primary)
        SELECT id, student_id, COALESCE(relationship, 'Guardian'), 1
        FROM parents
        WHERE student_id IS NOT NULL AND student_id > 0
    """)

    # 12. Synchronize CGPA from real marks
    try:
        from services.academic_service import sync_student_cgpa
        conn_ref = cursor.connection if hasattr(cursor, 'connection') else None
        if conn_ref:
            all_students = cursor.execute("SELECT id FROM students").fetchall()
            for s_row in all_students:
                sync_student_cgpa(conn_ref, s_row['id'])
    except Exception as e:
        print(f"[DB CGPA Sync Warning] {e}")



