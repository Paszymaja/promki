import os
import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

TASKS_SCOPES = ["https://www.googleapis.com/auth/tasks"]
TASKS_TOKEN_FILE = str(_PROJECT_ROOT / "tasks_token.json")
TASKS_CREDENTIALS_FILE = str(_PROJECT_ROOT / "credentials.json")


def get_tasks_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TASKS_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TASKS_TOKEN_FILE, TASKS_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(TASKS_CREDENTIALS_FILE):
                print(f"Missing {TASKS_CREDENTIALS_FILE}")
                print("Download OAuth client credentials from https://console.cloud.google.com/apis/credentials")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(TASKS_CREDENTIALS_FILE, TASKS_SCOPES)
            creds = flow.run_local_server(port=8085)
        with open(TASKS_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("tasks", "v1", credentials=creds)


def create_shopping_list(items: list[dict]):
    service = get_tasks_service()

    today = datetime.now().strftime("%d.%m.%Y")
    list_title = f"Lidl promocje {today}"

    tasklist = service.tasklists().insert(body={"title": list_title}).execute()
    tasklist_id = tasklist["id"]
    print(f"\nCreated task list: {list_title}")

    for item in items:
        task_body = {"title": item["title"]}
        if item["description"]:
            task_body["notes"] = item["description"]
        service.tasks().insert(tasklist=tasklist_id, body=task_body).execute()
        desc = f" ({item['description'].split(chr(10))[0]})" if item["description"] else ""
        print(f"  + {item['title']}{desc}")

    print(f"\n{len(items)} items added to Google Tasks")
