# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import date, datetime
from database import fetchall, execute, fetchone, get_conn
from geopy.distance import geodesic
from flask import session
from werkzeug.security import generate_password_hash, check_password_hash
import os
def is_in_campus(lat, lon):
    point = (lat, lon)
    distance_m = geodesic(point, CAMPUS_CENTER).meters
    return distance_m <= CAMPUS_RADIUS_M, distance_m
print(">> app.py starting — PID:", __import__('os').getpid())

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET', 'devsecret')

def admin_required():
    if session.get('role') != 'admin':
        flash("Admin access required", "danger")
        return False
    return True

# GEOfence configuration (center + radius in meters)
CAMPUS_CENTER = (26.769897, 75.877684)
CAMPUS_RADIUS_M = 250

# ---- Routes ----

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/timetable")
def timetable_view():
    pass
    # show weekly timetable grid

@app.route('/admin/timetable/edit/<int:timetable_id>', methods=['GET', 'POST'])
def edit_timetable(timetable_id):
    if session.get('role') != 'admin':
        flash("Admin access required", "danger")
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        day = request.form['day']
        period_no = request.form['period_no']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        subject_id = request.form['subject_id']

        cur.execute("""
        UPDATE timetable
        SET day=%s,
            period_no=%s,
            start_time=%s,
            end_time=%s,
            subject_id=%s
        WHERE timetable_id=%s
        """, (day, period_no, start_time, end_time, subject_id, timetable_id))

        conn.commit()
        flash("Timetable updated successfully", "success")
        return redirect(url_for('admin_timetable'))

    timetable = fetchone(
        "SELECT * FROM timetable WHERE timetable_id=%s",
        (timetable_id,)
    )

    subjects = fetchall("SELECT subject_id, subject_name FROM subjects")

    return render_template(
        "edit_timetable.html",
        timetable=timetable,
        subjects=subjects
    )

@app.route("/student/attendance")
def student_attendance():
    pass
    # show own period-wise attendance

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out", "success")
    return redirect(url_for('index'))

@app.route('/admin/timetable')
def admin_timetable():
    if session.get('role') != 'admin':
        flash("Admin access required", "danger")
        return redirect(url_for('admin_login'))

    q = """
    SELECT 
        t.timetable_id,
        t.day,
        t.period_no,
        t.start_time,
        t.end_time,
        sub.subject_name
    FROM timetable t
    JOIN subjects sub ON t.subject_id = sub.subject_id
    ORDER BY FIELD(t.day,'Mon','Tue','Wed','Thu','Fri','Sat'), t.period_no
    """
    rows = fetchall(q)
    return render_template("admin_timetable.html", rows=rows)

@app.route('/admin/mark-period/<int:timetable_id>', methods=['GET', 'POST'])
def mark_period(timetable_id):
    status = request.form.get("status")

    if status not in ["Present", "Absent"]:
       flash("Invalid attendance value", "danger")
       return redirect(request.url)

    # 1️⃣ Admin protection
    if session.get('role') != 'admin':
        flash("Admin access required", "danger")
        return redirect(url_for('admin_login'))

    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    # 2️⃣ Load period info
    cur.execute("""
        SELECT t.timetable_id, t.day, t.period_no,
               s.subject_name
        FROM timetable t
        JOIN subjects s ON t.subject_id = s.subject_id
        WHERE t.timetable_id = %s
    """, (timetable_id,))
    period = cur.fetchone()

    if not period:
        flash("Invalid period", "danger")
        return redirect(url_for('admin_timetable'))

    # 3️⃣ Load students
    cur.execute("""
        SELECT student_id, name, roll_no
        FROM students
        ORDER BY roll_no
    """)
    students = cur.fetchall()

    # 4️⃣ POST → save attendance
    if request.method == 'POST':
        for student in students:
            status = request.form.get(f"status_{student['student_id']}")

            cur.execute("""
                INSERT INTO period_attendance
                (student_id, timetable_id, status)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE status = VALUES(status)
            """, (student['student_id'], timetable_id, status))

        conn.commit()
        flash("Attendance marked successfully", "success")
        return redirect(url_for('admin_timetable'))

    # 5️⃣ GET → SHOW PAGE (THIS WAS MISSING)
    return render_template(
        "mark_period.html",
        period=period,
        students=students
    )

