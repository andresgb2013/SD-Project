from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, name, email, password):
        self.id = id
        self.name = name
        self.email = email
        self.password = password

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
            return redirect(request.args.get('next') or url_for('home'))
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
    referrer = request.referrer or url_for('home')
    return redirect(referrer)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if request.method == 'POST':
        destination = request.form['destination']
        check_in = request.form['check_in']
        check_out = request.form['check_out']
        guests = request.form['guests']
        rooms = request.form['rooms']
        hotel_name = request.form.get('hotel_name')

        session['booking_details'] = {
            'destination': destination,
            'check_in': check_in,
            'check_out': check_out,
            'guests': guests,
            'rooms': rooms,
            'hotel_name': hotel_name
        }

        print("Booking details saved in session:", session['booking_details'])

        if hotel_name:
            return redirect(url_for('confirmation'))

    booking_details = session.get('booking_details', {})
    print("Booking details retrieved from session:", booking_details)

    hotels_by_city = {
        'Berlin': [
            {'name': 'Hotel Berlin', 'price': '100', 'image': url_for('static', filename='images/hotel1.jpg')},
            {'name': 'Berlin Hilton', 'price': '150', 'image': url_for('static', filename='images/hotel2.jpg')},
            {'name': 'Berlin Marriott', 'price': '200', 'image': url_for('static', filename='images/hotel3.jpg')}
        ],
        'Munich': [
            {'name': 'Munich International', 'price': '120', 'image': url_for('static', filename='images/hotel1.jpg')},
            {'name': 'Munich Hilton', 'price': '170', 'image': url_for('static', filename='images/hotel2.jpg')},
            {'name': 'Munich Marriott', 'price': '220', 'image': url_for('static', filename='images/hotel3.jpg')}
        ],
        'Hamburg': [
            {'name': 'Hamburg Inn', 'price': '90', 'image': url_for('static', filename='images/hotel1.jpg')},
            {'name': 'Hamburg Hilton', 'price': '140', 'image': url_for('static', filename='images/hotel2.jpg')},
            {'name': 'Hamburg Marriott', 'price': '190', 'image': url_for('static', filename='images/hotel3.jpg')}
        ]
    }

    destination = booking_details.get('destination')
    hotels = hotels_by_city.get(destination, [])

    return render_template('booking.html', booking_details=booking_details, hotels=hotels)


@app.route('/confirmation', methods=['GET', 'POST'])
@login_required
def confirmation():
    if request.method == 'POST':
        hotel_name = request.form['hotel_name']
        hotel_price = int(request.form['hotel_price'])

        booking_details = session.get('booking_details', {})
        check_in = datetime.strptime(booking_details['check_in'], '%Y-%m-%d')
        check_out = datetime.strptime(booking_details['check_out'], '%Y-%m-%d')
        num_nights = (check_out - check_in).days

        total_price = hotel_price * num_nights

        booking_details['hotel_name'] = hotel_name
        booking_details['hotel_price'] = total_price
        session['booking_details'] = booking_details

        flash('Booking confirmed!')
        return redirect(url_for('confirmation'))

    booking_details = session.get('booking_details', {})
    if not booking_details:
        flash('No booking details found. Please start your booking again.')
        return redirect(url_for('home'))

    return render_template('confirmation.html', booking_details=booking_details)


@app.route('/confirm_booking', methods=['POST'])
@login_required
def confirm_booking():
    if request.method == 'POST':
        session['booking_confirmed'] = True
        return redirect(url_for('confirmation'))

    flash('Failed to confirm booking.')
    return redirect(url_for('confirmation'))


if __name__ == '__main__':
    app.run(debug=True)
