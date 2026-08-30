"""
CampusGuard AI — Admin SOS Alerts & History Integration Tests
Verifies that:
1. Admin Active SOS shows ONLY active emergencies (TRIGGERED, ACKNOWLEDGED, ASSIGNED, EN_ROUTE, ON_SCENE).
2. Resolved/Closed SOS moves permanently to SOS History and disappears from Active SOS.
3. Database is the single source of truth; zero fake or hardcoded data.
4. Active SOS count matches database exactly.
5. History API supports filtering and search.
6. Student and Parent portals remain fully synchronized on Admin resolution.
"""

import unittest
import datetime
from app import app
from database.db import get_db_connection
from services.emergency_service import (
    create_emergency,
    transition_emergency_status,
    assign_responder,
    get_student_latest_emergency,
    get_parent_ward_emergency
)


class TestAdminSOSManagement(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        # Initialize clean test fixtures in database
        conn = get_db_connection()
        try:
            # Clean test records
            conn.execute("DELETE FROM emergency_audit_logs WHERE user_name LIKE '%AdminTest%' OR user_name LIKE '%TestStudent%'")
            conn.execute("DELETE FROM emergency_notes WHERE author_name LIKE '%AdminTest%'")
            conn.execute("DELETE FROM emergency_notifications WHERE recipient_id IN (8801, 8802, 8803)")
            conn.execute("DELETE FROM emergencies WHERE user_id IN (8801, 8802, 8803)")
            conn.execute("DELETE FROM incidents WHERE student_id IN (8801, 8802, 8803)")
            conn.execute("DELETE FROM parents WHERE id = 8802")
            conn.execute("DELETE FROM students WHERE id = 8801")
            conn.execute("DELETE FROM admins WHERE id = 8809")

            # Create test student
            conn.execute("""
                INSERT INTO students (id, name, register_number, email, password_hash, department, year, phone, parent_name, parent_phone)
                VALUES (8801, 'AdminTest Student A', 'ADMTEST001', 'admintest.a@example.com', 'hash123', 'Computer Science', 3, '+91 98765 00001', 'AdminTest Parent A', '+91 98765 00002')
            """)

            # Create test parent
            conn.execute("""
                INSERT INTO parents (id, parent_id, name, email, phone, password_hash, student_id)
                VALUES (8802, 'P-ADMTEST-01', 'AdminTest Parent A', 'admintest.parent@example.com', '+91 98765 00002', 'hash123', 8801)
            """)

            # Create test admin
            conn.execute("""
                INSERT INTO admins (id, name, username, email, password_hash, role)
                VALUES (8809, 'Admin Commander Test', 'admin_test', 'admin_test@example.com', 'hash123', 'Super Admin')
            """)

            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM emergencies WHERE user_id IN (8801, 8802, 8803)")
            conn.execute("DELETE FROM incidents WHERE student_id IN (8801, 8802, 8803)")
            conn.execute("DELETE FROM parents WHERE id = 8802")
            conn.execute("DELETE FROM students WHERE id = 8801")
            conn.execute("DELETE FROM admins WHERE id = 8809")
            conn.commit()
        finally:
            conn.close()

    def _login_as_admin(self):
        with self.client.session_transaction() as sess:
            sess['admin_id'] = 8809
            sess['admin_name'] = 'Admin Commander Test'
            sess['user_role'] = 'admin'
            sess['admin_logged_in'] = True

    def test_01_clean_state_returns_zero_active(self):
        """Verify when no active emergencies exist for this test set, active count is clean and accurate."""
        self._login_as_admin()
        
        # Clean all active emergencies for pristine baseline
        conn = get_db_connection()
        try:
            conn.execute("UPDATE emergencies SET status = 'RESOLVED' WHERE status IN ('TRIGGERED', 'ACKNOWLEDGED', 'ASSIGNED', 'RESPONDER_ASSIGNED', 'EN_ROUTE', 'ON_SCENE', 'ACTIVE', 'RESPONDING')")
            conn.commit()
        finally:
            conn.close()

        resp = self.client.get('/api/admin/sos/active')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('no-store', resp.headers.get('Cache-Control', ''))
        data = resp.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['count'], 0)
        self.assertEqual(len(data['emergencies']), 0)

        # Admin safety page should show 0 active alerts
        resp_page = self.client.get('/admin/safety')
        self.assertEqual(resp_page.status_code, 200)
        self.assertIn(b'0</span> Active Alert', resp_page.data)
        self.assertIn(b'All Campus Sectors Clear', resp_page.data)

    def test_02_new_sos_appears_in_active_only(self):
        """Verify newly triggered SOS appears in Active SOS and NOT in SOS History."""
        res = create_emergency(
            reporter_id=8801,
            reporter_name='AdminTest Student A',
            reporter_role='student',
            category='Medical Emergency',
            severity='CRITICAL',
            campus_zone='Innovation Hub Lab 4',
            description='Severe asthma attack during robotics lab',
            skip_idempotency=True
        )
        self.assertEqual(res['status'], 'success')
        emg_id = res['emergency']['emergency_id']

        self._login_as_admin()

        # 1. Check Active API
        resp_active = self.client.get('/api/admin/sos/active')
        self.assertEqual(resp_active.status_code, 200)
        data_active = resp_active.get_json()
        active_ids = [e['incident_id'] for e in data_active['emergencies']]
        self.assertIn(emg_id, active_ids)

        # 2. Check History API (Must NOT contain active SOS)
        resp_hist = self.client.get('/api/admin/sos/history')
        self.assertEqual(resp_hist.status_code, 200)
        data_hist = resp_hist.get_json()
        hist_ids = [h['incident_id'] for h in data_hist['history']]
        self.assertNotIn(emg_id, hist_ids)

        # 3. Check Safety Portal View
        resp_safety = self.client.get('/admin/safety')
        self.assertEqual(resp_safety.status_code, 200)
        self.assertIn(emg_id.encode(), resp_safety.data)
        self.assertIn(b'AdminTest Student A', resp_safety.data)
        self.assertIn(b'Innovation Hub Lab 4', resp_safety.data)
        self.assertIn(b'CRITICAL', resp_safety.data)

        # 4. Check Dashboard View
        resp_dash = self.client.get('/admin/dashboard')
        self.assertEqual(resp_dash.status_code, 200)
        self.assertIn(emg_id.encode(), resp_dash.data)

    def test_03_admin_resolves_sos_moves_to_history(self):
        """Verify when Admin resolves an SOS, it disappears from Active and appears in History."""
        res = create_emergency(
            reporter_id=8801,
            reporter_name='AdminTest Student A',
            reporter_role='student',
            category='Personal Safety',
            severity='HIGH',
            campus_zone='South Gate Quadrangle',
            skip_idempotency=True
        )
        emg_id = res['emergency']['emergency_id']

        self._login_as_admin()

        # Transition to ACKNOWLEDGED then EN_ROUTE then RESOLVED
        conn = get_db_connection()
        try:
            transition_emergency_status(emg_id, 'ACKNOWLEDGED', 'Admin Commander Test', 'admin', conn=conn)
            transition_emergency_status(emg_id, 'EN_ROUTE', 'Officer Vikram', 'security', conn=conn)
            
            # Post resolution form like Admin UI does
            resp_post = self.client.post('/admin/sos/status-update', data={
                'incident_id': emg_id,
                'new_status': 'RESOLVED'
            }, follow_redirects=True)
            self.assertEqual(resp_post.status_code, 200)
        finally:
            conn.close()

        # 1. Active API must NO LONGER contain this SOS
        resp_active = self.client.get('/api/admin/sos/active')
        data_active = resp_active.get_json()
        active_ids = [e['incident_id'] for e in data_active['emergencies']]
        self.assertNotIn(emg_id, active_ids)

        # 2. History API MUST contain this SOS with status RESOLVED and resolved_at
        resp_hist = self.client.get('/api/admin/sos/history')
        data_hist = resp_hist.get_json()
        hist_records = {h['incident_id']: h for h in data_hist['history']}
        self.assertIn(emg_id, hist_records)
        self.assertEqual(hist_records[emg_id]['status'], 'RESOLVED')
        self.assertIsNotNone(hist_records[emg_id]['resolved_at'])

        # 3. Verify record was updated in database and NOT deleted
        conn = get_db_connection()
        try:
            emg_row = conn.execute("SELECT * FROM emergencies WHERE emergency_id = ?", (emg_id,)).fetchone()
            self.assertIsNotNone(emg_row)
            self.assertEqual(emg_row['status'], 'RESOLVED')
            self.assertIsNotNone(emg_row['resolved_at'])
        finally:
            conn.close()

    def test_04_multiple_incidents_partitioning(self):
        """Verify multiple incidents partition strictly: active ones in active list, resolved/closed in history."""
        # 1. TRIGGERED (Active)
        e1 = create_emergency(reporter_id=8801, reporter_name='Student 1', reporter_role='student', category='Medical Emergency', severity='CRITICAL', campus_zone='Zone 1', skip_idempotency=True)['emergency']['emergency_id']
        # 2. RESOLVED (History)
        e2 = create_emergency(reporter_id=8801, reporter_name='Student 2', reporter_role='student', category='Personal Safety', severity='HIGH', campus_zone='Zone 2', skip_idempotency=True)['emergency']['emergency_id']
        # 3. ON_SCENE (Active)
        e3 = create_emergency(reporter_id=8801, reporter_name='Student 3', reporter_role='student', category='Security', severity='HIGH', campus_zone='Zone 3', skip_idempotency=True)['emergency']['emergency_id']
        # 4. CLOSED (History)
        e4 = create_emergency(reporter_id=8801, reporter_name='Student 4', reporter_role='student', category='Campus Infrastructure', severity='LOW', campus_zone='Zone 4', skip_idempotency=True)['emergency']['emergency_id']
        # 5. ACKNOWLEDGED (Active)
        e5 = create_emergency(reporter_id=8801, reporter_name='Student 5', reporter_role='student', category='Fire/Safety', severity='HIGH', campus_zone='Zone 5', skip_idempotency=True)['emergency']['emergency_id']

        conn = get_db_connection()
        try:
            transition_emergency_status(e2, 'RESOLVED', 'Admin Commander Test', 'admin', conn=conn)
            transition_emergency_status(e3, 'ACKNOWLEDGED', 'Admin Commander Test', 'admin', conn=conn)
            transition_emergency_status(e3, 'ON_SCENE', 'Officer Vikram', 'security', conn=conn)
            transition_emergency_status(e4, 'CLOSED', 'Admin Commander Test', 'admin', conn=conn)
            transition_emergency_status(e5, 'ACKNOWLEDGED', 'Admin Commander Test', 'admin', conn=conn)
        finally:
            conn.close()

        self._login_as_admin()

        # Check Active Endpoint
        resp_act = self.client.get('/api/admin/sos/active')
        act_data = resp_act.get_json()
        act_ids = [a['incident_id'] for a in act_data['emergencies']]

        self.assertIn(e1, act_ids)
        self.assertIn(e3, act_ids)
        self.assertIn(e5, act_ids)
        self.assertNotIn(e2, act_ids)
        self.assertNotIn(e4, act_ids)

        # Check History Endpoint
        resp_hist = self.client.get('/api/admin/sos/history')
        hist_data = resp_hist.get_json()
        hist_ids = [h['incident_id'] for h in hist_data['history']]

        self.assertIn(e2, hist_ids)
        self.assertIn(e4, hist_ids)
        self.assertNotIn(e1, hist_ids)
        self.assertNotIn(e3, hist_ids)
        self.assertNotIn(e5, hist_ids)

    def test_05_history_search_and_filtering(self):
        """Verify SOS History endpoint filters properly by status, category, severity, and text search."""
        e_crit = create_emergency(reporter_id=8801, reporter_name='Student SearchTarget', reporter_role='student', category='Medical Emergency', severity='CRITICAL', campus_zone='Special Search Location Alpha', skip_idempotency=True)['emergency']['emergency_id']
        e_low = create_emergency(reporter_id=8801, reporter_name='Student NormalTarget', reporter_role='student', category='Campus Infrastructure', severity='LOW', campus_zone='Normal Location Beta', skip_idempotency=True)['emergency']['emergency_id']

        conn = get_db_connection()
        try:
            transition_emergency_status(e_crit, 'RESOLVED', 'Admin', 'admin', conn=conn)
            transition_emergency_status(e_low, 'CLOSED', 'Admin', 'admin', conn=conn)
        finally:
            conn.close()

        self._login_as_admin()

        # 1. Filter by Severity=CRITICAL
        resp_sev = self.client.get('/api/admin/sos/history?severity=CRITICAL')
        data_sev = resp_sev.get_json()
        sev_ids = [h['incident_id'] for h in data_sev['history']]
        self.assertIn(e_crit, sev_ids)
        self.assertNotIn(e_low, sev_ids)

        # 2. Filter by Status=CLOSED
        resp_st = self.client.get('/api/admin/sos/history?status=CLOSED')
        data_st = resp_st.get_json()
        st_ids = [h['incident_id'] for h in data_st['history']]
        self.assertIn(e_low, st_ids)
        self.assertNotIn(e_crit, st_ids)

        # 3. Search by Query text 'SearchTarget'
        resp_q = self.client.get('/api/admin/sos/history?q=SearchTarget')
        data_q = resp_q.get_json()
        q_ids = [h['incident_id'] for h in data_q['history']]
        self.assertIn(e_crit, q_ids)
        self.assertNotIn(e_low, q_ids)

    def test_06_student_and_parent_sync_on_admin_resolution(self):
        """Verify Student and Parent status APIs immediately reflect RESOLVED state when Admin resolves the incident."""
        res = create_emergency(
            reporter_id=8801,
            reporter_name='AdminTest Student A',
            reporter_role='student',
            category='Medical Emergency',
            severity='HIGH',
            campus_zone='Hostel Block B',
            skip_idempotency=True
        )
        emg_id = res['emergency']['emergency_id']

        # Admin resolves SOS
        conn = get_db_connection()
        try:
            transition_emergency_status(emg_id, 'RESOLVED', 'Admin Commander', 'admin', notes='Assisted by Health Center nurse.', conn=conn)
        finally:
            conn.close()

        # 1. Student Status API check
        with self.client.session_transaction() as sess:
            sess['student_id'] = 8801
            sess['user_role'] = 'student'

        resp_st = self.client.get('/api/student/emergency/status')
        self.assertEqual(resp_st.status_code, 200)
        data_st = resp_st.get_json()
        self.assertTrue(data_st['success'])
        self.assertFalse(data_st['is_active'])
        self.assertEqual(data_st['status'], 'RESOLVED')
        self.assertEqual(data_st['incident_id'], emg_id)

        # 2. Parent Status API check
        with self.client.session_transaction() as sess:
            sess['parent_id'] = 8802
            sess['user_role'] = 'parent'

        resp_pt = self.client.get('/api/parent/emergency/status')
        self.assertEqual(resp_pt.status_code, 200)
        data_pt = resp_pt.get_json()
        self.assertTrue(data_pt['success'])
        self.assertFalse(data_pt['is_active'])
        self.assertEqual(data_pt['status'], 'RESOLVED')


if __name__ == '__main__':
    unittest.main()
