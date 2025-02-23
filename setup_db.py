import sqlite3
import bcrypt

def init_db():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS professors 
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)''')
    conn.commit()
    conn.close()

def add_professor(username, password):
    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO professors (username, password) VALUES (?, ?)", 
              (username, hashed_pw.decode('utf-8')))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    add_professor("testprofessor", "testpassword")