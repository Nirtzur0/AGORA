"""
Shared agent task schema and constants.

This module is the canonical source for agent task payload structure,
task statuses, and role names across services.
"""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RoleName(str, Enum):
    MAINTAINER = "Maintainer"
    LITERATURE_ANALYST = "Literature Analyst"
    EXPERIMENTALIST = "Experimentalist"
    METHOD_REVIEWER = "Method Reviewer"
    SKEPTIC = "Skeptic"
    SYNTHESIZER = "Synthesizer"


class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskInput(BaseModel):
    """Version-pinned input for a task."""
    artifact_version_id: str = Field(..., description="UUID of artifact_versions.id")
    location: Optional[str] = Field(None, description="Optional evidence location")
    label: Optional[str] = Field(None, description="Optional display label")


class TaskPayload(BaseModel):
    """Structured task payload stored in agent_tasks.payload."""
    model_config = ConfigDict(extra="allow")

    objective: str = Field(..., description="Single-sentence task goal")
    inputs: List[TaskInput] = Field(..., description="Version-pinned inputs")
    required_outputs: List[str] = Field(..., description="Required outputs (e.g., claim.create)")
    context_links: Optional[List[Dict[str, Any]]] = Field(None, description="Related items")
    acceptance_criteria: Optional[List[str]] = Field(None, description="Completion checks")
    priority: Optional[str] = Field(None, description="low|medium|high|urgent")


class TaskResultLink(BaseModel):
    """Result link returned by agent when completing a task."""
    type: str = Field(..., description="Result type (claim|artifact|draft|critique|log)")
    id: str = Field(..., description="UUID of referenced item")
    note: Optional[str] = Field(None, description="Optional note")


TASK_STATUS_VALUES = {status.value for status in TaskStatus}
ROLE_NAME_VALUES = {role.value for role in RoleName}
