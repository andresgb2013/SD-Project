from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Example user class
class User(UserMixin):
    def __init__(self, id, name, email, password):
        self.id = id
        self.name = name
        self.email = email
        self.password = password

# Example users dictionary
users = {
    '1': User('1', 'Alice', 'alice@example.com', generate_password_hash('password')),
    '2': User('2', 'Bob', 'bob@example.com', generate_password_hash('password'))
}

@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        remember = 'remember' in request.form

        user = next((u for u in users.values() if u.email == email), None)
        if user and check_password_hash(user.password, password):
            login_user(user, remember=remember)
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        if next((u for u in users.values() if u.email == email), None):
            flash('Email address already registered')
        else:
            user_id = str(len(users) + 1)
            new_user = User(user_id, name, email, generate_password_hash(password))
            users[user_id] = new_user
            login_user(new_user)
            return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/')
def home():
    return render_template('home.html')

if __name__ == "__main__":
    app.run(debug=True)

