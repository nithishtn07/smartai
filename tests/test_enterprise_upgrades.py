"""
=============================================================================
CampusGuard AI — Enterprise Upgrades Comprehensive Verification Test Suite
=============================================================================
Validates:
1. Institutional RAG Knowledge Search & Semantic Citations
2. Predictive Academic & Retention Risk ML Engine
3. Constraint-Based Smart Timetable Optimizer & Conflict Detector
4. Multi-Tier Automated Emergency Escalation Protocol
5. Indoor Geolocation & BLE Beacon Telemetry Resolution
6. CCTV Optical Computer Vision Safety Telemetry
7. TOTP Multi-Factor Authentication (2FA) & Recovery Codes
8. Sliding Window Rate Limiting & Brute Force Defense
9. Role-Based Access Control (RBAC) Granular Permissions
10. Cryptographic Tamper-Evident Audit Ledger Chaining
11. Dynamic Anti-Proxy QR Attendance Verification
12. Multilingual Localization (i18n) Engine
13. OpenAPI 3.0 / Swagger Interactive Explorer Endpoints
=============================================================================
"""

import unittest
import json
import sqlite3
import time
import app
from database.db import get_db_connection, init_db

# New Enterprise Modules
from services.rag_knowledge_engine import search_campus_knowledge, format_rag_context_for_llm
from services.predictive_ml_engine import evaluate_student_predictive_risk, evaluate_cohort_predictive_risk
from services.timetable_optimizer import detect_schedule_conflicts, optimize_department_timetable
from services.emergency_escalation_service import trigger_incident_escalation
from services.indoor_geofence_service import resolve_indoor_location
from services.cctv_vision_service import analyze_cctv_feed, get_all_campus_cctv_telemetry
from utils.mfa_service import generate_mfa_secret, get_totp_token, verify_totp_token, generate_backup_codes
from utils.rate_limiter import is_rate_limited, clear_rate_limits
from utils.rbac import has_permission, ROLE_PERMISSIONS
from utils.audit_ledger import append_secure_audit_entry, verify_audit_chain_integrity
from services.qr_attendance_service import generate_qr_attendance_token, verify_student_qr_scan
from utils.i18n import t, get_available_languages


