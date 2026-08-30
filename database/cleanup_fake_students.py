"""
CampusGuard AI — Safe Database Cleanup Script for Fake & Test Student Records
Removes demo/sample/test students and their dependent records while preserving
genuine manual student additions and legitimate parent accounts.
"""

import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database.db import get_db_connection


def perform_cleanup():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Fetch all students currently in DB
        all_students = cursor.execute("SELECT id, register_number, name, email, parent_name, status FROM students").fetchall()
        print(f"[1] Total students found in database: {len(all_students)}")
        
        # 2. Identify legitimate vs fake/demo/test students
        legitimate_student_ids = []
        fake_student_ids = []
        
        for s in all_students:
            reg = s['register_number'].upper()
            if reg == 'STU004':  # Legitimate manually created student HARSHIKA
                legitimate_student_ids.append(s['id'])
                print(f"  [KEEP] Preserving genuine manual student: ID={s['id']}, Reg={s['register_number']}, Name={s['name']}")
            else:
                fake_student_ids.append(s['id'])
                
        print(f"[2] Identified {len(fake_student_ids)} fake/demo/test student records to remove.")
        print(f"[2] Preserved {len(legitimate_student_ids)} legitimate manual student records.")
        
        if not fake_student_ids:
            print("[INFO] No fake student records found to remove. Database is clean.")
            return

        placeholders = ', '.join(['?'] * len(fake_student_ids))
        
        # 3. Clean all dependent tables referencing students(id)
        # 3.1 Parent-Student Mappings
        res_ps = cursor.execute(f"DELETE FROM parent_student WHERE student_id IN ({placeholders})", fake_student_ids)
        print(f"  - Cleaned {res_ps.rowcount} parent_student mapping rows.")
        
        # 3.2 Marks & Assessments
        res_marks = cursor.execute(f"DELETE FROM marks WHERE student_id IN ({placeholders})", fake_student_ids)
        print(f"  - Cleaned {res_marks.rowcount} marks rows.")
        
        # 3.3 Attendance & Logs
        res_att = cursor.execute(f"DELETE FROM attendance WHERE student_id IN ({placeholders})", fake_student_ids)
        res_att_logs = cursor.execute(f"DELETE FROM attendance_logs WHERE student_id IN ({placeholders})", fake_student_ids)
        print(f"  - Cleaned {res_att.rowcount} attendance rows and {res_att_logs.rowcount} attendance logs.")
        
        # 3.4 Fees & Transactions
        cursor.execute(f"DELETE FROM payment_transactions WHERE student_id IN ({placeholders})", fake_student_ids)
        res_fees = cursor.execute(f"DELETE FROM fees WHERE student_id IN ({placeholders})", fake_student_ids)
        print(f"  - Cleaned {res_fees.rowcount} fee rows.")
        
        # 3.5 Hostel & Leaves
        cursor.execute(f"DELETE FROM hostel_details WHERE student_id IN ({placeholders})", fake_student_ids)
        cursor.execute(f"DELETE FROM hostel_leaves WHERE student_id IN ({placeholders})", fake_student_ids)
        
        # 3.6 Safety, Complaints, SOS, Wellbeing & Safe Walk
        cursor.execute(f"DELETE FROM complaints WHERE student_id IN ({placeholders})", fake_student_ids)
        cursor.execute(f"DELETE FROM incidents WHERE student_id IN ({placeholders})", fake_student_ids)
        cursor.execute(f"DELETE FROM wellbeing_appointments WHERE student_id IN ({placeholders})", fake_student_ids)
        cursor.execute(f"DELETE FROM safe_walk_sessions WHERE student_id IN ({placeholders})", fake_student_ids)
        cursor.execute(f"DELETE FROM emergencies WHERE user_role = 'student' AND user_id IN ({placeholders})", fake_student_ids)
        
        # 3.7 Submissions, Transport, Lab Experiments, Requests, Lost & Found, Settings, Alert Reads
        cursor.execute(f"DELETE FROM student_submissions WHERE student_id IN ({placeholders})", fake_student_ids)
        cursor.execute(f"DELETE FROM student_transport WHERE student_id IN ({placeholders})", fake_student_ids)
        cursor.execute(f"DELETE FROM lab_experiments WHERE student_id IN ({placeholders})", fake_student_ids)
        cursor.execute(f"DELETE FROM student_requests WHERE student_id IN ({placeholders})", fake_student_ids)
        cursor.execute(f"DELETE FROM lost_found WHERE student_id IN ({placeholders})", fake_student_ids)
        cursor.execute(f"DELETE FROM student_settings WHERE student_id IN ({placeholders})", fake_student_ids)
        cursor.execute(f"DELETE FROM student_alert_reads WHERE student_id IN ({placeholders})", fake_student_ids)

        # 3.8 Messages & Notifications
        cursor.execute(f"DELETE FROM notifications WHERE recipient_role = 'student' AND recipient_id IN ({placeholders})", fake_student_ids)
        cursor.execute(f"DELETE FROM parent_messages WHERE student_id IN ({placeholders})", fake_student_ids)
        cursor.execute(f"DELETE FROM messages WHERE student_id IN ({placeholders})", fake_student_ids)
        
        # 4. Handle Parent Accounts
        # Identify parents that are NOT linked to ANY remaining legitimate student
        all_parents = cursor.execute("SELECT id, parent_id, name, email, student_id FROM parents").fetchall()
        orphan_parent_ids = []
        for p in all_parents:
            active_links = cursor.execute("SELECT COUNT(*) FROM parent_student WHERE parent_id = ?", (p['id'],)).fetchone()[0]
            direct_legit_child = cursor.execute("SELECT COUNT(*) FROM students WHERE id = ? AND id NOT IN (" + placeholders + ")", [p['student_id']] + fake_student_ids).fetchone()[0]
            if active_links == 0 and direct_legit_child == 0:
                orphan_parent_ids.append(p['id'])
            elif p['student_id'] in fake_student_ids:
                # Reassign or nullify primary student_id to an active legitimate student if any, or NULL
                other_link = cursor.execute("SELECT student_id FROM parent_student WHERE parent_id = ? AND student_id NOT IN (" + placeholders + ")", [p['id']] + fake_student_ids).fetchone()
                new_stu_id = other_link['student_id'] if other_link else None
                cursor.execute("UPDATE parents SET student_id = ? WHERE id = ?", (new_stu_id, p['id']))
                
        if orphan_parent_ids:
            p_placeholders = ', '.join(['?'] * len(orphan_parent_ids))
            cursor.execute(f"DELETE FROM parent_alert_reads WHERE parent_id IN ({p_placeholders})", orphan_parent_ids)
            cursor.execute(f"DELETE FROM notifications WHERE recipient_role = 'parent' AND recipient_id IN ({p_placeholders})", orphan_parent_ids)
            cursor.execute(f"DELETE FROM parent_messages WHERE parent_id IN ({p_placeholders})", orphan_parent_ids)
            res_parents = cursor.execute(f"DELETE FROM parents WHERE id IN ({p_placeholders})", orphan_parent_ids)
            print(f"[4] Cleaned {res_parents.rowcount} unlinked/demo parent accounts.")
        else:
            print("[4] No orphaned parent accounts found.")
            
        # 5. Remove fake students from students table
        res_students = cursor.execute(f"DELETE FROM students WHERE id IN ({placeholders})", fake_student_ids)
        print(f"[5] Successfully deleted {res_students.rowcount} fake/seed/test student records from students table.")
        
        conn.commit()
        print("\n[SUCCESS] Database cleanup completed successfully. Transaction committed.")
        
        # 6. Post-cleanup audit
        remaining_students = cursor.execute("SELECT id, register_number, name, email FROM students").fetchall()
        remaining_parents = cursor.execute("SELECT id, parent_id, name, email FROM parents").fetchall()
        print(f"\n[SUMMARY AUDIT]")
        print(f"Remaining legitimate students: {len(remaining_students)}")
        for s in remaining_students:
            print(f"  - {s['register_number']}: {s['name']} ({s['email']})")
        print(f"Remaining legitimate parents: {len(remaining_parents)}")
        for p in remaining_parents:
            print(f"  - {p['parent_id']}: {p['name']} ({p['email']})")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Database cleanup failed: {e}")
        raise e
    finally:
        conn.close()


if __name__ == '__main__':
    perform_cleanup()
