from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import pymongo
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename

from flask import send_file
import gridfs



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

fs = gridfs.GridFS(db)

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
@login_required
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

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if request.method == 'POST':
        # Lógica existente para manejar el formulario de búsqueda
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
        # Lógica para manejar la solicitud GET desde "Popular Destinations"
        destination = request.args.get('destination')
        if destination:
            hotels = list(hotels_collection.find({'address.city': destination}))

            return render_template('booking.html', destination=destination, hotels=hotels)

    return redirect(url_for('home'))



@app.route('/hotel_info', methods=['GET', 'POST'])
@login_required
def hotel_info():
    if request.method == 'POST':
        hotel_name = request.form['hotel_name']
        hotel_price = float(request.form['hotel_price'])
        hotel_photos= request.form['hotel_photos']

        booking_details = session.get('booking_details', {})
        if not booking_details:
            flash('No booking details found. Please start your booking again.')
            return redirect(url_for('home'))

        check_in = datetime.strptime(booking_details['check_in'], '%Y-%m-%d')
        check_out = datetime.strptime(booking_details['check_out'], '%Y-%m-%d')
        num_nights = (check_out - check_in).days

        total_price = hotel_price * num_nights

        booking_details['hotel_name'] = hotel_name
        booking_details['hotel_price'] = total_price
        booking_details['hotel_photos']= hotel_photos
        session['booking_details'] = booking_details

        flash('Booking confirmed!')
        return redirect(url_for('confirmation'))

    booking_details = session.get('booking_details', {})
    if not booking_details:
        flash('No booking details found. Please start your booking again.')
        return redirect(url_for('home'))


    return render_template('hotel_info.html', booking_details=booking_details)


@app.route('/confirmation', methods=['GET', 'POST'])
@login_required
def confirmation():
    if request.method == 'POST':
        hotel_name = request.form['hotel_name']
        hotel_price = float(request.form['hotel_price'])
        hotel_photos= request.form['hotel_photos']

        booking_details = session.get('booking_details', {})
        if not booking_details:
            flash('No booking details found. Please start your booking again.')
            return redirect(url_for('home'))

        check_in = datetime.strptime(booking_details['check_in'], '%Y-%m-%d')
        check_out = datetime.strptime(booking_details['check_out'], '%Y-%m-%d')
        num_nights = (check_out - check_in).days

        total_price = hotel_price * num_nights

        booking_details['hotel_name'] = hotel_name
        booking_details['hotel_price'] = total_price
        booking_details['hotel_photos']= hotel_photos
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

    # Sample data for managers and cities
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
        lastName = request.form['lastname']
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
                'lastname': lastName,
                'email': email,
                'password_hash': generate_password_hash(password),
                'auth_level': 'manager_user'  # Asignar nivel de autorización de manager
            }
            users_collection.insert_one(user_data)
            flash('Manager added successfully', 'success')
            return redirect(url_for('super_listing'))
    
    return render_template('super_add_manager.html')

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
        street2 = request.form.get('street2', '')  # Campo opcional
        street3 = request.form.get('street3', '')  # Campo opcional
        postal_code = request.form['postal_code']
        city = request.form['city']
        country = request.form['country']
        description = request.form['description']
        extra_info = request.form.get('extra_info', '')  # Campo opcional
        no_of_guests = int(request.form['no_of_guests'])
        price_per_night = float(request.form['price_per_night'])
        
        photos = request.files.getlist('photos')
        photo_ids = []

        # Guardar fotos en MongoDB usando GridFS
        for photo in photos:
            if photo.filename == '':
                continue  # Ignorar archivos no seleccionados
            filename = secure_filename(photo.filename)
            file_id = fs.put(photo, filename=filename)
            photo_ids.append(file_id)

        # Crear el documento del hotel
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

        # Insertar el documento en la colección de hoteles
        db.hotels.insert_one(hotel_data)
        flash('Hotel added successfully!')
        return redirect(url_for('home'))

    return render_template('add_hotel.html')

@app.route('/hotels')
def hotels():
    all_hotels = db.hotels.find()
    hotels_list = []

    for hotel in all_hotels:
        # Convert ObjectId to string for JSON serialization
        hotel['_id'] = str(hotel['_id'])
        hotel['photos'] = [str(photo_id) for photo_id in hotel['photos']]
        hotels_list.append(hotel)

    return render_template('hotels_testing.html', hotels=hotels_list)



@app.route('/hotel_photo/<photo_id>')
def hotel_photo(photo_id):
    photo = fs.get(ObjectId(photo_id))
    return send_file(photo, mimetype='image/jpeg')

@app.route('/hotels_city', methods=['GET', 'POST'])
def hotels_city():
    city = request.form.get('city')
    query = {}  # Consulta vacía por defecto


    if city:
        query['address.city'] = city

    hotels = hotels_collection.find(query)
    return render_template('hotels_testing.html', hotels=hotels)



if __name__ == '__main__':
    app.run(debug=True)
