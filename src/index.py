from flask import Flask, render_template, redirect, url_for, request, flash, session, send_file, make_response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import pymongo
from bson.objectid import ObjectId
import gridfs
from middleware import LastURLMiddleware






app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')
app.wsgi_app = LastURLMiddleware(app.wsgi_app)
# Configuración de Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
app.config['images'] = 'static/images'

# Configuración de la conexión a MongoDB
client = pymongo.MongoClient('mongodb+srv://andresgb2013:DN0kJdOtj5eJmoo3@cluster0.jzfu1jp.mongodb.net/')
db = client['SD_Project']
users_collection = db['users']
hotels_collection = db['hotels']
reservations_collection = db['reservations']
cities_collection = db['cities']

fs = gridfs.GridFS(db)


from functools import wraps
from flask import abort



def role_required(role):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            if current_user.auth_level != role:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403


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

            # Recuperar la última URL visitada
            last_url = request.cookies.get('last_url')

            if last_url:
                response = make_response(redirect(last_url))
                response.delete_cookie('last_url')
                return response
            else:
                # Redireccionar a la página de inicio según el nivel de autenticación
                if user.auth_level == 'super_user':
                    return redirect(url_for('super_profile'))
                elif user.auth_level == 'manager_user':
                    return redirect(url_for('manager_profile'))
                else:
                    return redirect(url_for('home'))
        else:
            flash('Invalid email or password', 'error')

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

@app.route('/', methods=['GET'])
def home():
    cities = list(cities_collection.find())
    return render_template('home.html', cities=cities)


@app.route('/user_profile', methods=['GET', 'POST'])
@login_required
@role_required('regular')
def user_profile():
    user_id = current_user.get_id()
    user_data = db.users.find_one({"_id": ObjectId(user_id)})
    reservations = list(db.reservations.find({'user_id': user_id}))

    if request.method == 'POST':
        if 'update_profile' in request.form:
            name = request.form.get('name')
            lastname = request.form.get('lastname')
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')

            if check_password_hash(user_data['password_hash'], current_password):
                update_data = {
                    "name": name,
                    "lastname": lastname,
                }

                if new_password:
                    update_data["password_hash"] = generate_password_hash(new_password)

                db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
                flash("Profile updated successfully!")
                return redirect(url_for('user_profile'))
            else:
                flash("Current password is incorrect. Please try again.")

        elif 'cancel_booking' in request.form:
            reservation_id = request.form.get('reservation_id')
            
            # Obtener detalles de la reserva
            reservation = db.reservations.find_one({"_id": ObjectId(reservation_id)})
            if reservation:
                hotel_id = reservation['hotel_id']
                guests_to_release = reservation['guests']
                
                # Eliminar la reserva
                db.reservations.delete_one({"_id": ObjectId(reservation_id)})
                
                # Actualizar la disponibilidad de huéspedes en el hotel
                db.hotels.update_one(
                    {"_id": ObjectId(hotel_id)},
                    {"$inc": {"no_of_guests": guests_to_release}}
                )
                
                flash("Booking cancelled successfully!")
                reservations = list(db.reservations.find({'user_id': user_id}))
    
    return render_template('user_profile.html', user_data=user_data, reservations=reservations)


