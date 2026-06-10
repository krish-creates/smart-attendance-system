"""
database.py
-----------
This file handles all SQLite database operations.
It creates tables and provides helper functions to
interact with the database (insert, fetch data).
"""

import sqlite3
import os

# Path to our SQLite database file
DATABASE = 'attendance.db'


def get_db_connection():
    """
    Opens a connection to the SQLite database.
    'check_same_thread=False' allows Flask to use it across threads.
    'row_factory' lets us access columns by name (like a dictionary).
    """
    conn = sqlite3.connect(DATABASE, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def init_db():
    """
    Creates all necessary tables if they don't exist yet.
    Run this once when the app starts.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # -------------------------------------------------------
    # Table: students
    # Stores basic student information
    # -------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            register_no TEXT    NOT NULL UNIQUE,
            name        TEXT    NOT NULL,
            email       TEXT,
            department  TEXT,
            class_name  TEXT,
            semester    TEXT
        )
    ''')

    # -------------------------------------------------------
    # Table: face_encodings
    # Stores the 128-number face encoding for each student.
    # One student can have multiple encodings (from 20 images).
    # encoding_data is stored as a string of numbers.
    # -------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS face_encodings (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id   INTEGER NOT NULL,
            encoding_data TEXT   NOT NULL,
            image_path   TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    ''')

    # -------------------------------------------------------
    # Table: attendance_sessions
    # Faculty creates a session before starting attendance.
    # -------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_sessions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name   TEXT    NOT NULL,
            subject_name TEXT    NOT NULL,
            session_date TEXT    NOT NULL,
            start_time   TEXT    NOT NULL,
            end_time     TEXT,
            status       TEXT    DEFAULT 'active'
        )
    ''')

    # -------------------------------------------------------
    # Table: attendance
    # Records which student attended which session.
    # -------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER NOT NULL,
            student_id  INTEGER NOT NULL,
            marked_time TEXT    NOT NULL,
            status      TEXT    DEFAULT 'present',
            FOREIGN KEY (session_id)  REFERENCES attendance_sessions(id),
            FOREIGN KEY (student_id)  REFERENCES students(id)
        )
    ''')

    conn.commit()
    conn.close()
    print("[DB] Tables created / verified successfully.")


# -------------------------------------------------------
# Helper functions for Students
# -------------------------------------------------------

def add_student(register_no, name, email, department, class_name, semester):
    """Insert a new student into the students table."""
    conn = get_db_connection()
    try:
        conn.execute(
            '''INSERT INTO students
               (register_no, name, email, department, class_name, semester)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (register_no, name, email, department, class_name, semester)
        )
        conn.commit()
        # Get the ID of the newly inserted student
        student_id = conn.execute(
            'SELECT id FROM students WHERE register_no = ?', (register_no,)
        ).fetchone()['id']
        return student_id
    except sqlite3.IntegrityError:
        # register_no must be unique — return None if duplicate
        return None
    finally:
        conn.close()


def get_all_students():
    """Return a list of all students."""
    conn = get_db_connection()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return students


def get_student_by_id(student_id):
    """Return one student by their ID."""
    conn = get_db_connection()
    student = conn.execute(
        'SELECT * FROM students WHERE id = ?', (student_id,)
    ).fetchone()
    conn.close()
    return student


# -------------------------------------------------------
# Helper functions for Face Encodings
# -------------------------------------------------------

def save_encoding(student_id, encoding_array, image_path):
    """
    Save one face encoding to the database.
    encoding_array is a numpy array — we convert it to a comma-separated string.
    """
    # Convert numpy array to a simple comma-separated string
    encoding_str = ','.join(str(val) for val in encoding_array)
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO face_encodings (student_id, encoding_data, image_path) VALUES (?, ?, ?)',
        (student_id, encoding_str, image_path)
    )
    conn.commit()
    conn.close()


def get_all_encodings():
    """
    Return ALL face encodings with student info.
    Used during live recognition to compare against.
    Returns a list of dicts: {student_id, name, register_no, encoding_array}
    """
    import numpy as np
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT fe.student_id, fe.encoding_data, s.name, s.register_no
        FROM face_encodings fe
        JOIN students s ON fe.student_id = s.id
    ''').fetchall()
    conn.close()

    result = []
    for row in rows:
        # Convert the comma-separated string back to a numpy array
        encoding_array = np.array([float(x) for x in row['encoding_data'].split(',')])
        result.append({
            'student_id':  row['student_id'],
            'name':        row['name'],
            'register_no': row['register_no'],
            'encoding':    encoding_array
        })
    return result


# -------------------------------------------------------
# Helper functions for Attendance Sessions
# -------------------------------------------------------

def create_session(class_name, subject_name, session_date, start_time):
    """Create a new attendance session and return its ID."""
    conn = get_db_connection()
    cursor = conn.execute(
        '''INSERT INTO attendance_sessions
           (class_name, subject_name, session_date, start_time, status)
           VALUES (?, ?, ?, ?, 'active')''',
        (class_name, subject_name, session_date, start_time)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def end_session(session_id, end_time):
    """Mark a session as ended."""
    conn = get_db_connection()
    conn.execute(
        'UPDATE attendance_sessions SET status = ?, end_time = ? WHERE id = ?',
        ('ended', end_time, session_id)
    )
    conn.commit()
    conn.close()


def get_active_sessions():
    """Return all currently active sessions."""
    conn = get_db_connection()
    sessions = conn.execute(
        "SELECT * FROM attendance_sessions WHERE status = 'active'"
    ).fetchall()
    conn.close()
    return sessions


def get_all_sessions():
    """Return all sessions."""
    conn = get_db_connection()
    sessions = conn.execute(
        'SELECT * FROM attendance_sessions ORDER BY session_date DESC, start_time DESC'
    ).fetchall()
    conn.close()
    return sessions


# -------------------------------------------------------
# Helper functions for Attendance Records
# -------------------------------------------------------

def mark_attendance(session_id, student_id, marked_time):
    """
    Mark attendance for a student in a session.
    Prevents duplicate entries for the same student in the same session.
    Returns True if marked, False if already marked.
    """
    conn = get_db_connection()

    # Check if this student already has attendance in this session
    existing = conn.execute(
        'SELECT id FROM attendance WHERE session_id = ? AND student_id = ?',
        (session_id, student_id)
    ).fetchone()

    if existing:
        conn.close()
        return False  # Already marked — do not duplicate

    # Insert the new attendance record
    conn.execute(
        'INSERT INTO attendance (session_id, student_id, marked_time, status) VALUES (?, ?, ?, ?)',
        (session_id, student_id, marked_time, 'present')
    )
    conn.commit()
    conn.close()
    return True  # Marked successfully


def get_attendance_report(session_id=None):
    """
    Return attendance records.
    If session_id is given, return records for that session only.
    Otherwise return all records.
    """
    conn = get_db_connection()
    if session_id:
        rows = conn.execute('''
            SELECT
                s.name,
                s.register_no,
                s.class_name,
                ses.subject_name,
                ses.session_date,
                a.marked_time,
                a.status
            FROM attendance a
            JOIN students s       ON a.student_id  = s.id
            JOIN attendance_sessions ses ON a.session_id = ses.id
            WHERE a.session_id = ?
            ORDER BY a.marked_time
        ''', (session_id,)).fetchall()
    else:
        rows = conn.execute('''
            SELECT
                s.name,
                s.register_no,
                s.class_name,
                ses.subject_name,
                ses.session_date,
                a.marked_time,
                a.status
            FROM attendance a
            JOIN students s       ON a.student_id  = s.id
            JOIN attendance_sessions ses ON a.session_id = ses.id
            ORDER BY ses.session_date DESC, a.marked_time
        ''').fetchall()
    conn.close()
    return rows


def delete_student(student_id):
    """
    Completely remove a student and all related data from the database.
    Note: The caller (app.py) should handle deleting the physical image folder.
    """
    conn = get_db_connection()
    try:
        # 1. Delete attendance records
        conn.execute('DELETE FROM attendance WHERE student_id = ?', (student_id,))
        # 2. Delete face encodings
        conn.execute('DELETE FROM face_encodings WHERE student_id = ?', (student_id,))
        # 3. Delete student record
        conn.execute('DELETE FROM students WHERE id = ?', (student_id,))
        conn.commit()
        print(f"[DB] Deleted student ID {student_id} and all related records.")
        return True
    except Exception as e:
        print(f"[DB ERROR] delete_student: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
def reset_sessions():
    """
    Delete all attendance sessions and associated attendance records.
    """
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM attendance')
        conn.execute('DELETE FROM attendance_sessions')
        conn.commit()
        print("[DB] All sessions and attendance records have been reset.")
        return True
    except Exception as e:
        print(f"[DB ERROR] reset_sessions: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
