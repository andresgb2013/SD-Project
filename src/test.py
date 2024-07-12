from flask import Flask, request, redirect, url_for, flash, render_template
from werkzeug.utils import secure_filename
from pymongo import MongoClient
import gridfs
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Conexión a MongoDB
client = MongoClient('mongodb+srv://andresgb2013:DN0kJdOtj5eJmoo3@cluster0.jzfu1jp.mongodb.net/')
db = client['SD_Project']  # Reemplaza 'your_database_name' con el nombre de tu base de datos
users_collection = db['users']
hotels_collection = db['hotels']



