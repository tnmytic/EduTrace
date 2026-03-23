# wifi_reader.py
"""
Wi-Fi MAC log reader for EduTrace.
Reads a CSV of connected MACs, finds matching students and marks them Present.
Two modes: API mode (default) calls your Flask /mark_attendance endpoint
or DB mode writes directly to the attendance table.
"""

import csv
import os
import requests
from datetime import date
from dotenv import load_dotenv

# For DB mode
import mysql.connector as mc

load_dotenv()

# ---------- CONFIG ----------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(PROJECT_ROOT, 'connected_macs.csv')

# Mode: "api" or "db"
MODE = os.getenv('WIFI_MODE', 'api')   # set WIFI_MODE=db in .env to use DB mode

# API settings (if using API)
API_BASE = os.getenv('API_BASE', 'http://127.0.0.1:5000')
MARK_ENDPOINT = f"{API_BASE}/mark_attendance"  # expects JSON { student_id, source }

# DB settings (if using DB mode)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'edutrace_user'),
    'password': os.getenv('DB_PASS', ''),
    'database': os.getenv('DB_NAME', 'edutrace_db'),
    'autocommit': True
}

# Optional: risk filter - ignore devices with unknown MACs, or use mapping file
# ---------- END CONFIG ----------

def read_mac_csv(path):
    macs = set()
    if not os.path.exists(path):
        print("CSV not found:", path)
        return macs
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            mac = r.get('mac_address') or r.get('MAC') or r.get('mac') or ''
            mac = mac.strip().upper()
            if mac:
                macs.add(mac)
    return macs

# DB helper for mapping MAC -> student_id
def get_mac_to_student_map():
    conn = mc.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT student_id, device_mac FROM students WHERE device_mac IS NOT NULL;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    mapping = {}
    for r in rows:
        mapping[r['device_mac'].strip().upper()] = r['student_id']
    return mapping

def mark_via_api(student_id, source='WIFI'):
    payload = {"student_id": student_id, "source": source}
    try:
        r = requests.post(MARK_ENDPOINT, json=payload, timeout=5)
        return r.status_code, r.text
    except Exception as e:
        return None, str(e)

def mark_via_db(student_id, source='WIFI'):
    conn = mc.connect(**DB_CONFIG)
    cur = conn.cursor()
    q = """
    INSERT INTO attendance (student_id, attendance_date, status, source)
    VALUES (%s, %s, 'Present', %s)
    ON DUPLICATE KEY UPDATE status='Present', source=%s
    """
    cur.execute(q, (student_id, date.today(), source, source))
    cur.close()
    conn.close()
    return True

def main():
    seen_macs = read_mac_csv(CSV_PATH)
    if not seen_macs:
        print("No MAC addresses detected in CSV.")
        return
    print(f"MACs found: {len(seen_macs)}")

    mapping = get_mac_to_student_map()
    matched = 0
    unknown = []

    for mac in seen_macs:
        sid = mapping.get(mac)
        if sid:
            matched += 1
            if MODE == 'api':
                code, resp = mark_via_api(sid, 'WIFI')
                print(f"API mark student {sid} -> {code} {resp}")
            else:
                mark_via_db(sid, 'WIFI')
                print(f"DB marked student {sid} present")
        else:
            unknown.append(mac)

    print(f"Matched students: {matched}. Unknown macs: {len(unknown)}")
    if unknown:
        print("Unknown MACs (sample):", unknown[:10])

if __name__ == '__main__':
    main()