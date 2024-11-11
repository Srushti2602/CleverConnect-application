# CleverConnect Project

This project is a Slack bot integrated with Google Gmail, Google Calendar, Trello, and Ollama. The bot fetches recent emails, extracts meeting details, syncs calendar events, and manages tasks on Trello based on user commands in Slack.

## Features

- **Slack Bot**: Interacts with users in Slack, allowing them to view recent emails, manage Trello lists, and synchronize Google Calendar events with Trello.
- **Google Gmail Integration**: Fetches recent emails and checks for meeting-related emails.
- **Google Calendar Integration**: Retrieves upcoming events from Google Calendar.
- **Trello Integration**: Creates, updates, and deletes tasks in Trello based on Slack commands.
- **Ollama Integration**: Uses the Ollama model to parse meeting details from email snippets.

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/CleverConnect.git
   cd CleverConnect
   ```

2. **Set Up a Virtual Environment**:
   ```bash
   python3 -m venv env
   source env/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Create Environment Variables**: Create a `.env` file in the root of the project and add the following:
   ```env
   SLACK_BOT_TOKEN=<your_slack_bot_token>
   APP_LEVEL_WRITE_TOKEN=<your_slack_app_level_token>
   TRELLO_API_KEY=<your_trello_api_key>
   TRELLO_API_SECRET=<your_trello_api_secret>
   TRELLO_TOKEN=<your_trello_token>
   TRELLO_BOARD_ID=<your_trello_board_id>
   OLLAMA_URL=http://localhost:11434  # Ensure Ollama server is running on this URL
   ```
   - **Note**: Replace placeholders with actual credentials.

5. **Set Up Google API Credentials**:
   - Follow the instructions in the [Google API Console](https://console.cloud.google.com/) to set up OAuth 2.0 credentials for Gmail and Calendar API access.
   - Download the credentials JSON file and save it as `credentials_gmail.json` and `credentials_calendar.json` in the project root.

## Usage

1. **Run Ollama Server** :
   Ensure that Ollama is running and accessible at the specified URL (`http://localhost:11434` by default).

2. **Start the Slack Bot**:
   ```bash
   python main.py
   ```

3. **Slack Commands**:
   - `hi`: Displays available commands.
   - `show me recent <number> emails`: Shows recent emails from Gmail.
   - `show me my <list_name> list`: Shows tasks in specified Trello list (`To Do`, `Doing`, `Done`, etc.).
   - `add event in <list_name> list <event_name> by <due_date>`: Adds an event to a Trello list.
   - `remove <task_name> from <list_name> list`: Removes a task from a specified list.
   - `create new list <list_name>`: Creates a new Trello list.
   - `sync calendar to trello`: Syncs Google Calendar events to the Trello list "Calendar Events".
   - `process recent emails for meetings`: Processes recent emails for meetings and adds to Trello if applicable.
   - `show me my events`: Displays combined Trello tasks and Google Calendar events.

## Project Structure

- `main.py`: Main script to run the Slack bot.
- `requirements.txt`: Python dependencies.
- `.env`: Environment variables for API keys and secrets.
- `credentials_gmail.json` and `credentials_calendar.json`: Google OAuth credentials.

## How It Works

1. **Email Processing**:
   - Retrieves recent emails from Gmail.
   - Uses keywords to identify meeting-related emails.
   - Extracts meeting details (date, time, description) with the help of the Ollama model.

2. **Trello Integration**:
   - Adds, updates, and removes tasks in Trello based on Slack commands and email/calendar synchronization.

3. **Calendar Synchronization**:
   - Retrieves Google Calendar events and synchronizes them with a specified Trello list.

4. **Slack Bot**:
   - Listens to Slack messages and performs actions based on commands.

## GitHub Actions Workflow (Optional)

A GitHub Actions workflow (`ollama-workflow.yml`) is provided to automate Ollama model pulling and API call tests.

Place the following file in `.github/workflows/ollama-workflow.yml`:

```yaml
name: Ollama
'on':
  workflow_dispatch:
jobs:
  run-ollama:
    runs-on: ubuntu-latest
    steps:
    - name: Install Ollama
      run: curl -fsSL https://ollama.com/install.sh | sh
    - name: Start Ollama Server
      run: ollama serve &
    - name: Pull Model
      run: ollama pull phi3:mini
    - name: Call Ollama API
      run: |
        curl -d '{"model": "phi3:mini", "stream": false, "prompt":"Whatever I say, answer with Yes"}' http://localhost:11434/api/generate
```

## Troubleshooting

- **Slack Bot not responding**: Ensure Slack tokens are correctly set in the `.env` file.
- **Ollama API errors**: Check if Ollama is running and accessible on the specified port.
- **Trello API issues**: Verify Trello API credentials and ensure the specified board ID is correct.
- **Google API errors**: Ensure `credentials_gmail.json` and `credentials_calendar.json` files are in the root directory.

## Contributing

Feel free to submit issues and pull requests. Contributions are welcome!

## License

This project is licensed under the MIT License.
```

