
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv
import os
import datetime
import logging
from trello import TrelloClient
import ollama
import ast
import re

# Load environment variables
load_dotenv()
OLLAMA_URL = "http://ollama:11434"

# Initialize Slack Bolt app with OAuth tokens
app = App(token=os.getenv("SLACK_BOT_TOKEN"))

# Set up a logger for debugging
logging.basicConfig(level=logging.DEBUG)

# Gmail and Calendar API Scopes
SCOPES_GMAIL = ['https://www.googleapis.com/auth/gmail.readonly']
SCOPES_CALENDAR = ['https://www.googleapis.com/auth/calendar.readonly']

# Authenticate Gmail (read capabilities)
def authenticate_gmail():
    creds = None
    if os.path.exists('token_gmail.json'):
        creds = Credentials.from_authorized_user_file('token_gmail.json', SCOPES_GMAIL)
    if not creds or not creds.valid:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file('credentials_gmail.json', SCOPES_GMAIL)
        creds = flow.run_local_server(port=0)
        with open('token_gmail.json', 'w') as token:
            token.write(creds.to_json())
    return creds

# Authenticate Google Calendar
def authenticate_calendar():
    creds = None
    if os.path.exists('token_calendar.json'):
        creds = Credentials.from_authorized_user_file('token_calendar.json', SCOPES_CALENDAR)
    if not creds or not creds.valid:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file('credentials_calendar.json', SCOPES_CALENDAR)
        creds = flow.run_local_server(port=0)
        with open('token_calendar.json', 'w') as token:
            token.write(creds.to_json())
    return creds

# Fetch Google Calendar events
def get_upcoming_calendar_events(max_results=5):
    creds = authenticate_calendar()
    service = build('calendar', 'v3', credentials=creds)
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=max_results, singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    return [{"summary": event.get("summary", "No Title"), "start": event["start"].get("dateTime", event["start"].get("date"))} for event in events]

# Authenticate Trello
def authenticate_trello():
    return TrelloClient(
        api_key=os.getenv('TRELLO_API_KEY'),
        api_secret=os.getenv('TRELLO_API_SECRET'),
        token=os.getenv('TRELLO_TOKEN'),
    )

# Function to get a Trello list by name
def get_list_by_name(list_name):
    client = authenticate_trello()
    board = client.get_board(os.getenv('TRELLO_BOARD_ID'))
    for trello_list in board.all_lists():
        if trello_list.name.lower() == list_name.lower():
            return trello_list
    return None
def parse_meeting_details(response_text):
    # Using regex to find a date and time pattern
    date_match = re.search(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}', response_text)
    time_match = re.search(r'\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\b', response_text)
    description_match = re.search(r'(?:about|regarding)\s+(.+)', response_text)  # Removed look-behind

    date = date_match.group(0) if date_match else None
    time = time_match.group(0) if time_match else None
    description = description_match.group(1).strip() if description_match else "Meeting"

    return date, time, description

# Function to create a new Trello list
def create_list_on_board(list_name):
    client = authenticate_trello()
    board = client.get_board(os.getenv('TRELLO_BOARD_ID'))
    try:
        return board.add_list(list_name)
    except Exception as e:
        logging.error(f"Error creating list '{list_name}': {e}")
        return None

# Function to fetch tasks from a Trello list
def get_tasks_from_list_by_name(list_name):
    trello_list = get_list_by_name(list_name)
    if trello_list:
        tasks = []
        for card in trello_list.list_cards():
            due_date = card.due_date
            if due_date and isinstance(due_date, datetime.datetime):
                due_date = due_date.strftime('%Y-%m-%d %H:%M:%S')
            else:
                due_date = 'No due date'
            tasks.append({"name": card.name, "due": due_date, "url": card.shortUrl})
        return tasks
    else:
        logging.error(f"Could not retrieve tasks for list '{list_name}'.")
    return []