@app.route('/student/dashboard')
def student_dashboard():
    if session.get('role') != 'student':
        flash("Student login required", "danger")
        return redirect(url_for('student_login'))

    student_id = session['student_id']

    # 1. Overall attendance %
    overall_q = """
    SELECT 
      COUNT(*) AS total_classes,
      SUM(status='Present') AS present_count
    FROM period_attendance
    WHERE student_id = %s
    """
    overall = fetchone(overall_q, (student_id,))
    total = overall['total_classes'] or 0
    present = overall['present_count'] or 0
    percentage = round((present / total) * 100, 2) if total > 0 else 0

    # 2. Subject-wise attendance
    subject_q = """
    SELECT sub.subject_name,
           COUNT(pa.status) AS total,
           SUM(pa.status='Present') AS present
    FROM period_attendance pa
    JOIN timetable t ON pa.timetable_id = t.timetable_id
    JOIN subjects sub ON t.subject_id = sub.subject_id
    WHERE pa.student_id = %s
    GROUP BY sub.subject_name
    """
    subjects = fetchall(subject_q, (student_id,))

    # 3. Today’s attendance (period-wise)
    today_q = """
    SELECT t.period_no, sub.subject_name, pa.status
    FROM period_attendance pa
    JOIN timetable t ON pa.timetable_id = t.timetable_id
    JOIN subjects sub ON t.subject_id = sub.subject_id
    WHERE pa.student_id = %s
    AND pa.date = CURDATE()
    ORDER BY t.period_no
    """
    today = fetchall(today_q, (student_id,))

    return render_template(
        "student_dashboard.html",
        percentage=percentage,
        subjects=subjects,
        today=today
    )

