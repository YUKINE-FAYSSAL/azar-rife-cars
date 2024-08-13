import os

class Config:
    SECRET_KEY = os.environ.get('bonjour') 
    MONGO_URI = os.environ.get('mongodb://localhost:27017/car_database')  # -*- coding: utf-8 -*-

