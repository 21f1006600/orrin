import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
oauth = OAuth()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'orrin-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///orrin.db'

    db.init_app(app)
    oauth.init_app(app)

    oauth.register(
        name='google',
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )

    oauth.register(
        name='slack',
        client_id=os.getenv('SLACK_CLIENT_ID'),
        client_secret=os.getenv('SLACK_CLIENT_SECRET'),
        access_token_url='https://slack.com/api/oauth.v2.access',
        authorize_url='https://slack.com/oauth/v2/authorize',
        client_kwargs={'scope': 'channels:history,channels:read,groups:read,groups:history,users:read'}
    )

    oauth.register(
        name='linear',
        client_id=os.getenv('LINEAR_CLIENT_ID'),
        client_secret=os.getenv('LINEAR_CLIENT_SECRET'),
        access_token_url='https://api.linear.app/oauth/token',
        authorize_url='https://linear.app/oauth/authorize',
        client_kwargs={'scope': 'read', 'token_endpoint_auth_method': 'client_secret_post'}
    )

    from app.routes import main
    app.register_blueprint(main)

    return app