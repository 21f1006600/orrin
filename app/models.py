from app import db


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