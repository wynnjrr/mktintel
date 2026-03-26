from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    buying_price = db.Column(db.Float)
    selling_price = db.Column(db.Float)
    quantity = db.Column(db.Integer)
    min_stock = db.Column(db.Integer)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # 🔥 NEW

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity_sold = db.Column(db.Integer)
    total_price = db.Column(db.Float)
    profit = db.Column(db.Float)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # 🔥 NEW