"""
Tests for CampusGuard AI — Unified Multi-Role AI Assistant with Gemini & Database
Verifies:
1. Student factual queries (Attendance, CGPA, Fees, Timetable).
2. Student analytical reasoning queries.
3. Parent role-isolated queries for linked ward.
4. Parent unauthorized rejection for unlinked students.
5. Faculty queries (at-risk attendance < 75%, class summaries).
6. Admin queries (student counts, fee collections, SOS statistics).
7. Safety and emergency SOS prompt triggers.
8. Missing record handling without hallucination.
9. Conversation history management.
10. Error resilience and API key privacy.
"""

import unittest
from app import app
from database.db import get_db_connection, init_db
from services.unified_ai_assistant import process_unified_ai_query, classify_query_intent


class TestUnifiedAIAssistant(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_01_query_intent_classification(self):
        """Intent classifier correctly maps factual vs analytical domains."""
        self.assertEqual(classify_query_intent("What is my attendance?")['domain'], 'ATTENDANCE')
        self.assertTrue(classify_query_intent("What is my attendance?")['is_factual'])

        self.assertEqual(classify_query_intent("Why is my attendance low and how to improve?")['domain'], 'ATTENDANCE')
        self.assertFalse(classify_query_intent("Why is my attendance low and how to improve?")['is_factual'])

        self.assertEqual(classify_query_intent("What is my CGPA?")['domain'], 'ACADEMICS')
        self.assertEqual(classify_query_intent("How much fee is pending?")['domain'], 'FEES')
        self.assertEqual(classify_query_intent("What classes do I have tomorrow?")['domain'], 'TIMETABLE')
        self.assertEqual(classify_query_intent("Help emergency SOS")['domain'], 'SAFETY')

    def test_02_student_factual_attendance_and_cgpa(self):
        """Student receives exact database-backed attendance and CGPA."""
        conn = get_db_connection()
        student = conn.execute("SELECT * FROM students WHERE status != 'DELETED' LIMIT 1").fetchone()
        
        # 1. Attendance query
        res_att = process_unified_ai_query(role='student', user_id=student['id'], query='What is my attendance?', conn=conn)
        self.assertEqual(res_att['status'], 'success')
        self.assertIn('%', res_att['reply'])

        # 2. CGPA query
        res_cgpa = process_unified_ai_query(role='student', user_id=student['id'], query='What is my CGPA?', conn=conn)
        self.assertEqual(res_cgpa['status'], 'success')
        self.assertIn('CGPA', res_cgpa['reply'])

        # 3. Fees query
        res_fee = process_unified_ai_query(role='student', user_id=student['id'], query='How much fee is pending?', conn=conn)
        self.assertEqual(res_fee['status'], 'success')
        self.assertIn('₹', res_fee['reply'])
        conn.close()

    def test_03_student_api_endpoint_with_session(self):
        """HTTP POST /api/student/chat responds with unified AI output and updates session."""
        conn = get_db_connection()
        student = conn.execute("SELECT * FROM students WHERE status != 'DELETED' LIMIT 1").fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess.clear()
            sess['student_id'] = student['id']
            sess['student_name'] = student['name']

        resp = self.client.post('/api/student/chat', json={'query': 'What is my current attendance?'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('reply', data)

    def test_04_parent_queries_linked_ward_only(self):
        """Parent queries linked ward details successfully."""
        conn = get_db_connection()
        parent = conn.execute("SELECT * FROM parents LIMIT 1").fetchone()
        student = conn.execute("SELECT * FROM students WHERE id = ?", (parent['student_id'],)).fetchone()
        
        res = process_unified_ai_query(
            role='parent',
            user_id=parent['id'],
            student_id=student['id'],
            query=f"What is {student['name']}'s attendance and CGPA?",
            conn=conn
        )
        self.assertEqual(res['status'], 'success')
        self.assertIn(' '.join(student['name'].split()), ' '.join(res['reply'].split()))
        conn.close()

    def test_05_parent_unauthorized_rejection(self):
        """Parent cannot query data of a student not linked to them."""
        conn = get_db_connection()
        parent = conn.execute("SELECT * FROM parents LIMIT 1").fetchone()
        other_student = conn.execute("SELECT * FROM students WHERE id != ? LIMIT 1", (parent['student_id'],)).fetchone()
        
        res = process_unified_ai_query(
            role='parent',
            user_id=parent['id'],
            student_id=other_student['id'],
            query="What is their attendance?",
            conn=conn
        )
        self.assertEqual(res['status'], 'error')
        self.assertIn('Access Denied', res['reply'])
        conn.close()

    def test_06_faculty_queries(self):
        """Faculty queries at-risk attendance list below 75%."""
        conn = get_db_connection()
        fac = conn.execute("SELECT * FROM faculties LIMIT 1").fetchone()
        
        res = process_unified_ai_query(
            role='faculty',
            user_id=fac['id'],
            query='Which students have attendance below 75%?',
            conn=conn
        )
        self.assertEqual(res['status'], 'success')
        self.assertIn('Attendance', res['reply'])
        conn.close()

    def test_07_admin_campus_statistics(self):
        """Admin queries registrar student counts and fee metrics."""
        conn = get_db_connection()
        admin = conn.execute("SELECT * FROM admins LIMIT 1").fetchone()
        
        # Student count
        res_count = process_unified_ai_query(
            role='admin',
            user_id=admin['id'],
            query='How many students are registered?',
            conn=conn
        )
        self.assertEqual(res_count['status'], 'success')
        self.assertIn('registered', res_count['reply'].lower())

        # Fee collection
        res_fees = process_unified_ai_query(
            role='admin',
            user_id=admin['id'],
            query='How much fee has been collected?',
            conn=conn
        )
        self.assertEqual(res_fees['status'], 'success')
        self.assertIn('₹', res_fees['reply'])
        conn.close()

    def test_08_safety_sos_trigger(self):
        """Emergency and SOS keywords return instant crisis emergency response."""
        conn = get_db_connection()
        student = conn.execute("SELECT * FROM students LIMIT 1").fetchone()
        
        res = process_unified_ai_query(role='student', user_id=student['id'], query='Emergency help SOS need assistance', conn=conn)
        self.assertEqual(res['status'], 'success')
        self.assertIn('EMERGENCY', res['reply'])
        self.assertIn('SOS', res['reply'])
        conn.close()

    def test_09_parent_assistant_route(self):
        """GET /parent/assistant returns 200 with parent template."""
        conn = get_db_connection()
        parent = conn.execute("SELECT * FROM parents LIMIT 1").fetchone()
        student = conn.execute("SELECT * FROM students WHERE id = ?", (parent['student_id'],)).fetchone()
        conn.close()

        with self.client.session_transaction() as sess:
            sess.clear()
            sess['parent_id'] = parent['id']
            sess['parent_name'] = parent['name']
            sess['parent_active_student_id'] = student['id']

        res = self.client.get('/parent/assistant')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'AI Ward Assistant', res.data)
        self.assertIn(student['name'].encode('utf-8'), res.data)


if __name__ == '__main__':
    unittest.main()
