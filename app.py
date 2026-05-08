"""
app.py
------
This is the main Flask application file.
It connects all routes (pages) together and handles
the webcam-based face recognition logic.

Routes:
  /                    → Home page
  /register            → Student registration form
  /capture/<id>        → Webcam capture + face encoding
  /session             → Create attendance session
  /recognize/<session> → Live face recognition + mark attendance
  /report              → View attendance report
"""

import os
import cv2
import numpy as np
import face_recognition
import base64
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash

# Import our database helper functions
import database as db

# -------------------------------------------------------
# Flask App Setup
# -------------------------------------------------------
app = Flask(__name__)
app.secret_key = 'smart_attendance_secret_key_2024'  # Needed for session storage

# Folder where we save captured face images
FACE_IMAGES_DIR = 'face_images'
os.makedirs(FACE_IMAGES_DIR, exist_ok=True)

# -------------------------------------------------------
# Initialize the database when app starts
# -------------------------------------------------------
db.init_db()


# ============================================================
# HOME PAGE
# ============================================================
@app.route('/')
def index():
    """Show the home/dashboard page."""
    students = db.get_all_students()
    sessions = db.get_all_sessions()
    return render_template('index.html', students=students, sessions=sessions)


# ============================================================
# PHASE 3 — STUDENT REGISTRATION
# ============================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    GET  → Show the student registration form.
    POST → Save student details and redirect to face capture.
    """
    if request.method == 'POST':
        # Read form data
        name        = request.form['name'].strip()
        register_no = request.form['register_no'].strip()
        email       = request.form['email'].strip()
        department  = request.form['department'].strip()
        class_name  = request.form['class_name'].strip()
        semester    = request.form['semester'].strip()

        # Save to database
        student_id = db.add_student(register_no, name, email, department, class_name, semester)

        if student_id is None:
            # Duplicate register number
            return render_template('register.html',
                                   error="Register number already exists! Use a unique number.")

        # Redirect to face capture page for this student
        return redirect(url_for('capture_face', student_id=student_id))

    return render_template('register.html')


# ============================================================
# PHASE 3 — FACE CAPTURE & ENCODING
# ============================================================

@app.route('/capture/<int:student_id>')
def capture_face(student_id):
    """Show the webcam capture page for a specific student."""
    student = db.get_student_by_id(student_id)
    if not student:
        return "Student not found!", 404
    return render_template('capture.html', student=student)


@app.route('/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    """Delete a student, their DB records, and their image folder."""
    # 1. Get student info (for folder path) before deleting
    student = db.get_student_by_id(student_id)
    if student:
        # 2. Delete from Database
        db.delete_student(student_id)

        # 3. Delete physical image folder
        import shutil
        folder_path = os.path.join(FACE_IMAGES_DIR, str(student_id))
        if os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path)
                print(f"[SYSTEM] Deleted folder: {folder_path}")
            except Exception as e:
                print(f"[ERROR] Could not delete folder: {e}")

        flash(f"Student {student['name']} deleted successfully.", "success")
    else:
        flash("Student not found.", "danger")

    return redirect(url_for('index'))


@app.route('/reset_sessions', methods=['POST'])
def reset_sessions():
    """Reset all attendance sessions."""
    db.reset_sessions()
    flash("Total sessions have been successfully reset.", "warning")
    return redirect(url_for('index'))


@app.route('/save_face', methods=['POST'])
def save_face():
    """
    Called via JavaScript (AJAX) from the capture page.
    Receives a base64-encoded image, decodes it,
    detects the face, generates encoding, saves to DB.
    Wrapped in try/except so it always returns JSON — never a 500 HTML page.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data received.'})

        student_id  = data.get('student_id')
        image_data  = data.get('image', '')       # base64 string
        image_index = data.get('image_index', 0)  # which capture (1-20)

        if not image_data or ',' not in image_data:
            return jsonify({'status': 'error', 'message': 'Invalid image data received.'})

        # ------- Decode base64 image to OpenCV format -------
        header, encoded = image_data.split(',', 1)
        img_bytes = base64.b64decode(encoded)
        np_arr    = np.frombuffer(img_bytes, np.uint8)
        frame     = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # Guard: imdecode returns None if image is invalid/blank
        if frame is None:
            return jsonify({'status': 'error', 'message': 'Could not decode image. Check camera.'})

        # ------- Convert BGR (OpenCV) to RGB (face_recognition uses RGB) -------
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # ------- Detect face locations -------
        face_locations = face_recognition.face_locations(rgb_frame)

        if len(face_locations) == 0:
            return jsonify({'status': 'no_face', 'message': 'No face detected. Adjust position & lighting.'})

        if len(face_locations) > 1:
            return jsonify({'status': 'multiple_faces', 'message': 'Multiple faces detected. Only one person please.'})

        # ------- Generate 128-dimensional face encoding -------
        encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        if len(encodings) == 0:
            return jsonify({'status': 'error', 'message': 'Could not generate encoding. Try again.'})

        encoding = encodings[0]  # We have one face, get its encoding

        # ------- Save the image to face_images folder -------
        student = db.get_student_by_id(student_id)
        if not student:
            return jsonify({'status': 'error', 'message': 'Student not found.'})

        folder  = os.path.join(FACE_IMAGES_DIR, str(student_id))
        os.makedirs(folder, exist_ok=True)
        filename   = f"{student['register_no']}_img{image_index}.jpg"
        image_path = os.path.join(folder, filename)
        cv2.imwrite(image_path, frame)

        # ------- Save encoding to database -------
        db.save_encoding(student_id, encoding, image_path)

        return jsonify({'status': 'success', 'message': f'Image {image_index} captured!'})

    except Exception as e:
        # Always return JSON — never let the server crash with an HTML 500 page
        print(f'[ERROR] /save_face: {e}')
        return jsonify({'status': 'error', 'message': f'Server error: {str(e)}'})  , 200


