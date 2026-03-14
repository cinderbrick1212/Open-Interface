"""State definition for the LangGraph execution agent."""

from typing import Any, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """State flowing through the LangGraph execution graph.

    Fields:
        user_request: The original user request string.
        step_num: Current step count (0-indexed). Incremented after each plan.
        instructions: The latest LLM response dict ({steps: [...], done: ...}).
        done: None while in progress; a string message when the task is complete.
        error: None unless an error occurred during execution.
        dom_context: Optional[dict] containing interactive DOM nodes if available.
    """
    user_request: str
    step_num: int
    instructions: dict[str, Any]
    done: Optional[str]
    error: Optional[str]
    dom_context: Optional[dict[str, Any]]
