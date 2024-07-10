from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import pymongo
from bson.objectid import ObjectId


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# Configuración de la conexión a MongoDB
client = pymongo.MongoClient('mongodb+srv://andresgb2013:DN0kJdOtj5eJmoo3@cluster0.jzfu1jp.mongodb.net/')
db = client['SD_Project']  # Reemplaza 'your_database_name' con el nombre de tu base de datos
users_collection = db['users']
hotels_collection = db['hotels']



class User(UserMixin):
    def __init__(self, user_id, name,lastname, email, password_hash, auth_level):
        self.id = user_id
        self.name = name
        self.lastname = lastname
        self.email = email
        self.password_hash = password_hash
        self.auth_level = auth_level

    @staticmethod
    def from_mongo(doc):
        return User(
            user_id=str(doc['_id']),
            name=doc['name'],
            lastname=doc['lastname'],
            email=doc['email'],
            password_hash=doc['password_hash'],
            auth_level=doc['auth_level']
        )


@login_manager.user_loader
def load_user(user_id):
    user_doc = users_collection.find_one({'_id': ObjectId(user_id)})
    if user_doc:
        return User.from_mongo(user_doc)
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user_doc = users_collection.find_one({'email': email})
        if user_doc and check_password_hash(user_doc['password_hash'], password):
            user = User.from_mongo(user_doc)
            login_user(user)
            
            if user.auth_level == 'super_user':
                return redirect(url_for('super_profile'))
            elif user.auth_level == 'manager_user':
                return redirect(url_for('manager_profile'))
            else:
                return redirect(url_for('home'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        lastName = request.form['lastname']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        existing_user = users_collection.find_one({'email': email})
        if existing_user:
            flash('Email address already registered', 'error')
                # Validar longitud mínima de contraseña
        elif len(password) < 8:
            flash('Password must be at least 8 characters long', 'error')
            return redirect(url_for('register'))
        elif password!= confirm_password:
            flash('Passwords do not match', 'error')
        else:
            user_data = {
                'name': name,
                'lastname': lastName,
                'email': email,
                'password_hash': generate_password_hash(password),
                'auth_level': 'regular'  # Valor predeterminado
            }
            users_collection.insert_one(user_data)
            flash('User registered successfully')
            return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/user_profile')
def user_profile():
    if session.get('authenticated'):
        return redirect(url_for('login'))
    return render_template('user_profile.html')

@app.route('/user_booking')
def user_booking():
    if session.get('authenticated'):
        return redirect(url_for('login'))
    return render_template('user_booking.html')

@app.route('/booking_cancel')
def booking_cancel():
    if session.get('authenticated'):
        return redirect(url_for('login'))
    return render_template('booking_cancel.html')

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/hotel_info/<hotel_name>', methods=['GET', 'POST'])
def hotel_info(hotel_name):
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    # Dummy data for example
    hotel = {
        'name': hotel_name,
        'city': 'Example City',
        'country': 'Example Country',
        'description': 'This is a beautiful hotel.',
        'price': 150,
        'distance_from_center': 2,
        'image1': 'path/to/room_image1.jpg',  # Update as necessary
        'image2': 'path/to/room_image2.jpg',  # Update as necessary
        'image3': 'path/to/room_image3.jpg'   # Update as necessary
    }
    return render_template('hotel_info.html', hotel=hotel)

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

@app.route('/manager_profile')
def manager_profile():
    return render_template('manager_profile.html')

@app.route('/manager_listing')
def manager_listing():
    return render_template('manager_listing.html')

@app.route('/manager_hotel_editing')
def manager_hotel_editing():
    return render_template('manager_hotel_editing.html')

@app.route('/super_profile')
def super_profile():
    return render_template('super_profile.html')

@app.route('/super_listing')
def super_listing():
    # Sample data for managers and cities
    managers = [{'name': 'John Doe', 'details': 'Manager of City A'}]
    cities = [{'name': 'City A', 'details': 'Details of City A'}]
    return render_template('super_listing.html', managers=managers, cities=cities)

@app.route('/super_add_city')
def super_add_city():
    return render_template('super_add_city.html')

@app.route('/super_add_manager')
def super_add_manager():
    return render_template('super_add_manager.html')



if __name__ == '__main__':
    app.run(debug=True)
