from ollama_email import extract_meeting_details

# Sample email snippet for testing
email_snippet = "You have a meeting scheduled tomorrow on November 9 2024 at 9 pm."

# Call the function and print the details
details = extract_meeting_details(email_snippet)
print("Extracted Details:", details)
