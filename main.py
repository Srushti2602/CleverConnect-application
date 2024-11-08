from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv
import os
import datetime
import logging
from trello import TrelloClient

# Load environment variables
load_dotenv()

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

# Fetch recent emails
def get_recent_emails():
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me', maxResults=5).execute()
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

# Fetch upcoming events from Google Calendar
def get_upcoming_events():
    creds = authenticate_calendar()
    service = build('calendar', 'v3', credentials=creds)
    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    events_result = service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=5, singleEvents=True,
        orderBy='startTime').execute()
    events = events_result.get('items', [])
    
    event_list = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        event_list.append({
            "summary": event.get('summary', 'No Title'),
            "start": start,
            "location": event.get('location', 'No Location'),
            "description": event.get('description', 'No Description')
        })
    return event_list

# Trello Authentication
def authenticate_trello():
    client = TrelloClient(
        api_key=os.getenv('TRELLO_API_KEY'),
        api_secret=os.getenv('TRELLO_API_SECRET'),
        token=os.getenv('TRELLO_TOKEN'),
    )
    return client

# Add event as a Trello task to the "To do" list
def add_event_to_trello(event_name, due_date=None):
    client = authenticate_trello()
    list_id = "672c424c28f1b7a66d5b16f6"  # "To do" list ID
    trello_list = client.get_list(list_id)
    card = trello_list.add_card(event_name)
    if due_date:
        card.set_due(due_date)
    return card

# Handle Slack events for commands
@app.event("message")
def handle_message_events(body, logger, say):
    """Handles message events and performs actions based on specific keywords."""
    logger.info("Message event received!")
    event = body.get("event", {})
    text = event.get("text", "").lower()
    user = event.get("user")
    
    if user and "subtype" not in event:
        if "emails" in text:
            say("Fetching your recent emails...")
            emails = get_recent_emails()
            if not emails:
                say("No recent emails found.")
            else:
                for email in emails:
                    say(f"*From:* {email['From']}\n*To:* {email['To']}\n*Subject:* {email['Subject']}\n*Snippet:* {email['Snippet']}\n")
        
        elif "events" in text:
            say("Fetching your upcoming events...")
            events = get_upcoming_events()
            if not events:
                say("No upcoming events found.")
            else:
                for event in events:
                    say(f"*Event:* {event['summary']}\n*Start:* {event['start']}\n*Location:* {event['location']}\n*Description:* {event['description']}\n")
        
        elif "add event" in text:
            # Extract event name and optional due date from the message text
            say("Adding a new event to Trello...")
            event_info = text.replace("add event", "").strip()
            if event_info:
                parts = event_info.split(" by ")
                event_name = parts[0].strip()
                due_date = None
                if len(parts) > 1:
                    due_date_str = parts[1].strip()
                    try:
                        due_date = datetime.datetime.strptime(due_date_str, "%Y-%m-%d")
                    except ValueError:
                        say("Invalid due date format. Please use YYYY-MM-DD.")
                        return
                add_event_to_trello(event_name, due_date)
                say(f"Event '{event_name}' added to Trello 'To do' list.")
            else:
                say("Please specify the event name after 'add event'.")
    
    else:
        logger.info("Event subtype detected, ignoring.")

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.getenv("APP_LEVEL_WRITE_TOKEN"))
    handler.start()