# ============================================================
# PHASE 4 — ATTENDANCE SESSION
# ============================================================

@app.route('/session', methods=['GET', 'POST'])
def create_session():
    """
    GET  → Show form to create a new session.
    POST → Save session and redirect to live recognition.
    """
    if request.method == 'POST':
        class_name   = request.form['class_name'].strip()
        subject_name = request.form['subject_name'].strip()
        session_date = datetime.now().strftime('%Y-%m-%d')
        start_time   = datetime.now().strftime('%H:%M:%S')

        session_id = db.create_session(class_name, subject_name, session_date, start_time)

        # Save session_id in Flask session so recognize page can use it
        session['active_session_id'] = session_id

        return redirect(url_for('recognize', session_id=session_id))

    active_sessions = db.get_active_sessions()
    return render_template('session.html', active_sessions=active_sessions)


@app.route('/end_session/<int:session_id>', methods=['GET', 'POST'])
def end_session(session_id):
    """
    End an active attendance session.
    Accepts both GET and POST for better reliability.
    """
    end_time = datetime.now().strftime('%H:%M:%S')
    db.end_session(session_id, end_time)
    print(f"[SESSION] Session {session_id} ended at {end_time}")
    return redirect(url_for('report'))


# ============================================================
# PHASE 5 — LIVE FACE RECOGNITION
# ============================================================

@app.route('/recognize/<int:session_id>')
def recognize(session_id):
    """Show the live webcam recognition page."""
    # Load all stored face encodings from the database
    all_encodings = db.get_all_encodings()
    return render_template('recognize.html',
                           session_id=session_id,
                           total_encodings=len(all_encodings))


@app.route('/recognize_frame', methods=['POST'])
def recognize_frame():
    """
    Called via JavaScript (AJAX) every 1.5 seconds from the recognize page.
    Receives a webcam frame, detects faces, compares with stored encodings.
    Returns recognized student info or 'Unknown'.
    Wrapped in try/except so it always returns JSON — never a 500 HTML page.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'faces': [], 'error': 'No data received.'})

        session_id = data.get('session_id')
        image_data = data.get('image', '')

        if not image_data or ',' not in image_data:
            return jsonify({'faces': [], 'error': 'Invalid image data.'})

        # ------- Decode the base64 image -------
        header, encoded = image_data.split(',', 1)
        img_bytes = base64.b64decode(encoded)
        np_arr    = np.frombuffer(img_bytes, np.uint8)
        frame     = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # Guard: imdecode returns None if image is invalid
        if frame is None:
            return jsonify({'faces': [], 'error': 'Could not decode frame.'})

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # ------- Detect all faces in this frame -------
        face_locations = face_recognition.face_locations(rgb_frame)
        if len(face_locations) == 0:
            return jsonify({'faces': []})

        # ------- Generate encodings for detected faces -------
        live_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        # ------- Load all stored student encodings from DB -------
        stored = db.get_all_encodings()
        if len(stored) == 0:
            return jsonify({'faces': [], 'message': 'No registered students found.'})

        known_encodings = [s['encoding'] for s in stored]

        results = []
        for i, live_enc in enumerate(live_encodings):
            # Compare live face with all stored encodings
            # tolerance=0.5 means stricter matching (lower = stricter)
            matches   = face_recognition.compare_faces(known_encodings, live_enc, tolerance=0.5)
            distances = face_recognition.face_distance(known_encodings, live_enc)

            face_info = {
                'location': list(face_locations[i]),  # (top, right, bottom, left) — list for JSON
                'name':        'Unknown User',
                'register_no': '',
                'status':      'unknown',
                'marked':      False
            }

            if True in matches:
                # Find the best match (smallest distance)
                best_index = int(np.argmin(distances))
                if matches[best_index]:
                    matched_student = stored[best_index]
                    face_info['name']        = matched_student['name']
                    face_info['register_no'] = matched_student['register_no']
                    face_info['student_id']  = int(matched_student['student_id'])
                    face_info['status']      = 'recognized'

                    # ------- Mark attendance -------
                    now        = datetime.now().strftime('%H:%M:%S')
                    was_marked = db.mark_attendance(session_id, matched_student['student_id'], now)
                    face_info['marked']       = was_marked
                    face_info['already_done'] = not was_marked

            results.append(face_info)

        return jsonify({'faces': results})

    except Exception as e:
        # Always return JSON — never let the server crash with an HTML 500 page
        print(f'[ERROR] /recognize_frame: {e}')
        return jsonify({'faces': [], 'error': str(e)})


# ============================================================
# PHASE 6 — ATTENDANCE REPORT
# ============================================================

@app.route('/report')
def report():
    """Show the full attendance report."""
    session_id = request.args.get('session_id', None)
    if session_id:
        records = db.get_attendance_report(int(session_id))
    else:
        records = db.get_attendance_report()

    all_sessions = db.get_all_sessions()
    return render_template('report.html',
                           records=records,
                           all_sessions=all_sessions,
                           selected_session=session_id)


# ============================================================
# RUN THE APP
# ============================================================
if __name__ == '__main__':
    print("=" * 50)
    print("  AI Smart Attendance System Starting...")
    print("  Open your browser: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True)