from flask import session, redirect, url_for, request, render_template
from datetime import datetime, timedelta

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    cities = list(cities_collection.find())  # Recuperamos las ciudades desde la BD.

    if request.method == 'POST':
        # Datos enviados desde el formulario
        destination = request.form['destination']
        check_in = request.form['check_in']
        check_out = request.form['check_out']
        guests = int(request.form['guests'])  # Asegurarse de que sea un entero
        
        # Guardamos los detalles en la sesión
        booking_details = {
            'destination': destination,
            'check_in': check_in,
            'check_out': check_out,
            'guests': guests
        }
        session['booking_details'] = booking_details

        # Redirigimos inmediatamente a una URL sin POST
        return redirect(url_for('booking'))

    elif request.method == 'GET':
        destination = request.args.get('destination')
        if destination:
            check_in = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
            check_out = (datetime.utcnow() + timedelta(days=2)).strftime('%Y-%m-%d')
            booking_details = {
                'destination': destination,
                'check_in': check_in,
                'check_out': check_out,
                'guests': 1  # Default
            }
            session['booking_details'] = booking_details

            hotels = list(hotels_collection.find({
                'address.city': destination,
                'no_of_guests': {'$gte': 1}  # Filtro por número de huéspedes
            }))
            return render_template('hotels_testing.html', destination=destination, hotels=hotels, booking_details=booking_details, cities=cities)

        # Manejamos el GET normal mostrando la información en la página booking.html
        booking_details = session.get('booking_details')
        if booking_details:
            hotels = list(hotels_collection.find({
                'address.city': booking_details['destination'],
                'no_of_guests': {'$gte': booking_details['guests']}  # Filtro por número de huéspedes
            }))
        else:
            hotels = []
        
        return render_template('booking.html', booking_details=booking_details, hotels=hotels, cities=cities)

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

        # Detalles del hotel y la reserva
        hotel_name = request.form['hotel_name']
        hotel_price = float(request.form['hotel_price'])
        hotel_photos = request.form.getlist('hotel_photos')

        # Actualizar detalles de la reserva
        check_in = request.form.get('check_in')
        check_out = request.form.get('check_out')
        guests = int(request.form.get('guests', 1))
        #rooms = int(request.form.get('rooms', 1))

        # Guardar los detalles de la reserva en la sesión
        booking_details = {
            'destination': session['booking_details'].get('destination', ''),
            'check_in': check_in,
            'check_out': check_out,
            'guests': guests,
            'hotel_id': hotel_id,
            'hotel_name': hotel_name,
            'hotel_price': hotel_price,
            'hotel_photos': hotel_photos,
            'total_price': hotel_price * (datetime.strptime(check_out, '%Y-%m-%d') - datetime.strptime(check_in, '%Y-%m-%d')).days * guests
        }
        session['booking_details'] = booking_details

        # Renderizar la página con la información del hotel y los detalles actualizados.
        hotel = hotels_collection.find_one({'_id': hotel_object_id})
        return render_template('hotel_info.html', hotel=hotel, booking_details=booking_details)

    # Método GET: mostrar detalles del hotel seleccionado.
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
@login_required
@role_required('regular')

def confirmation():
    booking_details = session.get('booking_details', {})
    if not booking_details:
        flash('No booking details found. Please start your booking again.')
        return redirect(url_for('home'))

    hotel_id = booking_details.get('hotel_name')
    if not hotel_id:
        flash('No hotel ID found in booking details. Please start your booking again.')
        return redirect(url_for('home'))

    try:
        hotel_name = hotel_id
    except (ValueError, Exception) as e:
        flash('Invalid hotel ID format. Please start your booking again.')
        return redirect(url_for('home'))

    hotel = hotels_collection.find_one({'title': hotel_name})
    if not hotel:
        flash('Hotel not found. Please start your booking again.')
        return redirect(url_for('home'))

    return render_template('confirmation.html', booking_details=booking_details, hotel=hotel)


@app.route('/confirm_booking', methods=['POST'])
@login_required
@role_required('regular')
def confirm_booking():
    booking_details = session.get('booking_details', {})
    if not booking_details:
        flash('No booking details found. Please start your booking again.')
        return redirect(url_for('login'))

    user_id = current_user.get_id()
    
    # Obtén los datos de pago desde el formulario
    payment_method = request.form.get('payment_method')
    card_number = request.form.get('card_number')
    expiration_date = request.form.get('expiration_date')
    cvv = request.form.get('cvv')

    # Construye el diccionario de reserva
    reservation = {
        'user_id': user_id,
        'hotel_name': booking_details['hotel_name'],
        'check_in': booking_details['check_in'],
        'check_out': booking_details['check_out'],
        'guests': booking_details['guests'],
        'hotel_id': booking_details['hotel_id'],
        'total_price': booking_details['total_price'],
        'hotel_photos': booking_details['hotel_photos'],
        'payment_method': payment_method,
        'created_at': datetime.now()
    }

    # Agrega la información de la tarjeta solo si no es "Cash"
    if payment_method != 'Cash':
        reservation.update({
            'card_number': card_number,
            'expiration_date': expiration_date,
            'cvv': cvv
        })

    reservations_collection.insert_one(reservation)

    # Reducción de la cantidad de huéspedes en el hotel
    hotel_title = booking_details['hotel_name']
    guests = booking_details['guests']
    hotels_collection.update_one(
        {'title': hotel_title},
        {'$inc': {'no_of_guests': -guests}}
    )

    flash('Booking confirmed!')
    return redirect(url_for('user_profile'))




#Rutas de Gestión de Usuarios
@app.route('/manager_profile', methods=['GET', 'POST'])
@login_required
@role_required('manager_user')
def manager_profile():
    user_id = current_user.get_id()
    user_data = db.users.find_one({"_id": ObjectId(user_id)})
    
    if request.method == 'POST':
        if 'update_profile' in request.form:
            name = request.form.get('name')
            lastname = request.form.get('lastname')
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')

            if not check_password_hash(user_data['password_hash'], current_password):
                flash('Current password is incorrect!')
                return redirect(url_for('manager_profile'))

            update_data = {
                "name": name,
                "lastname": lastname,
            }
            if new_password:
                update_data["password_hash"] = generate_password_hash(new_password)

            db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
            flash("Profile updated successfully!")
            return redirect(url_for('manager_profile'))

    return render_template('manager_profile.html', user_data=user_data)


