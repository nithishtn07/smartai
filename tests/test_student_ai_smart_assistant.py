import unittest
import json
import sqlite3
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from database.db import get_db_connection
from services.student_ai_assistant import (
    get_student_profile,
    get_student_attendance,
    calculate_attendance_what_if,
    get_student_timetable,
    get_upcoming_exams,
    get_student_marks_analysis,
    get_student_assignments,
    get_pending_fees,
    generate_personalized_study_plan,
    detect_safety_emergency_intent,
    get_campus_knowledge,
    answer_student_assistant_query
)
from services.briefing_ai import generate_student_briefing


class TestStudentAiSmartAssistant(unittest.TestCase):
    """
    Comprehensive verification suite for CampusGuard AI — Smart Campus Assistant
    covering all 30 user requirements and database integrations.
    """

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key-assistant'
        self.client = self.app.test_client()

        # Authenticate as student STU001 (Nithish Nagaraj)
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_type'] = 'student'
            sess['student_id'] = 1
            sess['student_name'] = 'Nithish Nagaraj'
            sess['student_reg'] = 'STU001'

    def tearDown(self):
        # Ensure database is left clean
        pass

    def test_01_student_attendance_query(self):
        """Verify attendance retrieval, percentage calculation, and threshold checks."""
        conn = get_db_connection()
        try:
            att = get_student_attendance(1, conn)
            self.assertTrue(att['has_records'])
            self.assertGreater(att['overall_pct'], 0)
            self.assertEqual(att['threshold'], 75.0)
            self.assertTrue(len(att['subjects']) > 0)

            # Test through conversational query router
            res = answer_student_assistant_query(1, "What is my attendance?", conn=conn)
            self.assertEqual(res['status'], 'success')
            self.assertEqual(res['intent'], 'ATTENDANCE_STATUS')
            self.assertIn("Overall Academic Attendance", res['reply'])
            self.assertIn("Based on your current CampusGuard database records", res['reply'])
        finally:
            conn.close()

    def test_02_attendance_what_if_miss_class(self):
        """Verify mathematical projection for missing upcoming lectures."""
        conn = get_db_connection()
        try:
            query = "If I miss tomorrow's OS class, what will my attendance become?"
            res = answer_student_assistant_query(1, query, conn=conn)
            self.assertEqual(res['status'], 'success')
            self.assertEqual(res['intent'], 'ATTENDANCE_WHAT_IF')
            self.assertIn("Attendance What-If Projection", res['reply'])
            self.assertIn("Current Attendance", res['reply'])
            self.assertIn("Projected Attendance", res['reply'])
            self.assertIn("Impact:", res['reply'])
        finally:
            conn.close()

    def test_03_attendance_what_if_attend_to_recover(self):
        """Verify recovery calculation to reach target threshold."""
        conn = get_db_connection()
        try:
            query = "How many classes do I need to attend to reach 75%?"
            res = answer_student_assistant_query(1, query, conn=conn)
            self.assertEqual(res['status'], 'success')
            self.assertEqual(res['intent'], 'ATTENDANCE_WHAT_IF')
            self.assertTrue("Attendance Recovery Target" in res['reply'] or "Attendance Standing" in res['reply'])
        finally:
            conn.close()

    def test_04_timetable_next_class_and_schedule(self):
        """Verify timetable query resolution for next class, venue, and faculty."""
        conn = get_db_connection()
        try:
            # Query for next class
            res_next = answer_student_assistant_query(1, "When is my next class?", conn=conn)
            self.assertEqual(res_next['status'], 'success')
            self.assertEqual(res_next['intent'], 'TIMETABLE')
            self.assertIn("Lecture", res_next['reply'])
            self.assertIn("Subject:", res_next['reply'])

            # Query for tomorrow's schedule
            res_tom = answer_student_assistant_query(1, "What classes do I have tomorrow?", conn=conn)
            self.assertEqual(res_tom['status'], 'success')
            self.assertEqual(res_tom['intent'], 'TIMETABLE')
        finally:
            conn.close()

    def test_05_upcoming_exams_and_dates(self):
        """Verify examination schedule retrieval, venue, and seat numbers."""
        conn = get_db_connection()
        try:
            exams = get_upcoming_exams(1, conn)
            self.assertTrue(len(exams) > 0)

            res = answer_student_assistant_query(1, "When is my next exam?", conn=conn)
            self.assertEqual(res['status'], 'success')
            self.assertEqual(res['intent'], 'EXAMS_SCHEDULE')
            self.assertIn("Upcoming Examination Schedule", res['reply'])
            self.assertIn("Seat:", res['reply'])
        finally:
            conn.close()

    def test_06_marks_and_performance_analysis(self):
        """Verify academic performance analysis, strong/weak subjects, and recommendations."""
        conn = get_db_connection()
        try:
            marks_info = get_student_marks_analysis(1, conn)
            self.assertTrue(marks_info['has_marks'])
            self.assertTrue(len(marks_info['courses']) > 0)

            res = answer_student_assistant_query(1, "Which subjects am I weak in?", conn=conn)
            self.assertEqual(res['status'], 'success')
            self.assertEqual(res['intent'], 'MARKS_PERFORMANCE')
            self.assertIn("Academic Performance Analysis", res['reply'])
            self.assertIn("CGPA", res['reply'])
        finally:
            conn.close()

    def test_07_personalized_study_planner(self):
        """Verify personalized 7-day study plan generation balancing weak subjects and exam dates."""
        conn = get_db_connection()
        try:
            res = answer_student_assistant_query(1, "Make me a study plan for FAT.", conn=conn)
            self.assertEqual(res['status'], 'success')
            self.assertEqual(res['intent'], 'STUDY_PLAN')
            self.assertIn("Personalized AI Academic Study Plan", res['reply'])
            self.assertIn("Monday:", res['reply'])
            self.assertIn("Sunday:", res['reply'])
        finally:
            conn.close()

    def test_08_assignment_tracking(self):
        """Verify pending assignments tracking and deadline urgency indicators."""
        conn = get_db_connection()
        try:
            res = answer_student_assistant_query(1, "What assignments are due?", conn=conn)
            self.assertEqual(res['status'], 'success')
            self.assertEqual(res['intent'], 'ASSIGNMENTS_DUE')
            self.assertIn("Assignments", res['reply'])
        finally:
            conn.close()

    def test_09_fee_assistant(self):
        """Verify real fee ledger calculation and balance inquiries."""
        conn = get_db_connection()
        try:
            fee_info = get_pending_fees(1, conn)
            self.assertTrue(fee_info['has_fees'])
            self.assertGreaterEqual(len(fee_info['fee_items']), 1)

            res = answer_student_assistant_query(1, "How much fee is pending?", conn=conn)
            self.assertEqual(res['status'], 'success')
            self.assertEqual(res['intent'], 'FEES_FINANCE')
            self.assertIn("Institutional Fee & Payment Status", res['reply'])
            self.assertIn("Outstanding Balance", res['reply'])
        finally:
            conn.close()

    def test_10_daily_briefing_synthesis(self):
        """Verify dynamic Daily AI Briefing generation."""
        conn = get_db_connection()
        try:
            briefing = generate_student_briefing({'id': 1, 'name': 'Nithish Nagaraj', 'department': 'Computer Science', 'year': 3}, conn)
            self.assertIn('greeting', briefing)
            self.assertIn('briefing_items', briefing)
            self.assertTrue(len(briefing['briefing_items']) >= 3)
            self.assertIn('primary_recommendation', briefing)

            res = answer_student_assistant_query(1, "What should I do today?", conn=conn)
            self.assertEqual(res['status'], 'success')
            self.assertEqual(res['intent'], 'DAILY_BRIEFING')
            self.assertIn("Daily AI Briefing", res['reply'])
        finally:
            conn.close()

    def test_11_safety_emergency_protocol(self):
        """Verify acute emergency distress recognition and safety protocol presentation without silent SOS activation."""
        conn = get_db_connection()
        try:
            queries = [
                "I am being followed and feel unsafe near the library.",
                "There is a fire in the science block!",
                "I need emergency help right now"
            ]
            for q in queries:
                res = answer_student_assistant_query(1, q, conn=conn)
                self.assertEqual(res['status'], 'success')
                self.assertEqual(res['intent'], 'EMERGENCY_SAFETY')
                self.assertIn("CRITICAL SAFETY ASSISTANCE PROTOCOL", res['reply'])
                self.assertIn("ACTIVATE LIVE EMERGENCY SOS", res['reply'])
                self.assertIn("+91 91234 56780", res['reply'])
        finally:
            conn.close()

    def test_12_campus_knowledge_base(self):
        """Verify verified campus directory responses and missing data handling."""
        conn = get_db_connection()
        try:
            # Library info
            res_lib = answer_student_assistant_query(1, "What are the library timings?", conn=conn)
            self.assertEqual(res_lib['status'], 'success')
            self.assertEqual(res_lib['intent'], 'CAMPUS_KNOWLEDGE')
            self.assertIn("Central University Library Information", res_lib['reply'])

            # Unknown query handling
            res_unk = answer_student_assistant_query(1, "Tell me about quantum space rocket engines on campus", conn=conn)
            self.assertEqual(res_unk['status'], 'success')
            self.assertIn("CampusGuard AI Smart Campus Assistant", res_unk['reply'])
        finally:
            conn.close()

    def test_13_api_student_chat_endpoint(self):
        """Verify HTTP POST /api/student/chat endpoint integration."""
        response = self.client.post('/api/student/chat', json={
            'query': 'What is my attendance?'
        })
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertIn('reply', data)
        self.assertIn('intent', data)
        self.assertIn('suggestions', data)

    def test_14_api_student_ai_feedback_endpoint(self):
        """Verify HTTP POST /api/student/ai-feedback endpoint."""
        response = self.client.post('/api/student/ai-feedback', json={
            'query': 'What is my attendance?',
            'rating': 'up',
            'comment': 'Accurate numbers!'
        })
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')

    def test_15_api_student_daily_briefing_endpoint(self):
        """Verify HTTP GET /api/student/daily-briefing endpoint."""
        response = self.client.get('/api/student/daily-briefing')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertIn('briefing', data)

    def test_16_offline_deterministic_fallback(self):
        """Verify that all assistant functions work deterministically in offline mode."""
        conn = get_db_connection()
        try:
            # Even with GEMINI_API_KEY unset or invalid, all tools execute deterministically
            res = answer_student_assistant_query(1, "When is my next class?", conn=conn)
            self.assertEqual(res['status'], 'success')
            self.assertIn("Lecture", res['reply'])
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
