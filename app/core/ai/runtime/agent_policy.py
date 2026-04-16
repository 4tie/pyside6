from dataclasses import dataclass, field
from typing import List


@dataclass
class AgentPolicy:
    """Policy configuration governing agent behaviour, tool usage, and safety rules.

    Attributes:
        system_prompt: The system-level instruction given to the AI model.
        tool_usage_policy: Guidance on when and how the agent should invoke tools.
        safety_rules: List of rules the agent must enforce in every response.
    """

    system_prompt: str
    tool_usage_policy: str
    safety_rules: List[str] = field(default_factory=list)


def default_policy() -> AgentPolicy:
    """Return the default read-and-advise agent policy.

    Returns:
        AgentPolicy pre-configured with a read-and-advise system prompt,
        a conservative tool usage policy, and a credential-redaction safety rule.
    """
    return AgentPolicy(
        system_prompt=(
            "You are a read-and-advise AI assistant for the Freqtrade GUI application. "
            "You help users understand their trading strategies, backtest results, and "
            "application state. You must not claim to execute trades, write files, or "
            "modify application state without explicit user confirmation. "
            "Use tools only when necessary to answer the user's question."
        ),
        tool_usage_policy=(
            "Use tools only when the user's question requires current application data. "
            "Prefer answering from context when possible."
        ),
        safety_rules=[
            "Never output raw API keys, bearer tokens, or credentials in responses. "
            "Strip or redact any string matching patterns like sk-..., Bearer ..., "
            "or similar secret patterns."
        ],
    )