@app.route('/manager_listing')
@login_required
@role_required('manager_user')
def manager_listing():
    hotels = db.hotels.find()
    hotels_by_city = {}
    for hotel in hotels:
        city = hotel['address']['city']
        if city not in hotels_by_city:
            hotels_by_city[city] = []
        hotels_by_city[city].append(hotel)
    return render_template('manager_listing.html', hotels_by_city=hotels_by_city)


@app.route('/manager_hotel_editing/<hotel_id>', methods=['GET', 'POST'])
@login_required
@role_required('manager_user')
def manager_hotel_editing(hotel_id):
    hotel = db.hotels.find_one({"_id": ObjectId(hotel_id)})
    cities = list(db.cities.find())

    if request.method == 'POST':
        title = request.form['title']
        street1 = request.form['street1']
        street2 = request.form.get('street2', '')
        street3 = request.form.get('street3', '')
        postal_code = request.form['postal_code']
        
        city_id = request.form['city']  # Capturamos el ID de la ciudad
        city = next((city['name'] for city in cities if str(city['_id']) == city_id), None)  # Buscamos el nombre basado en el ID

        country = request.form['country']
        description = request.form['description']
        extra_info = request.form.get('extra_info', '')
        no_of_guests = int(request.form['no_of_guests'])
        price_per_night = float(request.form['price_per_night'])
        
        update_data = {
            'title': title,
            'address': {
                'street1': street1,
                'street2': street2,
                'street3': street3,
                'postal_code': postal_code,
                'city_id': city_id,  # Guardamos el ID de la ciudad
                'city': city,  # Guardamos el nombre de la ciudad
                'country': country
            },
            'description': description,
            'extra_info': extra_info,
            'no_of_guests': no_of_guests,
            'price_per_night': price_per_night
        }

        # Eliminar fotos seleccionadas
        if 'delete_photo' in request.form:
            photo_id_to_delete = request.form['delete_photo']
            db.hotels.update_one({"_id": ObjectId(hotel_id)}, {"$pull": {"photos": ObjectId(photo_id_to_delete)}})
            fs.delete(ObjectId(photo_id_to_delete))
            flash('Photo deleted successfully!')
            return redirect(url_for('manager_hotel_editing', hotel_id=hotel_id))

        # Manejo de nuevas fotos
        photos = request.files.getlist('photos')
        photo_ids = []
        
        if photos:
            for photo in photos:
                if photo.filename == '':
                    continue
                filename = secure_filename(photo.filename)
                file_id = fs.put(photo, filename=filename)
                photo_ids.append(file_id)
        
        if photo_ids:
            db.hotels.update_one({"_id": ObjectId(hotel_id)}, {"$push": {"photos": {"$each": photo_ids}}})
        
        db.hotels.update_one({"_id": ObjectId(hotel_id)}, {"$set": update_data})
        flash('Hotel updated successfully!')
        return redirect(url_for('manager_listing'))

    return render_template('hotel_editing.html', hotel=hotel, cities=cities)



@app.route('/delete_hotel/<hotel_id>', methods=['POST'])
@login_required
@role_required('manager_user')
def delete_hotel(hotel_id):
    try:
        # Eliminar todas las reservas asociadas al hotel
        db.reservations.delete_many({"hotel_id": hotel_id})

        # Eliminar el hotel
        db.hotels.delete_one({"_id": ObjectId(hotel_id)})

        flash('Hotel and associated reservations deleted successfully!')

    except Exception as e:
        # Manejar excepciones y proporcionar retroalimentación
        flash(f'An error occurred: {e}')

    return redirect(url_for('manager_listing'))

@app.route('/manager_bookings')
@login_required
@role_required('manager_user')
def manager_bookings():
    # Obtener todas las reservas
    reservations = list(db.reservations.find())

    # Obtener todos los user_ids de las reservas y convertirlos a ObjectId
    user_ids = {ObjectId(reservation['user_id']) for reservation in reservations}

    # Obtener información de los usuarios
    users = {str(user['_id']): user for user in db.users.find({"_id": {"$in": list(user_ids)}})}

    return render_template('manager_bookings.html', reservations=reservations, users=users)


