import os
import logging
from datetime import timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
oauth = OAuth()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per hour"])
csrf = CSRFProtect()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('orrin.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('orrin')


def create_app():
    app = Flask(__name__)

    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY is not set in .env. Generate one with: "
            "python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    app.config['SECRET_KEY'] = secret_key
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///orrin.db'

    # Harden session cookies
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    # Set to True once deployed behind HTTPS in production
    app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'

    # Sessions expire after 24 hours of inactivity, forcing re-login
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

    db.init_app(app)
    oauth.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)

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

    from app import logger
    from flask import request

    @app.errorhandler(429)
    def ratelimit_handler(e):
        logger.warning(f"Rate limit exceeded: {request.remote_addr} on {request.path}")
        return {"error": "Too many requests. Please slow down."}, 429

    from app.routes import main
    app.register_blueprint(main)

    return app