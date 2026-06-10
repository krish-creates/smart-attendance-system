import os
from flask import Flask, redirect, url_for
from werkzeug.security import generate_password_hash

# Import our SQLAlchemy database and the User model
from models import db, User, Course, AttendanceLog

# Import your blueprints
from auth import auth_bp
from admin import admin_bp
from faculty import faculty_bp
from student import student_bp

app = Flask(__name__)
app.secret_key = 'smart_attendance_secret_key_2024'

# --- DATABASE CONFIGURATION ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bioscan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 1. Bind the SQLAlchemy object to your Flask app
db.init_app(app)

# Folder where we save captured face images
FACE_IMAGES_DIR = 'face_images'
os.makedirs(FACE_IMAGES_DIR, exist_ok=True)

# 2. Create the actual database tables and run the Admin Seeder
with app.app_context():
    db.create_all()
    
    # --- THE ADMIN SEEDER ---
    # Check if an admin already exists in the database
    admin_exists = User.query.filter_by(role='admin').first()
    
    if not admin_exists:
        print(">> No Admin found. Generating default Master Admin...")
        default_admin = User(
            name='System Administrator',
            username='admin',
            email='admin@institute.edu',
            password_hash=generate_password_hash('admin123'),
            role='admin',
            identifier='ADMIN-001'
        )
        db.session.add(default_admin)
        db.session.commit()
        print(">> Master Admin created successfully! (Email: admin@institute.edu | Pass: admin123)")

# 3. Register Blueprints (Crucial for routing!)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(faculty_bp)
app.register_blueprint(student_bp)

# Base route redirects to auth
@app.route('/')
def index():
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    print("=" * 50)
    print("   AI Smart Attendance Modular System Starting...")
    print("   Open your browser: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True)