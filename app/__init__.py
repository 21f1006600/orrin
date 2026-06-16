from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'orrin-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///orrin.db'
    
    db.init_app(app)
    
    from app.routes import main
    app.register_blueprint(main)
    
    return app