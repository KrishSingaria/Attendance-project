import sqlite3
import pickle
import bcrypt
import os

# Database schema and initialization functions from your database.py
def init_db():
    conn = sqlite3.connect('attendance.db')
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

def add_student(roll_no, name, hashed_password, face_embedding=None):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    embedding_blob = pickle.dumps(face_embedding) if face_embedding is not None else None
    c.execute("INSERT OR IGNORE INTO students (roll_no, name, password, face_embedding) VALUES (?, ?, ?, ?)", 
              (roll_no, name, hashed_password, embedding_blob))
    conn.commit()
    conn.close()

# Main initialization function
def initialize_db():
    # Delete existing database (optional, comment out if you want to keep existing data)
    if os.path.exists('attendance.db'):
        os.remove('attendance.db')
        print("Existing attendance.db deleted.")

    # Initialize database schema
    init_db()
    print("Database schema initialized.")

    # Add predefined professor
    prof_username = "manoj"
    prof_email = "krishsingaria2005@gmail.com"
    prof_password = "123456789"
    hashed_prof_pw = bcrypt.hashpw(prof_password.encode('utf-8'), bcrypt.gensalt())
    add_professor(prof_username, prof_email, hashed_prof_pw.decode('utf-8'))
    print(f"Professor '{prof_username}' added with email '{prof_email}'.")

    # Add predefined student
    student_roll_no = "B23143"
    student_name = "krish"
    student_password = "123456789"
    hashed_student_pw = bcrypt.hashpw(student_password.encode('utf-8'), bcrypt.gensalt())
    add_student(student_roll_no, student_name, hashed_student_pw.decode('utf-8'))
    print(f"Student '{student_name}' added with roll_no '{student_roll_no}'.")

if __name__ == "__main__":
    initialize_db()
    print("Database initialization complete. You can now run app.py.")