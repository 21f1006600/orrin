import requests
from datetime import datetime
from app import db
from app.models import SlackMessage, LinearIssue


def sync_slack_data(user):
    """Pull recent messages from all public channels the bot can see."""
    headers = {'Authorization': f'Bearer {user.slack_bot_token}'}

    # Step 1: get list of channels
    channels_response = requests.get(
        'https://slack.com/api/conversations.list',
        headers=headers,
        params={'types': 'public_channel,private_channel', 'limit': 50}
    )
    channels_data = channels_response.json()

    if not channels_data.get('ok'):
        return {'success': False, 'error': channels_data.get('error')}

    channels = channels_data.get('channels', [])
    messages_synced = 0

    for channel in channels:
        channel_id = channel['id']
        channel_name = channel['name']

        # Step 2: get messages from this channel
        history_response = requests.get(
            'https://slack.com/api/conversations.history',
            headers=headers,
            params={'channel': channel_id, 'limit': 30}
        )
        history_data = history_response.json()

        if not history_data.get('ok'):
            continue  # skip channels the bot isn't in or can't access

        for msg in history_data.get('messages', []):
            # skip messages with no real text (joins, bot events etc)
            if not msg.get('text'):
                continue

            existing = SlackMessage.query.filter_by(
                user_id=user.id,
                channel_id=channel_id,
                posted_at=datetime.fromtimestamp(float(msg['ts']))
            ).first()

            if existing:
                continue  # avoid duplicate entries on repeated syncs

            new_message = SlackMessage(
                user_id=user.id,
                channel_id=channel_id,
                channel_name=channel_name,
                message_text=msg.get('text'),
                author=msg.get('user', 'unknown'),
                posted_at=datetime.fromtimestamp(float(msg['ts']))
            )
            db.session.add(new_message)
            messages_synced += 1

    db.session.commit()
    return {'success': True, 'messages_synced': messages_synced}


def sync_linear_data(user):
    """Pull recent issues from the user's Linear workspace."""
    query = """
    {
      issues(first: 50, orderBy: updatedAt) {
        nodes {
          identifier
          title
          description
          state { name }
          assignee { name }
          updatedAt
        }
      }
    }
    """

    response = requests.post(
        'https://api.linear.app/graphql',
        json={'query': query},
        headers={'Authorization': user.linear_access_token}
    )
    data = response.json()

    if 'errors' in data:
        return {'success': False, 'error': data['errors']}

    issues = data.get('data', {}).get('issues', {}).get('nodes', [])
    issues_synced = 0

    for issue in issues:
        existing = LinearIssue.query.filter_by(
            user_id=user.id,
            issue_identifier=issue['identifier']
        ).first()

        if existing:
            # update existing issue instead of duplicating
            existing.title = issue['title']
            existing.description = issue.get('description', '')
            existing.status = issue['state']['name']
            existing.assignee = issue['assignee']['name'] if issue.get('assignee') else None
            existing.updated_at = datetime.fromisoformat(issue['updatedAt'].replace('Z', '+00:00'))
        else:
            new_issue = LinearIssue(
                user_id=user.id,
                issue_identifier=issue['identifier'],
                title=issue['title'],
                description=issue.get('description', ''),
                status=issue['state']['name'],
                assignee=issue['assignee']['name'] if issue.get('assignee') else None,
                updated_at=datetime.fromisoformat(issue['updatedAt'].replace('Z', '+00:00'))
            )
            db.session.add(new_issue)
            issues_synced += 1

    db.session.commit()
    return {'success': True, 'issues_synced': issues_synced}