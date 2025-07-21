from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import sqlite3
import logging
from utils.security import verify_password, encrypt_password

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/')
def login():
    """Render login page or redirect if already logged in."""
    if 'username' in session:
        return redirect(url_for('quiz_bp.index'))
    return render_template('login.html')

@auth_bp.route('/login', methods=['POST'])
def do_login():
    """Handle user login."""
    username = request.form.get('username')
    password = request.form.get('password')
    try:
        conn = sqlite3.connect('scores.db')
        cursor = conn.cursor()
        cursor.execute('SELECT password FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()

        if result and verify_password(result[0], password):
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('quiz_bp.index'))
        else:
            flash('Invalid username or password.', 'error')
            return redirect(url_for('auth_bp.login'))

    except sqlite3.Error as e:
        logging.error(f"[LoginError] {e}")
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('auth_bp.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Register a new user."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        try:
            encrypted_password = encrypt_password(password)
            conn = sqlite3.connect('scores.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, encrypted_password))
            conn.commit()
            conn.close()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth_bp.login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.', 'error')
            return redirect(url_for('auth_bp.register'))
        except Exception as e:
            logging.error(f"[RegisterError] {e}")
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('auth_bp.register'))
    return render_template('register.html')

@auth_bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    """Reset password for existing user."""
    if request.method == 'POST':
        username = request.form.get('username')
        new_password = request.form.get('new_password')
        try:
            encrypted_password = encrypt_password(new_password)
            conn = sqlite3.connect('scores.db')
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET password = ? WHERE username = ?', (encrypted_password, username))
            if cursor.rowcount == 0:
                flash('Username not found.', 'error')
            else:
                conn.commit()
                flash('Password reset successful! Please log in.', 'success')
            conn.close()
            return redirect(url_for('auth_bp.login'))
        except Exception as e:
            logging.error(f"[ResetPasswordError] {e}")
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('auth_bp.reset_password'))
    return render_template('reset_password.html')

@auth_bp.route('/logout')
def logout():
    """Log the user out and clear session."""
    session.pop('username', None)
    flash('Logged out successfully.', 'success')
    return redirect(url_for('auth_bp.login'))