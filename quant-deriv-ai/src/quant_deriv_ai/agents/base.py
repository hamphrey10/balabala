"""Abstract agent interfaces — no trading strategy logic here."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from quant_deriv_ai.core.event_bus import EventBus
from quant_deriv_ai.core.exceptions import AgentError


class AgentState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class AgentContext(BaseModel):
    """Shared runtime context passed into agents."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    name: str
    bus: EventBus
    config: dict[str, Any] = Field(default_factory=dict)


class BaseAgent(ABC):
    """Minimal agent lifecycle. Subclasses implement ``run`` / ``shutdown``."""

    def __init__(self, context: AgentContext) -> None:
        self.context = context
        self._state = AgentState.CREATED

    @property
    def name(self) -> str:
        return self.context.name

    @property
    def state(self) -> AgentState:
        return self._state

    def start(self) -> None:
        if self._state is AgentState.RUNNING:
            msg = f"agent {self.name!r} already running"
            raise AgentError(msg)
        self._state = AgentState.RUNNING
        try:
            self.run()
        except Exception:
            self._state = AgentState.FAILED
            raise

    def stop(self) -> None:
        if self._state is AgentState.STOPPED:
            return
        self.shutdown()
        self._state = AgentState.STOPPED

    @abstractmethod
    def run(self) -> None:
        """Execute agent work (sync for LOT-001; async orchestration later)."""

    @abstractmethod
    def shutdown(self) -> None:
        """Release resources."""
