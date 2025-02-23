from bson.objectid import ObjectId
from flask_dance.contrib.google import make_google_blueprint, google
from flask import Flask, request, redirect, url_for, render_template, flash, session, jsonify
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_session import Session
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo
import random
from dotenv import load_dotenv
import os


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './flask_session/'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_PERMANENT'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit file size to 16MB
Session(app)

client = MongoClient(os.getenv('MONGO_URI'))
db = client['car_database']
users_collection = db['users']
cars_collection = db['cars']

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_signup'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Access your environment variables securely
SECRET_KEY = os.getenv('SECRET_KEY')
MONGO_URI = os.getenv('MONGO_URI')


admin_user = {
    "username": "fou.ad@gmail.com",
    "password": generate_password_hash("Fouad@2025@Admin", method='pbkdf2:sha256')
,    
     "role": "admin"
}

# Insérer l'utilisateur admin dans la collection users
users_collection.insert_one(admin_user)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class User(UserMixin):
    def __init__(self, username, password, role):
        self.username = username
        self.password_hash = password
        self.role = role

    def get_id(self):
        return self.username

@login_manager.user_loader
def load_user(username):
    user_data = users_collection.find_one({"username": username})
    if user_data:
        return User(user_data['username'], user_data['password'], user_data['role'])
    return None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            flash("You do not have permission to access this page.")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class SignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    submit = SubmitField('Signup')

class ContactForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    message = TextAreaField('Message', validators=[DataRequired()])
    submit = SubmitField('Send Message')

@app.route('/')
def home():
    cars = list(cars_collection.find())
    random_cars = random.sample(cars, min(4, len(cars)))  # Select 4 random cars
    form = ContactForm()  # Create the form instance
    return render_template('index.html', cars=random_cars, form=form)

@app.route('/login_signup', methods=['GET', 'POST'])
def login_signup():
    login_form = LoginForm()
    signup_form = SignupForm()
    if request.method == 'POST':
        if 'login' in request.form:
            if login_form.validate_on_submit():
                username = login_form.username.data
                password = login_form.password.data
                user_data = users_collection.find_one({"username": username})
                if user_data and check_password_hash(user_data['password'], password):
                    user = User(user_data['username'], user_data['password'], user_data['role'])
                    login_user(user)
                    return redirect(url_for('home'))
                flash('Invalid username or password.', 'error')
        elif 'signup' in request.form:
            if signup_form.validate_on_submit():
                username = signup_form.username.data
                password = signup_form.password.data
                confirm_password = signup_form.confirm_password.data
                if password != confirm_password:
                    flash("Passwords do not match.", 'error')
                    return redirect(url_for('login_signup'))
                existing_user = users_collection.find_one({"username": username})
                if existing_user:
                    flash("Username already taken.", 'error')
                    return redirect(url_for('login_signup'))
                hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
                new_user = {
                    "username": username,
                    "password": hashed_password,
                    "role": "user"
                }
                users_collection.insert_one(new_user)
                flash("Sign up successful. You can now log in.")
                return redirect(url_for('login_signup'))
    return render_template('login_signup.html', login_form=login_form, signup_form=signup_form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/car/<car_id>')
def car_details(car_id):
    car = cars_collection.find_one({'_id': ObjectId(car_id)})
    if car is None:
        return "Car not found", 404
    print(car)  # Add this line to see what the car object contains in your console
    return render_template('car_details.html', car=car)


@app.route('/admin')
@login_required
@admin_required
def admin():
    cars = cars_collection.find()
    return render_template('admin.html', cars=cars)

@app.route('/service')
def service():
    return render_template('service.html')

@app.route('/about', methods=['GET', 'POST'])
def about():
    form = ContactForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        message = form.message.data
        # Handle the form submission (e.g., save to a database, send an email, etc.)
        flash('Message sent successfully!', 'success')
        return redirect(url_for('about'))
    return render_template('about.html', form=form)

@app.route('/cars')
def cars():
    search_query = request.args.get('search', '').lower()
    transmission = request.args.get('transmission', '').lower()
    availability = request.args.get('availability', '').lower()  # New parameter
    page = int(request.args.get('page', 1))
    per_page = 9  # Changed to 9
    
    query = {}
    
    if search_query:
        query['$or'] = [
            {'make': {'$regex': search_query, '$options': 'i'}},
            {'model': {'$regex': search_query, '$options': 'i'}}
        ]
    
    if transmission:
        query['transmission'] = {'$regex': transmission, '$options': 'i'}
    
    if availability:  # New filtering condition
        query['is_available'] = (availability == 'true')
    
    # Fetch cars from the database
    all_cars = list(cars_collection.find(query))
    total_cars = len(all_cars)
    cars = all_cars[(page - 1) * per_page: page * per_page]

    return render_template('cars.html', cars=cars, total_cars=total_cars, page=page, per_page=per_page, search_query=search_query, transmission=transmission, availability=availability)


@app.route('/delete_car/<car_id>', methods=['POST'])
@login_required
@admin_required
def delete_car(car_id):
    cars_collection.delete_one({'_id': ObjectId(car_id)})
    return redirect(url_for('admin'))

@app.route('/add_car', methods=['GET', 'POST'])
@login_required
@admin_required
def add_car():
    if request.method == 'POST':
        make = request.form.get('make')
        model = request.form.get('model')
        year = request.form.get('year')
        description = request.form.get('description')
        price = request.form.get('price')
        transmission = request.form.get('transmission')
        is_available = request.form.get('is_available') == 'on'

        car_images = request.files.getlist('car_images')
        image_filenames = []

        for car_image in car_images:
            if car_image and allowed_file(car_image.filename):
                filename = secure_filename(car_image.filename)
                car_image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filenames.append(filename)

        car = {
            'make': make,
            'model': model,
            'year': year,
            'description': description,
            'price': price,
            'images': image_filenames,
            'transmission': transmission,
            'is_available': is_available
        }

        cars_collection.insert_one(car)
        return redirect(url_for('admin'))

    return render_template('add_car.html')

@app.route('/edit_car/<car_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_car(car_id):
    car = cars_collection.find_one({'_id': ObjectId(car_id)})
    if request.method == 'POST':
        make = request.form.get('make')
        model = request.form.get('model')
        year = request.form.get('year')
        description = request.form.get('description')
        price = request.form.get('price')
        transmission = request.form.get('transmission')
        is_available = request.form.get('is_available') == 'on'

        update_data = {
            'make': make,
            'model': model,
            'year': year,
            'description': description,
            'price': price,
            'transmission': transmission,
            'is_available': is_available
        }

        if 'car_images' in request.files:
            car_images = request.files.getlist('car_images')
            image_filenames = car.get('images', [])
            for i, image in enumerate(car_images):
                if image.filename != '':
                    filename = secure_filename(image.filename)
                    image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    if i < len(image_filenames):
                        image_filenames[i] = filename
                    else:
                        image_filenames.append(filename)
            update_data['images'] = image_filenames
        
        cars_collection.update_one({'_id': ObjectId(car_id)}, {'$set': update_data})
        return redirect(url_for('admin'))

    return render_template('edit.html', car=car)


@app.route('/travel')
def travel():
    return render_template('travel.html')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
