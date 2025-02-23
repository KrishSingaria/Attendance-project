from flask import Flask, request, render_template, jsonify, session, send_file, redirect, url_for
import bcrypt
import sqlite3
import torch
import os
import numpy as np
import base64
import cv2
import csv
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from insightface.app import FaceAnalysis
import logging
from database import (init_db, add_professor, get_professor_by_username, get_professor_by_id, add_student, 
                     update_student_face, get_student_by_roll_no, add_course, get_courses_by_professor, 
                     get_all_courses, enroll_student, unenroll_student, get_student_courses, 
                     get_students_by_course, mark_attendance, get_attendance_by_course, get_attendance_for_csv,
                     delete_course)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key")

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize InsightFace with ArcFace model
face_app = FaceAnalysis(name='buffalo_l', det_size=(1280, 720))  # Match downscaled resolution
face_app.prepare(ctx_id=0 if torch.cuda.is_available() else -1)  # ctx_id=0 for GPU, -1 for CPU on Windows

init_db()

@app.route('/')
def landing():
    return render_template('landing.html')

# Student Routes
@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        roll_no = request.form.get('roll_no')
        name = request.form.get('name')
        password = request.form.get('password')
        if not all([roll_no, name, password]):
            return jsonify({"success": False, "message": "Missing fields"})
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        add_student(roll_no, name, hashed_pw.decode('utf-8'))
        return jsonify({"success": True, "message": "Student registered successfully"})
    return render_template('student_register.html')

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        roll_no = request.form.get('roll_no')
        password = request.form.get('password')
        if not roll_no or not password:
            return jsonify({"success": False, "message": "Missing fields"})
        student = get_student_by_roll_no(roll_no)
        if student and bcrypt.checkpw(password.encode('utf-8'), student[3].encode('utf-8')):
            session['student_id'] = student[0]
            return jsonify({"success": True, "message": "Login successful"})
        return jsonify({"success": False, "message": "Invalid credentials"})
    return render_template('student_login.html')

@app.route('/student/home')
def student_home():
    if 'student_id' not in session:
        return redirect(url_for('student_login'))
    courses = get_student_courses(session['student_id'])
    all_courses = get_all_courses()
    return render_template('student_home.html', courses=courses, all_courses=all_courses)

@app.route('/student/enroll', methods=['POST'])
def student_enroll():
    if 'student_id' not in session:
        return redirect(url_for('student_login'))
    course_id = request.form.get('course_id')
    enroll_student(session['student_id'], course_id)
    return redirect(url_for('student_home'))

@app.route('/student/unenroll', methods=['POST'])
def student_unenroll():
    if 'student_id' not in session:
        return redirect(url_for('student_login'))
    course_id = request.form.get('course_id')
    unenroll_student(session['student_id'], course_id)
    return redirect(url_for('student_home'))

@app.route('/student/face_data', methods=['GET', 'POST'])
def student_face_data():
    if 'student_id' not in session:
        return redirect(url_for('student_login'))
    if request.method == 'POST':
        frame_data = request.form.get('frame')
        if not frame_data:
            return jsonify({"success": False, "message": "No frame data"})
        
        try:
            # Decode base64 frame (downscaled resolution)
            frame_bytes = base64.b64decode(frame_data.split(',')[1])
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)  # InsightFace expects BGR
            
            # Use full frame (downscaled) for embedding
            faces = face_app.get(frame_rgb, max_num=1)  # Limit to 1 face
            if not faces or len(faces) == 0:
                return jsonify({"success": False, "message": "No face detected"})
            
            embedding = faces[0].embedding  # 512D vector
            logger.debug(f"Stored embedding shape: {embedding.shape}, sample: {embedding[:5]}")
            update_student_face(session['student_id'], embedding)
            return jsonify({"success": True, "message": "Face data updated successfully"})
        
        except Exception as e:
            logger.error(f"Error updating face data: {str(e)}", exc_info=True)
            return jsonify({"success": False, "message": f"Server error: {str(e)}"})
    
    return render_template('student_face_data.html')

@app.route('/detect_face', methods=['POST'])
def detect_face():
    try:
        frame_data = request.form.get('frame')
        if not frame_data:
            return jsonify({"success": False, "message": "No frame data"})
        
        frame_bytes = base64.b64decode(frame_data.split(',')[1])
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        faces = face_app.get(frame_rgb, max_num=1)
        if faces and len(faces) > 0:
            box = faces[0].bbox
            return jsonify({
                "success": True,
                "box": {"left": int(box[0]), "top": int(box[1]), "right": int(box[2]), "bottom": int(box[3])}
            })
        return jsonify({"success": False, "message": "No face detected"})
    except Exception as e:
        logger.error(f"Error in detect_face: {str(e)}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"})

# Professor Routes
@app.route('/professor/register', methods=['GET', 'POST'])
def professor_register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        if not username or not email or not password:
            return jsonify({"success": False, "message": "Missing fields"})
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        add_professor(username, email, hashed_pw.decode('utf-8'))
        return jsonify({"success": True, "message": "Professor registered successfully"})
    return render_template('professor_register.html')

@app.route('/professor/login', methods=['GET', 'POST'])
def professor_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            return jsonify({"success": False, "message": "Missing fields"})
        professor = get_professor_by_username(username)
        if professor and bcrypt.checkpw(password.encode('utf-8'), professor[3].encode('utf-8')):
            session['professor_id'] = professor[0]
            return jsonify({"success": True, "message": "Login successful"})
        return jsonify({"success": False, "message": "Invalid credentials"})
    return render_template('professor_login.html')

@app.route('/professor/home')
def professor_home():
    if 'professor_id' not in session:
        return redirect(url_for('professor_login'))
    courses = get_courses_by_professor(session['professor_id'])
    return render_template('professor_home.html', courses=courses)

