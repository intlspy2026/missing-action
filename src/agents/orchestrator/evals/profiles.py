"""
Master Agent Evaluation Profiles

Each profile defines:
- trace_filter: MLflow filter string for trace selection
- metrics: List of metric IDs to apply
- extractor: (Optional) span extractor function name for span-level evaluation

Profiles can use trace tags set by the Master Agent:

Tags:
- tags.workflow_name: Active workflow name
- tags.workflow_finished: "true" or "false"
"""

MASTER_AGENT_PROFILES = {
    # Routing plausibility - evaluates intent_classifier routing decisions
    "routing": {
        "trace_filter": "status = 'OK'",
        "metrics": ["routing_plausibility"],
        "extractor": "get_routing_spans",  # Span-level extraction
    },

    # Tone compliance - evaluates MasterAgent responses in human_in_the_loop
    "tone": {
        "trace_filter": "status = 'OK'",
        "metrics": ["tone_compliance"],
        "extractor": "get_tone_spans",  # Span-level extraction
    },
}


def get_profiles(profile_names: list = None) -> dict:
    """
    Get evaluation profiles.

    Args:
        profile_names: Optional list of profile names to retrieve.
                      If None, returns all profiles.

    Returns:
        Dictionary of profile configurations.
    """
    if profile_names is None:
        return MASTER_AGENT_PROFILES

    return {
        name: MASTER_AGENT_PROFILES[name]
        for name in profile_names
        if name in MASTER_AGENT_PROFILES
    }
