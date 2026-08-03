import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.providers.ollama_provider import OllamaProvider
from agents.intent_agent import IntentAgent

def test():
    print("Testing IntentAgent...")
    provider = OllamaProvider()
    agent = IntentAgent(provider=provider, model_name="llama3.2:1b")
    
    # Test cases that previously relied on regex, plus some nuanced ones
    prompts = [
        "Please generate a PDF report of my expenses",
        "Can you create a python script that sorts an array?",
        "I need a spreadsheet to track my workouts",
        "Plot a bar chart of the sales data",
        "What is the capital of France?",
        "Translate 'hello world' to French",
        "Draft an email to my boss about the meeting"
    ]
    
    for p in prompts:
        print(f"\nPrompt: '{p}'")
        try:
            result = agent.classify(p)
            print(f"  -> Intent: {result.get('intent')}, Confidence: {result.get('confidence')}")
        except Exception as e:
            print(f"  -> Error: {e}")

if __name__ == "__main__":
    test()
