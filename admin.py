from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, Response
from models import db, User, Course, AttendanceLog
import csv
from io import StringIO

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))
        
    students = User.query.filter_by(role='student').all()
    faculty_count = User.query.filter_by(role='faculty').count()
    course_count = Course.query.count()

    # --- NEW: Calculate Students At Risk ---
    at_risk_count = 0
    for student in students:
        assigned_courses = Course.query.filter_by(target_section=student.class_name).all()
        total_conducted = 0
        total_attended = 0
        
        for c in assigned_courses:
            all_logs = AttendanceLog.query.filter_by(course_id=c.id, student_id=student.id).all()
            total_conducted += len(all_logs)
            total_attended += sum(1 for log in all_logs if log.status == 'Present')
            
        if total_conducted > 0:
            percentage = int((total_attended / total_conducted) * 100)
            if percentage < 75:
                at_risk_count += 1

    return render_template('admin/dashboard.html', 
                           students=len(students), 
                           faculty=faculty_count, 
                           courses=course_count,
                           at_risk_count=at_risk_count)

@admin_bp.route('/at_risk_students')
def at_risk_students():
    """Generates the list of students falling below the 75% threshold."""
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))

    all_students = User.query.filter_by(role='student').all()
    at_risk_list = []
    
    for student in all_students:
        assigned_courses = Course.query.filter_by(target_section=student.class_name).all()
        total_conducted = 0
        total_attended = 0
        
        for c in assigned_courses:
            all_logs = AttendanceLog.query.filter_by(course_id=c.id, student_id=student.id).all()
            total_conducted += len(all_logs)
            total_attended += sum(1 for log in all_logs if log.status == 'Present')
            
        if total_conducted > 0:
            percentage = int((total_attended / total_conducted) * 100)
            if percentage < 75:
                at_risk_list.append({
                    'name': student.name,
                    'identifier': student.identifier,
                    'section': student.class_name,
                    'percentage': percentage,
                    'conducted': total_conducted,
                    'attended': total_attended
                })
    
    # Sort the list so the students with the lowest percentages are at the very top!
    at_risk_list = sorted(at_risk_list, key=lambda x: x['percentage'])
    
    return render_template('admin/at_risk.html', students=at_risk_list)

