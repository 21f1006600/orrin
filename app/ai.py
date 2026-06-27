import os
import json
import random
from app.models import SlackMessage, LinearIssue

# Set to True to use free mock responses instead of calling the real Gemini API.
# Flip to False once you have a free Gemini API key from aistudio.google.com.
MOCK_MODE = False

if not MOCK_MODE:
    from google import genai as google_genai

    gemini_key = os.getenv('GEMINI_API_KEY')
    if not gemini_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to your .env locally, "
            "or to your Railway/Render environment variables in production."
        )

    # New SDK (google-genai), replacing the deprecated google-generativeai library
    # which was officially sunset and caused credential-discovery failures in production.
    genai_client = google_genai.Client(api_key=gemini_key)
    # gemini-2.5-flash-lite: free tier as of June 2026, cheapest paid option if quota exceeded
    # gemini-2.0-flash and gemini-2.0-flash-lite were both shut down June 1, 2026
    # check https://ai.google.dev/gemini-api/docs/models for current free-tier models if this breaks
    GEMINI_MODEL = 'gemini-2.5-flash-lite'


def build_context(user):
    """Pull recent Slack messages and Linear issues for this user into a text block."""

    slack_messages = (
        SlackMessage.query
        .filter_by(user_id=user.id)
        .order_by(SlackMessage.posted_at.desc())
        .limit(100)
        .all()
    )

    linear_issues = (
        LinearIssue.query
        .filter_by(user_id=user.id)
        .order_by(LinearIssue.updated_at.desc())
        .limit(50)
        .all()
    )

    slack_text = "\n".join([
        f"[Slack #{m.channel_name}] {m.author} ({m.posted_at}): {m.message_text}"
        for m in slack_messages
    ])

    linear_text = "\n".join([
        f"[Linear {i.issue_identifier}] {i.title} — Status: {i.status} — Assignee: {i.assignee or 'unassigned'} — Updated: {i.updated_at}\n  Description: {i.description or 'none'}"
        for i in linear_issues
    ])

    return slack_text, linear_text, slack_messages, linear_issues


SYSTEM_PROMPT = """You are Orrin, an AI that answers operational questions about a startup by synthesizing information from Slack messages and Linear issues.

Rules:
- Only use the provided Slack and Linear data to answer. Never invent facts.
- If the data doesn't contain enough information to answer confidently, say so honestly.
- Give a direct, synthesized answer — not a list of raw messages.
- Identify the root causes or key facts, not just a summary.
- Return your response as valid JSON only, no markdown, no extra text, in this exact structure:

{
  "answer": "2-3 sentence direct answer to the question",
  "confidence": 85,
  "root_causes": ["short bullet 1", "short bullet 2", "short bullet 3"],
  "used_slack_indexes": [0, 2],
  "used_linear_indexes": [0, 1]
}

confidence is your honest 0-100 estimate of how well the data supports this answer.
used_slack_indexes and used_linear_indexes refer to the index position (starting at 0) of the messages/issues listed below that you actually used as evidence.
If there is not enough data at all, set confidence below 40 and explain that in the answer.
"""


