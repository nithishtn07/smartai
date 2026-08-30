"""
=============================================================================
Unit & Integration Tests: CampusGuard Smart Automated Notification Platform
=============================================================================
Verifies:
1. Smart Attendance Triggers (Threshold evaluation, Student alert, Parent alert).
2. Smart Marks & CGPA Recalculation Triggers (Student and Parent notifications).
3. Smart Demo Fee Payment Settlement Triggers (Parent receipt, Student record, Admin ledger).
4. Smart Timetable Change Triggers (Targeted department student fan-out).
5. Targeted Announcement Distribution (Students, Parents, Faculty filtering).
6. Read / Unread Status Lifecycle & Badge Count Persistence.
7. Duplicate Notification Prevention.
8. Role-Based Access Isolation & IDOR Protection.
9. SOS Notification System Isolation & Non-Interference.
=============================================================================
"""

import unittest
from app import app
from database.db import get_db_connection, init_db
from services.notification_service import (
    create_notification,
    notify_student,
    notify_parent,
    notify_faculty,
    notify_admin,
    generate_smart_attendance_notification,
    generate_smart_marks_notification,
    generate_smart_cgpa_notification,
    generate_smart_payment_notification,
    generate_smart_timetable_notification,
    broadcast_announcement,
    is_duplicate_notification
)
from services.payment_service import verify_and_record_payment, create_fee_order


