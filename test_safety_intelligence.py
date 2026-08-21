"""
=============================================================================
CampusGuard AI - Enterprise Safety Intelligence Automated Test Suite
Validates 0-100 quantitative risk scoring, temporal clustering, emerging risk
detection, repeated pattern correlation, NLP incident understanding, historical
context matching, priority ranking, and executive AI briefings.
=============================================================================
"""

import unittest
import sqlite3
import datetime
from app import app, init_db, DATABASE_FILE
from services.safety_intelligence import (
    calculate_location_risk_scores,
    analyze_temporal_patterns,
    detect_emerging_risks,
    detect_repeated_patterns,
    calculate_incident_priority,
    generate_executive_safety_briefing
)
from services.incident_analyzer import extract_incident_intelligence, correlate_safety_context
from services.campus_assistant import answer_campus_query

class TestCampusSafetyIntelligence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-safety-intelligence-secret-2026'
        init_db()

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['student_id'] = 1
            sess['student_register_number'] = 'STU001'
            sess['student_name'] = 'Nithish Kumar'

    # -----------------------------------------------------------------------
    # 1. 0–100 Location Risk Scoring Test
    # -----------------------------------------------------------------------
    def test_01_location_risk_scoring(self):
        """Verify 0-100 quantitative risk scoring algorithm and tier bucketing"""
        mock_incidents = [
            {'location': 'Parking Area', 'incident_type': 'Harassment', 'description': 'Harassment at night', 'created_at': '2026-08-20 19:30:00'},
            {'location': 'Parking Area', 'incident_type': 'Theft Attempt', 'description': 'Theft in dark alley', 'created_at': '2026-08-20 20:00:00'},
            {'location': 'Parking Area', 'incident_type': 'Suspicious Person', 'description': 'Suspicious stalking', 'created_at': '2026-08-19 19:45:00'},
            {'location': 'Parking Area', 'incident_type': 'Harassment', 'description': 'Verbal threat', 'created_at': '2026-08-18 20:15:00'},
            {'location': 'Central University Library', 'incident_type': 'Broken Chair', 'description': 'Squeaky chair', 'created_at': '2026-08-18 10:00:00'}
        ]

        scores = calculate_location_risk_scores(mock_incidents)
        parking = scores['Parking Area']
        library = scores['Central University Library']

        self.assertGreaterEqual(parking['risk_score'], 60)
        self.assertIn(parking['risk_level'], ['HIGH', 'CRITICAL'])
        self.assertEqual(parking['common_incident'], 'Harassment')
        self.assertEqual(parking['peak_time'], 'Evening (18:00 - 21:00)')

        self.assertLessEqual(library['risk_score'], 45)
        self.assertIn(library['risk_level'], ['LOW', 'MODERATE'])
        print("[PASS] 1. Location Risk Scoring: 0-100 risk scoring and tier categorization verified.")

    # -----------------------------------------------------------------------
    # 2. Temporal Pattern & Peak Window Analysis Test
    # -----------------------------------------------------------------------
    def test_02_temporal_risk_analysis(self):
        """Verify peak hours and day-of-week clustering calculations"""
        mock_incidents = [
            {'created_at': '2026-08-14 19:15:00'},
            {'created_at': '2026-08-14 19:45:00'},
            {'created_at': '2026-08-21 20:10:00'},
            {'created_at': '2026-08-19 10:30:00'}
        ]

        temporal = analyze_temporal_patterns(mock_incidents)
        self.assertEqual(temporal['status'], 'ACTIVE')
        self.assertEqual(temporal['peak_window'], 'Evening (18:00 - 21:00)')
        self.assertEqual(temporal['peak_count'], 3)
        self.assertEqual(temporal['peak_percentage'], 75.0)
        print("[PASS] 2. Temporal Risk Analysis: Peak window and percentage distribution verified.")

    # -----------------------------------------------------------------------
    # 3. Emerging Risk Surge Detection Test
    # -----------------------------------------------------------------------
    def test_03_emerging_risk_detection(self):
        """Verify surge percentage detection comparing rolling 30-day periods"""
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        mock_incidents = [
            {'location': 'Hostel Block B (Oak Wing)', 'created_at': now},
            {'location': 'Hostel Block B (Oak Wing)', 'created_at': now},
            {'location': 'Hostel Block B (Oak Wing)', 'created_at': now},
            {'location': 'Hostel Block B (Oak Wing)', 'created_at': now},
            {'location': 'Central University Library', 'created_at': '2026-06-01 10:00:00'}
        ]

        emerging = detect_emerging_risks(mock_incidents)
        self.assertGreaterEqual(len(emerging), 1)
        self.assertEqual(emerging[0]['location'], 'Hostel Block B (Oak Wing)')
        self.assertGreaterEqual(emerging[0]['surge_pct'], 50)
        self.assertIn("Hostel Block B", emerging[0]['alert_title'])
        print("[PASS] 3. Emerging Risk Detection: Automatic surge detection and alert generation verified.")

    # -----------------------------------------------------------------------
    # 4. Repeated Safety Pattern Correlation Test
    # -----------------------------------------------------------------------
    def test_04_repeated_safety_pattern_correlation(self):
        """Verify multi-complaint clustering into linked safety themes"""
        mock_incidents = [
            {'location': 'Hostel Block B (Oak Wing)', 'incident_type': 'Broken Lamp', 'description': 'Dark blind spot on walkway'},
            {'location': 'Hostel Block B (Oak Wing)', 'incident_type': 'Suspicious Person', 'description': 'Unsafe walking condition at night'}
        ]
        mock_complaints = [
            {'location': 'Hostel Block B (Oak Wing)', 'category': 'Safety', 'description': 'Harassment near dark hostel gate'}
        ]

        patterns = detect_repeated_patterns(mock_incidents, mock_complaints)
        self.assertGreaterEqual(len(patterns), 1)
        pat = patterns[0]
        self.assertEqual(pat['location'], 'Hostel Block B (Oak Wing)')
        self.assertIn("Lighting", pat['pattern_theme'])
        self.assertIn("patrol", pat['recommended_action'].lower())
        print("[PASS] 4. Repeated Pattern Correlation: Multi-report safety deficit detection verified.")

    # -----------------------------------------------------------------------
    # 5. Natural Language Incident Understanding Test
    # -----------------------------------------------------------------------
    def test_05_nlp_incident_understanding(self):
        """Verify extraction of severity, priority, risk indicators, and department"""
        text = "There is dense smoke and sparks coming from the electrical distribution panel in Block C and students are still inside."
        intel = extract_incident_intelligence(text, "Academic Block C")

        self.assertEqual(intel['severity'], 'CRITICAL')
        self.assertEqual(intel['priority'], 'IMMEDIATE')
        self.assertIn('Smoke/Fire Hazard', intel['risk_indicators'])
        self.assertIn('Campus Security', intel['department'])
        self.assertIn('fire', intel['recommended_action'].lower())
        print("[PASS] 5. NLP Incident Understanding: Severity, risk indicators, and response units verified.")

    # -----------------------------------------------------------------------
    # 6. Historical Safety Context Engine Test
    # -----------------------------------------------------------------------
    def test_06_historical_safety_context(self):
        """Verify matching of incoming incident against historical zone patterns"""
        historical = [
            {'location': 'Parking Area', 'incident_type': 'Harassment', 'created_at': '2026-08-10 19:30:00'},
            {'location': 'Parking Area', 'incident_type': 'Harassment', 'created_at': '2026-08-11 20:00:00'},
            {'location': 'Parking Area', 'incident_type': 'Harassment', 'created_at': '2026-08-12 19:45:00'}
        ]

        new_report = {'location': 'Parking Area', 'incident_type': 'Harassment'}
        context = correlate_safety_context(new_report, historical)

        self.assertTrue(context['has_pattern'])
        self.assertEqual(context['match_count'], 3)
        self.assertIn("Similar historical pattern detected", context['pattern_summary'])
        self.assertGreaterEqual(len(context['recommended_actions']), 2)
        print("[PASS] 6. Historical Safety Context: Spatial-temporal pattern matching verified.")

    # -----------------------------------------------------------------------
    # 7. Priority Queue Composite Scoring Test
    # -----------------------------------------------------------------------
    def test_07_priority_queue_scoring(self):
        """Verify composite priority score (0-100) ranks critical events at top"""
        crit_incident = {'incident_type': 'EMERGENCY_SOS', 'status': 'ACTIVE'}
        low_incident = {'incident_type': 'Broken Chair', 'status': 'RESOLVED'}

        crit_score = calculate_incident_priority(crit_incident, location_risk_score=85)
        low_score = calculate_incident_priority(low_incident, location_risk_score=20)

        self.assertGreaterEqual(crit_score, 85)
        self.assertLessEqual(low_score, 45)
        self.assertGreater(crit_score, low_score)
        print("[PASS] 7. Priority Queue Scoring: Composite ranking correctly prioritizes emergencies.")

    # -----------------------------------------------------------------------
    # 8. Executive AI Safety Briefing Test
    # -----------------------------------------------------------------------
    def test_08_executive_safety_briefing(self):
        """Verify institutional safety briefing synthesis from database telemetry"""
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        incidents = conn.execute("SELECT * FROM incidents").fetchall()
        complaints = conn.execute("SELECT * FROM complaints").fetchall()
        conn.close()

        zone_scores = calculate_location_risk_scores(incidents, complaints)
        briefing = generate_executive_safety_briefing(incidents, complaints, zone_scores)

        self.assertIn(briefing['overall_risk_level'], ['LOW-MODERATE', 'MEDIUM-HIGH', 'HIGH', 'CRITICAL'])
        self.assertGreaterEqual(len(briefing['top_hotspots']), 1)
        self.assertGreaterEqual(len(briefing['ai_recommendations']), 1)
        self.assertTrue(len(briefing['peak_risk_window']) > 5)
        print("[PASS] 8. Executive Safety Briefing: Multi-source briefing synthesis verified.")

    # -----------------------------------------------------------------------
    # 9. Admin & Security Assistant Queries Test
    # -----------------------------------------------------------------------
    def test_09_assistant_safety_queries(self):
        """Verify AI Campus Assistant answers high-risk locations, peak hours, and trends"""
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        try:
            # Query 1: Highest risk locations
            resp_risk = answer_campus_query(1, "What are the highest-risk campus locations?", conn)
            self.assertIn("Campus Safety Risk Rankings", resp_risk)
            self.assertIn("Risk Score", resp_risk)

            # Query 2: Peak hours
            resp_peak = answer_campus_query(1, "What are the peak risk hours?", conn)
            self.assertIn("Peak Risk Window", resp_peak)

            # Query 3: Trends
            resp_trend = answer_campus_query(1, "Are incidents increasing this month?", conn)
            self.assertIn("Trend", resp_trend)
        finally:
            conn.close()

        print("[PASS] 9. AI Campus Assistant: Security intelligence conversational queries verified.")

    # -----------------------------------------------------------------------
    # 10. Interactive Zone Intelligence API Endpoint Test
    # -----------------------------------------------------------------------
    def test_10_zone_intel_api_endpoint(self):
        """Verify GET /api/security/zone-intel/<zone_id> returns structured telemetry"""
        resp = self.client.get('/api/security/zone-intel/parking')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['zone_id'], 'parking')
        self.assertGreaterEqual(data['risk_score'], 50)
        self.assertIn('Parking', data['short_name'])
        self.assertIn('CCTVs Active', f"{data['cctv_count']} CCTVs Active")
        print("[PASS] 10. Zone Intelligence API: Interactive telemetry JSON endpoint verified.")

if __name__ == '__main__':
    unittest.main()
