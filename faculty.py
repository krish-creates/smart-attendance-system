from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from models import db, User, Course, AttendanceLog
import base64
import numpy as np
import cv2
import face_recognition
from datetime import datetime

faculty_bp = Blueprint('faculty', __name__, url_prefix='/faculty')

@faculty_bp.route('/dashboard')
def dashboard():
    # Ensure only logged-in faculty can view this
    if 'user_id' not in session or session.get('role') != 'faculty':
        return redirect(url_for('auth.login'))
        
    # Get courses assigned specifically to this professor
    courses = Course.query.filter_by(faculty_id=session['user_id']).all()
    today = datetime.now().strftime('%A, %b %d')
    
    return render_template('faculty/dashboard.html', courses=courses, today=today)

@faculty_bp.route('/scanner/<int:course_id>')
def scanner(course_id):
    # Ensure they are logged in
    if 'user_id' not in session or session.get('role') != 'faculty':
        return redirect(url_for('auth.login'))
        
    course = Course.query.get_or_404(course_id)
    
    # Security check: ensure this professor actually teaches this course!
    if course.faculty_id != session['user_id']:
        flash("Unauthorized: You are not assigned to this course.", "error")
        return redirect(url_for('faculty.dashboard'))
        
    return render_template('faculty/recognize.html', course=course)

@faculty_bp.route('/process_frame', methods=['POST'])
def process_frame():
    """This route receives the silent webcam pictures and runs the AI!"""
    if 'user_id' not in session or session.get('role') != 'faculty':
        return jsonify({'status': 'error', 'message': 'Unauthorized'})
        
    data = request.get_json()
    course_id = data.get('course_id')
    image_data = data.get('image')
    
    if not image_data or not course_id:
        return jsonify({'status': 'error', 'message': 'Missing data'})
        
    try:
        # 1. Clean the Base64 String
        if ',' in image_data:
            image_data = image_data.split(',')[1]

        # 2. Convert Base64 back into an OpenCV Image array
        img_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # 3. Find any faces in the picture
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_img)
        
        if not face_locations:
            return jsonify({'status': 'success', 'recognized': []})
            
        live_encodings = face_recognition.face_encodings(rgb_img, face_locations)
        
        # 4. Fetch all students who are supposed to be in this specific class
        course = Course.query.get(course_id)
        students = User.query.filter_by(role='student', class_name=course.target_section).all()
        
        recognized_students = []
        today = datetime.now().date()
        
        # 5. Compare the live faces against the database!
        for live_encoding in live_encodings:
            for student in students:
                if student.face_encoding:
                    # Convert binary from DB back to an array
                    known_encoding = np.frombuffer(student.face_encoding, dtype=np.float64)
                    
                    # AI MATCH CHECK (Tolerance 0.5 is strict and accurate)
                    matches = face_recognition.compare_faces([known_encoding], live_encoding, tolerance=0.5)
                    
                    if matches[0]:
                        # Check if they were already marked present today
                        existing_log = AttendanceLog.query.filter_by(
                            student_id=student.id, course_id=course.id, date=today
                        ).first()
                        
                        if not existing_log:
                            # Mark them Present!
                            new_log = AttendanceLog(
                                student_id=student.id, course_id=course.id,
                                status='Present', date=today,
                                time_marked=datetime.now().time()
                            )
                            db.session.add(new_log)
                            recognized_students.append(f"Marked: {student.name}")
                        else:
                            recognized_students.append(f"Exists: {student.name}")
                        break 
                        
        db.session.commit()
        return jsonify({'status': 'success', 'recognized': recognized_students})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    