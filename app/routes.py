from flask import Blueprint, render_template, redirect, url_for, session
from app import oauth, db, limiter, logger
from app.models import User
from app.sync import sync_slack_data, sync_linear_data

main = Blueprint('main', __name__)


def get_current_user():
    """Returns the logged-in user's own record, derived strictly from session.
    Never accepts a user ID from the request itself - this is the IDOR-safe pattern.
    Returns None if nobody is logged in.
    """
    email = session.get('user_email')
    if not email:
        return None
    return User.query.filter_by(email=email).first()


@main.route('/')
def index():
    return render_template('index.html')


@main.route('/login')
@limiter.limit("20 per minute")
def login():
    if 'user_email' in session:
        return redirect(url_for('main.connect'))
    return render_template('login.html')


@main.route('/auth/google')
@limiter.limit("10 per minute")
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
    is_new_signup = existing_user is None

    if not existing_user:
        existing_user = User(
            email=user_info['email'],
            name=user_info.get('name'),
            picture=user_info.get('picture')
        )
        db.session.add(existing_user)
        db.session.commit()
        logger.info(f"NEW SIGNUP: {existing_user.email}")

    session.permanent = True
    session['user_email'] = existing_user.email
    session['user_name'] = existing_user.name
    session['user_picture'] = existing_user.picture

    import sentry_sdk
    sentry_sdk.set_user({"email": existing_user.email, "username": existing_user.name})

    logger.info(f"Login successful: {existing_user.email}")

    return redirect(url_for('main.connect'))


@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))


@main.route('/auth/slack')
@limiter.limit("10 per minute")
def slack_login():
    if 'user_email' not in session:
        return redirect(url_for('main.login'))
    redirect_uri = url_for('main.slack_callback', _external=True)
    return oauth.slack.authorize_redirect(redirect_uri)


@main.route('/auth/slack/callback')
def slack_callback():
    token = oauth.slack.authorize_access_token()

    current_user = get_current_user()
    current_user.slack_team_id = token.get('team', {}).get('id')
    current_user.slack_team_name = token.get('team', {}).get('name')
    current_user.slack_bot_token = token.get('access_token')
    db.session.commit()

    sync_slack_data(current_user)

    logger.info(f"SLACK CONNECTED: {current_user.email} -> {current_user.slack_team_name}")

    return redirect(url_for('main.connect'))


@main.route('/auth/linear')
@limiter.limit("10 per minute")
def linear_login():
    if 'user_email' not in session:
        return redirect(url_for('main.login'))
    redirect_uri = url_for('main.linear_callback', _external=True)
    return oauth.linear.authorize_redirect(redirect_uri)


@main.route('/auth/linear/callback')
def linear_callback():
    token = oauth.linear.authorize_access_token()
    access_token = token.get('access_token')

    # Fetch the workspace name using Linear's GraphQL API
    import requests
    response = requests.post(
        'https://api.linear.app/graphql',
        json={'query': '{ organization { name } }'},
        headers={'Authorization': access_token}
    )
    org_data = response.json()
    workspace_name = org_data.get('data', {}).get('organization', {}).get('name', 'Linear Workspace')

    current_user = get_current_user()
    current_user.linear_access_token = access_token
    current_user.linear_workspace_name = workspace_name
    db.session.commit()

    sync_linear_data(current_user)

    logger.info(f"LINEAR CONNECTED: {current_user.email} -> {current_user.linear_workspace_name}")

    return redirect(url_for('main.connect'))


@main.route('/sync')
@limiter.limit("5 per minute")
def manual_sync():
    if 'user_email' not in session:
        return redirect(url_for('main.login'))

    current_user = get_current_user()
    results = {}

    if current_user.slack_bot_token:
        results['slack'] = sync_slack_data(current_user)

    if current_user.linear_access_token:
        results['linear'] = sync_linear_data(current_user)

    logger.info(f"Sync triggered by {current_user.email}: {results}")

    return results


@main.route('/connect')
def connect():
    if 'user_email' not in session:
        return redirect(url_for('main.login'))

    current_user = get_current_user()
    return render_template('connect.html', user=current_user)


@main.route('/dashboard')
def dashboard():
    if 'user_email' not in session:
        return redirect(url_for('main.login'))

    current_user = get_current_user()
    return render_template('dashboard.html', user=current_user, result=None, question=None)


@main.route('/dashboard/ask', methods=['POST'])
@limiter.limit("15 per minute")
def dashboard_ask():
    if 'user_email' not in session:
        return redirect(url_for('main.login'))

    from flask import request
    from app.ai import ask_orrin

    current_user = get_current_user()
    question = request.form.get('question', '').strip()

    # Input validation - reject empty or absurdly long questions
    if not question:
        return redirect(url_for('main.dashboard'))

    if len(question) > 500:
        question = question[:500]

    result = ask_orrin(current_user, question)

    logger.info(f"QUESTION ASKED: {current_user.email} -> \"{question[:100]}\" (confidence: {result.get('confidence', 0)}%)")

    return render_template('dashboard.html', user=current_user, result=result, question=question)