"""Pydantic schemas for Cursor API requests and responses."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """Run status enumeration."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class CreateTaskRequest(BaseModel):
    """Request model for creating a task (agent)."""

    prompt: dict = Field(..., description="Prompt object with text")
    source: dict = Field(..., description="Source object with repository")


class CreateRunRequest(BaseModel):
    """Request model for creating a run."""

    action: str = Field(..., description="Action type: plan, ask, or code_generate")
    instructions: str = Field(..., description="User instructions for the run")


class TaskResponse(BaseModel):
    """Response model for a task."""

    id: str = Field(..., description="Task ID")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")


class RunResponse(BaseModel):
    """Response model for a run."""

    id: str = Field(..., description="Run ID")
    status: RunStatus = Field(..., description="Run status")
    output: Optional[str] = Field(None, description="Run output if completed")
    error: Optional[str] = Field(None, description="Error message if failed")

