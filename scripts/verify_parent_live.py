"""
End-to-End Live HTTP Integration Test for CampusGuard AI Parent Portal
Tests the active running server at http://127.0.0.1:5000
"""
import urllib.request
import urllib.parse
import http.cookiejar
import json
import re

BASE_URL = "http://127.0.0.1:5000"

def test_live_parent_flow():
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    
    print("\n--- 1. Testing Landing Page (/) ---")
    resp = opener.open(f"{BASE_URL}/")
    assert resp.status == 200
    html = resp.read().decode('utf-8')
    assert 'href="/parent/login"' in html
    assert 'Parent Portal' in html
    print("[PASS] Landing page loads with valid Parent Portal link.")

    print("\n--- 2. Testing Parent Login Page (/parent/login) ---")
    resp = opener.open(f"{BASE_URL}/parent/login")
    assert resp.status == 200
    html = resp.read().decode('utf-8')
    assert 'Parent Portal Sign In' in html
    assert 'parent@example.com' in html
    assert 'Parent@123' in html
    print("[PASS] Parent login page loads with form and demo credentials.")

    print("\n--- 3. Submitting Valid Parent Login ---")
    login_data = urllib.parse.urlencode({
        'identifier': 'parent@example.com',
        'password': 'Parent@123',
        'remember': '1'
    }).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/parent/login", data=login_data)
    resp = opener.open(req)
    assert resp.status == 200
    html = resp.read().decode('utf-8')
    assert 'Nithish Nagaraj' in html
    assert 'STU001' in html
    assert 'Computer Science' in html
    print("[PASS] Parent successfully authenticated and redirected to Dashboard.")

    print("\n--- 4. Testing All 11 Parent Modules ---")
    routes_to_test = [
        ('/parent/dashboard', ['Nithish Nagaraj', 'Attendance', 'CGPA']),
        ('/parent/academics', ['Database Management Systems', 'CAT 1', 'Grade']),
        ('/parent/attendance', ['Attendance Analytics', 'Safe Absence Margin', 'Conducted']),
        ('/parent/fees', ['Fee Dues &amp; Payment Ledger', 'Total Semester Dues', 'Receipt']),
        ('/parent/exams', ['FAT Semester 5', 'Upcoming Examinations Timetable', 'Hall Ticket']),
        ('/parent/timetable', ['Weekly Class Timetable', 'Monday', 'Classroom']),
        ('/parent/leave', ['Hostel Leave &amp; Digital Outpasses', 'Block B', 'Warden']),
        ('/parent/notifications', ['Parent Notification Center', 'Emergency &amp; Safety', 'Announcements']),
        ('/parent/safety', ['Campus Safety &amp; Emergency Command', 'Campus Security Command Center', 'Helplines']),
        ('/parent/messages', ['Parent-Faculty Communication Center', 'Dr. Ramesh Rao', 'Compose Message']),
        ('/parent/profile', ['Parent Profile &amp; Account Settings', 'Nagaraj', 'Linked Ward Profile'])
    ]

    for route, expected_snippets in routes_to_test:
        resp = opener.open(f"{BASE_URL}{route}")
        assert resp.status == 200, f"Failed on {route}"
        page_html = resp.read().decode('utf-8')
        for snippet in expected_snippets:
            assert snippet in page_html, f"Snippet '{snippet}' not found on {route}"
        print(f"[PASS] {route} verified with all expected content.")

    print("\n--- 5. Testing Parent-Faculty Message Transmission ---")
    msg_data = urllib.parse.urlencode({
        'receiver_name': 'Dr. Ramesh Rao (Faculty Advisor)',
        'subject': 'Live Verification Message from Parent',
        'content': 'Confirming live transmission test from Parent Portal.'
    }).encode('utf-8')
    msg_req = urllib.request.Request(f"{BASE_URL}/parent/messages", data=msg_data)
    resp = opener.open(msg_req)
    assert resp.status == 200
    html = resp.read().decode('utf-8')
    assert 'Live Verification Message from Parent' in html
    print("[PASS] Live message transmission verified.")

    print("\n--- 6. Testing Parent Logout (/parent/logout) ---")
    resp = opener.open(f"{BASE_URL}/parent/logout")
    assert resp.status == 200
    html = resp.read().decode('utf-8')
    assert 'Parent Portal Sign In' in html
    print("[PASS] Parent logout successfully clears session.")

    print("\n--- 7. Testing Student Portal Regression (/student/login) ---")
    student_login_data = urllib.parse.urlencode({
        'register_number': 'STU001',
        'password': 'Student@123'
    }).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/student/login", data=student_login_data)
    resp = opener.open(req)
    assert resp.status == 200
    html = resp.read().decode('utf-8')
    assert 'Nithish Nagaraj' in html
    assert 'Computer Science' in html
    print("[PASS] Student Portal login and dashboard remain 100% operational.")

    print("\n=======================================================")
    print("ALL LIVE INTEGRATION TESTS PASSED WITH 100% SUCCESS!")
    print("=======================================================\n")

if __name__ == '__main__':
    test_live_parent_flow()
