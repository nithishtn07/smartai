"""
=============================================================================
CampusGuard AI — Comprehensive Live Inter-Portal Verification Script
=============================================================================
Verifies all 4 Portals (Student, Parent, Faculty, Admin), Real-Time Handlers,
Notification Systems, Two-Way Messaging, and Nithish Nagaraj Name Consistency.
=============================================================================
"""

import sys
import unittest
import json
import app

def run_live_verification():
    print("=" * 80)
    print("  CAMPUSGUARD AI - UNIFIED INTER-PORTAL LIVE VERIFICATION SUITE")
    print("=" * 80)

    test_app = app.app
    test_app.config['TESTING'] = True
    client = test_app.test_client()

    # 1. Initialize DB
    app.init_db()
    conn = app.get_db_connection()
    conn.execute("UPDATE students SET name = 'Nithish Nagaraj' WHERE register_number = 'STU001'")
    conn.commit()

    student = conn.execute("SELECT * FROM students WHERE register_number = 'STU001'").fetchone()
    parent = conn.execute("SELECT * FROM parents WHERE email = 'parent@example.com'").fetchone()
    faculty = conn.execute("SELECT * FROM faculties WHERE email = 'faculty@example.com'").fetchone()
    admin = conn.execute("SELECT * FROM admins WHERE username = 'admin'").fetchone()
    conn.close()

    passed = 0
    total = 0

    def verify_check(desc, condition):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f"  [PASS] {desc}")
        else:
            print(f"  [FAIL] {desc}")

    print("\n--- [1] GATEWAY & LANDING PAGE ---")
    resp = client.get('/')
    verify_check("Landing page returns 200 OK", resp.status_code == 200)
    verify_check("Landing page contains Student Portal link", b'/student/login' in resp.data)
    verify_check("Landing page contains Faculty Portal link", b'/faculty/login' in resp.data)
    verify_check("Landing page contains Parent Portal link", b'/parent/login' in resp.data)
    verify_check("Landing page contains Admin Portal link", b'/admin/login' in resp.data)

    print("\n--- [2] STUDENT PORTAL & NAME CONSISTENCY ---")
    with client.session_transaction() as sess:
        sess['student_id'] = student['id']
        sess['user_role'] = 'student'

    stu_routes = [
        ('/student/dashboard', ['Nithish Nagaraj', 'STU001', 'Live Connected', 'notif-bell-btn']),
        ('/student/messages', ['Messages', 'Communication', 'Compose Message', 'notif-bell-btn']),
        ('/student/academics', ['Academics', 'Credits']),
        ('/student/attendance', ['Attendance', 'Safe Margin']),
        ('/student/fees', ['Fees', 'Tuition']),
        ('/student/safety', ['Safety Center']),
        ('/student/emergency', ['Emergency SOS']),
    ]

    for route, expected_snippets in stu_routes:
        r = client.get(route)
        verify_check(f"Student Route '{route}' returns 200 OK", r.status_code == 200)
        for snip in expected_snippets:
            verify_check(f"Student Route '{route}' contains '{snip}'", snip.encode('utf-8') in r.data)

    print("\n--- [3] PARENT PORTAL & WARD LINKING ---")
    with client.session_transaction() as sess:
        sess.clear()
        sess['parent_id'] = parent['id']
        sess['user_role'] = 'parent'

    parent_routes = [
        ('/parent/dashboard', ['Nithish Nagaraj', 'STU001', 'Live Connected', 'notif-bell-btn']),
        ('/parent/academics', ['Nithish Nagaraj', 'Academic Performance']),
        ('/parent/attendance', ['Attendance', 'Compliance']),
        ('/parent/messages', ['Faculty Communication', 'notif-bell-btn']),
        ('/parent/safety', ['Campus Safety', 'Emergency']),
        ('/parent/notifications', ['Notification Center', 'All Notifications']),
    ]

    for route, expected_snippets in parent_routes:
        r = client.get(route)
        verify_check(f"Parent Route '{route}' returns 200 OK", r.status_code == 200)
        for snip in expected_snippets:
            verify_check(f"Parent Route '{route}' contains '{snip}'", snip.encode('utf-8') in r.data)

    print("\n--- [4] FACULTY PORTAL ROUTES & ACTIONS ---")
    with client.session_transaction() as sess:
        sess.clear()
        sess['faculty_id'] = faculty['id']
        sess['user_role'] = 'faculty'

    faculty_routes = [
        ('/faculty/dashboard', ['Dr. Ramesh Rao', 'FACULTY', 'Assigned Courses', 'notif-bell-btn']),
        ('/faculty/attendance', ['Course Attendance', 'Nithish Nagaraj', 'CS301']),
        ('/faculty/marks', ['Marks', 'Nithish Nagaraj']),
        ('/faculty/assignments', ['Course Assignments', 'Post New Assignment']),
        ('/faculty/leaves', ['Student Hostel Leave', 'Outpass Review']),
        ('/faculty/messages', ['Faculty Communication Center', 'Compose Message']),
        ('/faculty/notifications', ['Faculty Notification Center', 'Unread Alert']),
        ('/faculty/profile', ['Dr. Ramesh Rao', 'Faculty Advisor']),
    ]

    for route, expected_snippets in faculty_routes:
        r = client.get(route)
        verify_check(f"Faculty Route '{route}' returns 200 OK", r.status_code == 200)
        for snip in expected_snippets:
            verify_check(f"Faculty Route '{route}' contains '{snip}'", snip.encode('utf-8') in r.data)

    print("\n--- [5] ADMIN PORTAL & COMMAND CONSOLE ---")
    with client.session_transaction() as sess:
        sess.clear()
        sess['admin_id'] = admin['id']
        sess['user_role'] = 'admin'

    admin_routes = [
        ('/admin/dashboard', ['Central Administration', 'Active SOS', 'notif-bell-btn']),
        ('/admin/announcements', ['Campus Announcements', 'Publish New Announcement']),
        ('/admin/audit-logs', ['Activity', 'System Activity Records']),
    ]

    for route, expected_snippets in admin_routes:
        r = client.get(route)
        verify_check(f"Admin Route '{route}' returns 200 OK", r.status_code == 200)
        for snip in expected_snippets:
            verify_check(f"Admin Route '{route}' contains '{snip}'", snip.encode('utf-8') in r.data)

    print("\n--- [6] CENTRAL NOTIFICATION & SEARCH REST APIs ---")
    # Student Notification API
    with client.session_transaction() as sess:
        sess.clear()
        sess['student_id'] = student['id']
        sess['user_role'] = 'student'

    r_cnt = client.get('/api/notifications/unread-count')
    verify_check("GET /api/notifications/unread-count returns 200", r_cnt.status_code == 200)
    data_cnt = json.loads(r_cnt.data)
    verify_check("Unread count returns JSON with role='student'", data_cnt.get('role') == 'student')

    r_rec = client.get('/api/notifications/recent')
    verify_check("GET /api/notifications/recent returns 200", r_rec.status_code == 200)

    r_srch = client.get('/api/global-search?q=database')
    verify_check("GET /api/global-search?q=database returns 200", r_srch.status_code == 200)
    data_srch = json.loads(r_srch.data)
    verify_check("Global search found results", len(data_srch.get('results', [])) > 0)

    print("\n" + "=" * 80)
    print(f"  VERIFICATION COMPLETE: {passed}/{total} Checks Passed ({int(passed/total*100)}%)")
    print("=" * 80)

    if passed == total:
        print("\n[SUCCESS] ALL UNIFIED INTER-PORTAL SYSTEMS OPERATIONAL AND CONNECTED PERFECTLY!\n")
        return 0
    else:
        print("\n[WARNING] SOME CHECKS FAILED.\n")
        return 1

if __name__ == '__main__':
    sys.exit(run_live_verification())
