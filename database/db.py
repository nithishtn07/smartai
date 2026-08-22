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
    """
    Establishes and returns an optimized connection to the central SQLite database.
    Row factory is set to sqlite3.Row so columns can be accessed by name or index.
    """
    conn = sqlite3.connect(DATABASE_FILE, timeout=20.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Initializes the complete enterprise database schema, applies non-destructive
    column migrations, creates performance indexes, and seeds the baseline demo data.
    """
    conn = get_db_connection()
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

    conn.close()


def _apply_column_migrations(cursor):
    """
    Ensures newly added columns are present in tables created in prior versions.
    """
    # 1. Students table migrations
    existing_stu_cols = {row[1] for row in cursor.execute("PRAGMA table_info(students)").fetchall()}
    stu_cols = {
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
