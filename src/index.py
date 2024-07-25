from flask import Flask, render_template, redirect, url_for, request, flash, session, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import pymongo
from bson.objectid import ObjectId
import gridfs



app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')

# Configuración de Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configuración de la conexión a MongoDB
client = pymongo.MongoClient('mongodb+srv://andresgb2013:DN0kJdOtj5eJmoo3@cluster0.jzfu1jp.mongodb.net/')
db = client['SD_Project']
users_collection = db['users']
hotels_collection = db['hotels']
reservations_collection = db['reservations']
fs = gridfs.GridFS(db)


class User(UserMixin):
    def __init__(self, user_id, name, lastname, email, password_hash, auth_level):
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
        lastname = request.form['lastname']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        existing_user = users_collection.find_one({'email': email})
        if existing_user:
            flash('Email address already registered', 'error')
        elif len(password) < 8:
            flash('Password must be at least 8 characters long', 'error')
        elif password != confirm_password:
            flash('Passwords do not match', 'error')
        else:
            user_data = {
                'name': name,
                'lastname': lastname,
                'email': email,
                'password_hash': generate_password_hash(password),
                'auth_level': 'regular'
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

#Rutas de la Aplicación
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/user_profile')
@login_required
def user_profile():
    user_id = current_user.get_id()
    reservations = list(reservations_collection.find({'user_id': user_id}))

    return render_template('user_profile.html', reservations=reservations)

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


@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if request.method == 'POST':
        destination = request.form['destination']
        check_in = request.form['check_in']
        check_out = request.form['check_out']
        guests = request.form['guests']
        rooms = request.form['rooms']

        booking_details = {
            'destination': destination,
            'check_in': check_in,
            'check_out': check_out,
            'guests': guests,
            'rooms': rooms
        }

        session['booking_details'] = booking_details
        hotels = list(hotels_collection.find({'address.city': destination}))
        return render_template('booking.html', booking_details=booking_details, hotels=hotels)

    elif request.method == 'GET':
        destination = request.args.get('destination')
        if destination:
            check_in = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
            check_out = (datetime.utcnow() + timedelta(days=2)).strftime('%Y-%m-%d')
            booking_details = {
                'destination': destination,
                'check_in': check_in,
                'check_out': check_out,
                'guests': 1,
                'rooms': 1
            }
            session['booking_details'] = booking_details
            hotels = list(hotels_collection.find({'address.city': destination}))
            return render_template('hotels_testing.html', destination=destination, hotels=hotels, booking_details=booking_details)

    return redirect(url_for('home'))


@app.route('/hotel_info', methods=['GET', 'POST'])
def hotel_info():
    if request.method == 'POST':
        try:
            hotel_id = request.form.get('hotel_id')
            if not hotel_id:
                raise ValueError('No hotel_id provided')
            hotel_object_id = ObjectId(hotel_id)
        except (ValueError, Exception) as e:
            flash('Invalid hotel ID format. Please start your booking again.')
            return redirect(url_for('home'))

        hotel_name = request.form['hotel_name']
        hotel_price = float(request.form['hotel_price'])
        hotel_photos = request.form.getlist('hotel_photos')

        # Update booking details from the form
        check_in = request.form.get('check_in')
        check_out = request.form.get('check_out')
        guests = request.form.get('guests')
        rooms = request.form.get('rooms')

        booking_details = {
            'destination': session['booking_details'].get('destination', ''),
            'check_in': check_in,
            'check_out': check_out,
            'guests': guests,
            'rooms': rooms,
            'hotel_name': hotel_name,
            'hotel_price': hotel_price,
            'hotel_photos': hotel_photos
        }

        # Calculate the total price
        check_in_date = datetime.strptime(check_in, '%Y-%m-%d')
        check_out_date = datetime.strptime(check_out, '%Y-%m-%d')
        num_nights = (check_out_date - check_in_date).days
        booking_details['hotel_price'] = hotel_price * num_nights

        # Save updated booking details to the session
        session['booking_details'] = booking_details

        flash('Booking details updated successfully!')
        return render_template('hotel_info.html', hotel=hotels_collection.find_one({'_id': hotel_object_id}), booking_details=booking_details)

    try:
        hotel_id = request.args.get('hotel_id')
        if not hotel_id:
            raise ValueError('No hotel_id provided')
        hotel_object_id = ObjectId(hotel_id)
    except (ValueError, Exception) as e:
        flash('Invalid hotel ID format. Please start your booking again.')
        return redirect(url_for('home'))

    hotel = hotels_collection.find_one({'_id': hotel_object_id})
    if not hotel:
        flash('Hotel not found. Please start your booking again.')
        return redirect(url_for('home'))

    booking_details = session.get('booking_details', {})
    if not booking_details:
        flash('No booking details found. Please start your booking again.')
        return redirect(url_for('home'))

    return render_template('hotel_info.html', hotel=hotel, booking_details=booking_details)



@app.route('/confirmation')
def confirmation():
    booking_details = session.get('booking_details', {})
    if not booking_details:
        flash('No booking details found. Please start your booking again.')
        return redirect(url_for('home'))

    return render_template('confirmation.html', booking_details=booking_details)

@app.route('/confirm_booking', methods=['POST'])
def confirm_booking():
    booking_details = session.get('booking_details', {})
    if not booking_details:
        flash('No booking details found. Please start your booking again.')
        return redirect(url_for('home'))

    user_id = current_user.get_id()

    reservation = {
        'user_id': user_id,
        'hotel_name': booking_details['hotel_name'],
        'check_in': booking_details['check_in'],
        'check_out': booking_details['check_out'],
        'guests': booking_details['guests'],
        'rooms': booking_details['rooms'],
        'total_price': booking_details['hotel_price'],
        'hotel_photos': booking_details['hotel_photos'],
        'created_at': datetime.now()
    }

    reservations_collection.insert_one(reservation)
    flash('Booking confirmed!')

    return redirect(url_for('user_profile'))

#Rutas de Gestión de Usuarios
@app.route('/manager_profile')
def manager_profile():
    return render_template('manager_profile.html')

@app.route('/manager_listing')
def manager_listing():
    return render_template('manager_listing.html')

@app.route('/manager_hotel_editing')
@login_required
def manager_hotel_editing():
    if current_user.auth_level != 'manager_user':
        flash("Access Denied: You don't have the necessary permissions.", 'danger')
        return redirect(url_for('login'))

    return render_template('manager_hotel_editing.html')

@app.route('/super_profile')
@login_required
def super_profile():
    if current_user.auth_level != 'super_user':
        flash("Access Denied: You don't have the necessary permissions.", 'danger')
        return redirect(url_for('login'))

    return render_template('super_profile.html')

@app.route('/super_listing')
@login_required
def super_listing():
    if current_user.auth_level != 'super_user':
        flash("Access Denied: You don't have the necessary permissions.", 'danger')
        return redirect(url_for('login'))

    managers = [{'name': 'John Doe', 'details': 'Manager of City A'}]
    cities = [{'name': 'City A', 'details': 'Details of City A'}]
    return render_template('super_listing.html', managers=managers, cities=cities)

@app.route('/super_add_city')
@login_required
def super_add_city():
    if current_user.auth_level != 'super_user':
        flash("Access Denied: You don't have the necessary permissions.", 'danger')
        return redirect(url_for('home'))

    return render_template('super_add_city.html')

@app.route('/super_add_manager', methods=['GET', 'POST'])
@login_required
def super_add_manager():
    if current_user.auth_level != 'super_user':
        flash("Access Denied: You don't have the necessary permissions.", 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        lastname = request.form['lastname']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        existing_user = users_collection.find_one({'email': email})
        if existing_user:
            flash('Email address already registered', 'error')
        elif len(password) < 8:
            flash('Password must be at least 8 characters long', 'error')
        elif password != confirm_password:
            flash('Passwords do not match', 'error')
        else:
            user_data = {
                'name': name,
                'lastname': lastname,
                'email': email,
                'password_hash': generate_password_hash(password),
                'auth_level': 'manager_user'
            }
            users_collection.insert_one(user_data)
            flash('Manager added successfully', 'success')
            return redirect(url_for('super_listing'))
    
    return render_template('super_add_manager.html')

# Rutas de Gestión de Hoteles
@app.route('/create_hotel', methods=['GET', 'POST'])
@login_required
def create_hotel():
    if current_user.auth_level != 'manager_user':
        flash("Access Denied: You don't have the necessary permissions.", 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        title = request.form['title']
        street1 = request.form['street1']
        street2 = request.form['street2']
        street3 = request.form['street3']
        postal_code = request.form['postal_code']
        city = request.form['city']
        country = request.form['country']
        description = request.form['description']
        extra_info = request.form['extra_info']
        no_of_guests = int(request.form['no_of_guests'])
        price_per_night = float(request.form['price_per_night'])

        photos = request.files.getlist('photos')
        photo_urls = []
        for photo in photos:
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['uploads'], filename))
            photo_urls.append(filename)

        hotel_data = {
            'title': title,
            'address': {
                'street1': street1,
                'street2': street2,
                'street3': street3,
                'postal_code': postal_code,
                'city': city,
                'country': country
            },
            'description': description,
            'extra_info': extra_info,
            'no_of_guests': no_of_guests,
            'price_per_night': price_per_night,
            'photos': photo_urls
        }

        hotels_collection.insert_one(hotel_data)
        flash('Hotel created successfully!')
        return redirect(url_for('manager_listing'))

    return render_template('create_hotel.html')

@app.route('/add_hotel', methods=['GET', 'POST'])
def add_hotel():
    if request.method == 'POST':
        title = request.form['title']
        street1 = request.form['street1']
        street2 = request.form.get('street2', '')
        street3 = request.form.get('street3', '')
        postal_code = request.form['postal_code']
        city = request.form['city']
        country = request.form['country']
        description = request.form['description']
        extra_info = request.form.get('extra_info', '')
        no_of_guests = int(request.form['no_of_guests'])
        price_per_night = float(request.form['price_per_night'])
        
        photos = request.files.getlist('photos')
        photo_ids = []

        for photo in photos:
            if photo.filename == '':
                continue
            filename = secure_filename(photo.filename)
            file_id = fs.put(photo, filename=filename)
            photo_ids.append(file_id)

        hotel_data = {
            'title': title,
            'address': {
                'street1': street1,
                'street2': street2,
                'street3': street3,
                'postal_code': postal_code,
                'city': city,
                'country': country
            },
            'photos': photo_ids,
            'description': description,
            'extra_info': extra_info,
            'no_of_guests': no_of_guests,
            'price_per_night': price_per_night
        }

        db.hotels.insert_one(hotel_data)
        flash('Hotel added successfully!')
        return redirect(url_for('home'))

    return render_template('add_hotel.html')

@app.route('/hotels')
def hotels():
    all_hotels = db.hotels.find()
    hotels_list = []

    for hotel in all_hotels:
        hotel['_id'] = str(hotel['_id'])
        hotel['photos'] = [str(photo_id) for photo_id in hotel['photos']]
        hotels_list.append(hotel)

    return render_template('hotels_testing.html', hotels=hotels_list)

@app.route('/hotel_photo/<photo_id>')
def hotel_photo(photo_id):
    photo = fs.get(ObjectId(photo_id))
    return send_file(photo, mimetype='image/jpeg')


#Ejecución de la Aplicación
if __name__ == '__main__':
    app.run(debug=True)

