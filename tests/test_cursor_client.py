"""Unit tests for CursorClient."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from cursor.client import (
    CursorAPIError,
    CursorClient,
    CursorTimeoutError,
)
from cursor.schemas import RunResponse, RunStatus, TaskResponse


@pytest.fixture
def client():
    """Create a CursorClient instance for testing."""
    return CursorClient(api_key="test_key", base_url="https://api.test.com")


@pytest.fixture
def mock_response():
    """Create a mock HTTP response."""
    response = MagicMock()
    response.json.return_value = {}
    response.raise_for_status = MagicMock()
    return response


@pytest.mark.asyncio
async def test_create_task_success(client, mock_response):
    """Test successful task creation."""
    task_data = {"id": "task_123", "title": "Test Task", "description": "Test Description"}
    mock_response.json.return_value = task_data

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        task = await client.create_task("Test Task", "Test Description")

        assert isinstance(task, TaskResponse)
        assert task.id == "task_123"
        assert task.title == "Test Task"
        assert task.description == "Test Description"
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_create_task_api_error(client):
    """Test task creation with API error."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_response
        )

        with pytest.raises(CursorAPIError) as exc_info:
            await client.create_task("Test Task", "Test Description")

        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_run_success(client, mock_response):
    """Test successful run creation."""
    run_data = {
        "id": "run_123",
        "status": "running",
        "output": None,
        "error": None,
    }
    mock_response.json.return_value = run_data

    with patch.object(client.client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        run = await client.create_run("task_123", "plan", "Test instructions")

        assert isinstance(run, RunResponse)
        assert run.id == "run_123"
        assert run.status == RunStatus.RUNNING
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_get_run_success(client, mock_response):
    """Test successful run retrieval."""
    run_data = {
        "id": "run_123",
        "status": "completed",
        "output": "Test output",
        "error": None,
    }
    mock_response.json.return_value = run_data

    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        run = await client.get_run("task_123", "run_123")

        assert isinstance(run, RunResponse)
        assert run.id == "run_123"
        assert run.status == RunStatus.COMPLETED
        assert run.output == "Test output"


@pytest.mark.asyncio
async def test_wait_run_completed(client):
    """Test waiting for run that completes immediately."""
    completed_run_data = {
        "id": "run_123",
        "status": "completed",
        "output": "Test output",
        "error": None,
    }

    mock_response = MagicMock()
    mock_response.json.return_value = completed_run_data
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        run = await client.wait_run("task_123", "run_123", timeout=300, poll_interval=5)

        assert run.status == RunStatus.COMPLETED
        assert run.output == "Test output"
        # Should only call once since it's already completed
        assert mock_get.call_count == 1


@pytest.mark.asyncio
async def test_wait_run_polling(client):
    """Test waiting for run with polling."""
    running_run_data = {
        "id": "run_123",
        "status": "running",
        "output": None,
        "error": None,
    }
    completed_run_data = {
        "id": "run_123",
        "status": "completed",
        "output": "Test output",
        "error": None,
    }

    mock_response_running = MagicMock()
    mock_response_running.json.return_value = running_run_data
    mock_response_running.raise_for_status = MagicMock()

    mock_response_completed = MagicMock()
    mock_response_completed.json.return_value = completed_run_data
    mock_response_completed.raise_for_status = MagicMock()

    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [mock_response_running, mock_response_completed]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            run = await client.wait_run("task_123", "run_123", timeout=300, poll_interval=5)

        assert run.status == RunStatus.COMPLETED
        assert run.output == "Test output"
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_wait_run_failed(client):
    """Test waiting for run that fails."""
    failed_run_data = {
        "id": "run_123",
        "status": "failed",
        "output": None,
        "error": "Test error",
    }

    mock_response = MagicMock()
    mock_response.json.return_value = failed_run_data
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        with pytest.raises(CursorAPIError) as exc_info:
            await client.wait_run("task_123", "run_123", timeout=300, poll_interval=5)

        assert "Test error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_wait_run_timeout(client):
    """Test waiting for run that times out."""
    running_run_data = {
        "id": "run_123",
        "status": "running",
        "output": None,
        "error": None,
    }

    mock_response = MagicMock()
    mock_response.json.return_value = running_run_data
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        # Mock time to simulate timeout
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop_instance = MagicMock()
            mock_loop.return_value = mock_loop_instance
            # Simulate timeout by making elapsed time exceed timeout
            mock_loop_instance.time.side_effect = [0, 301]  # Start at 0, then 301 seconds

            with pytest.raises(CursorTimeoutError):
                await client.wait_run("task_123", "run_123", timeout=300, poll_interval=5)


@pytest.mark.asyncio
async def test_close(client):
    """Test closing the client."""
    with patch.object(client.client, "aclose", new_callable=AsyncMock) as mock_close:
        await client.close()
        mock_close.assert_called_once()

