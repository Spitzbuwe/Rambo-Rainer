from flask_sqlalchemy import SQLAlchemy
import datetime

db = SQLAlchemy()
Base = db.Model

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
