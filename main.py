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

# Authenticate Trello
def authenticate_trello():
    client = TrelloClient(
        api_key=os.getenv('TRELLO_API_KEY'),
        api_secret=os.getenv('TRELLO_API_SECRET'),
        token=os.getenv('TRELLO_TOKEN'),
    )
    return client

# Function to get a list by name
def get_list_by_name(list_name):
    client = authenticate_trello()
    board_id = os.getenv('TRELLO_BOARD_ID')
    board = client.get_board(board_id)
    for trello_list in board.all_lists():
        if trello_list.name.lower() == list_name.lower():
            return trello_list
    return None


# Function to fetch tasks from a list by name
def add_task_to_list_by_name(list_name, task_name, due_date=None):
    trello_list = get_list_by_name(list_name)
    if trello_list:
        card = trello_list.add_card(task_name)
        if due_date:
            card.set_due(due_date)
        return card
    else:
        return None



# Function to remove a task from a list by name
def remove_task_from_list_by_name(list_name, task_name):
    trello_list = get_list_by_name(list_name)
    if trello_list:
        for card in trello_list.list_cards():
            if card.name.lower() == task_name.lower():
                card.delete()
                return True
    return False

def create_list_on_board(list_name):
    client = authenticate_trello()
    board_id = os.getenv('TRELLO_BOARD_ID')
    board = client.get_board(board_id)
    # Create a new list on the board
    try:
        new_list = board.add_list(list_name)
        return new_list
    except Exception as e:
        logging.error(f"Error creating list '{list_name}': {e}")
        return None

def get_tasks_from_list_by_name(list_name):
    trello_list = get_list_by_name(list_name)
    if trello_list:
        tasks = []
        for card in trello_list.list_cards():
            # Check if due_date is a datetime object before formatting
            due_date = (
                card.due_date.strftime('%Y-%m-%d %H:%M:%S')
                if isinstance(card.due_date, datetime.datetime)
                else card.due_date or 'No due date'
            )
            tasks.append({"name": card.name, "due": due_date, "url": card.shortUrl})
        return tasks
    else:
        return None
tasks = get_tasks_from_list_by_name("sephora")
if not tasks:
    print("Your Sephora list is empty or could not be found.")
else:
    for task in tasks:
        due = task['due'] if isinstance(task['due'], str) else task['due'].strftime('%Y-%m-%d %H:%M:%S')
        print(f"*Task:* {task['name']}\n*Due:* {due}\n*Link:* {task['url']}\n")

# Fetch recent emails with added debug logs
def get_recent_emails(num_emails=5):
    try:
        logging.info("Authenticating Gmail...")
        creds = authenticate_gmail()
        service = build('gmail', 'v1', credentials=creds)
        logging.info(f"Fetching the last {num_emails} emails...")
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
            logging.info(f"Email fetched: {email_info}")
            emails.append(email_info)
        return emails
    except Exception as e:
        logging.error(f"An error occurred while fetching emails: {e}")
        return []

