from app import db
from datetime import datetime


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    name = db.Column(db.String(150))
    picture = db.Column(db.String(300))

    slack_team_id = db.Column(db.String(150))
    slack_team_name = db.Column(db.String(150))
    slack_bot_token = db.Column(db.String(300))

    linear_access_token = db.Column(db.String(300))
    linear_workspace_name = db.Column(db.String(150))

    last_synced_at = db.Column(db.DateTime)


class SlackMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    channel_id = db.Column(db.String(150))
    channel_name = db.Column(db.String(150))
    message_text = db.Column(db.Text)
    author = db.Column(db.String(150))
    posted_at = db.Column(db.DateTime)

    synced_at = db.Column(db.DateTime, default=datetime.utcnow)


class LinearIssue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    issue_identifier = db.Column(db.String(50))   # e.g. ORR-123
    title = db.Column(db.String(300))
    description = db.Column(db.Text)
    status = db.Column(db.String(100))
    assignee = db.Column(db.String(150))
    updated_at = db.Column(db.DateTime)

    synced_at = db.Column(db.DateTime, default=datetime.utcnow)