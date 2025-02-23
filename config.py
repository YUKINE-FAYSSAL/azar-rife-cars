import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('Fouad@2025@Admin')
    MONGO_URI = os.getenv('mongodb://localhost:27017/car_database')