@app.route('/edit_reservation/<reservation_id>', methods=['GET', 'POST'])
@login_required
@role_required('manager_user')
def edit_reservation(reservation_id):
    reservation = db.reservations.find_one({"_id": ObjectId(reservation_id)})

    if request.method == 'POST':
        check_in = request.form['check_in']
        check_out = request.form['check_out']
        guests = int(request.form['guests'])
        #rooms = int(request.form['rooms'])
        total_price = float(request.form['total_price'])
        
        db.reservations.update_one(
            {"_id": ObjectId(reservation_id)},
            {"$set": {
                "check_in": check_in,
                "check_out": check_out,
                "guests": guests,
                #"rooms": rooms,
                "total_price": total_price
            }}
        )
        flash('Reservation updated successfully!')
        return redirect(url_for('manager_bookings'))

    return render_template('edit_reservation.html', reservation=reservation)


@app.route('/delete_reservation/<reservation_id>', methods=['POST'])
@login_required
@role_required('manager_user')
def delete_reservation(reservation_id):
    try:
        # Recuperar la reserva
        reservation = db.reservations.find_one({"_id": ObjectId(reservation_id)})
        if not reservation:
            flash('Reservation not found!')
            return redirect(url_for('manager_bookings'))

        hotel_id = reservation['hotel_id']
        guests_to_release = reservation['guests']

        # Eliminar la reserva
        db.reservations.delete_one({"_id": ObjectId(reservation_id)})

        # Actualizar la disponibilidad de huéspedes en el hotel
        db.hotels.update_one(
            {"_id": ObjectId(hotel_id)},
            {"$inc": {"no_of_guests": guests_to_release}}
        )

        flash('Reservation deleted and hotel availability updated successfully!')
    
    except Exception as e:
        # Manejar excepciones y proporcionar retroalimentación
        flash(f'An error occurred: {e}')

    return redirect(url_for('manager_bookings'))









@app.route('/super_profile', methods=['GET', 'POST'])
@login_required
@role_required('super_user')
def super_profile():
    user_id = current_user.get_id()
    user_data = db.users.find_one({"_id": ObjectId(user_id)})
    
    if request.method == 'POST':
        if 'update_profile' in request.form:
            name = request.form.get('name')
            lastname = request.form.get('lastname')
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')

            if not check_password_hash(user_data['password'], current_password):
                flash('Current password is incorrect!')
                return redirect(url_for('super_profile'))

            update_data = {
                "name": name,
                "lastname": lastname,
            }
            if new_password:
                update_data["password"] = generate_password_hash(new_password)

            db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
            flash("Profile updated successfully!")
            return redirect(url_for('super_profile'))

    return render_template('super_profile.html', user_data=user_data)


@app.route('/super_listing')
@login_required
@role_required('super_user')
def super_listing():
    if current_user.auth_level != 'super_user':
        flash("Access Denied: You don't have the necessary permissions.", 'danger', category='login')
        return redirect(url_for('login'))

    cities = list(cities_collection.find())
    return render_template('super_listing.html', cities=cities)

@app.route('/super_manager')
@login_required
@role_required('super_user')
def super_manager():
    if current_user.auth_level != 'super_user':
        flash("Access Denied: You don't have the necessary permissions.", 'danger', category='login')
        return redirect(url_for('login'))

    managers = list(users_collection.find({'auth_level': 'manager_user'}))
    return render_template('super_manager.html', managers=managers)

