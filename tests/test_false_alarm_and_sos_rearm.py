"""
test_false_alarm_and_sos_rearm.py
=================================
Automated test suite verifying the False Alarm (Stand Down) state transition:
1. Status immediately updates as SAFE.
2. Neutral Ready card renders with the prominent 'ACTIVATE EMERGENCY SOS' button.
3. The SOS button is fully usable and immediately ready to trigger a new emergency alert.
"""

import unittest
from app import app
from database.db import get_db_connection
from services.emergency_service import (
    get_student_latest_emergency,
    transition_emergency_status
)


class TestFalseAlarmAndSOSRearm(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        conn = get_db_connection()
        try:
            conn.execute("UPDATE emergencies SET status = 'STAND_DOWN' WHERE status NOT IN ('RESOLVED', 'CLOSED', 'STAND_DOWN', 'CANCELLED')")
            conn.execute("UPDATE incidents SET status = 'CANCELLED' WHERE status NOT IN ('RESOLVED', 'CLOSED', 'STAND_DOWN', 'CANCELLED')")
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        conn = get_db_connection()
        try:
            conn.execute("UPDATE emergencies SET status = 'STAND_DOWN' WHERE status NOT IN ('RESOLVED', 'CLOSED', 'STAND_DOWN', 'CANCELLED')")
            conn.execute("UPDATE incidents SET status = 'CANCELLED' WHERE status NOT IN ('RESOLVED', 'CLOSED', 'STAND_DOWN', 'CANCELLED')")
            conn.commit()
        finally:
            conn.close()
        self.app_context.pop()

    def _login_student(self):
        return self.client.post('/student/login', data={
            'register_number': 'STU001',
            'password': 'Student@123'
        }, follow_redirects=True)

    def test_01_false_alarm_updates_status_as_safe_and_rearms_sos_button(self):
        """Test SOS trigger -> False alarm stand-down -> Safe status confirmed -> Alert button immediately usable again."""
        self._login_student()

        # Step 1: Trigger Emergency SOS
        resp_trigger = self.client.post('/student/emergency', data={
            'category': 'Personal Safety',
            'severity': 'HIGH',
            'location_zone': 'Computer Center & AI Labs',
            'latitude': '12.9716',
            'longitude': '77.5946',
            'description': 'Test Distress Beacon'
        }, follow_redirects=True)

        self.assertEqual(resp_trigger.status_code, 200)
        self.assertIn(b'EMERGENCY SOS ACTIVE', resp_trigger.data)

        # Retrieve triggered incident ID
        conn = get_db_connection()
        try:
            student = conn.execute("SELECT id FROM students WHERE register_number = 'STU001'").fetchone()
            student_id = student['id']

            st_status = get_student_latest_emergency(student_id, conn)
            self.assertTrue(st_status['has_emergency'])
            self.assertTrue(st_status['is_active'])
            self.assertFalse(st_status['is_safe'])
            incident_id = st_status['emergency_id']
        finally:
            conn.close()

        # Step 2: Stand down as False Alarm
        resp_cancel = self.client.post(f'/student/emergency/cancel/{incident_id}', follow_redirects=True)
        self.assertEqual(resp_cancel.status_code, 200)

        # Step 3: Verify Status is marked SAFE
        self.assertIn(b'stood down. Marked safe', resp_cancel.data)
        self.assertIn(b'Status: Safe / Ready', resp_cancel.data)
        self.assertIn(b'False Alarm / Stand Down Confirmed', resp_cancel.data)

        # Step 4: Verify the SOS button is present, visible, and usable in the response HTML
        self.assertIn(b'ACTIVATE EMERGENCY SOS', resp_cancel.data)
        self.assertIn(b'main-activate-sos-btn', resp_cancel.data)

        # Step 5: Verify backend DB state reflects Safe
        conn = get_db_connection()
        try:
            latest_status = get_student_latest_emergency(student_id, conn)
            self.assertFalse(latest_status['is_active'])
            self.assertTrue(latest_status['is_safe'])
            self.assertTrue(latest_status['is_stood_down'])
            self.assertEqual(latest_status['status'], 'STAND_DOWN')
        finally:
            conn.close()

        # Step 6: Verify polling API /api/student/emergency/status returns Safe
        resp_api = self.client.get('/api/student/emergency/status')
        self.assertEqual(resp_api.status_code, 200)
        api_data = resp_api.get_json()
        self.assertTrue(api_data['success'])
        self.assertFalse(api_data['is_active'])
        self.assertTrue(api_data['is_safe'])
        self.assertEqual(api_data['status'], 'STAND_DOWN')

        # Step 7: Verify student can immediately trigger a NEW emergency SOS alert
        resp_trigger_2 = self.client.post('/student/emergency', data={
            'category': 'Medical Emergency',
            'severity': 'CRITICAL',
            'location_zone': 'Central University Library',
            'latitude': '12.9720',
            'longitude': '77.5950',
            'description': 'Second Distress Beacon after false alarm'
        }, follow_redirects=True)

        self.assertEqual(resp_trigger_2.status_code, 200)
        self.assertIn(b'EMERGENCY SOS ACTIVE', resp_trigger_2.data)

        conn = get_db_connection()
        try:
            new_status = get_student_latest_emergency(student_id, conn)
            self.assertTrue(new_status['is_active'])
            self.assertFalse(new_status['is_safe'])
            self.assertNotEqual(new_status['emergency_id'], incident_id)
            self.assertEqual(new_status['category'], 'Medical Emergency')

            # Clean up: Stand down second alert
            transition_emergency_status(new_status['emergency_id'], 'STAND_DOWN', 'Nithish Nagaraj', 'student', conn=conn)
            conn.execute("UPDATE incidents SET status = 'CANCELLED' WHERE incident_id = ?", (new_status['emergency_id'],))
            conn.commit()
        finally:
            conn.close()

    def test_02_dedicated_stand_down_api(self):
        """Test the dedicated JSON stand-down / cancel API endpoint."""
        self._login_student()

        # Trigger emergency
        self.client.post('/student/emergency', data={
            'category': 'Security',
            'severity': 'HIGH',
            'location_zone': 'North Security Gate',
            'latitude': '12.9730',
            'longitude': '77.5960',
            'description': 'Security Alert Test'
        }, follow_redirects=True)

        conn = get_db_connection()
        try:
            student = conn.execute("SELECT id FROM students WHERE register_number = 'STU001'").fetchone()
            st_status = get_student_latest_emergency(student['id'], conn)
            emg_id = st_status['emergency_id']
        finally:
            conn.close()

        # Call JSON stand-down endpoint
        resp = self.client.post(f'/api/emergency/{emg_id}/stand-down', json={'notes': 'False alarm pressed'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(data.get('is_safe'))
        self.assertEqual(data['new_status'], 'STAND_DOWN')


if __name__ == '__main__':
    unittest.main()
