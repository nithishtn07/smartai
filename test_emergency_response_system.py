"""
CampusGuard AI — Emergency Response System Test Suite
Tests all 12 scenarios:
1. Emergency SOS Triggering (Web + API)
2. Geolocation Telemetry & Fallback Zone Capture
3. 6-Stage State Machine Lifecycle Transitions
4. Non-Blocking AI Classification Advisory
5. Collaborative Incident Notes
6. Immutable Audit Trail Logging
7. Response Interval Metrics Computation
8. Multi-Portal Scoped Notifications (Student, Linked Parent, Faculty, Admin)
9. Security & Role Isolation Access Control
10. Live Active Emergency Stream API
11. Incident Archive & Multi-Criteria Filtering
12. Safety Analytics & Risk Heatmap Matrix
"""

import unittest
import json
import sqlite3
from app import app
from database.db import get_db_connection
from database.seed import seed_database
from services.ai_emergency_service import classify_emergency_text, generate_ai_incident_summary
from services.emergency_service import (
    create_emergency,
    transition_emergency_status,
    assign_responder,
    add_incident_note,
    calculate_response_times,
    get_emergency_full_dossier
)


class TestEmergencyResponseSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        conn = get_db_connection()
        try:
            seed_database(conn)
        finally:
            conn.close()

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    # -----------------------------------------------------------------------
    # Scenario 1: Emergency SOS Triggering (Student Web & REST API)
    # -----------------------------------------------------------------------
    def test_01_emergency_sos_triggering(self):
        # A. Via REST API
        with self.client.session_transaction() as sess:
            sess['user_role'] = 'student'
            sess['student_id'] = 1
            sess['user_name'] = 'Nithish Nagaraj'

        resp = self.client.post('/api/emergency/create', json={
            'category': 'Medical Emergency',
            'severity': 'CRITICAL',
            'description': 'Student collapsed near chemistry lab with severe shortness of breath.',
            'campus_zone': 'Main Academic Block',
            'building': 'Science Wing',
            'floor': '2nd Floor',
            'room': 'Lab 204',
            'latitude': 12.9716,
            'longitude': 77.5946,
            'accuracy': 4.5
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue('emergency' in data)
        emg_id = data['emergency']['emergency_id']
        self.assertTrue(emg_id.startswith('EMG-'))
        self.assertEqual(data['emergency']['severity'], 'CRITICAL')
        self.assertEqual(data['emergency']['status'], 'TRIGGERED')

        # B. Via Student Portal Form
        resp_web = self.client.post('/student/emergency', data={
            'location': 'Hostel Block B (Oak Wing)',
            'latitude': '12.9720',
            'longitude': '77.5950',
            'category': 'Personal Safety',
            'severity': 'HIGH',
            'sos_note': 'Suspicious individual outside hostel gate'
        }, follow_redirects=True)
        self.assertEqual(resp_web.status_code, 200)
        self.assertIn(b'EMERGENCY SOS ACTIVE', resp_web.data)

    # -----------------------------------------------------------------------
    # Scenario 2: Geolocation Telemetry & Fallback Zone Capture
    # -----------------------------------------------------------------------
    def test_02_geolocation_and_manual_zone_fallback(self):
        # Case A: Accurate GPS coordinates provided
        res_gps = create_emergency(
            reporter_id=1,
            reporter_name='Nithish Nagaraj',
            reporter_role='student',
            category='Fire/Safety',
            severity='HIGH',
            latitude=12.97182,
            longitude=77.59481,
            location_accuracy=3.2,
            campus_zone='Computer Center & AI Labs',
            skip_idempotency=True
        )
        self.assertEqual(res_gps['status'], 'success')
        emg = res_gps['emergency']
        self.assertAlmostEqual(emg['latitude'], 12.97182, places=4)
        self.assertAlmostEqual(emg['location_accuracy'], 3.2, places=1)

        # Case B: GPS Denied / Unavailable -> Manual Campus Zone Fallback
        res_fallback = create_emergency(
            reporter_id=1,
            reporter_name='Nithish Nagaraj',
            reporter_role='student',
            category='Campus Infrastructure',
            severity='MEDIUM',
            latitude=None,
            longitude=None,
            location_accuracy=None,
            campus_zone='Central University Library',
            building='Library Annex',
            floor='3rd Floor',
            room='Reading Room 3B',
            skip_idempotency=True
        )
        self.assertEqual(res_fallback['status'], 'success')
        emg_fb = res_fallback['emergency']
        self.assertIsNone(emg_fb['latitude'])
        self.assertEqual(emg_fb['campus_zone'], 'Central University Library')
        self.assertEqual(emg_fb['building'], 'Library Annex')

    # -----------------------------------------------------------------------
    # Scenario 3: 6-Stage State Machine Lifecycle Transitions
    # -----------------------------------------------------------------------
    def test_03_six_stage_state_machine_lifecycle(self):
        res = create_emergency(
            reporter_id=1,
            reporter_name='Nithish Nagaraj',
            reporter_role='student',
            category='Medical Emergency',
            severity='HIGH',
            campus_zone='Sports Arena',
            skip_idempotency=True
        )
        emg_id = res['emergency']['emergency_id']

        # 1. TRIGGERED -> Initial state
        dossier1 = get_emergency_full_dossier(emg_id)
        self.assertEqual(dossier1['emergency']['status'], 'TRIGGERED')

        # 2. ACKNOWLEDGED
        res_ack = transition_emergency_status(emg_id, 'ACKNOWLEDGED', 'Chief Security Officer', 'security', 'Acknowledged by Control Tower.')
        self.assertEqual(res_ack['status'], 'success')
        self.assertEqual(res_ack['new_status'], 'ACKNOWLEDGED')

        # 3. RESPONDER_ASSIGNED
        res_assign = assign_responder(emg_id, 'Officer Ramesh', 'Quick Response Team', '+91 98765 00001', 'Admin Console', 'admin')
        self.assertEqual(res_assign['status'], 'success')
        self.assertEqual(res_assign['emergency']['status'], 'RESPONDER_ASSIGNED')
        self.assertEqual(res_assign['emergency']['assigned_responder'], 'Officer Ramesh')

        # 4. EN_ROUTE
        res_route = transition_emergency_status(emg_id, 'EN_ROUTE', 'Officer Ramesh', 'security', 'QRT vehicle rolling to Sports Arena.')
        self.assertEqual(res_route['status'], 'success')
        self.assertEqual(res_route['new_status'], 'EN_ROUTE')

        # 5. ON_SCENE
        res_scene = transition_emergency_status(emg_id, 'ON_SCENE', 'Officer Ramesh', 'security', 'Arrived at Sports Arena. Contact established.')
        self.assertEqual(res_scene['status'], 'success')
        self.assertEqual(res_scene['new_status'], 'ON_SCENE')

        # 6. RESOLVED
        res_resolve = transition_emergency_status(emg_id, 'RESOLVED', 'Officer Ramesh', 'security', 'Student received first aid and hydrated. All safe.')
        self.assertEqual(res_resolve['status'], 'success')
        self.assertEqual(res_resolve['new_status'], 'RESOLVED')
        self.assertIsNotNone(res_resolve['emergency']['resolution_summary'])

        # 7. CLOSED
        res_close = transition_emergency_status(emg_id, 'CLOSED', 'Admin Command', 'admin', 'Incident formally archived.')
        self.assertEqual(res_close['status'], 'success')
        self.assertEqual(res_close['new_status'], 'CLOSED')

    # -----------------------------------------------------------------------
    # Scenario 4: Non-Blocking AI Classification NLP Suggestions
    # -----------------------------------------------------------------------
    def test_04_ai_classification_suggestions(self):
        # Case A: Medical description
        med_ai = classify_emergency_text("Student fainted and unconscious with severe head trauma after fall", "Sports Arena")
        self.assertEqual(med_ai['category'], 'Medical Emergency')
        self.assertEqual(med_ai['severity'], 'CRITICAL')
        self.assertEqual(med_ai['priority'], 'IMMEDIATE')
        self.assertIn('unconscious', med_ai['key_indicators'])

        # Case B: Fire hazard description
        fire_ai = classify_emergency_text("Dense smoke and electrical sparks spreading from circuit box", "Science Block")
        self.assertEqual(fire_ai['category'], 'Fire/Safety')
        self.assertIn(fire_ai['severity'], ['HIGH', 'CRITICAL'])

        # Case C: Infrastructure description
        infra_ai = classify_emergency_text("Elevator stuck between 3rd and 4th floor with 4 students inside", "Main Academic Block")
        self.assertEqual(infra_ai['category'], 'Campus Infrastructure')

    # -----------------------------------------------------------------------
    # Scenario 5: Collaborative Incident Notes
    # -----------------------------------------------------------------------
    def test_05_collaborative_incident_notes(self):
        res = create_emergency(reporter_id=1, reporter_name='Nithish Nagaraj', reporter_role='student', category='Security', skip_idempotency=True)
        emg_id = res['emergency']['emergency_id']

        # Add notes from different roles
        n1 = add_incident_note(emg_id, 1, 'Nithish Nagaraj', 'student', 'Distress beacon activated from West Stairwell.')
        self.assertEqual(n1['status'], 'success')

        n2 = add_incident_note(emg_id, 2, 'Officer Vikram', 'security', 'Patrol unit Alpha-2 redirected to West Stairwell.')
        self.assertEqual(n2['status'], 'success')

        dossier = get_emergency_full_dossier(emg_id)
        self.assertEqual(len(dossier['notes']), 2)
        self.assertEqual(dossier['notes'][0]['author_role'], 'student')
        self.assertEqual(dossier['notes'][1]['author_role'], 'security')

    # -----------------------------------------------------------------------
    # Scenario 6: Immutable Audit Trail Logging
    # -----------------------------------------------------------------------
    def test_06_immutable_audit_trail_logging(self):
        res = create_emergency(reporter_id=1, reporter_name='Nithish Nagaraj', reporter_role='student', category='Personal Safety', skip_idempotency=True)
        emg_id = res['emergency']['emergency_id']

        transition_emergency_status(emg_id, 'ACKNOWLEDGED', 'Admin User', 'admin')
        assign_responder(emg_id, 'QRT Bravo', 'Quick Response Team', '+91 98765 00002', 'Admin User', 'admin')

        conn = get_db_connection()
        logs = conn.execute("SELECT * FROM emergency_audit_logs WHERE emergency_id = ? ORDER BY timestamp ASC", (emg_id,)).fetchall()
        conn.close()

        actions = [log['action'] for log in logs]
        self.assertIn('SOS_TRIGGERED', actions)
        self.assertIn('STATUS_CHANGE', actions)
        self.assertIn('ASSIGN_RESPONDER', actions)

    # -----------------------------------------------------------------------
    # Scenario 7: Response Interval Metrics Computation
    # -----------------------------------------------------------------------
    def test_07_response_interval_metrics(self):
        emg_data = {
            'emergency_id': 'EMG-2026-TEST01',
            'created_at': '2026-08-22 10:00:00',
            'acknowledged_at': '2026-08-22 10:00:45',
            'assigned_at': '2026-08-22 10:01:30',
            'response_started_at': '2026-08-22 10:02:00',
            'arrived_at': '2026-08-22 10:04:30',
            'resolved_at': '2026-08-22 10:15:00'
        }
        metrics = calculate_response_times(emg_data)
        self.assertEqual(metrics['time_to_acknowledge'], '45s')
        self.assertEqual(metrics['time_to_assign'], '45s')
        self.assertEqual(metrics['time_to_arrive'], '2m 30s')
        self.assertEqual(metrics['total_resolution_time'], '15m 0s')
        self.assertEqual(metrics['total_seconds'], 900)

    # -----------------------------------------------------------------------
    # Scenario 8: Multi-Portal Scoped Notifications
    # -----------------------------------------------------------------------
    def test_08_multi_portal_scoped_notifications(self):
        # Create emergency as student 1 (Nithish Nagaraj, whose parent is Nagaraj Kumar)
        res = create_emergency(
            reporter_id=1,
            reporter_name='Nithish Nagaraj',
            reporter_role='student',
            category='Medical Emergency',
            severity='CRITICAL',
            campus_zone='Hostel Block B (Oak Wing)',
            skip_idempotency=True
        )
        emg_id = res['emergency']['emergency_id']

        conn = get_db_connection()
        # Verify parent notification
        parent_notif = conn.execute("SELECT * FROM emergency_notifications WHERE emergency_id = ? AND recipient_role = 'parent'", (emg_id,)).fetchone()
        self.assertIsNotNone(parent_notif)
        self.assertEqual(parent_notif['recipient_name'], 'R. S. Kumar')
        self.assertIn('Nithish Nagaraj', parent_notif['title'])

        # Verify admin notification in notifications table
        admin_notif = conn.execute("SELECT * FROM notifications WHERE recipient_role = 'admin' AND category = 'Safety' ORDER BY id DESC LIMIT 1").fetchone()
        self.assertIsNotNone(admin_notif)
        self.assertIn(emg_id, admin_notif['title'])
        conn.close()

    # -----------------------------------------------------------------------
    # Scenario 9: Security & Role Isolation Access Control
    # -----------------------------------------------------------------------
    def test_09_security_and_role_isolation(self):
        res = create_emergency(
            reporter_id=1,
            reporter_name='Nithish Nagaraj',
            reporter_role='student',
            category='Personal Safety',
            skip_idempotency=True
        )
        emg_id = res['emergency']['emergency_id']

        # Case A: Student 2 attempting to access Student 1's emergency -> 403 Forbidden
        with self.client.session_transaction() as sess:
            sess['user_role'] = 'student'
            sess['student_id'] = 2
            sess['user_name'] = 'Ananya Sharma'

        resp_s2 = self.client.get(f'/api/emergency/{emg_id}')
        self.assertEqual(resp_s2.status_code, 403)

        # Case B: Parent 2 (linked to Student 2) attempting to access Student 1's emergency -> 403 Forbidden
        with self.client.session_transaction() as sess:
            sess['user_role'] = 'parent'
            sess['parent_id'] = 2
            sess['user_name'] = 'Suresh Sharma'

        resp_p2 = self.client.get(f'/api/emergency/{emg_id}')
        self.assertEqual(resp_p2.status_code, 403)

        # Case C: Parent 1 (linked to Student 1) accessing Student 1's emergency -> 200 OK
        with self.client.session_transaction() as sess:
            sess['user_role'] = 'parent'
            sess['parent_id'] = 1
            sess['user_name'] = 'Nagaraj Kumar'

        resp_p1 = self.client.get(f'/api/emergency/{emg_id}')
        self.assertEqual(resp_p1.status_code, 200)
        self.assertEqual(resp_p1.get_json()['status'], 'success')

        # Case D: Admin accessing Student 1's emergency -> 200 OK
        with self.client.session_transaction() as sess:
            sess['user_role'] = 'admin'
            sess['admin_id'] = 1
            sess['user_name'] = 'Dean Office'

        resp_adm = self.client.get(f'/api/emergency/{emg_id}')
        self.assertEqual(resp_adm.status_code, 200)

    # -----------------------------------------------------------------------
    # Scenario 10: Live Active Emergency Stream API
    # -----------------------------------------------------------------------
    def test_10_live_active_emergency_stream_api(self):
        resp = self.client.get('/api/emergency/active')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertIsInstance(data['emergencies'], list)
        if len(data['emergencies']) > 0:
            self.assertTrue('metrics' in data['emergencies'][0])
            self.assertTrue('priority_score' in data['emergencies'][0])

    # -----------------------------------------------------------------------
    # Scenario 11: Emergency Incident Archive & Multi-Criteria Filtering
    # -----------------------------------------------------------------------
    def test_11_incident_archive_and_filtering(self):
        with self.client.session_transaction() as sess:
            sess['user_role'] = 'admin'
            sess['admin_id'] = 1

        # A. All history view
        resp_all = self.client.get('/emergency/history')
        self.assertEqual(resp_all.status_code, 200)
        self.assertIn(b'Emergency Incident Archive', resp_all.data)

        # B. Filter by Category
        resp_cat = self.client.get('/emergency/history?category=Medical+Emergency')
        self.assertEqual(resp_cat.status_code, 200)

        # C. Filter by Severity
        resp_sev = self.client.get('/emergency/history?severity=CRITICAL')
        self.assertEqual(resp_sev.status_code, 200)

        # D. Keyword search
        resp_search = self.client.get('/emergency/history?q=EMG-2026')
        self.assertEqual(resp_search.status_code, 200)

    # -----------------------------------------------------------------------
    # Scenario 12: Safety Analytics & Risk Heatmap Matrix
    # -----------------------------------------------------------------------
    def test_12_safety_analytics_and_risk_heatmap(self):
        with self.client.session_transaction() as sess:
            sess['user_role'] = 'admin'
            sess['admin_id'] = 1

        resp = self.client.get('/emergency/analytics')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Emergency Response Analytics', resp.data)
        self.assertIn(b'Campus Zone Risk Matrix', resp.data)
        self.assertIn(b'AI Predictive Pattern Mining', resp.data)


if __name__ == '__main__':
    unittest.main()