@admin_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handles the Single Profile Creation form"""
    if request.method == 'POST':
        name = request.form.get('name')
        register_no = request.form.get('register_no')
        email = request.form.get('email')
        department = request.form.get('department')
        class_name = request.form.get('class_name')
        semester = request.form.get('semester')

        existing = User.query.filter((User.email == email) | (User.identifier == register_no)).first()
        
        if existing:
            flash("Error: Student with this Email or Register No already exists.", "error")
        else:
            new_student = User(
                name=name, email=email, role='student', identifier=register_no,
                department=department, class_name=class_name, semester=semester
            )
            db.session.add(new_student)
            db.session.commit()
            flash(f"Successfully enrolled Student: {name} ({register_no})", "success")
            
        return redirect(url_for('admin.register'))
        
    return render_template('admin/register.html')

@admin_bp.route('/bulk_register', methods=['POST'])
def bulk_register():
    """Handles the Mass Registry Import (CSV/Excel)"""
    if 'bulk_file' not in request.files:
        flash("No file was uploaded.", "error")
        return redirect(url_for('admin.register'))
    
    file = request.files['bulk_file']
    if file.filename == '':
        flash("No selected file.", "error")
        return redirect(url_for('admin.register'))
        
    if file and (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):
        try:
            # Read the file using Pandas
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            
            # Validate columns match your HTML instructions
            required_cols = ['name', 'register_no', 'email', 'department', 'class_name', 'semester']
            if not all(col in df.columns for col in required_cols):
                flash(f"Invalid format. Column headers must be exactly: {', '.join(required_cols)}", "error")
                return redirect(url_for('admin.register'))
            
            # Insert everyone into the database
            added_count = 0
            for index, row in df.iterrows():
                existing = User.query.filter((User.email == row['email']) | (User.identifier == str(row['register_no']))).first()
                if not existing:
                    new_student = User(
                        name=row['name'], email=row['email'], role='student', identifier=str(row['register_no']),
                        department=row['department'], class_name=row['class_name'], semester=row['semester']
                    )
                    db.session.add(new_student)
                    added_count += 1
            
            db.session.commit()
            flash(f"Successfully imported {added_count} students via bulk upload!", "success")
            
        except Exception as e:
            flash(f"Error processing file: {str(e)}", "error")
    else:
        flash("Invalid file type. Please upload a .csv or .xlsx file.", "error")
        
    return redirect(url_for('admin.register'))

@admin_bp.route('/register_faculty', methods=['GET', 'POST'])
def register_faculty():
    """Handles Faculty Onboarding"""
    if request.method == 'POST':
        name = request.form.get('name')
        employee_id = request.form.get('employee_id')
        email = request.form.get('email')
        department = request.form.get('department')

        existing_user = User.query.filter((User.email == email) | (User.identifier == employee_id)).first()

        if existing_user:
            flash("Error: A user with this Email or Employee ID already exists.", "error")
        else:
            new_faculty = User(
                name=name, email=email, role='faculty', 
                identifier=employee_id, department=department
            )
            db.session.add(new_faculty)
            db.session.commit()
            flash(f"Successfully registered Faculty: {name}", "success")
            
        return redirect(url_for('admin.register_faculty'))

    return render_template('admin/faculty_registry.html')

@admin_bp.route('/manage_courses', methods=['GET', 'POST'])
def manage_courses():
    """Handles Mapping Subjects to Faculty"""
    if request.method == 'POST':
        code = request.form.get('course_code')
        name = request.form.get('course_name')
        target_section = request.form.get('target_section')
        faculty_id = request.form.get('faculty_id')
        total_classes = request.form.get('total_classes') # <-- WE MISSED THIS!

        existing_course = Course.query.filter_by(code=code).first()
        
        if existing_course:
            flash("Error: A course with this code already exists.", "error")
        else:
            new_course = Course(
                code=code, name=name, 
                target_section=target_section, faculty_id=faculty_id,
                total_classes=int(total_classes) if total_classes else 0 # <-- AND SAVING IT HERE!
            )
            db.session.add(new_course)
            db.session.commit()
            flash(f"Course '{name}' successfully mapped to Faculty!", "success")
            
        return redirect(url_for('admin.manage_courses'))

    active_courses = Course.query.all()
    available_faculty = User.query.filter_by(role='faculty').all()
    
    return render_template('admin/courses.html', courses=active_courses, faculties=available_faculty)

@admin_bp.route('/report', methods=['GET'])
def report():
    """Fetches live attendance data and shapes it for the report.html template."""
    
    # 1. Capture the dropdown filter if the Admin clicked "Apply Filter"
    selected_course_id = request.args.get('session_id')

    # 2. Build the fake "Sessions" list for your Dropdown using the mapped Courses
    all_courses = Course.query.all()
    all_sessions = []
    for c in all_courses:
        all_sessions.append({
            'id': c.id,
            'session_date': 'Mapped Course', 
            'class_name': c.target_section,
            'subject_name': c.name,
            'status': 'Active'
        })

    # 3. Query the actual database logs, joining Users and Courses
    query = db.session.query(AttendanceLog, User, Course)\
        .join(User, AttendanceLog.student_id == User.id)\
        .join(Course, AttendanceLog.course_id == Course.id)
        
    # If they selected a filter, apply it to the query!
    if selected_course_id:
        query = query.filter(AttendanceLog.course_id == selected_course_id)

    # Execute the query and sort by newest first
    logs = query.order_by(AttendanceLog.date.desc(), AttendanceLog.time_marked.desc()).all()

    # 4. Format the raw database data into the exact dictionaries your HTML expects
    records = []
    for log_entry, student, course in logs:
        records.append({
            'name': student.name,
            'register_no': student.identifier,
            'class_name': student.class_name,
            'subject_name': course.name,
            'session_date': log_entry.date.strftime('%Y-%m-%d'),
            'marked_time': log_entry.time_marked.strftime('%I:%M %p'),
            'status': log_entry.status.lower() # converts 'Present' to 'present' for your green badge
        })

    # Send it all directly to your existing, unchanged HTML file!
    return render_template('admin/report.html', 
                           records=records, 
                           all_sessions=all_sessions, 
                           selected_session=selected_course_id)
@admin_bp.route('/delete_user', methods=['POST'])
def delete_user():
    """PERMANENTLY deletes a user and all their associated data."""
    identifier = request.form.get('identifier')
    
    # 1. Find the user by their Register No or Employee ID
    user_to_delete = User.query.filter_by(identifier=identifier).first()

    if not user_to_delete:
        flash(f"Error: No user found with ID '{identifier}'.", "error")
        return redirect(url_for('admin.dashboard'))

    # 2. Prevent the Admin from accidentally deleting themselves!
    if user_to_delete.role == 'admin':
        flash("Action Denied: You cannot delete the Master Admin.", "error")
        return redirect(url_for('admin.dashboard'))

    try:
        # 3. CASCADE DELETE: Remove their child records first
        if user_to_delete.role == 'student':
            # Wipe all their attendance logs
            AttendanceLog.query.filter_by(student_id=user_to_delete.id).delete()
        elif user_to_delete.role == 'faculty':
            # Wipe (or reassign) their courses
            Course.query.filter_by(faculty_id=user_to_delete.id).delete()

        # 4. Finally, permanently delete the user profile and biometrics
        db.session.delete(user_to_delete)
        db.session.commit()
        
        flash(f"SUCCESS: {user_to_delete.name} ({identifier}) and all their data was permanently wiped.", "success")
        
    except Exception as e:
        db.session.rollback() # If something goes wrong, undo the deletion!
        flash(f"Database Error: {str(e)}", "error")

    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/delete_course/<int:course_id>', methods=['POST'])
def delete_course(course_id):
    """PERMANENTLY deletes a course and all its attendance records."""
    course_to_delete = Course.query.get_or_404(course_id)

    try:
        # 1. CASCADE DELETE: Wipe all attendance logs for this specific course first
        AttendanceLog.query.filter_by(course_id=course_to_delete.id).delete()

        # 2. Delete the course mapping
        db.session.delete(course_to_delete)
        db.session.commit()
        
        flash(f"SUCCESS: Course '{course_to_delete.code}' and its logs were permanently deleted.", "success")
        
    except Exception as e:
        db.session.rollback() # Undo if something breaks
        flash(f"Database Error: {str(e)}", "error")

    return redirect(url_for('admin.manage_courses'))