import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory.prompt_builder import PromptBuilder, PromptSection

def test_builder():
    builder = PromptBuilder()
    
    # Adding out of order
    builder.add_section(PromptSection.CONVERSATION_HISTORY, "User: Hi\nAssistant: Hello", title="Conversation")
    builder.add_section(PromptSection.CORE_IDENTITY, "You are Mimir.")
    builder.add_section(PromptSection.CRITICAL_RULES, "Rule 1: Be helpful.")
    
    # Empty content should be ignored
    builder.add_section(PromptSection.WORKING_MEMORY, "   ")
    
    result = builder.build()
    
    print("--- RENDERED PROMPT ---")
    print(result)
    print("-----------------------")
    
    # Assertions
    assert "You are Mimir." in result
    assert "=== CONVERSATION ===" in result
    assert "Rule 1" in result
    
    # Core Identity should come before Conversation
    assert result.index("You are Mimir.") < result.index("=== CONVERSATION ===")
    
    print("PromptBuilder test passed!")

if __name__ == "__main__":
    test_builder()
