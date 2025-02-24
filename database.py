import sqlite3
import pickle
import psycopg2
import os

def init_db():
    conn = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST"),
        port=os.environ.get("POSTGRES_PORT"),
        user=os.environ.get("POSTGRES_USER"),
        password=os.environ.get("POSTGRES_PASSWORD"),
        dbname=os.environ.get("POSTGRES_DB")
    )
    # conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS professors 
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, email TEXT UNIQUE, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS students 
                 (id INTEGER PRIMARY KEY, roll_no TEXT UNIQUE, name TEXT, password TEXT, face_embedding BLOB)''')
    c.execute('''CREATE TABLE IF NOT EXISTS courses 
                 (id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT, professor_id INTEGER,
                  FOREIGN KEY(professor_id) REFERENCES professors(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS student_courses 
                 (student_id INTEGER, course_id INTEGER, 
                  FOREIGN KEY(student_id) REFERENCES students(id), 
                  FOREIGN KEY(course_id) REFERENCES courses(id), 
                  PRIMARY KEY(student_id, course_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS attendance 
                 (id INTEGER PRIMARY KEY, student_id INTEGER, course_id INTEGER, timestamp TEXT,
                  FOREIGN KEY(student_id) REFERENCES students(id),
                  FOREIGN KEY(course_id) REFERENCES courses(id))''')
    conn.commit()
    conn.close()

def add_professor(username, email, hashed_password):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO professors (username, email, password) VALUES (?, ?, ?)", 
              (username, email, hashed_password))
    conn.commit()
    conn.close()

def get_professor_by_username(username):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT * FROM professors WHERE username = ?", (username,))
    professor = c.fetchone()
    conn.close()
    return professor

def get_professor_by_id(professor_id):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT * FROM professors WHERE id = ?", (professor_id,))
    professor = c.fetchone()
    conn.close()
    return professor

def add_student(roll_no, name, hashed_password, face_embedding=None):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    embedding_blob = pickle.dumps(face_embedding) if face_embedding is not None else None
    c.execute("INSERT OR IGNORE INTO students (roll_no, name, password, face_embedding) VALUES (?, ?, ?, ?)", 
              (roll_no, name, hashed_password, embedding_blob))
    conn.commit()
    conn.close()

def update_student_face(student_id, face_embedding):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    embedding_blob = pickle.dumps(face_embedding)
    c.execute("UPDATE students SET face_embedding = ? WHERE id = ?", (embedding_blob, student_id))
    conn.commit()
    conn.close()

def get_student_by_roll_no(roll_no):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT * FROM students WHERE roll_no = ?", (roll_no,))
    student = c.fetchone()
    conn.close()
    return student

def add_course(code, name, professor_id):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO courses (code, name, professor_id) VALUES (?, ?, ?)", 
              (code, name, professor_id))
    conn.commit()
    conn.close()

def get_courses_by_professor(professor_id):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT id, code, name FROM courses WHERE professor_id = ?", (professor_id,))
    courses = c.fetchall()
    conn.close()
    return courses

def get_all_courses():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT id, code, name FROM courses")
    courses = c.fetchall()
    conn.close()
    return courses

def enroll_student(student_id, course_id):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO student_courses (student_id, course_id) VALUES (?, ?)", 
              (student_id, course_id))
    conn.commit()
    conn.close()

def unenroll_student(student_id, course_id):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("DELETE FROM student_courses WHERE student_id = ? AND course_id = ?", 
              (student_id, course_id))
    conn.commit()
    conn.close()

def get_student_courses(student_id):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("""
        SELECT c.id, c.code, c.name 
        FROM student_courses sc 
        JOIN courses c ON sc.course_id = c.id 
        WHERE sc.student_id = ?
    """, (student_id,))
    courses = c.fetchall()
    conn.close()
    return courses

def get_students_by_course(course_id):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("""
        SELECT s.id, s.roll_no, s.name, s.face_embedding
        FROM student_courses sc 
        JOIN students s ON sc.student_id = s.id 
        WHERE sc.course_id = ?
    """, (course_id,))
    students = c.fetchall()
    conn.close()
    return [(s[0], s[1], s[2], pickle.loads(s[3]) if s[3] else None) for s in students]

def mark_attendance(student_id, course_id, timestamp):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("INSERT INTO attendance (student_id, course_id, timestamp) VALUES (?, ?, ?)", 
              (student_id, course_id, timestamp))
    conn.commit()
    conn.close()

def get_attendance_by_course(course_id, timestamp):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT DISTINCT student_id FROM attendance WHERE course_id = ? AND timestamp LIKE ?", 
              (course_id, f"{timestamp.split()[0]}%"))
    attended = [row[0] for row in c.fetchall()]
    conn.close()
    return attended

def get_attendance_for_csv(course_id, date):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("""
        SELECT s.name, s.roll_no, c.code, a.timestamp 
        FROM attendance a 
        JOIN students s ON a.student_id = s.id 
        JOIN courses c ON a.course_id = c.id 
        WHERE a.course_id = ? AND a.timestamp LIKE ?
    """, (course_id, f"{date}%"))
    records = c.fetchall()
    conn.close()
    return records

def delete_course(course_id):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    # Delete the course from the courses table
    c.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    # Delete related student enrollments
    c.execute("DELETE FROM student_courses WHERE course_id = ?", (course_id,))
    # Delete related attendance records
    c.execute("DELETE FROM attendance WHERE course_id = ?", (course_id,))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()