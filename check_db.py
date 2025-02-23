import sqlite3
conn = sqlite3.connect('attendance.db')
c = conn.cursor()
c.execute("SELECT * FROM attendance")
print(c.fetchall())
conn.close()