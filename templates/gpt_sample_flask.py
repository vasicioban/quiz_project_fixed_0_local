from flask import Flask, request, jsonify, g, session, redirect, url_for
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'

# Dummy data for users and roles
users = {
    "admin": {
        "password": generate_password_hash("admin_pass"),
        "role": "admin"
    },
    "user": {
        "password": generate_password_hash("user_pass"),
        "role": "user"
    }
}

# Authentication decorator
def authenticate(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'message': 'Authentication required!'}), 401
        user = users.get(session['username'])
        if not user:
            return jsonify({'message': 'Invalid credentials!'}), 401
        g.current_user = user
        return f(*args, **kwargs)
    return decorated

# Role-based access control decorator
def authorize(role):
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if g.current_user['role'] != role:
                return jsonify({'message': 'Permission denied!'}), 403
            return f(*args, **kwargs)
        return decorated
    return wrapper

@app.route('/login', methods=['POST'])
def login():
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return jsonify({'message': 'Missing credentials!'}), 400
    user = users.get(auth.username)
    if not user or not check_password_hash(user['password'], auth.password):
        return jsonify({'message': 'Invalid credentials!'}), 401
    session['username'] = auth.username
    return jsonify({'message': 'Login successful!'})

@app.route('/logout')
@authenticate
def logout():
    session.pop('username', None)
    return jsonify({'message': 'Logout successful!'})

@app.route('/public')
def public():
    return jsonify({'message': 'Anyone can view this!'})

@app.route('/user')
@authenticate
def user_route():
    return jsonify({'message': f'Hello, {session["username"]}! You are logged in as a user.'})

@app.route('/admin')
@authenticate
@authorize('admin')
def admin_route():
    return jsonify({'message': 'Welcome, admin!'})

if __name__ == '__main__':
    app.run(debug=True)