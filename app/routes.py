from flask import Blueprint, render_template, redirect, url_for, session
from app import oauth, db
from app.models import User

main = Blueprint('main', __name__)


@main.route('/')
def index():
    return render_template('index.html')


@main.route('/login')
def login():
    if 'user_email' in session:
        return redirect(url_for('main.connect'))
    return render_template('login.html')


@main.route('/auth/google')
def google_login():
    redirect_uri = url_for('main.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@main.route('/auth/google/callback')
def google_callback():
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')

    if not user_info:
        return redirect(url_for('main.login'))

    existing_user = User.query.filter_by(email=user_info['email']).first()

    if not existing_user:
        existing_user = User(
            email=user_info['email'],
            name=user_info.get('name'),
            picture=user_info.get('picture')
        )
        db.session.add(existing_user)
        db.session.commit()

    session['user_email'] = existing_user.email
    session['user_name'] = existing_user.name
    session['user_picture'] = existing_user.picture

    return redirect(url_for('main.connect'))


@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))


@main.route('/connect')
def connect():
    if 'user_email' not in session:
        return redirect(url_for('main.login'))
    return f"Welcome {session.get('user_name')}! Connect workspace page coming next."