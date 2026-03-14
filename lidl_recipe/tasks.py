import sys
from datetime import datetime


TASKS_SCOPES = ["https://www.googleapis.com/auth/tasks"]


def get_tasks_service(config):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if config.tasks_token_file.exists():
        creds = Credentials.from_authorized_user_file(str(config.tasks_token_file), TASKS_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not config.tasks_credentials_file.exists():
                print(f"Missing {config.tasks_credentials_file}")
                print("Download OAuth client credentials from https://console.cloud.google.com/apis/credentials")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(config.tasks_credentials_file), TASKS_SCOPES)
            creds = flow.run_local_server(port=8085)
        with open(config.tasks_token_file, "w") as f:
            f.write(creds.to_json())

    return build("tasks", "v1", credentials=creds)


def create_shopping_list(items: list[dict], config):
    service = get_tasks_service(config)

    today = datetime.now().strftime("%d.%m.%Y")
    list_title = f"Lidl promocje {today}"

    tasklist = service.tasklists().insert(body={"title": list_title}).execute()
    tasklist_id = tasklist["id"]
    print(f"\nCreated task list: {list_title}")

    for item in items:
        valid_until = item.get("valid_until")
        date_suffix = f" (do {valid_until.strftime('%d.%m')})" if valid_until else ""
        task_body = {"title": f"{item['title']}{date_suffix}"}
        if item["description"]:
            task_body["notes"] = item["description"]
        service.tasks().insert(tasklist=tasklist_id, body=task_body).execute()
        desc = f" ({item['description'].split(chr(10))[0]})" if item["description"] else ""
        print(f"  + {item['title']}{date_suffix}{desc}")

    print(f"\n{len(items)} items added to Google Tasks")
