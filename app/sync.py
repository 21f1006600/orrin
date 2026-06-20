import requests
from datetime import datetime
from app import db
from app.models import SlackMessage, LinearIssue


def sync_slack_data(user):
    """Pull recent messages from all public channels the bot can see."""
    headers = {'Authorization': f'Bearer {user.slack_bot_token}'}
    user_name_cache = {}

    # Clean up old system messages that were stored before the subtype filter existed
    SlackMessage.query.filter_by(user_id=user.id).filter(
        SlackMessage.message_text.like('%has joined the channel%')
    ).delete(synchronize_session=False)
    db.session.commit()

    def get_user_name(slack_user_id):
        if not slack_user_id or slack_user_id == 'unknown':
            return 'Unknown'
        if slack_user_id in user_name_cache:
            return user_name_cache[slack_user_id]

        try:
            response = requests.get(
                'https://slack.com/api/users.info',
                headers=headers,
                params={'user': slack_user_id}
            )
            data = response.json()
            if data.get('ok'):
                name = data['user'].get('real_name') or data['user'].get('name') or slack_user_id
            else:
                print(f"Slack users.info failed for {slack_user_id}: {data.get('error')}")
                name = slack_user_id
        except Exception as e:
            print(f"Slack users.info exception for {slack_user_id}: {e}")
            name = slack_user_id

        user_name_cache[slack_user_id] = name
        return name

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

            # skip system/subtype messages like channel_join, bot_message, etc
            if msg.get('subtype'):
                continue

            existing = SlackMessage.query.filter_by(
                user_id=user.id,
                channel_id=channel_id,
                posted_at=datetime.fromtimestamp(float(msg['ts']))
            ).first()

            if existing:
                # refresh author name in case it was stored as a raw ID before
                existing.author = get_user_name(msg.get('user'))
                existing.message_text = msg.get('text')
                continue

            new_message = SlackMessage(
                user_id=user.id,
                channel_id=channel_id,
                channel_name=channel_name,
                message_text=msg.get('text'),
                author=get_user_name(msg.get('user')),
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