# Add a task to a Trello list
def add_task_to_list_by_name(list_name, task_name, due_date=None):
    trello_list = get_list_by_name(list_name)
    if trello_list:
        try:
            card = trello_list.add_card(task_name)
            if due_date:
                card.set_due(due_date)
            logging.info(f"Added task '{task_name}' to list '{list_name}' with due date '{due_date}'.")
            return card
        except Exception as e:
            logging.error(f"Error adding task to Trello: {e}")
            return None
    else:
        logging.error(f"Failed to add task '{task_name}' to list '{list_name}' because the list was not found.")
    return None


# Function to remove a task from a Trello list
def remove_task_from_list_by_name(list_name, task_name):
    trello_list = get_list_by_name(list_name)
    if trello_list:
        for card in trello_list.list_cards():
            if card.name.lower() == task_name.lower():
                card.delete()
                logging.info(f"Removed task '{task_name}' from list '{list_name}'.")
                return True
    logging.warning(f"Task '{task_name}' not found in list '{list_name}'.")
    return False

# Function to sync Google Calendar events to a Trello list
def sync_calendar_to_trello(list_name="Calendar Events"):
    events = get_upcoming_calendar_events()
    trello_list = get_list_by_name(list_name)
    if trello_list:
        for event in events:
            event_name = event["summary"]
            start_time = event["start"]
            if start_time:
                try:
                    start_time = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                except ValueError:
                    start_time = None
            if not any(card.name == event_name for card in trello_list.list_cards()):
                trello_list.add_card(name=event_name, due=start_time)
    else:
        logging.error(f"Trello list '{list_name}' not found.")
    return events
def is_meeting_email(email_content):
    # Expanded set of keywords commonly associated with meetings
    meeting_keywords = ["meeting", "scheduled", "appointment", "conference", "call", "discussion", "event", "session"]
    for keyword in meeting_keywords:
        if re.search(rf'\b{keyword}\b', email_content, re.IGNORECASE):
            return True
    return False


def get_recent_emails(num_emails=5):
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me', maxResults=num_emails).execute()
    messages = results.get('messages', [])
    
    emails = []
    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        headers = msg.get("payload", {}).get("headers", [])
        email_info = {
            "From": next((header['value'] for header in headers if header['name'] == "From"), "Unknown"),
            "To": next((header['value'] for header in headers if header['name'] == "To"), "Unknown"),
            "Subject": next((header['value'] for header in headers if header['name'] == "Subject"), "No Subject"),
            "Snippet": msg.get("snippet", "")
        }
        emails.append(email_info)
    return emails


import requests

def extract_meeting_details(email_content):
    """
    Extract meeting details (date, time, and purpose) from the email content using Ollama.
    Only return details if the content indicates a scheduled meeting.
    """
    prompt = f"""
    Extract meeting details (date, time, and purpose) only if the text indicates a scheduled meeting. 
    Ignore job alerts, newsletters, and any unrelated emails.

    Example text: "You have a meeting scheduled on November 9 2024 at 9 pm about project updates."
    Expected format: {{'date': 'November 9 2024', 'time': '9 pm', 'description': 'project updates'}}
    
    Text: {email_content}
    """
    
    try:
        # Make a POST request to the Ollama API
        response = requests.post(
            f"{OLLAMA_URL}/models/llama3.2/run",
            json={"prompt": prompt}
        )
        response.raise_for_status()  # Raise an error for bad responses
        
        # Parse response from Ollama
        result = response.json().get('response', '')
        
        # Process and parse the JSON response
        details = ast.literal_eval(result.strip())
        if details.get('date') and details.get('time') and details.get('description'):
            return details
    except Exception as e:
        logging.error(f"Error interacting with Ollama API: {e}")
    return None


def process_emails_and_add_to_trello(list_name="Meetings"):
    emails = get_recent_emails(num_emails=5)
    logging.debug(f"Fetched {len(emails)} emails.")
    
    for email in emails:
        logging.debug(f"Processing email: {email}")
        
        if is_meeting_email(email["Snippet"]):
            details = extract_meeting_details(email["Snippet"])
            if details:
                due_date_str = f"{details['date']} {details['time']}"
                try:
                    due_date_parsed = datetime.datetime.strptime(due_date_str, "%B %d %Y %I %p")
                    logging.info(f"Adding meeting to Trello: {details['description']} on {due_date_parsed}")
                    add_task_to_list_by_name(list_name, details['description'], due_date_parsed)
                    logging.info(f"Successfully added '{details['description']}' to Trello under '{list_name}'.")
                except ValueError as e:
                    logging.error(f"Error parsing due date '{due_date_str}': {e}")
            else:
                logging.warning("Incomplete meeting details; skipping addition to Trello.")
        else:
            logging.info("Non-meeting email detected and ignored.")



