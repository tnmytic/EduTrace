# scheduler.py
"""
EduTrace scheduler: find students absent for N days and send email alerts to parents.
Requires: python-dotenv, yagmail, mysql-connector-python
Run: python scheduler.py
"""

import os
from datetime import date, timedelta, datetime
from dotenv import load_dotenv
import yagmail
import mysql.connector as mc

load_dotenv()

# CONFIG from .env
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'edutrace_user'),
    'password': os.getenv('DB_PASS', ''),
    'database': os.getenv('DB_NAME', 'edutrace_db'),
    'autocommit': True
}
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
EMAIL_FROM = os.getenv('EMAIL_FROM', EMAIL_USER)
ATTACH_PATH = os.getenv('ATTACHMENT_PATH')  # optional attachment

# How many consecutive absent days before emailing
ALERT_DAYS = 3

def get_db_conn():
    return mc.connect(**DB_CONFIG)

def students_absent_for_n_days(n=ALERT_DAYS):
    """
    Return list of students absent for n consecutive days up to yesterday (not counting today).
    This function uses a simple approach: it checks attendance for the last n days and ensures no 'Present'.
    You can refine this to account for weekends/holidays.
    """
    conn = get_db_conn()
    cur = conn.cursor(dictionary=True)

    # date range: last n days (including today or excluding? choose policy)
    # We'll check the last n days including today to capture recent absence patterns.
    end = date.today()
    start = end - timedelta(days=n-1)

    # Get all students
    cur.execute("SELECT student_id, name, parent_email FROM students;")
    students = cur.fetchall()

    absent_students = []
    for s in students:
        sid = s['student_id']
        # fetch attendance records for the student in the date range
        cur.execute("""
            SELECT attendance_date, status
            FROM attendance
            WHERE student_id = %s
              AND attendance_date BETWEEN %s AND %s
            """, (sid, start, end))
        rows = cur.fetchall()
        # Build a map of date->status
        status_by_date = {r['attendance_date']: r['status'] for r in rows}
        # For every date in range, if missing treat as 'Absent'
        all_absent = True
        for i in range(n):
            d = start + timedelta(days=i)
            st = status_by_date.get(d, 'Absent')
            if st == 'Present':
                all_absent = False
                break
        if all_absent:
            absent_students.append({
                'student_id': sid,
                'name': s['name'],
                'parent_email': s['parent_email'],
                'start_date': start,
                'end_date': end
            })

    cur.close()
    conn.close()
    return absent_students

def already_alerted(student_id, start_date, end_date):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM absence_alerts
        WHERE student_id=%s AND first_absent_on=%s AND last_absent_on=%s
    """, (student_id, start_date, end_date))
    cnt = cur.fetchone()[0]
    cur.close()
    conn.close()
    return cnt > 0

def record_alert(student_id, streak_days, start_date, end_date, emailed_to):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO absence_alerts (student_id, streak_days, first_absent_on, last_absent_on, emailed_to, sent_at)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (student_id, streak_days, start_date, end_date, emailed_to, datetime.utcnow()))
    cur.close()
    conn.close()

def send_email(to_email, subject, body, attachments=None):
    if not EMAIL_USER or not EMAIL_PASS:
        raise RuntimeError("Email credentials not set in .env (EMAIL_USER, EMAIL_PASS)")
    yag = yagmail.SMTP(EMAIL_USER, EMAIL_PASS)
    yag.send(to=to_email, subject=subject, contents=body, attachments=attachments)

def compose_body(student_name, start_date, end_date):
    return f"""
Dear Parent / Guardian,

This is an automated alert from EduTrace.

Your child, {student_name}, has been marked absent from campus for {ALERT_DAYS} consecutive days
(from {start_date} to {end_date}).

Please contact the institution or ensure the student returns to classes. If this is an error,
you may contact the tutor to correct attendance records.

Regards,
EduTrace - Attendance Monitoring System
"""

def main():
    print(f"[{datetime.now()}] Checking for students absent for {ALERT_DAYS} days...")
    absent_list = students_absent_for_n_days(ALERT_DAYS)
    print(f"Found {len(absent_list)} students meeting the criteria.")
    for s in absent_list:
        sid = s['student_id']
        parent = s['parent_email']
        start = s['start_date']
        end = s['end_date']

        # skip if we've already sent this exact alert
        if already_alerted(sid, start, end):
            print(f"Skipping {sid} ({s['name']}) — alert already sent for this period.")
            continue

        subject = f"Attendance Alert: {s['name']}"
        body = compose_body(s['name'], start, end)

        attachments = None
        if ATTACH_PATH and os.path.exists(ATTACH_PATH):
            attachments = [ATTACH_PATH]

        try:
            send_email(parent, subject, body, attachments=attachments)
            print(f"Email sent to {parent} for student {s['name']}.")
            record_alert(sid, ALERT_DAYS, start, end, parent)
        except Exception as e:
            print(f"Failed to send email to {parent}: {e}")

if __name__ == "__main__":
    main()