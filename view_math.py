import numpy as np
from app import app, db
from models import User

with app.app_context():
    print("Connecting to the database...")
    
    # 1. Count how many total students exist
    total_students = User.query.filter_by(role='student').count()
    print(f"Total student accounts found in database: {total_students}")
    
    if total_students == 0:
        print("\n[ALERT] There are 0 students registered in your database.")
        print("Go to your Admin panel, add a student email, log in as that student, and complete the facial registration first!")
        import sys
        sys.exit()

    # 2. Fetch all students to see who has an encoding
    all_students = User.query.filter_by(role='student').all()
    
    student_with_face = None
    for student in all_students:
        if student.face_encoding:
            student_with_face = student
            break
            
    # 3. Print the results
    if student_with_face:
        print(f"\n[SUCCESS] Found face encoding data for: {student_with_face.name}")
        print("-" * 50)
        
        # Convert binary BLOB to NumPy mathematical array
        math_array = np.frombuffer(student_with_face.face_encoding, dtype=np.float64)
        
        print(f"Total dimensions extracted: {len(math_array)} values.")
        print("First 10 facial vector coordinates:")
        for i, val in enumerate(math_array[:10]):
            print(f"  Vector coordinate {i+1}: {val:.6f}")
            
        print("\n... (and 118 more precise facial measurements mapping your face structure) ...")
        print("-" * 50)
    else:
        print("\n[ALERT] Student accounts exist, but NONE of them have completed facial registration yet.")
        print("The 'face_encoding' column for all students is currently empty (NULL).")