# database.py
import mysql.connector as mc
from mysql.connector import Error
from dotenv import load_dotenv
import os

load_dotenv()  # loads .env in project root

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'edutrace_user'),
    'password': os.getenv('DB_PASS', ''),
    'database': os.getenv('DB_NAME', 'edutrace_db'),
    'autocommit': True
}

def get_conn():
    try:
        conn = mc.connect(**DB_CONFIG)
        return conn
    except Error as e:
        raise RuntimeError(f"Database connection failed: {e}")

def fetchall(query, params=None):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute(query, params or ())
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def fetchone(query, params=None):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute(query, params or ())
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def execute(query, params=None):
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute(query, params or ())
    conn.commit()
    cur.close()
    conn.close()