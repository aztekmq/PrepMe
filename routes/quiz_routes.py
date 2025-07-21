from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import logging
import random
import sqlite3
import builtins
import json
import os
from werkzeug.utils import secure_filename
from flask import jsonify

course_data = builtins.course_data  # Provided by flash_card.py

quiz_bp = Blueprint('quiz_bp', __name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'courses')
ALLOWED_EXTENSIONS = {'json'}

@quiz_bp.route('/index')
def index():
    if 'username' not in session:
        flash("Please log in.", "error")
        return redirect(url_for('auth_bp.login'))

    try:
        # Reload course_data from builtins (which is updated by select_course)
        global course_data
        course_data = builtins.course_data

        modules = course_data['course']['modules']

        # Get selected filename from session or use fallback
        filename = session.get('selected_course', 'Untitled')

        # Use 'name' or 'title' from course data to display
        course_name = course_data['course'].get('name') or course_data['course'].get('title') or filename

        # Update session with current course name
        session['current_course_name'] = course_name

        # List available .json files in /courses
        course_dir = os.path.join(os.getcwd(), 'courses')
        course_selection = []
        for fname in os.listdir(course_dir):
            if fname.endswith('.json'):
                try:
                    with open(os.path.join(course_dir, fname), 'r') as f:
                        data = json.load(f)
                    name = data.get('course', {}).get('name') or data.get('course', {}).get('title') or fname
                except Exception as e:
                    logging.warning(f"Error reading course {fname}: {e}")
                    name = fname
                course_selection.append((fname, name))

        return render_template(
            'index.html',
            modules=modules,
            username=session['username'],
            current_course_name=course_name,
            course_selection=course_selection
        )
    except Exception as e:
        logging.error(f"Index error: {e}")
        flash("Failed to load modules.", "error")
        return render_template('error.html')

@quiz_bp.route('/edit_module/<int:module_id>', methods=['GET', 'POST'])
def edit_module_questions(module_id):
    course = course_data.get("course", {})
    modules = course.get("modules", [])
    selected_module = next((m for m in modules if m.get("id") == module_id), None)

    if not selected_module:
        flash("Module not found.", "error")
        return redirect(url_for('quiz_bp.index'))

    if request.method == 'POST':
        try:
            total = int(request.form.get("total_questions", 0))
            questions = []
            for i in range(total):
                q_text = request.form.get(f"question_{i}")
                opts = [
                    request.form.get(f"option_{i}_0"),
                    request.form.get(f"option_{i}_1"),
                    request.form.get(f"option_{i}_2"),
                    request.form.get(f"option_{i}_3")
                ]
                answer = request.form.get(f"answer_{i}", "").upper()
                questions.append({
                    "question": q_text,
                    "options": opts,
                    "answer": answer
                })

            # Update in-memory course data
            selected_module["questions"] = questions

            # Persist to JSON
            filename = session.get('selected_course')
            if not filename:
                raise ValueError("No course selected in session.")

            filepath = os.path.join(UPLOAD_FOLDER, filename)
            with open(filepath, 'w') as f:
                json.dump(course_data, f, indent=2)

            flash("Questions saved and persisted to file!", "success")
        except Exception as e:
            logging.error(f"Failed to save questions: {e}")
            flash("Error saving questions.", "error")

    # Reload updated questions
    questions = selected_module.get("questions") or selected_module.get("knowledge_check") or []
    return render_template("edit_questions.html", module=selected_module, questions=questions)
    
@quiz_bp.route('/select_course/<filename>')
def select_course(filename):
    try:
        filepath = os.path.join('courses', filename)
        with open(filepath, 'r') as f:
            new_course_data = json.load(f)
            course_name = new_course_data['course'].get('name') or new_course_data['course'].get('title') or filename
            builtins.course_data = new_course_data
            session['selected_course'] = filename
            session['current_course_name'] = course_name
            flash(f"Course '{course_name}' loaded successfully.", "success")

        # Prepare courses data for the template
        course_dir = os.path.join(os.getcwd(), 'courses')
        courses = {}
        for fname in os.listdir(course_dir):
            if fname.endswith('.json'):
                try:
                    with open(os.path.join(course_dir, fname), 'r') as f:
                        data = json.load(f)
                        courses[fname] = {
                            'name': data['course'].get('name') or data['course'].get('title') or fname,
                            'modules': data['course'].get('modules', [])
                        }
                except Exception as e:
                    logging.warning(f"Error reading course {fname}: {e}")
                    courses[fname] = {'name': fname, 'modules': []}

        return render_template('index.html', courses=courses)
    except Exception as e:
        logging.error(f"Failed to load selected course '{filename}': {e}")
        return jsonify({'success': False}), 500

