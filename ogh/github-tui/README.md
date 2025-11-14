# GitHub TUI - Terminal User Interface for GitHub Notifications

A terminal-based interface for managing GitHub notifications, specifically focused on mentions.

## Features

- View all mentions across your GitHub repositories
- Sort by priority with human-friendly age display (e.g., "2h", "3d", "1w")
- Toggle between newest-first and oldest-first sorting
- Filter notifications by repository name
- Track when you last viewed each notification
- Real-time status bar showing API operations
- Clean, keyboard-driven interface
- Opens notifications directly in your browser

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your GitHub Personal Access Token:
   - Go to GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)
   - Generate a new token with `notifications` scope
   - Create a `.env` file in this directory:
   ```
   GITHUB_TOKEN=your_token_here
   ```

## Usage

Run the application:
```bash
python main.py
```

## Keyboard Controls

### Navigation
- `↑/↓` or `j/k` - Navigate through mentions one at a time
- `PageUp/PageDown` - Navigate by page (10 rows at a time)

### Actions
- `Enter` or **Click** - View notification details in a modal panel
- `r` - Refresh notifications from GitHub
- `/` - Focus the filter input to search by repository
- `s` - Toggle sort order (newest first ↔ oldest first)
- `q` - Quit

### Detail Panel
When you press `Enter` or click on a notification, a detail panel opens showing:
- Repository name
- Issue/PR title
- Reason for notification (mention, team_mention)
- Last update time and age
- Read/unread status
- Last viewed time (if applicable)
- Clickable URL

From the detail panel:
- `o` or click "Open in Browser" - Open the URL in your default browser
- `Esc` or click "Close" - Close the panel without opening

### Filtering
Type `/` to focus the filter input, then type part of a repository name (e.g., "owner/repo"). The table will update in real-time to show only matching repositories. Press `Esc` to exit the filter input and return to navigation.

## How It Works

The app fetches your GitHub notifications filtered by mentions and stores the last time you viewed each one locally. It calculates "age" as the time between the notification's last update and when you last viewed it, helping you prioritize which mentions need attention.
