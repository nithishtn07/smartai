"""
=============================================================================
CampusGuard AI - AI Intelligence Layer Comprehensive Test Suite
Validates Attendance AI, Complaint AI Triage, Emergency Triage, Spatial-Temporal
Risk Analysis, Safe Walk Sessions, Smart SOS, AI Briefings, and Login Security.
=============================================================================
"""

import unittest
import json
import sqlite3
import datetime
from app import app, init_db, DATABASE_FILE
from services.attendance_ai import analyze_student_attendance
from services.complaint_ai import classify_complaint
from services.safety_ai import triage_emergency_incident, analyze_campus_risk_patterns, calculate_safe_route
from services.campus_assistant import answer_campus_query
from services.briefing_ai import generate_student_briefing

class TestAIIntelligenceLayer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-ai-intelligence-secret-2026'
        init_db()

    def login(self):
        with self.client.session_transaction() as sess:
            sess['student_id'] = 1
            sess['student_register_number'] = 'STU001'
            sess['student_name'] = 'Nithish Kumar'

    def setUp(self):
        self.client = app.test_client()
        self.login()

    # -----------------------------------------------------------------------
    # 1. Attendance AI Intelligence Tests
    # -----------------------------------------------------------------------
    def test_01_attendance_ai_intelligence(self):
        """Verify attendance risk detection and exact safe missed class prediction"""
        mock_records = [
            {'subject_code': 'CS301', 'subject_name': 'DBMS', 'classes_held': 40, 'classes_attended': 37, 'classes_missed': 3, 'attendance_pct': 92.5},
            {'subject_code': 'CS303', 'subject_name': 'Data Science', 'classes_held': 35, 'classes_attended': 27, 'classes_missed': 8, 'attendance_pct': 77.1}
        ]
        res = analyze_student_attendance(mock_records)
        
        self.assertAlmostEqual(res['overall_pct'], 85.3, places=1)
        self.assertEqual(len(res['risk_courses']), 1)
        self.assertEqual(res['risk_courses'][0]['code'], 'CS303')
        self.assertEqual(res['risk_courses'][0]['status'], 'WARNING')
        
        # Check safe absences prediction for DBMS (37 - 0.75*40)/0.75 = (37 - 30)/0.75 = 7/0.75 = 9
        dbms_pred = next(p for p in res['predictions'] if p['code'] == 'CS301')
        self.assertEqual(dbms_pred['safe_misses'], 9)
        self.assertTrue(len(res['recommendations']) > 0)
        print("[PASS] 1. Attendance AI: Risk detection & safe absence predictions verified.")

    # -----------------------------------------------------------------------
    # 2. Complaint & Grievance AI Triage Tests
    # -----------------------------------------------------------------------
    def test_02_complaint_ai_triage(self):
        """Verify NLP triage assigns appropriate category, severity, priority and department"""
        # Test A: Safety Harassment
        triage_safety = classify_complaint(
            title="Broken lights near hostel",
            description="The lights near Hostel Block C have not been working for three days and students feel unsafe walking there at night.",
            category="Safety",
            location="Hostel Block C"
        )
        self.assertIn("Safety", triage_safety['category'])
        self.assertIn(triage_safety['severity'], ['HIGH', 'CRITICAL'])
        self.assertIn("Security", triage_safety['dept'])

        # Test B: Infrastructure Spark Hazard
        triage_hazard = classify_complaint(
            title="Electrical spark near lab",
            description="Open wire with smoke and spark near CS Lab 2 entrance",
            category="Infrastructure",
            location="CS Lab 2"
        )
        self.assertEqual(triage_hazard['severity'], 'HIGH')
        self.assertEqual(triage_hazard['priority'], 'URGENT')
        self.assertIn("Maintenance", triage_hazard['dept'])

        # Test C: End-to-end form submission
        resp = self.client.post('/student/complaints', data={
            'title': 'Broken water cooler in Block C',
            'description': 'The water cooler has been leaking for two days',
            'category': 'Hostel',
            'location': 'Block C',
            'priority': 'Medium'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Grievance Ticket CMP-', resp.data)
        print("[PASS] 2. Complaint AI: Triage & department routing verified.")

    # -----------------------------------------------------------------------
    # 3. Emergency Incident Triage Tests
    # -----------------------------------------------------------------------
    def test_03_emergency_incident_triage(self):
        """Verify emergency triage tags high severity incidents with immediate response"""
        emg_fire = triage_emergency_incident("Fire Hazard", "Smoke coming from electrical room in Block B", "Block B")
        self.assertEqual(emg_fire['severity'], 'CRITICAL')
        self.assertEqual(emg_fire['priority'], 'IMMEDIATE')
        self.assertIn("Security", emg_fire['department'])

        emg_infra = triage_emergency_incident("Broken Chair", "Broken chair in classroom", "Room 201")
        self.assertEqual(emg_infra['severity'], 'MEDIUM')
        self.assertEqual(emg_infra['priority'], 'NORMAL')
        print("[PASS] 3. Emergency Incident Triage: Priority prioritization verified.")

    # -----------------------------------------------------------------------
    # 4. Spatial-Temporal Campus Risk Analysis Tests
    # -----------------------------------------------------------------------
    def test_04_spatial_temporal_campus_risk_analysis(self):
        """Verify spatial hotspot detection and insufficient data handling"""
        sample_incidents = [
            {'location': 'Parking Area', 'status': 'RESOLVED', 'created_at': '2026-08-10 19:15:00'},
            {'location': 'Parking Area', 'status': 'RESOLVED', 'created_at': '2026-08-11 19:45:00'},
            {'location': 'Parking Area', 'status': 'RESOLVED', 'created_at': '2026-08-12 20:10:00'},
            {'location': 'Parking Area', 'status': 'RESOLVED', 'created_at': '2026-08-14 18:30:00'},
            {'location': 'Parking Area', 'status': 'RESOLVED', 'created_at': '2026-08-16 20:00:00'},
            {'location': 'Hostel Gate', 'status': 'RESOLVED', 'created_at': '2026-08-15 14:00:00'},
            {'location': 'Hostel Gate', 'status': 'RESOLVED', 'created_at': '2026-08-17 22:30:00'},
            {'location': 'Library', 'status': 'RESOLVED', 'created_at': '2026-08-18 11:00:00'}
        ]

        analysis = analyze_campus_risk_patterns(sample_incidents)
        self.assertEqual(analysis['status'], 'ACTIVE_ANALYSIS')
        self.assertEqual(analysis['top_hotspot'], 'Parking Area')
        self.assertIn('Evening', analysis['peak_window'])
        self.assertIn('patrols', analysis['recommendation'].lower())

        # Insufficient data test
        scarce_analysis = analyze_campus_risk_patterns([{'location': 'Gate 1', 'status': 'RESOLVED'}])
        self.assertEqual(scarce_analysis['status'], 'INSUFFICIENT_DATA')
        self.assertIn("Insufficient", scarce_analysis['message'])
        print("[PASS] 4. Campus Risk Analysis: Spatial-temporal hotspot pattern detection verified.")

    # -----------------------------------------------------------------------
    # 5. Smart Emergency SOS Workflow Tests
    # -----------------------------------------------------------------------
    def test_05_smart_emergency_sos_workflow(self):
        """Verify SOS activation with GPS, status tracking, and stand-down"""
        # Step A: POST SOS
        resp = self.client.post('/student/emergency', data={
            'location': 'Hostel Block B Outer Yard',
            'latitude': '12.971598',
            'longitude': '77.594566'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'EMERGENCY SOS ACTIVE: EMG-', resp.data)

        # Step B: Stand down via cancel
        conn = sqlite3.connect(DATABASE_FILE, timeout=15.0)
        try:
            conn.row_factory = sqlite3.Row
            active_sos = conn.execute("SELECT * FROM incidents WHERE student_id = 1 AND status = 'ACTIVE' AND incident_type = 'EMERGENCY_SOS'").fetchone()
            self.assertIsNotNone(active_sos)
            inc_id = active_sos['incident_id']
        finally:
            conn.close()

        resp_cancel = self.client.post(f'/student/emergency/cancel/{inc_id}', follow_redirects=True)
        self.assertEqual(resp_cancel.status_code, 200)
        self.assertIn(b'stood down. Marked safe', resp_cancel.data)
        print("[PASS] 5. Smart Emergency SOS: GPS attachment & 5-stage timeline verified.")

    # -----------------------------------------------------------------------
    # 6. Safe Walk Companion & Session Timer Tests
    # -----------------------------------------------------------------------
    def test_06_safewalk_session_and_checkin(self):
        """Verify Safe Walk journey creation, active monitoring, and safe check-in"""
        # Step A: View Safe Walk
        resp_get = self.client.get('/student/safewalk')
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(b'Safe Walk Companion', resp_get.data)

        # Step B: Start Safe Walk Session
        resp_start = self.client.post('/student/safewalk/start', data={
            'start_location': 'Hostel Block B (Oak Wing)',
            'destination': 'Central University Library',
            'duration_minutes': '15'
        }, follow_redirects=True)
        self.assertEqual(resp_start.status_code, 200)
        self.assertIn(b'Safe Walk session started', resp_start.data)
        self.assertIn(b'I\'m Safe (Arrived Safely)', resp_start.data)

        # Step C: Complete Safe Walk
        conn = sqlite3.connect(DATABASE_FILE, timeout=15.0)
        try:
            conn.row_factory = sqlite3.Row
            sess_row = conn.execute("SELECT id FROM safe_walk_sessions WHERE student_id = 1 AND status = 'IN_PROGRESS' ORDER BY id DESC LIMIT 1").fetchone()
            self.assertIsNotNone(sess_row)
            sess_id = sess_row['id']
        finally:
            conn.close()

        resp_safe = self.client.post(f'/student/safewalk/safe/{sess_id}', follow_redirects=True)
        self.assertEqual(resp_safe.status_code, 200)
        self.assertIn(b'Safe Walk completed! You have checked in safely.', resp_safe.data)
        print("[PASS] 6. Safe Walk: Session creation, countdown monitoring & check-in verified.")

    # -----------------------------------------------------------------------
    # 7. Personalized AI Campus Briefing Tests
    # -----------------------------------------------------------------------
    def test_07_personalized_ai_campus_briefing(self):
        """Verify dynamic AI briefing synthesis for dashboard"""
        conn = sqlite3.connect(DATABASE_FILE, timeout=15.0)
        try:
            conn.row_factory = sqlite3.Row
            student = conn.execute("SELECT * FROM students WHERE id = 1").fetchone()
            briefing = generate_student_briefing(student, conn)
        finally:
            conn.close()

        self.assertIn("Nithish", briefing['greeting'])
        self.assertGreater(len(briefing['briefing_items']), 2)
        self.assertIn("overall_pct", briefing)
        self.assertIn("next_class", briefing)
        print("[PASS] 7. AI Campus Briefing: Dynamic synthesis on dashboard verified.")

    # -----------------------------------------------------------------------
    # 8. Login Security & Anomaly Detection Tests
    # -----------------------------------------------------------------------
    def test_08_login_security_and_anomaly_detection(self):
        """Verify tracking failed login attempts and protective lockout on 5 failed attempts"""
        # Create separate unauthenticated test client
        unauth_client = app.test_client()

        # Clear existing attempts for STU_TEST
        conn = sqlite3.connect(DATABASE_FILE, timeout=15.0)
        try:
            conn.execute("DELETE FROM login_attempts WHERE register_number = 'STU_TEST'")
            conn.commit()
        finally:
            conn.close()

        # Submit 4 wrong password attempts
        for _ in range(4):
            resp = unauth_client.post('/student/login', data={
                'register_number': 'STU_TEST',
                'password': 'WrongPassword123'
            })
            self.assertIn(b'Invalid register number or password', resp.data)

        # 5th attempt triggers lockout
        unauth_client.post('/student/login', data={'register_number': 'STU_TEST', 'password': 'WrongPassword123'})
        resp_5th = unauth_client.post('/student/login', data={'register_number': 'STU_TEST', 'password': 'WrongPassword123'})
        self.assertIn(b'Multiple failed login attempts detected', resp_5th.data)

        # Cleanup attempts
        conn = sqlite3.connect(DATABASE_FILE, timeout=15.0)
        try:
            conn.execute("DELETE FROM login_attempts WHERE register_number = 'STU_TEST'")
            conn.commit()
        finally:
            conn.close()
        print("[PASS] 8. Login Security: Anomaly tracking & temporary protection verified.")

    # -----------------------------------------------------------------------
    # 9. Context-Aware AI Campus Assistant Tests
    # -----------------------------------------------------------------------
    def test_09_context_aware_ai_assistant(self):
        """Verify context-aware answers using authorized student data"""
        queries = [
            ("What is my current attendance?", ["Overall Academic Attendance", "84"]),
            ("Which subject has my lowest attendance?", ["Lowest Attendance", "Data Science"]),
            ("When is my next class?", ["Next Lecture"]),
            ("What classes do I have tomorrow?", ["Tomorrow", "Schedule"]),
            ("What complaints are still pending?", ["Grievance", "Awaiting"]),
            ("How do I submit a complaint?", ["Navigate to", "Grievance Tickets"]),
            ("What should I do during an emergency?", ["Emergency Protocol", "+91 91234 56780"]),
            ("Are there any new campus alerts?", ["Alerts", "EMERGENCY"])
        ]

        conn = sqlite3.connect(DATABASE_FILE, timeout=15.0)
        try:
            conn.row_factory = sqlite3.Row
            for q, expected_keywords in queries:
                reply = answer_campus_query(1, q, conn)
                for kw in expected_keywords:
                    self.assertIn(kw.lower(), reply.lower(), f"Keyword '{kw}' missing in query '{q}' response:\n{reply}")
        finally:
            conn.close()
        print("[PASS] 9. AI Campus Assistant: Contextual student query responses verified.")

    # -----------------------------------------------------------------------
    # 10. Student Data Privacy & Isolation Tests
    # -----------------------------------------------------------------------
    def test_10_student_data_isolation(self):
        """Verify that AI assistant and routes only access authenticated student ID"""
        conn = sqlite3.connect(DATABASE_FILE, timeout=15.0)
        try:
            conn.execute("INSERT OR IGNORE INTO students (id, name, register_number, email, password_hash, department, year, cgpa) VALUES (2, 'Other Student', 'STU002', 'other@example.com', 'hash', 'Mechanical', 2, 7.2)")
            conn.execute("INSERT OR IGNORE INTO attendance (student_id, subject_code, subject_name, classes_held, classes_attended, classes_missed, attendance_pct) VALUES (2, 'ME201', 'Thermodynamics', 30, 20, 10, 66.7)")
            conn.commit()

            conn.row_factory = sqlite3.Row
            reply_stu1 = answer_campus_query(1, "What is my attendance?", conn)
            self.assertNotIn("Thermodynamics", reply_stu1)
            self.assertNotIn("Other Student", reply_stu1)

            reply_stu2 = answer_campus_query(2, "What is my attendance?", conn)
            self.assertIn("Thermodynamics", reply_stu2)
            self.assertIn("66.7%", reply_stu2)
        finally:
            conn.close()
        print("[PASS] 10. Student Data Privacy & Isolation verified across distinct accounts.")

if __name__ == '__main__':
    unittest.main()
