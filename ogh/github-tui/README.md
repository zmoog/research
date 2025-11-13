# GitHub TUI - Terminal User Interface for GitHub Notifications

A terminal-based interface for managing GitHub notifications, specifically focused on mentions.

## Features

- View all mentions across your GitHub repositories
- Sort by date (newest first) and "age" (time since last update vs last time you viewed it)
- Track when you last viewed each notification
- Clean, keyboard-driven interface

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

- `↑/↓` or `j/k` - Navigate through mentions
- `Enter` - Open notification in browser and mark as viewed
- `r` - Refresh notifications
- `q` - Quit

## How It Works

The app fetches your GitHub notifications filtered by mentions and stores the last time you viewed each one locally. It calculates "age" as the time between the notification's last update and when you last viewed it, helping you prioritize which mentions need attention.
