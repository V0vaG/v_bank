from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import socket
from functools import wraps
from funcs import *

# Configuration
app = Flask(__name__)
app.secret_key = 'supersecretkey'
version = os.getenv('B_NUM', '0.0.0')
host = socket.gethostname()

# Set up paths
alias = "topix"
HOME_DIR = os.path.expanduser("~")
FILES_PATH = os.path.join(HOME_DIR, "script_files", alias)
DATA_DIR = os.path.join(FILES_PATH, "data")
USERS_FILE = os.path.join(DATA_DIR, 'users.json')

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, 'w') as f:
        json.dump([], f)

@app.route('/register', methods=['GET', 'POST'])
def register():
    users_file = os.path.join(DATA_DIR, 'users.json')

    # Load existing users
    if os.path.exists(users_file):
        with open(users_file, 'r') as f:
            users = json.load(f)
    else:
        users = []

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        groups = request.form.get('groups').split(',')

        # If there are no users, make the first user an admin
        if len(users) == 0:
            role = 'admin'
        else:
            role = request.form.get('role') if 'role' in request.form else 'user'

        # Check if username already exists
        if any(user['username'] == username for user in users):
            flash(f"Username '{username}' already exists.", "danger")
            return redirect(url_for('register'))

        # Hash the password before saving it
        hashed_password = generate_password_hash(password)

        # Create new user object
        new_user = {
            'username': username,
            'password': hashed_password,
            'kind': role,  # Use the selected or auto-assigned role (user/admin)
            'groups': groups
        }

        # Save new user
        users.append(new_user)
        with open(users_file, 'w') as f:
            json.dump(users, f, indent=4)

        flash(f"User created successfully as {role}!", "success")
        return redirect(url_for('show_login'))

    # Check if accessed from admin area or login page
    show_role_selection = 'admin_area' in request.args  # Flag for role dropdown
    back_url = url_for('admin_area') if 'admin_area' in request.args else url_for('show_login')  # Determine where to go back to
    
    return render_template('register.html', show_role_selection=show_role_selection, back_url=back_url)


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    # Load users
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
    else:
        users = []

    # Find the user by username
    user = next((u for u in users if u['username'] == username), None)

    # Check if the user exists and password matches
    if user and check_password_hash(user['password'], password):
        session['active_user'] = username  # Store the username in the session
        flash("Login successful!", "success")
        return redirect(url_for('home'))

    flash("Invalid username or password.", "danger")
    return redirect(url_for('show_login'))

@app.route('/')
def show_login():
    # Load users from the JSON file
    users_file = os.path.join(DATA_DIR, 'users.json')
    if os.path.exists(users_file):
        with open(users_file, 'r') as f:
            users = json.load(f)
    else:
        users = []

    # Check if there are no users
    no_users_exist = len(users) == 0

    # Load the external registration setting
    config_file = os.path.join(DATA_DIR, 'config.json')
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {"allow_registration": False}

    allow_registration = config.get('allow_registration', False)

    return render_template('login.html', no_users_exist=no_users_exist, allow_registration=allow_registration)

@app.route('/logout')
def logout():
    session.pop('active_user', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('show_login'))

# Move this decorator definition to a standalone section of the code
def login_required(f):
    @wraps(f)  # This preserves the original function name and prevents overwriting issues
    def wrap(*args, **kwargs):
        if 'active_user' not in session:
            flash("You need to login first.", "danger")
            return redirect(url_for('show_login'))
        return f(*args, **kwargs)
    return wrap

@app.route('/index')
@login_required
def home():
    # Load the user information from the session
    username = session.get('active_user')
    
    # Load users to find the current user's role
    with open(USERS_FILE, 'r') as f:
        users = json.load(f)
    
    # Check if the current user is an admin
    user = next((u for u in users if u['username'] == username), None)
    is_admin = user and user['kind'] == 'admin'

    # Render the home page with the admin flag
    return render_template('index.html', version=version, host=host, is_admin=is_admin, user=username)

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_area():
    # Ensure the logged-in user is an admin
    username = session.get('active_user')

    with open(USERS_FILE, 'r') as f:
        users = json.load(f)

    user = next((u for u in users if u['username'] == username), None)
    if user and user['kind'] == 'admin':
        # Load the external registration setting
        config_file = os.path.join(DATA_DIR, 'config.json')
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
        else:
            config = {"allow_registration": False}

        allow_registration = config.get('allow_registration', False)

        # Count topics created by each user
        user_topics_count = {user['username']: 0 for user in users}

        for folder in os.listdir(DATA_DIR):
            folder_path = os.path.join(DATA_DIR, folder)
            if os.path.isdir(folder_path):
                json_file = os.path.join(folder_path, f"{folder}.json")
                if os.path.exists(json_file):
                    with open(json_file, 'r') as f:
                        topic_data = json.load(f)[0]
                        editor = topic_data.get('editor')
                        if editor in user_topics_count:
                            user_topics_count[editor] += 1

        # Create a list of user data with the topic counts
        user_data = [(user, user_topics_count.get(user['username'], 0)) for user in users]

        return render_template('admin.html', allow_registration=allow_registration, user_data=user_data)
    
    flash("You do not have access to the admin area.", "danger")
    return redirect(url_for('home'))

@app.route('/delete_user/<username>', methods=['POST'])
@login_required
def delete_user(username):
    # Ensure the logged-in user is an admin
    active_username = session.get('active_user')

    with open(USERS_FILE, 'r') as f:
        users = json.load(f)

    # Check if the current user is an admin
    active_user = next((u for u in users if u['username'] == active_username), None)
    if not active_user or active_user['kind'] != 'admin':
        flash("You do not have permission to perform this action.", "danger")
        return redirect(url_for('home'))

    # Prevent the admin from deleting themselves
    if active_username == username:
        flash("You cannot delete yourself.", "danger")
        return redirect(url_for('admin_area'))

    # Filter out the user to be deleted
    updated_users = [user for user in users if user['username'] != username]

    # Save the updated user list
    with open(USERS_FILE, 'w') as f:
        json.dump(updated_users, f, indent=4)

    flash(f"User '{username}' has been deleted.", "success")
    return redirect(url_for('admin_area'))

@app.route('/toggle_registration', methods=['POST'])
@login_required
def toggle_registration():
    # Ensure the logged-in user is an admin
    username = session.get('active_user')

    with open(USERS_FILE, 'r') as f:
        users = json.load(f)

    user = next((u for u in users if u['username'] == username), None)
    if user and user['kind'] == 'admin':
        allow_registration = 'allow_registration' in request.form

        # Update the config file
        config_file = os.path.join(DATA_DIR, 'config.json')
        config = {'allow_registration': allow_registration}
        with open(config_file, 'w') as f:
            json.dump(config, f)

        flash("Settings updated successfully.", "success")
        return redirect(url_for('admin_area'))

    flash("You do not have permission to perform this action.", "danger")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)