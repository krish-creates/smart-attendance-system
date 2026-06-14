from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from models import db, User, Course, AttendanceLog
import base64
import numpy as np
import cv2
import face_recognition
import math
from datetime import datetime



# A global set to track which students have successfully blinked during a session
# (In a real production app, this would go in a Redis cache or database)
verified_live_users = set()

def euclidean_dist(pt1, pt2):
    """Calculates the distance between two (x,y) coordinates."""
    return math.sqrt((pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2)

def calculate_ear(eye_points):
    """Calculates the Eye Aspect Ratio (EAR) given 6 eye coordinates."""
    # Vertical distances between the eyelids
    A = euclidean_dist(eye_points[1], eye_points[5])
    B = euclidean_dist(eye_points[2], eye_points[4])
    # Horizontal distance across the eye
    C = euclidean_dist(eye_points[0], eye_points[3])
    
    # Calculate EAR
    ear = (A + B) / (2.0 * C)
    return ear

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
    data = request.get_json()
    base64_image = data.get('image')
    course_id = data.get('course_id')

    is_new_session = data.get('is_new_session', False) 
    
    if is_new_session:
        verified_live_users.clear()

    if not base64_image:
        return jsonify({'status': 'error', 'message': 'No image provided'})

    # Decode the Base64 image from the browser
    header, encoded = base64_image.split(",", 1)
    image_data = base64.b64decode(encoded)
    np_arr = np.frombuffer(image_data, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Find faces, their encodings, AND their facial landmarks
    face_locations = face_recognition.face_locations(rgb_frame)
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
    face_landmarks_list = face_recognition.face_landmarks(rgb_frame, face_locations)

    course = Course.query.get(course_id)
    enrolled_students = User.query.filter_by(role='student', class_name=course.target_section).all()
    
    known_encodings = []
    known_names = []
    known_ids = []
    
    for student in enrolled_students:
        if student.face_encoding:
            known_encodings.append(np.frombuffer(student.face_encoding, dtype=np.float64))
            known_names.append(student.name)
            known_ids.append(student.id)

    recognized_list = []

    # Loop through every face found in the frame
    for face_encoding, face_landmarks in zip(face_encodings, face_landmarks_list):
        matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.5)
        
        if True in matches:
            first_match_index = matches.index(True)
            matched_student_id = known_ids[first_match_index]
            matched_student_name = known_names[first_match_index]

            # --- LIVENESS DETECTION (EAR) ---
            left_eye = face_landmarks['left_eye']
            right_eye = face_landmarks['right_eye']
            
            avg_ear = (calculate_ear(left_eye) + calculate_ear(right_eye)) / 2.0
            
            # 1. Did they blink? (EAR drops below 0.22)
            if avg_ear < 0.22:
                verified_live_users.add(matched_student_id)
                recognized_list.append(f"Waiting: {matched_student_name} (Blink Detected!)")
                continue # Skip marking attendance until their eyes open again
                
            # 2. Are their eyes open (EAR > 0.25) AND have they already blinked?
            if avg_ear > 0.25 and matched_student_id in verified_live_users:
                # Security passed! Check if they are already logged today
                existing_log = AttendanceLog.query.filter_by(
                    student_id=matched_student_id, 
                    course_id=course.id, 
                    date=datetime.now().date()
                ).first()

                if not existing_log:
                    new_log = AttendanceLog(
                        student_id=matched_student_id,
                        course_id=course.id,
                        status='Present'
                    )
                    db.session.add(new_log)
                    db.session.commit()
                    recognized_list.append(f"Marked: {matched_student_name}")
                else:
                    recognized_list.append(f"Already Logged: {matched_student_name}")
            else:
                recognized_list.append(f"Please Blink: {matched_student_name}")

    return jsonify({'status': 'success', 'recognized': recognized_list})

from datetime import datetime

@faculty_bp.route('/end_session/<int:course_id>')
def end_session(course_id):
    if 'user_id' not in session or session.get('role') != 'faculty':
        return redirect(url_for('auth.login'))

    course = Course.query.get_or_404(course_id)
    today = datetime.now().date()

    # 1. Fetch EVERY student enrolled in this specific section
    enrolled_students = User.query.filter_by(role='student', class_name=course.target_section).all()

    # 2. Find everyone who was already marked 'Present' today
    present_logs = AttendanceLog.query.filter_by(course_id=course_id, date=today, status='Present').all()
    
    # Extract just their IDs into a simple list for easy checking
    present_student_ids = [log.student_id for log in present_logs]

    # 3. Sweep through the roster and mark the absentees!
    absent_count = 0
    for student in enrolled_students:
        if student.id not in present_student_ids:
            
            # Double check an 'Absent' log doesn't already exist so we don't duplicate
            existing_absent = AttendanceLog.query.filter_by(
                student_id=student.id, course_id=course_id, date=today, status='Absent'
            ).first()
            
            if not existing_absent:
                new_log = AttendanceLog(
                    student_id=student.id,
                    course_id=course_id,
                    status='Absent'
                )
                db.session.add(new_log)
                absent_count += 1

    db.session.commit()
    flash(f'Session closed securely. {absent_count} unscanned students were marked Absent.', 'success')
    
    return redirect(url_for('faculty.dashboard'))