@app.route('/professor/add_course', methods=['POST'])
def professor_add_course():
    if 'professor_id' not in session:
        return redirect(url_for('professor_login'))
    code = request.form.get('code')
    name = request.form.get('name')
    add_course(code, name, session['professor_id'])
    return redirect(url_for('professor_home'))

@app.route('/professor/students', methods=['GET'])
def professor_students():
    if 'professor_id' not in session:
        return redirect(url_for('professor_login'))
    course_id = request.args.get('course_id')
    students = get_students_by_course(course_id)
    csv_filename = f"students_{course_id}.csv"
    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Roll No', 'Name'])
        for student in students:
            writer.writerow([student[1], student[2]])
    return send_file(csv_filename, as_attachment=True, download_name=csv_filename)

@app.route('/professor/take_attendance', methods=['GET', 'POST'])
def professor_take_attendance():
    if 'professor_id' not in session:
        return redirect(url_for('professor_login'))
    if request.method == 'POST':
        try:
            course_id = request.form.get('course_id')
            frame_data = request.form.get('frame')
            if not course_id or not frame_data:
                logger.warning("Missing course_id or frame data")
                return jsonify({"success": False, "message": "Missing course or frame"})

            # Decode base64 frame (downscaled resolution)
            frame_bytes = base64.b64decode(frame_data.split(',')[1])
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                logger.error("Failed to decode frame")
                return jsonify({"success": False, "message": "Invalid frame data"})
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Detect faces with InsightFace
            faces = face_app.get(frame_rgb)
            logger.debug(f"Detected {len(faces)} faces")
            if not faces or len(faces) == 0:
                return jsonify({"success": True, "faces": []})

            # Load known students
            students = get_students_by_course(course_id)
            known_embeddings = [student[3] for student in students if student[3] is not None]
            known_ids = [student[0] for student in students]
            known_names = [student[2] for student in students]
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            attended_ids = get_attendance_by_course(course_id, timestamp)
            
            results = []
            for i, face in enumerate(faces):
                embedding = face.embedding  # 512D ArcFace embedding
                distances = [np.linalg.norm(embedding - known_emb) for known_emb in known_embeddings]
                logger.debug(f"Face {i} distances: {distances}")
                name = "Unknown"
                student_id = None
                if distances:
                    min_dist = min(distances)
                    min_idx = distances.index(min_dist)
                    logger.debug(f"Min distance: {min_dist}, Threshold: 1.0")
                    if min_dist:  # Adjusted threshold
                        name = known_names[min_idx]
                        student_id = known_ids[min_idx]
                        if student_id not in attended_ids:
                            mark_attendance(student_id, course_id, timestamp)
                            attended_ids.append(student_id)
                
                box = face.bbox
                results.append({
                    "name": name,
                    "left": int(box[0]),
                    "top": int(box[1]),
                    "right": int(box[2]),
                    "bottom": int(box[3])
                })
                logger.debug(f"Face {i}: {name} at ({box[0]}, {box[1]}, {box[2]}, {box[3]})")
            
            return jsonify({"success": True, "faces": results})
        
        except Exception as e:
            logger.error(f"Error in take_attendance: {str(e)}", exc_info=True)
            return jsonify({"success": False, "message": f"Server error: {str(e)}"})
    
    courses = get_courses_by_professor(session['professor_id'])
    return render_template('professor_take_attendance.html', courses=courses)

@app.route('/professor/generate_csv', methods=['GET'])
def professor_generate_csv():
    if 'professor_id' not in session:
        return redirect(url_for('professor_login'))
    course_id = request.args.get('course_id')
    date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
    records = get_attendance_for_csv(course_id, date)
    if not records:
        return "No attendance records found.", 404
    
    csv_filename = f"attendance_{course_id}_{date}.csv"
    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Name', 'Roll No', 'Course Code', 'Timestamp'])
        for record in records:
            writer.writerow(record)
    return send_file(csv_filename, as_attachment=True, download_name=csv_filename)

@app.route('/professor/email_attendance', methods=['POST'])
def professor_email_attendance():
    if 'professor_id' not in session:
        return redirect(url_for('professor_login'))
    course_id = request.form.get('course_id')
    date = request.form.get('date', datetime.now().strftime("%Y-%m-%d"))
    records = get_attendance_for_csv(course_id, date)
    if not records:
        return "No attendance records found.", 404
    
    csv_filename = f"attendance_{course_id}_{date}.csv"
    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Name', 'Roll No', 'Course Code', 'Timestamp'])
        for record in records:
            writer.writerow(record)
    
    professor = get_professor_by_id(session['professor_id'])
    email = professor[2]
    
    msg = MIMEMultipart()
    msg['From'] = "your-email@gmail.com"
    msg['To'] = email
    msg['Subject'] = f"Attendance for Course {course_id} on {date}"
    msg.attach(MIMEText("Attached is the attendance record.", 'plain'))
    
    with open(csv_filename, 'rb') as f:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={csv_filename}')
        msg.attach(part)
    
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login("your-email@gmail.com", "your-app-password")
        server.send_message(msg)
    
    return redirect(url_for('professor_home'))

@app.route('/professor/delete_course', methods=['POST'])
def professor_delete_course():
    # Check if the user is a logged-in professor
    if 'professor_id' not in session:
        return redirect(url_for('professor_login'))
    
    # Get the course ID from the form data
    course_id = request.form.get('course_id')
    if not course_id:
        return jsonify({"success": False, "message": "Missing course ID"})
    
    # Delete the course and related data
    delete_course(course_id)
    
    # Redirect back to the professor's dashboard
    return redirect(url_for('professor_home'))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)