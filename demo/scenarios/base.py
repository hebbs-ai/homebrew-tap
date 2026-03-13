"""Base class for scripted scenarios with assertion framework.

Every scenario:
  1. Connects to a running HEBBS server via gRPC
  2. Runs a predefined sequence of operations
  3. Validates assertions about HEBBS behavior
  4. Reports pass/fail with details

Adapted for async gRPC SDK (HebbsClient).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console

from demo.agent import SalesAgent
from demo.config import DemoConfig
from demo.display import DisplayManager, Verbosity


@dataclass
class Assertion:
    name: str
    passed: bool
    message: str = ""
    expected: Any = None
    actual: Any = None


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    assertions: list[Assertion] = field(default_factory=list)
    elapsed_ms: float = 0.0
    error: str | None = None

    @property
    def failed_assertions(self) -> list[Assertion]:
        return [a for a in self.assertions if not a.passed]


class Scenario(ABC):
    """Base class for scripted scenarios using the gRPC SDK."""

    name: str = "unnamed"
    description: str = ""

    def __init__(
        self,
        config: DemoConfig | None = None,
        verbosity: Verbosity = Verbosity.NORMAL,
        use_mock_llm: bool = True,
        console: Console | None = None,
    ) -> None:
        self._config = config or DemoConfig()
        self._verbosity = verbosity
        self._use_mock_llm = use_mock_llm
        self._console = console or Console()
        self._assertions: list[Assertion] = []

    def assert_true(self, name: str, condition: bool, message: str = "") -> None:
        self._assertions.append(Assertion(
            name=name, passed=condition, message=message,
        ))

    def assert_equal(self, name: str, expected: Any, actual: Any, message: str = "") -> None:
        self._assertions.append(Assertion(
            name=name, passed=(expected == actual),
            message=message or f"expected {expected}, got {actual}",
            expected=expected, actual=actual,
        ))

    def assert_gte(self, name: str, actual: int | float, minimum: int | float, message: str = "") -> None:
        self._assertions.append(Assertion(
            name=name, passed=(actual >= minimum),
            message=message or f"expected >= {minimum}, got {actual}",
            expected=f">= {minimum}", actual=actual,
        ))

    def assert_empty(self, name: str, collection: Any, message: str = "") -> None:
        is_empty = len(collection) == 0 if collection is not None else True
        self._assertions.append(Assertion(
            name=name, passed=is_empty,
            message=message or f"expected empty, got {len(collection) if collection else 0} items",
        ))

    def assert_not_empty(self, name: str, collection: Any, message: str = "") -> None:
        is_not_empty = len(collection) > 0 if collection is not None else False
        self._assertions.append(Assertion(
            name=name, passed=is_not_empty,
            message=message or "expected non-empty collection",
        ))

    async def _setup(self) -> tuple[Any, SalesAgent]:
        """Connect to a HEBBS server and create a SalesAgent."""
        from hebbs import HebbsClient
        hebbs = HebbsClient(self._config.hebbs.address)
        await hebbs.connect()
        display = DisplayManager(self._verbosity, self._console)
        agent = SalesAgent(
            config=self._config,
            hebbs=hebbs,
            display=display,
            use_mock_llm=self._use_mock_llm,
        )
        return hebbs, agent

    async def _cleanup_entities(self, hebbs: Any, entity_ids: list[str]) -> None:
        """Forget all memories for the given entities (idempotent cleanup)."""
        for eid in entity_ids:
            try:
                await hebbs.forget(entity_id=eid)
            except Exception:
                pass

    async def _teardown(self, hebbs: Any) -> None:
        """Close the HEBBS gRPC connection."""
        try:
            await hebbs.close()
        except Exception:
            pass

    async def run(self) -> ScenarioResult:
        """Execute the scenario and return results."""
        self._assertions = []
        t0 = time.perf_counter()

        try:
            hebbs, agent = await self._setup()
        except Exception as e:
            return ScenarioResult(
                name=self.name, passed=False, elapsed_ms=0,
                error=f"Setup failed: {e}",
            )

        try:
            await self.execute(hebbs, agent)
        except Exception as e:
            self._assertions.append(Assertion(
                name="scenario_execution", passed=False,
                message=f"Scenario raised exception: {e}",
            ))
        finally:
            await self._teardown(hebbs)

        elapsed = (time.perf_counter() - t0) * 1000
        all_passed = all(a.passed for a in self._assertions)

        return ScenarioResult(
            name=self.name,
            passed=all_passed,
            assertions=list(self._assertions),
            elapsed_ms=elapsed,
        )

    @abstractmethod
    async def execute(self, hebbs: Any, agent: SalesAgent) -> None:
        """Run the scenario's conversation and assertions.

        Subclasses implement this method. Use self.assert_* methods to record
        assertions that will be checked after execution.
        """
        ...
