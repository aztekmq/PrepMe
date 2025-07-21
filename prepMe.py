import os
import json
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_session import Session
from cryptography.fernet import Fernet

# Setup Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Logging config
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('flashcard_app.log'),
        logging.StreamHandler()
    ]
)

# Session config
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './.flask_session'
app.config['SESSION_PERMANENT'] = False
Session(app)

# Fernet key setup
KEY_FILE = 'secret.key'
if not os.path.exists(KEY_FILE):
    with open(KEY_FILE, 'wb') as f:
        f.write(Fernet.generate_key())
with open(KEY_FILE, 'rb') as f:
    key = f.read()
fernet = Fernet(key)

# Set global access to fernet
import utils.security as security
security.init_fernet(key)

# Course loading helper
def load_course(course_filename):
    try:
        full_path = os.path.join('courses', course_filename)
        with open(full_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f'Failed to load course file {course_filename}: {e}')
        return None

# Initial/default course
DEFAULT_COURSE_FILE = 'course.json'
DEFAULT_COURSE_PATH = os.path.join('courses', DEFAULT_COURSE_FILE)
if not os.path.exists(DEFAULT_COURSE_PATH):
    raise FileNotFoundError(f"Missing {DEFAULT_COURSE_PATH}")

course_data = load_course(DEFAULT_COURSE_FILE)
current_course = DEFAULT_COURSE_FILE

# Expose to builtins
import builtins
builtins.course_data = course_data
builtins.current_course = current_course

# Init DB
def init_db():
    conn = sqlite3.connect('scores.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            module_id TEXT,
            score INTEGER,
            correct INTEGER,
            total INTEGER,
            timestamp TEXT,
            FOREIGN KEY (username) REFERENCES users(username)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS missed_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER,
            question_text TEXT,
            user_answer TEXT,
            correct_answer TEXT,
            FOREIGN KEY (attempt_id) REFERENCES scores(id)
        )
    ''')
    conn.commit()
    conn.close()
    logging.info('Database initialized successfully')

init_db()

# Import and register blueprints
from routes.auth_routes import auth_bp
from routes.quiz_routes import quiz_bp

app.register_blueprint(auth_bp)
app.register_blueprint(quiz_bp, url_prefix='/quiz')

# Home redirects to quiz
@app.route('/')
def home():
    return redirect(url_for('quiz_bp.index'))

# Admin question editing
@app.route('/admin/questions')
def manage_questions():
    if 'username' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('auth_bp.login'))
    logging.debug(f"[Admin Edit] Current course: {getattr(builtins, 'current_course', 'UNKNOWN')}")
    # ✅ Use updated reference from builtins
    return render_template('manage_questions.html', modules=builtins.course_data.get('course', {}).get('modules', []))

# Course selection form (GET) and action (POST)
@app.route('/select_course', methods=['GET', 'POST'])
def select_course():
    courses_dir = 'courses'
    courses = {}
    for fname in os.listdir(courses_dir):
        if fname.endswith('.json'):
            try:
                course_data = load_course(fname)
                if course_data:
                    courses[fname] = {
                        'name': course_data['course'].get('name') or course_data['course'].get('title') or fname,
                        'modules': course_data['course'].get('modules', [])
                    }
            except Exception as e:
                logging.warning(f"Error reading course {fname}: {e}")
                courses[fname] = {'name': fname, 'modules': []}

    if request.method == 'POST':
        selected_file = request.form.get('course_file')
        if selected_file and selected_file in courses:
            new_data = load_course(selected_file)
            if new_data:
                builtins.course_data = new_data
                builtins.current_course = selected_file
                session['selected_course'] = selected_file
                session['current_course_name'] = new_data['course'].get('name') or new_data['course'].get('title') or selected_file
                flash(f"Course '{session['current_course_name']}' loaded successfully.", "success")
            else:
                flash("Failed to load selected course.", "error")
        else:
            flash("Invalid course file selected.", "error")
        return redirect(url_for('quiz_bp.index'))

    return render_template('select_course.html', courses=courses, current_course=current_course)

# Run app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)