@quiz_bp.route('/start_quiz', methods=['POST'])
def start_quiz():
    module_id = request.form.get('module_id')
    order = request.form.get('order')

    if module_id == 'all':
        all_questions = []
        for module in course_data['course']['modules']:
            questions = module.get('questions') or module.get('knowledge_check')
            for q in questions:
                q['module_title'] = module['title']
                all_questions.append(q)
        if order == 'random':
            random.shuffle(all_questions)

        session['quiz_data'] = {
            'module_id': 'all',
            'module_title': 'All Modules',
            'questions': all_questions,
            'current_index': 0,
            'score': 0,
            'correct': 0,
            'total': len(all_questions),
            'user_answers': [],
            'missed_questions': [],
            'save_to_db': True  # Flag to determine if data should be saved
        }
        return redirect(url_for('quiz_bp.quiz'))

    elif module_id == 'random':
        module = random.choice(course_data['course']['modules'])
    else:
        module = next((m for m in course_data['course']['modules'] if str(m['id']) == module_id), None)

    if not module:
        logging.error(f"Invalid module ID: {module_id}")
        flash("Selected module does not exist.", "error")
        return redirect(url_for('quiz_bp.index'))

    questions = module.get('questions') or module.get('knowledge_check')
    if order == 'random':
        random.shuffle(questions)

    session['quiz_data'] = {
        'module_id': module.get('id', 'random'),
        'module_title': module['title'],
        'questions': questions,
        'current_index': 0,
        'score': 0,
        'correct': 0,
        'total': len(questions),
        'user_answers': [],
        'missed_questions': [],
        'save_to_db': True  # Flag to determine if data should be saved
    }
    return redirect(url_for('quiz_bp.quiz'))

@quiz_bp.route('/quiz', methods=['GET', 'POST'])
def quiz():
    quiz_data = session.get('quiz_data')
    if not quiz_data:
        return redirect(url_for('quiz_bp.index'))

    index = quiz_data.get('current_index', 0)

    if request.method == 'POST':
        action = request.form.get('action')
        selected_option = request.form.get('answer')
        current_question = quiz_data['questions'][index]

        options = [opt.split(':', 1)[-1].strip() if ':' in opt else opt for opt in current_question['options']]
        correct_letter = current_question['answer'].strip().upper()
        correct_index = ord(correct_letter) - ord('A')
        correct_text = options[correct_index]
        selected_text = options[ord(selected_option.upper()) - ord('A')] if selected_option else ""

        if action == 'submit':
            is_correct = selected_option and selected_option.strip().upper() == correct_letter

            quiz_data['user_answers'].append({
                'question': current_question['question'],
                'your_answer': selected_option,
                'your_answer_text': selected_text,
                'correct_answer': correct_letter,
                'correct_answer_text': correct_text,
                'options': options,
                'is_correct': is_correct
            })

            if is_correct:
                quiz_data['score'] += 1
                quiz_data['correct'] += 1
            else:
                quiz_data['missed_questions'].append({
                    'question': current_question['question'],
                    'user_answer': selected_option,
                    'user_answer_text': selected_text,
                    'correct_answer': correct_letter,
                    'correct_answer_text': correct_text,
                    'options': options
                })

        elif action == 'skip':
            quiz_data['user_answers'].append({
                'question': current_question['question'],
                'your_answer': None,
                'your_answer_text': '',
                'correct_answer': correct_letter,
                'correct_answer_text': correct_text,
                'options': options,
                'is_correct': False
            })

            quiz_data['missed_questions'].append({
                'question': current_question['question'],
                'user_answer': None,
                'user_answer_text': '',
                'correct_answer': correct_letter,
                'correct_answer_text': correct_text,
                'options': options
            })

        quiz_data['current_index'] = index + 1
        session['quiz_data'] = quiz_data

        if quiz_data['current_index'] >= quiz_data['total']:
            return redirect(url_for('quiz_bp.show_results'))

        index = quiz_data['current_index']

    elif request.method == 'GET' and 'end_quiz' in request.args:
        # Handle "End Quiz Now" click by setting save_to_db to False
        quiz_data['save_to_db'] = False
        session['quiz_data'] = quiz_data
        return redirect(url_for('quiz_bp.show_results'))

    current_question = quiz_data['questions'][index]
    options = [opt.split(':', 1)[-1].strip() if ':' in opt else opt for opt in current_question['options']]
    lettered_options = [(chr(65 + i), opt) for i, opt in enumerate(options)]

    return render_template(
        'quiz.html',
        question=current_question,
        question_num=index + 1,
        total=quiz_data['total'],
        module_title=quiz_data.get('module_title', 'Unknown Module'),
        lettered_options=lettered_options
    )