def add_event_to_trello(list_name, description, date, time):
    trello_list = get_list_by_name(list_name)
    if trello_list:
        due_date = None
        if date and time:
            try:
                due_date_str = f"{date} {time}"
                due_date = datetime.strptime(due_date_str, "%B %d %Y %I:%M %p")  # Adjust the date format if needed
            except ValueError as e:
                print(f"Error parsing date and time: {e}")

        # Create Trello card
        card = trello_list.add_card(name=description, due=due_date)
        print(f"Added event to Trello: {description} with due date {due_date}")
    else:
        print(f"Trello list '{list_name}' not found.")
prompt = "Extract meeting details from email content."
# Main code to process response from Ollama and add to Trello
try:
    for response in ollama.generate(model="llama3.2", prompt=prompt):
        print("Response from Ollama:", response)
        # Parse the response text for meeting details
        date, time, description = parse_meeting_details(response)
        # Add to Trello if date and description are present
        if description:
            add_event_to_trello("To Do", description, date, time)
        else:
            print("No valid meeting details found in the response.")
except Exception as e:
    print(f"Error: {e}")


# Slack message event handler
@app.event("message")
def handle_message_events(body, say):
    text = body.get("event", {}).get("text", "").lower()
    match = re.search(r"(show|fetch|get|display)\s+(?:me\s+)?recent\s+(\d+)?\s+emails?", text)
    if match:
        try:
            # If a number is specified, use it; otherwise, default to 5
            num_emails = int(match.group(2)) if match.group(2) else 5
        except ValueError:
            num_emails = 5  # Default to 5 if there's an error

        # Fetch recent emails
        emails = get_recent_emails(num_emails)
        if emails:
            for email in emails:
                say(f"*From:* {email['From']}\n*Subject:* {email['Subject']}\n*Snippet:* {email['Snippet']}")
        else:
            say("No recent emails found.")
    if text == "hi":
        say("Hello! Here are the commands you can use:\n" +
            "- `show me recent <number> emails`: Shows recent emails\n" +
            "- `show me my to do list`: Shows your To Do list\n" +
            "- `show me my doing list`: Shows your Doing list\n" +
            "- `show me my done list`: Shows your Done list\n" +
            "- `show me my sephora list`: Shows tasks in your Sephora list\n" +
            "- `add event in <list_name> list <event_name> by <due_date>`: Adds an event to a Trello list\n" +
            "- `remove <task_name> from <list_name> list`: Removes a task from a specified list\n" +
            "- `create new list <list_name>`: Creates a new list on Trello\n" +
            "- `sync calendar to trello`: Syncs Google Calendar events to a Trello list\n" +
            "- `show me my events`: Shows your combined Trello tasks and Google Calendar events\n" +
            "- `process recent emails for meetings`: Extracts meetings from emails and adds to Trello")

    elif "show me recent" in text and "emails" in text:
        try:
            num_emails = int(text.split("recent")[1].split("emails")[0].strip())
        except ValueError:
            num_emails = 5
        emails = get_recent_emails(num_emails)
        if emails:
            for email in emails:
                say(f"*From:* {email['From']}\n*Subject:* {email['Subject']}\n*Snippet:* {email['Snippet']}")
        else:
            say("No recent emails found.")
    # Show list commands (To Do, Doing, Done, Sephora)
    elif re.search(r"(show|display|fetch|get|list)\s+me\s+my\s+(to do|doing|done|sephora)\s+list", text):
        list_name = re.search(r"(to do|doing|done|sephora)", text).group(1).strip()
        tasks = get_tasks_from_list_by_name(list_name)
        if tasks:
            for task in tasks:
                due_date = task['due']
                say(f"*Task:* {task['name']}\n*Due:* {due_date}\n*Link:* {task['url']}")
        else:
            say(f"Your {list_name} list is empty or could not be found.")

    # Add event in list command
    elif re.search(r"add\s+event\s+in\s+(\w+)\s+list\s+(.+?)\s+by\s+(\d{4}-\d{2}-\d{2})", text):
        match = re.search(r"add\s+event\s+in\s+(\w+)\s+list\s+(.+?)\s+by\s+(\d{4}-\d{2}-\d{2})", text)
        list_name, event_name, due_date_str = match.groups()
        try:
            due_date = datetime.datetime.strptime(due_date_str, "%Y-%m-%d")
            card = add_task_to_list_by_name(list_name, event_name, due_date)
            if card:
                say(f"Event '{event_name}' added to '{list_name}' list on Trello.")
            else:
                say(f"List '{list_name}' not found on Trello.")
        except ValueError:
            say("Invalid due date format. Please use YYYY-MM-DD.")

    # Remove task from list command
    elif re.search(r"remove\s+(.+?)\s+from\s+(\w+)\s+list", text):
        match = re.search(r"remove\s+(.+?)\s+from\s+(\w+)\s+list", text)
        task_name, list_name = match.groups()
        if remove_task_from_list_by_name(list_name, task_name):
            say(f"Task '{task_name}' removed from '{list_name}' list.")
        else:
            say(f"Task '{task_name}' not found in '{list_name}' list.")

    elif "process recent emails for meetings" in text:
        process_emails_and_add_to_trello()
        say("Processed recent emails and added meetings to Trello.")

    elif "show me my" in text and "list" in text:
        list_name = text.split("show me my")[1].split("list")[0].strip()
        tasks = get_tasks_from_list_by_name(list_name)
        if tasks:
            for task in tasks:
                due_date = task['due']
                say(f"*Task:* {task['name']}\n*Due:* {due_date}\n*Link:* {task['url']}")
        else:
            say(f"Your {list_name} list is empty or could not be found.")

    elif text.startswith("add event in"):
        try:
            parts = text.replace("add event in", "").strip().split(" list ")
            list_name = parts[0].strip()
            event_info = parts[1].strip() if len(parts) > 1 else ""
            if event_info:
                event_parts = event_info.split(" by ")
                event_name = event_parts[0].strip()
                due_date = None
                if len(event_parts) > 1:
                    due_date_str = event_parts[1].strip()
                    try:
                        due_date = datetime.datetime.strptime(due_date_str, "%Y-%m-%d")
                    except ValueError:
                        say("Invalid due date format. Please use YYYY-MM-DD.")
                        return
                card = add_task_to_list_by_name(list_name, event_name, due_date)
                if card:
                    say(f"Event '{event_name}' added to '{list_name}' list on Trello.")
                else:
                    say(f"List '{list_name}' not found on Trello.")
            else:
                say("Please specify the event name after the list name.")
        except Exception as e:
            logging.error(f"Error processing add event command: {e}")
            say("There was an error processing your request. Please check the format and try again.")

    
    elif text.startswith("create new list"):
        list_name = text.replace("create new list", "").strip()
        if list_name:
            new_list = create_list_on_board(list_name)
            if new_list:
                say(f"List '{list_name}' has been created on Trello.")
            else:
                say("There was an issue creating the list. Please try again.")
        else:
            say("Please specify a name for the new list.")

    elif "sync calendar to trello" in text:
        sync_calendar_to_trello()
        say("Google Calendar events have been synced to the Trello list 'Calendar Events'.")

    elif "show me my events" in text:
        tasks = get_tasks_from_list_by_name("Calendar Events") + get_tasks_from_list_by_name("To Do")
        if tasks:
            for task in tasks:
                due_date = task['due']
                say(f"*Task:* {task['name']}\n*Due:* {due_date}\n*Link:* {task['url']}")
        else:
            say("No events found in Trello or Calendar.")

# Start the Slack app
if __name__ == "__main__":
    handler = SocketModeHandler(app, os.getenv("APP_LEVEL_WRITE_TOKEN"))
    handler.start()
