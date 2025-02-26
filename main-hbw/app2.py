import os
import shutil
import secrets
import sqlite3
import hashlib
import requests
from werkzeug.utils import secure_filename
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, jsonify, g, send_from_directory
)
from flask_bcrypt import Bcrypt
from flask_cors import CORS

# Initialize Flask app
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
CORS(app)

# Ensure the instance folder exists
os.makedirs(app.instance_path, exist_ok=True)

# Configuration for file uploads
UPLOAD_FOLDER = os.path.join(app.instance_path, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Allowed extensions for file uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Mock API URLs
HOTEL_API_URL = "https://67aec7a19e85da2f020e563c.mockapi.io/hotels/api/hotels"
FLIGHT_API_URL = "https://67aec7a19e85da2f020e563c.mockapi.io/hotels/api/flights"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database connection functions
def get_user_db_connection():
    if 'user_db' not in g:
        db_path = os.path.join(app.instance_path, 'user.db')
        g.user_db = sqlite3.connect(db_path)
        g.user_db.row_factory = sqlite3.Row
    return g.user_db

def get_admin_db_connection():
    if 'admin_db' not in g:
        db_path = os.path.join(app.instance_path, 'admin.db')
        g.admin_db = sqlite3.connect(db_path)
        g.admin_db.row_factory = sqlite3.Row
    return g.admin_db

@app.teardown_appcontext
def close_db_connection(exception):
    user_db = g.pop('user_db', None)
    admin_db = g.pop('admin_db', None)
    if user_db is not None:
        user_db.close()
    if admin_db is not None:
        admin_db.close()

# Password hashing
bcrypt = Bcrypt(app)

def hash_password(password):
    return bcrypt.generate_password_hash(password).decode('utf-8')

def check_password(hashed_password, password):
    return bcrypt.check_password_hash(hashed_password, password)

# Create databases and tables
def create_databases():
    # Create user database
    user_db_path = os.path.join(app.instance_path, 'user.db')
    print(f"Creating user database at: {user_db_path}")
    conn_user = sqlite3.connect(user_db_path)
    cursor_user = conn_user.cursor()
    cursor_user.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    cursor_user.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user INTEGER NOT NULL,
            type TEXT NOT NULL,
            booking_ref TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (user) REFERENCES users (id)
        )
    ''')
    cursor_user.execute('''
        CREATE TABLE IF NOT EXISTS flight_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL,
            flight_number TEXT NOT NULL,
            from_city TEXT NOT NULL,
            to_city TEXT NOT NULL,
            departure_date TEXT NOT NULL,
            arrival_date TEXT NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (booking_id) REFERENCES bookings (id)
        )
    ''')
    cursor_user.execute('''
        CREATE TABLE IF NOT EXISTS hotel_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL,
            hotel_id INTEGER NOT NULL,
            check_in_date TEXT NOT NULL,
            check_out_date TEXT NOT NULL,
            number_of_guests INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (booking_id) REFERENCES bookings (id)
        )
    ''')
    cursor_user.execute('PRAGMA journal_mode=WAL;')  # Enable WAL mode
    conn_user.commit()
    conn_user.close()
    print("User database created successfully.")

    # Create admin database
    admin_db_path = os.path.join(app.instance_path, 'admin.db')
    print(f"Creating admin database at: {admin_db_path}")
    conn_admin = sqlite3.connect(admin_db_path)
    cursor_admin = conn_admin.cursor()
    cursor_admin.execute('''
        CREATE TABLE IF NOT EXISTS hotels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            city TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL,
            picture_url TEXT
        )
    ''')
    cursor_admin.execute('PRAGMA journal_mode=WAL;')  # Enable WAL mode
    conn_admin.commit()
    conn_admin.close()
    print("Admin database created successfully.")

# Ensure the databases are created when the app starts
with app.app_context():
    create_databases()

# Auth Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'user')  # Default to user if not specified

        if not username or not email or not password:
            flash('All fields are required!', 'error')
            return redirect(url_for('register'))

        hashed_password = hash_password(password)

        conn = get_user_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)',
                           (username, email, hashed_password, role))
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            session['user_id'] = cursor.lastrowid
            session['username'] = username
            session['role'] = role
            if role == 'admin':
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('index'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists!', 'error')
        except Exception as e:
            flash(f'An error occurred: {e}', 'error')
        finally:
            close_db_connection(None)

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('All fields are required!', 'error')
            return redirect(url_for('login'))

        conn = get_user_db_connection()
        try:
            cursor = conn.cursor()
            user = cursor.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            if user and check_password(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                flash('Login successful!', 'success')
                if user['role'] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password!', 'error')
        except Exception as e:
            flash(f'An error occurred: {e}', 'error')
        finally:
            close_db_connection(None)

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('role', None)
    flash('You have been logged out!', 'success')
    return redirect(url_for('index'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')

        if not email:
            flash('Email is required!', 'error')
            return redirect(url_for('forgot_password'))

        conn = get_user_db_connection()
        try:
            cursor = conn.cursor()
            user = cursor.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            if user:
                return redirect(url_for('reset_password', email=email))
            else:
                flash('Email not found!', 'error')
        except Exception as e:
            flash(f'An error occurred: {e}', 'error')
        finally:
            close_db_connection(None)

    return render_template('forgot_password.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    email = request.args.get('email')  # Get email from query parameter
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not new_password or not confirm_password:
            flash('All fields are required!', 'error')
            return redirect(url_for('reset_password', email=email))

        if new_password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('reset_password', email=email))

        hashed_password = hash_password(new_password)

        conn = get_user_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET password = ? WHERE email = ?', (hashed_password, email))
            conn.commit()
            flash('Password reset successfully!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'An error occurred: {e}', 'error')
        finally:
            close_db_connection(None)

    return render_template('reset_password.html', email=email)

# Main Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please login to access the dashboard!', 'error')
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_user_db_connection()
    bookings = []
    
    try:
        cursor = conn.cursor()
        
        # Get all bookings for the user
        bookings_data = cursor.execute('''
            SELECT b.id, b.type, b.booking_ref, b.status, 
                   fb.flight_number, fb.from_city, fb.to_city, fb.departure_date, fb.price as flight_price,
                   hb.hotel_id, h.name as hotel_name, hb.check_in_date, hb.check_out_date, hb.price as hotel_price
            FROM bookings b
            LEFT JOIN flight_bookings fb ON b.id = fb.booking_id
            LEFT JOIN hotel_bookings hb ON b.id = hb.booking_id
            LEFT JOIN admin.hotels h ON hb.hotel_id = h.id
            WHERE b.user = ?
            ORDER BY b.id DESC
        ''', (user_id,)).fetchall()
        
        # Format the bookings
        for booking in bookings_data:
            booking_info = {
                'id': booking['id'],
                'type': booking['type'],
                'booking_ref': booking['booking_ref'],
                'status': booking['status']
            }
            
            if booking['type'] == 'flight':
                booking_info['details'] = {
                    'flight_number': booking['flight_number'],
                    'from': booking['from_city'],
                    'to': booking['to_city'],
                    'departure': booking['departure_date'],
                    'price': booking['flight_price']
                }
            elif booking['type'] == 'hotel':
                booking_info['details'] = {
                    'hotel_name': booking['hotel_name'],
                    'check_in': booking['check_in_date'],
                    'check_out': booking['check_out_date'],
                    'price': booking['hotel_price']
                }
                
            bookings.append(booking_info)
            
    except Exception as e:
        flash(f'An error occurred: {e}', 'error')
    finally:
        close_db_connection(None)

    return render_template('dashboard.html', username=session['username'], bookings=bookings)

@app.route('/hotels')
def hotels_page():
    return render_template('hotels.html')

@app.route('/flights')
def flights_page():
    return render_template('flights.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contactus')
def contactus():
    return render_template('contactus.html')

@app.route('/feedback_form')
def feedback():
    return render_template('feedback_form.html')

@app.route('/privacypolicy')
def privacy_policy():
    return render_template('privacypolicy.html')

@app.route('/termsandconditions')
def terms_conditions():
    return render_template('termsandconditions.html')

# Admin Routes
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please login as admin to access the admin page!', 'error')
        return redirect(url_for('login'))

    conn = get_admin_db_connection()
    try:
        cursor = conn.cursor()
        hotels = cursor.execute('SELECT * FROM hotels').fetchall()
    except Exception as e:
        flash(f'An error occurred: {e}', 'error')
        hotels = []
    finally:
        close_db_connection(None)

    return render_template('admin_dashboard.html', hotels=hotels)

@app.route('/admin/hotels')
def admin_hotels():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please login as admin to access this page!', 'error')
        return redirect(url_for('login'))

    conn = get_admin_db_connection()
    try:
        cursor = conn.cursor()
        hotels = cursor.execute('SELECT * FROM hotels').fetchall()
    except Exception as e:
        flash(f'An error occurred: {e}', 'error')
        hotels = []
    finally:
        close_db_connection(None)

    return render_template('admin_hotels.html', hotels=hotels)

@app.route('/admin/add_hotel', methods=['GET', 'POST'])
def add_hotel():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please login as admin to access this page!', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')
        location = request.form.get('location')
        city = request.form.get('city')
        description = request.form.get('description')
        price = request.form.get('price')

        if 'picture' not in request.files:
            flash('No picture file selected!', 'error')
            return redirect(url_for('add_hotel'))

        picture = request.files['picture']
        if picture.filename == '':
            flash('No picture file selected!', 'error')
            return redirect(url_for('add_hotel'))

        if not name or not location or not city or not description or not price:
            flash('All fields are required!', 'error')
            return redirect(url_for('add_hotel'))

        if picture and allowed_file(picture.filename):
            filename = secure_filename(picture.filename)
            instance_path = os.path.join(app.instance_path, 'uploads', filename)
            picture.save(instance_path)

            # Generate the URL using the route
            picture_url = url_for('uploaded_file', filename=filename)

        conn = get_admin_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO hotels (name, location, city, description, price, picture_url) VALUES (?, ?, ?, ?, ?, ?)',
                           (name, location, city, description, float(price), picture_url))
            conn.commit()
            flash('Hotel added successfully!', 'success')
        except Exception as e:
            flash(f'An error occurred: {e}', 'error')
        finally:
            close_db_connection(None)

        return redirect(url_for('admin_hotels'))

    return render_template('add_hotel.html')

@app.route('/admin/edit_hotel/<int:hotel_id>', methods=['GET', 'POST'])
def edit_hotel(hotel_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please login as admin to access this page!', 'error')
        return redirect(url_for('login'))

    conn = get_admin_db_connection()
    try:
        cursor = conn.cursor()
        hotel = cursor.execute('SELECT * FROM hotels WHERE id = ?', (hotel_id,)).fetchone()

        if request.method == 'POST':
            name = request.form.get('name')
            location = request.form.get('location')
            city = request.form.get('city')
            description = request.form.get('description')
            price = request.form.get('price')

            if 'picture' in request.files and request.files['picture'].filename != '':
                picture = request.files['picture']
                if picture and allowed_file(picture.filename):
                    filename = secure_filename(picture.filename)
                    instance_path = os.path.join(app.instance_path, 'uploads', filename)
                    picture.save(instance_path)

                    # Generate the URL using the route
                    picture_url = url_for('uploaded_file', filename=filename)
                else:
                    picture_url = hotel['picture_url']
            else:
                picture_url = hotel['picture_url']

            if not name or not location or not city or not description or not price:
                flash('All fields are required!', 'error')
                return redirect(url_for('edit_hotel', hotel_id=hotel_id))

            cursor.execute('UPDATE hotels SET name = ?, location = ?, city = ?, description = ?, price = ?, picture_url = ? WHERE id = ?',
                           (name, location, city, description, float(price), picture_url, hotel_id))
            conn.commit()
            flash('Hotel updated successfully!', 'success')
            return redirect(url_for('admin_hotels'))
    except Exception as e:
        flash(f'An error occurred: {e}', 'error')
        hotel = None
    finally:
        close_db_connection(None)

    return render_template('edit_hotel.html', hotel=hotel)

@app.route('/admin/delete_hotel/<int:hotel_id>', methods=['POST'])
def delete_hotel(hotel_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please login as admin to access this page!', 'error')
        return redirect(url_for('login'))

    conn = get_admin_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM hotels WHERE id = ?', (hotel_id,))
        conn.commit()
        flash('Hotel deleted successfully!', 'success')
    except Exception as e:
        flash(f'An error occurred: {e}', 'error')
    finally:
        close_db_connection(None)

    return redirect(url_for('admin_hotels'))

@app.route('/admin/bookings')
def admin_bookings():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please login as admin to access this page!', 'error')
        return redirect(url_for('login'))

    conn = get_user_db_connection()
    bookings = []
    
    try:
        cursor = conn.cursor()
        
        # Get all bookings
        bookings_data = cursor.execute('''
            SELECT b.id, b.user, u.username, b.type, b.booking_ref, b.status, 
                   fb.flight_number, fb.from_city, fb.to_city, fb.departure_date, fb.price as flight_price,
                   hb.hotel_id, h.name as hotel_name, hb.check_in_date, hb.check_out_date, hb.price as hotel_price
            FROM bookings b
            JOIN users u ON b.user = u.id
            LEFT JOIN flight_bookings fb ON b.id = fb.booking_id
            LEFT JOIN hotel_bookings hb ON b.id = hb.booking_id
            LEFT JOIN admin.hotels h ON hb.hotel_id = h.id
            ORDER BY b.id DESC
        ''').fetchall()
        
        # Format the bookings
        for booking in bookings_data:
            booking_info = {
                'id': booking['id'],
                'username': booking['username'],
                'type': booking['type'],
                'booking_ref': booking['booking_ref'],
                'status': booking['status']
            }
            
            if booking['type'] == 'flight':
                booking_info['details'] = {
                    'flight_number': booking['flight_number'],
                    'from': booking['from_city'],
                    'to': booking['to_city'],
                    'departure': booking['departure_date'],
                    'price': booking['flight_price']
                }
            elif booking['type'] == 'hotel':
                booking_info['details'] = {
                    'hotel_name': booking['hotel_name'],
                    'check_in': booking['check_in_date'],
                    'check_out': booking['check_out_date'],
                    'price': booking['hotel_price']
                }
                
            bookings.append(booking_info)
            
    except Exception as e:
        flash(f'An error occurred: {e}', 'error')
    finally:
        close_db_connection(None)

    return render_template('admin_bookings.html', bookings=bookings)

@app.route('/admin/update_booking/<int:booking_id>', methods=['POST'])
def update_booking_status(booking_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please login as admin to access this page!', 'error')
        return redirect(url_for('login'))
        
    status = request.form.get('status')
    
    conn = get_user_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE bookings SET status = ? WHERE id = ?', (status, booking_id))
        conn.commit()
        flash('Booking status updated successfully!', 'success')
    except Exception as e:
        flash(f'An error occurred: {e}', 'error')
    finally:
        close_db_connection(None)
        
    return redirect(url_for('admin_bookings'))

# API Routes
@app.route('/api/hotels', methods=['GET'])
def get_hotels_api():
    try:
        city = request.args.get("city")
        
        conn = get_admin_db_connection()
        cursor = conn.cursor()
        
        if city:
            query = "SELECT * FROM hotels WHERE city = ?"
            hotels = cursor.execute(query, (city,)).fetchall()
        else:
            query = "SELECT * FROM hotels"
            hotels = cursor.execute(query).fetchall()
            
        # Convert to list of dictionaries
        result = []
        for hotel in hotels:
            result.append({
                'id': hotel['id'],
                'name': hotel['name'],
                'location': hotel['location'],
                'city': hotel['city'],
                'description': hotel['description'],
                'price': hotel['price'],
                'picture_url': hotel['picture_url']
            })
            
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Error fetching data: {e}"}), 500
    finally:
        close_db_connection(None)

@app.route('/api/flights', methods=['GET'])
def get_flights_api():
    from_city = request.args.get("from")
    to_city = request.args.get("to")

    if not from_city or not to_city:
        return jsonify({"error": "Missing parameters"}), 400

    try:
        response = requests.get(FLIGHT_API_URL)
        if response.status_code != 200:
            return jsonify({"error": "Failed to fetch flights"}), 500
        
        flights = response.json()

        # Filter flights based on search
        filtered_flights = [flight for flight in flights if flight["from"] == from_city and flight["to"] == to_city]

        return jsonify(filtered_flights)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Booking Routes
@app.route('/book_hotel', methods=['POST'])
def book_hotel():
    if 'user_id' not in session:
        return jsonify({"error": "Please login to book a hotel"}), 401
        
    data = request.json
    hotel_id = data.get('hotel_id')
    check_in = data.get('check_in')
    check_out = data.get('check_out')
    guests = data.get('guests', 1)
    price = data.get('price')
    
    if not all([hotel_id, check_in, check_out, price]):
        return jsonify({"error": "Missing required booking information"}), 400
        
    user_id = session['user_id']
    booking_ref = f"HTL-{secrets.token_hex(4).upper()}"
    
    conn = get_user_db_connection()
    try:
        cursor = conn.cursor()
        
        # Start transaction
        cursor.execute('BEGIN TRANSACTION')
        
        # Create main booking record
        cursor.execute(
            'INSERT INTO bookings (user, type, booking_ref, status) VALUES (?, ?, ?, ?)',
            (user_id, 'hotel', booking_ref, 'confirmed')
        )
        booking_id = cursor.lastrowid
        
        # Create hotel booking details
        cursor.execute(
            'INSERT INTO hotel_bookings (booking_id, hotel_id, check_in_date, check_out_date, number_of_guests, price) VALUES (?, ?, ?, ?, ?, ?)',
            (booking_id, hotel_id, check_in, check_out, guests, price)
        )
        
        # Commit transaction
        cursor.execute('COMMIT')
        
        return jsonify({
            "success": True,
            "message": "Hotel booked successfully!",
            "booking_ref": booking_ref
        })
    except Exception as e:
        cursor.execute('ROLLBACK')
        return jsonify({"error": f"Booking failed: {e}"}), 500
    finally:
        close_db_connection(None)

@app.route('/book_flight', methods=['POST'])
def book_flight():
    if 'user_id' not in session:
        return jsonify({"error": "Please login to book a flight"}), 401
        
    data = request.json
    flight_number = data.get('flight_number')
    from_city = data.get('from')
    to_city = data.get('to')
    departure_date = data.get('departure_date')
    arrival_date = data.get('arrival_date', departure_date)  # Default to same day if not provided
    price = data.get('price')
    
    if not all([flight_number, from_city, to_city, departure_date, price]):
        return jsonify({"error": "Missing required booking information"}), 400
        
    user_id = session['user_id']
    booking_ref = f"FLT-{secrets.token_hex(4).upper()}"
    
    conn = get_user_db_connection()
    try:
        cursor = conn.cursor()
        
        # Start transaction
        cursor.execute('BEGIN TRANSACTION')
        
        # Create main booking record
        cursor.execute(
            'INSERT INTO bookings (user, type, booking_ref, status) VALUES (?, ?, ?, ?)',
            (user_id, 'flight', booking_ref, 'confirmed')
        )
        booking_id = cursor.lastrowid
        
        # Create flight booking details
        cursor.execute(
            'INSERT INTO flight_bookings (booking_id, flight_number, from_city, to_city, departure_date, arrival_date, price) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (booking_id, flight_number, from_city, to_city, departure_date, arrival_date, price)
        )
        
        # Commit transaction
        cursor.execute('COMMIT')
        
        return jsonify({
            "success": True,
            "message": "Flight booked successfully!",
            "booking_ref": booking_ref
        })
    except Exception as e:
        cursor.execute('ROLLBACK')
        return jsonify({"error": f"Booking failed: {e}"}), 500
    finally:
        close_db_connection(None)

@app.route('/cancel_booking/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    if 'user_id' not in session:
        flash('Please login to cancel a booking!', 'error')
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    
    conn = get_user_db_connection()
    try:
        cursor = conn.cursor()
        
        # Check if booking belongs to user
        booking = cursor.execute('SELECT * FROM bookings WHERE id = ? AND user = ?', 
                                (booking_id, user_id)).fetchone()
        
        if not booking:
            flash('Booking not found or not authorized!', 'error')
            return redirect(url_for('dashboard'))
            
        # Update booking status
        cursor.execute('UPDATE bookings SET status = ? WHERE id = ?', ('cancelled', booking_id))
        conn.commit()
        
        flash('Booking cancelled successfully!', 'success')
    except Exception as e:
        flash(f'An error occurred: {e}', 'error')
    finally:
        close_db_connection(None)
        
    return redirect(url_for('dashboard'))

# Utility routes
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(os.path.join(app.instance_path, 'uploads'), filename)

if __name__ == '__main__':
    app.run(debug=True)