@quiz_bp.route('/show_results')
def show_results():
    quiz_data = session.get('quiz_data')
    if not quiz_data:
        return redirect(url_for('quiz_bp.index'))

    # Only save to DB if save_to_db is True
    if not quiz_data.get('saved') and quiz_data.get('save_to_db', True):
        attempt_id = save_quiz_results(quiz_data, session.get('username'))
        quiz_data['saved'] = True
        quiz_data['attempt_id'] = attempt_id  # ✅ Add to session
        session['quiz_data'] = quiz_data
    elif not quiz_data.get('save_to_db', True):
        # Clear quiz_data if "End Quiz Now" was clicked to prevent future saves
        session.pop('quiz_data', None)
        flash("Quiz ended early. Results not saved.", "info")

    return render_template('results.html', quiz_data=quiz_data)


@quiz_bp.route('/missed_questions/<int:attempt_id>')
def missed_questions_by_attempt(attempt_id):
    try:
        conn = sqlite3.connect('scores.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT question_text, user_answer, correct_answer
            FROM missed_questions
            WHERE attempt_id = ?
        ''', (attempt_id,))
        rows = cursor.fetchall()
        conn.close()

        missed = [
            {
                'question': row[0],
                'user_answer': row[1],
                'correct_answer': row[2]
            }
            for row in rows
        ]

        return render_template('missed_questions.html', missed=missed)
    except Exception as e:
        logging.error(f"[MissedQuestionsByAttemptError] {e}")
        flash("Failed to load missed questions for this attempt.", "error")
        return redirect(url_for('quiz_bp.scoreboard'))

@quiz_bp.route('/scoreboard')
def scoreboard():
    try:
        conn = sqlite3.connect('scores.db')
        cursor = conn.cursor()
        cursor.execute('''SELECT id, username, module_id, score, correct, total, timestamp
                          FROM scores ORDER BY timestamp DESC LIMIT 50''')
        rows = cursor.fetchall()
        conn.close()

        scores = []
        for row in rows:
            attempt_id, username, module_id, score, correct, total, timestamp = row
            module_title = next(
                (m['title'] for m in course_data['course']['modules'] if str(m['id']) == str(module_id)),
                f"Module {module_id}"
            )

            scores.append({
                'attempt_id': attempt_id,
                'username': username,
                'module_id': module_id,
                'score': score,
                'correct': correct,
                'total': total,
                'timestamp': timestamp,
                'module_title': module_title
            })

        return render_template('scoreboard.html', scores=scores, username=session.get('username'))

    except Exception as e:
        logging.error(f"[ScoreboardError] {e}")
        flash("Failed to load scoreboard.", "error")
        return redirect(url_for('quiz_bp.index'))

@quiz_bp.route('/upload_course', methods=['POST'])
def upload_course():
    if 'username' not in session:
        flash("You must be logged in to upload courses.", "error")
        return redirect(url_for('auth_bp.login'))

    file = request.files.get('course_file')
    if not file or file.filename == '':
        flash("No file selected.", "error")
        return redirect(url_for('quiz_bp.index'))

    filename = secure_filename(file.filename)
    if not filename.endswith('.json') or '.' not in filename:
        flash("Only .json files are allowed.", "error")
        return redirect(url_for('quiz_bp.index'))

    filepath = os.path.join(UPLOAD_FOLDER, filename)

    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file.save(filepath)

        with open(filepath, 'r') as f:
            loaded_data = json.load(f)

        # Validate structure
        if 'course' not in loaded_data or 'modules' not in loaded_data['course']:
            flash("Invalid course file format.", "error")
            return redirect(url_for('quiz_bp.index'))

        builtins.course_data = loaded_data
        session['selected_course'] = filename
        session['current_course_name'] = loaded_data['course'].get('name') or loaded_data['course'].get('title') or filename
        flash("New course uploaded and selected!", "success")
        return redirect(url_for('quiz_bp.index'))

    except Exception as e:
        logging.error(f"Upload failed: {e}")
        flash("Error uploading course file.", "error")
        return redirect(url_for('quiz_bp.index'))

def save_quiz_results(quiz_data, username):
    try:
        conn = sqlite3.connect('scores.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO scores (username, module_id, score, correct, total, timestamp)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        ''', (
            username,
            quiz_data.get('module_id'),
            quiz_data.get('score'),
            quiz_data.get('correct'),
            quiz_data.get('total')
        ))
        attempt_id = cursor.lastrowid

        for q in quiz_data.get('missed_questions', []):
            cursor.execute('''
                INSERT INTO missed_questions (attempt_id, question_text, user_answer, correct_answer)
                VALUES (?, ?, ?, ?)
            ''', (
                attempt_id,
                q['question'],
                q.get('user_answer'),
                q['correct_answer']
            ))

        conn.commit()
        conn.close()
        return attempt_id  # ✅ RETURN it
    except Exception as e:
        logging.error(f"Failed to save quiz result: {e}")
        return None
    
@quiz_bp.route('/help')
def help():
    return render_template('help.html')