# Canvas Assignment Tracker PWA

A Progressive Web App (PWA) that tracks your Canvas LMS assignments, sends Discord notifications for upcoming deadlines, late assignments, and newly graded work.

## Features

- **Course Tracking**: Automatically syncs your active courses from Canvas
- **Assignment Views**:
  - Upcoming assignments with due dates
  - Late/overdue assignments
  - Recently graded assignments with scores
- **Discord Notifications**:
  - Upcoming assignment reminders (1 week, 5 days, 3 days, 1 day, 10 hours, 1 hour before due)
  - Overdue assignment alerts (daily)
  - Grade notifications when assignments are graded
- **PWA Support**: Install as a standalone app on mobile/desktop
- **Offline Capable**: Service worker for basic offline functionality
- **Background Sync**: Automatically syncs assignments every 30 minutes

## Project Structure

```
canvas-tracker-pwa/
├── app.py                 # Flask backend with Canvas API integration
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html         # Main frontend template
├── static/
│   ├── script.js          # Frontend JavaScript
│   ├── style.css          # Custom styles
│   ├── manifest.json      # PWA manifest
│   ├── service-worker.js  # Service worker for offline support
│   └── icons/             # PWA icons (various sizes)
└── canvas_tracker.db      # SQLite database (auto-created)
```

## Prerequisites

- Python 3.9+
- Canvas LMS account with API access
- Discord server with webhook access

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd canvas-tracker-pwa
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:

   Set the following environment variables before running the app:

   ```bash
   export CANVAS_API_TOKEN="your_canvas_api_token"
   export CANVAS_BASE_URL="https://your-school.instructure.com"
   export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
   ```

   **Getting your Canvas API Token**:
   1. Log in to Canvas
   2. Go to Account > Settings
   3. Scroll to "Approved Integrations"
   4. Click "+ New Access Token"
   5. Copy the generated token

   **Getting a Discord Webhook URL**:
   1. Open Discord server settings
   2. Go to Integrations > Webhooks
   3. Click "New Webhook"
   4. Copy the webhook URL

## Running the App

```bash
python app.py
```

The app will start on `http://127.0.0.1:5001`

On first run, it will:
1. Create the SQLite database
2. Sync courses and assignments from Canvas
3. Start the background scheduler for periodic syncs

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main web interface |
| `/api/status` | GET | Check backend and API connection status |
| `/api/courses` | GET | Fetch and sync courses from Canvas |
| `/api/assignments` | GET | Get upcoming assignments |
| `/api/assignments/late` | GET | Get late/overdue assignments |
| `/api/assignments/graded` | GET | Get recently graded assignments |
| `/api/test_discord` | GET/POST | Send a test Discord notification |

### Query Parameters

- `course_ids`: Comma-separated list of course IDs to filter assignments (e.g., `?course_ids=123,456`)

## Notification Thresholds

Upcoming assignment reminders are sent at these intervals before the due date:
- 1 week
- 5 days
- 3 days
- 1 day
- 10 hours
- 1 hour

Overdue notifications are sent once per day for late assignments.

## Database Schema

**Courses Table**:
- `id` (Primary Key, from Canvas)
- `name`
- `course_code`
- `is_active`
- `created_at`, `updated_at`

**Assignments Table**:
- `id` (Primary Key, from Canvas)
- `name`
- `due_at`
- `points_possible`
- `html_url`
- `course_id` (Foreign Key)
- `submitted_at`, `graded_at`
- `score`, `grade`
- `workflow_state`
- `last_upcoming_notification_level`
- `last_late_notification_sent_at`
- `last_grade_notification_sent_at`

## Troubleshooting

**"Canvas API Token or Base URL is not configured"**
- Ensure environment variables are set correctly
- Check that the Canvas URL doesn't have a trailing slash issue

**"Unauthorized - check token/URL"**
- Your Canvas API token may have expired
- Generate a new token from Canvas settings

**Discord notifications not sending**
- Verify the webhook URL is correct
- Check that the webhook hasn't been deleted from Discord
- Look at the Flask logs for error messages

**Assignments not syncing**
- Check the Flask console for API errors
- Ensure your Canvas account has student enrollment in courses

## License

MIT License
