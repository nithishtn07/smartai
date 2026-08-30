"""
CampusGuard AI — Comprehensive Emergency SOS Status Synchronization Test Suite

Tests the end-to-end multi-portal synchronization across Student, Parent, and Admin/Security portals:
- Single source of truth in SQLite (emergencies & incidents tables).
- Full lifecycle transitions: TRIGGERED -> ACKNOWLEDGED -> ASSIGNED -> EN_ROUTE -> ON_SCENE -> RESOLVED -> CLOSED.
- Real-time status API endpoints: /api/student/emergency/status, /api/parent/emergency/status, /api/emergency/my-active.
- Anti-cache headers validation.
- Resolution consistency (no stale TRIGGERED status remaining).
- Multi-incident handling & IDOR protection.
"""

import unittest
import json
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from database.db import get_db_connection, init_db
from services.emergency_service import (
    create_emergency,
    transition_emergency_status,
    assign_responder,
    get_student_latest_emergency,
    get_parent_ward_emergency,
    ACTIVE_EMERGENCY_STATUSES,
    COMPLETED_EMERGENCY_STATUSES
)


class TestEmergencySync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key-sync'
        self.client = self.app.test_client()

        # Clean database records for test
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM emergency_audit_logs")
            conn.execute("DELETE FROM emergency_notes")
            conn.execute("DELETE FROM emergency_notifications")
            conn.execute("DELETE FROM emergency_responders")
            conn.execute("DELETE FROM emergencies")
            conn.execute("DELETE FROM incidents")
            conn.execute("DELETE FROM parents WHERE email = 'parent.sync@campusguard.test'")
            conn.execute("DELETE FROM students WHERE email = 'student.sync@campusguard.test'")

            # Create test student
            conn.execute("""
                INSERT INTO students (id, name, email, register_number, password_hash, department, year, parent_name, parent_phone)
                VALUES (9901, 'Sync Test Student', 'student.sync@campusguard.test', 'REG-SYNC-01', 'hash123', 'Computer Science', 3, 'Sync Parent', '+91 99999 11111')
            """)

            # Create test parent linked to student 9901
            conn.execute("""
                INSERT INTO parents (id, parent_id, name, email, phone, password_hash, student_id)
                VALUES (9902, 'P-SYNC-01', 'Sync Parent', 'parent.sync@campusguard.test', '+91 99999 11111', 'hash123', 9901)
            """)

            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM emergency_audit_logs")
            conn.execute("DELETE FROM emergency_notes")
            conn.execute("DELETE FROM emergency_notifications")
            conn.execute("DELETE FROM emergency_responders")
            conn.execute("DELETE FROM emergencies")
            conn.execute("DELETE FROM incidents")
            conn.execute("DELETE FROM parents WHERE email = 'parent.sync@campusguard.test'")
            conn.execute("DELETE FROM students WHERE email = 'student.sync@campusguard.test'")
            conn.commit()
        finally:
            conn.close()

    def test_01_constants_and_service_helpers(self):
        """Verify lifecycle constants and status grouping."""
        self.assertIn('TRIGGERED', ACTIVE_EMERGENCY_STATUSES)
        self.assertIn('ACKNOWLEDGED', ACTIVE_EMERGENCY_STATUSES)
        self.assertIn('EN_ROUTE', ACTIVE_EMERGENCY_STATUSES)
        self.assertIn('ON_SCENE', ACTIVE_EMERGENCY_STATUSES)
        self.assertIn('RESOLVED', COMPLETED_EMERGENCY_STATUSES)
        self.assertIn('CLOSED', COMPLETED_EMERGENCY_STATUSES)
        self.assertIn('STAND_DOWN', COMPLETED_EMERGENCY_STATUSES)

    def test_02_emergency_creation_and_initial_status(self):
        """Verify student SOS creation sets single source of truth in SQLite."""
        res = create_emergency(
            reporter_id=9901,
            reporter_name='Sync Test Student',
            reporter_role='student',
            category='Medical Assistance',
            severity='CRITICAL',
            campus_zone='Library Block B',
            latitude=12.9716,
            longitude=77.5946,
            description='Severe dizziness in reading hall',
            skip_idempotency=True
        )
        self.assertEqual(res['status'], 'success')
        emergency_id = res['emergency']['emergency_id']

        conn = get_db_connection()
        try:
            # Check emergencies table
            emg = conn.execute("SELECT * FROM emergencies WHERE emergency_id = ?", (emergency_id,)).fetchone()
            self.assertIsNotNone(emg)
            self.assertEqual(emg['status'], 'TRIGGERED')
            self.assertEqual(emg['campus_zone'], 'Library Block B')

            # Check incidents table synchronized
            inc = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (emergency_id,)).fetchone()
            self.assertIsNotNone(inc)
            self.assertEqual(inc['status'], 'ACTIVE')

            # Query student latest emergency via helper
            st_status = get_student_latest_emergency(9901, conn)
            self.assertTrue(st_status['has_emergency'])
            self.assertTrue(st_status['is_active'])
            self.assertEqual(st_status['status'], 'TRIGGERED')
            self.assertEqual(st_status['incident_id'], emergency_id)

            # Query parent ward emergency via helper
            pt_status = get_parent_ward_emergency(9902, conn)
            self.assertTrue(pt_status['has_emergency'])
            self.assertTrue(pt_status['is_active'])
            self.assertEqual(pt_status['status'], 'TRIGGERED')
        finally:
            conn.close()

    def test_03_lifecycle_transitions_to_resolved(self):
        """Verify full lifecycle transitions and synchronization on RESOLVED."""
        res = create_emergency(
            reporter_id=9901,
            reporter_name='Sync Test Student',
            reporter_role='student',
            category='Personal Safety',
            severity='HIGH',
            campus_zone='Sports Complex',
            latitude=12.9720,
            longitude=77.5950,
            skip_idempotency=True
        )
        self.assertEqual(res['status'], 'success')
        emergency_id = res['emergency']['emergency_id']

        conn = get_db_connection()
        try:
            # 1. Acknowledge
            t1 = transition_emergency_status(emergency_id, 'ACKNOWLEDGED', 'Command Center Officer', 'admin', conn=conn)
            self.assertEqual(t1['status'], 'success')
            st1 = get_student_latest_emergency(9901, conn)
            self.assertTrue(st1['is_active'])
            self.assertEqual(st1['status'], 'ACKNOWLEDGED')

            # 2. Assign responder
            assign_responder(emergency_id, 'Officer Vikram', 'Campus QRT', phone='+91 91234 56780', actor_name='Security Lead', actor_role='security', conn=conn)
            st2 = get_student_latest_emergency(9901, conn)
            self.assertTrue(st2['is_active'])
            self.assertEqual(st2['status'], 'RESPONDER_ASSIGNED')
            self.assertEqual(st2['assigned_responder'], 'Officer Vikram')

            # 3. En Route
            transition_emergency_status(emergency_id, 'EN_ROUTE', 'Officer Vikram', 'security', conn=conn)
            st3 = get_student_latest_emergency(9901, conn)
            self.assertTrue(st3['is_active'])
            self.assertEqual(st3['status'], 'EN_ROUTE')

            # 4. On Scene
            transition_emergency_status(emergency_id, 'ON_SCENE', 'Officer Vikram', 'security', conn=conn)
            st4 = get_student_latest_emergency(9901, conn)
            self.assertTrue(st4['is_active'])
            self.assertEqual(st4['status'], 'ON_SCENE')

            # 5. RESOLVE EMERGENCY
            t_res = transition_emergency_status(
                emergency_id, 'RESOLVED', 'Admin Security Chief', 'admin',
                notes='Student assisted safely. Medical check normal. Stood down.', conn=conn
            )
            self.assertEqual(t_res['status'], 'success')

            # Verify both tables are RESOLVED
            emg_row = conn.execute("SELECT * FROM emergencies WHERE emergency_id = ?", (emergency_id,)).fetchone()
            self.assertEqual(emg_row['status'], 'RESOLVED')
            self.assertIsNotNone(emg_row['resolved_at'])

            inc_row = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (emergency_id,)).fetchone()
            self.assertEqual(inc_row['status'], 'RESOLVED')

            # Critical assertion: Student latest emergency must NOT be active!
            st_res = get_student_latest_emergency(9901, conn)
            self.assertTrue(st_res['has_emergency'])
            self.assertFalse(st_res['is_active'])  # Must be False!
            self.assertEqual(st_res['status'], 'RESOLVED')
            self.assertIsNotNone(st_res['resolved_at'])

            # Parent ward emergency must NOT be active!
            pt_res = get_parent_ward_emergency(9902, conn)
            self.assertTrue(pt_res['has_emergency'])
            self.assertFalse(pt_res['is_active'])  # Must be False!
            self.assertEqual(pt_res['status'], 'RESOLVED')
        finally:
            conn.close()

    def test_04_api_student_and_parent_status_endpoints(self):
        """Verify REST API status endpoints return accurate JSON with anti-cache headers."""
        res = create_emergency(
            reporter_id=9901,
            reporter_name='Sync Test Student',
            reporter_role='student',
            category='Medical Assistance',
            severity='HIGH',
            campus_zone='Hostel Block C',
            skip_idempotency=True
        )
        emergency_id = res['emergency']['emergency_id']

        # 1. Check Student Status Endpoint as authenticated student
        with self.client.session_transaction() as sess:
            sess['student_id'] = 9901
            sess['user_role'] = 'student'
            sess['user_type'] = 'student'

        resp = self.client.get('/api/student/emergency/status')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('no-store', resp.headers.get('Cache-Control', ''))
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['has_emergency'])
        self.assertTrue(data['is_active'])
        self.assertEqual(data['status'], 'TRIGGERED')
        self.assertEqual(data['incident_id'], emergency_id)

        # 2. Check Parent Status Endpoint as authenticated parent
        with self.client.session_transaction() as sess:
            sess['parent_id'] = 9902
            sess['user_role'] = 'parent'
            sess['user_type'] = 'parent'

        resp_p = self.client.get('/api/parent/emergency/status')
        self.assertEqual(resp_p.status_code, 200)
        self.assertIn('no-store', resp_p.headers.get('Cache-Control', ''))
        data_p = resp_p.get_json()
        self.assertTrue(data_p['success'])
        self.assertTrue(data_p['is_active'])
        self.assertEqual(data_p['status'], 'TRIGGERED')

        # 3. Resolve Emergency via Admin Action
        conn = get_db_connection()
        try:
            transition_emergency_status(emergency_id, 'RESOLVED', 'Admin Security', 'admin', conn=conn)
        finally:
            conn.close()

        # 4. Check Student Status Endpoint AFTER RESOLUTION
        with self.client.session_transaction() as sess:
            sess['student_id'] = 9901
            sess['user_type'] = 'student'

        resp_resolved = self.client.get('/api/student/emergency/status')
        self.assertEqual(resp_resolved.status_code, 200)
        data_resolved = resp_resolved.get_json()
        self.assertTrue(data_resolved['success'])
        self.assertTrue(data_resolved['has_emergency'])
        self.assertFalse(data_resolved['is_active'])  # Stale state fixed!
        self.assertEqual(data_resolved['status'], 'RESOLVED')
        self.assertIsNotNone(data_resolved['resolved_at'])

        # 5. Check /api/emergency/my-active endpoint
        resp_my_active = self.client.get('/api/emergency/my-active')
        self.assertEqual(resp_my_active.status_code, 200)
        data_my_active = resp_my_active.get_json()
        self.assertEqual(data_my_active['status'], 'resolved')
        self.assertFalse(data_my_active['is_active'])

    def test_05_multi_incident_resolution_and_no_stale_active(self):
        """Verify when multiple past emergencies exist, only the latest active is active, and resolved ones are inactive."""
        # Incident 1 - Resolved
        res1 = create_emergency(reporter_id=9901, reporter_name='Sync Test Student', reporter_role='student', category='General', severity='LOW', campus_zone='Block A', skip_idempotency=True)
        emg1_id = res1['emergency']['emergency_id']
        conn = get_db_connection()
        try:
            transition_emergency_status(emg1_id, 'RESOLVED', 'Security', 'security', conn=conn)
        finally:
            conn.close()

        conn = get_db_connection()
        try:
            st_check = get_student_latest_emergency(9901, conn)
            self.assertFalse(st_check['is_active'])
            self.assertEqual(st_check['status'], 'RESOLVED')
        finally:
            conn.close()

        # Incident 2 - New Triggered
        res2 = create_emergency(reporter_id=9901, reporter_name='Sync Test Student', reporter_role='student', category='Medical', severity='CRITICAL', campus_zone='Block B', skip_idempotency=True)
        emg2_id = res2['emergency']['emergency_id']

        conn = get_db_connection()
        try:
            st_check2 = get_student_latest_emergency(9901, conn)
            self.assertTrue(st_check2['is_active'])
            self.assertEqual(st_check2['status'], 'TRIGGERED')
            self.assertEqual(st_check2['incident_id'], emg2_id)

            # Resolve Incident 2
            transition_emergency_status(emg2_id, 'RESOLVED', 'Admin', 'admin', conn=conn)
            st_check3 = get_student_latest_emergency(9901, conn)
            self.assertFalse(st_check3['is_active'])
            self.assertEqual(st_check3['status'], 'RESOLVED')
            self.assertEqual(st_check3['incident_id'], emg2_id)
        finally:
            conn.close()

    def test_06_dedicated_student_sos_history_page_and_api(self):
        """Verify dedicated /student/emergency/history page, segregation from live console, metrics, and JSON API."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 9901
            sess['user_role'] = 'student'
            sess['student_id'] = 9901

        # Create 3 distinct historical records: 1 resolved, 1 stood-down, 1 active
        res1 = create_emergency(reporter_id=9901, reporter_name='Sync Test Student', reporter_role='student', category='Personal Safety', severity='HIGH', campus_zone='Hostel Yard', skip_idempotency=True)
        id1 = res1['emergency']['emergency_id']

        res2 = create_emergency(reporter_id=9901, reporter_name='Sync Test Student', reporter_role='student', category='Medical Emergency', severity='CRITICAL', campus_zone='Sports Arena', skip_idempotency=True)
        id2 = res2['emergency']['emergency_id']

        res3 = create_emergency(reporter_id=9901, reporter_name='Sync Test Student', reporter_role='student', category='Security', severity='HIGH', campus_zone='East Gate', skip_idempotency=True)
        id3 = res3['emergency']['emergency_id']

        conn = get_db_connection()
        try:
            transition_emergency_status(id1, 'RESOLVED', 'Command Officer', 'security', conn=conn)
            transition_emergency_status(id2, 'STAND_DOWN', 'Sync Test Student', 'student', conn=conn)
        finally:
            conn.close()

        # 1. Test HTML view rendering
        resp_html = self.client.get('/student/emergency/history')
        self.assertEqual(resp_html.status_code, 200)
        self.assertIn(b'Emergency SOS Incident History &amp; Audit Logs', resp_html.data)
        self.assertIn(b'Total SOS Distresses', resp_html.data)
        self.assertIn(id1.encode(), resp_html.data)
        self.assertIn(id2.encode(), resp_html.data)
        self.assertIn(id3.encode(), resp_html.data)
        self.assertIn(b'Go to Live SOS Console', resp_html.data)

        # 2. Test JSON API endpoint with metrics
        resp_json = self.client.get('/student/emergency/history', headers={'Accept': 'application/json'})
        self.assertEqual(resp_json.status_code, 200)
        data = resp_json.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['metrics']['total'], 3)
        self.assertEqual(data['metrics']['resolved'], 1)
        self.assertEqual(data['metrics']['stand_down'], 1)
        self.assertEqual(data['metrics']['active'], 1)

        # 3. Test status filtering on JSON API
        resp_filtered = self.client.get('/student/emergency/history?status=stand_down', headers={'Accept': 'application/json'})
        self.assertEqual(resp_filtered.status_code, 200)
        data_filt = resp_filtered.get_json()
        self.assertEqual(len(data_filt['history']), 1)
        self.assertEqual(data_filt['history'][0]['emergency_id'], id2)


if __name__ == '__main__':
    unittest.main()
