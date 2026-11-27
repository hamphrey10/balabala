"""Agent interface tests."""

from __future__ import annotations

from quant_deriv_ai.agents.base import AgentContext, AgentState, BaseAgent
from quant_deriv_ai.core.event_bus import EventBus


class _ProbeAgent(BaseAgent):
    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.ran = False
        self.shut = False

    def run(self) -> None:
        self.ran = True

    def shutdown(self) -> None:
        self.shut = True


def test_agent_lifecycle() -> None:
    ctx = AgentContext(name="probe", bus=EventBus())
    agent = _ProbeAgent(ctx)
    assert agent.state is AgentState.CREATED
    agent.start()
    assert agent.ran is True
    assert agent.state is AgentState.RUNNING
    agent.stop()
    assert agent.shut is True
    assert agent.state is AgentState.STOPPED