# Handle Slack events for commands
@app.event("message")
def handle_message_events(body, logger, say):
    logger.info("Message event received!")
    event = body.get("event", {})
    text = event.get("text", "").lower()
    user = event.get("user")

    if user and "subtype" not in event:
        # Respond to "hi" with a list of available commands
        if text == "hi":
            say(
                "Hello! Here are the commands you can use:\n"
                "- `show me recent <number> emails`: Shows your recent emails\n"
                "- `add event in <list_name> list <event_name> by <due_date>`: Adds an event to a Trello list\n"
                "- `show me my to do list`: Shows tasks in your To Do list\n"
                "- `show me my doing list`: Shows tasks in your Doing list\n"
                "- `show me my done list`: Shows tasks in your Done list\n"
                "- `show me my sephora list`: Shows tasks in your Sephora list\n"
                "- `create new list <list_name>`: Creates a new list on Trello\n"
                "- `remove <task_name> from <list_name> list`: Removes a task from a specified list"
            )

        # Command to show the Sephora list
        elif "show me my sephora list" in text:
            say("Fetching your Sephora list...")
            tasks = get_tasks_from_list_by_name("sephora")
            if not tasks:
                say("Your Sephora list is empty or could not be found.")
            else:
                for task in tasks:
                    due = task['due']
                    if due and isinstance(due, datetime.datetime):
                        due = due.strftime('%Y-%m-%d %H:%M:%S')
                    say(f"*Task:* {task['name']}\n*Due:* {due or 'No due date'}\n*Link:* {task['url']}\n")

        # Command to create a new list
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

        # Fetch recent emails based on specified number
        elif "recent" in text and "emails" in text:
            try:
                num_emails = int(text.split("recent")[1].split("emails")[0].strip())
            except ValueError:
                num_emails = 5  # Default to 5 if parsing fails
            say(f"Fetching your recent {num_emails} emails...")
            emails = get_recent_emails(num_emails)
            if not emails:
                say("No recent emails found or an error occurred.")
            else:
                for email in emails:
                    say(f"*From:* {email['From']}\n*To:* {email['To']}\n*Subject:* {email['Subject']}\n*Snippet:* {email['Snippet']}\n")

        # Add event to specified Trello list by name
        elif "add event in" in text:
            say("Adding a new event...")
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
                logger.error(f"Error processing add event command: {e}")
                say("There was an error processing your request. Please check the format and try again.")

        # Remove task from specified Trello list by name
        elif "remove" in text and "from" in text:
            try:
                parts = text.replace("remove", "").strip().split(" from ")
                task_name = parts[0].strip()
                list_name = parts[1].replace("list", "").strip()
                
                if remove_task_from_list_by_name(list_name, task_name):
                    say(f"Task '{task_name}' removed from '{list_name}' list.")
                else:
                    say(f"Task '{task_name}' not found in '{list_name}' list.")
            except Exception as e:
                logger.error(f"Error processing remove task command: {e}")
                say("There was an error processing your request. Please check the format and try again.")
            
        elif "show me my to do list" in text:
            say("Fetching your To Do list...")
            tasks = get_tasks_from_list_by_name("To Do")
            if not tasks:
                say("Your To Do list is empty or could not be found.")
            else:
                for task in tasks:
                    due = task['due']
                    if due and isinstance(due, datetime.datetime):
                        due = due.strftime('%Y-%m-%d %H:%M:%S')
                    say(f"*Task:* {task['name']}\n*Due:* {due or 'No due date'}\n*Link:* {task['url']}\n")

        elif "show me my doing list" in text:
            say("Fetching your Doing list...")
            tasks = get_tasks_from_list_by_name("Doing")
            if not tasks:
                say("Your Doing list is empty or could not be found.")
            else:
                for task in tasks:
                    due = task['due']
                    if due and isinstance(due, datetime.datetime):
                        due = due.strftime('%Y-%m-%d %H:%M:%S')
                    say(f"*Task:* {task['name']}\n*Due:* {due or 'No due date'}\n*Link:* {task['url']}\n")

        elif "show me my done list" in text:
            say("Fetching your Done list...")
            tasks = get_tasks_from_list_by_name("Done")
            if not tasks:
                say("Your Done list is empty or could not be found.")
            else:
                for task in tasks:
                    due = task['due']
                    if due and isinstance(due, datetime.datetime):
                        due = due.strftime('%Y-%m-%d %H:%M:%S')
                    say(f"*Task:* {task['name']}\n*Due:* {due or 'No due date'}\n*Link:* {task['url']}\n")
        
        elif text.startswith("show me my") and "list" in text:
            list_name = text.replace("show me my", "").replace("list", "").strip()
            say(f"Fetching your {list_name} list...")
            tasks = get_tasks_from_list_by_name(list_name)
            if not tasks:
                say(f"Your {list_name} list is empty or could not be found.")
            else:
                for task in tasks:
                    due = task['due']
                    if due and isinstance(due, datetime.datetime):
                        due = due.strftime('%Y-%m-%d %H:%M:%S')
                    say(f"*Task:* {task['name']}\n*Due:* {due or 'No due date'}\n*Link:* {task['url']}\n")
        
        # Command to create a new list
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


        

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.getenv("APP_LEVEL_WRITE_TOKEN"))
    handler.start()
