"""GitHub Notifications TUI - Main Application."""
import os
import webbrowser
from datetime import datetime
from typing import List

from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, DataTable, Static
from textual.binding import Binding

from github_client import GitHubClient, NotificationData
from state_manager import StateManager


class NotificationStats(Static):
    """Display statistics about notifications."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.total = 0
        self.unread = 0

    def update_stats(self, total: int, unread: int):
        """Update the statistics."""
        self.total = total
        self.unread = unread
        self.update(f"Total mentions: {total} | Unread: {unread}")


class StatusBar(Static):
    """Display current operation status."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.update("Initializing...")

    def set_status(self, status: str):
        """Update the status message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.update(f"[{timestamp}] {status}")


class GitHubTUI(App):
    """GitHub Notifications TUI Application."""

    CSS = """
    Screen {
        background: $surface;
    }

    #stats {
        height: 3;
        content-align: center middle;
        background: $primary;
        color: $text;
        text-style: bold;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: $accent-darken-2;
        color: $text;
        padding: 0 1;
    }

    DataTable {
        height: 1fr;
    }

    DataTable > .datatable--header {
        background: $accent;
        color: $text;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: $secondary;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("enter", "open_notification", "Open", priority=True),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
    ]

    def __init__(self):
        super().__init__()
        self.github_client = None
        self.state_manager = StateManager()
        self.notifications: List[NotificationData] = []

    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header(show_clock=True)
        yield NotificationStats(id="stats")
        yield DataTable(id="notifications", cursor_type="row")
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the application."""
        status_bar = self.query_one("#status-bar", StatusBar)

        # Load environment variables
        status_bar.set_status("Loading configuration...")
        load_dotenv()
        token = os.getenv("GITHUB_TOKEN")

        if not token:
            status_bar.set_status("Error: GITHUB_TOKEN not found")
            self.exit(message="Error: GITHUB_TOKEN not found. Please set it in .env file")
            return

        try:
            status_bar.set_status("Initializing GitHub client...")
            self.github_client = GitHubClient(token)
        except Exception as e:
            status_bar.set_status(f"Error: {e}")
            self.exit(message=f"Error initializing GitHub client: {e}")
            return

        # Set up the data table
        status_bar.set_status("Setting up interface...")
        table = self.query_one("#notifications", DataTable)
        table.add_columns("Repository", "Title", "Updated", "Age Score", "Status")
        table.cursor_type = "row"

        # Load notifications
        self.action_refresh()

    def action_refresh(self) -> None:
        """Refresh notifications from GitHub."""
        if not self.github_client:
            return

        status_bar = self.query_one("#status-bar", StatusBar)
        self.title = "GitHub TUI - Loading..."

        try:
            # Fetch mentions
            status_bar.set_status("Fetching notifications from GitHub API...")
            mentions = self.github_client.get_mentions()
            status_bar.set_status(f"Received {len(mentions)} mention(s) from GitHub")

            # Convert to NotificationData with state
            status_bar.set_status("Processing notifications and loading view history...")
            self.notifications = []
            for mention in mentions:
                last_viewed = self.state_manager.get_last_viewed(mention.id)
                notif_data = NotificationData(mention, last_viewed)
                self.notifications.append(notif_data)

            # Sort by age score (descending) and then by updated_at (descending)
            status_bar.set_status("Sorting notifications by priority...")
            self.notifications.sort(
                key=lambda n: (n.age_score(), n.updated_at),
                reverse=True
            )

            # Update the table
            status_bar.set_status("Updating display...")
            self._update_table()

            self.title = "GitHub TUI - Mentions"
            status_bar.set_status("Ready - Press 'r' to refresh, 'q' to quit")

        except Exception as e:
            self.title = f"GitHub TUI - Error: {e}"
            status_bar.set_status(f"Error: {e}")

    def _update_table(self) -> None:
        """Update the data table with current notifications."""
        table = self.query_one("#notifications", DataTable)
        table.clear()

        for notif in self.notifications:
            # Format the updated time
            updated = notif.updated_at.strftime("%Y-%m-%d %H:%M")

            # Format age score
            age = f"{notif.age_score():.1f}"

            # Status
            status = "●" if notif.unread else "○"
            if notif.last_viewed:
                viewed_time = notif.last_viewed.strftime("%m-%d %H:%M")
                status += f" (viewed: {viewed_time})"

            table.add_row(
                notif.repository,
                notif.title[:60],  # Truncate long titles
                updated,
                age,
                status,
                key=notif.id
            )

        # Update stats
        stats = self.query_one("#stats", NotificationStats)
        unread_count = sum(1 for n in self.notifications if n.unread)
        stats.update_stats(len(self.notifications), unread_count)

    def action_open_notification(self) -> None:
        """Open the selected notification in browser."""
        table = self.query_one("#notifications", DataTable)
        status_bar = self.query_one("#status-bar", StatusBar)

        if not table.cursor_row:
            return

        try:
            row_key = table.get_row_at(table.cursor_row)
            notification_id = str(row_key[0])  # The key we stored

            # Find the notification
            notification = next(
                (n for n in self.notifications if n.id == notification_id),
                None
            )

            if notification:
                # Mark as viewed in our state
                status_bar.set_status(f"Opening: {notification.title[:50]}...")
                self.state_manager.mark_viewed(notification.id)

                # Open in browser
                webbrowser.open(notification.html_url)

                # Refresh to show updated state
                self.action_refresh()

        except Exception as e:
            self.title = f"Error opening notification: {e}"
            status_bar.set_status(f"Error: {e}")

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        table = self.query_one("#notifications", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        table = self.query_one("#notifications", DataTable)
        table.action_cursor_up()


def main():
    """Run the application."""
    app = GitHubTUI()
    app.run()


if __name__ == "__main__":
    main()