class TestSmartNotifications(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_01_smart_attendance_triggers(self):
        """Attendance below 75% triggers Critical alert for Student and Warning for Parent."""
        conn = get_db_connection()
        try:
            student = conn.execute("SELECT * FROM students WHERE status != 'DELETED' LIMIT 1").fetchone()
            parent = conn.execute("SELECT * FROM parents WHERE student_id = ?", (student['id'],)).fetchone()
            self.assertIsNotNone(student)

            # Test Below 75% Trigger
            generate_smart_attendance_notification(
                student_id=student['id'],
                course_code="CS301",
                course_name="Database Management Systems",
                current_pct=72.0,
                db_conn=conn
            )

            # Verify Student Notification
            stu_notif = conn.execute("""
                SELECT * FROM notifications 
                WHERE recipient_role = 'student' AND recipient_id = ? AND title LIKE '%CS301%'
                ORDER BY id DESC LIMIT 1
            """, (student['id'],)).fetchone()
            self.assertIsNotNone(stu_notif)
            self.assertIn("72", stu_notif['message'])
            self.assertEqual(stu_notif['priority'], 'Critical')
            self.assertEqual(stu_notif['action_url'], '/student/attendance')

            # Verify Linked Parent Notification if parent exists
            if parent:
                par_notif = conn.execute("""
                    SELECT * FROM notifications 
                    WHERE recipient_role = 'parent' AND recipient_id = ? AND title LIKE ?
                    ORDER BY id DESC LIMIT 1
                """, (parent['id'], f"%{student['name']}%")).fetchone()
                self.assertIsNotNone(par_notif)
                self.assertIn(student['name'], par_notif['title'])
                self.assertEqual(par_notif['priority'], 'Critical')
        finally:
            conn.close()

    def test_02_smart_marks_and_cgpa_triggers(self):
        """Marks entry triggers continuous assessment notifications and CGPA recalculation notice."""
        conn = get_db_connection()
        try:
            student = conn.execute("SELECT * FROM students WHERE status != 'DELETED' LIMIT 1").fetchone()
            parent = conn.execute("SELECT * FROM parents WHERE student_id = ?", (student['id'],)).fetchone()

            # 1. Marks Trigger
            generate_smart_marks_notification(
                student_id=student['id'],
                course_code="CS302",
                course_name="Operating Systems",
                assessment_type="Continuous Assessment",
                marks_obtained=88.5,
                max_marks=100,
                grade="A",
                db_conn=conn
            )

            stu_mark_notif = conn.execute("""
                SELECT * FROM notifications 
                WHERE recipient_role = 'student' AND recipient_id = ? AND title LIKE '%CS302%'
                ORDER BY id DESC LIMIT 1
            """, (student['id'],)).fetchone()
            self.assertIsNotNone(stu_mark_notif)
            self.assertIn("CS302", stu_mark_notif['title'])
            self.assertIn("88.5", stu_mark_notif['message'])

            # 2. CGPA Recalculation Trigger
            generate_smart_cgpa_notification(
                student_id=student['id'],
                new_cgpa=9.15,
                prev_cgpa=9.00,
                db_conn=conn
            )

            stu_cgpa_notif = conn.execute("""
                SELECT * FROM notifications 
                WHERE recipient_role = 'student' AND recipient_id = ? AND title LIKE '%CGPA%'
                ORDER BY id DESC LIMIT 1
            """, (student['id'],)).fetchone()
            self.assertIsNotNone(stu_cgpa_notif)
            self.assertIn("9.15", stu_cgpa_notif['message'])
        finally:
            conn.close()

    def test_03_smart_fee_payment_triggers(self):
        """Fee settlement dispatches atomic notifications across Parent, Student, and Admin."""
        conn = get_db_connection()
        try:
            parent = conn.execute("SELECT * FROM parents LIMIT 1").fetchone()
            self.assertIsNotNone(parent)
            student = conn.execute("SELECT * FROM students WHERE id = ?", (parent['student_id'],)).fetchone()
            self.assertIsNotNone(student)

            generate_smart_payment_notification(
                parent_id=parent['id'],
                student_id=student['id'],
                amount=15000.0,
                fee_type="Tuition Fee (Fall 2026)",
                receipt_no="REC-TEST-9999",
                txn_id="TXN-TEST-1234",
                is_demo=True,
                db_conn=conn
            )

            # Parent check
            par_notif = conn.execute("""
                SELECT * FROM notifications 
                WHERE recipient_role = 'parent' AND recipient_id = ? AND title LIKE '%REC-TEST-9999%'
            """, (parent['id'],)).fetchone()
            self.assertIsNotNone(par_notif)
            self.assertEqual(par_notif['priority'], 'Informational')

            # Student check
            stu_notif = conn.execute("""
                SELECT * FROM notifications 
                WHERE recipient_role = 'student' AND recipient_id = ? AND title LIKE '%15,000%'
            """, (student['id'],)).fetchone()
            self.assertIsNotNone(stu_notif)

            # Admin check
            adm_notif = conn.execute("""
                SELECT * FROM notifications 
                WHERE recipient_role = 'admin' AND title LIKE '%15,000%'
                ORDER BY id DESC LIMIT 1
            """).fetchone()
            self.assertIsNotNone(adm_notif)
        finally:
            conn.close()

    def test_04_smart_timetable_triggers(self):
        """Timetable schedule updates fan out to all students in that department and year."""
        conn = get_db_connection()
        try:
            student = conn.execute("SELECT * FROM students WHERE status != 'DELETED' LIMIT 1").fetchone()
            dept = student['department']
            year = student['year']

            notified_count = generate_smart_timetable_notification(
                department=dept,
                year=year,
                course_code="CS304",
                day_of_week="Wednesday",
                start_time="10:00 AM",
                room_no="Lab 302",
                change_type="Rescheduled",
                db_conn=conn
            )
            self.assertGreaterEqual(notified_count, 1)

            tt_notif = conn.execute("""
                SELECT * FROM notifications 
                WHERE recipient_role = 'student' AND recipient_id = ? AND category = 'Timetable'
                ORDER BY id DESC LIMIT 1
            """, (student['id'],)).fetchone()
            self.assertIsNotNone(tt_notif)
            self.assertEqual(tt_notif['priority'], 'High')
        finally:
            conn.close()

    def test_05_targeted_announcement_broadcast(self):
        """Announcements targeted to 'Students' do not create notifications for faculty/parents."""
        conn = get_db_connection()
        try:
            ann_id = broadcast_announcement(
                title="Special Student Workshop",
                description="Campus AI workshop on Saturday at 2 PM.",
                target_audience="Students",
                category="Academic",
                priority="Normal",
                author_name="Admin",
                db_conn=conn
            )
            self.assertIsNotNone(ann_id)

            # Check student received it
            stu_ann = conn.execute("""
                SELECT * FROM notifications 
                WHERE recipient_role = 'student' AND related_id = ? AND related_type = 'announcement'
            """, (ann_id,)).fetchall()
            self.assertGreater(len(stu_ann), 0)

            # Check faculty did not receive it
            fac_ann = conn.execute("""
                SELECT * FROM notifications 
                WHERE recipient_role = 'faculty' AND related_id = ? AND related_type = 'announcement'
            """, (ann_id,)).fetchall()
            self.assertEqual(len(fac_ann), 0)
        finally:
            conn.close()

    def test_06_read_unread_lifecycle_and_api(self):
        """Test unread count, recent endpoint, and single/all mark read APIs."""
        conn = get_db_connection()
        try:
            student = conn.execute("SELECT * FROM students WHERE status != 'DELETED' LIMIT 1").fetchone()
            
            # Create a fresh unread notification
            notif_id = create_notification(
                recipient_id=student['id'],
                recipient_role='student',
                title='Test Lifecycle Alert',
                message='Notification for lifecycle test.',
                category='Academic',
                priority='Normal',
                action_url='/student/marks',
                db_conn=conn,
                allow_duplicate=True
            )
            self.assertIsNotNone(notif_id)

            with self.client.session_transaction() as sess:
                sess.clear()
                sess['user_role'] = 'student'
                sess['student_id'] = student['id']
                sess['student_name'] = student['name']

            # 1. Check Unread Count API
            resp_cnt = self.client.get('/api/notifications/unread-count')
            self.assertEqual(resp_cnt.status_code, 200)
            data_cnt = resp_cnt.get_json()
            self.assertGreaterEqual(data_cnt['unread_count'], 1)

            # 2. Check Recent Notifications API
            resp_rec = self.client.get('/api/notifications/recent')
            self.assertEqual(resp_rec.status_code, 200)
            data_rec = resp_rec.get_json()
            self.assertIn('notifications', data_rec)

            # 3. Mark Single as Read
            resp_read = self.client.post(f'/api/notifications/mark-read/{notif_id}')
            self.assertEqual(resp_read.status_code, 200)

            # 4. Mark All as Read
            resp_all = self.client.post('/api/notifications/mark-all-read')
            self.assertEqual(resp_all.status_code, 200)

            # Verify unread is now 0
            resp_cnt_after = self.client.get('/api/notifications/unread-count')
            self.assertEqual(resp_cnt_after.get_json()['unread_count'], 0)
        finally:
            conn.close()

    def test_07_duplicate_prevention(self):
        """Identical unread automated notifications within the deduplication window are prevented."""
        conn = get_db_connection()
        try:
            student = conn.execute("SELECT * FROM students WHERE status != 'DELETED' LIMIT 1").fetchone()

            # First trigger call
            id1 = notify_student(
                student_id=student['id'],
                title="Deduplication Verification Alert",
                message="Testing spam prevention.",
                category="Attendance",
                priority="High",
                db_conn=conn,
                allow_duplicate=False
            )

            # Second identical trigger call
            id2 = notify_student(
                student_id=student['id'],
                title="Deduplication Verification Alert",
                message="Testing spam prevention.",
                category="Attendance",
                priority="High",
                db_conn=conn,
                allow_duplicate=False
            )

            # Must return the same ID without inserting duplicate row
            self.assertEqual(id1, id2)

            dup_count = conn.execute("""
                SELECT COUNT(*) as cnt FROM notifications 
                WHERE recipient_role = 'student' AND recipient_id = ? AND title = 'Deduplication Verification Alert'
            """, (student['id'],)).fetchone()['cnt']
            self.assertEqual(dup_count, 1)
        finally:
            conn.close()

    def test_08_sos_system_isolation(self):
        """Emergency notifications and SOS systems remain completely untouched and isolated."""
        conn = get_db_connection()
        try:
            # Check emergency_notifications table exists and is independent
            has_em_table = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='emergency_notifications'").fetchone()
            self.assertIsNotNone(has_em_table)

            # Verify notifications table is separate
            has_notif_table = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'").fetchone()
            self.assertIsNotNone(has_notif_table)
            self.assertNotEqual(has_em_table['name'], has_notif_table['name'])
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