@app.route('/login/student', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        student = fetchone("SELECT * FROM student_accounts WHERE username=%s", (username,))
        if student and check_password_hash(student['password_hash'], password):
            session['role'] = 'student'
            session['student_id'] = student['student_id']
            flash("Student login successful", "success")
            return redirect(url_for('student_dashboard'))

        flash("Invalid student username/password", "danger")
        return redirect(url_for('student_login'))

    return render_template("student_login.html")

@app.route('/admin/forgot-password', methods=['GET', 'POST'])
def admin_forgot_password():
    if request.method == 'POST':
        reset_key = request.form.get('reset_key')
        new_password = request.form.get('new_password')

        if reset_key != os.getenv("ADMIN_RESET_KEY"):
            flash("Invalid reset key!", "danger")
            return redirect(url_for("admin_forgot_password"))

        if not new_password or len(new_password) < 4:
            flash("Password must be at least 4 characters.", "danger")
            return redirect(url_for("admin_forgot_password"))

        password_hash = generate_password_hash(new_password)

        execute("UPDATE admins SET password_hash=%s WHERE admin_id=%s", (password_hash, 1))

        flash("Admin password updated successfully!", "success")
        return redirect(url_for("admin_login"))

    return render_template("admin_forgot_password.html")

@app.route('/admin/create-student-login/<int:student_id>', methods=['GET', 'POST'])
def create_student_login(student_id):
    if session.get('role') != 'admin':
        flash("Admin access required", "danger")
        return redirect(url_for('admin_login'))

    student = fetchone("SELECT * FROM students WHERE student_id=%s", (student_id,))
    if not student:
        flash("Student not found", "danger")
        return redirect(url_for('students'))

    existing = fetchone("SELECT * FROM student_accounts WHERE student_id=%s", (student_id,))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # If password is empty, only update username
        if password and password.strip() != "":
            password_hash = generate_password_hash(password)
            execute("""
                INSERT INTO student_accounts (student_id, username, password_hash)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE username=%s, password_hash=%s
            """, (student_id, username, password_hash, username, password_hash))
        else:
            execute("""
                INSERT INTO student_accounts (student_id, username, password_hash)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE username=%s
            """, (student_id, username, generate_password_hash("temp123"), username))

        flash("Student login updated successfully", "success")
        return redirect(url_for('students'))

    return render_template("create_student_login.html", student=student, existing=existing)

@app.route('/admin/chat', methods=['GET', 'POST'])
def admin_chat():
    if session.get('role') != 'admin':
        flash("Admin access required", "danger")
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        msg = request.form.get('message')

        if not msg or msg.strip() == "":
            flash("Message cannot be empty", "danger")
            return redirect(url_for('admin_chat'))

        execute(
            "INSERT INTO announcements (admin_id, message) VALUES (%s, %s)",
            (session.get('admin_id'), msg.strip())
        )
        flash("Message sent to students", "success")
        return redirect(url_for('admin_chat'))

    msgs = fetchall("""
        SELECT a.msg_id, a.message, a.created_at, ad.username
        FROM announcements a
        JOIN admins ad ON ad.admin_id = a.admin_id
        ORDER BY a.created_at DESC
        LIMIT 50
    """)
    return render_template("admin_chat.html", msgs=msgs)

@app.route('/student/chat')
def student_chat():
    if session.get('role') != 'student':
        flash("Student login required", "danger")
        return redirect(url_for('student_login'))

    msgs = fetchall("""
        SELECT a.message, a.created_at, ad.username
        FROM announcements a
        JOIN admins ad ON ad.admin_id = a.admin_id
        ORDER BY a.created_at DESC
        LIMIT 50
    """)
    return render_template("student_chat.html", msgs=msgs)

@app.route('/admin/panel')
def admin_panel():
    if session.get('role') != 'admin':
        flash("Admin access required", "danger")
        return redirect(url_for('admin_login'))

    return render_template("admin_panel.html")

@app.route('/login/admin', methods=['GET', 'POST'])
def admin_login():  #
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        admin = fetchone("SELECT * FROM admins WHERE username=%s", (username,))
        if admin and admin['password_hash'] != 'TEMP' and check_password_hash(admin['password_hash'], password):
            session['role'] = 'admin'
            session['admin_id'] = admin['admin_id']
            flash("Admin login successful", "success")
            return redirect(url_for('admin_panel'))

        flash("Invalid admin username/password", "danger")
        return redirect(url_for('admin_login'))

    return render_template("admin_login.html")

@app.route('/dashboard')
def dashboard():
    if session.get('role') != 'admin':
        flash("Admin access required", "danger")
        return redirect(url_for('admin_login'))
    today = date.today()
    q = """
    SELECT s.student_id, s.name, s.roll_no,
           COALESCE(a.status, 'Absent') AS status,
           COALESCE(a.source, 'AUTO') AS source
    FROM students s
    LEFT JOIN attendance a
      ON a.student_id = s.student_id AND a.attendance_date = %s
    ORDER BY s.roll_no;
    """
    rows = fetchall(q, (today,))
    return render_template('dashboard.html', rows=rows, today=today)

# Add / list students
@app.route('/students', methods=['GET', 'POST'])
def students():
    if session.get('role') != 'admin':
        flash("Admin access required", "danger")
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        name = request.form.get('name')
        roll_no = request.form.get('roll_no')
        parent_email = request.form.get('parent_email')
        device_mac = request.form.get('device_mac') or None

        q = """INSERT INTO students (name, roll_no, parent_email, device_mac)
               VALUES (%s,%s,%s,%s)"""
        try:
            execute(q, (name, roll_no, parent_email, device_mac))
            flash('Student added', 'success')
        except Exception as e:
            flash(f'Error adding student: {e}', 'danger')

        return redirect(url_for('students'))

    rows = fetchall("SELECT * FROM students ORDER BY roll_no;")
    return render_template('students.html', rows=rows)
    
    

@app.route('/delete-student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    if session.get('role') != 'admin':
        flash("Admin access required", "danger")
        return redirect(url_for('admin_login'))

    try:
        execute("DELETE FROM students WHERE student_id=%s", (student_id,))
        flash("Student deleted", "success")
    except Exception as e:
        flash(f"Error deleting student: {e}", "danger")

    return redirect(url_for('students'))

@app.route('/admin/change-credentials', methods=['GET', 'POST'])
def admin_change_credentials():
    if session.get('role') != 'admin':
        flash("Admin access required", "danger")
        return redirect(url_for('admin_login'))

    admin_id = session.get('admin_id')
    admin = fetchone("SELECT * FROM admins WHERE admin_id=%s", (admin_id,))

    if request.method == 'POST':
        new_username = request.form.get('username')
        new_password = request.form.get('password')

        # if password empty → only update username
        if new_password and new_password.strip() != "":
            password_hash = generate_password_hash(new_password)
            execute(
                "UPDATE admins SET username=%s, password_hash=%s WHERE admin_id=%s",
                (new_username, password_hash, admin_id)
            )
        else:
            execute(
                "UPDATE admins SET username=%s WHERE admin_id=%s",
                (new_username, admin_id)
            )

        flash("Admin credentials updated successfully", "success")
        return redirect(url_for('admin_panel'))

    return render_template("admin_change_credentials.html", admin=admin)

# Manual attendance UI + save
@app.route('/manual-attendance', methods=['GET', 'POST'])
def manual_attendance():
    if session.get('role') != 'admin':
        flash("Admin access required", "danger")
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        selected = request.form.getlist('present_ids')
        selected_ids = set(int(s) for s in selected)
        att_date = request.form.get('date') or str(date.today())
        students_list = fetchall("SELECT student_id FROM students;")
        for s in students_list:
            sid = s['student_id']
            status = 'Present' if sid in selected_ids else 'Absent'
            q = """
            INSERT INTO attendance (student_id, attendance_date, status, source)
            VALUES (%s, %s, %s, 'MANUAL')
            ON DUPLICATE KEY UPDATE status=%s, source='MANUAL'
            """
            execute(q, (sid, att_date, status, status))
        flash('Manual attendance saved', 'success')
        return redirect(url_for('dashboard'))
    else:
        students_list = fetchall("SELECT student_id, roll_no, name FROM students ORDER BY roll_no;")
        today = date.today()
        return render_template('manual_attendance.html', students=students_list, today=today)

# API: mark attendance (used by Wi-Fi scripts)
@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    data = request.get_json() or {}
    sid = data.get('student_id')
    source = data.get('source', 'WIFI')
    if not sid:
        return jsonify({"status":"error","message":"student_id required"}), 400
    att_date = date.today()
    try:
        q = """
        INSERT INTO attendance (student_id, attendance_date, status, source)
        VALUES (%s, %s, 'Present', %s)
        ON DUPLICATE KEY UPDATE status='Present', source=%s
        """
        execute(q, (sid, att_date, source, source))
        return jsonify({"status":"ok","message":"marked present"}), 200
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}), 500

