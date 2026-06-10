from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from models import db, User, Course, AttendanceLog
import base64
import numpy as np
import cv2
import face_recognition

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/dashboard')
def dashboard():
    # Ensure only logged-in students can view this page
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('auth.login'))

    # 1. Fetch the logged-in student
    student = User.query.get(session['user_id'])
    
    # 2. Get all courses mapped to this student's specific section
    assigned_courses = Course.query.filter_by(target_section=student.class_name).all()
    
    courses_data = []
    total_attended_overall = 0
    total_classes_overall = 0 # We will now count CONDUCTED classes here, not semester totals
    safe_count = warning_count = critical_count = 0

    # 3. Calculate dynamic stats for every single course
    for c in assigned_courses:
        # Fetch ALL logs (Presents + Absents) to know how many classes actually happened
        all_logs = AttendanceLog.query.filter_by(course_id=c.id, student_id=student.id).all()
        
        conducted = len(all_logs)
        attended = sum(1 for log in all_logs if log.status == 'Present')
        semester_total = c.total_classes

        # Real-world percentage math!
        if conducted == 0:
            percentage = 100 # Clean slate if classes haven't started
        else:
            percentage = int((attended / conducted) * 100)

        total_attended_overall += attended
        total_classes_overall += conducted

        # Categorize their status
        if percentage >= 75:
            status = 'safe'
            safe_count += 1
        elif percentage >= 70:
            status = 'warning'
            warning_count += 1
        else:
            status = 'critical'
            critical_count += 1
            
        faculty = User.query.get(c.faculty_id)

        courses_data.append({
            'db_id': c.id, 
            'id': c.code,
            'name': c.name,
            'attended': attended,
            'conducted': conducted,
            'total': semester_total,
            'percentage': percentage,
            'status': status,
            'instructor': faculty.name if faculty else 'Unknown Faculty'
        })

    # 4. Calculate Overall Mathematics based on CONDUCTED classes
    if total_classes_overall > 0:
        overall_attendance = int((total_attended_overall / total_classes_overall) * 100)
    else:
        overall_attendance = 100

    # 5. Fetch their most recent scanner activity (Limit to last 3)
    recent_logs = db.session.query(AttendanceLog, Course).join(Course, AttendanceLog.course_id == Course.id)\
        .filter(AttendanceLog.student_id == student.id)\
        .order_by(AttendanceLog.date.desc(), AttendanceLog.time_marked.desc())\
        .limit(3).all()

    return render_template('student/dashboard.html', 
                           student=student,
                           courses=courses_data,
                           overall_attendance=overall_attendance,
                           attendance_goal=75,
                           safe_count=safe_count,
                           warning_count=warning_count,
                           critical_count=critical_count,
                           recent_logs=recent_logs)

@student_bp.route('/course/<int:course_id>')
def course_detail(course_id):
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('auth.login'))

    student = User.query.get(session['user_id'])
    db_course = Course.query.get_or_404(course_id)

    if db_course.target_section != student.class_name:
        flash("Unauthorized: You are not enrolled in this course.", "error")
        return redirect(url_for('student.dashboard'))

    # 1. Get ALL logs for this specific course to find out how many classes actually happened
    raw_logs = AttendanceLog.query.filter_by(course_id=db_course.id, student_id=student.id)\
        .order_by(AttendanceLog.date.desc(), AttendanceLog.time_marked.desc()).all()
    
    # 2. Strict Real-World Math
    conducted = len(raw_logs)
    attended = sum(1 for log in raw_logs if log.status == 'Present')
    semester_total = db_course.total_classes
    
    # Prevent divide-by-zero if the semester just started
    percentage = int((attended / conducted) * 100) if conducted > 0 else 100
    
    # How many classes are left in the semester? (This is our simulator's ceiling!)
    remaining = semester_total - conducted if semester_total > conducted else 0

    course_data = {
        'name': db_course.name,
        'code': db_course.code,
        'percentage': percentage,
        'attended': attended,
        'conducted': conducted,
        'remaining': remaining,
        'semester_total': semester_total
    }

    formatted_history = []
    for log in raw_logs:
        formatted_history.append({
            'date': log.date.strftime('%b %d, %Y'),
            'time': log.time_marked.strftime('%I:%M %p'),
            'type': 'AI Vision Match',
            'status': log.status
        })

    return render_template('student/course_detail.html', course=course_data, history=formatted_history)

@student_bp.route('/capture/<int:student_id>')
def capture_face(student_id):
    # 1. Fetch the real student from the database
    student = User.query.get_or_404(student_id)
    
    # 2. Package the data exactly how our capture.html frontend expects it
    student_data = {
        'id': student.id,
        'name': student.name,
        'register_no': student.identifier,
        'class_name': student.class_name
    }
    
    return render_template('student/capture.html', student=student_data)

@student_bp.route('/save_face', methods=['POST'])
def save_face():
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        image_data = data.get('image')

        # 1. Clean the Base64 String
        if ',' in image_data:
            image_data = image_data.split(',')[1]

        # 2. Convert Base64 back into an OpenCV Image array
        img_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # 3. Hand it to the AI to look for faces
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_img)

        # 4. Strict Validation
        if len(face_locations) == 0:
            return jsonify({'status': 'no_face', 'message': 'No face detected.'})
        elif len(face_locations) > 1:
            return jsonify({'status': 'error', 'message': 'Multiple faces detected. Please stand alone.'})

        # 5. Extract the 128-point face encoding
        live_encoding = face_recognition.face_encodings(rgb_img, face_locations)[0]

        # 6. Fetch the student from the DB
        student = User.query.get(student_id)
        if not student:
            return jsonify({'status': 'error', 'message': 'Student not found in database.'})

        # 7. Convert the numpy array to binary bytes and save it!
        student.face_encoding = live_encoding.tobytes()
        db.session.commit()

        return jsonify({'status': 'success', 'message': 'Frame captured successfully!'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})