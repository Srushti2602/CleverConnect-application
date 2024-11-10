import ollama
import logging
import re  # Import re for regex

def is_meeting_email(email_content):
    """
    Check if the email content is related to a meeting.
    """
    meeting_keywords = ["meeting", "appointment", "call", "conference", "discussion", "scheduled"]
    for keyword in meeting_keywords:
        if re.search(rf'\b{keyword}\b', email_content, re.IGNORECASE):
            return True
    return False

def extract_meeting_details(email_content):
    """
    Extract the meeting date, time, and description from the provided email content using Ollama.
    """
    prompt = f"""
    Extract meeting details (date, time, and purpose) only if the text indicates a scheduled meeting. 
    Ignore job alerts, newsletters, and any unrelated emails.
    
    Example text: "You have a meeting scheduled on November 9 2024 at 9 pm about project updates."
    Expected format: {{'date': 'November 9 2024', 'time': '9 pm', 'description': 'project updates'}}
    
    Text: {email_content}
    """
    try:
        response = ollama.generate(model="llama3.2", prompt=prompt)
        result = response.get('response')
        if result:
            try:
                details = eval(result)
                return details
            except Exception as e:
                logging.error(f"Error parsing Ollama response: {e}")
                return {'date': None, 'time': None, 'description': None}
        else:
            return {'date': None, 'time': None, 'description': None}
    except Exception as e:
        logging.error(f"Error in Ollama model generation: {e}")
        return {'date': None, 'time': None, 'description': None}

# Main function to process emails and add meeting details to Trello
def process_emails_and_add_to_trello(list_name="To Do"):
    emails = get_recent_emails(num_emails=5)  # Fetch recent emails
    for email in emails:
        # Use is_meeting_email to filter only meeting-related emails
        if is_meeting_email(email["Snippet"]):
            details = extract_meeting_details(email["Snippet"])
            
            # Add to Trello if valid details are extracted
            if details['date'] and details['time'] and details['description']:
                add_event_to_trello(list_name, details['description'], details['date'], details['time'])
            else:
                logging.warning("Incomplete meeting details; skipping addition to Trello.")
        else:
            logging.info("Non-meeting email detected and ignored.")