# API: gps ping (from student mobile or simulator)
@app.route('/gps_ping', methods=['POST'])
def gps_ping():
    # 1. Read the JSON sent from phone / Postman
    data = request.get_json() or {}

    sid = data.get('student_id')       # student_id
    lat = data.get('latitude')         # latitude
    lon = data.get('longitude')        # longitude

    # 2. Check if all values are sent
    if not all([sid, lat, lon]):
        return jsonify({
            "status": "error",
            "message": "student_id, latitude, longitude required"
        }), 400

    # 3. Convert lat/lon to float numbers
    lat = float(lat)
    lon = float(lon)

    # 4. Calculate distance between student & campus
    student_point = (lat, lon)
    distance_m = geodesic(student_point, CAMPUS_CENTER).meters

    # 5. Check if inside campus
    inside = distance_m <= CAMPUS_RADIUS_M

    # 6. Save GPS ping in DB (history)
    log_q = """
    INSERT INTO geofence_pings (student_id, latitude, longitude, pinged_at, inside_campus)
    VALUES (%s, %s, %s, %s, %s)
    """
    execute(log_q, (sid, lat, lon, datetime.utcnow(), 1 if inside else 0))

    # 7. If inside campus → mark attendance
    if inside:
        att_q = """
        INSERT INTO attendance (student_id, attendance_date, status, source)
        VALUES (%s, %s, 'Present', 'GEOFENCE')
        ON DUPLICATE KEY UPDATE status='Present', source='GEOFENCE'
        """
        execute(att_q, (sid, date.today()))

    # 8. Send result back to phone
    return jsonify({
        "status": "ok",
        "inside": inside,
        "distance_m": round(distance_m, 2)
    })

@app.route('/edit-student/<int:student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    if not admin_required():
          return redirect(url_for('admin_login'))
    if request.method == 'POST':
        name = request.form.get('name')
        roll_no = request.form.get('roll_no')
        parent_email = request.form.get('parent_email')
        device_mac = request.form.get('device_mac') or None

        q = """
        UPDATE students
        SET name=%s, roll_no=%s, parent_email=%s, device_mac=%s
        WHERE student_id=%s
        """
        execute(q, (name, roll_no, parent_email, device_mac, student_id))
        flash("Student updated successfully", "success")
        return redirect(url_for('students'))

    student = fetchone("SELECT * FROM students WHERE student_id=%s", (student_id,))
    if not student:
        flash("Student not found", "danger")
        return redirect(url_for('students'))

    return render_template("edit_student.html", student=student)
if __name__ == '__main__':
    app.run(debug=True)