def ask_orrin(user, question):
    slack_text, linear_text, slack_messages, linear_issues = build_context(user)

    if not slack_text and not linear_text:
        return {
            "answer": "There's no synced data yet. Connect Slack or Linear, then try asking again.",
            "confidence": 0,
            "root_causes": [],
            "slack_sources": [],
            "linear_sources": []
        }

    # Number the messages/issues so we can reference them by index
    numbered_slack = "\n".join([
        f"{idx}. [#{m.channel_name}] {m.author}: {m.message_text}"
        for idx, m in enumerate(slack_messages)
    ])
    numbered_linear = "\n".join([
        f"{idx}. [{i.issue_identifier}] {i.title} — {i.status} — {i.assignee or 'unassigned'}"
        for idx, i in enumerate(linear_issues)
    ])

    if MOCK_MODE:
        result = _generate_mock_answer(question, slack_messages, linear_issues)
    else:
        full_prompt = f"""{SYSTEM_PROMPT}

Question: {question}

SLACK MESSAGES:
{numbered_slack if numbered_slack else "No Slack messages available."}

LINEAR ISSUES:
{numbered_linear if numbered_linear else "No Linear issues available."}

Answer the question using only the data above. Return valid JSON only."""

        response = genai_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=full_prompt
        )
        raw_text = response.text.strip()

        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`").replace("json\n", "", 1)

        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            result = {
                "answer": "Orrin had trouble processing that question. Try rephrasing it.",
                "confidence": 0,
                "root_causes": [],
                "used_slack_indexes": [],
                "used_linear_indexes": []
            }

    # Map the indexes back to real objects for displaying source cards
    slack_sources = [
        {
            "channel": slack_messages[i].channel_name,
            "author": slack_messages[i].author,
            "text": slack_messages[i].message_text,
            "posted_at": slack_messages[i].posted_at.strftime("%b %d, %I:%M %p") if slack_messages[i].posted_at else ""
        }
        for i in result.get("used_slack_indexes", []) if i < len(slack_messages)
    ]

    linear_sources = [
        {
            "identifier": linear_issues[i].issue_identifier,
            "title": linear_issues[i].title,
            "status": linear_issues[i].status,
            "assignee": linear_issues[i].assignee
        }
        for i in result.get("used_linear_indexes", []) if i < len(linear_issues)
    ]

    return {
        "answer": result.get("answer", ""),
        "confidence": result.get("confidence", 0),
        "root_causes": result.get("root_causes", []),
        "slack_sources": slack_sources,
        "linear_sources": linear_sources
    }


def _generate_mock_answer(question, slack_messages, linear_issues):
    """Generates a realistic fake answer using real synced data, no API call needed.
    This lets you test the full UI and data pipeline for free before spending on the real API.
    """

    if not slack_messages and not linear_issues:
        return {
            "answer": "There's no synced data yet. Connect Slack or Linear, then try asking again.",
            "confidence": 0,
            "root_causes": [],
            "used_slack_indexes": [],
            "used_linear_indexes": []
        }

    # Pick a few real messages/issues to "use" as evidence, simulating what the AI would select
    sample_slack_count = min(3, len(slack_messages))
    sample_linear_count = min(3, len(linear_issues))

    used_slack_indexes = random.sample(range(len(slack_messages)), sample_slack_count) if slack_messages else []
    used_linear_indexes = random.sample(range(len(linear_issues)), sample_linear_count) if linear_issues else []

    blocked_issues = [
        i for i in linear_issues
        if (i.status and 'block' in i.status.lower())
        or (i.title and 'block' in i.title.lower())
    ]

    if blocked_issues:
        primary_issue = blocked_issues[0]
        answer = (
            f"Based on your synced data, \"{primary_issue.title}\" ({primary_issue.issue_identifier}) "
            f"appears to be the main blocker, currently assigned to {primary_issue.assignee or 'no one'}. "
            f"This is reflected across recent Slack discussions and Linear activity."
        )
        confidence = random.randint(78, 94)
        root_causes = [
            f"{primary_issue.title} is marked as {primary_issue.status}",
            f"Related discussion found in {sample_slack_count} Slack message(s)",
            "Dependency or ownership unclear based on current data"
        ]
    elif slack_messages:
        answer = (
            f"Based on {len(slack_messages)} recent Slack messages and {len(linear_issues)} Linear issues, "
            f"the team has been actively discussing this topic, though no single blocker stands out clearly yet."
        )
        confidence = random.randint(60, 80)
        root_causes = [
            "Multiple related conversations found, but no single root cause isolated",
            "Consider syncing more data or asking a more specific question"
        ]
    else:
        answer = "There's limited data to fully answer this. Try syncing more Slack and Linear data first."
        confidence = random.randint(30, 50)
        root_causes = []

    return {
        "answer": answer,
        "confidence": confidence,
        "root_causes": root_causes,
        "used_slack_indexes": used_slack_indexes,
        "used_linear_indexes": used_linear_indexes
    }