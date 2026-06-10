from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Notice we only need two things now!
        username = request.form.get('username')
        password = request.form.get('password')

        # 1. Search the entire database for this unique username
        user = User.query.filter_by(username=username).first()

        # 2. Verify password
        if user and user.password_hash and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['role'] = user.role
            session['name'] = user.name

            # 3. Auto-route them based on their hidden database role!
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'faculty':
                return redirect(url_for('faculty.dashboard'))
            elif user.role == 'student':
                return redirect(url_for('student.dashboard'))
        else:
            flash("Invalid username or password.", "error")
            return redirect(url_for('auth.login'))

    return render_template('auth/login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        account_type = request.form.get('account_type')
        email = request.form.get('email')
        new_username = request.form.get('username') # The username they want
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for('auth.signup'))

        # 1. Verify their email is pre-registered
        user = User.query.filter_by(email=email, role=account_type).first()
        if not user:
            flash("Email not recognized. Contact Admin.", "error")
            return redirect(url_for('auth.signup'))
        if user.password_hash:
            flash("Account is already activated. Please log in.", "error")
            return redirect(url_for('auth.login'))

        # 2. Check if the username they picked is already taken by someone else
        existing_username = User.query.filter_by(username=new_username).first()
        if existing_username:
            flash("That username is already taken. Please choose another.", "error")
            return redirect(url_for('auth.signup'))

        # 3. Save the new username and encrypted password
        user.username = new_username
        user.password_hash = generate_password_hash(password)
        db.session.commit()

        return render_template('auth/signup.html', success=True, account_type=account_type, user_id=user.id)

    return render_template('auth/signup.html', success=False)


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))