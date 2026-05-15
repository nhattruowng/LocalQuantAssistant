"""Base contracts for orchestration agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging

from agents.context import AgentContext
from config.settings import Settings


class AgentError(RuntimeError):
    """Raised when an agent cannot complete its responsibility."""


class BaseAgent(ABC):
    """Base class for deterministic pipeline agents."""

    name = "BaseAgent"

    def __init__(
        self,
        settings: Settings,
        logger: logging.Logger | None = None,
    ) -> None:
        self.settings = settings
        self.logger = logger or logging.getLogger("localquant.agents")

    @abstractmethod
    def run(self, context: AgentContext) -> AgentContext:
        """Run this agent and return the updated context."""

    def log_start(self, context: AgentContext) -> None:
        """Log the beginning of an agent step."""
        self.logger.info("%s started for symbol=%s", self.name, context.symbol)

    def log_finish(self, context: AgentContext) -> None:
        """Log the completion of an agent step."""
        self.logger.info("%s finished for symbol=%s", self.name, context.symbol)
