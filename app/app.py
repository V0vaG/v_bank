from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import json
import threading
import time
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import schedule
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Flask app configuration
app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Paths
alias = "topix"
HOME_DIR = os.path.expanduser("~")
FILES_PATH = os.path.join(HOME_DIR, "script_files", alias)
DATA_DIR = os.path.join(FILES_PATH, "data")
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')

# Scheduler flag (persistent)
scheduler_started = False

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, 'w') as f:
        json.dump([], f)

# Ensure configuration file exists
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"schedule_task_time": "00:00"}, f, indent=4)

# Load configuration from the JSON file
def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

# Save configuration to the JSON file
def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def start_scheduler():
    global scheduler_started
    # Ensure the scheduler starts only in the main process
    if not scheduler_started and os.getenv('WERKZEUG_RUN_MAIN') == 'true':
        scheduler_started = True
        scheduler_thread = threading.Thread(target=schedule_task, daemon=True)
        scheduler_thread.start()

# Function to handle scheduling
def schedule_task():
    config = load_config()
    schedule_time = config.get("schedule_task_time", "00:00")  # Default to 00:00 if not set

    logging.info(f"Scheduling task at: {schedule_time}")
    schedule.clear()  # Clear existing jobs to avoid duplication
    schedule.every().day.at(schedule_time).do(update_all_balances)

    # Log scheduled jobs
    for job in schedule.jobs:
        logging.info(f"Scheduled job: {job}")

    while True:
        schedule.run_pending()
        time.sleep(1)

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('active_user', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('show_login'))

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
    else:
        users = []

    user = next((u for u in users if u['username'] == username), None)
    if user and check_password_hash(user['password'], password):
        session['active_user'] = username
        
        if user['kind'] == 'admin':
            flash("Login successful! Welcome, Admin.", "success")
            return redirect(url_for('admin_area'))
        
        flash("Login successful!", "success")
        return redirect(url_for('user_info'))

    flash("Invalid username or password.", "danger")
    return redirect(url_for('show_login'))


# Decorator for login-required routes
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'active_user' not in session:
            flash("You need to login first.", "danger")
            return redirect(url_for('show_login'))
        return f(*args, **kwargs)
    return wrap

@app.route('/')
def show_login():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
    else:
        users = []

    no_users_exist = len(users) == 0
    return render_template('login.html', no_users_exist=no_users_exist)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
    else:
        users = []

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        name = request.form.get('name')
        balance = float(request.form.get('balance', 0))
        weekly_pay = float(request.form.get('weekly_pay', 0))
        overdraft = float(request.form.get('overdraft', 0))
        interest = float(request.form.get('interest', 0))
        role = 'admin' if len(users) == 0 else request.form.get('role', 'user')

        if any(user['username'] == username for user in users):
            flash("Username already exists.", "danger")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = {
            'username': username,
            'password': hashed_password,
            'name': name,
            'balance': balance,
            'weekly_pay': weekly_pay,
            'overdraft': overdraft,
            'interest': interest,
            'kind': role
        }

        users.append(new_user)
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)

        flash("Registration successful!", "success")
        return redirect(url_for('show_login'))

    return render_template('register.html')

@app.route('/update_schedule_time', methods=['POST'])
@login_required
def update_schedule_time():
    new_time = request.form.get('schedule_task_time', "00:00")
    try:
        # Validate the time format (HH:MM)
        datetime.strptime(new_time, "%H:%M")
    except ValueError:
        flash("Invalid time format. Please use HH:MM.", "danger")
        return redirect(url_for('admin_area'))

    # Update the schedule_task_time in config.json
    config = load_config()
    config['schedule_task_time'] = new_time
    save_config(config)

    flash(f"Schedule time updated to {new_time}.", "success")
    return redirect(url_for('admin_area'))

@app.route('/admin', methods=['GET'])
@login_required
def admin_area():
    with open(USERS_FILE, 'r') as f:
        users = json.load(f)

    # Load the current schedule_task_time from config.json
    config = load_config()
    schedule_task_time = config.get("schedule_task_time", "00:00")

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template(
        'admin.html', 
        user_data=users, 
        current_time=current_time, 
        schedule_task_time=schedule_task_time
    )

@app.route('/edit_user/<username>', methods=['GET', 'POST'])
@login_required
def edit_user(username):
    with open(USERS_FILE, 'r') as f:
        users = json.load(f)

    user_to_edit = next((u for u in users if u['username'] == username), None)
    if not user_to_edit:
        flash("User not found.", "danger")
        return redirect(url_for('admin_area'))

    if request.method == 'POST':
        user_to_edit['name'] = request.form.get('name')
        user_to_edit['balance'] = float(request.form.get('balance', 0))
        user_to_edit['weekly_pay'] = float(request.form.get('weekly_pay', 0))
        user_to_edit['overdraft'] = float(request.form.get('overdraft', 0))
        user_to_edit['interest'] = float(request.form.get('interest', 0))
        user_to_edit['kind'] = request.form.get('role', 'user')

        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)

        flash("User updated successfully.", "success")
        return redirect(url_for('admin_area'))

    return render_template('edit_user.html', user=user_to_edit)

# Function to update all balances by interest
def update_all_balances():
    with open(USERS_FILE, 'r') as f:
        users = json.load(f)

    for user in users:
        if 'balance' in user and 'interest' in user:
            user['balance'] += user['balance'] * (user['interest'] / 100)
            logging.info(f"Updated user: {user['username']} with new balance: {user['balance']}")
        else:
            logging.warning(f"Skipping user {user.get('username', 'unknown')} due to missing 'balance' or 'interest' key.")

    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

    logging.info("Balances updated by interest.")

if __name__ == '__main__':
    start_scheduler()
    app.run(debug=True)
