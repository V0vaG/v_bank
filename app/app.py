from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import json
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Configuration
app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Paths
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
        return redirect(url_for('admin_area' if user['kind'] == 'admin' else 'home'))

    flash("Invalid username or password.", "danger")
    return redirect(url_for('show_login'))

@app.route('/admin', methods=['GET'])
@login_required
def admin_area():
    with open(USERS_FILE, 'r') as f:
        users = json.load(f)

    return render_template('admin.html', user_data=users)

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

@app.route('/logout')
def logout():
    session.pop('active_user', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('show_login'))

if __name__ == '__main__':
    app.run(debug=True)
