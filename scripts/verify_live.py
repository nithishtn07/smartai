import urllib.request
import urllib.parse
import http.cookiejar
import json

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# 1. Login
data_valid = urllib.parse.urlencode({'register_number': 'STU001', 'password': 'Student@123'}).encode()
r = opener.open('http://127.0.0.1:5000/student/login', data=data_valid).read().decode()
assert 'Nithish' in r, 'Dashboard login failed'
print('[PASS] Live HTTP: /student/dashboard')

# 2. Check all 24 pages
pages = [
    ('/student/profile', 'Digital Campus Smart ID'),
    ('/student/academics', 'Academics &amp; Registered Courses'),
    ('/student/marks', 'Academic Marks &amp; Performance'),
    ('/student/attendance', 'Attendance Analytics &amp; Safe Margin'),
    ('/student/timetable', 'Academic Timetable'),
    ('/student/assignments', 'Course Assignments &amp; Study Repository'),
    ('/student/examinations', 'Examinations, Hall Tickets &amp; Transcripts'),
    ('/student/fees', 'Student Fees &amp; Payments Ledger'),
    ('/student/calendar', 'Unified Campus &amp; Academic Calendar'),
    ('/student/hostel', 'Hostel Administration &amp; Mess Services'),
    ('/student/safewalk', 'Safe Walk Companion'),
    ('/student/transport', 'Campus Transport &amp; Live Bus Tracking'),
    ('/student/placements', 'Placements, Internships &amp; AI Resume Suite'),
    ('/student/requests', 'Administrative Requests &amp; Certificate Services'),
    ('/student/lost-found', 'Campus Lost &amp; Found Directory'),
    ('/student/wellbeing', 'Student Health &amp; Wellbeing Center'),
    ('/student/communication', 'Communication Center &amp; Faculty Connect'),
    ('/student/alerts', 'Campus Alerts'),
    ('/student/safety', 'Campus Safety Center'),
    ('/student/campus-map', 'Campus Safety Map &amp; Monitored Safe Routes'),
    ('/student/emergency', 'Emergency SOS'),
    ('/student/assistant', 'AI Campus Assistant'),
    ('/student/settings', 'Portal Settings'),
    ('/security/dashboard', 'SECURITY COMMAND'),
    ('/admin/analytics', 'Institutional Campus Safety Briefing')
]

for url_path, marker in pages:
    content = opener.open('http://127.0.0.1:5000' + url_path).read().decode()
    assert marker in content, f'Marker "{marker}" not found in {url_path}'
    print(f'[PASS] Live HTTP: {url_path}')

print('\nALL 24 LIVE HTTP ENDPOINTS TESTED & ACCESSIBLE!')
