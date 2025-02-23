import sqlite3

def clear_students():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("DELETE FROM students")
    conn.commit()
    conn.close()
    print("All students cleared from the database.")

if __name__ == "__main__":
    clear_students()