class TestEnterpriseUpgrades(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.app.config['TESTING'] = True
        app.app.config['SECRET_KEY'] = 'enterprise-upgrade-test-secret-2026'
        init_db()

    def setUp(self):
        self.client = app.app.test_client()
        clear_rate_limits()

    # 1. RAG Knowledge Search
    def test_01_rag_knowledge_search(self):
        results = search_campus_knowledge("What is the minimum attendance requirement to write FAT exams?")
        self.assertTrue(len(results) > 0)
        top = results[0]
        self.assertEqual(top['id'], 'ACAD-01')
        self.assertIn("75.0%", top['content'])
        self.assertIn("Section 4.2", top['section'])

        context = format_rag_context_for_llm(results)
        self.assertIn("INSTITUTIONAL REGULATORY CITATIONS", context)
        print("[PASS] 1. RAG Knowledge Search & Citation Formatting verified.")

    # 2. Predictive Academic Risk Engine
    def test_02_predictive_academic_risk_engine(self):
        conn = get_db_connection()
        try:
            profile = evaluate_student_predictive_risk(1, conn)
            self.assertEqual(profile['student_id'], 1)
            self.assertIn('composite_risk_score', profile)
            self.assertIn('risk_tier', profile)
            self.assertIn('dropout_probability_pct', profile)
            self.assertTrue(0 <= profile['composite_risk_score'] <= 100)

            cohort = evaluate_cohort_predictive_risk(conn)
            self.assertTrue(len(cohort) > 0)
        finally:
            conn.close()
        print("[PASS] 2. Predictive Academic & Retention Risk ML Engine verified.")

    # 3. Timetable Constraint Optimizer
    def test_03_timetable_optimizer(self):
        mock_courses = [
            {'course_code': 'CS401', 'course_name': 'Cloud Computing', 'faculty_name': 'Dr. Rao', 'credits': 3},
            {'course_code': 'CS402L', 'course_name': 'Cloud Lab', 'faculty_name': 'Dr. Rao', 'credits': 2}
        ]
        rooms = ['CS-Lab 1', 'CS-301']
        opt = optimize_department_timetable(mock_courses, rooms, 'Computer Science', 4)
        self.assertEqual(opt['status'], 'OPTIMIZED')
        self.assertTrue(opt['total_sessions'] >= 3)
        self.assertEqual(opt['conflicts_count'], 0)

        # Test conflict detector
        clashing = [
            {'day_of_week': 'Monday', 'start_time': '09:00 AM', 'room_number': 'CS-101', 'faculty_name': 'Prof A', 'department': 'CS', 'year': 3},
            {'day_of_week': 'Monday', 'start_time': '09:00 AM', 'room_number': 'CS-101', 'faculty_name': 'Prof B', 'department': 'IT', 'year': 2}
        ]
        conflicts = detect_schedule_conflicts(clashing)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['type'], 'ROOM_COLLISION')
        print("[PASS] 3. Smart Timetable Optimizer & Conflict Detector verified.")

    # 4. Multi-Tier Emergency Escalation
    def test_04_emergency_escalation_protocol(self):
        conn = get_db_connection()
        try:
            res = trigger_incident_escalation(
                incident_id="SOS-TEST-999",
                severity="CRITICAL",
                location="Academic Block B 3rd Floor",
                student_name="Nithish Nagaraj",
                student_id=1,
                conn=conn
            )
            self.assertEqual(res['incident_id'], "SOS-TEST-999")
            self.assertEqual(res['escalation_stages_count'], 4)
            self.assertEqual(res['status'], 'ACTIVE_RESPONSE')
        finally:
            conn.close()
        print("[PASS] 4. Multi-Tier Emergency Escalation Matrix verified.")

    # 5. Indoor Geolocation & BLE Beacon Resolver
    def test_05_indoor_geofence_service(self):
        beacon_res = resolve_indoor_location(beacon_id="BCN-ENG-304")
        self.assertTrue(beacon_res['resolved'])
        self.assertEqual(beacon_res['zone_id'], 'ZONE_ENG_B_FL3')
        self.assertIn("3rd Floor", beacon_res['floor'])
        self.assertIn("North Stairwell", beacon_res['nearest_exit'])

        gps_res = resolve_indoor_location(latitude=12.9720, longitude=77.5950)
        self.assertTrue(gps_res['resolved'])
        self.assertEqual(gps_res['zone_id'], 'ZONE_ENG_B_FL3')
        print("[PASS] 5. Indoor Geolocation & BLE Beacon Resolver verified.")

    # 6. Computer Vision CCTV Safety Telemetry
    def test_06_cctv_vision_telemetry(self):
        cam = analyze_cctv_feed("CAM-MAIN-GATE-01", simulated_people_count=120)
        self.assertEqual(cam['safety_tier'], 'CRITICAL')
        self.assertTrue(len(cam['detected_anomalies']) > 0)
        self.assertEqual(cam['detected_anomalies'][0]['type'], 'CROWD_SURGE_DETECTED')

        all_cams = get_all_campus_cctv_telemetry()
        self.assertEqual(len(all_cams), 4)
        print("[PASS] 6. Optical CCTV Computer Vision Telemetry verified.")

    # 7. TOTP Multi-Factor Authentication
    def test_07_totp_mfa_engine(self):
        secret = generate_mfa_secret()
        self.assertTrue(len(secret) >= 16)

        token = get_totp_token(secret)
        self.assertEqual(len(token), 6)
        self.assertTrue(token.isdigit())

        is_valid = verify_totp_token(secret, token)
        self.assertTrue(is_valid)

        is_invalid = verify_totp_token(secret, "000000" if token != "000000" else "111111")
        self.assertFalse(is_invalid)

        backup_codes = generate_backup_codes(8)
        self.assertEqual(len(backup_codes), 8)
        print("[PASS] 7. TOTP MFA 2-Factor Authentication verified.")

    # 8. Sliding Window Rate Limiter
    def test_08_rate_limiter(self):
        key = "test_client_ip_127_0_0_1:login"
        for _ in range(5):
            limited = is_rate_limited(key, max_requests=5, window_seconds=10)
            self.assertFalse(limited)

        # 6th request triggers rate limit
        self.assertTrue(is_rate_limited(key, max_requests=5, window_seconds=10))
        print("[PASS] 8. Sliding Window Rate Limiter & Anti-Brute-Force verified.")

    # 9. RBAC Granular Permissions
    def test_09_rbac_permissions(self):
        self.assertTrue(has_permission('admin', 'anything_at_all'))
        self.assertTrue(has_permission('faculty', 'mark_attendance'))
        self.assertFalse(has_permission('student', 'mark_attendance'))
        self.assertTrue(has_permission('parent', 'pay_ward_fees'))
        self.assertTrue(has_permission('student', 'trigger_emergency_sos'))
        print("[PASS] 9. RBAC Granular Permissions Matrix verified.")

    # 10. Tamper-Evident Cryptographic Audit Ledger
    def test_10_cryptographic_audit_ledger(self):
        conn = get_db_connection()
        try:
            entry = append_secure_audit_entry(
                user_name="Dr. Rao",
                user_role="faculty",
                action="UPDATE_MARKS",
                details="Updated CS301 marks for STU001 to S Grade",
                ip_address="192.168.1.50",
                conn=conn
            )
            self.assertIn('block_hash', entry)
            self.assertEqual(len(entry['block_hash']), 64)

            audit_check = verify_audit_chain_integrity(conn)
            self.assertTrue(audit_check['integrity_verified'])
        finally:
            conn.close()
        print("[PASS] 10. Cryptographic Tamper-Evident Audit Ledger verified.")

    # 11. Anti-Proxy Dynamic QR Attendance
    def test_11_dynamic_qr_attendance(self):
        token_data = generate_qr_attendance_token("CS301", "FAC001", "CS-301")
        self.assertIn("CG-QR:CS301:", token_data['token'])
        self.assertTrue(token_data['expires_in_seconds'] <= 15)

        # Student in-room scan
        scan_res = verify_student_qr_scan(token_data['token'], student_id=1, student_lat=12.9716, student_lon=77.5946)
        self.assertTrue(scan_res['success'])

        # Expired token rejection
        fake_expired_token = "CG-QR:CS301:1000:invalidsig"
        exp_res = verify_student_qr_scan(fake_expired_token, student_id=1)
        self.assertFalse(exp_res['success'])
        print("[PASS] 11. Dynamic Anti-Proxy QR Attendance Engine verified.")

    # 12. Multilingual Localization (i18n)
    def test_12_multilingual_localization(self):
        self.assertEqual(t('emergency_sos', 'en'), 'Emergency SOS')
        self.assertEqual(t('emergency_sos', 'hi'), 'आपातकालीन एसओएस')
        self.assertEqual(t('emergency_sos', 'es'), 'SOS de Emergencia')
        self.assertEqual(t('emergency_sos', 'ta'), 'அவசர SOS')
        self.assertEqual(t('emergency_sos', 'fr'), 'SOS Urgence')

        langs = get_available_languages()
        self.assertTrue(len(langs) >= 5)
        print("[PASS] 12. Multilingual Localization (i18n) Engine verified.")

    # 13. REST API Swagger & OpenAPI Explorer Endpoints
    def test_13_api_swagger_endpoints(self):
        # 1. Swagger UI page
        res = self.client.get('/api/docs')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Swagger Explorer", res.data)

        # 2. OpenAPI JSON Spec
        res_json = self.client.get('/api/swagger.json')
        self.assertEqual(res_json.status_code, 200)
        spec = json.loads(res_json.data)
        self.assertEqual(spec['openapi'], '3.0.0')
        self.assertIn('/api/v1/predictive-risk', spec['paths'])

        # 3. RAG Search API
        res_search = self.client.get('/api/v1/knowledge-search?q=attendance%20condonation')
        self.assertEqual(res_search.status_code, 200)
        data = json.loads(res_search.data)
        self.assertEqual(data['status'], 'success')
        self.assertTrue(len(data['results']) > 0)

        # 4. CCTV Telemetry API
        res_cctv = self.client.get('/api/v1/cctv-telemetry')
        self.assertEqual(res_cctv.status_code, 200)
        cctv_data = json.loads(res_cctv.data)
        self.assertEqual(cctv_data['status'], 'success')
        self.assertEqual(cctv_data['active_cameras_count'], 4)

        # 5. Predictive Risk API
        res_risk = self.client.get('/api/v1/predictive-risk?student_id=1')
        self.assertEqual(res_risk.status_code, 200)
        risk_data = json.loads(res_risk.data)
        self.assertEqual(risk_data['status'], 'success')
        self.assertEqual(risk_data['data']['student_id'], 1)
        print("[PASS] 13. OpenAPI 3.0 / Swagger Interactive Explorer Endpoints verified.")


if __name__ == '__main__':
    unittest.main()
