import os
import posthog

# Initialize PostHog
posthog.api_key = os.getenv("POSTHOG_API_KEY")
posthog.host = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")


def enabled():
    """Return True if PostHog is configured."""
    return bool(posthog.api_key)


def identify_user(user):
    """Identify a user in PostHog."""
    if not enabled():
        return

    posthog.identify(
        distinct_id=str(user.id),
        properties={
            "email": user.email,
            "name": user.name,
        },
    )


def capture(user, event, properties=None):
    """Capture an analytics event."""
    if not enabled():
        return

    posthog.capture(
        distinct_id=str(user.id),
        event=event,
        properties=properties or {},
    )