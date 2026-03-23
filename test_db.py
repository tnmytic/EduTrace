import mysql.connector as mc

try:
    conn = mc.connect(
        host="localhost",
        user="root",
        password="EduTrace9090",
        database="edutrace_db"
    )

    if conn.is_connected():
        print("Connected to MySQL successfully!")

        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()

        print("\nTables inside 'edutrace_db':")
        for t in tables:
            print(" -", t[0])

        cursor.close()
        conn.close()
    else:
        print("Connection failed.")

except mc.Error as e:
    print("MySQL Error:", e)