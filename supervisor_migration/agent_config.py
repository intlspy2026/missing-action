"""
Agent Configuration

Defines agent endpoints with the is_workflow flag for workflow management.
Only includes decline_letter and smart_strategy agents as per requirements.
"""

from typing import TypedDict, Optional
from pydantic import BaseModel, Field


class RequiredInput(BaseModel):
    """Definition of a required input field for an agent."""
    name: str = Field(description="Field name (snake_case)")
    display_name: str = Field(description="Human-readable name for prompts")
    description: str = Field(description="Description of what this field is for")
    example: str = Field(default="", description="Example value for user guidance")


class AgentEndpointConfig(TypedDict):
    """Configuration for a single agent endpoint."""
    endpoint_name: str
    description: str
    introduction: str
    expose_to_user: bool
    can_generate_task: bool
    is_workflow: bool  # True = workflow agent
    use_checkpointer: bool
    text_annotation: Optional[str]
    rationale_annotation: Optional[str]
    required_inputs: Optional[list[RequiredInput]]  # Inputs to collect before calling agent


# Required inputs for smart_strategy agent
SMART_STRATEGY_REQUIRED_INPUTS = [
    RequiredInput(
        name="claim_id",
        display_name="Claim ID",
        description="The unique identifier for the insurance claim",
        example="CLM-2024-001234",
    ),
    RequiredInput(
        name="policy_number",
        display_name="Policy Number",
        description="The policy number associated with the claim",
        example="POL-ABC-123456",
    ),
    RequiredInput(
        name="date_range",
        display_name="Date Range",
        description="The date range for the search (e.g., start and end dates)",
        example="2024-01-01 to 2024-12-31",
    ),
    RequiredInput(
        name="customer_name",
        display_name="Customer Name",
        description="The name of the customer or policyholder",
        example="John Smith",
    ),
]

# Agent endpoint configurations - only decline_letter and smart_strategy
AGENT_ENDPOINTS: dict[str, AgentEndpointConfig] = {
    "decline_letter": {
        "endpoint_name": "decline-letter-agent",
        "description": "Crafts standardized declined letters for insurance claims based on claim details. Use this when the user needs help drafting a decline letter for a claim.",
        "introduction": "I can help you draft a declined letter for an insurance claim.",
        "expose_to_user": True,
        "can_generate_task": True,
        "is_workflow": True,
        "use_checkpointer": False,
        "text_annotation": "The claim details or information needed for drafting the decline letter.",
        "rationale_annotation": "Explanation of why this tool is appropriate for the user's request.",
        "required_inputs": None,  # No upfront inputs required
    },
    "smart_strategy": {
        "endpoint_name": "smart-strategy-agent",
        "description": "Helps find claim IDs, policy information, and related claim details. Use this when the user needs to look up information about claims or policies.",
        "introduction": "I can help you find your claim ID or policy information.",
        "expose_to_user": True,
        "can_generate_task": True,
        "is_workflow": True,
        "use_checkpointer": False,
        "text_annotation": "The search query or information to look up.",
        "rationale_annotation": "Explanation of why this tool is appropriate for the user's request.",
        "required_inputs": SMART_STRATEGY_REQUIRED_INPUTS,  # Collect these before calling
    },
}

# HITL agent name constant
HITL_AGENT_NAME = "human_in_the_loop"

# Master agent name constant
SUPERVISOR_AGENT_NAME = "supervisor"


def get_workflow_agents() -> list[str]:
    """Get list of workflow agent names."""
    return [name for name, cfg in AGENT_ENDPOINTS.items() if cfg["is_workflow"]]


def get_non_workflow_agents() -> list[str]:
    """Get list of non-workflow agent names."""
    return [name for name, cfg in AGENT_ENDPOINTS.items() if not cfg["is_workflow"]]


def get_exposed_agents() -> list[str]:
    """Get list of agents exposed to user."""
    return [name for name, cfg in AGENT_ENDPOINTS.items() if cfg["expose_to_user"]]


def get_agents_introduction() -> str:
    """Get formatted introduction string for all exposed agents."""
    return "\n".join(
        f"- {name}: {cfg['introduction']}"
        for name, cfg in AGENT_ENDPOINTS.items()
        if cfg["expose_to_user"]
    )


def get_agents_description_string() -> str:
    """Get formatted description string for all exposed agents."""
    return "\n".join(
        f"- {name}: {cfg['description']}"
        for name, cfg in AGENT_ENDPOINTS.items()
        if cfg["expose_to_user"]
    )


def get_agent_config(agent_name: str) -> Optional[AgentEndpointConfig]:
    """Get configuration for a specific agent."""
    return AGENT_ENDPOINTS.get(agent_name)


def is_workflow_agent(agent_name: str) -> bool:
    """Check if an agent is a workflow agent."""
    config = AGENT_ENDPOINTS.get(agent_name)
    return config["is_workflow"] if config else False


def get_task_string() -> str:
    """Get formatted task string for prompts."""
    return "\n- ".join(get_exposed_agents())


def get_required_inputs(agent_name: str) -> list[RequiredInput]:
    """Get required inputs for an agent, or empty list if none."""
    config = AGENT_ENDPOINTS.get(agent_name)
    if config and config.get("required_inputs"):
        return config["required_inputs"]
    return []


def get_missing_inputs(agent_name: str, provided_inputs: dict) -> list[RequiredInput]:
    """
    Get list of required inputs that are missing from provided_inputs.

    Args:
        agent_name: Name of the agent
        provided_inputs: Dict of inputs already provided by user

    Returns:
        List of RequiredInput that are missing or empty
    """
    required = get_required_inputs(agent_name)
    missing = []
    for req_input in required:
        value = provided_inputs.get(req_input.name, "")
        if not value or (isinstance(value, str) and not value.strip()):
            missing.append(req_input)
    return missing


def format_input_collection_prompt(agent_name: str, missing_inputs: list[RequiredInput]) -> str:
    """
    Format a prompt asking user to provide missing inputs.

    Args:
        agent_name: Name of the agent
        missing_inputs: List of missing RequiredInput

    Returns:
        Formatted prompt string
    """
    config = AGENT_ENDPOINTS.get(agent_name, {})
    intro = config.get("introduction", f"I need some information to help you with {agent_name}.")

    fields_str = "\n".join([
        f"- **{inp.display_name}**: {inp.description}" + (f" (e.g., {inp.example})" if inp.example else "")
        for inp in missing_inputs
    ])

    return f"""{intro}

Please provide the following information:
{fields_str}"""
