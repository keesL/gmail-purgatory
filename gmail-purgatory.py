import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
PURGATORY_LABEL="00-Purgatory"
ALLOWED_ADDRESSES = ["leune@adelphi.edu"]

def main():
  """Based on Google Quickstart.py
  """
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "credentials.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("token.json", "w") as token:
      token.write(creds.to_json())

  try:
    # Call the Gmail API
    service = build("gmail", "v1", credentials=creds)

    # fetch the purgatory label
    results = service.users().labels().list(userId="me").execute()
    label_id = [label['id'] for label in results.get("labels", []) if label['name'] == PURGATORY_LABEL]
    if len(label_id) == 0:
        print(f"Unable to find label {PURGATORY_LABEL}.")
        return
    label_id = label_id[0]

    # Get all message in the Inbox and return their IDs
    results = service.users().messages().list(userId="me", labelIds = ["INBOX"]).execute()
    message_ids = results.get("messages", [])
    if not message_ids:
        print("No messages found.")
        return
    messages = []

    """ 
    Helper function for batch processing
    """
    def add_message_to_batch(id, msg, err):
        # id is given because this will not be called in the same order
        if err:
            print(err)
        else:
            messages.append(msg)

    batch = service.new_batch_http_request()
    for msg in message_ids:
        batch.add(service.users().messages().get(userId='me', id=msg['id']), add_message_to_batch)
    batch.execute()

    # determine if message needs to be purgatoried
    purgatory_staging=[]
    for message in messages:
        headers=message['payload']['headers']
        hit = False
        to=subject=frm=None
        for h in headers:
            # extract relevant headers
            if h['name'] == 'To': to = h['value'].lower()
            elif h['name'] == 'Subject': subject = h['value']
            elif h['name'] == 'From': frm=h['value'].lower()
            
        if not (to and frm and subject):
            print(f'Unable to parge message.')
            purgatory_staging.append(message['id'])
        else:
            accept=False
            for allowed in ALLOWED_ADDRESSES:
              if allowed in to and "adelphi.edu" in frm:
                print(f'[accepted]   From: {frm}: {subject}')
                accept=True

            if not accept:
                print(f'[PURGATORY]  From: {frm}: {subject}')
                purgatory_staging.append(message['id'])
    
    
    if len(purgatory_staging) > 0:
      print(f"Applying {label_id} to and removing  INBOX from: {purgatory_staging}")

      operations = {
        "removeLabelIds": ["INBOX"],
        "ids": purgatory_staging,
        "addLabelIds": [label_id]
      }
      results = service.users().messages().batchModify(userId="me", body=operations).execute()

  except HttpError as error:
    # TODO(developer) - Handle errors from gmail API.
    print(f"An error occurred: {error}")


if __name__ == "__main__":
  main()