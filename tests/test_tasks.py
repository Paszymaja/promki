from unittest.mock import MagicMock, call, patch

from lidl_recipe.config import Config
from lidl_recipe.tasks import create_shopping_list


@patch("lidl_recipe.tasks.get_tasks_service")
def test_create_shopping_list_creates_list_and_tasks(mock_get_service):
    service = MagicMock()
    mock_get_service.return_value = service

    service.tasklists().insert().execute.return_value = {"id": "list-1"}

    items = [
        {"title": "Ser Gouda", "description": "2.99 zł"},
        {"title": "Mleko UHT", "description": ""},
    ]

    config = Config(access_token="test")
    create_shopping_list(items, config)

    # Verify tasklist was created with correct title format
    tasklist_call = service.tasklists().insert.call_args
    body = tasklist_call.kwargs["body"]
    assert body["title"].startswith("Lidl promocje ")

    # Verify tasks were inserted
    assert service.tasks().insert().execute.call_count == 2


@patch("lidl_recipe.tasks.get_tasks_service")
def test_create_shopping_list_includes_notes_for_description(mock_get_service):
    service = MagicMock()
    mock_get_service.return_value = service
    service.tasklists().insert().execute.return_value = {"id": "list-1"}

    items = [{"title": "Ser Gouda", "description": "2.99 zł"}]
    config = Config(access_token="test")
    create_shopping_list(items, config)

    task_call = service.tasks().insert.call_args
    body = task_call.kwargs["body"]
    assert body["title"] == "Ser Gouda"
    assert body["notes"] == "2.99 zł"


@patch("lidl_recipe.tasks.get_tasks_service")
def test_create_shopping_list_no_notes_when_empty_description(mock_get_service):
    service = MagicMock()
    mock_get_service.return_value = service
    service.tasklists().insert().execute.return_value = {"id": "list-1"}

    items = [{"title": "Mleko UHT", "description": ""}]
    config = Config(access_token="test")
    create_shopping_list(items, config)

    task_call = service.tasks().insert.call_args
    body = task_call.kwargs["body"]
    assert body["title"] == "Mleko UHT"
    assert "notes" not in body