@app.route('/super_add_city', methods=['GET', 'POST'])
@login_required
@role_required('super_user')
def super_add_city():
    if current_user.auth_level != 'super_user':
        flash("Access Denied: You don't have the necessary permissions.", 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        name = request.form['name']
        country = request.form['country']
        description = request.form['description']

        image = request.files.get('image')
        image_url = None
        if image and image.filename:
            filename = secure_filename(image.filename)
            image_url = os.path.join(app.config['images'], filename)
            image.save(image_url)

        city_data = {
            'name': name,
            'country': country,
            'description': description,
            'image_url': filename if image_url else None  # Guardar solo el nombre del archivo
        }

        cities_collection.insert_one(city_data)
        flash('City added successfully', 'success')
        return redirect(url_for('super_listing'))

    return render_template('super_add_city.html')


@app.route('/super_edit_city/<city_id>', methods=['GET', 'POST'])
@login_required
@role_required('super_user')
def super_edit_city(city_id):
    if current_user.auth_level != 'super_user':
        flash("Access Denied: You don't have the necessary permissions.", 'danger')
        return redirect(url_for('login'))

    city = cities_collection.find_one({"_id": ObjectId(city_id)})

    if request.method == 'POST':
        name = request.form['name']
        country = request.form['country']
        description = request.form['description']

        image = request.files.get('image')
        if image and image.filename:
            filename = secure_filename(image.filename)
            image_url = os.path.join(app.config['images'], filename)
            image.save(image_url)
            image_path = filename  # Actualizar con el nuevo nombre de archivo
        else:
            image_path = city.get('image_url')  # Mantener la imagen actual si no se carga una nueva

        update_data = {
            'name': name,
            'country': country,
            'description': description,
            'image_url': image_path
        }

        cities_collection.update_one({"_id": ObjectId(city_id)}, {"$set": update_data})
        flash('City updated successfully', 'success')
        return redirect(url_for('super_listing'))

    return render_template('super_edit_city.html', city=city)




@app.route('/super_add_manager', methods=['GET', 'POST'])
@login_required
@role_required('super_user')
def super_add_manager():
    if current_user.auth_level != 'super_user':
        flash("Access Denied: You don't have the necessary permissions.", 'danger', category='login')
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
            return redirect(url_for('super_manager'))
    
    return render_template('super_add_manager.html')

@app.route('/super_edit_manager/<manager_id>', methods=['GET', 'POST'])
@login_required
@role_required('super_user')
def super_edit_manager(manager_id):
    manager = db.users.find_one({'_id': ObjectId(manager_id)})
    if request.method == 'POST':
        name = request.form['name']
        lastname = request.form['lastname']
        db.users.update_one({'_id': ObjectId(manager_id)}, {'$set': {
            'name': name,
            'lastname': lastname,
        }})
        flash('Manager updated successfully')
        return redirect(url_for('super_manager'))
    return render_template('super_edit_manager.html', manager=manager)





@app.route('/delete_manager/<manager_id>', methods=['POST'])
@login_required
@role_required('super_user')
def delete_manager(manager_id):
    if current_user.auth_level != 'super_user':
        flash("Access Denied: You don't have the necessary permissions.", 'danger', category='login')
        return redirect(url_for('login'))
    
    users_collection.delete_one({"_id": ObjectId(manager_id)})
    flash('Manager deleted successfully', 'success')
    return redirect(url_for('super_manager'))

# Route to delete city
@app.route('/delete_city/<city_id>', methods=['POST'])
@login_required
@role_required('super_user')
def delete_city(city_id):
    if current_user.auth_level != 'super_user':
        flash("Access Denied: You don't have the necessary permissions.", 'danger', category='login')
        return redirect(url_for('login'))
    
    try:
        # Encontrar todos los hoteles asociados a la ciudad
        hotels = list(db.hotels.find({"address.city_id": city_id}))
        hotel_ids = [hotel['_id'] for hotel in hotels]

        # Eliminar las reservas asociadas a esos hoteles
        if hotel_ids:
            db.reservations.delete_many({"hotel_id": {"$in": hotel_ids}})

        # Eliminar los hoteles asociados a la ciudad
        if hotel_ids:
            db.hotels.delete_many({"_id": {"$in": hotel_ids}})

        # Eliminar la ciudad
        db.cities.delete_one({"_id": ObjectId(city_id)})

        flash('City and all associated hotels and reservations deleted successfully!', 'success')
    except Exception as e:
        # Manejar cualquier excepción y proporcionar retroalimentación
        flash(f'An error occurred: {e}', 'danger')
    
    return redirect(url_for('super_listing'))


# Rutas de Gestión de Hoteles

@app.route('/add_hotel', methods=['GET', 'POST'])
@login_required
@role_required('manager_user')
def add_hotel():
    cities = list(db.cities.find())
    
    if request.method == 'POST':
        title = request.form['title']
        street1 = request.form['street1']
        street2 = request.form.get('street2', '')
        street3 = request.form.get('street3', '')
        postal_code = request.form['postal_code']
        
        city_id = request.form['city']  # Captura el ID de la ciudad
        city = next((city['name'] for city in cities if str(city['_id']) == city_id), None)  # Busca el nombre basado en el ID

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
                'city_id': city_id,  # Almacena el ID de la ciudad
                'city': city,  # Almacena el nombre de la ciudad
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
        return redirect(url_for('manager_profile'))

    return render_template('add_hotel.html', cities=cities)




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


@app.route('/get_photo/<photo_id>')
def get_photo(photo_id):
    try:
        photo = fs.get(ObjectId(photo_id))
        response = make_response(photo.read())
        response.mimetype = 'image/jpeg'
        return response
    except:
        return '', 404


#Ejecución de la Aplicación
if __name__ == '__main__':
    app.run(debug=True)

