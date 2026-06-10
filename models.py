from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize the database object
db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    
    # The unique username they create during signup
    username = db.Column(db.String(50), unique=True, nullable=True) 
    
    password_hash = db.Column(db.String(200), nullable=True) 
    role = db.Column(db.String(20), nullable=False) 
    identifier = db.Column(db.String(50), unique=True, nullable=False) 
    department = db.Column(db.String(100), nullable=True)
    class_name = db.Column(db.String(50), nullable=True) 
    semester = db.Column(db.String(20), nullable=True)
    face_encoding = db.Column(db.LargeBinary, nullable=True)

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    total_classes = db.Column(db.Integer, default=0)
    target_section = db.Column(db.String(50), nullable=False) 
    
    # Foreign Key linking to the Faculty User
    faculty_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

class AttendanceLog(db.Model):
    __tablename__ = 'attendance_logs'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow().date)
    time_marked = db.Column(db.Time, default=datetime.utcnow().time)
    status = db.Column(db.String(20), nullable=False) # 'Present' or 'Absent'
    
    # Foreign Keys
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)