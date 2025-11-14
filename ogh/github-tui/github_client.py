"""GitHub API client for fetching notifications."""
from datetime import datetime
from typing import List, Dict, Any
from github import Github, Auth
from github.Notification import Notification


class NotificationData:
    """Wrapper for notification data with additional computed fields."""

    def __init__(self, notification: Notification, last_viewed: datetime = None):
        self.id = notification.id
        self.title = notification.subject.title
        self.reason = notification.reason
        self.repository = notification.repository.full_name
        self.updated_at = notification.updated_at
        self.url = notification.subject.url
        self.html_url = self._get_html_url(notification)
        self.unread = notification.unread
        self.last_viewed = last_viewed

    def _get_html_url(self, notification: Notification) -> str:
        """Extract the HTML URL from the notification."""
        # The URL in subject is an API URL, we need to convert it
        subject_type = notification.subject.type
        url = notification.subject.url

        if not url:
            return notification.repository.html_url

        # Convert API URL to HTML URL
        # Example: https://api.github.com/repos/owner/repo/issues/123
        # -> https://github.com/owner/repo/issues/123
        if 'api.github.com/repos/' in url:
            return url.replace('api.github.com/repos/', 'github.com/')

        return url

    def age_score(self) -> float:
        """
        Calculate age score for sorting.
        Higher score = needs more attention.
        Based on time since last update vs time since last viewed.
        """
        now = datetime.now()

        # Time since last update (in hours)
        hours_since_update = (now - self.updated_at.replace(tzinfo=None)).total_seconds() / 3600

        if self.last_viewed:
            # Time since last viewed (in hours)
            hours_since_viewed = (now - self.last_viewed).total_seconds() / 3600
            # If viewed after update, lower priority
            if self.last_viewed > self.updated_at.replace(tzinfo=None):
                return hours_since_update * 0.5  # Lower priority
            else:
                # Not viewed since update - high priority
                return hours_since_update * 2.0
        else:
            # Never viewed - highest priority
            return hours_since_update * 3.0

    def human_age(self) -> str:
        """
        Return human-friendly age string.
        Examples: "2m", "3h", "5d", "2w", "3mo"
        """
        now = datetime.now()
        delta = now - self.updated_at.replace(tzinfo=None)

        seconds = delta.total_seconds()
        minutes = seconds / 60
        hours = minutes / 60
        days = hours / 24
        weeks = days / 7
        months = days / 30
        years = days / 365

        if years >= 1:
            return f"{int(years)}y"
        elif months >= 1:
            return f"{int(months)}mo"
        elif weeks >= 1:
            return f"{int(weeks)}w"
        elif days >= 1:
            return f"{int(days)}d"
        elif hours >= 1:
            return f"{int(hours)}h"
        elif minutes >= 1:
            return f"{int(minutes)}m"
        else:
            return "now"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for display."""
        return {
            'id': self.id,
            'title': self.title,
            'reason': self.reason,
            'repository': self.repository,
            'updated_at': self.updated_at,
            'html_url': self.html_url,
            'unread': self.unread,
            'last_viewed': self.last_viewed,
            'age_score': self.age_score()
        }


class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(self, token: str):
        auth = Auth.Token(token)
        self.client = Github(auth=auth)

    def get_mentions(self) -> List[Notification]:
        """Fetch all notifications where the user was mentioned."""
        user = self.client.get_user()
        notifications = user.get_notifications(all=True)

        # Filter for mentions
        mentions = [n for n in notifications if n.reason in ['mention', 'team_mention']]
        return mentions

    def mark_as_read(self, notification_id: str) -> None:
        """Mark a notification as read on GitHub."""
        try:
            # This requires getting the notification object first
            # For now, we'll skip this to avoid additional API calls
            # Users can mark as read manually if needed
            pass
        except Exception as e:
            print(f"Error marking notification as read: {e}")
