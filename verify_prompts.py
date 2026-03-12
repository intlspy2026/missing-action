import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to pythonpath
sys.path.append(str(Path(__file__).parent / "src"))

# Mocking modules that might require dependencies or credentials
sys.modules["mlflow"] = MagicMock()
sys.modules["mlflow.pyfunc"] = MagicMock()
sys.modules["databricks"] = MagicMock()
sys.modules["databricks.sdk"] = MagicMock()

# Mock the specific tools import since the directory might not exist locally
sys.modules["agents.orchestrator.tools.control_test"] = MagicMock()
sys.modules["agents.orchestrator.tools.control_test"].agent_tools = []

# Mock Config utils to avoid file loading issues
with patch("smart_investigator.foundation.utils.configs_utils.get_nginx_configs", return_value={}):
    from agents.orchestrator.master_agent_prompts import WELCOME_PROMPT
    from agents.orchestrator.master_agent_utils import IC_PROMPT_TEMPLATE

def test_welcome_prompt():
    print("\n--- Testing Welcome Prompt ---")
    print(f"Current Prompt:\n{WELCOME_PROMPT}")
    
    if "Hello!" in WELCOME_PROMPT and "Drafting" not in WELCOME_PROMPT and "Crafting" not in WELCOME_PROMPT:
        print("\n✅ SUCCESS: Welcome prompt is friendly.")
    else:
        print("\n⚠️ WARNING: Welcome prompt might need adjustment.")

def test_rationale_prompt():
    print("\n--- Testing Rationale Instructions (Intro) ---")
    
    # Check if the specific instructions are in the template
    required_phrases = [
        "friendly and professional",
        "Drafting",
        "never as 'the user'",
        "rationale' argument must"
    ]
    
    missing = [p for p in required_phrases if p not in IC_PROMPT_TEMPLATE]
    
    print(f"Template Snippet:\n{IC_PROMPT_TEMPLATE[:500]}...\n")
    
    if not missing:
        print("✅ SUCCESS: All tone/terminology constraints are present in the system prompt.")
    else:
        print(f"❌ FAILURE: Missing the following constraints: {missing}")

if __name__ == "__main__":
    test_welcome_prompt()
    test_rationale_prompt()
